"""
app.py — Gradio query interface for the UCSD Dining RAG project (Milestone 5).

Type a dining question and get a grounded answer with inline source attribution.
A small keyword router picks the right source_type before calling rag.ask(), so
e.g. dining-plan questions are filtered to the dining_plan chunks.

Usage:
    python app.py
"""

from __future__ import annotations

import gradio as gr

from rag import ask

REFUSAL = "I do not have that information in my current sources"

# Friendly display names for each source file.
FRIENDLY_SOURCES = {
    "clean_menu.json": "HDH Dining Menus",
    "clean_static_accommodations.json": "HDH Dining Accommodations",
    "clean_static_incoming.json": "Incoming Student Dining Plans",
    "clean_static_continuing.json": "Continuing Student Dining Plans",
    "clean_static_index.json": "Triton2Go FAQ",
    "clean_reddit.json": "UCSD Reddit Recommendations",
    "clean_blink.json": "UCSD Campus Eateries (Blink)",
}

# Campus eatery / venue names used to detect "where can I eat X" location queries.
LOCATIONS = [
    "ventanas", "canyon vista", "64 degrees", "sixth", "makai", "pines",
    "oceanview", "ocean view", "roots", "spice", "bistro", "seventh",
    "goody", "sunshine", "tandoor", "soul", "wok", "taqueria", "triton grill",
    "garden bar", "al dente", "umi", "rooftop", "crave", "wolftown", "noodles",
]


def route(query: str) -> str | None:
    """Pick a source_type for a query using simple keyword rules (first match wins)."""
    q = query.lower()
    if any(kw in q for kw in ("dining plan", "meal plan", "triton gold", "triton blue")):
        return "dining_plan"
    if any(kw in q for kw in ("poke", "eat", "food", "menu", "get", "order")) \
            and any(loc in q for loc in LOCATIONS):
        return None  # location query — search across all sources
    if any(kw in q for kw in ("allerg", "vegan", "halal", "kosher", "rad")):
        return "accommodations"
    if any(kw in q for kw in ("triton2go", "container", "deposit", "reusable")):
        return "faq"
    if any(kw in q for kw in ("reddit", "recommend", "students say", "good at")):
        return "reddit"
    return None


def _attribution(chunks: list[dict]) -> str:
    """Build a deduplicated, friendly 'retrieved from' line from chunk sources."""
    names: list[str] = []
    for c in chunks:
        friendly = FRIENDLY_SOURCES.get(c["source"], c["source"])
        if friendly not in names:
            names.append(friendly)
    return ", ".join(names)


def handle_query(query: str) -> str:
    """Route, answer, and append inline source attribution as a single string."""
    if not query or not query.strip():
        return ""
    result = ask(query, source_type=route(query))
    answer = result["answer"]

    # Don't tack a "retrieved from" line onto a refusal — it would contradict it.
    if REFUSAL in answer:
        return answer

    sources = _attribution(result["chunks"])
    if not sources:
        return answer
    return f"{answer}\n\nThis information was retrieved from: {sources}"


with gr.Blocks(title="UCSD Dining Assistant") as demo:
    gr.Markdown("# UCSD Dining Assistant\nAsk about menus, dining plans, "
                "Triton2Go, accommodations, and campus eateries.")

    query_box = gr.Textbox(
        label="Ask about UCSD dining",
        placeholder="e.g. Where can I get poke on campus?",
    )
    submit_btn = gr.Button("Ask", variant="primary")

    answer_box = gr.Textbox(label="Answer", lines=8)

    gr.Examples(
        examples=[
            ["What dining plan should I get if I eat 1-2 meals a day?"],
            ["Where can I get poke on campus?"],
            ["What can I eat if I have a peanut allergy?"],
            ["What is the Triton2Go container deposit?"],
        ],
        inputs=query_box,
    )

    # Submit on button click and on Enter in the textbox.
    submit_btn.click(handle_query, inputs=query_box, outputs=answer_box)
    query_box.submit(handle_query, inputs=query_box, outputs=answer_box)


if __name__ == "__main__":
    demo.launch()
