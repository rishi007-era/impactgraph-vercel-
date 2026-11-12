# ImpactGraph Phase 1: experiment results

All numbers below were produced by executing `python -m impactgraph.experiments.runner` and read from the SQLite database.
Simulation outputs are frequencies under ASSUMED transition probabilities, not calibrated real-world probabilities. Telemetry is synthetic. UNSW-NB15 is lab traffic, not Colonial Pipeline traffic.

## Detection (Isolation Forest, held-out episodes)
36 test episodes, 207360 node-steps.

| variant | precision | recall | f1 | FPR | FNR | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|---|
| Primary (raw telemetry) | 0.997 | 0.907 | 0.950 | 0.000 | 0.093 | 25550 | 67 | 179121 | 2622 |
| Ablation (+ mass-balance residual) | 0.997 | 0.763 | 0.864 | 0.000 | 0.237 | 21489 | 67 | 179121 | 6683 |

Event-level detection (primary detector):
| type | events | detected | median_delay |
|---|---|---|---|
| cyber_activity | 102 | 1.000 | 1.000 |
| physical_failure | 33 | 1.000 | 1.000 |
| ransomware | 31 | 1.000 | 0.000 |

## Network attack classifier (UNSW-NB15, Random Forest)
UNSW-NB15 official training partition, re-split 60/20/20 (stratified by attack category)
Rows: 175341 raw, 99268 after removing duplicates/conflicts. Test accuracy 0.841, macro-F1 0.715.
Binary (attack vs normal): precision 0.832, recall 0.997, F1 0.907, FPR 0.185, FNR 0.003.

| class | precision | recall | f1 | support |
|---|---|---|---|---|
| Analysis | 0.254 | 0.910 | 0.398 | 78.000 |
| Backdoor | 0.879 | 0.725 | 0.795 | 80.000 |
| DoS | 0.526 | 0.371 | 0.435 | 496.000 |
| Exploits | 0.873 | 0.842 | 0.857 | 3684.000 |
| Fuzzers | 0.613 | 0.953 | 0.746 | 2921.000 |
| Generic | 0.973 | 0.877 | 0.922 | 780.000 |
| Normal | 0.997 | 0.815 | 0.896 | 10333.000 |
| Reconnaissance | 0.815 | 0.961 | 0.882 | 1242.000 |
| Shellcode | 0.463 | 0.894 | 0.610 | 217.000 |
| Worms | 0.533 | 0.696 | 0.604 | 23.000 |

## Scenario S1 (run 1, seed 42, 500 trials)

| label | impact | throughput | hazard | blast_weighted | phys_hit | n_isolated | cost | objective | constraints_violated |
|---|---|---|---|---|---|---|---|---|---|
| No isolation | 0.270 | 0.522 | 0.000 | 0.317 | 0.122 | 0 | 0.000 | 0.270 | 0 |
| Isolate initial component | 0.270 | 0.522 | 0.000 | 0.317 | 0.122 | 1 | 0.500 | 0.272 | 0 |
| Full precautionary shutdown | 0.559 | 0.000 | 0.000 | 0.689 | 0.122 | 0 | 10.000 | 0.609 | 0 |
| ImpactGraph recommendation | 0.229 | 0.596 | 0.000 | 0.276 | 0.122 | 2 | 3.500 | 0.246 | 0 |

Recommended isolation (greedy, ImpactGraph):
- E05: cutting the link Vendor VPN Gateway -> Identity Service (Active Directory) (network) reduces expected impact by 0.014 and the chance of a physical failure by 0.0 percentage points (isolation cost 2.0).
- E06: cutting the link Vendor VPN Gateway -> Billing Application Server (network) reduces expected impact by 0.017 and the chance of a physical failure by 0.0 percentage points (isolation cost 1.5).

Prediction vs 2000-trial hold-out: node precision 0.937, recall 0.936, F1 0.916; frequency MAE 0.008; relative impact error 0.011.

Robustness (perturbed probabilities, fixed strategies):
| strategy | mean_j | p90_j | worst_j | std_j | win_rate_vs_no_isolation |
|---|---|---|---|---|---|
| no_isolation | 0.276 | 0.295 | 0.297 | 0.014 | 1.000 |
| initial_component | 0.279 | 0.297 | 0.299 | 0.014 | 0.000 |
| full_shutdown | 0.610 | 0.614 | 0.615 | 0.003 | 0.000 |
| impactgraph_greedy | 0.261 | 0.284 | 0.297 | 0.023 | 0.867 |

Sensitivity of the recommendation to lambda:
| lambda | isolated | n | cost |
|---|---|---|---|
| 0.000 | ['E05', 'E06', 'E10', 'E14', 'E22', 'E23'] | 6 | 12.500 |
| 0.020 | ['E05', 'E06'] | 2 | 3.500 |
| 0.050 | ['E05', 'E06'] | 2 | 3.500 |
| 0.100 | [] | 0 | 0.000 |
| 0.200 | [] | 0 | 0.000 |

