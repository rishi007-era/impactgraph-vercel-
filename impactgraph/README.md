# ImpactGraph (Phase 1)

AI-powered cyber-physical failure propagation, impact prediction and resilience engine, built on a Colonial Pipeline-inspired
case study. Simulation and decision support only: it never connects to or controls real industrial systems.

**Quick start**
```bash
pip install -r requirements.txt
python -m impactgraph.experiments.runner --fresh      # about 90 s; results are stored in impactgraph.db
streamlit run app.py                                  # dashboard at http://localhost:8501
python -m pytest -q                                   # 61 tests
```
See `docs/RUN_GUIDE.md` (run it), `docs/PRESENTATION_GUIDE.md` (present it), `docs/architecture.md`, `docs/graph_schema.md`,
`docs/assumptions_and_limitations.md` and `results/RESULTS.md` (measured results).

## Deploy
- **Static web viewer** (`web/`, React + Vite, no backend): Vercel, GitHub Pages, Firebase Hosting, Google AI Studio.
- **Full interactive app** (Streamlit): Docker (`Dockerfile`) on Google Cloud Run, or Streamlit Community Cloud.
- Step-by-step guide: [`DEPLOY.md`](DEPLOY.md).

Safety: ImpactGraph is a simulation and decision-support tool. It never scans, connects to or controls real systems.
Telemetry is synthetic and all probabilities are assumptions. See `docs/assumptions_and_limitations.md`.
