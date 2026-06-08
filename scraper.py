"""
scraper.py — Stage 1 (Document Ingestion) for the UCSD Dining RAG project.

Pulls raw content from the six source types listed in planning.md and writes the
extracted output to JSON files under raw/ *before* any chunking/cleaning happens
downstream (Milestone 3's chunker.py consumes these files).

Sources & strategy (all server-rendered — no JS, so requests + BeautifulSoup is enough):
  - HDH venue menu pages ....... scrape_menu(url)    -> list[dict] of menu items
  - Static HDH pages ........... scrape_static(url)   -> dict with cleaned body text
    (accommodations, Triton2Go FAQ, dining plans)
  - Reddit thread .............. scrape_reddit(url)   -> dict {post_title, comments}
  - Blink "Places to Eat" PDF .. extract_pdf(path)    -> list[dict] of page texts

Every scrape function:
  * is defensive — network/parse failures are reported, not fatal, so one broken
    source never kills the whole run;
  * saves its raw output to raw/<name>.json before returning.

Usage:
    python scraper.py            # scrape every source from planning.md
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

# pdfplumber prints noisy CropBox warnings on some PDFs; quiet them.
import warnings
warnings.filterwarnings("ignore", message=".*CropBox.*")
import pdfplumber


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 30  # seconds


class ScrapeError(Exception):
    """Raised when a source can't be fetched or parsed."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _slugify(text: str) -> str:
    """Turn a label into a safe-ish filename slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "source"


def _fetch_html(url: str) -> BeautifulSoup:
    """GET a URL and return parsed soup, raising ScrapeError on any failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapeError(f"network error fetching {url}: {exc}") from exc
    if not resp.text.strip():
        raise ScrapeError(f"empty response body from {url}")
    return BeautifulSoup(resp.text, "lxml")


def _save_raw(name: str, data) -> Path:
    """Write extracted output to raw/<name>.json before any cleaning."""
    path = RAW_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# --------------------------------------------------------------------------- #
# 1. HDH venue menu pages
# --------------------------------------------------------------------------- #

def _venue_name_from_title(soup: BeautifulSoup) -> str:
    """'Canyon Vista Marketplace  Food Menu | HDH Dining ...' -> 'Canyon Vista Marketplace'."""
    title = (soup.title.string or "").strip() if soup.title else ""
    name = re.split(r"\bFood Menu\b", title)[0]
    return re.sub(r"\s+", " ", name).strip() or "Unknown Venue"


def _menu_date(soup: BeautifulSoup) -> str | None:
    """Grab the long-form date the menu is showing (dayNum=0 == today)."""
    m = re.search(
        r"(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),\s+"
        r"[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}",
        soup.get_text(" ", strip=True),
    )
    return m.group(0) if m else None


def _station_name(row) -> str:
    """
    Resolve an item's station from its nearest div.station-list ancestor, whose
    class encodes the station name (the menu-category-section class only carries
    it for some meal periods, so we can't rely on that).
        ['station-list', 'station_Fresh']          -> 'Fresh'
        ['station-list', 'station_Fusion', 'Grill'] -> 'Fusion Grill'
        ['station-list', 'station_Three', 'Sixty']  -> 'Three Sixty'
    """
    sl = row.find_parent("div", class_="station-list")
    classes = sl.get("class") if sl else None
    if not classes:
        return "Unknown Station"
    for i, c in enumerate(classes):
        if c.startswith("station_"):
            parts = [c[len("station_"):], *classes[i + 1:]]
            return " ".join(p for p in parts if p).strip() or "Unknown Station"
    return "Unknown Station"


def _parse_calories(text: str) -> int | None:
    m = re.search(r"\d[\d,]*", text or "")
    return int(m.group(0).replace(",", "")) if m else None


