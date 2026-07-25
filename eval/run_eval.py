import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from openai import AzureOpenAI

from app.config import get_settings
from eval.metrics import answer_relevancy, context_precision, context_recall, detect_refusal, faithfulness

load_dotenv()
configure_azure_monitor()
logger = logging.getLogger("rag.eval")
logger.setLevel(logging.INFO)

API_URL = "http://127.0.0.1:8000"
GOLDEN_DATASET_PATH = Path("eval/golden_dataset.json")
RESULTS_DIR = Path("eval/results")
STRATEGIES = ["fixed", "semantic"]
QUERY_MAX_RETRIES = 3
QUERY_RETRY_SECONDS = 10


def _post_query(payload: dict) -> dict:
    last_error = None
    for attempt in range(QUERY_MAX_RETRIES):
        try:
            response = requests.post(f"{API_URL}/query", json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException,) as e:
            last_error = e
            print(f"    /query failed ({e}), retrying in {QUERY_RETRY_SECONDS}s...")
            time.sleep(QUERY_RETRY_SECONDS)
    raise last_error


def evaluate_item(client: AzureOpenAI, chat_deployment: str, embedding_deployment: str, item: dict, strategy: str) -> dict:
    data = _post_query({"question": item["question"], "strategy": strategy, "top_k": 5})
    answer = data["answer"]
    contexts = [c["content"] for c in data["chunks"]]

    result = {
        "id": item["id"],
        "question": item["question"],
        "type": item["type"],
        "category": item["category"],
        "strategy": strategy,
        "answer": answer,
        "num_contexts": len(contexts),
        "route": data["route"],
    }

    if "expected_route" in item:
        result["route_correct"] = data["route"] == item["expected_route"]
    if item["category"] != "out-of-scope" and item.get("expected_route") == "temporal":
        result["expected_source_present"] = item["source"] in {c["source"] for c in data["chunks"]}

    if item["type"] == "should_refuse":
        result["correctly_refused"] = detect_refusal(answer)
        return result

    result["faithfulness"] = faithfulness(client, chat_deployment, item["question"], answer, contexts)["score"]
    result["answer_relevancy"] = answer_relevancy(client, chat_deployment, embedding_deployment, item["question"], answer)["score"]
    result["context_precision"] = context_precision(client, chat_deployment, item["question"], contexts)["score"]
    result["context_recall"] = context_recall(client, chat_deployment, item["expected_answer"], contexts)["score"]
    return result


def summarize(results: list[dict], strategy: str) -> dict:
    strategy_results = [r for r in results if r["strategy"] == strategy]
    answerable = [r for r in strategy_results if r["type"] == "answerable"]
    refuse = [r for r in strategy_results if r["type"] == "should_refuse"]
    routed = [r for r in strategy_results if "route_correct" in r]

    def avg(key):
        values = [r[key] for r in answerable if r.get(key) is not None]
        return statistics.mean(values) if values else None

    return {
        "strategy": strategy,
        "n_answerable": len(answerable),
        "n_should_refuse": len(refuse),
        "faithfulness": avg("faithfulness"),
        "answer_relevancy": avg("answer_relevancy"),
        "context_precision": avg("context_precision"),
        "context_recall": avg("context_recall"),
        "refusal_accuracy": (sum(1 for r in refuse if r["correctly_refused"]) / len(refuse)) if refuse else None,
        "router_accuracy": (sum(1 for r in routed if r["route_correct"]) / len(routed)) if routed else None,
    }


def main() -> None:
    settings = get_settings()
    client = AzureOpenAI(
        azure_endpoint=settings.openai_endpoint,
        api_key=settings.openai_api_key,
        api_version=settings.openai_api_version,
    )

    golden_dataset = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))

    results = []
    for strategy in STRATEGIES:
        print(f"\n=== Evaluating strategy: {strategy} ===")
        for i, item in enumerate(golden_dataset, start=1):
            print(f"  [{i}/{len(golden_dataset)}] {item['id']}")
            result = evaluate_item(client, settings.chat_deployment, settings.embedding_deployment, item, strategy)
            results.append(result)

    summaries = [summarize(results, s) for s in STRATEGIES]

    for s in summaries:
        logger.info("eval_summary", extra={k: v for k, v in s.items() if v is not None})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RESULTS_DIR / f"eval_{timestamp}.json"
    output_path.write_text(
        json.dumps({"summaries": summaries, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nSaved results to {output_path}")
    print("\n=== Summary ===")

    def fmt(value):
        return f"{value:.3f}" if value is not None else "n/a"

    for s in summaries:
        print(
            f"{s['strategy']:>10} | faithfulness={fmt(s['faithfulness'])} answer_relevancy={fmt(s['answer_relevancy'])} "
            f"context_precision={fmt(s['context_precision'])} context_recall={fmt(s['context_recall'])} "
            f"refusal_accuracy={fmt(s['refusal_accuracy'])} router_accuracy={fmt(s['router_accuracy'])}"
        )


if __name__ == "__main__":
    main()
