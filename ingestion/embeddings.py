import os
import time

import tiktoken
from openai import AzureOpenAI, RateLimitError

_ENCODING = tiktoken.get_encoding("cl100k_base")
_MAX_INPUT_TOKENS = 8000


def _truncate_for_embedding(text: str) -> str:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= _MAX_INPUT_TOKENS:
        return text
    return _ENCODING.decode(tokens[:_MAX_INPUT_TOKENS])


def get_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )


def _embed_batch_with_retry(client: AzureOpenAI, deployment: str, batch: list[str], max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            return client.embeddings.create(model=deployment, input=batch)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait_seconds = 60
            print(f"    Rate limited, waiting {wait_seconds}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait_seconds)


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    client = get_client()
    deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [_truncate_for_embedding(t) for t in texts[i : i + batch_size]]
        response = _embed_batch_with_retry(client, deployment, batch)
        embeddings.extend(item.embedding for item in response.data)
        time.sleep(1)
    return embeddings
