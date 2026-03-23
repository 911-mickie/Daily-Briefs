"""
Lightweight SQLite store to track which articles have already appeared
in a daily brief so they are not repeated.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).parent / "content_history.db"
EXPIRY_DAYS = 120  # ~4 months


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS used_articles (
                url        TEXT PRIMARY KEY,
                title      TEXT,
                source     TEXT,
                category   TEXT,
                date_used  TEXT NOT NULL
            )
            """
        )


def filter_unseen(articles: List[Dict]) -> List[Dict]:
    """Return only articles whose URL has not been used before."""
    if not articles:
        return articles
    with _connect() as conn:
        urls = {a["link"] for a in articles}
        placeholders = ",".join("?" for _ in urls)
        rows = conn.execute(
            f"SELECT url FROM used_articles WHERE url IN ({placeholders})",
            list(urls),
        ).fetchall()
        seen = {r[0] for r in rows}
    kept = [a for a in articles if a["link"] not in seen]
    if len(articles) != len(kept):
        print(f"  Dedup: {len(articles) - len(kept)} already-seen articles removed")
    return kept


def mark_used(articles: List[Dict]) -> None:
    """Record articles that made it into today's brief."""
    if not articles:
        return
    today = date.today().isoformat()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO used_articles (url, title, source, category, date_used)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (a["link"], a.get("title", ""), a.get("source", ""), a.get("category", ""), today)
                for a in articles
            ],
        )


def purge_old() -> None:
    """Delete entries older than EXPIRY_DAYS."""
    cutoff = (date.today() - timedelta(days=EXPIRY_DAYS)).isoformat()
    with _connect() as conn:
        deleted = conn.execute(
            "DELETE FROM used_articles WHERE date_used < ?", (cutoff,)
        ).rowcount
    if deleted:
        print(f"  Purged {deleted} expired entries from content history")
