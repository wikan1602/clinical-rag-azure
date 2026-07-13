# Blueprint: Production-Grade RAG Platform on Azure
### Clinical Knowledge Assistant — Portfolio Project

**Owner:** Wikan Priambudi
**Duration:** 4 weeks (1 month+)
**Goal:** Build a production-grade Retrieval-Augmented Generation (RAG) system on Azure with evaluation, monitoring, and CI/CD — demonstrating end-to-end LLM engineering maturity for AI Engineer (LLM/RAG) roles.

---

## 1. Project Overview

### 1.1 Problem Statement
Clinical staff need fast, trustworthy answers to questions grounded in official guidelines (e.g., WHO clinical guidelines, drug interaction references, discharge instruction templates) — without hallucination risk. This project builds a RAG system that retrieves from a curated medical knowledge base and generates grounded, citable answers.

### 1.2 Why This Project
- Directly extends current experience at PT Daya Medika Pratama (LLM-powered HIS assistant)
- Demonstrates **production rigor** (eval + monitoring + CI/CD), not just a demo chatbot — this is the differentiator most candidates lack
- Reuses existing MLOps skillset (Docker, Airflow, MLflow, Evidently AI, GitHub Actions) in a new cloud context (Azure)
- Produces a coherent interview narrative: architecture decisions, trade-offs, and measurable quality metrics

### 1.3 Target Outcome
A deployed, publicly accessible RAG application with:
- A documented architecture diagram
- A measurable evaluation report (faithfulness, relevancy, precision/recall)
- A live monitoring dashboard
- A CI/CD pipeline that gates deployment on eval pass/fail
- A GitHub repo + write-up suitable for CV/portfolio/LinkedIn

---

## 2. Tech Stack Summary

| Layer | Tool/Service | Notes |
|---|---|---|
| LLM | Azure OpenAI (GPT-4o-mini) | Cost-efficient for experimentation |
| Retrieval / Vector Store | Azure AI Search | Hybrid search (vector + keyword + semantic ranker) |
| Orchestration | Azure AI Foundry | Prompt flow, tracing, deployment management |
| Evaluation | RAGAS / Azure AI Evaluation SDK | Faithfulness, relevancy, context precision/recall |
| Monitoring | Azure Monitor + Application Insights | Latency, token usage, cost, quality alerts |
| App Layer | FastAPI (backend) + Streamlit (UI) | Reuse existing skillset |
| Containerization | Docker | Already proficient |
| Deployment | Azure Container Apps | Simpler & cheaper than AKS for a portfolio project |
| CI/CD | GitHub Actions | Eval-gated deployment |
| IaC | Bicep (or Terraform) | Native Azure IaC, adds infra-as-code credibility |
| Dashboarding (optional) | Apache Superset | Reuse from prior MLOps project |

---

## 3. Architecture Overview

```
                 ┌─────────────────────┐
                 │   Document Corpus    │
                 │ (Clinical Guidelines,│
                 │  Drug Interactions)  │
                 └──────────┬───────────┘
                            │ ingestion
                            ▼
                 ┌─────────────────────┐
                 │  Chunking Pipeline   │
                 │ (fixed vs semantic)  │
                 └──────────┬───────────┘
                            │ embeddings
                            ▼
                 ┌─────────────────────┐
                 │   Azure AI Search    │
                 │ (hybrid vector+kw)   │
                 └──────────┬───────────┘
                            │ retrieved context
                            ▼
        ┌───────────────────────────────────┐
        │        FastAPI RAG Service         │
        │  (retrieval → prompt → generation) │
        └───────┬─────────────────┬──────────┘
                 │                 │
                 ▼                 ▼
     ┌─────────────────┐   ┌──────────────────┐
     │ Azure OpenAI     │   │ App Insights /    │
     │ (GPT-4o-mini)    │   │ Azure Monitor      │
     └─────────────────┘   └──────────────────┘
                 │
                 ▼
     ┌─────────────────┐
     │ Streamlit UI     │
     └─────────────────┘

     Parallel track: Evaluation Framework (RAGAS)
     → Golden Q&A dataset → regression testing → CI gate
```

---

## 4. Weekly Breakdown

### Week 1 — Core RAG Pipeline
**Goal:** Working end-to-end RAG, deployed locally.

- [ ] Set up Azure account, resource group, budget alerts
- [ ] Provision Azure OpenAI resource + deploy GPT-4o-mini
- [ ] Provision Azure AI Search resource
- [ ] Collect/curate document corpus (public clinical guidelines — WHO, PubMed abstracts, or open discharge-instruction templates)
- [ ] Build ingestion pipeline: PDF parsing → chunking
  - [ ] Implement fixed-size chunking (baseline)
  - [ ] Implement semantic chunking (comparison)
- [ ] Generate embeddings, index into Azure AI Search (hybrid: vector + keyword + semantic ranker)
- [ ] Build retrieval + generation service (FastAPI)
- [ ] Build minimal Streamlit UI for manual testing
- [ ] Document chunking strategy comparison (short write-up: which performed better and why)

