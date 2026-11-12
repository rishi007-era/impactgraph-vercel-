# Full interactive ImpactGraph (Streamlit) for Google Cloud Run or any container host.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# UNSW-NB15 is not stored in git (licence + size). Download it so "Run new simulation" can use the classifier.
# If the download fails the app still works; it simply runs without the classifier evidence.
RUN python scripts/download_unsw.py || echo "dataset download skipped"
ENV PORT=8080
EXPOSE 8080
CMD streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false
