"""RSS feed fetcher — three-tier source system with category tagging."""
import feedparser

# ── Feed definitions ───────────────────────────────────────────────────────────
# Each entry: (name, url, tier, category)
# Tier 1 = high-signal expert blogs  (fewer but denser)
# Tier 2 = curated newsletters/aggregators
# Tier 3 = papers / community (handled separately in arxiv_fetcher)
# Category: "ai" (default), "java", "database"

FEEDS: list[tuple[str, str, int, str]] = [
    # ── Tier 0: Individual Researchers (highest signal) ───────────────────────
    ("Lilian Weng",         "https://lilianweng.github.io/index.xml",                    1, "ai"),
    ("Simon Willison",      "https://simonwillison.net/atom/everything/",                1, "ai"),
    ("Chip Huyen",          "https://huyenchip.com/feed.xml",                            1, "ai"),
    ("Sebastian Raschka",   "https://magazine.sebastianraschka.com/feed",               1, "ai"),
    ("Eugene Yan",          "https://eugeneyan.com/rss.xml",                             1, "ai"),
    ("Jay Alammar",         "https://jalammar.github.io/feed.xml",                      1, "ai"),
    ("Cameron Wolfe",       "https://cameronrwolfe.substack.com/feed",                  1, "ai"),
    ("One Useful Thing",    "https://www.oneusefulthing.org/feed",                       1, "ai"),

    # ── Tier 1: Lab / Company blogs ───────────────────────────────────────────
    ("OpenAI Blog",         "https://openai.com/blog/rss.xml",                          1, "ai"),
    ("DeepMind Blog",       "https://www.deepmind.com/blog/rss.xml",                    1, "ai"),
    ("Anthropic",           "https://www.anthropic.com/rss.xml",                        1, "ai"),
    ("HuggingFace",         "https://huggingface.co/blog/feed.xml",                     1, "ai"),
    ("Google AI Blog",      "https://blog.google/technology/ai/rss/",                   1, "ai"),
    ("Microsoft Research",  "https://www.microsoft.com/en-us/research/blog/feed/",      1, "ai"),
    ("NVIDIA Tech Blog",    "https://developer.nvidia.com/blog/feed/",                  1, "ai"),
    ("AWS ML Blog",         "https://aws.amazon.com/blogs/machine-learning/feed/",      1, "ai"),
    ("Amazon Science",      "https://www.amazon.science/index.rss",                     1, "ai"),
    ("Meta AI Eng",         "https://engineering.fb.com/category/ai-research/feed/",    1, "ai"),
    ("Apple ML Research",   "https://machinelearning.apple.com/rss.xml",                1, "ai"),
    ("Netflix Tech Blog",   "https://netflixtechblog.com/feed",                         2, "ai"),
    ("BAIR Blog",           "https://bair.berkeley.edu/blog/feed.xml",                  2, "ai"),

    # ── Tier 2: Newsletters / Aggregators ─────────────────────────────────────
    ("Latent Space",        "https://www.latent.space/feed",                            2, "ai"),
    ("The Batch",           "https://www.deeplearning.ai/the-batch/feed/",              2, "ai"),
    ("Last Week in AI",     "https://lastweekin.ai/feed",                               2, "ai"),
    ("The AiEdge",          "https://theaiedge.substack.com/feed",                      2, "ai"),
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/",                2, "ai"),
    ("TLDR AI",             "https://tldr.tech/rss/ai",                                 2, "ai"),
    ("Import AI",           "https://jack-clark.net/feed/",                             2, "ai"),

# ── Java & Spring Boot ────────────────────────────────────────────────────
    ("Baeldung",          "https://www.baeldung.com/feed",                          2, "java"),
    ("Spring Blog",       "https://spring.io/blog.atom",                            2, "java"),
    ("InfoQ Java",        "https://feed.infoq.com/java",                            2, "java"),
    ("Inside Java",       "https://inside.java/feed.xml",                           2, "java"),
    ("Vlad Mihalcea",     "https://vladmihalcea.com/feed",                          1, "java"),  # NEW — best Java+DB blog
    ("Thorben Janssen",   "https://thorben-janssen.com/feed/",                      1, "java"),  # NEW — JPA/Hibernate depth
    ("Piotr Minkowski",   "https://piotrminkowski.com/feed/",                       1, "java"),  # NEW — Spring Boot microservices
    ("Reflectoring",      "https://reflectoring.io/feed.xml",                       2, "java"),  # NEW — practical Spring patterns
    ("Marco Behler",      "https://www.marcobehler.com/feed.xml",                   1, "java"),  # NEW — opinionated Spring internals
    ("Martin Fowler",     "https://martinfowler.com/feed.atom",                     1, "java"),  # NEW — architecture patterns
    ("Foojay OpenJDK",    "https://foojay.io/feed/",                                2, "java"),  # NEW — Java language evolution
    ("JetBrains Blog",    "https://blog.jetbrains.com/feed/",                       2, "java"),  # NEW — JVM, tooling, Kotlin

    # ── Databases ─────────────────────────────────────────────────────────────
    ("Planet PostgreSQL", "https://planet.postgresql.org/rss20.xml",                2, "database"),
    ("PlanetScale",       "https://planetscale.com/blog/rss.xml",                   2, "database"),
    ("Use The Index Luke","https://use-the-index-luke.com/blog/feed",               2, "database"),
    ("InfoQ Data Eng",    "https://feed.infoq.com/data-engineering",                2, "database"),
    ("Crunchy Data",      "https://www.crunchydata.com/blog/feed.xml",              1, "database"),  # NEW — deep Postgres
    ("Percona Blog",      "https://www.percona.com/blog/feed/",                     1, "database"),  # NEW — MySQL/Postgres perf
    ("Cybertec Postgres", "https://www.cybertec-postgresql.com/en/blog/feed/",      1, "database"),  # NEW — Postgres internals
    ("EnterpriseDB",      "https://www.enterprisedb.com/blog/rss.xml",              2, "database"),  # NEW — Postgres at scale
    ("High Scalability",  "http://feeds.feedburner.com/HighScalability",            1, "database"),  # NEW — system design+DB arch
    ("ByteByteGo",        "https://blog.bytebytego.com/feed",                       1, "database"),  # NEW — interview-aligned system design
    ("Brandur Leach",     "https://brandur.org/articles.atom",                      1, "database"),  # NEW — Postgres reliability deep dives
]

# Max articles pulled per feed per tier
_LIMIT: dict[int, int] = {1: 4, 2: 3}


def fetch_all(category: str | None = None) -> list[dict]:
    """Fetch all feeds and return a flat list of article dicts.

    Each article has: title, summary, source, link, tier, category.
    If category is specified, only fetch feeds matching that category.
    """
    articles: list[dict] = []
    for name, url, tier, cat in FEEDS:
        if category and cat != category:
            continue
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
                    "category": cat,
                })
        except Exception as e:
            print(f"  [warn] Failed to fetch {name}: {e}")
    return articles
