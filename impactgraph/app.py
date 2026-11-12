"""ImpactGraph dashboard. Run:  streamlit run app.py"""
import os

import streamlit as st

st.set_page_config(page_title="ImpactGraph", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

from impactgraph.dashboard import theme as T  # noqa: E402
from impactgraph.dashboard.data import DB, list_runs, load_graph, load_run, scenario_of, stamp  # noqa: E402
from impactgraph.dashboard import pages_a, pages_b  # noqa: E402

T.inject_css()
PAGES = {
    "Executive Summary": pages_a.page_exec, "1 · Infrastructure Overview": pages_a.page_overview, "2 · Network Topology": pages_a.page_topology,
    "3 · Telemetry": pages_a.page_telemetry, "4 · Anomaly Detection": pages_a.page_anomaly, "5 · Attack Scenario": pages_b.page_attack,
    "6 · Propagation Simulation": pages_b.page_propagation, "7 · Risk Assessment": pages_b.page_risk, "8 · Isolation Recommendations": pages_b.page_isolation,
    "9 · Before / After": pages_b.page_before_after, "10 · Evaluation Metrics": pages_b.page_eval,
}

st.sidebar.markdown(f'<div style="font-size:1.45rem;font-weight:800;color:{T.ACCENT}">⬡ ImpactGraph</div>'
                    f'<div style="color:{T.MUTED};font-size:.78rem;margin-bottom:10px">Cyber-physical impact & resilience engine</div>', unsafe_allow_html=True)

s = stamp()
if not os.path.exists(DB) or len(list_runs(DB, s)) == 0:
    T.hero("ImpactGraph", "No experiment results found yet.", [])
    st.info("Generate results first (about 90 seconds):  `python -m impactgraph.experiments.runner --fresh`")
    if st.button("Run all three scenarios now", type="primary"):
        from impactgraph.experiments.runner import run_all
        with st.spinner("Running detection, simulation, risk and containment ..."):
            run_all(DB, fresh=False, use_classifier=os.path.exists("data/raw/unsw-nb15/UNSW_NB15_training-set.csv"), log=lambda *_: None)
        st.cache_data.clear(); st.rerun()
    st.stop()

runs = list_runs(DB, s)
sids = sorted(runs.scenario_id.unique())
qp = st.query_params
_sc_default = sids.index(qp["sc"]) if qp.get("sc") in sids else 0
sid = st.sidebar.selectbox("Scenario", sids, index=_sc_default, format_func=lambda i: f"{i} · {scenario_of(i).name.split('(')[0].strip()[:42]}")
sub = runs[runs.scenario_id == sid].sort_values("run_id", ascending=False)
run_id = int(st.sidebar.selectbox("Simulation run (reload history)", list(sub.run_id), format_func=lambda r: f"run {r} · seed {sub[sub.run_id == r].seed.iloc[0]} · {sub[sub.run_id == r].trials.iloc[0]} trials"))
_pg_default = int(qp["page"]) if str(qp.get("page", "")).isdigit() and int(qp["page"]) < len(PAGES) else 0
page = st.sidebar.radio("Navigate", list(PAGES), index=_pg_default, label_visibility="collapsed")

with st.sidebar.expander("Simulation controls · new run"):
    seed = st.number_input("Random seed", 0, 10_000, 42)
    trials = st.select_slider("Monte Carlo trials", [100, 250, 500, 1000, 2000], value=500)
    if st.button("Run new simulation", type="primary"):
        from impactgraph.experiments import runner
        from impactgraph.infrastructure.topology import build_phase1_topology
        from impactgraph.database.repository import Repository
        from impactgraph.simulation.propagation import PropagationModel

        @st.cache_resource(show_spinner=False)
        def _artifacts():
            ig = build_phase1_topology(); model = PropagationModel(ig)
            return ig, model, runner.build_artifacts(ig, model, use_classifier=os.path.exists("data/raw/unsw-nb15/UNSW_NB15_training-set.csv"), log=lambda *_: None)

        with st.spinner("Training detectors (first time only) and running the scenario ..."):
            ig0, model0, art = _artifacts()
            repo = Repository(DB)
            cfg = int(sub.iloc[0].get("config_id", 1)) if "config_id" in sub.columns else 1
            runner.run_scenario(ig0, model0, art, repo, 1, sid, int(seed), int(trials), log=lambda *_: None)
            repo.close()
        st.cache_data.clear(); st.rerun()
st.sidebar.markdown(f'<div style="color:{T.MUTED};font-size:.72rem;margin-top:14px">All outputs come from simulation of an assumed model. Not a forecast. Advisory only.</div>', unsafe_allow_html=True)

d = dict(load_run(DB, run_id, s))
cfg_id = int(d["run"]["config_id"])
ig = load_graph(DB, cfg_id, s)
rec = d["strategies"][d["strategies"].strategy == "impactgraph_greedy"].iloc[0]
d["_rec_edges"] = list(rec["isolated"])
ctx = {"ig": ig, "d": d, "sc": scenario_of(sid), "sid": sid, "run_id": run_id, "db": DB, "stamp": s}
PAGES[page](ctx)
