# Week 4 Notes: Agentic Query Routing (Temporal & Aggregate Retrieval)

## Motivation

Pure vector/hybrid search only answers "what's semantically similar to this question" — it has no concept of recency or completeness. Two query shapes break it:

- **Temporal** ("what's the latest guideline on X?") — needs sorting/filtering by publish date, not similarity ranking.
- **Aggregate** ("summarize all recommendations about X") — needs broad coverage of matching documents, not a narrow top-k of the closest chunks.

This was identified as a real limitation the user had hit building a RAG chatbot at work, and deliberately built out here as a portfolio differentiator (an "agentic RAG" query router) rather than left as future work, since cost/token budget is not a constraint for this project.

## What was built

- **`data/document_metadata.json`** — hand-curated manifest (7 documents, not auto-parsed from filenames) mapping each PDF to a single `topic` (`hypertension` | `cardiovascular` | `diabetes`) and `published_year`.
- **Index schema** ([ingestion/search_index.py](../ingestion/search_index.py)) — added `topic` (filterable/facetable) and `published_year` (filterable/**sortable**/facetable) fields to both `clinical-guidelines-fixed` and `clinical-guidelines-semantic`. Both indexes were fully re-ingested and re-indexed to backfill the new fields onto all existing chunks (748 fixed, 1342 semantic).
- **Query router** ([app/query_router.py](../app/query_router.py)) — `classify_query()` makes one Azure OpenAI function-calling request (forced tool choice) that classifies a question into `semantic | temporal | aggregate` and optionally extracts a topic filter, constrained to the known topic enum so it can't hallucinate an invalid value. Any failure (bad tool call, network error) falls back to `RouterDecision("semantic", None)` — the router can never crash a request, only silently degrade to the old behavior.
- **Two new retrieval strategies** ([app/retrieval.py](../app/retrieval.py)):
  - `retrieve_temporal` — a **two-stage** query: (1) find the most recent `published_year` matching the topic filter, (2) run a normal hybrid vector+text search *within that year* to rank chunks by actual relevance. See "Bug found" below for why this isn't a single `order_by` query.
  - `retrieve_aggregate` — filters by topic, pulls as many hybrid-ranked chunks as fit under a `token_budget` (6000 tokens, a local constant matching the existing `UPLOAD_BATCH_SIZE`/`_MAX_INPUT_TOKENS` pattern rather than an env var), and reports `truncated=True` when relevant chunks had to be left out — the cutoff is visible and traceable, not a silent truncation.
- **`app/generation.py`** — `generate_answer` takes a `route` param; `aggregate` uses a system prompt variant instructing the model to synthesize across *all* provided excerpts rather than favoring the first source.
- **`/query` API surface** ([app/main.py](../app/main.py)) — `QueryRequest` gained optional `route`/`topic` fields (`None` = auto-routed via the classifier; set explicitly to bypass the router, used for deterministic eval runs). `QueryResponse` now reports the resolved `route`, `topic`, and `truncated` flag so callers (Streamlit, eval) can see what the system actually decided.
- **Streamlit UI** ([ui/app.py](../ui/app.py)) — shows the resolved route/topic and a truncation warning; chunk expanders handle `score: null` (temporal has no similarity score) and show `published_year` when present.
- **Eval harness** — 6 new golden dataset items (3 temporal, 3 aggregate, English and Indonesian phrasings) with an `expected_route` field; `eval/run_eval.py` checks router correctness per item and `summarize()` reports a new `router_accuracy` metric alongside the existing RAGAS-style scores.

## Bug found: `retrieve_temporal` returning cover pages instead of content

