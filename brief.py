import os
import feedparser
import requests
from datetime import date
from langchain_core.messages import HumanMessage

# ── RSS feeds ──────────────────────────────────────────────────────────────────
FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://www.anthropic.com/rss.xml",
    "https://paperswithcode.com/trending.rss",
    "https://medium.com/feed/tag/machine-learning",
    "https://www.deeplearning.ai/the-batch/feed/",
]

MAX_ARTICLES = 25


# ── Step 1: Fetch feeds ────────────────────────────────────────────────────────
def fetch_articles() -> list[dict]:
    articles = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            articles.append({
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip()[:400],
                "source": feed.feed.get("title", url),
                "link": entry.get("link", ""),
            })
    return articles[:MAX_ARTICLES]


# ── Step 2: Pick today's concept ──────────────────────────────────────────────
def get_todays_topics() -> list[str]:
    with open("topics.txt") as f:
        topics = [line.strip() for line in f if line.strip()]
    day = date.today().day
    return [topics[day % len(topics)]]


# ── Step 3: Build LLM client ──────────────────────────────────────────────────
def get_llm():
    provider = os.environ.get("MODEL_PROVIDER", "groq").lower()

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=os.environ["GROQ_API_KEY"],
            model="llama-3.3-70b-versatile",
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=os.environ["GEMINI_API_KEY"],
            model="gemini-2.0-flash",
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="claude-haiku-4-5-20251001",
        )
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {provider}. Use 'groq', 'gemini', or 'anthropic'.")


# ── Step 4: Call LLM ──────────────────────────────────────────────────────────
def generate_brief(articles: list[dict], topics: list[str]) -> str:
    articles_block = "\n".join(
        f"[{i+1}] [{a['source']}] {a['title']}\nURL: {a['link']}\n{a['summary']}"
        for i, a in enumerate(articles)
    )

    concepts_block = "\n".join(f"- {t}" for t in topics)

    prompt = f"""You are writing a daily ML/AI morning brief for a machine learning practitioner preparing for interviews and staying current with the field.

Here are today's articles (each has a URL — you MUST use the exact URLs provided):

{articles_block}

Write the brief using Telegram HTML formatting. Use these exact tags only:
- <b>text</b> for bold
- <i>text</i> for italic
- <a href="URL">text</a> for clickable links — use the EXACT URLs from the articles above, never make up URLs

Structure the brief exactly like this:

━━━━━━━━━━━━━━━━━━━
📰 <b>TOP NEWS</b>
━━━━━━━━━━━━━━━━━━━

Pick the 3 most interesting news/product/announcement items (not research papers). For each:

• <b><a href="EXACT_URL">Title</a></b>
<i>Why it matters:</i> One sharp sentence for an ML practitioner.

━━━━━━━━━━━━━━━━━━━
📄 <b>PAPERS & RESEARCH</b>
━━━━━━━━━━━━━━━━━━━

Pick the 3 most interesting research papers or technical findings. For each:

• <b><a href="EXACT_URL">Paper title</a></b>
2-3 sentences: what it does, why it matters, in plain English.

━━━━━━━━━━━━━━━━━━━
💡 <b>CONCEPT REFRESHER</b>
━━━━━━━━━━━━━━━━━━━

Today's concept: {concepts_block}

<b>[Concept Name]</b>
3-4 clear sentences explaining it. Then:
<b>Q1:</b> [interview question] → <i>[one-line answer]</i>
<b>Q2:</b> [interview question] → <i>[one-line answer]</i>

Rules:
- Only use <b>, <i>, <a href=""> HTML tags — nothing else
- Do NOT use markdown (**bold**, [text](url), ## headers)
- Never invent or modify URLs — only use exact URLs from the article list above
- Writing must be punchy and specific, not generic filler"""

    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


# ── Step 5: Send to Telegram ──────────────────────────────────────────────────
def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    today = date.today().strftime("%B %-d")
    header = f"🧠 <b>ML Daily Brief — {today}</b>\n\n"

    payload = {
        "chat_id": chat_id,
        "text": header + text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=10,
    )

    if not resp.ok:
        print(f"Telegram error: {resp.json()}")
        # Fallback: strip all HTML tags and send as plain text
        import re
        plain = re.sub(r"<[^>]+>", "", header + text)
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": plain, "disable_web_page_preview": True},
            timeout=10,
        )
        resp.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    provider = os.environ.get("MODEL_PROVIDER", "groq")
    print(f"Using provider: {provider}")

    print("Fetching articles...")
    articles = fetch_articles()
    print(f"  Got {len(articles)} articles")

    topics = get_todays_topics()
    print(f"  Today's concepts: {', '.join(topics)}")

    print("Generating brief...")
    brief = generate_brief(articles, topics)
    print("  Done.\n")
    print(brief)

    print("\nSending to Telegram...")
    send_telegram(brief)
    print("  Delivered.")
