import React, { useMemo } from "react";
import { COND_COLOR, EDGE_COLOR, EDGE_LABEL, ZONE_COLOR, ZONE_LABEL } from "./util.js";

const X = (x) => (x + 0.6) * 100;
const Y = (y) => (5.1 - y) * 100;
const SYMBOL = { vendor: "diamond", it: "square", ot: "hexagon", physical: "circle" };
const short = (s, n = 17) => (s.length <= n ? s : s.slice(0, n - 1) + "…");

function edgePath(p, q, off, others, r = 0.3) {
  const dx = q[0] - p[0], dy = q[1] - p[1], d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d, nx = -uy, ny = ux;
  const sx = p[0] + ux * r + nx * off, sy = p[1] + uy * r + ny * off, ex = q[0] - ux * r + nx * off, ey = q[1] - uy * r + ny * off;
  const pts = (c) => {
    const mx = (sx + ex) / 2 + nx * c, my = (sy + ey) / 2 + ny * c;
    return Array.from({ length: 15 }, (_, i) => { const t = i / 14; return [(1 - t) ** 2 * sx + 2 * (1 - t) * t * mx + t * t * ex, (1 - t) ** 2 * sy + 2 * (1 - t) * t * my + t * t * ey]; });
  };
  const clear = (path) => Math.min(9, ...path.flatMap(([x, y]) => others.map(([ox, oy]) => Math.hypot(x - ox, y - oy))));
  let best = pts(0);
  if (clear(best) < 0.33) {
    for (const c of [0.125 * d, -0.125 * d, 0.225 * d, -0.225 * d]) {
      const cand = pts(c);
      if (clear(cand) > clear(best)) best = cand;
      if (clear(best) >= 0.33) break;
    }
  }
  return best;
}

function Shape({ kind, r, fill, stroke, opacity }) {
  const common = { fill, stroke, strokeWidth: 3, opacity };
  if (kind === "circle") return <circle r={r} {...common} />;
  if (kind === "square") return <rect x={-r} y={-r} width={2 * r} height={2 * r} rx="2" {...common} />;
  if (kind === "diamond") return <polygon points={`0,${-r * 1.25} ${r * 1.25},0 0,${r * 1.25} ${-r * 1.25},0`} {...common} />;
  const pts = Array.from({ length: 6 }, (_, i) => { const a = (Math.PI / 3) * i; return `${(r * 1.15 * Math.cos(a)).toFixed(1)},${(r * 1.15 * Math.sin(a)).toFixed(1)}`; }).join(" ");
  return <polygon points={pts} {...common} />;
}

