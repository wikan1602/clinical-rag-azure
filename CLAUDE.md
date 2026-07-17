# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

Week 1 in progress. Azure foundation is provisioned; application code (ingestion, FastAPI, Streamlit, eval) has not been written yet. There are no build/lint/test commands to run until that code exists.

Provisioned so far (resource group `rg-clinical-rag`, region `eastus`):
- Azure AI Search `search-clinical-rag` (Free tier — no semantic ranker; upgrade to Basic later if semantic ranking from the blueprint's hybrid-search design is needed)
- Azure OpenAI `openai-clinical-rag` with two deployments:
  - `gpt-5-mini` (chat) — the blueprint specifies GPT-4o-mini, but that model (and gpt-4.1-mini) is closed for new deployments as of this writing; gpt-5-mini is the replacement. Re-check model availability with `az cognitiveservices account list-models` before assuming a blueprint-named model can still be deployed.
  - `text-embedding-3-small` (embeddings)
- Local `.env` holds real credentials for both (gitignored) — `.env.example` shows the required shape only.

When code is added, update this file with the actual commands (e.g., `pytest`, `docker build`, `az deployment ...`) and remove this notice.

## What This Project Is

A portfolio project: a production-grade Retrieval-Augmented Generation (RAG) system on Azure — a "Clinical Knowledge Assistant" that answers questions grounded in clinical guideline documents (WHO guidelines, drug interaction references, discharge instructions) with citations, evaluation, monitoring, and CI/CD. The differentiator from a demo chatbot is production rigor: automated eval gating deployment, observability, and infra-as-code.

Full plan, weekly breakdown, and open decisions live in the blueprint — read it before starting implementation work, since it defines scope and target metrics that should drive design choices.

## Intended Architecture

Data flow: Document corpus → chunking pipeline (fixed-size vs. semantic, compared empirically) → embeddings → Azure AI Search (hybrid vector + keyword + semantic ranker) → FastAPI RAG service (retrieval → prompt → generation via Azure OpenAI gpt-5-mini) → Streamlit UI. A parallel evaluation track (RAGAS) runs a golden Q&A dataset against the pipeline for regression testing and CI gating.

Key components once built:
- **Ingestion/chunking pipeline** — compares fixed-size vs. semantic chunking; the choice must be justified by eval data, not intuition (see blueprint §4 Week 1–2).
- **FastAPI service** — retrieval + prompt assembly + generation; instrumented with Application Insights for latency/token/cost/error tracking, and full trace logging (query → retrieved chunks → prompt → answer) for debugging.
- **Evaluation harness** — RAGAS (or Azure AI Evaluation SDK) computing faithfulness, answer relevancy, context precision, context recall against a golden dataset (30–50 Q&A pairs, including cases that should be refused/unknown to test hallucination resistance). Target thresholds are in blueprint §5 (faithfulness/relevancy > 0.85, precision/recall > 0.75, p95 latency < 3–5s).
- **CI/CD** — GitHub Actions: unit tests → eval suite against golden dataset → deployment gated on eval scores meeting threshold → deploy to Azure Container Apps.
- **IaC** — Bicep or Terraform for Azure OpenAI, AI Search, Container Apps, App Insights (decision still open — see blueprint §8).

## Working Conventions for This Repo

- Every chunking/retrieval/prompting decision should be evaluated with the RAGAS metrics rather than asserted — this project's entire value proposition is measurable rigor over "it works."
- Keep scope aligned to the weekly breakdown in the blueprint; treat multi-modal or agentic extensions as future work, not part of this build (see blueprint §6 Risks & Mitigations).
- Use only public/open datasets for the document corpus (WHO guidelines, open PubMed abstracts) — avoid anything requiring institutional access, per the licensing constraint in the blueprint.
- Prefer GPT-4o-mini and small corpora during development to conserve Azure credits; scale up only for final demo.