**Deliverable:** Working local RAG demo + short architecture note.

---

### Week 2 — Evaluation Framework
**Goal:** Quantify RAG quality, not just "it works."

- [ ] Build golden dataset: 30–50 Q&A pairs grounded in the corpus (include some "should refuse/unknown" cases to test hallucination resistance)
- [ ] Integrate RAGAS (or Azure AI Evaluation SDK) to measure:
  - [ ] Faithfulness (no hallucination beyond retrieved context)
  - [ ] Answer relevancy
  - [ ] Context precision
  - [ ] Context recall
- [ ] Run baseline eval on both chunking strategies from Week 1 — pick the winner with data, not intuition
- [ ] Log eval results (versioned per pipeline config) — reuse MLflow if convenient, or simple CSV/JSON + Superset dashboard
- [ ] Write up eval methodology + results (this becomes strong interview material)

**Deliverable:** Evaluation report with baseline scores + chosen configuration justified by data.

---

### Week 3 — Monitoring & Observability
**Goal:** Make the system debuggable and production-aware.

- [ ] Instrument FastAPI service with Application Insights (latency, token usage, cost per query, error rate)
- [ ] Implement full trace logging: query → retrieved chunks → prompt → final answer (for debugging bad answers)
- [ ] Set up Azure AI Foundry tracing (or Langfuse/LangSmith if preferring open-source tooling)
- [ ] Define quality thresholds and configure alerting (e.g., alert if faithfulness drops below X% on scheduled eval runs)
- [ ] Build a simple monitoring dashboard (Azure Monitor workbook or Superset) showing: latency trend, cost trend, eval score trend

**Deliverable:** Live dashboard + documented alerting strategy.

---

### Week 4 — CI/CD & Deployment
**Goal:** Ship it like a real product.

- [ ] Containerize FastAPI + Streamlit with Docker
- [ ] Write Bicep (or Terraform) templates for Azure resources (Search, OpenAI, Container Apps, App Insights)
- [ ] Set up GitHub Actions pipeline:
  - [ ] On push: run unit tests
  - [ ] Run eval suite against golden dataset
  - [ ] Gate deployment — only deploy if eval scores meet threshold
  - [ ] Deploy to Azure Container Apps on pass
- [ ] Set up staging vs production environment (optional but strong signal)
- [ ] Final documentation pass: architecture diagram, README, cost breakdown, lessons learned

**Deliverable:** Publicly accessible deployed app + CI/CD pipeline visible on GitHub.

---

## 5. Evaluation Metrics Reference

| Metric | What it measures | Target |
|---|---|---|
| Faithfulness | Does the answer stay grounded in retrieved context? | > 0.85 |
| Answer Relevancy | Is the answer actually relevant to the question? | > 0.85 |
| Context Precision | Are retrieved chunks relevant (low noise)? | > 0.75 |
| Context Recall | Did retrieval capture the needed information? | > 0.75 |
| Latency (p95) | End-to-end response time | < 3–5s |
| Cost per query | Token cost tracking | Track & optimize |

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Azure free credit runs out mid-project | Set budget alerts early; use GPT-4o-mini + small corpus during dev; scale up only for final demo |
| Scope creep (adding too many features) | Stick to weekly deliverables; treat "nice-to-haves" (multi-modal, agentic actions) as future work, not this project |
| Medical domain data licensing issues | Use clearly public/open datasets (WHO guidelines, open PubMed abstracts) — avoid anything requiring institutional access |
| Eval framework complexity stalls progress | Start with 3–4 core RAGAS metrics; expand only if time allows |
| CI/CD setup eats too much time in Week 4 | Keep IaC minimal (core resources only); don't over-engineer staging/prod split if time-constrained |

---

## 7. Portfolio & CV Output

By the end of this project, you should have:

1. **GitHub repo** — well-documented README, architecture diagram, setup instructions
2. **Live demo link** — deployed on Azure Container Apps
3. **Evaluation report** — quantified quality metrics, methodology write-up
4. **CV bullet point**, e.g.:
   > *"Designed and deployed a production-grade RAG system on Azure (Azure OpenAI + Azure AI Search) with automated evaluation (RAGAS), observability (Application Insights), and CI/CD-gated deployment (GitHub Actions), achieving >0.85 faithfulness score on a curated clinical Q&A benchmark."*
5. **LinkedIn post** — short write-up on the build process, architecture decisions, and eval results (good for building the freelance/consulting brand mentioned separately, without mixing project scopes)
6. **Interview talking points** — chunking strategy trade-offs, hybrid search rationale, eval methodology, monitoring/alerting design

---

## 8. Open Decisions (fill in as you go)

- [ ] Final document corpus source: _______________
- [ ] Chunking strategy chosen: _______________ (justify with eval data)
- [ ] Open-source tracing tool (if used instead of/alongside Azure-native): _______________
- [ ] IaC tool: Bicep / Terraform (circle one)
- [ ] Staging environment: yes / no

---

*This blueprint is a living document — update checkboxes and open decisions as the project progresses.*
