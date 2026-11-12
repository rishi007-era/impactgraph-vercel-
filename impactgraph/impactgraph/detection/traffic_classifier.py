"""Supervised network-traffic attack classifier (UNSW-NB15) and the flow bridge to the infrastructure graph.

This module is SEPARATE from industrial-telemetry anomaly detection. UNSW-NB15 is lab-generated enterprise
traffic; it does not represent Colonial Pipeline traffic. The bridge below is an explicit ASSUMPTION: flows
sampled from the dataset stand in for the traffic of IT/vendor components during simulated incidents.
"""
from __future__ import annotations

import json
import os
import time

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support)

from ..ingestion.dataset_loader import PreparedData

MODEL_PATH = os.path.join("data", "models", "traffic_rf.joblib")
METRICS_PATH = os.path.join("results", "classifier_metrics.json")


def train(data: PreparedData, seed: int = 42):
    t0 = time.perf_counter()
    clf = RandomForestClassifier(n_estimators=60, max_depth=16, min_samples_leaf=2,
                                 class_weight="balanced_subsample", n_jobs=1, random_state=seed)
    clf.fit(data.X_train, data.y_train)
    return clf, time.perf_counter() - t0


def _metrics(clf, X, y) -> dict:
    pred = clf.predict(X)
    classes = list(clf.classes_)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=classes, zero_division=0)
    cm = confusion_matrix(y, pred, labels=classes)
    y_bin, p_bin = (y != "Normal").to_numpy(), (pred != "Normal")
    tp = int((y_bin & p_bin).sum()); fp = int((~y_bin & p_bin).sum())
    tn = int((~y_bin & ~p_bin).sum()); fn = int((y_bin & ~p_bin).sum())
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "classes": classes,
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i, c in enumerate(classes)},
        "confusion_matrix": cm.tolist(),
        "binary": {"precision": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn),
                   "f1": 2 * tp / max(1, 2 * tp + fp + fn), "fpr": fp / max(1, fp + tn), "fnr": fn / max(1, fn + tp),
                   "tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def evaluate(clf, data: PreparedData, train_seconds: float) -> dict:
    m = {"dataset": "UNSW-NB15 official training partition, re-split 60/20/20 (stratified by attack category)",
         "n_raw": data.n_raw, "n_after_dedup": data.n_after_dedup, "n_conflicting_dropped": data.n_conflicts_dropped,
         "n_features": len(data.features), "train_seconds": train_seconds,
         "class_counts_raw": {k: int(v) for k, v in data.class_counts_raw.items()},
         "class_counts_train": {k: int(v) for k, v in data.y_train.value_counts().items()},
         "validation": _metrics(clf, data.X_val, data.y_val), "test": _metrics(clf, data.X_test, data.y_test)}
    imp = sorted(zip(data.features, clf.feature_importances_), key=lambda x: -x[1])[:10]
    m["top_features"] = [{"feature": f, "importance": float(v)} for f, v in imp]
    return m


def load_or_train(data: PreparedData, seed: int = 42, force: bool = False):
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    if not force and os.path.exists(MODEL_PATH) and os.path.exists(METRICS_PATH):
        return joblib.load(MODEL_PATH), json.load(open(METRICS_PATH))
    clf, secs = train(data, seed)
    metrics = evaluate(clf, data, secs)
    joblib.dump(clf, MODEL_PATH, compress=3)
    json.dump(metrics, open(METRICS_PATH, "w"), indent=2)
    return clf, metrics


class FlowBridge:
    """Samples classifier attack-probabilities for flows attributed to a component (assumption, see module doc)."""

    def __init__(self, clf, data: PreparedData, pool: int = 3000, seed: int = 0):
        rng = np.random.default_rng(seed)
        y = data.y_test.to_numpy()
        classes = list(clf.classes_)
        normal_idx = classes.index("Normal")
        self.p_benign = self._probs(clf, data.X_test[y == "Normal"], rng, pool, normal_idx)
        self.p_attack = self._probs(clf, data.X_test[y != "Normal"], rng, pool, normal_idx)
        # calibration: 95th percentile of rolling-mean attack probability on BENIGN traffic
        w = 5
        sample = rng.choice(self.p_benign, size=(2000, w)).mean(axis=1)
        self.benign_ref = float(np.quantile(sample, 0.95))

    @staticmethod
    def _probs(clf, X, rng, pool, normal_idx):
        idx = rng.choice(len(X), size=min(pool, len(X)), replace=False)
        return 1.0 - clf.predict_proba(X.iloc[idx])[:, normal_idx]

    def node_evidence(self, episode_df, seed: int = 0, attack_share: float = 0.7, window: int = 5) -> dict:
        """Per cyber component: calibrated (benign-referenced) max rolling attack-probability, in [0,1]."""
        rng = np.random.default_rng(seed)
        out = {}
        cyber = episode_df[episode_df.zone != "physical"]
        for nid, g in cyber.groupby("component_id"):
            g = g.sort_values("step")
            active = g.label.isin(["cyber_activity", "ransomware"]).to_numpy()
            use_attack = active & (rng.random(len(g)) < attack_share)
            p = np.where(use_attack, rng.choice(self.p_attack, len(g)), rng.choice(self.p_benign, len(g)))
            roll = np.convolve(p, np.ones(window) / window, mode="valid")
            # 0 = within normal benign variation, 1 = classifier fully convinced
            out[nid] = float(np.clip((roll.max() - self.benign_ref) / (1.0 - self.benign_ref), 0.0, 1.0))
        return out
