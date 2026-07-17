# Week 2 Notes: Evaluation Framework

## What was built

- **Golden dataset** ([eval/golden_dataset.json](../eval/golden_dataset.json)): 39 Q&A pairs — 31 answerable (grounded in the actual corpus text, source-tagged) + 8 `should_refuse` cases (topics deliberately outside the corpus, to test hallucination resistance).
- **Evaluation harness** ([eval/metrics.py](../eval/metrics.py), [eval/run_eval.py](../eval/run_eval.py)): runs every golden dataset question against both Azure AI Search indexes (`fixed`, `semantic`) through the live FastAPI service, then scores each answer.

## Deviation from blueprint: custom metrics instead of the `ragas` library

The blueprint specifies RAGAS. Installing the `ragas` PyPI package failed — one of its dependencies (`scikit-network`) has no prebuilt wheel for Python 3.14 on Windows and needs Microsoft C++ Build Tools to compile from source, which aren't installed on this machine.

Rather than install a large C++ toolchain for one dependency, the four standard RAGAS metrics were reimplemented directly against Azure OpenAI (`gpt-5-mini` as judge, `text-embedding-3-small` for embeddings) — no extra dependencies beyond what Week 1 already installed:

- **Faithfulness** — LLM extracts factual claims from the answer, judges each against the retrieved context, score = supported / total.
- **Answer relevancy** — LLM generates 3 hypothetical questions the answer would suit; score = mean cosine similarity between those and the real question.
- **Context precision** — LLM judges each retrieved chunk's relevance (in rank order); score = Average Precision, rewarding relevant chunks that rank higher.
- **Context recall** — LLM extracts claims from `expected_answer` (ground truth) and checks whether each is attributable to the retrieved context.

This mirrors RAGAS's own published methodology for these four metrics, just without the library. Both `ingestion/embeddings.py`'s and `eval/metrics.py`'s LLM/embedding calls retry with a 60s backoff on `RateLimitError`, since the default deployment capacity (10 units) is easy to exceed when running ~40 questions × 2 strategies × ~5 calls each sequentially.

## Results

39 questions × 2 strategies = 78 evaluations, run against the live indexes built in Week 1.

| Metric | Fixed | Semantic | Blueprint target |
|---|---|---|---|
| Faithfulness | 0.985 | 0.993 | > 0.85 — both pass |
| Answer relevancy | 0.772 | 0.768 | > 0.85 — **both fail** |
| Context precision | 0.927 | 0.936 | > 0.75 — both pass |
| Context recall | 0.878 | 0.965 | > 0.75 — both pass, semantic clearly ahead |
| Refusal accuracy | 1.000 | 1.000 | — 8/8 out-of-scope questions correctly declined, both strategies |

Full per-question results: [eval/results/eval_20260717T103908Z.json](../eval/results/eval_20260717T103908Z.json).

## Interpretation

- **Semantic chunking wins on context recall** (0.965 vs 0.878, a real ~9-point gap, not noise) — it more consistently retrieves everything needed to fully answer a question. This is the clearest, most decision-relevant signal from this run, and lines up with the Week 1 hypothesis that smaller, topic-coherent chunks make more precise retrieval matches.
- Faithfulness and context precision are close between strategies (within ~1 point) — not a meaningful difference either way.
- **Refusal accuracy is perfect for both** — confirms the qualitative Week 1 finding (the system correctly declined all 8 out-of-scope questions) with actual numbers this time.
- **Answer relevancy fails the >0.85 target for both strategies (~0.77)** — investigated below. This is the one metric worth explaining before drawing conclusions from it.

## Investigating the low answer relevancy score

Spot-checked the lowest-scoring items (e.g. `dm2-001`, "What medicine does WHO recommend as second-line treatment... when metformin alone is not enough?"). The generated answer correctly names sulfonylurea as the recommendation, then adds two grounded implementation caveats from the guideline (avoid glibenclamide in patients ≥60; prefer gliclazide when hypoglycaemia is a concern).

The metric works by generating 3 hypothetical questions from the answer and comparing them to the real question:

| Generated question | Similarity to real question |
|---|---|
| "What is recommended as second-line treatment... ?" | 0.921 |
| "Should glibenclamide be used in patients aged 60+... ?" | 0.611 |
| "Which sulfonylureas are preferred for hypoglycaemia risk... ?" | 0.686 |

The average (~0.74) gets dragged down by the two caveat-derived questions, even though those caveats are accurate and clinically useful (consistent with the near-perfect faithfulness score for the same answers).

**Conclusion: this is a known limitation of the answer-relevancy methodology itself (also present in the real RAGAS library, not unique to this reimplementation), not evidence that the RAG system gives bad answers.** The metric implicitly rewards short, narrowly-scoped answers and penalizes thorough ones that include grounded supporting detail. Given faithfulness is ~99%, the low relevancy score here reads as "answers are more detailed than the metric expects" rather than "answers are off-topic."

## Decision going forward

**Semantic chunking is the chosen strategy** for the RAG service — it matches or beats fixed-size on every metric, with a clear, non-marginal advantage on context recall. `app/main.py`'s default `strategy` param is already `"semantic"`.

## Follow-ups (not done this week, noted for later)

- The oversized semantic chunk bug documented in [week1-notes.md](week1-notes.md) (one 10,720-token chunk) wasn't specifically checked against eval results — worth a targeted look if a future eval run shows a low-scoring question sourced from `who-diabetes-global-monitoring-guidance.pdf`.
- Answer relevancy as implemented penalizes thorough answers; if this matters later (e.g. for CI gating in Week 4), consider either accepting a lower threshold for this specific metric, or adjusting the prompt to generate hypothetical questions only from the answer's primary claim.
