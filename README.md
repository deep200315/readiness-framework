# Readiness Framework

An AI-driven data quality agent that automates the gap between raw Databricks tables and ML-ready data. Instead of manually inspecting and cleaning data before training, this agent scores your data, explains what's wrong, and applies fixes — with a human approval step before anything changes.

---

## Stack

- **Agent** — LangGraph (stateful graph, human-in-the-loop checkpoints)
- **LLM** — Azure OpenAI GPT-4o (generates fix suggestions)
- **Backend** — FastAPI + Redis
- **Data** — Databricks SQL (source user-selected, target fixed)
- **Frontend** — Streamlit

---

## Setup

### 1. Clone & create virtualenv

```bash
git clone https://github.com/deep200315/readiness-framework.git
cd readiness-framework
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
```

Fill in `.env`:

```env
DATABRICKS_HOST=your-workspace.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxx
DATABRICKS_TOKEN=dapi...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your-key
REDIS_URL=redis://localhost:6379
```

### 3. Set target table

Edit `config/config.yaml` — set `target_catalog`, `target_schema`, `target_table` to a Databricks location your token can write to.

### 4. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 5. Run

```bash
# Backend (terminal 1)
uvicorn backend.main:app --reload-dir backend --reload-dir config --reload-dir agent --reload-dir metrics --reload-dir connectors --reload-dir pipelines --port 8000

# Frontend (terminal 2)
streamlit run frontend/app.py
```

Open **http://localhost:8501**

---

## How it works

1. Select a Databricks table in the UI
2. Agent fetches up to 50k rows locally
3. Scores data 0–10 across metadata, quality, governance, and fairness
4. **Score ≥ 8.0** → pushes directly to the target table
5. **Score < 8.0** → GPT-4o suggests fixes → you approve → local pipeline applies transforms → re-scores → repeat (up to 5 iterations)

Logs are written to `logs/logs.log` in real time.

---

## Notes

- `.env` is gitignored — never commit it
- Source table is never modified; all transforms run on a local copy
- Target table is fixed in config; users only pick the source
