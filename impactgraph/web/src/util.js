export const ZONE_COLOR = { vendor: "#A78BFA", it: "#38BDF8", ot: "#F59E0B", physical: "#34D399" };
export const ZONE_LABEL = { vendor: "ZONE 1 - VENDOR / EXTERNAL ACCESS", it: "ZONE 2 - ENTERPRISE IT", ot: "ZONE 3 - OPERATIONAL TECHNOLOGY", physical: "ZONE 4 - PHYSICAL PIPELINE INFRASTRUCTURE" };
export const COND_COLOR = { normal: "#1B2740", degraded: "#FBBF24", compromised: "#F97316", failed: "#EF4444", isolated: "#94A3B8" };
export const EDGE_COLOR = { network: "#38BDF8", auth: "#A78BFA", control: "#F59E0B", physical_flow: "#2DD4BF", operational_dep: "#7C8DA8", service_dep: "#7C8DA8" };
export const EDGE_LABEL = { network: "Network", auth: "Authentication", control: "Control / actuation", physical_flow: "Physical product flow", operational_dep: "Operational dependency", service_dep: "Service dependency" };
export const STRATEGY_COLOR = { no_isolation: "#EF4444", initial_component: "#F59E0B", full_shutdown: "#94A3B8", impactgraph_greedy: "#34D399" };
export const STRATEGY_LABEL = { no_isolation: "No isolation", initial_component: "Isolate initial component", full_shutdown: "Full precautionary shutdown", impactgraph_greedy: "ImpactGraph recommendation" };
export const STRATEGY_ORDER = ["no_isolation", "initial_component", "full_shutdown", "impactgraph_greedy"];
export const MODE = { A: ["MODE A · HISTORICAL RECONSTRUCTION (IT SIDE)", "#FBBF24"], B: ["MODE B · HYPOTHETICAL CYBER-PHYSICAL", "#EF4444"], P: ["MODE P · PHYSICAL SABOTAGE (HYPOTHETICAL)", "#E879F9"] };
export const pct = (x, d = 0) => (100 * x).toFixed(d) + "%";
export const f2 = (x, d = 2) => (x == null ? "-" : Number(x).toFixed(d));
export function replayState(nodes, step, final) {
  const out = {};
  for (const r of nodes) {
    let c = "normal";
    if (r.t_failed != null && r.t_failed <= step) c = "failed";
    else if (r.t_compromised != null && r.t_compromised <= step) c = "compromised";
    else if (final && ["degraded", "failed", "compromised"].includes(r.condition)) c = r.condition;
    out[r.component_id] = c;
  }
  return out;
}
export function replayMax(nodes) {
  const v = nodes.flatMap((r) => [r.t_compromised, r.t_failed]).filter((x) => x != null);
  return v.length ? Math.max(...v) : 0;
}