def scrape_menu(url: str) -> list[dict]:
    """
    Extract menu items from an HDH venue page.

    Returns a list of dicts, each:
        name, description, station, meal_period, allergens (list),
        calories (int|None), price (str|None), location, date
    Items render twice (desktop + mobile responsive blocks), so we de-dupe on
    (meal_period, station, name, nutrition-link).
    """
    soup = _fetch_html(url)
    location = _venue_name_from_title(soup)
    date = _menu_date(soup)

    items: list[dict] = []
    seen: set[tuple] = set()

    # meal-category (Breakfast/Lunch/Dinner/...) -> menu-category-section (station) -> item rows
    for meal_block in soup.select("div.meal-category"):
        heading = meal_block.find(["h1", "h2", "h3", "h4"])
        meal_period = (
            re.sub(r"\s*Menu\s*$", "", heading.get_text(strip=True)).strip()
            if heading else None
        )

        for section in meal_block.select("div.menu-category-section"):
            for row in section.select("div.menU-item-row"):
                link = row.select_one("a.sublocsitem")
                if not link:
                    continue
                name = link.get_text(strip=True)
                href = link.get("href", "")
                station = _station_name(row)

                dedupe_key = (meal_period, station, name, href)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                desc_el = row.select_one("div.proI")
                description = desc_el.get_text(" ", strip=True) if desc_el else ""

                cals_el = row.select_one("span.cals")
                calories = _parse_calories(cals_el.get_text()) if cals_el else None

                price_el = row.select_one("span.item-price")
                price = price_el.get_text(strip=True) if price_el else ""

                # Allergen / dietary icons (e.g. "Contains Dairy", "Vegan").
                allergens = [
                    img.get("title").strip()
                    for img in row.find_all("img")
                    if "allergenicons" in (img.get("src", "").lower())
                    and img.get("title")
                ]

                items.append({
                    "name": name,
                    "description": description,
                    "station": station,
                    "meal_period": meal_period,
                    "allergens": allergens,
                    "calories": calories,
                    "price": price or None,
                    "location": location,
                    "date": date,
                })

    if not items:
        raise ScrapeError(
            f"parsed 0 menu items from {url} — page layout may have changed "
            "or the venue has no menu for this day"
        )

    _save_raw(f"menu_{_slugify(location)}", items)
    return items


# --------------------------------------------------------------------------- #
# 2. Static HDH pages (accommodations, FAQ, dining plans)
# --------------------------------------------------------------------------- #

def scrape_static(url: str) -> dict:
    """
    Extract the body text of a static HDH page, dropping nav/header/footer/script
    boilerplate. The real content lives in <main id="main-content">.

    Returns: {url, title, headings (list), text}
    """
    soup = _fetch_html(url)
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    main = soup.select_one("main, #main-content")
    if main is None:
        raise ScrapeError(f"could not locate <main> content on {url}")

    # Strip boilerplate that sometimes lives inside <main>.
    for junk in main.select("script, style, nav, header, footer, noscript, form"):
        junk.decompose()

    headings = [
        h.get_text(strip=True)
        for h in main.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ]
    # Extract one line per block-level element, joining each block's inner text
    # with spaces (separator=" ") so inline links (<a>, <strong>, ...) flow into
    # the surrounding sentence instead of breaking onto their own lines. Block
    # boundaries still become newlines, which keeps line-based cleaning working.
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6",
                  "p", "li", "blockquote", "figcaption", "dt", "dd", "td", "th"]
    lines = []
    for block in main.find_all(block_tags):
        line = block.get_text(separator=" ", strip=True)
        if line:
            lines.append(re.sub(r"\s+", " ", line))
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if not text.strip():
        raise ScrapeError(f"extracted empty body text from {url}")

    data = {"url": url, "title": title, "headings": headings, "text": text}
    name = _slugify(urlparse(url).path.rsplit("/", 1)[-1].replace(".html", "")) or "static"
    _save_raw(f"static_{name}", data)
    return data


# --------------------------------------------------------------------------- #
# 3. Reddit thread (via old.reddit.com — server-rendered)
# --------------------------------------------------------------------------- #

def _comment_score(comment) -> int | None:
    el = comment.select_one("span.score.unvoted")
    if not el:
        return None
    raw = el.get("title") or el.get_text(strip=True)
    m = re.search(r"-?\d+", raw)
    return int(m.group(0)) if m else None


def scrape_reddit(url: str) -> dict:
    """
    Extract the post title and every comment from an old.reddit.com thread.

    Returns: {url, post_title, comments: [{body, upvotes, date, is_reply}, ...]}
    A comment is is_reply=True when nested inside another comment.
    """
    # old.reddit serves full HTML; rewrite www/new reddit hosts so this works.
    parsed = urlparse(url)
    if "old.reddit.com" not in parsed.netloc:
        url = parsed._replace(netloc="old.reddit.com").geturl()

    soup = _fetch_html(url)

    title_el = soup.select_one("a.title") or soup.select_one("p.title a")
    post_title = title_el.get_text(strip=True) if title_el else None

    comments: list[dict] = []
    for comment in soup.select("div.comment"):
        body_el = comment.select_one("div.entry div.usertext-body div.md")
        if body_el is None:
            continue  # deleted/removed or collapsed placeholder
        body = body_el.get_text(" ", strip=True)
        if not body or body.lower() in {"[deleted]", "[removed]"}:
            continue

        time_el = comment.select_one("time")
        date = time_el.get("datetime") if time_el else None

        # Nested inside another div.comment => it's a reply.
        is_reply = comment.find_parent("div", class_="comment") is not None

        comments.append({
            "body": body,
            "upvotes": _comment_score(comment),
            "date": date,
            "is_reply": is_reply,
        })

    if not comments:
        raise ScrapeError(
            f"parsed 0 comments from {url} — Reddit may be rate-limiting "
            "(try again shortly) or the thread layout changed"
        )

    data = {"url": url, "post_title": post_title, "comments": comments}
    slug = _slugify(parsed.path.strip("/").split("/")[-1] or "thread")
    _save_raw(f"reddit_{slug}", data)
    return data


