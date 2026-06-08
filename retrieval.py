"""
retrieval.py — Stage 4 (retrieval) for the UCSD Dining RAG project.

Loads the persistent ChromaDB collection "ucsd_dining" and the all-MiniLM-L6-v2
model, then exposes retrieve(query, source_type=None). top-k is chosen per
source_type per planning.md's Retrieval Approach.

Run directly to execute the five evaluation queries from planning.md.

Usage:
    python retrieval.py
"""

from __future__ import annotations

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION = "ucsd_dining"
MODEL_NAME = "all-MiniLM-L6-v2"

# top-k by source_type. planning.md names "menu_item" and "policy"; the actual
# chunk source_type values are "menu" and "accommodations", so we map both.
DEFAULT_K = 5
K_BY_SOURCE_TYPE = {
    "menu": 7, "menu_item": 7,
    "faq": 3,
    "accommodations": 3, "policy": 3,
    "dining_plan": 3,
    "places_to_eat": 5,
    "reddit": 5,
}

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_collection(COLLECTION)
_model = SentenceTransformer(MODEL_NAME)


def retrieve(query: str, source_type: str | None = None) -> list[dict]:
    """
    Embed the query and return the top-k most similar chunks, optionally
    restricted to a single source_type. k depends on source_type (see above).

    Each result: {chunk_id, text, source, metadata, distance_score}.
    """
    k = K_BY_SOURCE_TYPE.get(source_type, DEFAULT_K) if source_type else DEFAULT_K
    query_emb = _model.encode([query], convert_to_numpy=True).tolist()
    where = {"source_type": source_type} if source_type else None

    res = _collection.query(query_embeddings=query_emb, n_results=k, where=where)

    results = []
    ids = res["ids"][0]
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        meta = dict(meta)
        results.append({
            "chunk_id": cid,
            "text": doc,
            "source": meta.get("source"),
            "metadata": meta,
            "distance_score": dist,
        })
    return results


TEST_QUERIES = [
    ("I only eat 1-2 meals a day, what dining plan should I get?", "dining_plan"),
    ("What is good at Ventanas?", "reddit"),
    # Unfiltered: location queries retrieve best across sources (poke lives in both
    # the Blink venue list and the Sixth College menu chunks, not just one).
    ("Where can I get poke?", None),
    ("What if I lose my Triton2Go container?", "faq"),
    ("What can I eat if I am allergic to peanuts?", "accommodations"),
]


def _run_tests() -> None:
    for i, (query, source_type) in enumerate(TEST_QUERIES, start=1):
        print("=" * 80)
        print(f"Q{i}: {query}   (source_type={source_type!r})")
        print("=" * 80)
        for rank, r in enumerate(retrieve(query, source_type=source_type), start=1):
            text = r["text"].replace("\n", " ")[:200]
            print(f"  #{rank}  {r['chunk_id']:<12} {r['source']:<28} "
                  f"dist={r['distance_score']:.4f}")
            print(f"       {text}")
        print()


if __name__ == "__main__":
    _run_tests()
