"""End-to-end experiment runner: telemetry -> detection -> attack/failure simulation -> risk -> containment -> persistence.

Every number written to the database comes from actual execution of this pipeline (no hand-entered results).

Usage:
    python -m impactgraph.experiments.runner --db impactgraph.db --trials 500 --seed 42
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import resource
import time

import numpy as np
import pandas as pd
import sklearn

from ..attack_analysis.path_analysis import reachability, top_paths
from ..config import settings
from ..database.repository import Repository
from ..detection import traffic_classifier as tc
from ..detection.evaluation import evaluate_detectors
from ..detection.isolation_forest import NodeAnomalyDetector
from ..infrastructure.graph_validator import validate_graph
from ..infrastructure.topology import PHASE1_ZONE_COUNTS, build_phase1_topology
from ..ingestion import dataset_loader
from ..ingestion.telemetry_generator import generate_episode
from ..optimization.strategies import (FULL_SHUTDOWN, IMPACTGRAPH, INITIAL_COMPONENT, NO_ISOLATION, Strategy,
                                       evaluate_strategy, greedy_isolation, initial_component_edges, robustness_test)
from ..resilience.resilience_metrics import summarize
from ..risk.criticality import single_points_of_failure
from ..risk.risk_scoring import risk_table, zone_risk
from ..simulation.monte_carlo import MonteCarloEngine
from ..simulation.propagation import PropagationModel
from ..simulation.scenarios import SCENARIOS


class DummyBridge:
    """Used only in unit tests when the dataset is not loaded."""
    def node_evidence(self, episode_df, **kw):
        return {}


@dataclasses.dataclass
class Artifacts:
    det: NodeAnomalyDetector
    det_abl: NodeAnomalyDetector
    bridge: object
    classifier_metrics: dict
    detection_metrics: dict


def build_artifacts(ig, model, use_classifier=True, log=print) -> Artifacts:
    t = time.time()
    normal = pd.concat([generate_episode(ig, 100 + i, episode_id=f"train{i}") for i in range(6)], ignore_index=True)
    val = pd.concat([generate_episode(ig, 200 + i, episode_id=f"val{i}") for i in range(3)], ignore_index=True)
    # PRIMARY detector: raw telemetry features only. The mass-balance residual variant is kept as an ablation:
    # on held-out episodes it did not improve detection in Phase 1 (see docs/limitations); this choice was made
    # AFTER seeing that ablation, so the reported primary metrics are slightly optimistic.
    det = NodeAnomalyDetector(ig, use_residual=False).fit(normal, val)
    det_abl = NodeAnomalyDetector(ig, use_residual=True).fit(normal, val)
    log(f"  detectors trained ({time.time() - t:.1f}s): 6 train / 3 validation normal episodes")
    t = time.time()
    det_metrics = evaluate_detectors(ig, model, det_abl, det)   # (with_residual, without_residual)
    log(f"  detection evaluated on {det_metrics['n_episodes']} held-out episodes ({time.time() - t:.1f}s)")
    if use_classifier:
        t = time.time()
        data = dataset_loader.prepare()
        clf, cm = tc.load_or_train(data)
        bridge = tc.FlowBridge(clf, data)
        log(f"  traffic classifier ready ({time.time() - t:.1f}s): test macro-F1 {cm['test']['macro_f1']:.3f}")
    else:
        bridge, cm = DummyBridge(), {}
    return Artifacts(det, det_abl, bridge, cm, det_metrics)


def _replay_frames(ig, trace):
    comp, failed, cond = trace["compromised"], trace["failed"], trace["conditions"]
    nodes = pd.DataFrame([{"component_id": n.id, "t_compromised": comp.get(n.id, np.nan),
                           "t_failed": failed[n.id][0] if n.id in failed else np.nan,
                           "fail_kind": failed[n.id][1] if n.id in failed else "",
                           "condition": cond[n.id].value} for n in ig.nodes])
    rows, seen = [], set()
    for eid, t0, t1 in trace["used_edges"]:
        e = ig.edge(eid)
        eff = (e.target in comp and abs(comp[e.target] - t1) < 1e-9) or (e.target in failed and abs(failed[e.target][0] - t1) < 1e-9)
        if eff and eid not in seen:
            seen.add(eid)
            rows.append({"edge_id": eid, "t_start": t0, "t_end": t1})
    return nodes, pd.DataFrame(rows, columns=["edge_id", "t_start", "t_end"])


def _peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run_scenario(ig, model, art: Artifacts, repo: Repository, config_id: int, sid: str, seed: int, trials: int, log=print) -> int:
    sc = SCENARIOS[sid]
    t_start = time.perf_counter()
    repo.save_scenario(sc)
    params = {"seed": seed, "trials": trials, "search_trials": settings.SEARCH_TRIALS, "holdout_trials": settings.HOLDOUT_TRIALS,
              "impact_weights": settings.IMPACT_WEIGHTS, "risk_weights": settings.RISK_LIKELIHOOD_WEIGHTS,
              "consequence_weights": settings.RISK_CONSEQUENCE_WEIGHTS, "lambda": settings.LAMBDA, "cost_ref": settings.COST_REF,
              "min_continuity": settings.MIN_CONTINUITY, "scenario": dataclasses.asdict(sc) | {
                  "allowed_zones": [z.value for z in sc.allowed_zones] if sc.allowed_zones else None,
                  "ransomware_zones": sorted(z.value for z in sc.ransomware_zones),
                  "entry_nodes": [[n, sorted(c)] for n, c in sc.entry_nodes]},
              "dataset": "UNSW-NB15 official training partition (re-split)", "sklearn": sklearn.__version__,
              "python": platform.python_version()}
    run_id = repo.new_run(sid, config_id, seed, trials, params)
    metrics = []
    M = lambda cat, name, val, detail=None: metrics.append({"category": cat, "metric": name, "value": float(val), "detail": json.dumps(detail) if detail is not None else None})
    log(f"[{sid}] {sc.name}")

    # 1. baseline Monte Carlo (no isolation)
    eng = MonteCarloEngine(ig, sc, trials, seed, model=model)
    base = eng.run(keep_trace=True)
    M("performance", "mc_trials_per_second", trials / max(base.runtime_s, 1e-9))
    prop = pd.DataFrame([{"component_id": i, "p_compromised": base.freq_compromised[i], "p_failed": base.freq_failed[i],
                          "p_degraded": base.freq_degraded[i], "p_affected": base.freq_affected[i],
                          "ci_low": base.ci_affected[i][0], "ci_high": base.ci_affected[i][1],
                          "mean_time": base.mean_time_compromise[i]} for i in base.freq_affected])
    repo.save_df("propagation_results", prop, run_id)
    log(f"   baseline: impact {base.mean('impact'):.3f}  throughput {base.mean('throughput'):.3f}  ({base.runtime_s:.2f}s)")

    # 2. telemetry from the representative trajectory -> detection -> classifier evidence
    trace = base.rep_trace
    ep = generate_episode(ig, seed + 11, trace=trace, episode_id=f"{sid}_rep", scenario_id=sid)
    scored = art.det.score(ep)
    alerts = art.det.alerts(scored)
    A = {}
    for cid, g in scored.sort_values("step").groupby("component_id"):
        s = g.anomaly_score.to_numpy()
        A[cid] = float(np.max(np.minimum(s[1:], s[:-1]))) if len(s) > 1 else float(s.max())
    N = art.bridge.node_evidence(ep, seed=seed)
    repo.save_df("telemetry", ep, run_id)
    repo.save_df("anomaly_scores", alerts[["step", "component_id", "anomaly_score", "alert"]].assign(alert=lambda d: d.alert.astype(int)), run_id)
    rows = []
    for cid, g in alerts.groupby("component_id"):
        fa = g[g.alert].step.min() if g.alert.any() else None
        expl = art.det.explain(ep, cid, int(fa), f"{sid}_rep") if fa is not None and not np.isnan(fa) else []
        rows.append({"component_id": cid, "max_score": A.get(cid, 0.0), "first_alert_step": None if fa is None or np.isnan(fa) else int(fa),
                     "explanation": json.dumps(expl)})
    repo.save_df("anomaly_results", pd.DataFrame(rows), run_id)
    y = ep.label != "normal"
    m = ep.merge(alerts[["step", "component_id", "alert"]], on=["step", "component_id"])
    tp = int(((m.label != "normal") & m.alert).sum()); fp = int(((m.label == "normal") & m.alert).sum()); fn = int(((m.label != "normal") & ~m.alert).sum())
    M("detection_episode", "alerts_true_positive_steps", tp); M("detection_episode", "alerts_false_positive_steps", fp)
    M("detection_episode", "missed_anomalous_steps", fn)

    # 3. risk assessment
    rt = risk_table(ig, base.freq_affected, A, N)
    repo.con.execute("INSERT INTO risk_scores VALUES (?,?)", (run_id, rt.to_json(orient="records")))
    repo.save_blob(run_id, "zone_risk", zone_risk(rt).to_dict("records"))
    repo.save_blob(run_id, "single_points_of_failure", single_points_of_failure(ig, model))
    log(f"   risk: top component {rt.iloc[0].component_id} ({rt.iloc[0].risk:.3f}); detection episode TP/FP/FN steps {tp}/{fp}/{fn}")

    # 4. attack-path analysis
    src = sc.entry_nodes[0][0] if sc.entry_nodes else "OT06"
    path_rows = []
    for tgt in sc.focus_targets:
        for r, p in enumerate(top_paths(ig, sc, src, tgt, k=3), start=1):
            path_rows.append({"rank": r, "target": tgt, "probability": p["probability"], "path_json": json.dumps(p)})
    repo.save_df("attack_paths", pd.DataFrame(path_rows, columns=["rank", "target", "probability", "path_json"]), run_id)
    repo.save_blob(run_id, "reachability", reachability(ig, sc, src))

    # 5. containment strategies
    t = time.perf_counter()
    greedy = greedy_isolation(ig, sc, model, seed=seed + 1)
    t_greedy = time.perf_counter() - t
    strategies = [Strategy(NO_ISOLATION), Strategy(INITIAL_COMPONENT, initial_component_edges(ig, sc)),
                  Strategy(FULL_SHUTDOWN, shutdown=True), greedy]
    eval_eng = MonteCarloEngine(ig, sc, trials, seed + 1000, model=model)
    for st in strategies:
        ev, res = evaluate_strategy(ig, model, sc, st, eval_eng)
        d = dataclasses.asdict(ev)
        d["throughput_hist"] = np.histogram(res.throughput, bins=np.linspace(0, 1, 11))[0].tolist()
        d["impact_hist"] = np.histogram(res.impact, bins=np.linspace(0, 1, 21))[0].tolist()
        d["resilience"] = summarize(ig, model, res, st.isolated)
        repo.con.execute("INSERT INTO strategy_results VALUES (?,?,?)", (run_id, st.key, json.dumps(d, default=float)))
        for k in ("impact", "throughput", "hazard", "blast_weighted", "phys_hit", "objective", "cost", "n_isolated", "constraints_violated"):
            M("containment/" + st.key, k, d[k])
        for k, v in d["resilience"].items():
            M("resilience/" + st.key, k, v)
    for i, s in enumerate(greedy.steps, start=1):
        repo.con.execute("INSERT INTO isolation_recommendations VALUES (?,?,?,?,?,?,?,?)",
                         (run_id, IMPACTGRAPH, i, s["edge"], s["delta_j"], s["delta_impact"], s["delta_phys"], s["text"]))
    M("performance", "greedy_search_seconds", t_greedy)
    log(f"   greedy isolation: {greedy.isolated or 'none worthwhile'} ({t_greedy:.1f}s)")

    # 6. before / after replay on the SAME trial (common random numbers)
    after = eng.trace_for_trial(base.rep_trial, isolated=greedy.isolated)
    for variant, tr in (("before", trace), ("after", after)):
        nodes_df, edges_df = _replay_frames(ig, tr)
        repo.save_df("replay_trace", nodes_df.assign(variant=variant), run_id)
        repo.save_df("replay_edges", edges_df.assign(variant=variant), run_id)

    # 7. validation of the prediction against an independent, larger simulation (hold-out)
    t = time.perf_counter()
    ref_eng = MonteCarloEngine(ig, sc, settings.HOLDOUT_TRIALS, seed + 2000, model=model)
    ref = ref_eng.run(collect_sets=True)
    pred = {k for k, v in base.freq_affected.items() if v >= 0.5}
    precs, recs, f1s = [], [], []
    for A_t in ref.extras["sets"]:
        if not A_t:
            continue
        inter = len(pred & A_t)
        p, r = inter / max(1, len(pred)), inter / len(A_t)
        precs.append(p); recs.append(r); f1s.append(0 if p + r == 0 else 2 * p * r / (p + r))
    M("propagation", "pred_set_size", len(pred))
    M("propagation", "pred_node_precision", np.mean(precs) if precs else 0.0)
    M("propagation", "pred_node_recall", np.mean(recs) if recs else 0.0)
    M("propagation", "pred_node_f1", np.mean(f1s) if f1s else 0.0)
    M("propagation", "frequency_mae_vs_reference", np.mean([abs(base.freq_affected[k] - ref.freq_affected[k]) for k in base.freq_affected]))
    M("propagation", "weighted_impact_error_rel", abs(base.mean("impact") - ref.mean("impact")) / max(ref.mean("impact"), 1e-9))
    lo, hi = base.ci("impact")
    M("propagation", "reference_impact_within_ci", float(lo <= ref.mean("impact") <= hi))
    M("propagation", "mean_impact", base.mean("impact")); M("propagation", "mean_blast_radius_weighted", base.mean("blast_weighted"))
    M("propagation", "mean_throughput", base.mean("throughput"))
    log(f"   propagation vs hold-out ({settings.HOLDOUT_TRIALS} trials, {time.perf_counter() - t:.1f}s): node F1 {np.mean(f1s) if f1s else 0:.3f}")

    # 8. robustness under perturbed probabilities (+-30%) and sensitivity to lambda
    t = time.perf_counter()
    rob = robustness_test(ig, model, sc, strategies, seed=seed + 3000)
    repo.save_blob(run_id, "robustness", rob)
    for k, v in rob.items():
        M("robustness/" + k, "mean_j", v["mean_j"]); M("robustness/" + k, "p90_j", v["p90_j"])
        M("robustness/" + k, "win_rate_vs_no_isolation", v["win_rate_vs_no_isolation"])
    sens = []
    old = settings.LAMBDA
    try:
        for lam in (0.0, 0.02, 0.05, 0.10, 0.20):
            settings.LAMBDA = lam
            g = greedy_isolation(ig, sc, model, seed=seed + 1)
            sens.append({"lambda": lam, "isolated": list(g.isolated), "n": len(g.isolated),
                         "cost": float(sum(ig.edge(e).isolation_cost for e in g.isolated))})
    finally:
        settings.LAMBDA = old
    repo.save_blob(run_id, "lambda_sensitivity", sens)
    log(f"   robustness + sensitivity ({time.perf_counter() - t:.1f}s)")

    # 9. performance + bookkeeping
    total = time.perf_counter() - t_start
    M("performance", "scenario_runtime_seconds", total); M("performance", "peak_memory_mb", _peak_mb())
    repo.save_df("experiment_metrics", pd.DataFrame(metrics), run_id)
    repo.finish_run(run_id, total)
    log(f"   done in {total:.1f}s (run_id={run_id})")
    return run_id


def save_global_metrics(repo: Repository, art: Artifacts):
    """Detection and classifier metrics are global (not per scenario) and stored under run_id 0."""
    repo.execute("DELETE FROM json_blobs WHERE run_id=0")
    repo.save_blob(0, "detection_metrics", art.detection_metrics)
    repo.save_blob(0, "classifier_metrics", art.classifier_metrics)
    os.makedirs("results", exist_ok=True)
    json.dump(art.detection_metrics, open(os.path.join("results", "detection_metrics.json"), "w"), indent=2, default=float)


def run_all(db_path=settings.DB_PATH, seed=settings.SEED, trials=settings.DEFAULT_TRIALS, scenarios=("S1", "S2", "S3"),
            fresh=False, use_classifier=True, log=print):
    if fresh and os.path.exists(db_path):
        os.remove(db_path)
    t0 = time.time()
    ig = build_phase1_topology()
    rep = validate_graph(ig, PHASE1_ZONE_COUNTS)
    log(f"Infrastructure validated: {rep.summary()}  ({len(ig.nodes)} nodes, {len(ig.edges)} edges)")
    assert rep.ok, [str(i) for i in rep.errors]
    model = PropagationModel(ig)
    repo = Repository(db_path)
    config_id = repo.save_infrastructure(ig)
    log("Building detection artifacts ...")
    art = build_artifacts(ig, model, use_classifier=use_classifier, log=log)
    save_global_metrics(repo, art)
    ids = [run_scenario(ig, model, art, repo, config_id, sid, seed, trials, log=log) for sid in scenarios]
    repo.close()
    log(f"All scenarios complete in {time.time() - t0:.0f}s. Database: {db_path}")
    return ids


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=settings.DB_PATH)
    ap.add_argument("--seed", type=int, default=settings.SEED)
    ap.add_argument("--trials", type=int, default=settings.DEFAULT_TRIALS)
    ap.add_argument("--scenarios", nargs="+", default=["S1", "S2", "S3"])
    ap.add_argument("--fresh", action="store_true", help="delete the database first")
    ap.add_argument("--no-classifier", action="store_true")
    a = ap.parse_args()
    run_all(a.db, a.seed, a.trials, tuple(a.scenarios), a.fresh, not a.no_classifier)
