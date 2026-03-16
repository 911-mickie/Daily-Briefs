import os
import feedparser
import google.generativeai as genai
import requests
from datetime import date

# ── RSS feeds ──────────────────────────────────────────────────────────────────
FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://www.anthropic.com/rss.xml",
    "https://paperswithcode.com/trending.rss",
    "https://medium.com/feed/tag/machine-learning",
    "https://www.deeplearning.ai/the-batch/feed/",
]

MAX_ARTICLES = 15


# ── Step 3a: Fetch feeds ───────────────────────────────────────────────────────
def fetch_articles() -> list[dict]:
    articles = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:4]:  # up to 4 per feed
            articles.append({
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip()[:300],
                "source": feed.feed.get("title", url),
            })
        if len(articles) >= MAX_ARTICLES:
            break
    return articles[:MAX_ARTICLES]


# ── Step 3b: Pick today's concept ─────────────────────────────────────────────
def get_todays_topic() -> str:
    with open("topics.txt") as f:
        topics = [line.strip() for line in f if line.strip()]
    day = date.today().day
    return topics[day % len(topics)]


# ── Step 3c: Call Claude ───────────────────────────────────────────────────────
def generate_brief(articles: list[dict], topic: str) -> str:
    articles_block = "\n".join(
        f"[{a['source']}] {a['title']}\n{a['summary']}"
        for a in articles
    )

    prompt = f"""Here are today's articles from ML/AI sources:

{articles_block}

Write a morning brief with exactly these three sections:

1. **📰 NEWS** — Top 3 news items, each with a one-line take on why it matters to an ML practitioner.

2. **📄 PAPER OF THE DAY** — Pick the most interesting research item from the list and explain it in plain English (3-4 sentences max).

3. **💡 CONCEPT REFRESHER** — Today's concept is: {topic}
   Explain it clearly in 3-4 lines, then give 2 likely interview questions with one-line answers.

Keep the entire brief under 450 words. Use plain text, no markdown headers beyond what's shown above."""

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


# ── Step 3d: Send to Telegram ──────────────────────────────────────────────────
def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    today = date.today().strftime("%B %-d")
    message = f"🧠 *ML Daily Brief — {today}*\n\n{text}"

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
        timeout=10,
    )
    resp.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching articles...")
    articles = fetch_articles()
    print(f"  Got {len(articles)} articles")

    topic = get_todays_topic()
    print(f"  Today's concept: {topic}")

    print("Generating brief with Claude...")
    brief = generate_brief(articles, topic)
    print("  Done.\n")
    print(brief)

    print("\nSending to Telegram...")
    send_telegram(brief)
    print("  Delivered.")
