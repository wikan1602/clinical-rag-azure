import json
from pathlib import Path

from dotenv import load_dotenv

from ingestion.chunking import count_tokens, fixed_size_chunk, semantic_chunk
from ingestion.embeddings import embed_texts
from ingestion.pdf_parser import extract_text_from_pdf

load_dotenv()

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def make_record(pdf_stem: str, source: str, strategy: str, index: int, text: str) -> dict:
    return {
        "id": f"{pdf_stem}-{strategy}-{index}",
        "source": source,
        "strategy": strategy,
        "chunk_index": index,
        "text": text,
        "token_count": count_tokens(text),
    }


def main() -> None:
    pdf_paths = sorted(RAW_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDFs found in {RAW_DIR}")

    fixed_records = []
    semantic_records = []

    for pdf_path in pdf_paths:
        print(f"Parsing {pdf_path.name}...")
        text = extract_text_from_pdf(pdf_path)

        fixed_chunks = fixed_size_chunk(text)
        fixed_records += [
            make_record(pdf_path.stem, pdf_path.name, "fixed", i, chunk)
            for i, chunk in enumerate(fixed_chunks)
        ]

        print(f"  Semantic chunking {pdf_path.name} (calls embedding API)...")
        semantic_chunks = semantic_chunk(text, embed_fn=embed_texts)
        semantic_records += [
            make_record(pdf_path.stem, pdf_path.name, "semantic", i, chunk)
            for i, chunk in enumerate(semantic_chunks)
        ]

        print(f"  -> {len(fixed_chunks)} fixed chunks, {len(semantic_chunks)} semantic chunks")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "chunks_fixed.json").write_text(
        json.dumps(fixed_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (PROCESSED_DIR / "chunks_semantic.json").write_text(
        json.dumps(semantic_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nTotal fixed-size chunks: {len(fixed_records)}")
    print(f"Total semantic chunks: {len(semantic_records)}")


if __name__ == "__main__":
    main()
