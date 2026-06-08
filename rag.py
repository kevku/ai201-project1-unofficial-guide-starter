"""
rag.py — Stage 5 (generation) for the UCSD Dining RAG project.

Retrieves chunks via retrieval.retrieve(), formats them as grounded context,
and asks Groq's llama-3.3-70b-versatile to answer using only that context.

Source attribution is built programmatically from the retrieved chunk metadata
BEFORE the LLM is called — the model is explicitly told not to cite sources, so
citations never depend on the model getting them right.

Usage:
    python rag.py                 # runs the planning.md eval queries
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from groq import Groq

from retrieval import retrieve

load_dotenv()
MODEL = "llama-3.3-70b-versatile"
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = (
    "You are a UCSD dining assistant. Answer only using the "
    "provided context. Do not use any outside knowledge. "
    "If the answer is not in the context, say exactly: "
    "I do not have that information in my current sources. "
    "Do not cite sources in your answer text — sources are "
    "handled separately."
)


def _format_context(chunks: list[dict]) -> str:
    """Render retrieved chunks as labeled context blocks for the prompt."""
    return "\n\n".join(
        f"[{c['chunk_id']} | {c['source']}]\n{c['text']}" for c in chunks
    )


def ask(query: str, source_type: str | None = None) -> dict:
    """
    Answer a query grounded in retrieved chunks.

    Returns:
        {
          "answer":  LLM response text (no source line),
          "sources": ["chunk_id | source_filename", ...],   # built programmatically
          "chunks":  [raw retrieved chunk dicts],
        }
    """
    chunks = retrieve(query, source_type=source_type)

    # Build source attribution from metadata up front — never rely on the LLM.
    sources = [f"{c['chunk_id']} | {c['source']}" for c in chunks]

    context = _format_context(chunks)
    user_message = f"Context:\n{context}\n\nQuestion: {query}"

    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    answer = response.choices[0].message.content.strip()

    return {"answer": answer, "sources": sources, "chunks": chunks}


if __name__ == "__main__":
    demo_queries = [
        ("I only eat 1-2 meals a day, what dining plan should I get?", "dining_plan"),
        ("What is good at Ventanas?", "reddit"),
        ("Where can I get poke?", None),
        ("What if I lose my Triton2Go container?", "faq"),
        ("What can I eat if I am allergic to peanuts?", "accommodations"),
        ("What is the best CS professor at UCSD?", None),
    ]
    for i, (q, st) in enumerate(demo_queries, start=1):
        result = ask(q, source_type=st)
        print("=" * 80)
        print(f"Q{i}: {q}  (source_type={st!r})")
        print("-" * 80)
        print(result["answer"])
        print("\nSources:")
        for s in result["sources"]:
            print(f"  • {s}")
        print()