# --------------------------------------------------------------------------- #
# 4. Blink "Places to Eat" PDF
# --------------------------------------------------------------------------- #

def extract_pdf(path: str) -> list[dict]:
    """
    Extract text from the Blink Places-to-Eat PDF, one entry per page.

    Returns: [{page: int, text: str}, ...]
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise ScrapeError(f"PDF not found: {pdf_path}")

    pages: list[dict] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append({"page": i, "text": text.strip()})
    except Exception as exc:  # pdfminer raises a grab-bag of exception types
        raise ScrapeError(f"failed to read PDF {pdf_path}: {exc}") from exc

    if not any(p["text"] for p in pages):
        raise ScrapeError(f"extracted no text from {pdf_path} (is it a scanned image?)")

    _save_raw(f"pdf_{_slugify(pdf_path.stem)}", pages)
    return pages


# --------------------------------------------------------------------------- #
# Driver — scrape every source listed in planning.md
# --------------------------------------------------------------------------- #

MENU_URLS = [
    # 64 Degrees
    "https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=64&subLocNum=00&locDetID=18&dayNum=0",
    # Restaurants at Sixth College
    "https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=37&subLocNum=00&locDetID=24&dayNum=0",
    # Canyon Vista Marketplace
    "https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=24&subLocNum=00&locDetID=11&dayNum=0",
    # Ventanas
    "https://hdh-web.ucsd.edu/dining/apps/diningservices/Restaurants/Venue_V3?locId=18&subLocNum=00&locDetID=8&dayNum=0",
]

STATIC_URLS = [
    "https://hdhdining.ucsd.edu/dining-plans/incoming.html",
    "https://hdhdining.ucsd.edu/dining-plans/continuing.html",
    "https://hdhdining.ucsd.edu/triton2go/index.html",
    "https://hdhdining.ucsd.edu/nutrition-services/accommodations.html",
]

REDDIT_URLS = [
    "https://old.reddit.com/r/UCSD/comments/1gsvgjl/need_food_recommendations_from_dining_halls/",
]

PDF_PATHS = [
    "documents/Places to Eat at UCSD.pdf",
]


def _run(label: str, fn, arg, summarize) -> bool:
    """Run one scrape, print a one-line status, and never crash the whole run."""
    try:
        result = fn(arg)
        print(f"  [ok]   {label}: {summarize(result)}")
        return True
    except ScrapeError as exc:
        print(f"  [WARN] {label}: {exc}", file=sys.stderr)
    except Exception as exc:  # unexpected — show it but keep going
        print(f"  [FAIL] {label}: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
    return False


def main() -> None:
    print(f"Scraping all sources -> {RAW_DIR}/\n")
    ok = total = 0

    print("Menu pages:")
    for u in MENU_URLS:
        total += 1
        loc_id = parse_qs(urlparse(u).query).get("locId", ["?"])[0]
        ok += _run(f"locId={loc_id}", scrape_menu,
                   u, lambda r: f"{len(r)} items ({r[0]['location']})")
        time.sleep(1)  # be polite to the server

    print("\nStatic pages:")
    for u in STATIC_URLS:
        total += 1
        ok += _run(u.rsplit("/", 1)[-1], scrape_static, u,
                   lambda r: f"{len(r['text'])} chars, {len(r['headings'])} headings")
        time.sleep(1)

    print("\nReddit:")
    for u in REDDIT_URLS:
        total += 1
        ok += _run(u.rsplit("/", 2)[-2], scrape_reddit, u,
                   lambda r: f"{len(r['comments'])} comments")
        time.sleep(2)  # Reddit is stricter about rate limits

    print("\nPDF:")
    for p in PDF_PATHS:
        total += 1
        ok += _run(p, extract_pdf, p, lambda r: f"{len(r)} pages")

    print(f"\nDone: {ok}/{total} sources scraped successfully. Raw JSON in {RAW_DIR}/")
    if ok < total:
        print("Some sources reported issues above — re-run or check the source URLs.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
