"""RSS feed fetcher — three-tier source system."""
import feedparser

# ── Feed definitions ───────────────────────────────────────────────────────────
# Each entry: (name, url, tier)
# Tier 1 = high-signal expert blogs  (fewer but denser)
# Tier 2 = curated newsletters/aggregators
# Tier 3 = papers / community (handled separately in arxiv_fetcher)

FEEDS: list[tuple[str, str, int]] = [
    # ── Tier 1: High-signal blogs ──────────────────────────────────────────────
    ("Lilian Weng",     "https://lilianweng.github.io/index.xml",              1),
    ("Simon Willison",  "https://simonwillison.net/atom/everything/",          1),
    ("Chip Huyen",      "https://huyenchip.com/feed.xml",                      1),
    ("OpenAI Blog",     "https://openai.com/blog/rss.xml",                     1),
    ("DeepMind Blog",   "https://www.deepmind.com/blog/rss.xml",               1),
    ("Meta AI Eng",     "https://engineering.fb.com/category/ai-research/feed/", 1),
    ("Latent Space",    "https://www.latent.space/feed",                       1),
    ("HuggingFace",     "https://huggingface.co/blog/feed.xml",                1),
    ("Anthropic",       "https://www.anthropic.com/rss.xml",                   1),

    # ── Tier 2: Curated newsletters / aggregators ──────────────────────────────
    ("The Batch",       "https://www.deeplearning.ai/the-batch/feed/",         2),
    ("TLDR AI",         "https://tldr.tech/rss/ai",                            2),
    ("Import AI",       "https://jack-clark.net/feed/",                        2),
    ("Medium ML",       "https://medium.com/feed/tag/machine-learning",        2),
    ("Papers w/ Code",  "https://paperswithcode.com/trending.rss",             2),
]

# Max articles pulled per feed per tier
_LIMIT: dict[int, int] = {1: 4, 2: 3}


def fetch_all() -> list[dict]:
    """Fetch all feeds and return a flat list of article dicts.

    Each article has: title, summary, source, link, tier.
    """
    articles: list[dict] = []
    for name, url, tier in FEEDS:
        try:
            feed = feedparser.parse(url)
            limit = _LIMIT.get(tier, 3)
            for entry in feed.entries[:limit]:
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "summary": entry.get("summary", entry.get("description", "")).strip()[:500],
                    "source":  feed.feed.get("title", name),
                    "link":    entry.get("link", ""),
                    "tier":    tier,
                })
        except Exception as e:
            print(f"  [warn] Failed to fetch {name}: {e}")
    return articles
