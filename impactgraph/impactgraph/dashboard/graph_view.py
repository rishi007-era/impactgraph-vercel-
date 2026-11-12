"""Zone-banded, Purdue-style topology rendering with Plotly. Every visual element is driven by model data."""
from __future__ import annotations

import math

import plotly.graph_objects as go

from . import theme as T

POS = {  # bands top to bottom: vendor, IT hub + IT servers, OT supervisory, OT controllers, physical pipeline
    "V03": (2.0, 4.5), "V04": (4.6, 4.5), "V01": (7.4, 4.5), "V02": (10.0, 4.5),
    "IT01": (6.4, 3.5), "IT05": (1.2, 2.6), "IT04": (3.0, 2.6), "IT06": (4.8, 2.6), "IT03": (6.9, 2.6), "IT02": (8.9, 2.6),
    "OT01": (6.4, 1.85), "OT02": (8.6, 1.85), "OT03": (10.7, 1.85),
    "OT05": (1.5, 1.0), "OT04": (3.6, 1.0), "OT06": (5.2, 1.0),
    "PH01": (0.7, 0.0), "PH02": (2.2, 0.0), "PH03": (3.7, 0.0), "PH04": (5.2, 0.0), "PH05": (6.7, 0.0),
    "PH06": (8.2, -0.55), "PH07": (9.7, 0.0), "PH08": (11.2, 0.0),
}
BANDS = {"vendor": (4.15, 5.0), "it": (2.2, 3.85), "ot": (0.62, 2.18), "physical": (-1.05, 0.42)}
SYMBOL = {"vendor": "diamond", "it": "square", "ot": "hexagon", "physical": "circle"}


def _short(name, n=17):
    return name if len(name) <= n else name[:n - 1] + "…"


def _shorten(p, q, r):
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1
    return (p[0] + dx / d * r, p[1] + dy / d * r), (q[0] - dx / d * r, q[1] - dy / d * r), math.degrees(math.atan2(dy, dx))


