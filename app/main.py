import logging

from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import AzureOpenAI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from app.config import get_settings
from app.generation import generate_answer
from app.retrieval import retrieve_chunks

load_dotenv()
configure_azure_monitor()
logging.getLogger("rag").setLevel(logging.INFO)

app = FastAPI(title="Clinical Knowledge Assistant")
FastAPIInstrumentor().instrument_app(app)
settings = get_settings()
openai_client = AzureOpenAI(
    azure_endpoint=settings.openai_endpoint,
    api_key=settings.openai_api_key,
    api_version=settings.openai_api_version,
)


class QueryRequest(BaseModel):
    question: str
    strategy: str = "semantic"  # "fixed" or "semantic"
    top_k: int = 5


class RetrievedChunk(BaseModel):
    id: str
    content: str
    source: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    chunks: list[RetrievedChunk]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    index_name = settings.search_index_fixed if request.strategy == "fixed" else settings.search_index_semantic
    chunks = retrieve_chunks(settings, openai_client, request.question, index_name, top_k=request.top_k)
    answer = generate_answer(openai_client, settings.chat_deployment, request.question, chunks)
    return QueryResponse(answer=answer, chunks=chunks)
