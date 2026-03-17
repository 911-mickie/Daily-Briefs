"""Weekly interview experience fetcher (runs on Sundays).

Pulls from Reddit RSS search queries looking for ML/DS interview experiences
posted in the last week. The LLM synthesis step later extracts the actual
questions from the post text.
"""
import feedparser
from datetime import date

_FEEDS = [
    (
        "r/MachineLearning",
        "https://www.reddit.com/r/MachineLearning/search.rss"
        "?q=interview+experience&sort=new&restrict_sr=1&t=week",
    ),
    (
        "r/cscareerquestions",
        "https://www.reddit.com/r/cscareerquestions/search.rss"
        "?q=ML+engineer+interview&sort=new&restrict_sr=1&t=week",
    ),
    (
        "r/datascience",
        "https://www.reddit.com/r/datascience/search.rss"
        "?q=interview+experience+ML&sort=new&restrict_sr=1&t=week",
    ),
]

_MAX_PER_FEED = 4


def is_sunday() -> bool:
    return date.today().weekday() == 6


def fetch() -> list[dict]:
    """Return recent interview experience posts from Reddit.

    Each entry has: title, link, summary, source.
    """
    posts: list[dict] = []
    for subreddit, url in _FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:_MAX_PER_FEED]:
                posts.append({
                    "title":   entry.get("title", "").strip(),
                    "summary": entry.get("summary", entry.get("description", "")).strip()[:600],
                    "source":  subreddit,
                    "link":    entry.get("link", ""),
                })
        except Exception as e:
            print(f"  [interview warn] {subreddit}: {e}")
    print(f"  Interview posts: {len(posts)} found")
    return posts
