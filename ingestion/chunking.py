import re
from typing import Callable

import numpy as np
import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")

EmbedFn = Callable[[list[str]], list[list[float]]]


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def fixed_size_chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    tokens = _ENCODING.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunks.append(_ENCODING.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end - overlap
    return chunks


def semantic_chunk(
    text: str,
    embed_fn: EmbedFn,
    breakpoint_percentile: int = 90,
    max_chunk_tokens: int = 700,
) -> list[str]:
    """Groups sentences into chunks, breaking where embedding similarity between
    consecutive sentences drops sharply (semantic shift) or the token budget is hit."""
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return sentences

    vectors = np.array(embed_fn(sentences))
    norms = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    similarities = np.sum(norms[:-1] * norms[1:], axis=1)
    distances = 1 - similarities
    threshold = np.percentile(distances, breakpoint_percentile)

    chunks = []
    current = [sentences[0]]
    current_tokens = count_tokens(sentences[0])
    for i, dist in enumerate(distances):
        next_sentence = sentences[i + 1]
        next_tokens = count_tokens(next_sentence)
        if dist >= threshold or current_tokens + next_tokens > max_chunk_tokens:
            chunks.append(" ".join(current))
            current = [next_sentence]
            current_tokens = next_tokens
        else:
            current.append(next_sentence)
            current_tokens += next_tokens
    chunks.append(" ".join(current))
    return chunks
