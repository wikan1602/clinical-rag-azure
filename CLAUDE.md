# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**All 4 weeks complete.** Weeks 1–3 (core RAG pipeline, evaluation framework, monitoring) and Week 4 (Docker containerization, Bicep IaC, GitHub Actions CI/CD) are all done, deployed, and verified end-to-end — the pipeline (`.github/workflows/deploy.yml`: build → run eval suite against the candidate build → gate on scores → push to ACR → deploy to Container Apps) runs fully green on push to `master`. Getting it green took real debugging: the eval step's `getaddrinfo failed` errors looked like Docker/CI networking flakiness through five debug cycles (`--dns` flags, `--network host`, IPv6 checks, running eval without Docker) but the actual root cause was a wrong `AZURE_OPENAI_ENDPOINT` value (a hostname that never existed in DNS, confirmed NXDOMAIN) in both `.env` and the GitHub secret — see the correction note in `docs/week4-notes.md`. A second, unrelated fix was needed after that: the Azure AD federated credential's subject had to be updated to GitHub's newer `repo:{owner}@{owner_id}/{repo}@{repo_id}:ref:...` OIDC subject format. An agentic query-routing extension (temporal/aggregate retrieval, beyond the original blueprint scope) was added before finishing Week 4 — see `docs/week4-notes.md`.

