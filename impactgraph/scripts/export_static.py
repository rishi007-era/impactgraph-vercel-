"""Export stored results to web/public/data.json for the static web viewer (Vercel, GitHub Pages, AI Studio, any static host).
Usage:  python scripts/export_static.py [impactgraph.db] [web/public/data.json]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from impactgraph.database.repository import Repository
from impactgraph.simulation.scenarios import SCENARIOS
from impactgraph.dashboard.graph_view import POS, BANDS

db = sys.argv[1] if len(sys.argv) > 1 else "impactgraph.db"
out = sys.argv[2] if len(sys.argv) > 2 else "web/public/data.json"
repo = Repository(db)
runs = repo.list_runs().sort_values("run_id").groupby("scenario_id").run_id.max().to_dict()
first = repo.load_run(next(iter(runs.values())))
ig = repo.load_infrastructure(int(first["run"]["config_id"]))
clean = lambda o: json.loads(json.dumps(o, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else (float(x) if isinstance(x, (np.floating,)) else (int(x) if isinstance(x, np.integer) else str(x)))))
topo = {"nodes": [dict(n.to_dict(), criticality=n.criticality.value) for n in ig.nodes], "edges": [e.to_dict() for e in ig.edges],
        "pos": {k: list(v) for k, v in POS.items()}, "bands": {k: list(v) for k, v in BANDS.items()}}
data = {"generated_from": os.path.basename(db), "topology": topo, "scenarios": {}, "global": {}}
data["global"]["detection"] = repo.load_blob(0, "detection_metrics")
data["global"]["classifier"] = repo.load_blob(0, "classifier_metrics")
for sid, rid in runs.items():
    d = repo.load_run(rid); sc = SCENARIOS[sid]
    strategies = []
    for k, r in d["strategies"].set_index("strategy").iterrows():
        strategies.append({"key": k, **{f: r[f] for f in ("label", "isolated", "n_isolated", "cost", "impact", "throughput", "hazard", "service_loss", "blast_weighted", "phys_hit", "objective", "constraints_violated", "continuity", "throughput_hist", "resilience")}})
    replay = {}
    for v in ("before", "after"):
        rn = d["replay_nodes"][d["replay_nodes"].variant == v].drop(columns=["variant"]).to_dict("records")
        re_ = d["replay_edges"][d["replay_edges"].variant == v].drop(columns=["variant"]).to_dict("records")
        replay[v] = {"nodes": rn, "edges": re_}
    paths = [{"target": r.target, "rank": int(r.rank), "probability": float(r.probability), **json.loads(r.path_json)} for r in d["attack_paths"].itertuples()]
    m = d["metrics"]
    data["scenarios"][sid] = {
        "id": sid, "name": sc.name, "mode": sc.mode, "description": sc.description, "assumptions": list(sc.assumptions),
        "run": {"run_id": int(rid), "seed": int(d["run"]["seed"]), "trials": int(d["run"]["trials"])},
        "strategies": strategies, "recommendations": d["recommendations"].to_dict("records"), "replay": replay,
        "risk": d["risk"].to_dict("records"), "propagation": d["propagation"].to_dict("records"), "paths": paths,
        "sensitivity": repo.load_blob(rid, "lambda_sensitivity"), "robustness": repo.load_blob(rid, "robustness"),
        "zone_risk": repo.load_blob(rid, "zone_risk"), "spof": repo.load_blob(rid, "single_points_of_failure"),
        "propagation_metrics": {r.metric: r.value for r in m[m.category == "propagation"].itertuples()},
        "performance": {r.metric: r.value for r in m[m.category == "performance"].itertuples()}}
def sanitize(o):
    if isinstance(o, dict): return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [sanitize(v) for v in o]
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))): return None
    return o
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(sanitize(clean(data)), open(out, "w"), separators=(",", ":"), allow_nan=False)
print("wrote", out, round(os.path.getsize(out) / 1024), "KB")
