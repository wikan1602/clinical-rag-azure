# Clinical Knowledge Assistant — RAG on Azure

Production-grade Retrieval-Augmented Generation (RAG) system on Azure, answering questions grounded in public clinical guideline documents with citations, evaluation, monitoring, and CI/CD.

See [Blueprint_Production_RAG_Azure.md](Blueprint_Production_RAG_Azure.md) for the full project plan.

## Project Structure

- `ingestion/` — PDF parsing, chunking (fixed-size and semantic), embedding + indexing scripts
- `app/` — FastAPI RAG service (retrieval → prompt → generation)
- `ui/` — Streamlit UI for manual testing
- `eval/` — RAGAS evaluation harness and golden dataset
- `infra/` — IaC templates (Bicep) for Azure resources

## Setup

1. Copy `.env.example` to `.env` and fill in your Azure OpenAI / Azure AI Search credentials.
2. `pip install -r requirements.txt`
3. Run the API: `uvicorn app.main:app --reload`
4. Run the UI: `streamlit run ui/app.py`
