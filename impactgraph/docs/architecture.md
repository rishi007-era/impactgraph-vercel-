# ImpactGraph architecture (Phase 1)

## Layers and data flow
```
config/settings.py  (all weights, lambda, thresholds: documented assumptions)
        |
infrastructure/  typed directed graph (24 nodes, 48 edges, 6 relationship types) + validator
        |                         \
ingestion/  synthetic telemetry     \__ dataset_loader (UNSW-NB15, leakage-safe split)
        |                                   |
detection/  Isolation Forest per component  traffic_classifier (Random Forest) + FlowBridge
        |  (calibrated scores, alerts, explanations)        |  (calibrated evidence N_i)
        +---------------------------+------------------------+
                                    |
attack_analysis/  access rules, stochastic attack model, weighted path analysis
simulation/       scenarios, propagation (service levels + max-flow), Monte Carlo (common random numbers)
risk/             risk score, downstream consequence, single points of failure, centrality (supplementary)
optimization/     strategies, objective J(S), constraints, greedy search, robustness test
resilience/       throughput, availability, operational connectivity
database/         SQLite repository (configs, scenarios, telemetry, alerts, paths, propagation, risk, isolation, metrics)
experiments/      runner (one reproducible pipeline), reports (RESULTS.md)
dashboard/        Streamlit app: only displays stored backend results
```

## One scenario run (experiments/runner.py)
1. Baseline Monte Carlo (no isolation), keep a representative trajectory.
2. Generate telemetry from that trajectory (ground-truth labels), score with Isolation Forest, raise alerts, get classifier evidence.
3. Risk table from simulated frequency, detection evidence, exposure, importance and downstream consequence.
4. Attack-path analysis (top routes, hop-level feasibility).
5. Containment: greedy search plus three baselines, evaluated on fresh random draws.
6. Before/after replay on the SAME trial (common random numbers).
7. Validation: independent 2000-trial hold-out, +/-30% probability robustness, lambda sensitivity.
8. Persist everything with seed, weights and versions.

## Mathematical models (all weights are assumptions)
- **Attack transition:** edge u->v may be attempted when u is compromised and all access conditions hold. Success within K attempts: p_total = 1-(1-p)^K; the attempt index gives the hop delay. A CONTROL edge into a physical asset models unsafe actuation. Isolation blocks transitions that would complete after the response time tau.
- **Service level:** s_i = 0 if failed, else prod over dependencies (1 - w_e (1 - s_source)). A dependency whose link is isolated counts as severed.
- **Throughput:** max-flow from the source pump station to the delivery point with node capacity = capacity * s_i (node splitting). Valve closures are reactive.
- **Release hazard:** flow that can still reach a ruptured asset / baseline throughput.
- **Impact:** 0.40 (1 - throughput) + 0.20 service loss + 0.25 hazard + 0.15 compromise exposure.
- **Objective:** J(S) = E[impact | S] + lambda * sum cost(S) / C_ref, with constraints C1 (no logical isolation into safety-critical targets), C2 (attack-free throughput >= 60%), C3 (<= 6 actions).
- **Risk:** R_i = L_i * C_i with L_i = 0.45 P_i + 0.35 max(A_i, N_i) + 0.20 X_i and C_i = 0.6 importance_i + 0.4 D_i.

## Evaluation plan
Detection: node-minute precision/recall/F1/FPR/FNR, event-level detection and delay, ablation, on 36 held-out episodes (different seeds from training and validation).
Classifier: accuracy, macro-F1, per-class metrics, confusion matrix, binary FPR/FNR on a held-out 20% split after de-duplication.
Propagation: node precision/recall/F1, frequency MAE and impact error against an independent 2000-trial run.
Containment: impact, throughput, hazard, cost, constraint violations for four strategies on identical trials.
Robustness: fixed strategies under 15 perturbed models. Performance: trials per second, runtime, peak memory.

## Phase 2 extension points (same architecture)
80-node configurable model; 8 scenarios; 5,000 trials; recovery dynamics; sensor-deception detection; exhaustive and constrained optimisation; scenario editor; PostgreSQL; experiment comparison; PDF reports.