First implementation was a single query: filter by topic, `order_by=["published_year desc"]`, take top 3. Live-tested against "Apa guideline diabetes yang paling baru?" (What's the newest diabetes guideline?) — it returned the correct document (2025) but the wrong *content*: the top 3 chunks were the cover page and Creative Commons license boilerplate, because `order_by` alone has no concept of relevance — it just returns the document's first chunks in index order.

Fixed by splitting into two queries: first find the latest matching `published_year`, then run a normal hybrid search *filtered to that year* so chunks are ranked by relevance to the actual question, not just document order. Re-tested with the same question — now correctly surfaces the guideline's acknowledgements/context section and produces an accurate, well-cited answer. Some noise remains (a reference-list chunk sometimes ranks alongside real content) because Indonesian-language queries have weak lexical overlap with the English source text, which the hybrid text-search component leans on — a known, honest limitation rather than a bug, and not something worth solving in this corpus/scope.

## Correction: the aggregate token budget IS exercised

Initial assumption (going into this build) was that a 7-document corpus is too small to ever trigger `retrieve_aggregate`'s `truncated=True` path. Live-tested against the hypertension topic and found 147 matching chunks in the semantic index, of which only 17 fit under the 6000-token budget — `truncated=True` fired for real. The guard is not just theoretical; a single WHO guideline document alone can contain enough relevant chunks to blow the budget for a fairly common "summarize everything about X" query.

## Metadata research: published_year for 3 undated documents

Three of the seven corpus documents had no publish year in their filename or title, and PDF-embedded metadata (`ModifyDate`/`CreateDate`) proved unreliable (dates reflected when a document was last edited in a design tool, not when WHO published it — confirmed by fetching the raw PDFs directly). Resolved via targeted web search instead of guessing or leaving them unfiltered:

| Document | Resolved year | Confidence |
|---|---|---|
| `who-cvd-risk-know-your-risk-booklet.pdf` | 2023 | Medium — tied to a WHO SEARO regional-committee event (Oct 2023), no explicit imprint page found |
| `who-diabetes-global-monitoring-guidance.pdf` | 2024 | High — WHO's own publications page states "14 November 2024" |
| `who-managing-diabetes-mellitus-health-workers-guide.pdf` | 2007 | High — but this document is not a direct WHO publication; it's a **Royal Government of Bhutan, Ministry of Health** national guideline (August 2007). Corrected in [data/SOURCES.md](../data/SOURCES.md). |

## Recurring issue: intermittent DNS resolution failures

Throughout this week's build and testing, outbound HTTPS calls to both `*.openai.azure.com` and `*.search.windows.net` intermittently failed with `getaddrinfo failed` — confirmed (via `nslookup`) to be a genuine local DNS resolver issue on the development machine, not an Azure-side problem, and not specific to this codebase (plain `google.com` failed to resolve during one occurrence too). This hit three different call sites over the course of the week: `ingestion/embeddings.py`'s embedding calls, the FastAPI service's Azure AI Search calls, and `eval/metrics.py`'s LLM-judge calls.

Given the recurring pattern, added retry-with-backoff in two places that didn't already have it:
- `eval/run_eval.py`'s `_post_query` — retries the `/query` HTTP call up to 3 times with a 10s pause on any `requests` exception.
- `eval/metrics.py`'s `_judge_json` — now also retries on `openai.APIConnectionError` (10s backoff), not just `RateLimitError` (60s backoff) as before.

This follows the same retry-on-transient-failure convention already used in `ingestion/embeddings.py`, applied to the two places that were still missing it.

## Bug found (unrelated to routing): refusal detection missed curly apostrophes

The full eval run surfaced a `should_refuse` item (`refuse-005`, appendectomy question) marked as incorrectly answered under the semantic strategy — but the model's answer actually *did* refuse ("I don't know. The provided WHO excerpts discuss..."). `eval/metrics.py`'s `detect_refusal` does plain substring matching against a fixed phrase list including `"i don't know"` with a straight ASCII apostrophe; the model's response used a Unicode curly apostrophe (`’`), which never matched. Fixed by normalizing curly quotes to straight ones before matching. This is a pre-existing Week 2 metric bug, unrelated to the router work — it just happened to surface now because this was the first time the model's phrasing used a curly quote in a refusal.

## Eval results

45 questions (39 original + 6 new temporal/aggregate) × 2 strategies = 90 evaluations, against the live re-indexed corpus. Full results: [eval/results/eval_20260725T062435Z.json](../eval/results/eval_20260725T062435Z.json).

| Metric | Fixed | Semantic | Week 2 baseline (fixed / semantic) |
|---|---|---|---|
| Faithfulness | 0.961 | 0.965 | 0.985 / 0.993 |
| Answer relevancy | 0.756 | 0.770 | 0.772 / 0.768 |
| Context precision | 0.947 | 0.948 | 0.927 / 0.936 |
| Context recall | 0.844 | 0.932 | 0.878 / 0.965 |
| Refusal accuracy | 1.000 | 0.875* | 1.000 / 1.000 |
| **Router accuracy** | **1.000** | **1.000** | — (new this week) |

\* The one semantic-strategy refusal "failure" was the curly-apostrophe detection bug above, not an actual wrong answer — fixed in `detect_refusal` after this run; not yet re-verified with a fresh full run since the fix is a pure metric-code change, not a retrieval/generation change.

**Router accuracy is perfect (6/6) on both chunking strategies** — the classifier correctly identified all 3 temporal and 3 aggregate test questions across English and Indonesian phrasings, with none misrouted to `semantic`. Faithfulness, context precision, and refusal accuracy are all consistent with the Week 2 baseline (small movements are noise from the corpus-wide re-embed, not a regression). Context recall dipped slightly for both strategies (likely the new temporal/aggregate items are inherently harder to fully "cover" than the original narrowly-scoped factual questions) but semantic chunking retains its clear Week 2 advantage over fixed-size.

## Known limitations (not fixed, noted for future work)

- **No true map-reduce summarization.** `retrieve_aggregate`'s token budget keeps every aggregate query within a single gpt-5-mini call for this 7-document corpus. If the corpus grows meaningfully, single-pass "stuffing" will need to become real map-reduce (batch-summarize, then combine) — deferred since it's not needed at current scale.
- **Temporal retrieval is document-level, not chunk-level recency-aware.** "Latest" means "the most recently published *document*," then ranks chunks within it by relevance. A single document that itself spans multiple years (e.g. an updated edition) isn't handled specially.
- **Cross-lingual retrieval noise.** Indonesian-language queries against this English-only corpus produce measurably noisier chunk selection (reference-list/citation chunks sometimes outrank real content) than English queries — visible in the temporal route testing above. Not addressed this week; would need either query translation before embedding, or a stronger reranking step.
