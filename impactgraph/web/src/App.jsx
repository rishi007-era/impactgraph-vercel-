import React, { useEffect, useMemo, useRef, useState } from "react";
import Graph, { GraphLegend } from "./Graph.jsx";
import { GroupedBars, HBars, Matrix } from "./charts.jsx";
import { COND_COLOR, EDGE_COLOR, EDGE_LABEL, MODE, STRATEGY_COLOR, STRATEGY_LABEL, STRATEGY_ORDER, ZONE_COLOR, f2, pct, replayMax, replayState } from "./util.js";

const REPO_URL = import.meta.env.VITE_REPO_URL || "";
const TABS = [["summary", "Summary"], ["replay", "Topology & Replay"], ["paths", "Attack Paths"], ["risk", "Risk"], ["contain", "Containment"], ["eval", "Evaluation"], ["about", "About"]];
const Badge = ({ t, c }) => <span className="badge" style={{ color: c, borderColor: c, background: c + "1A" }}>{t}</span>;
const Kpi = ({ l, v, s, c = "#22D3EE" }) => <div className="kpi" style={{ "--c": c }}><div className="l">{l}</div><div className="v">{v}</div><div className="s">{s}</div></div>;
const Honesty = () => <><Badge t="SYNTHETIC TELEMETRY" c="#22D3EE" /><Badge t="ASSUMED PROBABILITIES" c="#FBBF24" /><Badge t="ADVISORY ONLY · NO REAL SYSTEMS" c="#34D399" /></>;
const strat = (sc, k) => sc.strategies.find((s) => s.key === k);

