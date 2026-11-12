import React from "react";

export function GroupedBars({ groups, series, values, max, fmt = (v) => v.toFixed(2), height = 300, yTitle }) {
  const W = 620, H = height, L = 46, R = 10, T = 14, B = 54;
  const iw = W - L - R, ih = H - T - B, m = (max ?? Math.max(...values.flat()) * 1.12) || 1;
  const gw = iw / groups.length, bw = Math.min(30, (gw * 0.8) / series.length);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * m);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img">
      {ticks.map((t, i) => (<g key={i}><line x1={L} x2={W - R} y1={T + ih - (t / m) * ih} y2={T + ih - (t / m) * ih} stroke="#243251" strokeDasharray="3 4" /><text x={L - 6} y={T + ih - (t / m) * ih + 4} fontSize="10" fill="#8FA3BF" textAnchor="end">{fmt(t)}</text></g>))}
      {groups.map((g, gi) => (
        <g key={g} transform={`translate(${L + gi * gw + gw / 2 - (bw * series.length) / 2},0)`}>
          {series.map((s, si) => { const v = values[si][gi], h = (v / m) * ih; return (<g key={s.name}><rect x={si * bw} y={T + ih - h} width={bw - 2} height={Math.max(h, 0.5)} fill={s.color} rx="2"><title>{`${s.name}: ${fmt(v)}`}</title></rect><text x={si * bw + (bw - 2) / 2} y={T + ih - h - 4} fontSize="9" fill="#E6EDF7" textAnchor="middle">{fmt(v)}</text></g>); })}
          <text x={(bw * series.length) / 2} y={H - 30} fontSize="11" fill="#E6EDF7" textAnchor="middle">{g}</text>
        </g>
      ))}
      {yTitle && <text x="12" y={T + ih / 2} fontSize="10" fill="#8FA3BF" transform={`rotate(-90 12 ${T + ih / 2})`} textAnchor="middle">{yTitle}</text>}
    </svg>
  );
}

export function HBars({ items, max = 1, fmt = (v) => (100 * v).toFixed(0) + "%", height }) {
  const rowH = 22, H = height || items.length * rowH + 24, L = 190, W = 620, iw = W - L - 40;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img">
      {items.map((it, i) => (
        <g key={it.label} transform={`translate(0,${12 + i * rowH})`}>
          <text x={L - 8} y="12" fontSize="10.5" fill="#E6EDF7" textAnchor="end">{it.label}</text>
          <rect x={L} y="2" width={Math.max((it.value / max) * iw, 1)} height="14" fill={it.color} rx="2"><title>{`${it.label}: ${fmt(it.value)}`}</title></rect>
          {it.lo != null && <g stroke="#CBD5E1" strokeWidth="1.2"><line x1={L + (it.lo / max) * iw} x2={L + (it.hi / max) * iw} y1="9" y2="9" /><line x1={L + (it.hi / max) * iw} x2={L + (it.hi / max) * iw} y1="5" y2="13" /><line x1={L + (it.lo / max) * iw} x2={L + (it.lo / max) * iw} y1="5" y2="13" /></g>}
          <text x={L + (it.hi ?? it.value) / max * iw + 6} y="13" fontSize="10" fill="#8FA3BF">{fmt(it.value)}</text>
        </g>
      ))}
    </svg>
  );
}

export function Matrix({ cm, labels, normalize = true }) {
  const n = labels.length, cell = Math.min(46, 460 / n), L = 100, T = 70, W = L + n * cell + 10, H = T + n * cell + 10;
  const rows = cm.map((r) => { const s = r.reduce((a, b) => a + b, 0) || 1; return normalize ? r.map((v) => v / s) : r; });
  const mx = Math.max(...rows.flat()) || 1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img">
      {labels.map((l, i) => (<g key={l}><text x={L - 6} y={T + i * cell + cell / 2 + 3} fontSize="9.5" fill="#E6EDF7" textAnchor="end">{l}</text><text transform={`translate(${L + i * cell + cell / 2},${T - 6}) rotate(-40)`} fontSize="9.5" fill="#E6EDF7">{l}</text></g>))}
      {rows.map((r, i) => r.map((v, j) => (<g key={i + "-" + j}><rect x={L + j * cell} y={T + i * cell} width={cell - 1} height={cell - 1} fill={`rgba(56,189,248,${0.08 + 0.85 * (v / mx)})`} /><text x={L + j * cell + cell / 2} y={T + i * cell + cell / 2 + 3} fontSize="9" fill="#E6EDF7" textAnchor="middle">{cm[i][j]}</text></g>)))}
    </svg>
  );
}
