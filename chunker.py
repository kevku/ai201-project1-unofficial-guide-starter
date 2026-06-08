"""
chunker.py — Stage 2 (chunking) for the UCSD Dining RAG project.

Turns the cleaned JSON in clean/ into embedding-ready chunks, following the
Chunking Strategy in planning.md. One chunking function per source type:

    menu ............ 1 item  = 1 chunk            (no overlap)
    accommodations .. 1 h2/h3 section = 1 chunk     (1-sentence overlap)
    dining plans .... 1 plan option = 1 chunk       (no overlap)
    FAQ ............. 1 Q&A pair = 1 chunk           (no overlap)
    reddit .......... 1 comment = 1 chunk; a reply is bundled with its parent
    blink ........... 1 venue = 1 chunk             (no overlap)

Every chunk has the same shape:
    {"chunk_id", "text", "source", "metadata": {...}}

Output: chunks/all_chunks.json (single list) + a token-count summary to stdout.
Token counts use tiktoken's cl100k_base encoding.

Section/question boundaries for the static pages are read from the matching
raw/static_*.json "headings" list (the h1/h2/h3 captured at scrape time), which
is far more reliable than guessing headings from the flattened clean text.

Usage:
    python chunker.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import tiktoken

CLEAN_DIR = Path(__file__).parent / "clean"
RAW_DIR = Path(__file__).parent / "raw"
CHUNKS_DIR = Path(__file__).parent / "chunks"
CHUNKS_DIR.mkdir(exist_ok=True)

ENC = tiktoken.get_encoding("cl100k_base")


def n_tokens(text: str) -> int:
    return len(ENC.encode(text))


def _load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _raw_headings(page: str) -> list[str]:
    """Return the h1/h2/h3 headings captured for a static page at scrape time."""
    raw = RAW_DIR / f"static_{page}.json"
    if raw.exists():
        return _load(raw).get("headings", [])
    return []


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _trim_footer(text: str) -> str:
    """
    Drop the block of short nav/related-links lines that leaks onto the end of
    every static page (e.g. 'Resources', 'Rooted in Flavor', repeated titles).
    A trailing line is footer-ish if it's short (<=6 words) and doesn't end like
    a sentence; real content lines are longer or end with .!?:.
    """
    lines = text.split("\n")
    while lines:
        last = lines[-1].strip()
        if last and len(last.split()) <= 6 and not re.search(r"[.!?:]$", last):
            lines.pop()
        else:
            break
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 1. Menu items
# --------------------------------------------------------------------------- #

def chunk_menu(items: list, source: str) -> list:
    chunks = []
    for i, item in enumerate(items, start=1):
        parts = [item["name"]]
        if item.get("description"):
            parts.append(item["description"])
        loc = ", ".join(p for p in [item.get("station"), item.get("location")] if p)
        if loc:
            parts.append(f"Served at {loc}")
        if item.get("meal_period"):
            parts.append(f"Meal: {item['meal_period']}")
        if item.get("allergens"):
            parts.append("Allergens: " + ", ".join(item["allergens"]))
        if item.get("dietary_tags"):
            parts.append("Dietary: " + ", ".join(item["dietary_tags"]))
        if item.get("calories") is not None:
            parts.append(f"Calories: {item['calories']}")
        if item.get("price"):
            parts.append(f"Price: {item['price']}")
        text = ". ".join(parts) + "."

        chunks.append({
            "chunk_id": f"menu_{i:04d}",
            "text": text,
            "source": source,
            "metadata": {
                "source_type": "menu",
                "location": item.get("location"),
                "station": item.get("station"),
                "meal_period": item.get("meal_period"),
                "date": item.get("date"),
            },
        })
    return chunks


# --------------------------------------------------------------------------- #
# 2. Accommodations — split on h2/h3 sections, 1-sentence overlap
# --------------------------------------------------------------------------- #

def chunk_accommodations(text: str, source: str, page: str) -> list:
    text = _trim_footer(text)
    headings = set(_raw_headings(page))

    # Group consecutive lines into (heading, [body lines]) sections.
    sections: list[tuple[str, list[str]]] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in headings:
            sections.append((stripped, []))
        elif sections:
            sections[-1][1].append(stripped)
        else:
            # Body before the first recognized heading — start an untitled section.
            sections.append(("", [stripped]))

    chunks = []
    prev_body = ""
    for i, (heading, body_lines) in enumerate(sections, start=1):
        body = " ".join(body_lines).strip()
        # 1-sentence overlap carried from the previous section for context bleed,
        # capped at 50 tokens (a list-only section has no sentence breaks, so the
        # last "sentence" could otherwise be huge).
        overlap = ""
        if prev_body:
            sents = _sentences(prev_body)
            if sents:
                last = sents[-1]
                toks = ENC.encode(last)
                if len(toks) > 50:
                    last = ENC.decode(toks[-50:])
                overlap = last + " "
        text_parts = [p for p in [heading, overlap + body] if p.strip()]
        chunk_text = "\n".join(text_parts).strip()
        if not chunk_text:
            continue

        chunks.append({
            "chunk_id": f"accom_{i:04d}",
            "text": chunk_text,
            "source": source,
            "metadata": {
                "source_type": "accommodations",
                "section_heading": heading or None,
            },
        })
        prev_body = body
    return chunks


# --------------------------------------------------------------------------- #
# 3. Dining plans — 1 plan option = 1 chunk
# --------------------------------------------------------------------------- #

_YEAR_RE = re.compile(r"(\d{4}-\d{2}).*Options")
# A plan-option line looks like "Triton Gold: $8,200 (...)". We match on the
# "<Name>: $<thousands>" shape (>=3 digits) rather than the headings list,
# because prior-year options are plain text, not <h3> headings, in the source.
_PLAN_RE = re.compile(r"^[A-Z][A-Za-z ]+:\s*\$[\d,]{3,}")


def chunk_plans(text: str, source: str, page: str, start_idx: int) -> tuple[list, int]:
    text = _trim_footer(text)

    chunks = []
    idx = start_idx
    academic_year = None
    current = None  # (plan_name, plan_heading, [body lines])

    def flush():
        nonlocal current, idx
        if current is None:
            return
        plan_name, plan_heading, body = current
        idx += 1
        chunk_text = "\n".join([plan_heading, *body]).strip()
        chunks.append({
            "chunk_id": f"plan_{idx:04d}",
            "text": chunk_text,
            "source": source,
            "metadata": {
                "source_type": "dining_plan",
                "plan_name": plan_name,
                "academic_year": academic_year,
            },
        })
        current = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        ym = _YEAR_RE.search(stripped)
        if ym:
            flush()
            academic_year = ym.group(1)
            continue
        if _PLAN_RE.match(stripped):
            flush()
            plan_name = stripped.split(":")[0].strip()
            current = (plan_name, stripped, [])
            continue
        if current is not None:
            current[2].append(stripped)
    flush()
    return chunks, idx


# --------------------------------------------------------------------------- #
# 4. Triton2Go FAQ — 1 Q&A pair = 1 chunk
# --------------------------------------------------------------------------- #

def chunk_faq(text: str, source: str, page: str) -> list:
    text = _trim_footer(text)
    headings = set(_raw_headings(page))
    questions = {h for h in headings if h.endswith("?")}

    chunks = []
    idx = 0
    current_q = None
    answer_lines: list[str] = []

    def flush():
        nonlocal current_q, answer_lines, idx
        if current_q is None:
            return
        idx += 1
        answer = " ".join(answer_lines).strip()
        text_ = f"Q: {current_q}\nA: {answer}".strip()
        chunks.append({
            "chunk_id": f"faq_{idx:04d}",
            "text": text_,
            "source": source,
            "metadata": {"source_type": "faq", "question": current_q},
        })
        current_q, answer_lines = None, []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in questions:           # start a new Q&A pair
            flush()
            current_q = stripped
        elif stripped in headings:          # a non-question section header ends the answer
            flush()
        elif current_q is not None:         # accumulate the answer
            answer_lines.append(stripped)
        # else: intro/section text before any question — skipped (not a Q&A pair)
    flush()
    return chunks


# --------------------------------------------------------------------------- #
# 5. Reddit — 1 comment = 1 chunk; bundle replies with their parent
# --------------------------------------------------------------------------- #

def chunk_reddit(comments: list, source: str) -> list:
    by_id = {c.get("id"): c for c in comments if c.get("id")}

    chunks = []
    for i, c in enumerate(comments, start=1):
        body = c["body"]
        parent = by_id.get(c.get("parent_id"))
        is_bundle = bool(c.get("is_reply") and parent is not None)

        if is_bundle:
            text = f"Original comment: {parent['body']}\nReply: {body}"
        else:
            text = body

        chunks.append({
            "chunk_id": f"reddit_{i:04d}",
            "text": text,
            "source": source,
            "metadata": {
                "source_type": "reddit",
                "upvotes": c.get("upvotes"),
                "date": c.get("date"),
                "is_reply_bundle": is_bundle,
            },
        })
    return chunks


# --------------------------------------------------------------------------- #
# 6. Blink "Places to Eat" venues
# --------------------------------------------------------------------------- #

def chunk_blink(venues: list, source: str) -> list:
    chunks = []
    for i, v in enumerate(venues, start=1):
        parts = [v["name"]]
        if v.get("description"):
            parts.append(v["description"])
        if v.get("location"):
            parts.append(f"Location: {v['location']}")
        if v.get("hours"):
            parts.append(f"Hours: {v['hours']}")
        if v.get("payments"):
            parts.append("Payments accepted: " + ", ".join(v["payments"]))
        if v.get("phone"):
            parts.append(f"Phone: {v['phone']}")
        text = ". ".join(parts) + "."

        chunks.append({
            "chunk_id": f"blink_{i:04d}",
            "text": text,
            "source": source,
            "metadata": {
                "source_type": "places_to_eat",
                "venue_name": v["name"],
                "location": v.get("location"),
                "payments_accepted": v.get("payments", []),
            },
        })
    return chunks


# --------------------------------------------------------------------------- #
# Driver + summary
# --------------------------------------------------------------------------- #

def main() -> None:
    all_chunks: list = []

    all_chunks += chunk_menu(_load(CLEAN_DIR / "clean_menu.json"), "clean_menu.json")

    all_chunks += chunk_accommodations(
        _load(CLEAN_DIR / "clean_static_accommodations.json"),
        "clean_static_accommodations.json", "accommodations",
    )

    # Plans span two files; keep chunk ids unique across both.
    plan_idx = 0
    for page in ("incoming", "continuing"):
        src = f"clean_static_{page}.json"
        plan_chunks, plan_idx = chunk_plans(_load(CLEAN_DIR / src), src, page, plan_idx)
        all_chunks += plan_chunks

    all_chunks += chunk_faq(
        _load(CLEAN_DIR / "clean_static_index.json"),
        "clean_static_index.json", "index",
    )

    all_chunks += chunk_reddit(_load(CLEAN_DIR / "clean_reddit.json"), "clean_reddit.json")

    all_chunks += chunk_blink(_load(CLEAN_DIR / "clean_blink.json"), "clean_blink.json")

    # Token count per chunk, for the summary.
    for ch in all_chunks:
        ch["_tokens"] = n_tokens(ch["text"])

    # Drop prior-year (2025-26) dining-plan chunks — keep only the current year.
    before = len(all_chunks)
    all_chunks = [
        c for c in all_chunks
        if not (c["metadata"]["source_type"] == "dining_plan"
                and c["metadata"].get("academic_year") == "2025-26")
    ]
    print(f"Filtered out {before - len(all_chunks)} dining_plan (2025-26) chunks; "
          f"{len(all_chunks)} chunks remain.")

    # Drop tiny chunks (under 8 tokens) that carry too little signal to embed.
    tiny = [c["chunk_id"] for c in all_chunks if c["_tokens"] < 8]
    all_chunks = [c for c in all_chunks if c["_tokens"] >= 8]
    print(f"Dropped {len(tiny)} chunks under 8 tokens: {tiny}")

    out = CHUNKS_DIR / "all_chunks.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in c.items() if k != "_tokens"} for c in all_chunks],
                  f, ensure_ascii=False, indent=2)

    # ---- summary ----
    by_type: dict[str, list[int]] = defaultdict(list)
    for ch in all_chunks:
        by_type[ch["metadata"]["source_type"]].append(ch["_tokens"])

    print(f"Wrote {len(all_chunks)} chunks -> {out}\n")
    print(f"{'source_type':<16}{'chunks':>8}{'min':>7}{'max':>7}{'avg':>8}")
    print("-" * 46)
    for st in sorted(by_type):
        toks = by_type[st]
        print(f"{st:<16}{len(toks):>8}{min(toks):>7}{max(toks):>7}{sum(toks)/len(toks):>8.1f}")
    print("-" * 46)
    total = [t for toks in by_type.values() for t in toks]
    print(f"{'TOTAL':<16}{len(total):>8}{min(total):>7}{max(total):>7}{sum(total)/len(total):>8.1f}")


if __name__ == "__main__":
    main()
