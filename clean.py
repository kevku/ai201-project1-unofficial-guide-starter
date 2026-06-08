"""
clean.py — Stage 1.5 (cleaning) for the UCSD Dining RAG project.

Takes the raw JSON written by scraper.py (in raw/) and produces cleaned,
chunker-ready JSON. One cleaning function per source type:

    clean_menu(list) -> list     menu items
    clean_static(str) -> str     accommodations / Triton2Go FAQ / dining plans body
    clean_reddit(list) -> list   thread comments
    clean_blink(list) -> list    Blink "Places to Eat" venues

Note on Blink: scraper.py's extract_pdf() saved page *text*, but clean_blink
expects structured venue dicts (name/description/phone/hours/payments). The PDF
is a 4-column table, so parse_blink_pdf() below re-reads it with pdfplumber's
table extraction to produce those records, which clean_blink then cleans.

Usage:
    python clean.py     # clean every source found in raw/
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", message=".*CropBox.*")
import pdfplumber


RAW_DIR = Path(__file__).parent / "raw"
CLEAN_DIR = Path(__file__).parent / "clean"
CLEAN_DIR.mkdir(exist_ok=True)

PDF_PATH = Path(__file__).parent / "documents" / "Places to Eat at UCSD.pdf"

# Sort-arrow icon glyphs the Blink table embeds in cells live in the
# Unicode Private Use Area (e.g. U+E150, U+E155); strip that whole range.
PUA_GLYPHS = re.compile(r"[\ue000-\uf8ff]")

# HTML entities to unescape to plain text.
HTML_ENTITIES = {"&amp;": "&", "&nbsp;": " ", "&lt;": "<", "&gt;": ">"}

# Sidebar / nav labels that show up as standalone short lines on static pages.
NAV_LABELS = {
    "Menus & Hours", "Events", "Student Jobs", "Toggle navigation",
    "Triton2Go", "Nutrition Services", "About Us", "Food Sources",
    "Dining Plans", "Housing Plans at UC San Diego",
}

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
    "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
}


# --------------------------------------------------------------------------- #
# small shared helpers
# --------------------------------------------------------------------------- #

def _strip_glyphs(text):
    """Remove the Blink sort-icon glyphs from a string (no-op for non-strings)."""
    if not isinstance(text, str):
        return text
    return PUA_GLYPHS.sub("", text).strip()


def _unescape_entities(text: str) -> str:
    for ent, plain in HTML_ENTITIES.items():
        text = text.replace(ent, plain)
    return text


def _save(name: str, data) -> Path:
    path = CLEAN_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# --------------------------------------------------------------------------- #
# 1. Menu items
# --------------------------------------------------------------------------- #

def clean_menu(data: list) -> list:
    """Normalize scraped menu-item dicts (see module docstring for keys)."""
    cleaned = []
    for item in data:
        name = (item.get("name") or "").strip()
        if not name:
            continue  # an item with no name is unusable

        # Icons arrive mixed together (a list, a comma string, or None). Split
        # true allergens ("Contains Dairy") from dietary tags (Vegan, Wellness...).
        raw_tags = item.get("allergens")
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            raw_tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raw_tags = []
        allergens = [t for t in raw_tags if "Contains" in t]
        dietary_tags = [t for t in raw_tags if "Contains" not in t]

        price = item.get("price")
        price = price.strip() if isinstance(price, str) else price
        if not price:
            price = "included with dining plan"

        calories = item.get("calories")
        if calories in ("", None):
            calories = None

        cleaned.append({
            "name": name,
            "description": (item.get("description") or "").strip(),
            "station": (item.get("station") or "").strip(),
            "meal_period": (item.get("meal_period") or "").strip(),
            "allergens": allergens,
            "dietary_tags": dietary_tags,
            "calories": calories,
            "price": price,
            "location": (item.get("location") or "").strip(),
            "date": (item.get("date") or "").strip(),
        })
    return cleaned


# --------------------------------------------------------------------------- #
# 2. Static pages (accommodations, FAQ, dining plans)
# --------------------------------------------------------------------------- #

def clean_static(text: str) -> str:
    """Strip breadcrumbs, sidebar nav, footer, and HTML entities from body text."""
    text = _unescape_entities(text)

    kept = []
    prev = None              # last non-empty line kept (for de-duping)
    seen_content = False     # have we kept any real content yet?
    for line in text.split("\n"):
        stripped = line.strip()

        # Drop the leading "Residential Dining" breadcrumb at the very top.
        if not seen_content and stripped == "Residential Dining":
            continue
        # Drop slash-separated breadcrumb trails ("Residential Dining / ... / Places").
        if " / " in stripped and len(stripped) < 200:
            continue
        # Drop standalone sidebar nav labels.
        if stripped in NAV_LABELS:
            continue
        # Drop footer/address/copyright lines.
        if "UC San Diego 9500 Gilman" in stripped or "Copyright" in stripped:
            continue
        # Drop duplicate consecutive lines ("Dining Accommodations" twice in a row).
        if stripped and stripped == prev:
            continue

        kept.append(line)
        if stripped:
            prev = stripped
            seen_content = True

    text = "\n".join(kept)
    # Collapse 2+ blank lines down to a single blank line.
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    # Pull punctuation back onto the preceding word ("osd.ucsd.edu ." -> "osd.ucsd.edu.").
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# 3. Reddit comments
# --------------------------------------------------------------------------- #

LOW_VALUE_BODIES = {"thanks!", "this!", "agreed"}


def clean_reddit(data: list) -> list:
    """Drop low-signal comments and strip whitespace from the rest."""
    cleaned = []
    for c in data:
        body = (c.get("body") or "").strip()
        upvotes = c.get("upvotes")
        upvotes = upvotes if isinstance(upvotes, int) else 0
        is_reply = bool(c.get("is_reply"))

        # Filler / too-short comments.
        if body.lower() in LOW_VALUE_BODIES or len(body) < 10:
            continue
        # Low-signal by score.
        if upvotes < 2:
            continue
        # Short replies that only make sense in-thread.
        if is_reply and len(body) < 20:
            continue

        cleaned.append({
            "id": c.get("id"),
            "parent_id": c.get("parent_id"),
            "body": body,
            "upvotes": upvotes,
            "date": c.get("date"),
            "is_reply": is_reply,
        })
    return cleaned


# --------------------------------------------------------------------------- #
# 4. Blink "Places to Eat" venues
# --------------------------------------------------------------------------- #

_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", re.IGNORECASE)


def _normalize_time(t: str) -> str:
    """'7:00 a.m.' -> '7:00am', '8 p.m.' -> '8:00pm'."""
    m = _TIME_RE.search(t)
    if not m:
        return t.strip()
    hour, minute, ap = m.group(1), m.group(2) or "00", m.group(3).lower()
    return f"{hour}:{minute}{ap}m"


def _flatten_hours(raw: str) -> str:
    """
    Turn a day-by-day hours blob into a compact grouped string, e.g.
        'Mon-Thu: 7:00am-11:00pm | Fri: 7:00am-8:00pm | Sat-Sun: 10:00am-11:00pm'
    Consecutive days that share the same hours are collapsed into a range.
    """
    if not raw:
        return ""
    flat = re.sub(r"\s+", " ", _strip_glyphs(raw))

    # Slice the blob into per-day chunks.
    day_hours: dict[str, str] = {}
    for i, day in enumerate(DAYS):
        start = re.search(rf"{day}\s*:", flat)
        if not start:
            continue
        rest = flat[start.end():]
        # Cut at the next day name, if any.
        nxt = min(
            (m.start() for d in DAYS[i + 1:]
             for m in [re.search(rf"{d}\s*:", rest)] if m),
            default=len(rest),
        )
        value = rest[:nxt].strip(" .–-")

        if "closed" in value.lower():
            day_hours[day] = "Closed"
            continue
        times = _TIME_RE.findall(value)
        if len(times) >= 2:
            open_t = _normalize_time(value[:value.find(times[0][0]) + 30])
            # Rebuild open/close cleanly from the first two matched times.
            spans = list(_TIME_RE.finditer(value))
            open_t = _normalize_time(spans[0].group(0))
            close_t = _normalize_time(spans[1].group(0))
            day_hours[day] = f"{open_t}-{close_t}"
        elif times:
            day_hours[day] = _normalize_time(_TIME_RE.search(value).group(0))
        else:
            day_hours[day] = value

    if not day_hours:
        return flat  # couldn't parse — keep the (whitespace-normalized) original

    # Group consecutive days with identical hours.
    groups: list[tuple[list[str], str]] = []
    for day in DAYS:
        if day not in day_hours:
            continue
        h = day_hours[day]
        if groups and groups[-1][1] == h and _consecutive(groups[-1][0][-1], day):
            groups[-1][0].append(day)
        else:
            groups.append(([day], h))

    parts = []
    for days, h in groups:
        label = DAY_ABBR[days[0]] if len(days) == 1 else f"{DAY_ABBR[days[0]]}-{DAY_ABBR[days[-1]]}"
        parts.append(f"{label}: {h}")
    return " | ".join(parts)


def _consecutive(day_a: str, day_b: str) -> bool:
    return DAYS.index(day_b) == DAYS.index(day_a) + 1


def clean_blink(data: list) -> list:
    """Clean structured Blink venue dicts (name/description/phone/hours/payments)."""
    cleaned = []
    for v in data:
        name = _strip_glyphs(v.get("name") or "")
        if not name:
            continue

        phone = _strip_glyphs(v.get("phone") or "")
        phone = phone or None  # not guaranteed on this page

        location = _strip_glyphs(v.get("location") or "")
        location = location or None  # building name not always present

        payments = v.get("payments")
        if isinstance(payments, str):
            # Newlines in the cell are word-wrapping ("Credit\nCard"), not item
            # separators — join them to spaces, then split on commas only.
            joined = re.sub(r"\s+", " ", payments.replace("\n", " "))
            payments = [p.strip() for p in joined.split(",") if p.strip()]
        payments = [_strip_glyphs(p) for p in (payments or []) if _strip_glyphs(p)]
        if not payments:
            payments = ["Dining Dollars"]  # assumption: all HDH locations accept DD

        cleaned.append({
            "name": name,
            "description": _strip_glyphs(v.get("description") or ""),
            "location": location,
            "phone": phone,
            "hours": _flatten_hours(v.get("hours") or ""),
            "payments": payments,
        })
    return cleaned


# --------------------------------------------------------------------------- #
# Blink PDF -> structured venue dicts (bridges extract_pdf's page text)
# --------------------------------------------------------------------------- #

_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")


def parse_blink_pdf(path: Path = PDF_PATH) -> list:
    """
    Re-read the Blink PDF as a table and emit raw venue dicts with keys
    name / description / location / phone / hours / payments for clean_blink.
    The "Location/ Telephone" column carries a phone number and sometimes a
    building name; we split them into separate phone and location fields.
    """
    venues = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if len(row) < 4:
                        continue
                    col_name, col_loc, col_hours, col_pay = (
                        (row[0] or ""), (row[1] or ""), (row[2] or ""), (row[3] or "")
                    )
                    # Skip the repeated column-header row.
                    if "Restaurants, caf" in col_name or "fast food" in col_name:
                        continue

                    lines = [l.strip() for l in col_name.splitlines() if l.strip()]
                    if not lines:
                        continue
                    name = lines[0]
                    description = " ".join(lines[1:]).strip()

                    loc_blob = re.sub(r"\s+", " ", col_loc).strip()
                    phone_match = _PHONE_RE.search(loc_blob)
                    phone = phone_match.group(0) if phone_match else ""
                    location = _PHONE_RE.sub("", loc_blob).strip(" .,")

                    venues.append({
                        "name": name,
                        "description": description,
                        "location": location,
                        "phone": phone,
                        "hours": col_hours,
                        "payments": col_pay,
                    })
    return venues


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def main() -> None:
    print(f"Cleaning raw/ -> {CLEAN_DIR}/\n")

    # Menu items — one combined file across all venues.
    all_menu = []
    for f in sorted(RAW_DIR.glob("menu_*.json")):
        all_menu.extend(json.load(f.open()))
    if all_menu:
        cleaned = clean_menu(all_menu)
        _save("clean_menu", cleaned)
        print(f"  menu:   {len(all_menu)} -> {len(cleaned)} items  (clean_menu.json)")

    # Static pages — one file each.
    for f in sorted(RAW_DIR.glob("static_*.json")):
        raw = json.load(f.open())
        page = f.stem.replace("static_", "")
        cleaned = clean_static(raw.get("text", ""))
        _save(f"clean_static_{page}", cleaned)
        print(f"  static: {page}: {len(raw.get('text',''))} -> {len(cleaned)} chars"
              f"  (clean_static_{page}.json)")

    # Reddit comments.
    for f in sorted(RAW_DIR.glob("reddit_*.json")):
        raw = json.load(f.open())
        comments = raw.get("comments", [])
        cleaned = clean_reddit(comments)
        _save("clean_reddit", cleaned)
        print(f"  reddit: {len(comments)} -> {len(cleaned)} comments  (clean_reddit.json)")

    # Blink venues — parse the PDF table, then clean.
    if PDF_PATH.exists():
        parsed = parse_blink_pdf()
        cleaned = clean_blink(parsed)
        _save("clean_blink", cleaned)
        print(f"  blink:  {len(parsed)} -> {len(cleaned)} venues  (clean_blink.json)")
    else:
        print("  blink:  PDF not found, skipped")

    print(f"\nDone. Cleaned JSON in {CLEAN_DIR}/")


if __name__ == "__main__":
    main()
