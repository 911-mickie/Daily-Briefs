import os
import requests
from datetime import date
import render
from fetchers import rss_fetcher, arxiv_fetcher, content_enricher, interview_fetcher
from pipeline import scorer, synthesizer


# ── Pick today's concept ───────────────────────────────────────────────────────
def get_todays_concept() -> str:
    with open("topics.txt") as f:
        topics = [line.strip() for line in f if line.strip()]
    return topics[date.today().day % len(topics)]


# ── Send Telegram teaser with link ────────────────────────────────────────────
def send_telegram_teaser(concept: str, brief_url: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    today = date.today().strftime("%B %-d")

    text = (
        f"🧠 <b>ML Daily Brief — {today}</b>\n\n"
        f"Today's concept: <b>{concept}</b>\n\n"
    )
    text += f"Read the full brief 👉 {brief_url}" if brief_url else "Brief generated — check the archive."

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=10,
    )
    if not resp.ok:
        print(f"Telegram error: {resp.json()}")
        resp.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── 1. Ingest ──────────────────────────────────────────────────────────────
    print("Fetching RSS articles...")
    articles = rss_fetcher.fetch_all()
    print(f"  Got {len(articles)} RSS articles")

    print("Fetching papers (Arxiv + HF Papers)...")
    articles += arxiv_fetcher.fetch()

    interview_posts = None
    if interview_fetcher.is_sunday():
        print("Sunday — fetching interview experiences...")
        interview_posts = interview_fetcher.fetch()

    print("Enriching articles with full text...")
    articles = content_enricher.enrich(articles)
    print(f"  Total: {len(articles)} articles enriched")

    # ── 2. Filter & Score ──────────────────────────────────────────────────────
    print("Scoring and filtering...")
    top_articles = scorer.score_and_filter(articles, n=15)

    # ── 3. Synthesize ──────────────────────────────────────────────────────────
    concept = get_todays_concept()
    print(f"  Today's concept: {concept}")

    print("Generating brief with Claude Sonnet...")
    brief = synthesizer.generate(
        articles=top_articles,
        concept=concept,
        interview_posts=interview_posts,
    )
    print("  Done.\n")
    print(brief)

    # ── 4. Deliver ─────────────────────────────────────────────────────────────
    date_str = date.today().strftime("%Y-%m-%d")
    print(f"\nRendering HTML to docs/{date_str}.html ...")
    render.render_daily_brief(brief, date_str)
    render.render_index()
    print("  Done.")

    pages_url = render.get_github_pages_url()
    brief_url = f"{pages_url}/{date_str}.html" if pages_url else ""

    print("\nSending Telegram teaser...")
    send_telegram_teaser(concept, brief_url)
    print("  Delivered.")
