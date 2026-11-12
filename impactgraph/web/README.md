# ImpactGraph web viewer

A static React + Vite app that shows the pre-computed ImpactGraph Phase 1 results: summary, topology with hop-by-hop replay,
attack paths, risk, containment, evaluation. It needs no backend and no API keys.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # outputs dist/ (works on any static host)
```

Data lives in `public/data.json`. Regenerate it from the Python results database (repo root):
```bash
python scripts/export_static.py impactgraph.db web/public/data.json
```
Deep links: `#/summary/S2`, `#/replay/S2`, `#/paths/S2`, `#/risk/S2`, `#/contain/S2`, `#/eval/S2`, `#/about/S2` (scenarios S1, S2, S3).
Optional environment variable `VITE_REPO_URL` adds a "Source code" link on the About tab.

Deploy: Vercel (Root Directory `web`), GitHub Pages, Firebase Hosting, Cloud Run, or Google AI Studio (Import from GitHub). See `../DEPLOY.md`.
