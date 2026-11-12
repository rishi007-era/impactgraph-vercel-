"""Dashboard pages 1-5: executive summary, infrastructure, topology, telemetry, anomaly detection."""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ..infrastructure.graph_validator import validate_graph
from ..infrastructure.telemetry_spec import TELEMETRY_FEATURES
from ..infrastructure.topology import PHASE1_ZONE_COUNTS
from ..optimization.strategies import FULL_SHUTDOWN, IMPACTGRAPH, INITIAL_COMPONENT, LABELS, NO_ISOLATION
from . import theme as T
from .data import CONFIG, pct, strategy_row
from .graph_view import make_graph

MODE_BADGE = {"A": ("MODE A · HISTORICAL RECONSTRUCTION (IT SIDE)", T.WARN), "B": ("MODE B · HYPOTHETICAL CYBER-PHYSICAL", T.BAD),
              "P": ("MODE P · PHYSICAL SABOTAGE (HYPOTHETICAL)", T.MAGENTA)}
DATA_BADGES = [T.badge("SYNTHETIC TELEMETRY", T.ACCENT), T.badge("ASSUMED PROBABILITIES", T.WARN), T.badge("ADVISORY ONLY · NO REAL SYSTEMS", T.GOOD)]


def page_exec(c):
    sc, d, ig = c["sc"], c["d"], c["ig"]
    txt, col = MODE_BADGE[sc.mode]
    T.hero("ImpactGraph", "AI-powered cyber-physical failure propagation, impact prediction and resilience engine · Colonial Pipeline–inspired case study",
           [T.badge(txt, col)] + DATA_BADGES)
    none, rec, shut = (strategy_row(d, k) for k in (NO_ISOLATION, IMPACTGRAPH, FULL_SHUTDOWN))
    prop = d["propagation"]
    T.kpi_row([
        ("Expected impact · no isolation", f"{none['impact']:.2f}", "importance-weighted, 0 = none, 1 = total", T.BAD),
        ("Expected impact · ImpactGraph", f"{rec['impact']:.2f}", f"{pct(1 - rec['impact'] / max(none['impact'], 1e-9))} lower than no isolation", T.GOOD),
        ("Throughput kept · ImpactGraph", pct(rec["throughput"]), f"no isolation {pct(none['throughput'])} · full shutdown {pct(shut['throughput'])}", T.ACCENT),
        ("Chance a physical asset fails", pct(none["phys_hit"]), f"after isolation {pct(rec['phys_hit'])} (simulated frequency)", T.WARN),
        ("Expected components affected", f"{prop.p_affected.sum():.1f} / {len(ig.nodes)}", "sum of simulated hit frequencies", T.MAGENTA),
    ])
    st.markdown("&nbsp;")
    L, R = st.columns([1.15, 1])
    with L:
        st.markdown(f'<div class="ig-card"><h4>Scenario · {sc.id}</h4><b>{sc.name}</b><br><span style="color:{T.MUTED}">{sc.description}</span></div>', unsafe_allow_html=True)
        recs = d["recommendations"]
        if len(recs):
            body = "".join(f'<div class="ig-step">{r.explanation}</div>' for r in recs.itertuples())
        else:
            body = '<div class="ig-step">No isolation was judged worthwhile under the objective for this scenario.</div>'
        st.markdown(f'<div class="ig-card"><h4>Recommended containment (advisory)</h4>{body}</div>', unsafe_allow_html=True)
        T.advisory("Recommendations are decision support computed inside a simulation. ImpactGraph never sends commands to real industrial systems.")
    with R:
        df = d["strategies"].set_index("strategy").loc[[NO_ISOLATION, INITIAL_COMPONENT, FULL_SHUTDOWN, IMPACTGRAPH]].reset_index()
        fig = go.Figure()
        fig.add_bar(x=df["label"], y=df["objective"], name="Objective J (lower is better)", marker_color=[T.BAD, T.WARN, "#94A3B8", T.GOOD],
                    text=[f"{v:.2f}" for v in df["objective"]], textposition="outside")
        T.style_fig(fig, 330, legend=False)
        fig.update_layout(title="Strategy comparison · same simulated incidents", yaxis_title="J = impact + λ·cost")
        st.plotly_chart(fig, config=CONFIG)
        st.caption("Full precautionary shutdown stops all deliveries by design, which is why its objective is high even when no damage occurs.")
    st.markdown("**What the evaluator is looking at:** detection → attack path → propagation → risk → isolation → before/after, all computed by the backend from one reproducible run (seed "
                f"{d['run']['seed']}, {d['run']['trials']} Monte Carlo trials).")


