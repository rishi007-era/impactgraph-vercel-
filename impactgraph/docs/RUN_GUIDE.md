# ImpactGraph Phase 1: how to run it

## 1. Requirements
Python 3.10+ (tested on 3.12), about 2 GB free RAM, no GPU, no cloud, no paid tools.

## 2. Install (once)
```bash
cd impactgraph
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Dataset (already included; only needed if the file is missing)
```bash
python scripts/download_unsw.py      # downloads UNSW-NB15 training partition to data/raw/unsw-nb15/
```

## 4. Run the full pipeline (about 90 seconds on one laptop CPU)
```bash
python -m impactgraph.experiments.runner --fresh
python -m impactgraph.experiments.reports impactgraph.db     # writes results/RESULTS.md and CSV tables
```
This executes: telemetry generation, Isolation Forest training and held-out evaluation, UNSW-NB15 classifier,
three scenarios (500 Monte Carlo trials each), risk scoring, greedy containment, baselines, robustness tests, and stores everything in `impactgraph.db`.
A pre-computed `impactgraph.db` (seed 42) is included so the dashboard opens immediately.

## 5. Open the dashboard
```bash
streamlit run app.py
```
Open http://localhost:8501. Deep links: `?page=<0-10>&sc=<S1|S2|S3>` (e.g. `http://localhost:8501/?page=9&sc=S2`).

## 6. Tests
```bash
python -m pytest -q          # 61 tests, about 30 seconds
```

## 7. Reproducibility
`--seed` and `--trials` control the run. The same seed gives identical stored results (tested). Every run stores its parameters, weights, versions and seed in the `runs` table; reload any previous run from the dashboard sidebar.

## 8. Troubleshooting
- "No experiment results found": run step 4.
- Port busy: `streamlit run app.py --server.port 8600`.
- Slow first "Run new simulation" in the sidebar: it trains detectors once (about 20 s), later runs are faster.
