import json
import time

import numpy as np
from openai import APIConnectionError, AzureOpenAI, RateLimitError

from ingestion.embeddings import embed_texts

REFUSAL_PHRASES = [
    "i don't know",
    "i do not know",
    "don't know",
    "not covered",
    "no information",
    "cannot find",
    "can't find",
    "not contain",
    "does not contain",
    "not enough information",
    "cannot answer",
    "can't answer",
    "i cannot",
    "unable to answer",
    "not available in",
    "not addressed",
]


def _judge_json(client: AzureOpenAI, deployment: str, prompt: str, max_retries: int = 5) -> dict | list:
    response = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a strict evaluation assistant. Respond with valid JSON only, no other text."},
                    {"role": "user", "content": prompt},
                ],
            )
            break
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            print(f"    Rate limited, waiting 60s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(60)
        except APIConnectionError:
            if attempt == max_retries - 1:
                raise
            print(f"    Connection error, waiting 10s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(10)

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def faithfulness(client: AzureOpenAI, deployment: str, question: str, answer: str, contexts: list[str]) -> dict:
    context_block = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = (
        f"Question: {question}\n\nAnswer to evaluate: {answer}\n\nContext excerpts:\n{context_block}\n\n"
        "Break the answer into individual factual claims. For each claim, decide if it is directly "
        "supported by the context excerpts above (true) or not supported/not present in the context (false). "
        'Respond with JSON: {"claims": [{"claim": "...", "supported": true|false}, ...]}'
    )
    result = _judge_json(client, deployment, prompt)
    claims = result.get("claims", [])
    if not claims:
        return {"score": None, "claims": []}
    score = sum(1 for c in claims if c.get("supported")) / len(claims)
    return {"score": score, "claims": claims}


def answer_relevancy(client: AzureOpenAI, deployment: str, embedding_deployment: str, question: str, answer: str) -> dict:
    prompt = (
        f"Answer: {answer}\n\n"
        "Generate 3 different questions that this answer would be a good, direct response to. "
        'Respond with JSON: {"questions": ["...", "...", "..."]}'
    )
    result = _judge_json(client, deployment, prompt)
    generated_questions = result.get("questions", [])
    if not generated_questions:
        return {"score": None, "generated_questions": []}

    vectors = embed_texts([question] + generated_questions)
    q_vec = np.array(vectors[0])
    gen_vecs = np.array(vectors[1:])
    q_norm = q_vec / np.linalg.norm(q_vec)
    gen_norms = gen_vecs / np.linalg.norm(gen_vecs, axis=1, keepdims=True)
    similarities = gen_norms @ q_norm
    return {"score": float(np.mean(similarities)), "generated_questions": generated_questions}


def context_precision(client: AzureOpenAI, deployment: str, question: str, contexts: list[str]) -> dict:
    if not contexts:
        return {"score": None, "relevance": []}
    context_block = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = (
        f"Question: {question}\n\nRetrieved context excerpts (in retrieval rank order):\n{context_block}\n\n"
        "For each excerpt, decide if it is relevant to answering the question. "
        'Respond with JSON: {"relevance": [true|false, ...]} with one entry per excerpt, in the same order.'
    )
    result = _judge_json(client, deployment, prompt)
    relevance = result.get("relevance", [])
    if not relevance:
        return {"score": None, "relevance": []}

    hits, sum_precision_at_k = 0, 0.0
    for k, is_relevant in enumerate(relevance, start=1):
        if is_relevant:
            hits += 1
            sum_precision_at_k += hits / k
    score = sum_precision_at_k / hits if hits > 0 else 0.0
    return {"score": score, "relevance": relevance}


def context_recall(client: AzureOpenAI, deployment: str, expected_answer: str, contexts: list[str]) -> dict:
    context_block = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = (
        f"Reference answer (ground truth): {expected_answer}\n\nRetrieved context excerpts:\n{context_block}\n\n"
        "Break the reference answer into individual factual claims. For each claim, decide if it can be "
        "attributed to (found or supported in) the retrieved context excerpts above. "
        'Respond with JSON: {"claims": [{"claim": "...", "attributed": true|false}, ...]}'
    )
    result = _judge_json(client, deployment, prompt)
    claims = result.get("claims", [])
    if not claims:
        return {"score": None, "claims": []}
    score = sum(1 for c in claims if c.get("attributed")) / len(claims)
    return {"score": score, "claims": claims}


def detect_refusal(answer: str) -> bool:
    lowered = answer.lower().replace("’", "'").replace("‘", "'")
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)
