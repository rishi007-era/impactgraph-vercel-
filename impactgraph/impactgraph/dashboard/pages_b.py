"""Dashboard pages 6-11: attack scenario, propagation, risk, isolation, before/after, evaluation."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ..config import settings
from ..optimization.strategies import FULL_SHUTDOWN, IMPACTGRAPH, INITIAL_COMPONENT, LABELS, NO_ISOLATION
from . import theme as T
from .data import CONFIG, load_blob, pct, replay_max, replay_state, strategy_row
from .graph_view import make_graph
from .pages_a import DATA_BADGES, MODE_BADGE

ORDER = [NO_ISOLATION, INITIAL_COMPONENT, FULL_SHUTDOWN, IMPACTGRAPH]
COLORS = {NO_ISOLATION: T.BAD, INITIAL_COMPONENT: T.WARN, FULL_SHUTDOWN: "#94A3B8", IMPACTGRAPH: T.GOOD}


def page_attack(c):
    sc, d, ig = c["sc"], c["d"], c["ig"]
    txt, col = MODE_BADGE[sc.mode]
    T.hero("Attack Scenario", sc.name, [T.badge(txt, col)] + DATA_BADGES)
    st.markdown(f'<div class="ig-card"><b>Narrative</b><br><span style="color:{T.MUTED}">{sc.description}</span></div>', unsafe_allow_html=True)
    with st.expander("Scenario assumptions (read before presenting)", expanded=True):
        for a in sc.assumptions:
            st.markdown(f"- {a}")
        st.markdown(f"- Attempts per link: **{sc.attempts}** · response delay: **{sc.response_delay:g} hops** · a graph connection alone never implies traversal: every hop needs its access conditions.")
    paths = d["attack_paths"]
    if paths.empty:
        T.note("This scenario has no cyber entry path (physical sabotage scenario). See the Propagation page for the physical effects.")
        return
    tgts = list(dict.fromkeys(paths.target))
    a, b = st.columns([1, 2])
    tgt = a.selectbox("Target component", tgts, format_func=lambda i: f"{i} · {ig.node(i).name}")
    sub = paths[paths.target == tgt].sort_values("rank")
    rk = b.radio("Candidate route (ranked by likelihood)", list(sub["rank"]), horizontal=True,
                 format_func=lambda r: f"Route {r} · {sub[sub['rank'] == r].probability.iloc[0]:.1%}")
    p = json.loads(sub[sub["rank"] == rk].path_json.iloc[0])
    hi = frozenset(h["edge"] for h in p["hops"])
    fills = {n: "#F97316" for n in p["nodes"]}
    fig = make_graph(ig, node_fill=fills, highlight=hi, height=640, selected=None)
    st.plotly_chart(fig, config=CONFIG)
    T.kpi_row([("Route likelihood", f"{p['probability']:.1%}", "product of per-link success within attempts (model)", T.BAD),
               ("Hops", p["length"], " → ".join(p["nodes"]), T.ACCENT),
               ("Security-boundary crossings", len(p["boundary_crossings"]), ", ".join(p["boundary_crossings"]) or "none", T.WARN)])
    rows = []
    for i, h in enumerate(p["hops"], start=1):
        rows.append({"hop": i, "from → to": f"{h['source']} → {h['target']}", "edge": h["edge"], "type": h["type"], "zones": h["zones"],
                     "p / attempt": h["p_single"], "p within attempts": h["p_total"],
                     "why feasible": "; ".join(f"{'✓' if ok else '✗'} {why}" for _, ok, why in h["conditions"])})
    st.markdown("**Hop-by-hop feasibility** (every route is explained, not just drawn)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={"p / attempt": st.column_config.NumberColumn(format="%.2f"),
                                                                     "p within attempts": st.column_config.NumberColumn(format="%.2f")})
    reach = load_blob(c["db"], c["run_id"], "reachability", c["stamp"]) or {}
    if reach:
        rdf = pd.DataFrame({"zone": list(reach), "reachable components": [len(v) for v in reach.values()]})
        fig2 = px.bar(rdf, x="zone", y="reachable components", color="zone", color_discrete_map=T.ZONE_COLOR)
        T.style_fig(fig2, 260, legend=False); fig2.update_layout(title="Reachability from the entry point by zone (structural, before probabilities)")
        st.plotly_chart(fig2, config=CONFIG)


def _graph_at(c, variant, step, final, selected=None, labels=True):
    ig, d = c["ig"], c["d"]
    rn = d["replay_nodes"]; rn = rn[rn.variant == variant]
    re_ = d["replay_edges"]; re_ = re_[(re_.variant == variant) & (re_.t_end <= step)]
    iso = frozenset(d["_rec_edges"]) if variant == "after" else frozenset()
    fills = replay_state(rn, step, final)
    return make_graph(ig, node_fill=fills, highlight=frozenset(re_.edge_id), isolated=iso, height=600, selected=selected, labels=labels), rn


def page_propagation(c):
    sc, d, ig = c["sc"], c["d"], c["ig"]
    T.hero("Failure Propagation Simulation", "Monte Carlo cascade simulation · step-by-step replay of one representative trial", DATA_BADGES)
    rn = d["replay_nodes"]
    maxt = int(np.ceil(max(replay_max(rn[rn.variant == "before"]), replay_max(rn[rn.variant == "after"]), 1)))
    a, b, cc = st.columns([1.2, 2.6, 1])
    variant = a.radio("Replay", ["before", "after"], format_func=lambda v: "No isolation" if v == "before" else "With ImpactGraph isolation", horizontal=True)
    step = b.slider("Propagation step (hops)", 0, maxt, 0)
    play = cc.button("▶ Play replay", type="primary")
    slot = st.empty()
    fig, rnv = _graph_at(c, variant, step, step >= maxt)
    slot.plotly_chart(fig, config=CONFIG, key="replay_static")
    if play:
        for s in range(0, maxt + 1):
            f, _ = _graph_at(c, variant, s, s >= maxt)
            slot.plotly_chart(f, config=CONFIG, key=f"replay_{s}")
            time.sleep(0.9)
    T.zone_legend()
    ev = []
    for r in rnv.itertuples():
        if not np.isnan(r.t_compromised) and int(r.t_compromised) <= step:
            ev.append({"hop": int(r.t_compromised), "component": f"{r.component_id} · {ig.node(r.component_id).name}", "event": "compromised"})
        if not np.isnan(r.t_failed) and int(r.t_failed) <= step:
            ev.append({"hop": int(r.t_failed), "component": f"{r.component_id} · {ig.node(r.component_id).name}", "event": f"failed ({r.fail_kind})"})
    L, R = st.columns([1, 1.6])
    L.markdown("**Event timeline up to this step**")
    L.dataframe(pd.DataFrame(ev, columns=["hop", "component", "event"]).sort_values("hop") if ev else pd.DataFrame(columns=["hop", "component", "event"]), hide_index=True, height=300)
    prop = d["propagation"].sort_values("p_affected", ascending=False).head(16).iloc[::-1]
    fig2 = go.Figure(go.Bar(x=prop.p_affected, y=[f"{i} {ig.node(i).name[:20]}" for i in prop.component_id], orientation="h",
                            marker_color=[T.ZONE_COLOR[ig.node(i).zone.value] for i in prop.component_id],
                            error_x=dict(type="data", symmetric=False, array=prop.ci_high - prop.p_affected, arrayminus=prop.p_affected - prop.ci_low, color="#94A3B8")))
    T.style_fig(fig2, 440, legend=False)
    fig2.update_layout(title=f"Simulated hit frequency per component ({d['run']['trials']} trials, 95% Wilson interval)", xaxis=dict(range=[0, 1], tickformat=".0%"))
    R.plotly_chart(fig2, config=CONFIG)
    T.note("These are SIMULATION FREQUENCIES under assumed transition probabilities. They are not calibrated real-world probabilities.")
    cas = []
    for s in range(0, maxt + 1):
        cas.append({"hop": s, "compromised": int(((rnv.t_compromised <= s) & ~(rnv.t_failed <= s)).sum()), "failed": int((rnv.t_failed <= s).sum())})
    fig3 = px.area(pd.DataFrame(cas), x="hop", y=["compromised", "failed"], color_discrete_map={"compromised": "#F97316", "failed": "#EF4444"})
    T.style_fig(fig3, 260); fig3.update_layout(title="Cascade progression in the replayed trial", yaxis_title="components")
    st.plotly_chart(fig3, config=CONFIG)


def page_risk(c):
    ig, d = c["ig"], c["d"]
    T.hero("Risk Assessment", "Transparent, assumption-based risk ranking · structural centrality shown only as a supplementary indicator", DATA_BADGES)
    risk = d["risk"]
    none = strategy_row(d, NO_ISOLATION)
    zr = pd.DataFrame(load_blob(c["db"], c["run_id"], "zone_risk", c["stamp"]) or [])
    spof = load_blob(c["db"], c["run_id"], "single_points_of_failure", c["stamp"]) or []
    top = risk.iloc[0]
    T.kpi_row([("Highest-risk component", top.component_id, f"{top['name']} · risk {top.risk:.2f}", T.BAD),
               ("Weighted blast radius", pct(none["blast_weighted"]), "importance share compromised / failed / degraded (no isolation)", T.WARN),
               ("Single points of failure", len(spof), ", ".join(spof) or "none", T.MAGENTA),
               ("Most exposed zone", zr.sort_values("mean_risk").iloc[-1].zone.upper() if len(zr) else "-", "highest mean component risk", T.ACCENT)])
    st.markdown("&nbsp;")
    rmap = dict(zip(risk.component_id, risk.risk))
    extra = {r.component_id: f"<b>risk {r.risk:.2f}</b> (likelihood {r.likelihood:.2f} × consequence {r.consequence:.2f})" for r in risk.itertuples()}
    fig = make_graph(ig, node_fill=rmap, node_extra=extra, colorbar={"scale": "YlOrRd", "min": 0, "max": float(risk.risk.max()), "title": "risk"}, height=600,
                     layers={"network", "auth", "control", "physical_flow"})
    st.plotly_chart(fig, config=CONFIG)
    L, R = st.columns([1.5, 1])
    L.markdown("**Component risk ranking**")
    L.dataframe(risk[["rank", "component_id", "name", "zone", "risk", "likelihood", "consequence", "sim_frequency", "evidence", "exposure", "downstream_share", "betweenness"]],
                hide_index=True, height=420,
                column_config={k: st.column_config.ProgressColumn(k, min_value=0, max_value=1, format="%.2f") for k in ("risk", "likelihood", "consequence", "sim_frequency", "evidence", "exposure", "downstream_share")}
                | {"betweenness": st.column_config.NumberColumn("betweenness (structural, supplementary)", format="%.3f")})
    if len(zr):
        fz = px.bar(zr, x="zone", y=["mean_risk", "max_risk"], barmode="group", color_discrete_sequence=[T.ACCENT, T.BAD])
        T.style_fig(fz, 420); fz.update_layout(title="Zone risk")
        R.plotly_chart(fz, config=CONFIG)
    w = settings.RISK_LIKELIHOOD_WEIGHTS
    t10 = risk.head(10).iloc[::-1]
    fd = go.Figure()
    fd.add_bar(y=t10.component_id, x=w["simulation"] * t10.sim_frequency, orientation="h", name="simulated frequency", marker_color=T.ACCENT)
    fd.add_bar(y=t10.component_id, x=w["evidence"] * t10.evidence, orientation="h", name="detection evidence", marker_color=T.WARN)
    fd.add_bar(y=t10.component_id, x=w["exposure"] * t10.exposure, orientation="h", name="exposure", marker_color=T.MAGENTA)
    fd.update_layout(barmode="stack")
    T.style_fig(fd, 380); fd.update_layout(title="Why these components? Likelihood contributions (weighted)")
    st.plotly_chart(fd, config=CONFIG)
    with st.expander("Risk formula, normalisation and assumptions"):
        st.code("S_i = max(A_i, N_i)                  # detection evidence: anomaly score vs calibrated traffic-classifier evidence\n"
                f"L_i = {w['simulation']}*P_i + {w['evidence']}*S_i + {w['exposure']}*X_i      # likelihood (P_i = simulated hit frequency, X_i = exposure)\n"
                f"C_i = {settings.RISK_CONSEQUENCE_WEIGHTS['importance']}*importance_i + {settings.RISK_CONSEQUENCE_WEIGHTS['downstream']}*D_i   # consequence (D_i = downstream importance share)\n"
                "R_i = L_i * C_i                      # all inputs in [0,1]; ranking aid, not a probability of loss", language="text")
        st.markdown("All weights are assumptions (config/settings.py). Anomaly scores are percentile-calibrated on normal data and classifier evidence is calibrated against benign traffic "
                    "before they are combined. Betweenness centrality is displayed for context and is **not** an input to risk.")


def page_isolation(c):
    ig, d = c["ig"], c["d"]
    T.hero("Isolation Recommendations", "Greedy containment search on a transparent objective, with hard safety and continuity constraints", DATA_BADGES)
    T.advisory("ADVISORY ONLY. These are simulated recommendations for human decision-makers. ImpactGraph never executes isolation, shutdown or valve commands on any real system.")
    st.markdown("&nbsp;")
    none, rec = strategy_row(d, NO_ISOLATION), strategy_row(d, IMPACTGRAPH)
    iso = list(rec["isolated"])
    T.kpi_row([("Actions recommended", len(iso), ", ".join(iso) or "none worthwhile", T.MAGENTA),
               ("Isolation cost", f"{rec['cost']:.1f}", f"of reference {settings.COST_REF:g} · λ = {settings.LAMBDA}", T.WARN),
               ("Impact reduction", pct(1 - rec["impact"] / max(none["impact"], 1e-9)), f"{none['impact']:.3f} → {rec['impact']:.3f}", T.GOOD),
               ("Throughput kept", pct(rec["throughput"]), f"was {pct(none['throughput'])} without isolation", T.ACCENT),
               ("Constraints violated", int(rec["constraints_violated"]), "C1 safety · C2 continuity · C3 action cap", T.GOOD if rec["constraints_violated"] == 0 else T.BAD)])
    st.markdown("&nbsp;")
    L, R = st.columns([1.7, 1])
    with L:
        fig = make_graph(ig, isolated=frozenset(iso), height=600, layers={"network", "auth", "control", "physical_flow"})
        st.plotly_chart(fig, config=CONFIG)
    with R:
        st.markdown("**Why each action is recommended**")
        recs = d["recommendations"]
        if len(recs):
            for r in recs.itertuples():
                st.markdown(f'<div class="ig-step"><b>Step {r.step}</b> · ΔJ −{r.delta_j:.3f}<br>{r.explanation}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ig-step">No single isolation lowers the objective enough to justify its cost and the dependencies it sacrifices. Doing nothing is the recommendation.</div>', unsafe_allow_html=True)
        st.markdown("**Hard constraints enforced**")
        st.markdown("- **C1** no logical isolation of a link into a safety-critical component\n"
                    f"- **C2** attack-free throughput stays ≥ {pct(settings.MIN_CONTINUITY)} (never 'disconnect everything')\n"
                    f"- **C3** at most {settings.MAX_ISOLATIONS} actions")
    with st.expander("Objective function and assumptions"):
        st.latex(r"J(S) = \mathbb{E}[\text{impact} \mid S] + \lambda \cdot \frac{\sum_{e \in S} \text{cost}(e)}{C_{ref}}")
        st.markdown(f"impact = {settings.IMPACT_WEIGHTS['throughput']}·(1 − throughput) + {settings.IMPACT_WEIGHTS['service']}·service loss + "
                    f"{settings.IMPACT_WEIGHTS['hazard']}·release hazard + {settings.IMPACT_WEIGHTS['exposure']}·compromise exposure. "
                    "Weights, costs and λ are assumptions. Valve closures are reactive (applied only after a release). Isolation decided after the first alert takes effect after the scenario's response delay.")
    sens = pd.DataFrame(load_blob(c["db"], c["run_id"], "lambda_sensitivity", c["stamp"]) or [])
    rob = load_blob(c["db"], c["run_id"], "robustness", c["stamp"]) or {}
    a, b = st.columns(2)
    if len(sens):
        a.markdown("**Sensitivity of the recommendation to λ** (how much isolation is 'too much')")
        sens["isolated"] = sens["isolated"].map(lambda x: ", ".join(x) or "none")
        a.dataframe(sens, hide_index=True)
    if rob:
        b.markdown("**Robustness: ±30% perturbation of every attack probability (15 models, fixed strategies)**")
        rt = pd.DataFrame([{"strategy": LABELS[k], **v} for k, v in rob.items()])
        b.dataframe(rt, hide_index=True, column_config={"win_rate_vs_no_isolation": st.column_config.ProgressColumn("win rate vs no isolation", min_value=0, max_value=1, format="%.2f")})


def page_before_after(c):
    ig, d = c["ig"], c["d"]
    T.hero("Before-and-After Comparison", "The same simulated incident (identical random draws) with and without containment", DATA_BADGES)
    maxt = int(np.ceil(max(replay_max(d["replay_nodes"][d["replay_nodes"].variant == "before"]), 1)))
    L, R = st.columns(2)
    for col, v, title in ((L, "before", "No isolation"), (R, "after", "ImpactGraph isolation")):
        fig, _ = _graph_at(c, v, maxt + 5, True, labels="id")
        fig.update_layout(title=title, height=520)
        col.plotly_chart(fig, config=CONFIG, key=f"ba_{v}")
    T.zone_legend()
    sdf = d["strategies"].set_index("strategy").loc[ORDER].reset_index()
    sdf["label"] = sdf.strategy.map(LABELS)
    a, b = st.columns(2)
    fig = go.Figure()
    for key, nm, col in (("impact", "expected impact", T.ACCENT), ("hazard", "release hazard", T.BAD), ("blast_weighted", "weighted blast radius", T.WARN)):
        fig.add_bar(x=sdf.label, y=sdf[key], name=nm, marker_color=col)
    fig.update_layout(barmode="group")
    T.style_fig(fig, 380); fig.update_layout(title="Impact components by strategy (lower is better)")
    a.plotly_chart(fig, config=CONFIG)
    bins = [f"{i * 10}-{(i + 1) * 10}%" for i in range(10)]
    fh = go.Figure()
    for r in sdf.itertuples():
        fh.add_bar(x=bins, y=np.array(r.throughput_hist) / sum(r.throughput_hist), name=r.label, marker_color=COLORS[r.strategy])
    fh.update_layout(barmode="group", yaxis_tickformat=".0%")
    T.style_fig(fh, 380); fh.update_layout(title="Distribution of delivered throughput across trials", xaxis_title="throughput retained")
    b.plotly_chart(fh, config=CONFIG)
    tab = sdf[["label", "impact", "throughput", "hazard", "blast_weighted", "phys_hit", "n_isolated", "cost", "objective", "constraints_violated"]].rename(
        columns={"label": "strategy", "blast_weighted": "weighted blast radius", "phys_hit": "P(physical failure)"})
    st.dataframe(tab, hide_index=True)
    res = pd.DataFrame([{"strategy": r.label, **r.resilience} for r in sdf.itertuples()])
    st.markdown("**Resilience after containment**")
    st.dataframe(res, hide_index=True)
    T.note("Full precautionary shutdown stops deliveries by design. It is shown because that was the real-world response to uncertainty in 2021. Its impact here depends on the assumed importance weights.")


def _cm_fig(cm, labels, title, normalize=True):
    z = np.array(cm, dtype=float)
    if normalize:
        z = z / np.maximum(z.sum(axis=1, keepdims=True), 1)
    fig = go.Figure(go.Heatmap(z=z, x=labels, y=labels, colorscale="Blues", text=np.array(cm), texttemplate="%{text}", colorbar=dict(thickness=10)))
    T.style_fig(fig, 460); fig.update_layout(title=title, xaxis_title="predicted", yaxis_title="actual", yaxis=dict(autorange="reversed"))
    return fig


def page_eval(c):
    d = c["d"]
    T.hero("Evaluation Metrics", "Measured results from actual execution · nothing on this page is hand-entered", DATA_BADGES)
    det = load_blob(c["db"], 0, "detection_metrics", c["stamp"]) or {}
    clf = load_blob(c["db"], 0, "classifier_metrics", c["stamp"]) or {}
    m = d["metrics"]
    tabs = st.tabs(["Detection", "Traffic classifier", "Propagation", "Containment", "Robustness", "Performance & reproducibility", "Limitations"])
    with tabs[0]:
        if det:
            p, ab = det["without_residual"], det["with_residual"]
            n = p["node_step"]
            T.kpi_row([("Precision", f"{n['precision']:.3f}", f"{n['tp']} TP · {n['fp']} FP", T.GOOD), ("Recall", f"{n['recall']:.3f}", f"{n['fn']} missed anomalous minutes", T.ACCENT),
                       ("F1", f"{n['f1']:.3f}", f"{det['n_episodes']} held-out episodes", T.ACCENT), ("False-positive rate", f"{n['fpr']:.4f}", f"{n['tn']} true negatives", T.WARN),
                       ("False-negative rate", f"{n['fnr']:.3f}", "node-minute level", T.BAD)])
            a, b = st.columns(2)
            cm = [[n["tn"], n["fp"]], [n["fn"], n["tp"]]]
            a.plotly_chart(_cm_fig(cm, ["normal", "anomalous"], "Confusion matrix · node-minutes (primary detector)", normalize=False), config=CONFIG)
            ev = pd.DataFrame(p["event_by_type"]); b.markdown("**Event-level detection** (was an injected event alerted, and how late?)")
            b.dataframe(ev.rename(columns={"detected": "detected share", "median_delay": "median delay (min)"}), hide_index=True)
            b.markdown("**Ablation: add physics-consistency (mass-balance residual) feature**")
            b.dataframe(pd.DataFrame([{"variant": "primary", **{k: p["node_step"][k] for k in ("precision", "recall", "f1", "fpr")}},
                                      {"variant": "+ residual", **{k: ab["node_step"][k] for k in ("precision", "recall", "f1", "fpr")}}]), hide_index=True)
            T.note("Honest finding: the residual feature did NOT improve detection on these held-out episodes (it diluted downstream-effect recall), so the simpler detector is primary. "
                   "That choice was made after seeing this ablation, so the primary figures are slightly optimistic. The residual is retained for Phase 2 sensor-spoofing tests.")
            lr = pd.DataFrame({"label": list(p["label_recall"]), "node-minute recall": list(p["label_recall"].values())})
            st.dataframe(lr, hide_index=True)
    with tabs[1]:
        if clf:
            t, b = clf["test"], clf["test"]["binary"]
            T.kpi_row([("Accuracy", f"{t['accuracy']:.3f}", "10-class test set", T.ACCENT), ("Macro-F1", f"{t['macro_f1']:.3f}", "equal weight per class", T.ACCENT),
                       ("Attack recall", f"{b['recall']:.3f}", f"FNR {b['fnr']:.3f}", T.GOOD), ("False-positive rate", f"{b['fpr']:.3f}", "benign flagged as attack", T.BAD),
                       ("Precision", f"{b['precision']:.3f}", "attack vs normal", T.WARN)])
            st.caption(f"{clf['dataset']} · {clf['n_raw']:,} raw rows → {clf['n_after_dedup']:,} after removing duplicates and conflicting duplicates · {clf['n_features']} features · "
                       "UNSW-NB15 is lab traffic, not Colonial Pipeline traffic.")
            a, b2 = st.columns(2)
            cc = pd.DataFrame({"class": list(clf["class_counts_raw"]), "records": list(clf["class_counts_raw"].values())}).sort_values("records")
            fi = px.bar(cc, x="records", y="class", orientation="h", log_x=True, color_discrete_sequence=[T.ACCENT])
            T.style_fig(fi, 380, legend=False); fi.update_layout(title="Class imbalance (raw, log scale)")
            a.plotly_chart(fi, config=CONFIG)
            b2.plotly_chart(_cm_fig(t["confusion_matrix"], t["classes"], "Confusion matrix (row-normalised, counts shown)"), config=CONFIG)
            pc = pd.DataFrame(t["per_class"]).T.reset_index().rename(columns={"index": "class"})
            st.dataframe(pc, hide_index=True)
            T.note("Weak classes (e.g. DoS, Analysis, Worms) and a 18.5% benign false-positive rate are reported as measured. In ImpactGraph the classifier is one evidence input, never an alarm on its own.")
    with tabs[2]:
        pm = m[m.category == "propagation"].set_index("metric").value
        T.kpi_row([("Node F1 vs hold-out", f"{pm['pred_node_f1']:.3f}", f"precision {pm['pred_node_precision']:.2f} · recall {pm['pred_node_recall']:.2f}", T.ACCENT),
                   ("Frequency MAE", f"{pm['frequency_mae_vs_reference']:.3f}", "500 vs 2000 independent trials", T.GOOD),
                   ("Impact estimate error", pct(pm["weighted_impact_error_rel"], 1), "relative to reference", T.WARN),
                   ("Reference inside 95% CI", "yes" if pm["reference_impact_within_ci"] else "no", "impact estimate", T.MAGENTA)])
        T.note("'Prediction' here is the set of components with simulated hit frequency ≥ 0.5, compared with realisations of an independent, larger simulation of the same model. It measures simulation stability, not accuracy against real incidents.")
    with tabs[3]:
        st.dataframe(d["strategies"].set_index("strategy").loc[ORDER].reset_index()[["label", "impact", "throughput", "hazard", "phys_hit", "n_isolated", "cost", "objective", "constraints_violated"]], hide_index=True)
    with tabs[4]:
        rob = load_blob(c["db"], c["run_id"], "robustness", c["stamp"]) or {}
        if rob:
            st.dataframe(pd.DataFrame([{"strategy": LABELS[k], **v} for k, v in rob.items()]), hide_index=True)
            st.caption("Strategies are FIXED (optimised under nominal probabilities) and re-evaluated under 15 models with every attack probability scaled by U(0.7, 1.3).")
    with tabs[5]:
        pf = m[m.category == "performance"].set_index("metric").value
        T.kpi_row([("Monte Carlo throughput", f"{pf['mc_trials_per_second']:.0f}/s", "trials per second (1 CPU)", T.ACCENT), ("Greedy search", f"{pf['greedy_search_seconds']:.1f}s", "full candidate scan", T.WARN),
                   ("Scenario runtime", f"{pf['scenario_runtime_seconds']:.1f}s", "all stages", T.GOOD), ("Peak memory", f"{pf['peak_memory_mb']:.0f} MB", "process", T.MAGENTA)])
        params = json.loads(d["run"]["params_json"])
        with st.expander("Reproducibility record for this run (seed, weights, scenario, versions)"):
            st.json(params)
    with tabs[6]:
        st.markdown("""
- Telemetry is **synthetic**; ranges and anomaly shapes are assumptions. Detection accuracy on real plant data is unknown.
- All attack/transition probabilities, importance values, costs and objective weights are **assumed**, not calibrated. Outputs are simulation frequencies.
- Mode A reproduces only the documented IT-side incident and the precautionary shutdown. The OT-foothold probability is an uncertainty assumption, not a historical fact.
- The network classifier uses the UNSW-NB15 training partition re-split internally; the flow bridge from dataset flows to graph components is an explicit assumption.
- The physics-consistency feature did not help in Phase 1; the primary-detector choice was made after seeing the ablation.
- Steady-state flow only: no hydraulics, no recovery dynamics (Phase 2).
- Phase 1 optimiser is greedy; an exhaustive reference and constrained optimisation arrive in Phase 2.
""")
