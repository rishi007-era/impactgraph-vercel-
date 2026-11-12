"""Monte Carlo driver: attack/failure outcomes per trial -> consequences -> aggregated frequencies.

Results are SIMULATION FREQUENCIES under assumed transition probabilities. They are not calibrated
real-world probabilities. Common random numbers are used so strategies are compared on identical trials.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from ..attack_analysis.attack_model import AttackModel
from ..config import settings
from ..infrastructure.enums import Condition, Zone
from ..infrastructure.graph_builder import InfrastructureGraph
from .propagation import PropagationModel
from .scenarios import Scenario


def wilson_interval(k: float, n: int, z: float = 1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


@dataclass
class MCResult:
    scenario_id: str
    trials: int
    seed: int
    isolated: tuple
    shutdown: bool
    freq_compromised: dict
    freq_failed: dict
    freq_degraded: dict
    freq_affected: dict
    ci_affected: dict
    mean_time_compromise: dict
    impact: np.ndarray
    throughput: np.ndarray
    hazard: np.ndarray
    service_loss: np.ndarray
    blast_weighted: np.ndarray
    n_affected: np.ndarray
    foothold_rate: float
    runtime_s: float
    phys_hit: np.ndarray = None
    exposure: np.ndarray = None
    rep_trial: int = -1
    rep_trace: object = None
    extras: dict = field(default_factory=dict)

    def mean(self, name: str) -> float:
        return float(getattr(self, name).mean())

    def ci(self, name: str):
        a = getattr(self, name)
        h = 1.96 * a.std(ddof=1) / math.sqrt(len(a)) if len(a) > 1 else 0.0
        return float(a.mean() - h), float(a.mean() + h)


class MonteCarloEngine:
    def __init__(self, ig: InfrastructureGraph, scenario: Scenario, trials: int, seed: int,
                 model: PropagationModel = None):
        self.ig, self.sc, self.trials, self.seed = ig, scenario, trials, seed
        self.model = model or PropagationModel(ig)
        self.attack = AttackModel(ig, scenario)
        rng = np.random.default_rng(seed)
        self.u_edge = rng.random((trials, max(1, self.attack.n_attack_edges())))
        self.u_ransom = rng.random((trials, len(ig.nodes)))
        self.u_phys = rng.random((trials, max(1, len(self.attack.phys_entries))))
        self.u_foot = rng.random(trials)
        self.ids = [n.id for n in ig.nodes]
        self.phys_ids = frozenset(self.model.phys_ids)

    def _trial(self, i, isolated, tau, prob_scale, shutdown):
        out = self.attack.run_trial(self.u_edge[i], self.u_ransom[i], self.u_phys[i], self.u_foot[i],
                                    isolated=isolated, tau=tau, prob_scale=prob_scale)
        failed = set(out.failed.keys())
        if shutdown:
            failed |= self.phys_ids
        sev = self.model.severed_dependencies(isolated)
        # valve closures are a REACTIVE response: they are applied only when a product release occurs
        closed = self.model.closed_flow_edges(isolated) if out.release else frozenset()
        cons = self.model.evaluate(frozenset(failed), sev, closed, out.release)
        cond = self.model.conditions(cons.services, set(out.compromised.keys()))
        if shutdown:   # physical-failure flag reflects the ATTACK outcome, not the deliberate shutdown
            cons_a = self.model.evaluate(frozenset(out.failed.keys()), sev, closed, out.release)
            cond_a = self.model.conditions(cons_a.services, set(out.compromised.keys()))
        else:
            cond_a = cond
        phys_flag = any(cond_a[p] == Condition.FAILED for p in self.phys_ids)
        return out, cons, cond, phys_flag

    def trace_for_trial(self, i, isolated=frozenset(), tau=None, prob_scale=None, shutdown=False) -> dict:
        out, cons, cond, _ = self._trial(i, frozenset(isolated), tau, prob_scale, shutdown)
        return {"compromised": dict(out.compromised), "failed": dict(out.failed), "release": set(out.release),
                "services": dict(cons.services), "conditions": cond,
                "used_edges": list(out.used_edges), "foothold": out.foothold}

    def run(self, isolated=frozenset(), shutdown=False, prob_scale=None, tau=None, keep_trace=False,
            collect_sets=False) -> MCResult:
        t0 = time.perf_counter()
        isolated = frozenset(isolated)
        n = self.trials
        comp = {i: 0 for i in self.ids}
        fail = {i: 0 for i in self.ids}
        degr = {i: 0 for i in self.ids}
        aff = {i: 0 for i in self.ids}
        tsum = {i: 0.0 for i in self.ids}
        impact = np.zeros(n); thr = np.zeros(n); haz = np.zeros(n); sl = np.zeros(n)
        blast = np.zeros(n); naff = np.zeros(n); foot = 0; phys_hit = np.zeros(n); expo = np.zeros(n)
        sets = []
        for i in range(n):
            out, cons, cond, pflag = self._trial(i, isolated, tau, prob_scale, shutdown)
            affected = []
            for nid, c in cond.items():
                if c != Condition.NORMAL:
                    aff[nid] += 1
                    affected.append(nid)
                if c == Condition.FAILED:
                    fail[nid] += 1
                elif c == Condition.COMPROMISED:
                    comp[nid] += 1
                elif c == Condition.DEGRADED:
                    degr[nid] += 1
            for nid, t in out.compromised.items():
                tsum[nid] += t
            expo[i] = sum(self.model.importance[x] for x in out.compromised) / self.model.total_importance
            impact[i] = cons.impact + settings.IMPACT_WEIGHTS["exposure"] * expo[i]
            thr[i], haz[i], sl[i] = cons.throughput_fraction, cons.hazard, cons.service_loss
            blast[i] = self.model.blast_radius_weighted(affected)
            naff[i] = len(affected)
            if collect_sets:
                sets.append(frozenset(affected))
            phys_hit[i] = 1.0 if pflag else 0.0
            foot += int(out.foothold)
        res = MCResult(
            scenario_id=self.sc.id, trials=n, seed=self.seed, isolated=tuple(sorted(isolated)), shutdown=shutdown,
            freq_compromised={k: v / n for k, v in comp.items()},
            freq_failed={k: v / n for k, v in fail.items()},
            freq_degraded={k: v / n for k, v in degr.items()},
            freq_affected={k: v / n for k, v in aff.items()},
            ci_affected={k: wilson_interval(v, n) for k, v in aff.items()},
            mean_time_compromise={k: (tsum[k] / comp_or_fail) if (comp_or_fail := max(1, aff[k])) else 0.0 for k in self.ids},
            impact=impact, throughput=thr, hazard=haz, service_loss=sl, blast_weighted=blast, n_affected=naff,
            foothold_rate=foot / n, runtime_s=0.0, phys_hit=phys_hit, exposure=expo)
        res.extras['sets'] = sets
        if keep_trace:
            nz = np.where(naff >= np.median(naff))[0]
            if len(nz) == 0:
                nz = np.arange(n)
            rep = int(nz[np.argmin(np.abs(impact[nz] - impact.mean()))])
            res.rep_trial = rep
            res.rep_trace = self.trace_for_trial(rep, isolated, tau, prob_scale, shutdown)
        res.runtime_s = time.perf_counter() - t0
        return res