function useHash() {
  const parse = () => { const [, tab, sid] = (location.hash || "").split("/"); return { tab: TABS.some((t) => t[0] === tab) ? tab : "summary", sid: sid || "S2" }; };
  const [h, setH] = useState(parse());
  useEffect(() => { const f = () => setH(parse()); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return [h, (tab, sid) => { location.hash = `/${tab}/${sid}`; }];
}

export default function App() {
  const [data, setData] = useState(null), [err, setErr] = useState("");
  const [{ tab, sid }, go] = useHash();
  useEffect(() => { fetch("./data.json").then((r) => r.json()).then(setData).catch((e) => setErr(String(e))); }, []);
  if (err) return <div className="shell"><div className="note">Could not load data.json: {err}</div></div>;
  if (!data) return <div className="shell muted">Loading results…</div>;
  const sids = Object.keys(data.scenarios), sc = data.scenarios[sids.includes(sid) ? sid : sids[0]];
  const props = { data, sc, topo: data.topology, go: (t) => go(t, sc.id) };
  return (
    <div className="shell">
      <header className="top">
        <div className="brand">⬡ ImpactGraph<small>Cyber-physical impact &amp; resilience engine · Phase 1 results viewer</small></div>
        <div className="spacer" />
        <label className="muted small">Scenario&nbsp;
          <select value={sc.id} onChange={(e) => go(tab, e.target.value)}>{sids.map((s) => <option key={s} value={s}>{s} · {data.scenarios[s].name.split("(")[0].trim().slice(0, 48)}</option>)}</select>
        </label>
      </header>
      <nav className="tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => go(k, sc.id)}>{l}</button>)}</nav>
      {tab === "summary" && <Summary {...props} />}
      {tab === "replay" && <Replay key={sc.id} {...props} />}
      {tab === "paths" && <Paths key={sc.id} {...props} />}
      {tab === "risk" && <Risk key={sc.id} {...props} />}
      {tab === "contain" && <Contain key={sc.id} {...props} />}
      {tab === "eval" && <Evaluation {...props} />}
      {tab === "about" && <About {...props} />}
      <footer>All outputs come from simulation of an assumed model with synthetic telemetry. Not a forecast. Advisory only. This site shows pre-computed results (seed {sc.run.seed}, {sc.run.trials} Monte Carlo trials); the live simulator is the Streamlit app in the same repository.</footer>
    </div>
  );
}

function Summary({ sc, go }) {
  const none = strat(sc, "no_isolation"), rec = strat(sc, "impactgraph_greedy"), shut = strat(sc, "full_shutdown");
  const [mt, mc] = MODE[sc.mode];
  const groups = STRATEGY_ORDER.map((k) => STRATEGY_LABEL[k].replace("Full precautionary ", "Full ").replace("ImpactGraph recommendation", "ImpactGraph"));
  const sers = [{ name: "Objective J", color: "#22D3EE" }];
  return (<>
    <div className="hero"><h1>{sc.name}</h1><p>{sc.description}</p><Badge t={mt} c={mc} /><Honesty /></div>
    <div className="grid g5">
      <Kpi l="Expected impact · no isolation" v={f2(none.impact)} s="0 = none, 1 = total" c="#EF4444" />
      <Kpi l="Expected impact · ImpactGraph" v={f2(rec.impact)} s={`${pct(1 - rec.impact / Math.max(none.impact, 1e-9))} lower than no isolation`} c="#34D399" />
      <Kpi l="Throughput kept · ImpactGraph" v={pct(rec.throughput)} s={`no isolation ${pct(none.throughput)} · full shutdown ${pct(shut.throughput)}`} />
      <Kpi l="Chance a physical asset fails" v={pct(none.phys_hit)} s={`after isolation ${pct(rec.phys_hit)} (simulated frequency)`} c="#FBBF24" />
      <Kpi l="Expected components affected" v={`${sc.propagation.reduce((a, r) => a + r.p_affected, 0).toFixed(1)} / 24`} s="sum of simulated hit frequencies" c="#E879F9" />
    </div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div>
        <div className="card"><h3>Recommended containment (advisory)</h3>
          {sc.recommendations.length ? sc.recommendations.map((r) => <div className="step" key={r.step}><b>Step {r.step}</b> · ΔJ −{f2(r.delta_j, 3)}<br />{r.explanation}</div>) : <div className="step">No isolation was judged worthwhile under the objective for this scenario.</div>}
        </div>
        <div className="advice">Recommendations are decision support computed inside a simulation. ImpactGraph never sends commands to real industrial systems.</div>
        <div className="card"><h3>Assumptions behind this scenario</h3><ul className="tight small">{sc.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></div>
      </div>
      <div className="card"><h3>Strategy comparison · same simulated incidents</h3>
        <GroupedBars groups={groups} series={sers} values={[STRATEGY_ORDER.map((k) => strat(sc, k).objective)]} yTitle="objective J (lower is better)" />
        <GroupedBars groups={groups} series={[{ name: "Throughput kept", color: "#34D399" }]} values={[STRATEGY_ORDER.map((k) => strat(sc, k).throughput * 100)]} max={100} fmt={(v) => v.toFixed(0)} yTitle="throughput kept, % (higher is better)" />
        <p className="muted small">Full shutdown stops all deliveries by design, which is why its objective is high even when no damage occurs.</p>
        <button className="primary" onClick={() => go("replay")}>Replay this incident →</button>
      </div>
    </div></>);
}

function Replay({ sc, topo, go }) {
  const [variant, setVariant] = useState("before"), [step, setStep] = useState(0), [playing, setPlaying] = useState(false), [sel, setSel] = useState("OT01");
  const rp = sc.replay[variant], maxT = Math.ceil(Math.max(replayMax(sc.replay.before.nodes), replayMax(sc.replay.after.nodes), 1));
  const timer = useRef();
  useEffect(() => { if (!playing) return; timer.current = setInterval(() => setStep((s) => { if (s >= maxT) { setPlaying(false); return s; } return s + 1; }), 900); return () => clearInterval(timer.current); }, [playing, maxT]);
  const fills = replayState(rp.nodes, step, step >= maxT);
  const hi = new Set(rp.edges.filter((e) => e.t_end <= step).map((e) => e.edge_id));
  const iso = variant === "after" ? new Set(strat(sc, "impactgraph_greedy").isolated) : new Set();
  const events = rp.nodes.flatMap((r) => [...(r.t_compromised != null && r.t_compromised <= step ? [{ hop: r.t_compromised, c: r.component_id, e: "compromised" }] : []), ...(r.t_failed != null && r.t_failed <= step ? [{ hop: r.t_failed, c: r.component_id, e: `failed (${r.fail_kind})` }] : [])]).sort((a, b) => a.hop - b.hop);
  const prop = [...sc.propagation].sort((a, b) => b.p_affected - a.p_affected).slice(0, 16);
  const nm = (id) => topo.nodes.find((n) => n.id === id);
  const node = nm(sel);
  const inn = topo.edges.filter((e) => e.target === sel), out = topo.edges.filter((e) => e.source === sel);
  return (<>
    <div className="controls">
      <button className={variant === "before" ? "on" : ""} onClick={() => setVariant("before")}>No isolation</button>
      <button className={variant === "after" ? "on" : ""} onClick={() => setVariant("after")}>With ImpactGraph isolation</button>
      <span className="muted small">step {step} / {maxT}</span>
      <input type="range" min="0" max={maxT} value={step} onChange={(e) => { setPlaying(false); setStep(+e.target.value); }} />
      <button className="primary" onClick={() => { if (step >= maxT) setStep(0); setPlaying(!playing); }}>{playing ? "❚❚ Pause" : "▶ Play replay"}</button>
    </div>
    <div className="grid g21">
      <div><Graph topo={topo} fills={fills} highlight={hi} isolated={iso} selected={sel} onSelect={setSel} /><GraphLegend /></div>
      <div>
        <div className="card" style={{ borderTop: `3px solid ${ZONE_COLOR[node.zone]}` }}><h3>{node.id} · {node.name}</h3>
          <div className="muted small">{node.node_type} · {node.zone} · Purdue L{node.purdue_level}</div>
          <div style={{ margin: "6px 0" }}><span className="pill">{node.criticality}</span> {node.safety_critical && <span className="pill" style={{ color: "#EF4444" }}>safety-critical</span>}</div>
          <div className="small">importance <b>{f2(node.operational_importance)}</b> · exposure <b>{f2(node.exposure)}</b><br />vulnerability <b>{f2(node.vulnerability)}</b> · physical access <b>{f2(node.physical_access_exposure)}</b></div>
          <div className="muted small" style={{ marginTop: 6 }}>{node.description}</div>
          <div className="small" style={{ marginTop: 8 }}><b>In:</b> {inn.map((e) => `${e.source} (${EDGE_LABEL[e.edge_type]})`).join(", ") || "-"}<br /><b>Out:</b> {out.map((e) => `${e.target} (${EDGE_LABEL[e.edge_type]})`).join(", ") || "-"}</div>
        </div>
        <div className="card"><h3>Events up to this step</h3><div className="scroll" style={{ maxHeight: 230 }}><table><thead><tr><th>hop</th><th>component</th><th>event</th></tr></thead><tbody>{events.map((e, i) => <tr key={i}><td>{e.hop}</td><td>{e.c} · {nm(e.c).name}</td><td>{e.e}</td></tr>)}</tbody></table></div></div>
      </div>
    </div>
    <div className="card"><h3>Simulated hit frequency per component ({sc.run.trials} trials, 95% Wilson interval)</h3>
      <HBars items={[...prop].map((p) => ({ label: `${p.component_id} ${nm(p.component_id).name.slice(0, 22)}`, value: p.p_affected, lo: p.ci_low, hi: p.ci_high, color: ZONE_COLOR[nm(p.component_id).zone] }))} />
      <div className="note">These are SIMULATION FREQUENCIES under assumed transition probabilities. They are not calibrated real-world probabilities. The replay shows one representative trial, not a prediction.</div></div>
  </>);
}

function Paths({ sc, topo }) {
  const targets = [...new Set(sc.paths.map((p) => p.target))];
  const [t, setT] = useState(targets[0]), [rk, setRk] = useState(1);
  if (!targets.length) return <div className="card"><h3>No cyber route in this scenario</h3><p>{sc.description}</p><div className="note">This is a physical-sabotage scenario: there is no cyber entry path. See Topology &amp; Replay for the physical effects.</div></div>;
  const routes = sc.paths.filter((p) => p.target === t).sort((a, b) => a.rank - b.rank), p = routes.find((r) => r.rank === rk) || routes[0];
  const nodes = Object.fromEntries(p.nodes.map((n) => [n, "compromised"]));
  return (<>
    <div className="controls"><label className="muted small">Target&nbsp;<select value={t} onChange={(e) => { setT(e.target.value); setRk(1); }}>{targets.map((x) => <option key={x} value={x}>{x} · {topo.nodes.find((n) => n.id === x).name}</option>)}</select></label>
      {routes.map((r) => <button key={r.rank} className={p.rank === r.rank ? "on" : ""} onClick={() => setRk(r.rank)}>Route {r.rank} · {pct(r.probability, 1)}</button>)}</div>
    <Graph topo={topo} fills={nodes} highlight={new Set(p.hops.map((h) => h.edge))} />
    <div className="grid g3" style={{ marginTop: 14 }}><Kpi l="Route likelihood" v={pct(p.probability, 1)} s="product of per-link success within attempts (model)" c="#EF4444" /><Kpi l="Hops" v={p.length} s={p.nodes.join(" → ")} /><Kpi l="Security-boundary crossings" v={p.boundary_crossings.length} s={p.boundary_crossings.join(", ") || "none"} c="#FBBF24" /></div>
    <div className="card" style={{ marginTop: 14 }}><h3>Hop-by-hop feasibility (every route is explained, not just drawn)</h3><table><thead><tr><th>hop</th><th>from → to</th><th>link</th><th>type</th><th>zones</th><th>p / attempt</th><th>p within attempts</th><th>why feasible</th></tr></thead><tbody>
      {p.hops.map((h, i) => <tr key={i}><td>{i + 1}</td><td>{h.source} → {h.target}</td><td>{h.edge}</td><td>{h.type}</td><td>{h.zones}</td><td>{f2(h.p_single)}</td><td>{f2(h.p_total)}</td><td>{h.conditions.map(([c, ok, why]) => <div key={c}>{ok ? "✓" : "✗"} {why}</div>)}</td></tr>)}</tbody></table></div>
    <div className="note">A graph connection alone never implies the attacker can use it: each hop needs its access conditions. Probabilities are assumptions.</div></>);
}

function Risk({ sc, topo }) {
  const risk = sc.risk, mx = Math.max(...risk.map((r) => r.risk));
  const fills = Object.fromEntries(risk.map((r) => { const t = r.risk / mx; const stops = ["#FFFFCC", "#FED976", "#FD8D3C", "#E31A1C", "#800026"]; return [r.component_id, stops[Math.min(4, Math.floor(t * 4.999))]]; }));
  const extra = Object.fromEntries(risk.map((r) => [r.component_id, `risk ${f2(r.risk)} (likelihood ${f2(r.likelihood)} × consequence ${f2(r.consequence)})`]));
  const none = strat(sc, "no_isolation");
  return (<>
    <div className="grid g4"><Kpi l="Highest-risk component" v={risk[0].component_id} s={`${risk[0].name} · risk ${f2(risk[0].risk)}`} c="#EF4444" /><Kpi l="Weighted blast radius" v={pct(none.blast_weighted)} s="importance share compromised / failed / degraded" c="#FBBF24" /><Kpi l="Single points of failure" v={sc.spof.length} s={sc.spof.join(", ")} c="#E879F9" /><Kpi l="Most exposed zone" v={[...sc.zone_risk].sort((a, b) => b.mean_risk - a.mean_risk)[0].zone.toUpperCase()} s="highest mean component risk" /></div>
    <div style={{ marginTop: 14 }}><Graph topo={topo} fills={fills} extra={extra} layers={new Set(["network", "auth", "control", "physical_flow"])} colorbar={{ stops: ["#800026", "#E31A1C", "#FD8D3C", "#FED976", "#FFFFCC"], title: "risk", max: f2(mx) }} /></div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div className="card"><h3>Component risk ranking</h3><div className="scroll"><table><thead><tr><th>#</th><th>component</th><th>risk</th><th>likelihood</th><th>consequence</th><th>sim freq</th><th>evidence</th><th>exposure</th></tr></thead><tbody>
        {risk.map((r) => <tr key={r.component_id}><td>{r.rank}</td><td>{r.component_id} · {r.name}</td><td><span className="barbg"><span className="bar" style={{ width: `${(100 * r.risk) / mx}%` }} /></span> {f2(r.risk)}</td><td>{f2(r.likelihood)}</td><td>{f2(r.consequence)}</td><td>{f2(r.sim_frequency)}</td><td>{f2(r.evidence)}</td><td>{f2(r.exposure)}</td></tr>)}</tbody></table></div></div>
      <div className="card"><h3>Zone risk</h3><GroupedBars groups={sc.zone_risk.map((z) => z.zone)} series={[{ name: "mean risk", color: "#22D3EE" }, { name: "max risk", color: "#EF4444" }]} values={[sc.zone_risk.map((z) => z.mean_risk), sc.zone_risk.map((z) => z.max_risk)]} />
        <div className="muted small">cyan = mean, red = max</div>
        <h3 style={{ marginTop: 14 }}>Formula</h3><pre className="small muted" style={{ whiteSpace: "pre-wrap" }}>{"S = max(anomaly score, classifier evidence)\nL = 0.45·P_sim + 0.35·S + 0.20·exposure\nC = 0.6·importance + 0.4·downstream share\nR = L × C   (ranking aid, not a probability)"}</pre></div>
    </div></>);
}

function Contain({ sc, topo }) {
  const rec = strat(sc, "impactgraph_greedy"), maxT = 99;
  const fb = replayState(sc.replay.before.nodes, maxT, true), fa = replayState(sc.replay.after.nodes, maxT, true);
  const hb = new Set(sc.replay.before.edges.map((e) => e.edge_id)), ha = new Set(sc.replay.after.edges.map((e) => e.edge_id));
  const bins = Array.from({ length: 10 }, (_, i) => `${i * 10}-${(i + 1) * 10}%`);
  return (<>
    <div className="advice">ADVISORY ONLY. These are simulated recommendations for human decision-makers. ImpactGraph never executes isolation, shutdown or valve commands on any real system.</div>
    <div className="grid g5" style={{ marginTop: 12 }}><Kpi l="Actions recommended" v={rec.n_isolated} s={rec.isolated.join(", ") || "none worthwhile"} c="#E879F9" /><Kpi l="Isolation cost" v={f2(rec.cost, 1)} s="relative units (assumed)" c="#FBBF24" /><Kpi l="Impact reduction" v={pct(1 - rec.impact / Math.max(strat(sc, "no_isolation").impact, 1e-9))} s={`${f2(strat(sc, "no_isolation").impact, 3)} → ${f2(rec.impact, 3)}`} c="#34D399" /><Kpi l="Throughput kept" v={pct(rec.throughput)} s={`was ${pct(strat(sc, "no_isolation").throughput)}`} /><Kpi l="Constraints violated" v={rec.constraints_violated} s="C1 safety · C2 continuity · C3 action cap" c="#34D399" /></div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div><div className="card"><h3>Same incident, before and after (identical random draws)</h3>
        <div className="grid g2"><div><b className="small bad">No isolation</b><Graph topo={topo} fills={fb} highlight={hb} labels="id" /></div><div><b className="small ok">ImpactGraph isolation</b><Graph topo={topo} fills={fa} highlight={ha} isolated={new Set(rec.isolated)} labels="id" /></div></div><GraphLegend /></div></div>
      <div><div className="card"><h3>Why each action is recommended</h3>{sc.recommendations.length ? sc.recommendations.map((r) => <div className="step" key={r.step}><b>Step {r.step}</b> · ΔJ −{f2(r.delta_j, 3)}<br />{r.explanation}</div>) : <div className="step">No single isolation lowers the objective enough to justify its cost and the dependencies it sacrifices. Doing nothing is the recommendation.</div>}
        <p className="small muted"><b>Hard constraints:</b> C1 no logical isolation into a safety-critical component · C2 attack-free throughput ≥ 60% · C3 at most 6 actions.</p></div></div>
    </div>
    <div className="grid g2">
      <div className="card"><h3>Strategies compared</h3><table><thead><tr><th>strategy</th><th>impact</th><th>throughput</th><th>hazard</th><th>cuts</th><th>objective J</th></tr></thead><tbody>{STRATEGY_ORDER.map((k) => { const s = strat(sc, k); return <tr key={k}><td><i className="dot" style={{ background: STRATEGY_COLOR[k], borderColor: STRATEGY_COLOR[k] }} /> {STRATEGY_LABEL[k]}</td><td>{f2(s.impact, 3)}</td><td>{pct(s.throughput)}</td><td>{f2(s.hazard, 3)}</td><td>{s.isolated.join(", ") || "-"}</td><td>{f2(s.objective, 3)}</td></tr>; })}</tbody></table></div>
      <div className="card"><h3>Distribution of delivered throughput across trials</h3><GroupedBars groups={bins} series={STRATEGY_ORDER.map((k) => ({ name: STRATEGY_LABEL[k], color: STRATEGY_COLOR[k] }))} values={STRATEGY_ORDER.map((k) => { const h = strat(sc, k).throughput_hist, t = h.reduce((a, b) => a + b, 0); return h.map((v) => (100 * v) / t); })} fmt={(v) => v.toFixed(0)} yTitle="% of trials" height={280} /></div>
    </div>
    <div className="grid g2">
      <div className="card"><h3>Sensitivity of the recommendation to λ</h3><table><thead><tr><th>λ</th><th>cuts chosen</th><th>count</th><th>cost</th></tr></thead><tbody>{sc.sensitivity.map((s) => <tr key={s.lambda}><td>{s.lambda}</td><td>{s.isolated.join(", ") || "none"}</td><td>{s.n}</td><td>{f2(s.cost, 1)}</td></tr>)}</tbody></table></div>
      <div className="card"><h3>Robustness: ±30% perturbed attack probabilities (15 models)</h3><table><thead><tr><th>strategy</th><th>mean J</th><th>90th pct J</th><th>win rate vs none</th></tr></thead><tbody>{STRATEGY_ORDER.map((k) => { const r = sc.robustness[k]; return <tr key={k}><td>{STRATEGY_LABEL[k]}</td><td>{f2(r.mean_j, 3)}</td><td>{f2(r.p90_j, 3)}</td><td>{pct(r.win_rate_vs_no_isolation)}</td></tr>; })}</tbody></table></div>
    </div></>);
}

function Evaluation({ data, sc }) {
  const det = data.global.detection, clf = data.global.classifier, p = det.without_residual.node_step, a = det.with_residual.node_step, ct = clf.test, b = ct.binary, pm = sc.propagation_metrics;
  return (<>
    <h2>Detection (Isolation Forest, {det.n_episodes} held-out episodes)</h2>
    <div className="grid g5"><Kpi l="Precision" v={f2(p.precision, 3)} s={`${p.tp} TP · ${p.fp} FP`} c="#34D399" /><Kpi l="Recall" v={f2(p.recall, 3)} s={`${p.fn} missed anomalous minutes`} /><Kpi l="F1" v={f2(p.f1, 3)} s={`${p.samples.toLocaleString()} node-minutes`} /><Kpi l="False-positive rate" v={f2(p.fpr, 4)} s={`${p.tn.toLocaleString()} true negatives`} c="#FBBF24" /><Kpi l="False-negative rate" v={f2(p.fnr, 3)} s="node-minute level" c="#EF4444" /></div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div className="card"><h3>Event-level detection</h3><table><thead><tr><th>type</th><th>events</th><th>detected</th><th>median delay (min)</th></tr></thead><tbody>{det.without_residual.event_by_type.map((r) => <tr key={r.type}><td>{r.type}</td><td>{r.events}</td><td>{pct(r.detected)}</td><td>{r.median_delay}</td></tr>)}</tbody></table></div>
      <div className="card"><h3>Ablation: add physics-consistency (mass-balance) feature</h3><table><thead><tr><th>variant</th><th>precision</th><th>recall</th><th>F1</th><th>FPR</th></tr></thead><tbody><tr><td>primary</td><td>{f2(p.precision, 3)}</td><td>{f2(p.recall, 3)}</td><td>{f2(p.f1, 3)}</td><td>{f2(p.fpr, 4)}</td></tr><tr><td>+ residual</td><td>{f2(a.precision, 3)}</td><td>{f2(a.recall, 3)}</td><td>{f2(a.f1, 3)}</td><td>{f2(a.fpr, 4)}</td></tr></tbody></table>
        <div className="note">Honest finding: the residual feature did NOT improve detection, so the simpler detector is primary. That choice was made after seeing the ablation, so primary figures are slightly optimistic.</div></div>
    </div>
    <h2>Network attack classifier (UNSW-NB15, Random Forest)</h2>
    <div className="grid g5"><Kpi l="Accuracy" v={f2(ct.accuracy, 3)} s="10-class test set" /><Kpi l="Macro-F1" v={f2(ct.macro_f1, 3)} s="equal weight per class" /><Kpi l="Attack recall" v={f2(b.recall, 3)} s={`FNR ${f2(b.fnr, 3)}`} c="#34D399" /><Kpi l="False-positive rate" v={f2(b.fpr, 3)} s="benign flagged as attack" c="#EF4444" /><Kpi l="Precision" v={f2(b.precision, 3)} s="attack vs normal" c="#FBBF24" /></div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div className="card"><h3>Confusion matrix (row-normalised, counts shown)</h3><Matrix cm={ct.confusion_matrix} labels={ct.classes} /></div>
      <div className="card"><h3>Per-class results</h3><div className="scroll"><table><thead><tr><th>class</th><th>precision</th><th>recall</th><th>F1</th><th>support</th></tr></thead><tbody>{Object.entries(ct.per_class).map(([k, v]) => <tr key={k}><td>{k}</td><td>{f2(v.precision, 3)}</td><td>{f2(v.recall, 3)}</td><td>{f2(v.f1, 3)}</td><td>{v.support}</td></tr>)}</tbody></table></div>
        <p className="muted small">{clf.dataset}. UNSW-NB15 is lab traffic, not Colonial Pipeline traffic.</p></div>
    </div>
    <h2>Propagation stability and performance ({sc.id})</h2>
    <div className="grid g4"><Kpi l="Node F1 vs hold-out" v={f2(pm.pred_node_f1, 3)} s={`precision ${f2(pm.pred_node_precision, 2)} · recall ${f2(pm.pred_node_recall, 2)}`} /><Kpi l="Frequency MAE" v={f2(pm.frequency_mae_vs_reference, 3)} s="500 vs 2000 independent trials" c="#34D399" /><Kpi l="Impact estimate error" v={pct(pm.weighted_impact_error_rel, 1)} s="relative to reference" c="#FBBF24" /><Kpi l="Monte Carlo speed" v={`${Math.round(sc.performance.mc_trials_per_second)}/s`} s="trials per second (1 CPU)" c="#E879F9" /></div>
    <div className="note">'Prediction' here is the set of components with simulated hit frequency ≥ 0.5, compared with an independent, larger simulation of the same model. It measures simulation stability, not accuracy against real incidents.</div>
    <div className="card"><h3>Limitations</h3><ul className="tight"><li>Telemetry is synthetic; ranges and anomaly shapes are assumptions.</li><li>All attack probabilities, importance values, costs and objective weights are assumed, not calibrated.</li><li>Mode A reproduces only the documented IT-side incident; the OT-foothold probability is an uncertainty assumption.</li><li>The classifier uses lab traffic; the bridge from dataset flows to graph components is an assumption.</li><li>Steady-state flow only; no recovery dynamics; the optimiser is greedy.</li></ul></div></>);
}

function About({ data }) {
  return (<div className="grid g2"><div>
    <div className="card"><h3>What this is</h3><p>ImpactGraph models a pipeline operator as a typed graph of vendors, corporate IT, control systems (OT) and physical assets. It detects unusual behaviour, simulates how an attack or failure could spread, scores risk and blast radius, and recommends which few links to cut so safe parts keep running.</p><p className="muted">This web viewer shows pre-computed Phase 1 results. The live simulator (Python/Streamlit) can run new scenarios, seeds and trial counts.</p></div>
    <div className="card"><h3>Honesty rules</h3><ul className="tight"><li>Mode A reproduces only the documented IT-side Colonial facts; everything touching OT or physical assets is hypothetical.</li><li>Telemetry is synthetic and probabilities are assumed.</li><li>Recommendations are advisory; nothing is ever executed on real systems.</li></ul></div></div>
    <div className="card"><h3>Project</h3><p className="small">{Object.keys(data.scenarios).length} scenarios · {data.topology.nodes.length} components · {data.topology.edges.length} typed relationships.</p>{REPO_URL && <p><a href={REPO_URL} target="_blank" rel="noreferrer">Source code on GitHub →</a></p>}<p className="muted small">SDG 9 · Industry, Innovation and Infrastructure.</p></div></div>);
}
