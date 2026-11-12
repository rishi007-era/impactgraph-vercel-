"""Detection evaluation on HELD-OUT episodes (different seeds from training and validation episodes).

Node-step metrics treat every (component, minute) as a sample: positive = ground-truth anomalous label.
Event-level metrics ask: for each injected anomaly episode on a component, was an alert raised during it, and how late?
Ablation: the same evaluation is run without the physics-consistency (mass-balance residual) feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..ingestion.telemetry_generator import generate_episode
from ..simulation.monte_carlo import MonteCarloEngine
from ..simulation.scenarios import SCENARIOS


def build_test_episodes(ig, model, seed: int = 5000, per_scenario: int = 6, normal: int = 6) -> pd.DataFrame:
    frames, k = [], 0
    for sid, sc in SCENARIOS.items():
        eng = MonteCarloEngine(ig, sc, 200, seed + k, model=model)
        rng = np.random.default_rng(seed + 50 + k)
        picked = 0
        for i in rng.permutation(200):
            tr = eng.trace_for_trial(int(i))
            if not tr["compromised"] and not tr["failed"]:
                continue
            frames.append(generate_episode(ig, seed + 1000 + 10 * k + picked, trace=tr,
                                           episode_id=f"test_{sid}_{picked}", scenario_id=sid))
            picked += 1
            if picked >= per_scenario:
                break
        k += 1
    # targeted rupture / valve / pump stress episodes (physics-consistency check)
    stress = {"rupture_PH02": {"PH02": (0.0, "sabotage")}, "rupture_PH05": {"PH05": (0.0, "sabotage")},
              "valve_PH03": {"PH03": (0.0, "sabotage")}, "pump_PH04": {"PH04": (0.0, "actuation")}}
    for name, failed in stress.items():
        for j in range(3):
            frames.append(generate_episode(ig, seed + 3000 + 7 * j + len(name), trace={"compromised": {}, "failed": failed, "services": {}},
                                           episode_id=f"test_{name}_{j}", scenario_id="stress"))
    for j in range(normal):
        frames.append(generate_episode(ig, seed + 4000 + j, episode_id=f"test_normal_{j}", scenario_id="normal"))
    return pd.concat(frames, ignore_index=True)


def _node_step_metrics(df, alerts) -> dict:
    m = df.merge(alerts[["episode_id", "step", "component_id", "alert", "anomaly_score"]],
                 on=["episode_id", "step", "component_id"])
    y, p = (m.label != "normal").to_numpy(), m.alert.fillna(False).to_numpy().astype(bool)
    tp = int((y & p).sum()); fp = int((~y & p).sum()); tn = int((~y & ~p).sum()); fn = int((y & ~p).sum())
    prec, rec = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / max(1e-12, prec + rec), "fpr": fp / max(1, fp + tn), "fnr": fn / max(1, fn + tp),
            "accuracy": (tp + tn) / max(1, len(m)), "samples": int(len(m))}, m


def _events(ig, m) -> pd.DataFrame:
    rows = []
    for (ep, cid), g in m.sort_values("step").groupby(["episode_id", "component_id"]):
        for lab in ("ransomware", "physical_failure", "cyber_activity"):
            sub = g[g.label == lab]
            if sub.empty:
                continue
            onset = int(sub.step.min())
            win = g[(g.step >= onset) & (g.step <= int(sub.step.max()) + 10)]
            hit = win[win.alert.fillna(False).astype(bool)]
            rows.append({"episode_id": ep, "component_id": cid, "type": lab, "node_type": ig.node(cid).node_type.value,
                         "onset": onset, "detected": not hit.empty,
                         "delay": int(hit.step.min() - onset) if not hit.empty else np.nan})
    return pd.DataFrame(rows)


def evaluate_detectors(ig, model, det, det_ablation) -> dict:
    df = build_test_episodes(ig, model)
    out = {"n_episodes": int(df.episode_id.nunique()), "n_samples": int(len(df))}
    for name, d in (("with_residual", det), ("without_residual", det_ablation)):
        alerts = d.alerts(d.score(df))
        ns, merged = _node_step_metrics(df, alerts)
        ev = _events(ig, merged)
        by_type = (ev.groupby("type").agg(events=("detected", "size"), detected=("detected", "mean"),
                                           median_delay=("delay", "median")).reset_index().to_dict("records")) if len(ev) else []
        by_node_type = (ev[ev.type == "physical_failure"].groupby("node_type").agg(events=("detected", "size"),
                        detected=("detected", "mean"), median_delay=("delay", "median")).reset_index().to_dict("records")) if len(ev) else []
        # per-label node-step recall
        lab_recall = {lab: float(g.alert.fillna(False).astype(bool).mean()) for lab, g in merged.groupby("label") if lab != "normal"}
        out[name] = {"node_step": ns, "event_by_type": by_type, "physical_by_node_type": by_node_type,
                     "label_recall": lab_recall}
    return out
