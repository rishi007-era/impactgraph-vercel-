# ImpactGraph Phase 1: presentation guide (10-12 minutes)

## Before you present
1. `streamlit run app.py`, open the browser full-screen (F11), zoom 100%.
2. Pick scenario **S2** first (clearest story). Keep **S1** and **S3** ready.
3. Have `results/RESULTS.md` open in a second window for tough questions.
4. Run `python -m pytest -q` once beforehand so you can say "61 tests pass".

## The story in one sentence
"Monitoring tells you one machine is suspicious; ImpactGraph tells you how far the incident can spread, what it would do to the pipeline, and which few links to cut so the safe parts keep running, instead of shutting everything down."

## Demo script (follow the sidebar order)
| Min | Page | Say | Click |
|---|---|---|---|
| 0:00 | Executive Summary | Problem, the three honesty badges (synthetic, assumed, advisory), headline numbers. | Point at the 5 KPI cards and the strategy bar chart. |
| 1:30 | 1 · Infrastructure Overview | 24 components, 48 typed relationships, 4 zones; the model validates itself. | Show validation PASS and the relationship donut. |
| 2:30 | 2 · Network Topology | Typed graph: attack routes, authentication, control and physical flow are never mixed. Zones follow the Purdue model with an IT/OT gateway. | Click a node (e.g. OT01) and read its inspector; toggle layers. |
| 3:30 | 3 · Telemetry, 4 · Anomaly Detection | Synthetic telemetry with ground truth; one Isolation Forest per component; an alert means "unusual", not "attack". | Drag the threshold slider; open "Why was this component flagged?". |
| 5:00 | 5 · Attack Scenario | A graph link is not enough: every hop needs access conditions. The route is explained hop by hop. | Pick target PH01; read the hop table. |
| 6:00 | 6 · Propagation Simulation | 500 Monte Carlo trials; replay one trial step by step. | Press **Play replay**; switch to "With ImpactGraph isolation". |
| 7:30 | 7 · Risk Assessment | Transparent formula; centrality is supplementary only. | Show the risk heat-map and the likelihood decomposition. |
| 8:30 | 8 · Isolation Recommendations | Greedy search on a stated objective, with safety and continuity constraints; every action explained. | Read one explanation; show the lambda sensitivity table. |
| 9:30 | 9 · Before / After | Same incident, with and without containment, identical random draws. | Compare the two graphs and the throughput histogram. |
| 10:30 | 10 · Evaluation Metrics | Real measured numbers, including the weak ones. | Detection tab, then Limitations tab. |

## Three-scenario summary (seed 42, 500 trials; see results/RESULTS.md)
- **S1 Mode A (Colonial-inspired, IT-side):** ImpactGraph's marginal recommendation (cut VPN to identity and billing) lowers impact modestly. A full precautionary shutdown costs far more under our assumptions.
- **S2 Mode B (hypothetical IT-to-OT):** cutting the two IT-to-DMZ links removes most of the path to the pump controller and preserves most throughput.
- **S3 Mode P (physical sabotage):** closing the pump-station discharge valve after a rupture removes the release hazard.

## What to say about honesty (graders respect this)
- Mode A reproduces only the documented IT-side incident and the precautionary shutdown. Mode B and P are hypothetical simulations, not claims about 2021.
- Probabilities are assumed, outputs are simulation frequencies, telemetry is synthetic, UNSW-NB15 is lab traffic.
- We tested a physics-consistency (mass-balance) feature; it did not help, so we say so and keep the simpler detector.

## Likely questions and honest answers
- **"Is this real data?"** No. Synthetic telemetry and an assumed model; the public dataset is only used for the traffic classifier.
- **"How accurate is the prediction?"** We measure simulation stability against an independent 2000-trial run and robustness under +/-30% perturbed probabilities. We cannot claim accuracy against real incidents.
- **"Why greedy?"** Transparent and fast; Phase 2 adds an exhaustive reference and constrained optimisation to measure the gap.
- **"Why did the classifier have 18.5% false positives?"** UNSW-NB15 after removing duplicates is hard; we report it and use the classifier only as one evidence input.
- **"What is novel?"** Not the algorithms. The contribution is the integrated, evaluated framework: attack paths with preconditions, throughput-based impact, containment with safety constraints, and robustness testing, all in one reproducible pipeline.
- **"Does it control real systems?"** No. Advisory only; no connection to any industrial system.

## Backup plan
If the live app misbehaves: open `results/RESULTS.md` and the `docs/figures` images (generated from the same database).
