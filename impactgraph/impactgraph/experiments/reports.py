"""Generate results/RESULTS.md and CSV tables from the database (all numbers come from stored experiment runs)."""
from __future__ import annotations

import json
import os

import pandas as pd

from ..database.repository import Repository

KEYS = ["no_isolation", "initial_component", "full_shutdown", "impactgraph_greedy"]


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def build(db_path: str, out_dir: str = "results") -> str:
    os.makedirs(out_dir, exist_ok=True)
    repo = Repository(db_path)
    runs = repo.list_runs().sort_values("run_id")
    latest = runs.groupby("scenario_id").run_id.max().to_dict()
    L = ["# ImpactGraph Phase 1: experiment results", "",
         "All numbers below were produced by executing `python -m impactgraph.experiments.runner` and read from the SQLite database.",
         "Simulation outputs are frequencies under ASSUMED transition probabilities, not calibrated real-world probabilities. "
         "Telemetry is synthetic. UNSW-NB15 is lab traffic, not Colonial Pipeline traffic.", ""]
    det = repo.load_blob(0, "detection_metrics")
    clf = repo.load_blob(0, "classifier_metrics")
    if det:
        L += ["## Detection (Isolation Forest, held-out episodes)", f"{det['n_episodes']} test episodes, {det['n_samples']} node-steps.", ""]
        rows = []
        for k, lab in (("without_residual", "Primary (raw telemetry)"), ("with_residual", "Ablation (+ mass-balance residual)")):
            n = det[k]["node_step"]
            rows.append({"variant": lab, "precision": n["precision"], "recall": n["recall"], "f1": n["f1"], "FPR": n["fpr"], "FNR": n["fnr"],
                         "TP": n["tp"], "FP": n["fp"], "TN": n["tn"], "FN": n["fn"]})
        L += [_md(pd.DataFrame(rows)), ""]
        ev = pd.DataFrame(det["without_residual"]["event_by_type"]); L += ["Event-level detection (primary detector):", _md(ev), ""]
        pd.DataFrame(rows).to_csv(os.path.join(out_dir, "detection_node_step.csv"), index=False)
    if clf:
        t = clf["test"]; b = t["binary"]
        L += ["## Network attack classifier (UNSW-NB15, Random Forest)", clf["dataset"],
              f"Rows: {clf['n_raw']} raw, {clf['n_after_dedup']} after removing duplicates/conflicts. Test accuracy {t['accuracy']:.3f}, macro-F1 {t['macro_f1']:.3f}.",
              f"Binary (attack vs normal): precision {b['precision']:.3f}, recall {b['recall']:.3f}, F1 {b['f1']:.3f}, FPR {b['fpr']:.3f}, FNR {b['fnr']:.3f}.", ""]
        pc = pd.DataFrame(t["per_class"]).T.reset_index().rename(columns={"index": "class"}); L += [_md(pc), ""]
        pc.to_csv(os.path.join(out_dir, "classifier_per_class.csv"), index=False)
    allrows = []
    for sid, rid in sorted(latest.items()):
        d = repo.load_run(rid)
        st = d["strategies"].set_index("strategy").loc[[k for k in KEYS if k in set(d["strategies"].strategy)]].reset_index()
        L += [f"## Scenario {sid} (run {rid}, seed {d['run']['seed']}, {d['run']['trials']} trials)", ""]
        tab = st[["label", "impact", "throughput", "hazard", "blast_weighted", "phys_hit", "n_isolated", "cost", "objective", "constraints_violated"]].copy()
        tab.insert(0, "scenario", sid); allrows.append(tab)
        L += [_md(tab.drop(columns="scenario")), ""]
        rec = d["recommendations"]
        if len(rec):
            L += ["Recommended isolation (greedy, ImpactGraph):"] + [f"- {r.explanation}" for r in rec.itertuples()] + [""]
        else:
            L += ["Recommended isolation: none judged worthwhile under the objective.", ""]
        m = d["metrics"]; pm = m[m.category == "propagation"].set_index("metric").value
        L += [f"Prediction vs 2000-trial hold-out: node precision {pm['pred_node_precision']:.3f}, recall {pm['pred_node_recall']:.3f}, F1 {pm['pred_node_f1']:.3f}; "
              f"frequency MAE {pm['frequency_mae_vs_reference']:.3f}; relative impact error {pm['weighted_impact_error_rel']:.3f}.", ""]
        rob = repo.load_blob(rid, "robustness")
        rt = pd.DataFrame([{"strategy": k, **v} for k, v in rob.items()]); L += ["Robustness (perturbed probabilities, fixed strategies):", _md(rt), ""]
        sens = repo.load_blob(rid, "lambda_sensitivity"); L += ["Sensitivity of the recommendation to lambda:", _md(pd.DataFrame(sens)), ""]
        d["risk"].head(8)[["rank", "component_id", "name", "likelihood", "consequence", "risk"]].to_csv(os.path.join(out_dir, f"risk_top_{sid}.csv"), index=False)
    if allrows:
        pd.concat(allrows).to_csv(os.path.join(out_dir, "strategy_comparison.csv"), index=False)
    text = "\n".join(L)
    open(os.path.join(out_dir, "RESULTS.md"), "w").write(text)
    repo.close()
    return text


if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else "impactgraph.db")
