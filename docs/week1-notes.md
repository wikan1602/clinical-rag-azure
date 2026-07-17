# Week 1 Notes: Chunking Strategy Comparison

## Corpus

7 public WHO clinical guideline PDFs (hypertension, diabetes, cardiovascular risk — see [data/SOURCES.md](../data/SOURCES.md)), ~12 MB total.

## Method

Two chunking strategies were implemented and run over the same corpus ([ingestion/chunking.py](../ingestion/chunking.py)):

- **Fixed-size**: 500 tokens per chunk, 50-token overlap, split purely on token count (`tiktoken`, `cl100k_base`), no regard for sentence or topic boundaries.
- **Semantic**: sentences are grouped together until the embedding-similarity between consecutive sentences drops below the 90th-percentile distance for that document (a topic shift), or a 700-token budget is hit.

Both were embedded (`text-embedding-3-small`) and indexed into separate Azure AI Search indexes (`clinical-guidelines-fixed`, `clinical-guidelines-semantic`) so they can be A/B compared later.

## Results

| Metric | Fixed-size | Semantic |
|---|---|---|
| Total chunks | 748 | 1342 |
| Avg tokens/chunk | 497.8 | 231.3 |
| Median tokens/chunk | 500 | 78 |
| Min / Max tokens | 55 / 500 | 1 / 10,720 |
| Stdev tokens | 24.9 | 401.6 |

## Observations

**Fixed-size is boring but predictable.** Every chunk except the last one per document is ~500 tokens, tightly clustered (stdev 24.9). Retrieval spot-checks (diabetes second-line medicine question) returned coherent, complete passages — but chunk boundaries sometimes cut mid-recommendation, splitting a WHO recommendation from its supporting rationale.

**Semantic produced ~1.8x more chunks, with much more variance** — and this variance is a bug, not just a feature. The median semantic chunk (78 tokens) is small — the chunker is aggressively breaking on topic shifts, often producing short, focused chunks (e.g. a single recommendation statement). Retrieval spot-checks (hypertension threshold question) returned tightly-scoped chunks that read like complete, self-contained answers.

However, the max chunk size (10,720 tokens, in `who-diabetes-global-monitoring-guidance.pdf`) reveals a real limitation: the sentence splitter (`ingestion/chunking.py:split_sentences`, a regex on `.!?`) breaks down on non-prose PDF content — in this case, an annex listing database search strategies with no sentence-ending punctuation across a huge block of text. That entire block became one "sentence" and thus one oversized chunk, bypassing the 700-token budget entirely (the budget check only fires *between* sentences, not *within* one). This also caused the `BadRequestError` (max embedding input length) hit during the first ingestion run, worked around by truncating text sent to the embedding API — but the full oversized text still ended up in the search index as a single (probably low-value) chunk.

## Known limitation / Week 2 follow-up

The semantic chunker needs a fallback: if a single sentence-unit exceeds the token budget, sub-split it (e.g. by fixed-size fallback) instead of emitting it whole. Worth checking how many chunks besides the one found are affected, and whether tiny (<10 token) chunks should be merged into neighbors rather than kept standalone.

## What Week 1 can't answer yet

Chunk-count and token-distribution stats, plus a handful of manual spot-checks, are not a substitute for a real evaluation. Both strategies produced plausible, well-cited answers in manual testing (including correctly refusing an out-of-scope chemotherapy-dosage question). Which strategy actually retrieves more relevant context and produces more faithful answers — the real question — needs the RAGAS faithfulness/relevancy/precision/recall metrics against a golden Q&A dataset, planned for Week 2 per the blueprint.

## Deviations from the original blueprint

- **Chat model**: blueprint specifies GPT-4o-mini; that model (and gpt-4.1-mini) was closed for new deployments in this subscription at build time. Using `gpt-5-mini` instead. See [CLAUDE.md](../CLAUDE.md).
- **Azure AI Search tier**: Free tier (no semantic ranker) chosen over Basic to avoid the ~$75/month cost during early experimentation. Hybrid search (vector + keyword) works on Free tier; semantic ranker can be added later by upgrading.
- **Two separate indexes** instead of one, tagged by strategy — chosen so fixed vs. semantic can be queried and evaluated independently in Week 2 without needing a `strategy` filter on every query.
