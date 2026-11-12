# Assumptions and limitations (Phase 1)

| Area | What is real | What is assumed or synthetic |
|---|---|---|
| Colonial incident | IT-side ransomware; precautionary operations shutdown; OT not shown compromised (public record) | OT-foothold probability (0.15), billing dependency on deliveries, all model structure |
| Topology | Zone concepts, Purdue levels, DMZ gateway are standard practice | All 24 components, 48 relationships, importance, exposure, vulnerability |
| Attack model | Independent-cascade attack-graph idea from the literature | Every traversal probability, 3 attempts per link, capability gains, response delay |
| Telemetry | none | All values, units, ranges, anomaly shapes (documented in the telemetry catalogue) |
| Classifier | UNSW-NB15 is a real public dataset | It is lab traffic; the flow bridge to graph components is an assumption |
| Optimiser | Greedy heuristic | Weights, costs, lambda, constraints (sensitivity reported for lambda) |

Known limitations: steady-state flow only; no recovery dynamics; detector choice made after seeing an ablation on test episodes (primary metrics slightly optimistic);
classifier has 18.5% benign false positives; propagation "prediction" is validated against the model itself, not real incidents; greedy search has no optimality guarantee.
