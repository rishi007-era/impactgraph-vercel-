# Deploying ImpactGraph

Two things can be deployed, because they have different needs:

| What | Folder | Needs | Where it can go |
|---|---|---|---|
| **Web viewer** (pre-computed results, replay, charts) | `web/` | static hosting only | Vercel, GitHub Pages, Firebase Hosting, Google AI Studio / Cloud Run |
| **Full app** (run new simulations, seeds, trials) | repo root, `app.py` | a Python server with WebSockets | Google Cloud Run (Dockerfile), Streamlit Community Cloud |

Vercel and GitHub Pages serve static sites and short serverless functions, which do not suit a long-running Streamlit server,
so the web viewer is the part you put there. Add the full app's URL to your README once it is live.

## 1. GitHub
1. Create an empty repository on github.com (for example `impactgraph`). Do not add a README there.
2. In the project folder:
   ```bash
   git init
   git add .
   git commit -m "ImpactGraph Phase 1"
   git branch -M main
   git remote add origin https://github.com/<your-username>/impactgraph.git
   git push -u origin main
   ```
3. Open the **Actions** tab: the `CI` workflow runs the 61 Python tests and builds the web viewer.
4. (Optional) GitHub Pages: Settings > Pages > Source: **GitHub Actions**; then Actions > "Deploy web viewer to GitHub Pages" > Run workflow.

The UNSW-NB15 dataset and trained model are not committed (see `.gitignore`). `python scripts/download_unsw.py` fetches the dataset.

## 2. Vercel (web viewer)
1. vercel.com > Add New > Project > Import your GitHub repository.
2. **Root Directory: `web`** (important). Framework Preset: Vite (auto-detected). Build command `npm run build`, output `dist`.
3. (Optional) Environment variable `VITE_REPO_URL` = your GitHub repository URL.
4. Deploy. Every push to `main` redeploys automatically.
CLI alternative: `cd web && npx vercel --prod`.

## 3. Google
**3a. Google AI Studio (Build mode)** builds web apps, so use the web viewer only:
1. Put the contents of the `web/` folder in its own GitHub repository (for example `impactgraph-web`; the second zip has it ready).
2. AI Studio > Build > the **+ (Add files)** menu in the prompt box > **Import from GitHub** > choose that repository.
3. If the preview does not start, paste: *"This is a static Vite + React app. Keep public/data.json and all components. Make sure `npm run build` and the preview work. Do not add any Gemini API calls."*
4. Use **Deploy** to publish to Cloud Run (Cloud Run charges may apply).

**3b. Full Streamlit app on Google Cloud Run** (from the repo root):
```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud run deploy impactgraph --source . --region asia-south1 --allow-unauthenticated --memory 2Gi --port 8080
```
Cloud Run needs a billing account on the project (it has a free tier). Runs created inside the deployed app are stored on the
container's disk and disappear when the instance restarts; the included `impactgraph.db` (seed 42) is always available.

**3c. Streamlit Community Cloud (free alternative for the full app):** share.streamlit.io > New app > your GitHub repo > branch `main` > main file `app.py`.

## 4. Updating results
```bash
python -m impactgraph.experiments.runner --fresh
python scripts/export_static.py impactgraph.db web/public/data.json
git add -A && git commit -m "Update results" && git push
```

## 5. Notes
- No secrets or API keys are required anywhere.
- Everything shown is simulation output (synthetic telemetry, assumed probabilities). Keep the honesty badges and the About tab when you publish.
- Confirm the licence (MIT in `LICENSE`) with your mentor or college before making the repository public.
