"""Component-level risk assessment (transparent, assumption-based, NOT calibrated).

All inputs are normalised to [0,1] before combination:

    S_i  detection evidence = max(A_i, N_i)
           A_i  Isolation-Forest anomaly score, percentile-calibrated on normal validation data
           N_i  traffic-classifier evidence, calibrated against benign traffic (0 = benign-like)
    P_i  simulated frequency that component i is compromised, failed or degraded (Monte Carlo, NOT a real probability)
    X_i  exposure attribute of the component (assumed)

    Likelihood  L_i = w_sim * P_i + w_evd * S_i + w_exp * X_i          (weights sum to 1)
    Consequence C_i = w_imp * importance_i + w_dwn * D_i               (D_i = downstream importance share)
    Risk        R_i = L_i * C_i                                        in [0,1]

Weights live in config/settings.py. Scores are rankings for decision support; they are not probabilities
of loss and are not validated against real incidents.
"""
from __future__ import annotations

import pandas as pd

from ..config import settings
from ..infrastructure.graph_builder import InfrastructureGraph
from .criticality import betweenness, downstream_share


def risk_table(ig: InfrastructureGraph, freq_affected: dict, anomaly: dict, classifier: dict) -> pd.DataFrame:
    wl, wc = settings.RISK_LIKELIHOOD_WEIGHTS, settings.RISK_CONSEQUENCE_WEIGHTS
    D, B = downstream_share(ig), betweenness(ig)
    rows = []
    for n in ig.nodes:
        P = freq_affected.get(n.id, 0.0)
        A, N = anomaly.get(n.id, 0.0), classifier.get(n.id, 0.0)
        S = max(A, N)
        L = wl["simulation"] * P + wl["evidence"] * S + wl["exposure"] * n.exposure
        C = wc["importance"] * n.operational_importance + wc["downstream"] * D[n.id]
        rows.append({
            "component_id": n.id, "name": n.name, "zone": n.zone.value, "criticality": n.criticality.value,
            "sim_frequency": P, "anomaly_score": A, "classifier_evidence": N, "evidence": S,
            "exposure": n.exposure, "likelihood": L, "importance": n.operational_importance,
            "downstream_share": D[n.id], "consequence": C, "risk": L * C, "betweenness": B.get(n.id, 0.0)})
    df = pd.DataFrame(rows).sort_values("risk", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def zone_risk(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("zone").agg(mean_risk=("risk", "mean"), max_risk=("risk", "max"), components=("risk", "size"))
    return g.reset_index()
