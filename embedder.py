"""
embedder.py — Stage 3 (embedding + vector store) for the UCSD Dining RAG project.

Loads chunks/all_chunks.json, embeds each chunk's text with all-MiniLM-L6-v2,
and stores everything in a persistent ChromaDB collection ("ucsd_dining") under
./chroma_db using cosine distance.

ChromaDB metadata values must be str/int/float/bool — no None, no lists. We
sanitize on the way in: drop None-valued keys (e.g. blink venues with no
building name) and join list values (e.g. payments_accepted) into a string.

Usage:
    python embedder.py
"""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path(__file__).parent / "chunks" / "all_chunks.json"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION = "ucsd_dining"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH = 100


def _sanitize(meta: dict) -> dict:
    """Coerce a metadata dict into Chroma-safe scalars (drop None, join lists)."""
    clean = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            clean[key] = ", ".join(str(v) for v in value)
        elif isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def main() -> None:
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_PATH}")

    print(f"Loading SentenceTransformer({MODEL_NAME!r})...")
    model = SentenceTransformer(MODEL_NAME)

    texts = [c["text"] for c in chunks]
    print("Encoding chunk texts...")
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # Recreate the collection so re-runs start clean (no stale/duplicate ids).
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    n = len(chunks)
    for start in range(0, n, BATCH):
        end = min(start + BATCH, n)
        batch = chunks[start:end]
        collection.add(
            ids=[c["chunk_id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embeddings[start:end],
            metadatas=[_sanitize({**c["metadata"], "source": c["source"]}) for c in batch],
        )
        print(f"  embedded {end}/{n} chunks")

    print(f"\nDone. ChromaDB collection {COLLECTION!r} now holds "
          f"{collection.count()} entries at {CHROMA_DIR}/")


if __name__ == "__main__":
    main()
