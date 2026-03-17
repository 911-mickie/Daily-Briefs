"""Fetch full article text for a list of articles.

Uses httpx + readability-lxml to extract the main body from each URL.
Falls back to the existing `summary` field on any error.
Uses a thread pool so all fetches run concurrently.
"""
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from readability import Document

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DailyBriefs/2.0)"}
_TIMEOUT = 8          # seconds per request
_MAX_CHARS = 8_000    # ~2 000 tokens
_MAX_WORKERS = 10


def _fetch_text(article: dict) -> dict:
    """Return a copy of the article dict with a `full_text` field added."""
    url = article.get("link", "")
    if not url:
        return {**article, "full_text": article.get("summary", "")}
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        doc = Document(resp.text)
        # readability returns HTML; strip tags for plain text
        import re
        text = re.sub(r"<[^>]+>", " ", doc.summary())
        text = re.sub(r"\s{2,}", " ", text).strip()
        return {**article, "full_text": text[:_MAX_CHARS]}
    except Exception as e:
        print(f"  [enrich warn] {url[:60]}: {e}")
        return {**article, "full_text": article.get("summary", "")}


def enrich(articles: list[dict]) -> list[dict]:
    """Enrich all articles with full_text. Returns a new list (same order)."""
    print(f"  Enriching {len(articles)} articles (up to {_MAX_WORKERS} concurrent)...")
    results: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_text, a): i for i, a in enumerate(articles)}
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
    return [results[i] for i in range(len(articles))]