Note on eval runtime in CI: the eval step alone can take well over an hour (90 evaluations × several model calls each, against the `gpt-5-mini` deployment's capacity-10 GlobalStandard quota) — this is real rate-limit-driven retry backoff, not a hang.

Weekly technical journals with design rationale, bugs found, and decisions made live in `docs/week1-notes.md` through `week4-notes.md` — read the relevant one before touching an area substantially changed in that week.

Provisioned Azure resources (resource group `rg-clinical-rag`, region `eastus`), declared in `infra/*.bicep`:
- Azure AI Search `search-clinical-rag` (Free tier), two indexes: `clinical-guidelines-fixed`, `clinical-guidelines-semantic`
- Azure OpenAI `openai-clinical-rag`: `gpt-5-mini` (chat — replaces blueprint's GPT-4o-mini, closed for new deployments at build time) and `text-embedding-3-small` (embeddings)
- Application Insights `appinsights-clinical-rag` (workspace-based, `law-clinical-rag`) + alerts (`alert-high-latency`, `alert-low-faithfulness`) + Workbook "Clinical RAG Monitoring"
- Azure Container Registry `acrclinicalragzgyaq2umgqzpg` + Container Apps environment with `ca-clinical-rag-api` (port 8000) and `ca-clinical-rag-ui` (port 8501)
- GitHub Actions authenticates to Azure via OIDC federated credential (Azure AD app `gh-clinical-rag-deploy`, Contributor scoped to `rg-clinical-rag` only) — no long-lived service-principal secret
- Local `.env` holds real credentials (gitignored); `.env.example` shows the required shape only. Never baked into Docker images — passed at container/Container-App runtime, or via GitHub Secrets in CI.

## Commands

```
# Local dev
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # API on :8000
streamlit run ui/app.py                # UI on :8501

# Ingestion (re-run after changing chunking/metadata)
python -m ingestion.run_ingestion      # parse PDFs, chunk, write data/processed/*.json
python -m ingestion.run_indexing       # embed + upload to Azure AI Search

# Evaluation
python -m eval.run_eval                # runs golden_dataset.json against both indexes, saves eval/results/*.json

# Docker
docker compose up --build              # both services, API reachable at :8000, UI at :8501

# IaC (Bicep) — see infra/README.md for full detail
az deployment group what-if -g rg-clinical-rag -f infra/main.bicep -p infra/main.bicepparam   # ALWAYS preview before applying
az deployment group create -g rg-clinical-rag -f infra/main.bicep -p infra/main.bicepparam

# CI/CD
gh workflow run deploy.yml             # manual trigger (also runs on every push to master)
gh run watch --exit-status             # follow the current run
python .github/scripts/check_eval_gate.py   # re-check the eval gate locally against the latest eval/results/*.json
```

No unit test suite exists yet (`pytest` not set up) — correctness is currently verified via `eval/run_eval.py` against the golden dataset, not unit tests. Note this gap if asked to add CI that "runs tests."

## What This Project Is

A portfolio project: a production-grade Retrieval-Augmented Generation (RAG) system on Azure — a "Clinical Knowledge Assistant" that answers questions grounded in WHO clinical guideline documents with citations, evaluation, monitoring, and CI/CD. The differentiator from a demo chatbot is production rigor: automated eval gating deployment, observability, and infra-as-code — plus, as of the agentic routing extension, moving beyond naive vector-only retrieval where the query shape demands it.

Full original plan and weekly breakdown live in the blueprint (`Blueprint_Production_RAG_Azure.md`); treat it as the initial design, not the current source of truth — several decisions (model substitution, agentic routing, custom eval metrics instead of the `ragas` library) deviated from it for documented reasons, see the weekly notes.

## Architecture

Data flow: Document corpus → chunking pipeline (fixed-size vs. semantic, both indexed) → embeddings → Azure AI Search → **query router** (classifies each question as `semantic`/`temporal`/`aggregate`) → matching retrieval strategy → FastAPI RAG service (prompt assembly → generation via gpt-5-mini) → Streamlit UI. A parallel evaluation track runs a golden Q&A dataset (including router-accuracy checks and refusal cases) against the pipeline for regression testing.

Key components:
- **`ingestion/`** — PDF parsing, fixed-size vs. semantic chunking, embedding + indexing. `data/document_metadata.json` is the hand-curated source of truth for each document's `topic`/`published_year` (used by the router, not auto-parsed from filenames).
- **`app/`** — FastAPI service. `app/query_router.py` classifies queries via Azure OpenAI function-calling; `app/retrieval.py` has three retrieval paths (`retrieve_chunks` semantic, `retrieve_temporal`, `retrieve_aggregate`); `app/generation.py` builds prompts and calls the chat model; `app/main.py` wires it together behind `/query`. Instrumented with Application Insights (`configure_azure_monitor()` + `FastAPIInstrumentor` — the latter must be called explicitly, auto-instrumentation alone misses FastAPI request telemetry).
- **`eval/`** — custom RAGAS-style metrics (`eval/metrics.py`, implemented directly against Azure OpenAI as judge — the `ragas` PyPI package doesn't install on this machine, see `docs/week2-notes.md`) plus `router_accuracy` for the routing extension.
- **`.github/workflows/deploy.yml`** — on push to `master` (or manual dispatch): builds both Docker images (for the later ACR push/deploy), then runs the candidate code directly via `uvicorn app.main:app` in the runner's own venv (not inside Docker — see the DNS root-cause note in `docs/week4-notes.md` for why), runs `eval/run_eval.py` against it (evaluates the *candidate* build, not the currently-live one), gates on `.github/scripts/check_eval_gate.py` (faithfulness/context_precision/context_recall/refusal_accuracy thresholds from the blueprint — `answer_relevancy` deliberately excluded, see `docs/week2-notes.md`), then pushes both Docker images to ACR and runs `az containerapp update` for both apps. No unit-test stage — there are no unit tests (see above).
- **`infra/`** — Bicep IaC for every Azure resource (Search, OpenAI, Log Analytics/App Insights/alerts/workbook, Container Registry, Container Apps environment + both apps). Secrets are never written to `.bicep`/`.bicepparam` — `containerapps.bicep` pulls keys live via `listKeys()`/`listAdminKeys()`. See `infra/README.md` for the what-if-before-apply deploy flow.

## Working Conventions for This Repo

- Every chunking/retrieval/prompting decision should be evaluated with the eval harness rather than asserted — this project's value proposition is measurable rigor over "it works." Semantic chunking is the chosen default (`app/main.py`'s `QueryRequest.strategy`) based on Week 2 eval results, not intuition.
- New retrieval/generation logic should log through the existing `logger = logging.getLogger("rag.<module>")` + `logger.info(event_name, extra={...})` convention so it stays visible in the Application Insights dashboard/alerts, not just local prints.
- Use only public/open datasets for the document corpus (WHO guidelines) — avoid anything requiring institutional access. Verify a document's actual publisher before citing it as "WHO" — one corpus document turned out to be a Royal Government of Bhutan MoH guideline, not a WHO publication (see `data/SOURCES.md`).
- Keep IaC/CI-CD minimal for Week 4 (single environment, no staging/prod split) — this was an explicit scope decision to avoid Week 4 eating disproportionate time, not an oversight.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
