# Clinical Knowledge Assistant — RAG on Azure

Production-grade Retrieval-Augmented Generation (RAG) system on Azure, answering questions grounded in public clinical guideline documents with citations, evaluation, monitoring, and CI/CD.

See [Blueprint_Production_RAG_Azure.md](Blueprint_Production_RAG_Azure.md) for the full project plan.

## Project Structure

- `ingestion/` — PDF parsing, chunking (fixed-size and semantic), embedding + indexing scripts
- `app/` — FastAPI RAG service (query router → retrieval → prompt → generation)
- `ui/` — Streamlit UI for manual testing
- `eval/` — RAGAS-style evaluation harness and golden dataset
- `infra/` — IaC templates (Bicep) for all Azure resources
- `.github/workflows/` — CI/CD: build → eval-gate → deploy to Azure Container Apps

## Setup

1. Create and activate a virtual environment: `python -m venv .venv` then `.venv\Scripts\activate` (Windows).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your Azure OpenAI / Azure AI Search credentials.
4. Run the API: `uvicorn app.main:app --reload`
5. Run the UI: `streamlit run ui/app.py`

## Running with Docker

Requires Docker Desktop and a filled-in `.env` (same one used for local venv setup — credentials are passed in at container runtime, never baked into the image).

```
docker compose up --build
```

- API: `http://localhost:8000` (health check at `/health`)
- UI: `http://localhost:8501`

`Dockerfile.api` and `Dockerfile.ui` build two separate images (the API and UI are independent processes communicating over HTTP — `docker-compose.yml` wires the UI container to the API container via `API_URL=http://api:8000`, Docker Compose's internal service DNS).