export default function Graph({ topo, fills = {}, extra = {}, layers, highlight = new Set(), isolated = new Set(), selected, onSelect, labels = "full", dim = new Set(), colorbar }) {
  const L = layers || new Set(Object.keys(EDGE_COLOR));
  const pos = topo.pos;
  const nodes = topo.nodes;
  const edges = useMemo(() => {
    const groups = {};
    topo.edges.forEach((e) => { (groups[e.source + ">" + e.target] ||= []).push(e); });
    const res = [];
    for (const [key, es] of Object.entries(groups)) {
      const [u, v] = key.split(">");
      es.forEach((e, k) => {
        const off = (k - (es.length - 1) / 2) * 0.11 + (groups[v + ">" + u] ? 0.07 : 0);
        const others = Object.keys(pos).filter((n) => n !== u && n !== v).map((n) => pos[n]);
        res.push({ e, path: edgePath(pos[u], pos[v], off, others) });
      });
    }
    return res;
  }, [topo]);
  const colors = new Set(Object.values(EDGE_COLOR).concat(["#E879F9", "#FB7185"]));
  const ordered = [...edges].filter((x) => L.has(x.e.edge_type)).sort((a, b) => (highlight.has(a.e.id) || isolated.has(a.e.id) ? 1 : 0) - (highlight.has(b.e.id) || isolated.has(b.e.id) ? 1 : 0));
  return (
    <svg className="graph" viewBox="0 0 1270 625" role="img" aria-label="Infrastructure topology graph">
      <defs>
        {[...colors].map((c) => (
          <marker key={c} id={"a" + c.slice(1)} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={c} /></marker>
        ))}
      </defs>
      {Object.entries(topo.bands).map(([z, [y0, y1]]) => (
        <g key={z}>
          <rect x={X(-0.55)} y={Y(y1)} width={(11.9 + 0.55) * 100} height={(y1 - y0) * 100} rx="4" fill={ZONE_COLOR[z]} fillOpacity="0.07" stroke={ZONE_COLOR[z]} strokeOpacity="0.5" />
          <text x={X(-0.45)} y={Y(y1) + 16} fill={ZONE_COLOR[z]} fontSize="11" fontWeight="600">{ZONE_LABEL[z]}</text>
        </g>
      ))}
      {ordered.map(({ e, path }) => {
        const iso = isolated.has(e.id), hi = highlight.has(e.id), et = e.edge_type;
        const color = iso ? "#E879F9" : hi ? "#FB7185" : EDGE_COLOR[et];
        const w = et === "physical_flow" ? 4.5 : hi ? 3.4 : iso ? 2.8 : 1.4;
        const d = "M" + path.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" L");
        const dash = iso || et === "operational_dep" || et === "service_dep" ? "7 5" : undefined;
        const mid = path[7];
        return (
          <g key={e.id}>
            <path d={d} fill="none" stroke={color} strokeWidth={w} strokeDasharray={dash} opacity={hi || iso ? 1 : et === "physical_flow" ? 0.9 : 0.6} markerEnd={`url(#a${color.slice(1)})`} />
            <path d={d} fill="none" stroke="transparent" strokeWidth="10"><title>{`${e.id}  ${e.source} → ${e.target}\n${EDGE_LABEL[et]}${e.traversal_probability != null ? `\nassumed per-attempt probability ${e.traversal_probability}\nconditions: ${e.access_conditions.join(", ")}` : ""}${e.dependency_strength != null ? `\ndependency strength ${e.dependency_strength}` : ""}${e.isolatable ? `\nisolatable (${e.isolation_kind}), cost ${e.isolation_cost}` : ""}`}</title></path>
          </g>
        );
      })}
      {nodes.map((n) => {
        const [px, py] = pos[n.id];
        const r = 11 + 10 * n.operational_importance;
        const fill = fills[n.id] ? (COND_COLOR[fills[n.id]] || fills[n.id]) : COND_COLOR.normal;
        const sel = selected === n.id;
        return (
          <g key={n.id} transform={`translate(${X(px)},${Y(py)})`} style={{ cursor: onSelect ? "pointer" : "default" }} onClick={() => onSelect && onSelect(n.id)} opacity={dim.has(n.id) ? 0.28 : 1}>
            {sel && <circle r={r + 12} fill="none" stroke="#22D3EE" strokeWidth="3" />}
            <Shape kind={SYMBOL[n.zone]} r={r} fill={fill} stroke={ZONE_COLOR[n.zone]} />
            {labels && (<>
              <text y={r + 15} textAnchor="middle" fill="#E6EDF7" fontSize="11" fontWeight="700">{n.id}</text>
              {labels === "full" && <text y={r + 28} textAnchor="middle" fill="#8FA3BF" fontSize="9.5">{short(n.name)}</text>}
            </>)}
            <title>{`${n.id} · ${n.name}\nzone ${n.zone} · ${n.node_type}\ncriticality ${n.criticality} (importance ${n.operational_importance})\nexposure ${n.exposure} · vulnerability ${n.vulnerability} · physical access ${n.physical_access_exposure}${extra[n.id] ? "\n" + extra[n.id] : ""}`}</title>
          </g>
        );
      })}
      {colorbar && (
        <g transform="translate(1215,120)">
          <defs><linearGradient id="cb" x1="0" y1="1" x2="0" y2="0">{colorbar.stops.map((c, i) => <stop key={i} offset={`${(100 * i) / (colorbar.stops.length - 1)}%`} stopColor={c} />)}</linearGradient></defs>
          <rect width="12" height="220" fill="url(#cb)" rx="2" />
          <text x="-2" y="-8" fill="#8FA3BF" fontSize="10" textAnchor="middle">{colorbar.title}</text>
          <text x="16" y="10" fill="#8FA3BF" fontSize="10">{colorbar.max}</text><text x="16" y="220" fill="#8FA3BF" fontSize="10">0</text>
        </g>
      )}
    </svg>
  );
}

export function GraphLegend() {
  return (
    <div className="legend">
      {Object.entries(ZONE_COLOR).map(([z, c]) => <span key={z}><i className="dot" style={{ borderColor: c }} />{z.toUpperCase()}</span>)}
      {["compromised", "failed", "degraded"].map((k) => <span key={k}><i className="dot" style={{ background: COND_COLOR[k], borderColor: COND_COLOR[k] }} />{k}</span>)}
      {["network", "auth", "control", "physical_flow", "service_dep"].map((k) => <span key={k}><i className="line" style={{ background: EDGE_COLOR[k] }} />{EDGE_LABEL[k]}</span>)}
      <span><i className="line" style={{ background: "#FB7185" }} />Attack path</span><span><i className="line dashed" style={{ borderColor: "#E879F9" }} />Isolated link</span>
    </div>
  );
}