def page_overview(c):
    ig = c["ig"]
    T.hero("Infrastructure Overview", "Representative 24-component pipeline model across four zones (a model, not Colonial's real architecture)", DATA_BADGES)
    rep = validate_graph(ig, PHASE1_ZONE_COUNTS)
    zc = ig.zone_counts()
    T.kpi_row([("Components", len(ig.nodes), "typed nodes", T.ACCENT), ("Relationships", len(ig.edges), "directed, typed edges", T.ACCENT),
               ("Model validation", "PASS" if rep.ok else "FAIL", rep.summary(), T.GOOD if rep.ok else T.BAD),
               ("Safety-critical", sum(n.safety_critical for n in ig.nodes), "process assets", T.WARN),
               ("Isolatable links", sum(e.isolatable for e in ig.edges), "candidate containment actions", T.MAGENTA)])
    st.markdown("&nbsp;")
    cols = st.columns(4)
    for col, (z, cnt) in zip(cols, zc.items()):
        names = ", ".join(n.name for n in ig.nodes_by_zone(z))
        col.markdown(f'<div class="ig-card" style="border-top:3px solid {T.ZONE_COLOR[z.value]}"><h4 style="color:{T.ZONE_COLOR[z.value]}">{z.value.upper()} · {cnt}</h4>'
                     f'<span style="color:{T.MUTED};font-size:.8rem">{names}</span></div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    et = pd.Series({t.value: len(ig.edges_by_type(t)) for t in __import__("impactgraph.infrastructure.enums", fromlist=["EdgeType"]).EdgeType})
    fig = px.pie(values=et.values, names=[T.EDGE_LABEL[k] for k in et.index], hole=0.55, color=[T.EDGE_LABEL[k] for k in et.index],
                 color_discrete_map={T.EDGE_LABEL[k]: T.EDGE_COLOR[k] for k in et.index})
    T.style_fig(fig, 340); fig.update_layout(title="Relationship types (never mixed)")
    a.plotly_chart(fig, config=CONFIG)
    crit = pd.DataFrame([{"zone": n.zone.value, "criticality": n.criticality.value} for n in ig.nodes])
    fig2 = px.histogram(crit, x="zone", color="criticality", barmode="stack", category_orders={"criticality": ["low", "medium", "high", "critical"]},
                        color_discrete_map={"low": "#64748B", "medium": T.ACCENT, "high": T.WARN, "critical": T.BAD})
    T.style_fig(fig2, 340); fig2.update_layout(title="Operational criticality by zone")
    b.plotly_chart(fig2, config=CONFIG)
    z = st.multiselect("Zone filter", [z.value for z in zc], default=[z.value for z in zc])
    tab = pd.DataFrame([{"id": n.id, "name": n.name, "zone": n.zone.value, "type": n.node_type.value, "Purdue level": n.purdue_level,
                         "criticality": n.criticality.value, "importance": n.operational_importance, "exposure": n.exposure,
                         "physical access": n.physical_access_exposure, "safety critical": n.safety_critical} for n in ig.nodes if n.zone.value in z])
    st.dataframe(tab, hide_index=True, column_config={"importance": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                                                       "exposure": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                                                       "physical access": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")})
    T.note("All importance, exposure and vulnerability values are assumptions for simulation. Real operators would supply asset registers and engineering data.")


def _selection(ev):
    try:
        pts = ev.selection.points
    except Exception:
        return None
    for p in pts or []:
        cd = p.get("customdata")
        cd = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if isinstance(cd, str):
            return cd
    return None


def page_topology(c):
    ig = c["ig"]
    T.hero("Network Topology", "Interactive typed dependency graph · click a component or relationship to inspect it", DATA_BADGES)
    f1, f2, f3, f4 = st.columns([1.2, 1.4, 1, 1])
    zones = f1.multiselect("Zones", list(T.ZONE_COLOR), default=list(T.ZONE_COLOR))
    layers = f2.multiselect("Relationship layers", list(T.EDGE_LABEL), default=list(T.EDGE_LABEL), format_func=lambda k: T.EDGE_LABEL[k])
    color_by = f3.selectbox("Colour nodes by", ["Initial condition", "Criticality", "Exposure", "Physical-access exposure"])
    q = f4.text_input("Search component", placeholder="e.g. SCADA, PH03")
    fills, cb = {}, None
    if color_by == "Criticality":
        m = {"low": "#475569", "medium": "#0EA5E9", "high": "#F59E0B", "critical": "#EF4444"}
        fills = {n.id: m[n.criticality.value] for n in ig.nodes}
    elif color_by in ("Exposure", "Physical-access exposure"):
        key = "exposure" if color_by == "Exposure" else "physical_access_exposure"
        fills = {n.id: float(getattr(n, key)) for n in ig.nodes}
        cb = {"scale": "YlOrRd", "min": 0, "max": 1, "title": color_by}
    dim = frozenset(n.id for n in ig.nodes if q and q.lower() not in (n.id + " " + n.name).lower())
    sel = st.session_state.get("sel_node", "OT01")
    fig = make_graph(ig, node_fill=fills or None, layers=layers, zones=zones, selected=sel, dim=dim, colorbar=cb, height=700)
    left, right = st.columns([3.2, 1.15])
    with left:
        ev = st.plotly_chart(fig, key="topo", on_select="rerun", selection_mode=("points",), config=CONFIG)
        T.zone_legend()
    picked = _selection(ev)
    if picked and not re.match(r"^E\d+$", picked):
        st.session_state["sel_node"] = picked
        sel = picked
    with right:
        ids = [n.id for n in ig.nodes]
        sel = st.selectbox("Selected component", ids, index=ids.index(sel) if sel in ids else 0, format_func=lambda i: f"{i} · {ig.node(i).name}")
        st.session_state["sel_node"] = sel
        n = ig.node(sel)
        st.markdown(f'<div class="ig-card" style="border-top:3px solid {T.ZONE_COLOR[n.zone.value]}"><h4>{n.name}</h4>'
                    f'<span style="color:{T.MUTED}">{n.node_type.value} · {n.zone.value} · Purdue L{n.purdue_level:g}</span><br>'
                    f'{T.badge(n.criticality.value.upper(), T.WARN)}{T.badge("SAFETY-CRITICAL", T.BAD) if n.safety_critical else ""}<br><br>'
                    f'importance <b>{n.operational_importance:.2f}</b><br>exposure <b>{n.exposure:.2f}</b> · vulnerability <b>{n.vulnerability:.2f}</b><br>'
                    f'physical access <b>{n.physical_access_exposure:.2f}</b><br>condition at start <b>{n.initial_condition.value}</b><br>'
                    f'<span style="color:{T.MUTED};font-size:.8rem">{n.description}</span></div>', unsafe_allow_html=True)
        st.caption("Telemetry features: " + ", ".join(n.telemetry_features))
    inn = [e for e in ig.edges if e.target == sel]
    out = [e for e in ig.edges if e.source == sel]

    def tab(es, other):
        return pd.DataFrame([{"edge": e.id, "other": getattr(e, other), "type": T.EDGE_LABEL[e.edge_type.value], "importance": e.importance,
                              "assumed p": e.traversal_probability, "dependency": e.dependency_strength,
                              "isolatable": (e.isolation_kind.value if e.isolatable else "-")} for e in es])

    a, b = st.columns(2)
    a.markdown("**Inbound relationships** (what reaches / feeds this component)")
    a.dataframe(tab(inn, "source"), hide_index=True)
    b.markdown("**Outbound relationships** (what this component can reach / affects)")
    b.dataframe(tab(out, "target"), hide_index=True)


def page_telemetry(c):
    ig, d = c["ig"], c["d"]
    T.hero("Telemetry", f"Synthetic industrial telemetry for scenario {c['sid']} · 1-minute resolution · ground-truth labels attached", DATA_BADGES)
    tel = d["telemetry"]
    ids = [n.id for n in ig.nodes]
    L, R = st.columns([1, 2])
    node = L.selectbox("Component", ids, index=ids.index("PH04") if "PH04" in ids else 0, format_func=lambda i: f"{i} · {ig.node(i).name}")
    feats = [f for f in tel.columns if f in TELEMETRY_FEATURES and tel[tel.component_id == node][f].notna().any()]
    chosen = R.multiselect("Features", feats, default=feats[:2])
    g = tel[tel.component_id == node].sort_values("step")
    fig = go.Figure()
    palette = [T.ACCENT, T.WARN, T.GOOD, T.MAGENTA]
    for i, f in enumerate(chosen):
        fig.add_scatter(x=g.step, y=g[f], mode="lines", name=f"{f} [{TELEMETRY_FEATURES[f].unit}]", line=dict(color=palette[i % 4], width=2))
    if chosen:
        sp = TELEMETRY_FEATURES[chosen[0]]
        fig.add_hrect(y0=sp.normal_low, y1=sp.normal_high, fillcolor=T.GOOD, opacity=0.07, line_width=0,
                      annotation_text=f"default normal range ({chosen[0]})", annotation_position="top left")
    lab = g.label.to_numpy()
    start = None
    for i in range(len(g) + 1):
        a = i < len(g) and lab[i] != "normal"
        if a and start is None:
            start = i
        if not a and start is not None:
            fig.add_vrect(x0=g.step.iloc[start], x1=g.step.iloc[i - 1], fillcolor=T.BAD, opacity=0.13, line_width=0)
            start = None
    T.style_fig(fig, 430)
    fig.update_layout(xaxis_title="minute", title=f"{node} · {ig.node(node).name}  (red band = ground-truth anomaly)")
    st.plotly_chart(fig, config=CONFIG)
    T.note("All values are synthetic model data with documented units and assumed ranges. They are not Colonial Pipeline telemetry. "
           "Node-specific nominal values (e.g. flow 400 m³/h at the tank) override the defaults below.")
    spec = pd.DataFrame([{"feature": f.name, "unit": f.unit, "default normal low": f.normal_low, "default normal high": f.normal_high,
                          "meaning": f.description} for f in TELEMETRY_FEATURES.values()])
    with st.expander("Telemetry catalogue: units, ranges and assumptions"):
        st.dataframe(spec, hide_index=True)
    ev = g[g.label != "normal"].groupby("label").agg(first_step=("step", "min"), last_step=("step", "max"), severity=("severity", "max")).reset_index()
    if len(ev):
        st.markdown("**Injected ground-truth events on this component**")
        st.dataframe(ev, hide_index=True)


def page_anomaly(c):
    ig, d = c["ig"], c["d"]
    T.hero("Anomaly Detection", "Per-component Isolation Forest · percentile-calibrated scores · persistence-based alerts", DATA_BADGES)
    sc = d["anomaly_scores"].copy()
    tel = d["telemetry"]
    q1, q2, q3 = st.columns([1.2, 1.2, 2])
    q = q1.slider("Alert threshold (calibrated score)", 0.90, 0.9999, 0.995, 0.0005, format="%.4f")
    pers = q2.slider("Persistence (consecutive minutes)", 1, 5, 2)
    show_truth = q3.checkbox("Overlay synthetic ground truth (✕)", value=True)
    sc = sc.sort_values(["component_id", "step"])
    sc["above"] = (sc.anomaly_score >= q).astype(int)
    sc["alert"] = sc.groupby("component_id").above.transform(lambda x: x.rolling(pers, min_periods=pers).sum()) >= pers
    order = [n.id for z in ("vendor", "it", "ot", "physical") for n in ig.nodes_by_zone(__import__("impactgraph.infrastructure.enums", fromlist=["Zone"]).Zone(z))]
    pv = sc.pivot(index="component_id", columns="step", values="anomaly_score").loc[order]
    fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=[f"{i} {ig.node(i).name[:18]}" for i in pv.index],
                               colorscale=[[0, "#0F1B33"], [0.9, "#1E3A8A"], [0.99, "#F59E0B"], [1, "#EF4444"]], zmin=0, zmax=1,
                               colorbar=dict(title="score", thickness=10)))
    al = sc[sc.alert]
    idx = {i: f"{i} {ig.node(i).name[:18]}" for i in order}
    fig.add_scatter(x=al.step, y=al.component_id.map(idx), mode="markers", marker=dict(color="white", size=4), name="alert")
    if show_truth:
        gt = tel[tel.label != "normal"]
        fig.add_scatter(x=gt.step, y=gt.component_id.map(idx), mode="markers", marker=dict(color="#22D3EE", size=4, symbol="x"), name="ground truth", opacity=0.6)
    T.style_fig(fig, 640)
    fig.update_layout(title="Calibrated anomaly score by component and minute", xaxis_title="minute", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, config=CONFIG)
    T.note("An alert means 'unusual compared with this component's normal behaviour', not 'confirmed attack'. Scores are calibrated against held-out normal data.")
    first = al.groupby("component_id").step.min().reset_index().rename(columns={"step": "first_alert_minute"})
    ar = d["anomaly_results"][["component_id", "max_score", "explanation"]].merge(first, on="component_id", how="left")
    ar["component"] = ar.component_id.map(lambda i: ig.node(i).name)
    ar["top feature (z-score)"] = ar.explanation.map(lambda s: (lambda e: f"{e[0]['feature']} ({e[0]['z']:+.1f}σ)" if e else "-")(json.loads(s)) if s else "-")
    risk = d["risk"][["component_id", "classifier_evidence"]]
    ar = ar.merge(risk, on="component_id", how="left").sort_values("first_alert_minute", na_position="last")
    st.markdown("**Alert table**")
    st.dataframe(ar[["component_id", "component", "first_alert_minute", "max_score", "top feature (z-score)", "classifier_evidence"]], hide_index=True,
                 column_config={"max_score": st.column_config.ProgressColumn("anomaly score", min_value=0, max_value=1, format="%.3f"),
                                "classifier_evidence": st.column_config.ProgressColumn("traffic-classifier evidence", min_value=0, max_value=1, format="%.2f")})
    comps = [i for i in ar.component_id if not pd.isna(ar.set_index("component_id").loc[i, "first_alert_minute"])] or order
    sel = st.selectbox("Why was this component flagged?", comps, format_func=lambda i: f"{i} · {ig.node(i).name}")
    row = d["anomaly_results"].set_index("component_id").loc[sel]
    ex = json.loads(row.explanation) if row.explanation else []
    if ex:
        edf = pd.DataFrame(ex)
        fig2 = px.bar(edf, x="z", y="feature", orientation="h", color="z", color_continuous_scale="RdBu_r", range_color=[-10, 10])
        T.style_fig(fig2, 240, legend=False); fig2.update_layout(title="Feature deviation from normal at the first alert (standard deviations)", coloraxis_showscale=False)
        st.plotly_chart(fig2, config=CONFIG)
        st.dataframe(edf.rename(columns={"value": "observed", "normal_mean": "normal mean"}), hide_index=True)
    else:
        st.info("This component did not raise an alert in the displayed episode.")
