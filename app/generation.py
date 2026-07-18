import logging

from openai import AzureOpenAI

logger = logging.getLogger("rag.generation")

SYSTEM_PROMPT = (
    "You are a clinical knowledge assistant. Answer the user's question ONLY using the "
    "provided context excerpts from WHO clinical guidelines. If the context does not "
    "contain enough information to answer confidently, say you don't know rather than "
    "guessing. Cite which source excerpt(s) you used, e.g. [1], [2]."
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[{i}] Source: {c['source']}\n{c['content']}" for i, c in enumerate(chunks, start=1))
    return f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer using only the context above."


def generate_answer(client: AzureOpenAI, deployment: str, question: str, chunks: list[dict]) -> str:
    prompt = build_prompt(question, chunks)
    logger.info("generation_prompt", extra={"question": question, "prompt": prompt})

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    answer = response.choices[0].message.content

    logger.info(
        "generation_answer",
        extra={
            "question": question,
            "answer": answer,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
    )
    return answer
