"""Containment strategies and the transparent objective used to compare them.

Objective (documented, assumption-based weights in config/settings.py):

    J(S) = E[ residual impact | isolate S ] + LAMBDA * sum_{e in S} cost(e) / COST_REF

    residual impact = w_t (1 - throughput) + w_s (importance-weighted service loss) + w_h (release hazard)

Hard constraints on every recommendation:
  C1  no LOGICAL isolation of a link whose target is safety-critical;
  C2  attack-free throughput with the isolations applied must stay >= MIN_CONTINUITY;
  C3  at most MAX_ISOLATIONS actions.
Recommendations are ADVISORY. Nothing here executes against any real system.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..config import settings
from ..infrastructure.enums import IsolationKind
from ..infrastructure.graph_builder import InfrastructureGraph
from ..simulation.monte_carlo import MCResult, MonteCarloEngine
from ..simulation.propagation import PropagationModel
from ..simulation.scenarios import Scenario

NO_ISOLATION = "no_isolation"
INITIAL_COMPONENT = "initial_component"
FULL_SHUTDOWN = "full_shutdown"
IMPACTGRAPH = "impactgraph_greedy"

LABELS = {
    NO_ISOLATION: "No isolation",
    INITIAL_COMPONENT: "Isolate initial component",
    FULL_SHUTDOWN: "Full precautionary shutdown",
    IMPACTGRAPH: "ImpactGraph recommendation",
}


@dataclass
class Strategy:
    key: str
    isolated: tuple = ()
    shutdown: bool = False
    steps: list = field(default_factory=list)   # explanation per greedy step

    @property
    def label(self) -> str:
        return LABELS[self.key]


def isolation_cost(ig: InfrastructureGraph, edges) -> float:
    return float(sum(ig.edge(e).isolation_cost for e in edges))


def objective(ig, res: MCResult, isolated, shutdown=False) -> float:
    cost = isolation_cost(ig, isolated) + (settings.COST_REF if shutdown else 0.0)
    return res.mean("impact") + settings.LAMBDA * cost / settings.COST_REF


def violates_constraints(ig, model: PropagationModel, isolated) -> list:
    v = []
    for eid in isolated:
        e = ig.edge(eid)
        if e.isolation_kind == IsolationKind.LOGICAL and ig.node(e.target).safety_critical:
            v.append(f"C1: {eid} isolates a link into safety-critical {e.target}")
    if model.continuity_without_attack(isolated) < settings.MIN_CONTINUITY:
        v.append("C2: attack-free throughput below minimum continuity")
    if len(isolated) > settings.MAX_ISOLATIONS:
        v.append("C3: too many isolation actions")
    return v


def candidate_edges(ig: InfrastructureGraph) -> list:
    out = []
    for e in ig.edges:
        if not e.isolatable:
            continue
        if e.isolation_kind == IsolationKind.LOGICAL and ig.node(e.target).safety_critical:
            continue
        out.append(e.id)
    return out


def initial_component_edges(ig: InfrastructureGraph, scenario: Scenario) -> tuple:
    seed = scenario.alert_seed_node
    return tuple(sorted(e.id for e in ig.edges
                        if e.isolatable and e.isolation_kind == IsolationKind.LOGICAL
                        and seed in (e.source, e.target)))


def explain_step(ig, model, eid, d_impact, d_phys, cost) -> str:
    e = ig.edge(eid)
    s, t = ig.node(e.source), ig.node(e.target)
    sev = [d for d in model.dep_in[e.target] if d.source == e.source]
    price = ""
    if sev:
        price = "; sacrifices dependency: " + ", ".join(
            f"{ig.node(d.target).name} loses up to {d.dependency_strength:.0%} service" for d in sev)
    kind = "closing the valve" if e.isolation_kind == IsolationKind.PHYSICAL else "cutting the link"
    return (f"{eid}: {kind} {s.name} -> {t.name} ({e.edge_type.value}) reduces expected impact by "
            f"{d_impact:.3f} and the chance of a physical failure by {100 * d_phys:.1f} percentage points "
            f"(isolation cost {cost:.1f}){price}.")


def greedy_isolation(ig: InfrastructureGraph, scenario: Scenario, model: PropagationModel, seed: int,
                     trials: int = settings.SEARCH_TRIALS) -> Strategy:
    engine = MonteCarloEngine(ig, scenario, trials, seed, model=model)
    chosen: list = []
    base = engine.run()
    cur_j, cur_imp, cur_phys = objective(ig, base, ()), base.mean("impact"), base.mean("phys_hit")
    steps: list = []
    cands = candidate_edges(ig)
    while len(chosen) < settings.MAX_ISOLATIONS:
        best = None
        for eid in cands:
            if eid in chosen:
                continue
            trial_set = tuple(sorted(chosen + [eid]))
            if violates_constraints(ig, model, trial_set):
                continue
            r = engine.run(isolated=trial_set)
            j = objective(ig, r, trial_set)
            if best is None or j < best[0]:
                best = (j, eid, r)
        if best is None or best[0] >= cur_j - 1e-3:
            break
        j, eid, r = best
        chosen.append(eid)
        steps.append({
            "edge": eid, "delta_j": cur_j - j, "delta_impact": cur_imp - r.mean("impact"),
            "delta_phys": cur_phys - r.mean("phys_hit"), "j_after": j,
            "text": explain_step(ig, model, eid, cur_imp - r.mean("impact"), cur_phys - r.mean("phys_hit"),
                                 ig.edge(eid).isolation_cost)})
        cur_j, cur_imp, cur_phys = j, r.mean("impact"), r.mean("phys_hit")
    return Strategy(IMPACTGRAPH, tuple(sorted(chosen)), False, steps)


@dataclass
class StrategyEvaluation:
    key: str
    label: str
    isolated: tuple
    n_isolated: int
    cost: float
    impact: float
    impact_ci: tuple
    throughput: float
    hazard: float
    service_loss: float
    blast_weighted: float
    phys_hit: float
    objective: float
    constraints_violated: int
    continuity: float
    runtime_s: float


def evaluate_strategy(ig, model, scenario, strat: Strategy, eval_engine: MonteCarloEngine) -> StrategyEvaluation:
    res = eval_engine.run(isolated=strat.isolated, shutdown=strat.shutdown)
    viol = len(violates_constraints(ig, model, strat.isolated))
    return StrategyEvaluation(
        key=strat.key, label=strat.label, isolated=strat.isolated, n_isolated=len(strat.isolated),
        cost=isolation_cost(ig, strat.isolated) + (settings.COST_REF if strat.shutdown else 0.0),
        impact=res.mean("impact"), impact_ci=res.ci("impact"), throughput=res.mean("throughput"),
        hazard=res.mean("hazard"), service_loss=res.mean("service_loss"), blast_weighted=res.mean("blast_weighted"),
        phys_hit=res.mean("phys_hit"), objective=objective(ig, res, strat.isolated, strat.shutdown),
        constraints_violated=viol, continuity=0.0 if strat.shutdown else model.continuity_without_attack(strat.isolated),
        runtime_s=res.runtime_s), res


def robustness_test(ig, model, scenario, strategies, n_models=15, trials=200, seed=777, spread=0.30):
    """Re-evaluate FIXED strategies under perturbed traversal probabilities (x U(1-spread, 1+spread))."""
    rng = np.random.default_rng(seed)
    attack_edges = [e.id for e in ig.edges if e.is_attack_traversable]
    rows = {s.key: [] for s in strategies}
    for m in range(n_models):
        scale = {eid: float(rng.uniform(1 - spread, 1 + spread)) for eid in attack_edges}
        eng = MonteCarloEngine(ig, scenario, trials, seed + 1 + m, model=model)
        for s in strategies:
            r = eng.run(isolated=s.isolated, shutdown=s.shutdown, prob_scale=scale)
            rows[s.key].append(objective(ig, r, s.isolated, s.shutdown))
    out = {}
    for k, v in rows.items():
        a = np.array(v)
        out[k] = {"mean_j": float(a.mean()), "p90_j": float(np.quantile(a, 0.9)), "worst_j": float(a.max()),
                  "std_j": float(a.std())}
    base = np.array(rows[NO_ISOLATION])
    for s in strategies:
        out[s.key]["win_rate_vs_no_isolation"] = float((np.array(rows[s.key]) <= base + 1e-9).mean())
    return out
