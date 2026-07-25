import json
import logging
from dataclasses import dataclass
from pathlib import Path

from openai import AzureOpenAI

logger = logging.getLogger("rag.query_router")

ROUTES = ("semantic", "temporal", "aggregate")

SYSTEM_PROMPT = (
    "You classify a user's question about WHO clinical guidelines into a retrieval route. "
    "Default to 'semantic' for ordinary factual questions. "
    "Use 'temporal' only when the question asks for the latest/most recent/newest guidance "
    "(e.g. contains words like 'terbaru', 'terkini', 'latest', 'most recent', 'newest'). "
    "Use 'aggregate' only when the question asks to summarize/list all recommendations across "
    "a whole topic (e.g. contains words like 'semua', 'ringkasan', 'summarize all', 'every'). "
    "Set topic only if the question is clearly scoped to one known topic, otherwise leave it null."
)


@dataclass
class RouterDecision:
    route: str
    topic: str | None


def load_known_topics(path: Path = Path("data/document_metadata.json")) -> list[str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return manifest["topics"]


def _build_router_tool(known_topics: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": "classify_query",
            "description": "Classify the retrieval route and optional topic filter for a question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": list(ROUTES)},
                    "topic": {"type": ["string", "null"], "enum": known_topics + [None]},
                },
                "required": ["route", "topic"],
            },
        },
    }


def classify_query(
    client: AzureOpenAI,
    deployment: str,
    question: str,
    known_topics: list[str],
) -> RouterDecision:
    tool = _build_router_tool(known_topics)
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "classify_query"}},
        )
        arguments = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        route = arguments["route"]
        topic = arguments.get("topic")

        if route not in ROUTES:
            raise ValueError(f"invalid route: {route}")
        if topic is not None and topic not in known_topics:
            raise ValueError(f"invalid topic: {topic}")

        decision = RouterDecision(route=route, topic=topic)
        logger.info(
            "router_decision",
            extra={"question": question, "route": decision.route, "topic": decision.topic},
        )
        return decision

    except Exception as e:
        logger.info(
            "router_fallback",
            extra={"question": question, "reason": str(e)},
        )
        return RouterDecision(route="semantic", topic=None)
