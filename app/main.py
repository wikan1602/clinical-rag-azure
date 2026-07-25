import logging

from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AzureOpenAI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from app.config import get_settings
from app.generation import generate_answer
from app.query_router import ROUTES, classify_query, load_known_topics
from app.retrieval import retrieve_aggregate, retrieve_chunks, retrieve_temporal

load_dotenv()
configure_azure_monitor()
logging.getLogger("rag").setLevel(logging.INFO)

app = FastAPI(title="Clinical Knowledge Assistant")
FastAPIInstrumentor().instrument_app(app)
settings = get_settings()
known_topics = load_known_topics()
openai_client = AzureOpenAI(
    azure_endpoint=settings.openai_endpoint,
    api_key=settings.openai_api_key,
    api_version=settings.openai_api_version,
)


class QueryRequest(BaseModel):
    question: str
    strategy: str = "semantic"  # "fixed" or "semantic" chunking index
    top_k: int = 5
    route: str | None = None  # None = auto-routing; set to override (eval/debug)
    topic: str | None = None  # only used when route is overridden manually


class RetrievedChunk(BaseModel):
    id: str
    content: str
    source: str
    chunk_index: int
    score: float | None = None
    published_year: int | None = None


class QueryResponse(BaseModel):
    answer: str
    chunks: list[RetrievedChunk]
    route: str
    topic: str | None
    truncated: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    index_name = settings.search_index_fixed if request.strategy == "fixed" else settings.search_index_semantic

    if request.route is not None:
        if request.route not in ROUTES:
            raise HTTPException(400, f"invalid route: {request.route}")
        if request.topic is not None and request.topic not in known_topics:
            raise HTTPException(400, f"unknown topic: {request.topic}")
        route, topic = request.route, request.topic
    else:
        decision = classify_query(openai_client, settings.chat_deployment, request.question, known_topics)
        route, topic = decision.route, decision.topic

    truncated = False
    if route == "temporal":
        chunks = retrieve_temporal(
            settings, openai_client, request.question, index_name, topic, top_k=min(request.top_k, 3)
        )
    elif route == "aggregate":
        agg = retrieve_aggregate(settings, openai_client, request.question, index_name, topic)
        chunks, truncated = agg["chunks"], agg["truncated"]
    else:
        chunks = retrieve_chunks(settings, openai_client, request.question, index_name, top_k=request.top_k)

    answer = generate_answer(openai_client, settings.chat_deployment, request.question, chunks, route=route)
    return QueryResponse(answer=answer, chunks=chunks, route=route, topic=topic, truncated=truncated)