## Scenario S2 (run 2, seed 42, 500 trials)

| label | impact | throughput | hazard | blast_weighted | phys_hit | n_isolated | cost | objective | constraints_violated |
|---|---|---|---|---|---|---|---|---|---|
| No isolation | 0.277 | 0.488 | 0.000 | 0.446 | 0.512 | 0 | 0.000 | 0.277 | 0 |
| Isolate initial component | 0.277 | 0.488 | 0.000 | 0.446 | 0.512 | 1 | 0.500 | 0.279 | 0 |
| Full precautionary shutdown | 0.542 | 0.000 | 0.000 | 0.797 | 0.512 | 0 | 10.000 | 0.592 | 0 |
| ImpactGraph recommendation | 0.070 | 0.916 | 0.000 | 0.240 | 0.084 | 2 | 2.000 | 0.080 | 0 |

Recommended isolation (greedy, ImpactGraph):
- E19: cutting the link Administrator Workstation -> IT/OT Gateway (DMZ) (network) reduces expected impact by 0.146 and the chance of a physical failure by 30.3 percentage points (isolation cost 1.0).
- E20: cutting the link Identity Service (Active Directory) -> IT/OT Gateway (DMZ) (auth) reduces expected impact by 0.089 and the chance of a physical failure by 18.3 percentage points (isolation cost 1.0).

Prediction vs 2000-trial hold-out: node precision 0.746, recall 0.901, F1 0.776; frequency MAE 0.020; relative impact error 0.092.

Robustness (perturbed probabilities, fixed strategies):
| strategy | mean_j | p90_j | worst_j | std_j | win_rate_vs_no_isolation |
|---|---|---|---|---|---|
| no_isolation | 0.271 | 0.303 | 0.327 | 0.032 | 1.000 |
| initial_component | 0.273 | 0.305 | 0.329 | 0.032 | 0.000 |
| full_shutdown | 0.592 | 0.596 | 0.597 | 0.003 | 0.000 |
| impactgraph_greedy | 0.078 | 0.092 | 0.100 | 0.014 | 1.000 |

Sensitivity of the recommendation to lambda:
| lambda | isolated | n | cost |
|---|---|---|---|
| 0.000 | ['E05', 'E14', 'E19', 'E20', 'E22', 'E23'] | 6 | 10.500 |
| 0.020 | ['E19', 'E20', 'E22', 'E23'] | 4 | 6.500 |
| 0.050 | ['E19', 'E20'] | 2 | 2.000 |
| 0.100 | ['E19', 'E20'] | 2 | 2.000 |
| 0.200 | ['E19', 'E20'] | 2 | 2.000 |

## Scenario S3 (run 3, seed 42, 500 trials)

| label | impact | throughput | hazard | blast_weighted | phys_hit | n_isolated | cost | objective | constraints_violated |
|---|---|---|---|---|---|---|---|---|---|
| No isolation | 0.487 | 0.104 | 0.396 | 0.152 | 0.896 | 0 | 0.000 | 0.487 | 0 |
| Isolate initial component | 0.487 | 0.104 | 0.396 | 0.152 | 0.896 | 0 | 0.000 | 0.487 | 0 |
| Full precautionary shutdown | 0.494 | 0.000 | 0.000 | 0.478 | 0.896 | 0 | 10.000 | 0.544 | 0 |
| ImpactGraph recommendation | 0.388 | 0.104 | 0.000 | 0.152 | 0.896 | 1 | 3.000 | 0.403 | 0 |

Recommended isolation (greedy, ImpactGraph):
- E41: closing the valve Pump Station 1 -> Pipeline Segment A (physical_flow) reduces expected impact by 0.117 and the chance of a physical failure by 0.0 percentage points (isolation cost 3.0).

Prediction vs 2000-trial hold-out: node precision 0.817, recall 0.339, F1 0.440; frequency MAE 0.007; relative impact error 0.016.

Robustness (perturbed probabilities, fixed strategies):
| strategy | mean_j | p90_j | worst_j | std_j | win_rate_vs_no_isolation |
|---|---|---|---|---|---|
| no_isolation | 0.486 | 0.503 | 0.527 | 0.017 | 1.000 |
| initial_component | 0.486 | 0.503 | 0.527 | 0.017 | 1.000 |
| full_shutdown | 0.544 | 0.544 | 0.545 | 0.000 | 0.000 |
| impactgraph_greedy | 0.396 | 0.407 | 0.412 | 0.009 | 1.000 |

Sensitivity of the recommendation to lambda:
| lambda | isolated | n | cost |
|---|---|---|---|
| 0.000 | ['E41'] | 1 | 3.000 |
| 0.020 | ['E41'] | 1 | 3.000 |
| 0.050 | ['E41'] | 1 | 3.000 |
| 0.100 | ['E41'] | 1 | 3.000 |
| 0.200 | ['E41'] | 1 | 3.000 |
