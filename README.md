# AutoRisk

Used car reliability and risk scoring for student buyers ($5–10k, 2008–2018 vehicles).

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scriptsctivate
pip install requests pandas scikit-learn nltk xgboost streamlit tqdm
```

## Phase 1 — Fetch NHTSA data

```bash
# Smoke test first (single vehicle, fast)
python src/fetch_nhtsa.py --test

# Full fetch (~30 vehicles, takes ~2 min with rate limiting)
python src/fetch_nhtsa.py
```

Outputs to `data/`:
- `complaints.csv`     — free-text complaint summaries (NLP input)
- `recalls.csv`        — recall campaigns
- `investigations.csv` — open/closed NHTSA investigations

## Project structure

```
autorisk/
├── data/               # CSV outputs (gitignore this)
├── src/
│   ├── fetch_nhtsa.py  # Phase 1: data pipeline
│   ├── nlp.py          # Phase 2: TF-IDF + KMeans
│   ├── model.py        # Phase 2: XGBoost depreciation
│   ├── scoring.py      # Phase 3: score engine
│   └── app.py          # Phase 4: Streamlit UI
├── requirements.txt
└── Dockerfile
```
