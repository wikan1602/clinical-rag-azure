# Week 3 Notes: Monitoring & Observability

## What was built

**Resources** (all in `rg-clinical-rag`, region `eastus`):
- `appinsights-clinical-rag` — Application Insights (workspace-based)
- `ag-clinical-rag` — Action Group, emails `wikanpriambudi@gmail.com` on alert
- `alert-high-latency` — metric alert, fires if avg request duration > 5000ms over a 5-minute window
- `alert-low-faithfulness` — scheduled query alert, fires if the latest `eval_summary` trace shows faithfulness < 0.85
- Workbook **"Clinical RAG Monitoring"** — 3 charts: latency trend, token usage trend (cost proxy), eval score trend table

**Code changes:**
- `app/main.py` — `configure_azure_monitor()` (package: `azure-monitor-opentelemetry`) wired up at startup, reading `APPLICATIONINSIGHTS_CONNECTION_STRING` from `.env`. `FastAPIInstrumentor().instrument_app(app)` added explicitly (see bug note below).
- `app/retrieval.py` — logs a `retrieved_chunks` trace per request: question, index name, chunk ids/sources, count.
- `app/generation.py` — logs `generation_prompt` (full prompt sent to the model) and `generation_answer` (answer + prompt/completion token counts) traces per request.
- `eval/run_eval.py` — logs an `eval_summary` trace per strategy after each eval run (the same summary dict that gets printed and saved to `eval/results/`), so eval history is queryable in Application Insights over time, not just in local JSON snapshots.

This satisfies the blueprint's "full trace logging: query → retrieved chunks → prompt → final answer" requirement — all four are now one KQL query away (`traces | where operation_Id == "..."`  ties them together per request).

## Bug found: FastAPI isn't auto-instrumented by `configure_azure_monitor()`

Expected `configure_azure_monitor()` alone to auto-instrument FastAPI (it does auto-instrument some libraries based on what's installed). It didn't — verified by querying Application Insights right after a test request: custom `traces` arrived, but the `requests` table (auto request telemetry: latency, status code) had zero rows for 15 minutes.

Fix: explicit `FastAPIInstrumentor().instrument_app(app)` call after the `FastAPI()` app object is constructed (not before — the instrumentor wraps a specific app instance, so it must run after `app = FastAPI(...)`). Verified again after the fix: `requests` table showed the test request (`POST /query`, ~9.4s duration, 200, success). `opentelemetry-instrumentation-fastapi` was already present as a transitive dependency of `azure-monitor-opentelemetry`, so no extra install was needed — just the missing wiring.

## CLI quirks hit while setting up alerts

- `az monitor scheduled-query create --condition` doesn't take a plain comparison expression. It needs a named placeholder that's defined separately: `--condition "count 'Placeholder_1' > 0"` paired with `--condition-query Placeholder_1="<KQL query>"`. Passing the KQL query directly in `--condition-query` without matching the placeholder name in `--condition` fails with a parser error pointing at the comparison operator, which is a confusing error for what's actually a missing-placeholder problem.
- `--action-groups` for scheduled query alerts needs the action group's **full resource ID**, not just its name — unlike `az monitor metrics alert create --action`, which accepts the short name directly. Same Azure surface, inconsistent CLI ergonomics between the two alert types.
- Both `microsoft.insights` and `microsoft.operationalinsights` resource providers needed registration on this subscription before Application Insights (workspace-based, which is now the default kind) would provision — `az monitor app-insights component create` auto-registered the first but not the second, failing with a `Conflict` error until `microsoft.operationalinsights` was registered manually and had a few minutes to propagate.

## Alert thresholds

Both thresholds were taken directly from the blueprint's own targets (§5 Evaluation Metrics Reference), not invented for this week:
- Latency: blueprint target is p95 < 3–5s. Alert set at avg > 5s over 5 minutes — a simpler avg-based check rather than true p95, since a p95 metric alert needs a bit more KQL than the CLI's `--condition` shorthand supports cleanly. Worth tightening to an actual p95 query later if this matters for CI gating in Week 4.
- Faithfulness: blueprint target is > 0.85. Alert fires below that same line.

## Verification

Confirmed end-to-end via `az monitor app-insights query` against the live resource (not just "the code looks right"):
- `retrieved_chunks`, `generation_prompt`, `generation_answer` traces all arrived with correct structured fields (question, chunk ids, full prompt, answer, token counts).
- `requests` table populated after the FastAPI instrumentation fix (confirmed count and duration for a real test request).
- Workbook renders in the portal (Application Insights → Workbooks → "Clinical RAG Monitoring") with all 3 charts.

Not yet verified: whether the alerts actually *fire* correctly (would need to either wait for a real latency spike / eval regression, or temporarily lower a threshold to force a test trigger — not done this week to avoid noisy test emails).
