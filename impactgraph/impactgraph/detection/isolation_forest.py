"""Per-component Isolation Forest anomaly detection with calibrated scores and feature-level explanations.

* One IsolationForest per component, trained ONLY on normal simulated behaviour (training episodes).
* Raw scores are mapped to [0,1] by the empirical CDF of scores on held-out NORMAL validation episodes
  (percentile calibration), so scores are comparable across components. A high score means "unusual
  compared with this component's normal behaviour", NOT "confirmed attack".
* An alert needs score >= quantile for ALERT_PERSISTENCE consecutive steps.
* use_residual=False disables the physics-consistency (mass-balance) feature for ablation.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ..config import settings
from ..ingestion.telemetry_generator import detection_features


class NodeAnomalyDetector:
    def __init__(self, ig, use_residual: bool = True, n_estimators: int = 100, seed: int = 0):
        self.ig, self.use_residual, self.n_estimators, self.seed = ig, use_residual, n_estimators, seed
        self.models, self.stats, self.cal, self.feats = {}, {}, {}, {}

    def _features(self, node) -> list:
        f = detection_features(node)
        if not self.use_residual and "flow_residual_m3h" in f:
            f.remove("flow_residual_m3h")
        return f

    def fit(self, normal_df: pd.DataFrame, val_df: pd.DataFrame) -> "NodeAnomalyDetector":
        for n in self.ig.nodes:
            f = self._features(n)
            tr = normal_df[normal_df.component_id == n.id][f].to_numpy(float)
            mu, sd = tr.mean(0), tr.std(0) + 1e-6
            m = IsolationForest(n_estimators=self.n_estimators, random_state=self.seed + zlib.crc32(n.id.encode()) % 1000,
                                contamination="auto").fit((tr - mu) / sd)
            va = val_df[val_df.component_id == n.id][f].to_numpy(float)
            raw = -m.score_samples((va - mu) / sd)
            self.models[n.id], self.stats[n.id], self.feats[n.id] = m, (mu, sd), f
            self.cal[n.id] = np.sort(raw)
        return self

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[["episode_id", "step", "component_id"]].copy()
        out["raw_score"] = np.nan
        out["anomaly_score"] = np.nan
        for n in self.ig.nodes:
            idx = df.component_id == n.id
            f = self.feats[n.id]
            X = df.loc[idx, f].to_numpy(float)
            mu, sd = self.stats[n.id]
            raw = -self.models[n.id].score_samples((X - mu) / sd)
            cal = self.cal[n.id]
            out.loc[idx, "raw_score"] = raw
            out.loc[idx, "anomaly_score"] = np.searchsorted(cal, raw, side="right") / len(cal)
        return out

    def alerts(self, scored: pd.DataFrame, quantile: float = settings.ALERT_QUANTILE,
               persistence: int = settings.ALERT_PERSISTENCE) -> pd.DataFrame:
        s = scored.sort_values(["episode_id", "component_id", "step"]).copy()
        s["above"] = (s.anomaly_score >= quantile).astype(int)
        s["run"] = s.groupby(["episode_id", "component_id"]).above.transform(
            lambda x: x.rolling(persistence, min_periods=persistence).sum())
        s["alert"] = (s.run >= persistence)
        return s.drop(columns=["run"])

    def explain(self, df: pd.DataFrame, component_id: str, step: int, episode_id: str = None, top: int = 3) -> list:
        """Top features by standardised deviation from this component's normal behaviour."""
        sel = (df.component_id == component_id) & (df.step == step)
        if episode_id is not None:
            sel &= df.episode_id == episode_id
        row = df[sel].iloc[0]
        mu, sd = self.stats[component_id]
        f = self.feats[component_id]
        z = (row[f].to_numpy(float) - mu) / sd
        order = np.argsort(-np.abs(z))[:top]
        return [{"feature": f[i], "value": float(row[f[i]]), "normal_mean": float(mu[i]), "z": float(z[i])}
                for i in order]