def _path(p, q, off, others, r=0.30):
    """Polyline from p to q (shortened by node radius), curved when a straight line would cross another node."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    nx_, ny_ = -uy, ux
    sx, sy = p[0] + ux * r + nx_ * off, p[1] + uy * r + ny_ * off
    ex, ey = q[0] - ux * r + nx_ * off, q[1] - uy * r + ny_ * off

    def pts(c):
        mx, my = (sx + ex) / 2 + nx_ * c, (sy + ey) / 2 + ny_ * c
        return [((1 - t) ** 2 * sx + 2 * (1 - t) * t * mx + t * t * ex, (1 - t) ** 2 * sy + 2 * (1 - t) * t * my + t * t * ey)
                for t in [i / 14 for i in range(15)]]

    def clearance(path):
        return min((math.hypot(x - ox, y - oy) for x, y in path for ox, oy in others), default=9)

    best, bc = pts(0.0), 0.0
    if clearance(best) < 0.33:
        for c in (0.25 * d * 0.5, -0.25 * d * 0.5, 0.45 * d * 0.5, -0.45 * d * 0.5):
            cand = pts(c)
            if clearance(cand) > clearance(best):
                best = cand
            if clearance(best) >= 0.33:
                break
    return best


def make_graph(ig, node_fill=None, node_extra=None, layers=None, highlight=frozenset(), isolated=frozenset(),
               selected=None, zones=None, height=720, title="", labels=True, node_text_color=None, dim=frozenset(),
               colorbar=None, size_attr="operational_importance"):
    node_fill = node_fill or {}
    node_extra = node_extra or {}
    layers = set(layers) if layers is not None else {"network", "auth", "control", "physical_flow", "operational_dep", "service_dep"}
    zones = set(zones) if zones is not None else set(T.ZONE_COLOR)
    fig = go.Figure()
    for z, (y0, y1) in BANDS.items():
        if z not in zones:
            continue
        fig.add_shape(type="rect", x0=-0.55, x1=11.9, y0=y0, y1=y1, line=dict(color=T.ZONE_COLOR[z], width=1),
                      fillcolor=T.ZONE_COLOR[z], opacity=0.07, layer="below")
        fig.add_annotation(x=-0.45, y=y1 - 0.05, text=T.ZONE_LABEL[z], showarrow=False, xanchor="left", yanchor="top",
                           font=dict(size=10, color=T.ZONE_COLOR[z]))
    visible = {n.id for n in ig.nodes if n.zone.value in zones}
    groups = {}
    for e in ig.edges:
        groups.setdefault((e.source, e.target), []).append(e)
    seen_legend = set()
    mid_x, mid_y, mid_txt, mid_id = [], [], [], []
    for (u, v), es in groups.items():
        if u not in visible or v not in visible:
            continue
        for k, e in enumerate(es):
            if e.edge_type.value not in layers:
                continue
            off = (k - (len(es) - 1) / 2) * 0.11 + (0.07 if (v, u) in groups else 0.0)
            others = [POS[n] for n in POS if n not in (u, v) and n in visible]
            path = _path(POS[u], POS[v], off, others)
            et = e.edge_type.value
            is_iso, is_hi = e.id in isolated, e.id in highlight
            color = T.MAGENTA if is_iso else ("#FB7185" if is_hi else T.EDGE_COLOR[et])
            width = 4.5 if et == "physical_flow" else (3.2 if is_hi else (2.6 if is_iso else 1.3))
            dash = "dash" if (is_iso or et in ("operational_dep", "service_dep")) else "solid"
            opacity = 1.0 if (is_hi or is_iso) else (0.9 if et == "physical_flow" else 0.6)
            name = "Isolated link" if is_iso else ("Attack path" if is_hi else T.EDGE_LABEL[et])
            fig.add_trace(go.Scatter(
                x=[c[0] for c in path], y=[c[1] for c in path], mode="lines+markers", line=dict(color=color, width=width, dash=dash),
                marker=dict(symbol="arrow", size=[0] * (len(path) - 1) + [12 if et != "physical_flow" else 15], color=color, angleref="previous"),
                opacity=opacity, hoverinfo="skip", name=name, legendgroup=name, showlegend=name not in seen_legend))
            seen_legend.add(name)
            mid = path[len(path) // 2]
            mid_x.append(mid[0]); mid_y.append(mid[1]); mid_id.append(e.id)
            cond = ", ".join(e.access_conditions) or "-"
            extra = ""
            if e.traversal_probability is not None:
                extra += f"<br>assumed per-attempt probability: {e.traversal_probability:.2f}<br>access conditions: {cond}"
            if e.dependency_strength is not None:
                extra += f"<br>dependency strength: {e.dependency_strength:.2f}"
            if e.flow_capacity_m3h is not None:
                extra += f"<br>flow capacity: {e.flow_capacity_m3h:.0f} m³/h (model units)"
            if e.isolatable:
                extra += f"<br>isolatable ({e.isolation_kind.value}), cost {e.isolation_cost:.1f}"
            mid_txt.append(f"<b>{e.id}</b>  {u} → {v}<br>{T.EDGE_LABEL[et]}{extra}")
    fig.add_trace(go.Scatter(x=mid_x, y=mid_y, mode="markers", marker=dict(size=9, color="rgba(0,0,0,0)"), hovertext=mid_txt,
                             hoverinfo="text", customdata=mid_id, showlegend=False, name="edges"))
    xs, ys, fills, lines, sizes, texts, hovers, ids, syms = [], [], [], [], [], [], [], [], []
    for n in ig.nodes:
        if n.id not in visible:
            continue
        x, y = POS[n.id]
        xs.append(x); ys.append(y); ids.append(n.id)
        fills.append(node_fill.get(n.id, T.COND_COLOR[n.current_condition.value]))
        lines.append(T.ZONE_COLOR[n.zone.value])
        base = getattr(n, size_attr) if size_attr else 0.5
        sizes.append(20 + 22 * float(base))
        syms.append(SYMBOL[n.zone.value])
        texts.append(f"<b>{n.id}</b>" if labels == "id" else (f"<b>{n.id}</b><br>{_short(n.name)}" if labels else ""))
        ex = node_extra.get(n.id, "")
        hovers.append(f"<b>{n.id} · {n.name}</b><br>zone: {n.zone.value}  ·  type: {n.node_type.value}<br>"
                      f"criticality: {n.criticality.value} (importance {n.operational_importance:.2f})<br>"
                      f"exposure {n.exposure:.2f} · vulnerability {n.vulnerability:.2f} · physical access {n.physical_access_exposure:.2f}"
                      f"{'<br>' + ex if ex else ''}")
    op = [0.28 if i in dim else 1.0 for i in ids]
    marker = dict(size=sizes, color=fills, symbol=syms, opacity=op, line=dict(color=lines, width=3))
    if colorbar:
        marker.update(colorscale=colorbar["scale"], cmin=colorbar["min"], cmax=colorbar["max"], showscale=True,
                      colorbar=dict(title=colorbar["title"], thickness=12, len=0.5, x=1.0), color=[node_fill[i] for i in ids])
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=texts, textposition="bottom center",
                             textfont=dict(size=9, color=node_text_color or T.TEXT), marker=marker, hovertext=hovers,
                             hoverinfo="text", customdata=ids, name="Components", showlegend=False))
    if selected and selected in POS and selected in visible:
        fig.add_trace(go.Scatter(x=[POS[selected][0]], y=[POS[selected][1]], mode="markers", hoverinfo="skip", showlegend=False,
                                 marker=dict(size=52, color="rgba(0,0,0,0)", line=dict(color=T.ACCENT, width=3), symbol="circle-open")))
    fig.update_xaxes(visible=False, range=[-0.6, 12.1], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-1.15, 5.1], fixedrange=True, scaleanchor=None)
    T.style_fig(fig, height=height)
    fig.update_layout(title=dict(text=title, font=dict(size=14)), margin=dict(l=0, r=0, t=36 if title else 8, b=0),
                      legend=dict(orientation="h", y=-0.02, x=0, font=dict(size=10)), hoverlabel=dict(bgcolor=T.PANEL2, font_size=12))
    return fig
