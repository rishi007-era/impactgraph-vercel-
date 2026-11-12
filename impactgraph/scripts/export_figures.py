"""Export static PNG backups of key figures (needs: pip install kaleido; plotly_get_chrome). Optional."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from impactgraph.dashboard import theme as T
from impactgraph.dashboard.data import replay_state
from impactgraph.dashboard.graph_view import make_graph
from impactgraph.database.repository import Repository

os.makedirs("docs/figures", exist_ok=True)
repo = Repository("impactgraph.db")
runs = repo.list_runs().sort_values("run_id").groupby("scenario_id").run_id.max().to_dict()
for sid, rid in runs.items():
    d = repo.load_run(rid)
    ig = repo.load_infrastructure(int(d["run"]["config_id"]))
    rec = d["strategies"][d["strategies"].strategy == "impactgraph_greedy"].iloc[0]
    for variant in ("before", "after"):
        rn = d["replay_nodes"][d["replay_nodes"].variant == variant]
        re_ = d["replay_edges"][d["replay_edges"].variant == variant]
        fig = make_graph(ig, node_fill=replay_state(rn, 99, True), highlight=frozenset(re_.edge_id),
                         isolated=frozenset(rec["isolated"]) if variant == "after" else frozenset(), height=760,
                         title=f"{sid} · {'No isolation' if variant == 'before' else 'ImpactGraph isolation'}")
        fig.update_layout(paper_bgcolor=T.BG)
        fig.write_image(f"docs/figures/{sid}_{variant}.png", width=1500, height=780)
        print("wrote", sid, variant)
fig = make_graph(ig, height=760, title="Phase 1 infrastructure (24 components, 48 typed relationships)")
fig.update_layout(paper_bgcolor=T.BG)
fig.write_image("docs/figures/topology.png", width=1500, height=780)
repo.close()
