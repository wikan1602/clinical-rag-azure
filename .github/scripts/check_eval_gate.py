import json
import sys
from pathlib import Path

GATE_STRATEGY = "semantic"
THRESHOLDS = {
    "faithfulness": 0.85,
    "context_precision": 0.75,
    "context_recall": 0.75,
    "refusal_accuracy": 0.875,
}


def latest_results_file() -> Path:
    results_dir = Path("eval/results")
    files = sorted(results_dir.glob("eval_*.json"))
    if not files:
        raise SystemExit("No eval results found in eval/results/")
    return files[-1]


def main() -> None:
    path = latest_results_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    summaries = {s["strategy"]: s for s in data["summaries"]}

    if GATE_STRATEGY not in summaries:
        raise SystemExit(f"No '{GATE_STRATEGY}' summary found in {path}")

    summary = summaries[GATE_STRATEGY]
    print(f"Gate check against {path} (strategy={GATE_STRATEGY})")

    passed = True
    for metric, threshold in THRESHOLDS.items():
        value = summary.get(metric)
        ok = value is not None and value >= threshold
        passed = passed and ok
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {metric}: {value} (threshold >= {threshold})")

    if not passed:
        print("\nEval gate FAILED — deployment blocked.")
        sys.exit(1)

    print("\nEval gate PASSED — proceeding to deploy.")


if __name__ == "__main__":
    main()
