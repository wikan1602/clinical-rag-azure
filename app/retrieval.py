from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

from app.config import Settings


def embed_query(client: AzureOpenAI, deployment: str, text: str) -> list[float]:
    response = client.embeddings.create(model=deployment, input=[text])
    return response.data[0].embedding


def retrieve_chunks(
    settings: Settings,
    openai_client: AzureOpenAI,
    question: str,
    index_name: str,
    top_k: int = 5,
) -> list[dict]:
    vector = embed_query(openai_client, settings.embedding_deployment, question)

    search_client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(settings.search_api_key),
    )

    results = search_client.search(
        search_text=question,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="content_vector")],
        top=top_k,
        select=["id", "content", "source", "chunk_index"],
    )

    return [
        {
            "id": r["id"],
            "content": r["content"],
            "source": r["source"],
            "chunk_index": r["chunk_index"],
            "score": r["@search.score"],
        }
        for r in results
    ]
