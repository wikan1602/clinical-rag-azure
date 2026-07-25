import logging

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

from app.config import Settings

logger = logging.getLogger("rag.retrieval")


def embed_query(client: AzureOpenAI, deployment: str, text: str) -> list[float]:
    response = client.embeddings.create(model=deployment, input=[text])
    return response.data[0].embedding


def _get_search_client(settings: Settings, index_name: str) -> SearchClient:
    return SearchClient(
        endpoint=settings.search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(settings.search_api_key),
    )


def _topic_filter(topic: str | None) -> str | None:
    return f"topic eq '{topic}'" if topic else None


def _log_retrieved_chunks(question: str, index_name: str, route: str, chunks: list[dict]) -> None:
    logger.info(
        "retrieved_chunks",
        extra={
            "question": question,
            "index_name": index_name,
            "route": route,
            "chunk_ids": [c["id"] for c in chunks],
            "chunk_sources": [c["source"] for c in chunks],
            "num_chunks": len(chunks),
        },
    )


def retrieve_chunks(
    settings: Settings,
    openai_client: AzureOpenAI,
    question: str,
    index_name: str,
    top_k: int = 5,
) -> list[dict]:
    vector = embed_query(openai_client, settings.embedding_deployment, question)
    search_client = _get_search_client(settings, index_name)

    results = search_client.search(
        search_text=question,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="content_vector")],
        top=top_k,
        select=["id", "content", "source", "chunk_index"],
    )

    chunks = [
        {
            "id": r["id"],
            "content": r["content"],
            "source": r["source"],
            "chunk_index": r["chunk_index"],
            "score": r["@search.score"],
        }
        for r in results
    ]

    _log_retrieved_chunks(question, index_name, "semantic", chunks)
    return chunks


def retrieve_temporal(
    settings: Settings,
    openai_client: AzureOpenAI,
    question: str,
    index_name: str,
    topic: str | None,
    top_k: int = 3,
) -> list[dict]:
    search_client = _get_search_client(settings, index_name)

    # Stage 1: find the most recent published_year among documents matching the topic filter.
    latest = list(
        search_client.search(
            search_text="*",
            filter=_topic_filter(topic),
            order_by=["published_year desc"],
            top=1,
            select=["published_year"],
        )
    )
    if not latest:
        _log_retrieved_chunks(question, index_name, "temporal", [])
        return []
    latest_year = latest[0]["published_year"]

    # Stage 2: rank chunks WITHIN that most-recent year by actual relevance to the question,
    # instead of just returning the document's first chunks (which are often cover/license pages).
    year_filter = f"published_year eq {latest_year}"
    combined_filter = f"{year_filter} and {_topic_filter(topic)}" if topic else year_filter

    vector = embed_query(openai_client, settings.embedding_deployment, question)
    results = search_client.search(
        search_text=question,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="content_vector")],
        filter=combined_filter,
        top=top_k,
        select=["id", "content", "source", "chunk_index", "published_year"],
    )

    chunks = [
        {
            "id": r["id"],
            "content": r["content"],
            "source": r["source"],
            "chunk_index": r["chunk_index"],
            "published_year": r["published_year"],
            "score": r["@search.score"],
        }
        for r in results
    ]

    _log_retrieved_chunks(question, index_name, "temporal", chunks)
    return chunks


def retrieve_aggregate(
    settings: Settings,
    openai_client: AzureOpenAI,
    question: str,
    index_name: str,
    topic: str | None,
    token_budget: int = 6000,
) -> dict:
    vector = embed_query(openai_client, settings.embedding_deployment, question)
    search_client = _get_search_client(settings, index_name)

    results = search_client.search(
        search_text=question,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=1000, fields="content_vector")],
        filter=_topic_filter(topic),
        top=1000,
        include_total_count=True,
        select=["id", "content", "source", "chunk_index", "token_count", "published_year"],
    )

    total_matching = results.get_count()
    chunks: list[dict] = []
    tokens_used = 0
    truncated = False

    for r in results:
        if tokens_used + r["token_count"] > token_budget:
            truncated = True
            break
        chunks.append(
            {
                "id": r["id"],
                "content": r["content"],
                "source": r["source"],
                "chunk_index": r["chunk_index"],
                "published_year": r["published_year"],
                "score": r["@search.score"],
            }
        )
        tokens_used += r["token_count"]

    logger.info(
        "retrieved_chunks",
        extra={
            "question": question,
            "index_name": index_name,
            "route": "aggregate",
            "chunk_ids": [c["id"] for c in chunks],
            "chunk_sources": [c["source"] for c in chunks],
            "num_chunks": len(chunks),
            "token_budget": token_budget,
            "tokens_used": tokens_used,
            "truncated": truncated,
            "total_matching": total_matching,
        },
    )
    return {"chunks": chunks, "truncated": truncated, "total_matching": total_matching}
