import logging
import time

from openai import APIConnectionError, AzureOpenAI, RateLimitError

logger = logging.getLogger("rag.generation")

SYSTEM_PROMPT = (
    "You are a clinical knowledge assistant. Answer the user's question ONLY using the "
    "provided context excerpts from WHO clinical guidelines. If the context does not "
    "contain enough information to answer confidently, say you don't know rather than "
    "guessing. Cite which source excerpt(s) you used, e.g. [1], [2]."
)

AGGREGATE_SYSTEM_PROMPT = (
    "You are a clinical knowledge assistant. The provided context excerpts may span multiple "
    "WHO guideline documents on the same topic. Synthesize a comprehensive answer that draws "
    "on ALL relevant excerpts, not just the first one — do not favor one source document over "
    "the others unless they genuinely disagree. Answer the user's question ONLY using the "
    "provided context. If the context does not contain enough information to answer confidently, "
    "say you don't know rather than guessing. Cite which source excerpt(s) you used, e.g. [1], [2]."
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[{i}] Source: {c['source']}\n{c['content']}" for i, c in enumerate(chunks, start=1))
    return f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer using only the context above."


def generate_answer(
    client: AzureOpenAI,
    deployment: str,
    question: str,
    chunks: list[dict],
    route: str = "semantic",
    max_retries: int = 5,
) -> str:
    prompt = build_prompt(question, chunks)
    logger.info("generation_prompt", extra={"question": question, "prompt": prompt, "route": route})

    system_prompt = AGGREGATE_SYSTEM_PROMPT if route == "aggregate" else SYSTEM_PROMPT
    response = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            break
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            logger.warning("openai_retry", extra={"reason": "rate_limited", "attempt": attempt + 1, "wait_seconds": 60})
            time.sleep(60)
        except APIConnectionError:
            if attempt == max_retries - 1:
                raise
            logger.warning("openai_retry", extra={"reason": "connection_error", "attempt": attempt + 1, "wait_seconds": 10})
            time.sleep(10)
    answer = response.choices[0].message.content

    logger.info(
        "generation_answer",
        extra={
            "question": question,
            "answer": answer,
            "route": route,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
    )
    return answer
