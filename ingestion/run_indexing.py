import json
from pathlib import Path

from dotenv import load_dotenv

from ingestion.embeddings import embed_texts
from ingestion.search_index import create_or_update_index, get_search_client

load_dotenv()

PROCESSED_DIR = Path("data/processed")

STRATEGY_FILES = {
    "fixed": PROCESSED_DIR / "chunks_fixed.json",
    "semantic": PROCESSED_DIR / "chunks_semantic.json",
}

UPLOAD_BATCH_SIZE = 500


def index_strategy(strategy: str, path: Path) -> None:
    records = json.loads(path.read_text(encoding="utf-8"))
    index_name = f"clinical-guidelines-{strategy}"

    print(f"Creating index '{index_name}'...")
    create_or_update_index(index_name)

    print(f"Embedding {len(records)} chunks for '{strategy}'...")
    texts = [r["text"] for r in records]
    vectors = embed_texts(texts)

    documents = [
        {
            "id": record["id"],
            "content": record["text"],
            "source": record["source"],
            "strategy": record["strategy"],
            "chunk_index": record["chunk_index"],
            "token_count": record["token_count"],
            "topic": record["topic"],
            "published_year": record["published_year"],
            "content_vector": vector,
        }
        for record, vector in zip(records, vectors)
    ]

    client = get_search_client(index_name)
    print(f"Uploading {len(documents)} documents to '{index_name}'...")
    for i in range(0, len(documents), UPLOAD_BATCH_SIZE):
        batch = documents[i : i + UPLOAD_BATCH_SIZE]
        results = client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        if failed:
            print(f"  {len(failed)} documents failed in batch starting at {i}: {failed[0].error_message}")

    print(f"Done indexing '{strategy}'.\n")


def main() -> None:
    for strategy, path in STRATEGY_FILES.items():
        index_strategy(strategy, path)


if __name__ == "__main__":
    main()
