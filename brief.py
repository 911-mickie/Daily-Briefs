import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from datetime import date
import render
from fetchers import rss_fetcher, arxiv_fetcher, content_enricher, interview_fetcher
from pipeline import scorer, synthesizer
import db


# ── Pick today's concept ───────────────────────────────────────────────────────
def get_todays_concept() -> str:
    with open("topics.txt") as f:
        topics = [line.strip() for line in f if line.strip()]
    return topics[date.today().day % len(topics)]


# ── Send email with full HTML brief ───────────────────────────────────────────
def send_email_brief(html_content: str, date_str: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipients = [r.strip() for r in os.environ["GMAIL_RECIPIENTS"].split(",") if r.strip()]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🧠 ML Daily Brief — {date_str}"
            msg["From"] = gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(html_content, "html"))
            server.sendmail(gmail_user, [recipient], msg.as_string())
            print(f"  Email sent to: {recipient}")


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
    # ── 0. Init DB ─────────────────────────────────────────────────────────────
    db.init_db()
    db.purge_old()

    # ── 1. Ingest ──────────────────────────────────────────────────────────────
    print("Fetching RSS articles...")
    ai_articles = rss_fetcher.fetch_all(category="ai")
    print(f"  Got {len(ai_articles)} AI/ML RSS articles")

    print("Fetching Java & Database articles...")
    java_db_articles = rss_fetcher.fetch_all(category="java") + rss_fetcher.fetch_all(category="database")
    print(f"  Got {len(java_db_articles)} Java/DB articles")

    print("Fetching papers (Arxiv + HF Papers)...")
    ai_articles += arxiv_fetcher.fetch()

    # ── 1b. Deduplicate ─────────────────────────────────────────────────────────
    print("Removing previously used articles...")
    ai_articles = db.filter_unseen(ai_articles)
    java_db_articles = db.filter_unseen(java_db_articles)
    print(f"  After dedup: {len(ai_articles)} AI + {len(java_db_articles)} Java/DB articles")

    interview_posts = None
    if interview_fetcher.is_sunday():
        print("Sunday — fetching interview experiences...")
        interview_posts = interview_fetcher.fetch()

    print("Enriching articles with full text...")
    ai_articles = content_enricher.enrich(ai_articles)
    java_db_articles = content_enricher.enrich(java_db_articles)
    print(f"  Total: {len(ai_articles)} AI + {len(java_db_articles)} Java/DB articles enriched")

    # ── 2. Filter & Score ──────────────────────────────────────────────────────
    print("Scoring and filtering AI articles...")
    top_articles = scorer.score_and_filter(ai_articles, n=15)

    # Java/DB articles are from curated feeds — take the most recent ones
    java_articles = [a for a in java_db_articles if a.get("category") == "java"][:5]
    db_articles = [a for a in java_db_articles if a.get("category") == "database"][:5]
    print(f"  Java: {len(java_articles)}, Database: {len(db_articles)} articles selected")

    # ── 3. Synthesize ──────────────────────────────────────────────────────────
    concept = get_todays_concept()
    print(f"  Today's concept: {concept}")

    print("Generating brief with Claude Sonnet...")
    brief = synthesizer.generate(
        articles=top_articles,
        concept=concept,
        interview_posts=interview_posts,
        java_articles=java_articles,
        db_articles=db_articles,
    )
    print("  Done.\n")
    print(brief)

    # ── 3b. Record used articles ─────────────────────────────────────────────
    db.mark_used(top_articles + java_articles + db_articles)
    print(f"  Saved {len(top_articles) + len(java_articles) + len(db_articles)} articles to content history")

    # ── 4. Deliver ─────────────────────────────────────────────────────────────
    date_str = date.today().strftime("%Y-%m-%d")

    # Save raw brief text so it can be re-rendered (e.g. for email testing)
    render.DOCS_DIR.mkdir(exist_ok=True)
    (render.DOCS_DIR / f"{date_str}.txt").write_text(brief, encoding="utf-8")

    print(f"\nRendering HTML to docs/{date_str}.html ...")
    render.render_daily_brief(brief, date_str)
    render.render_index()
    print("  Done.")

    pages_url = render.get_github_pages_url()
    brief_url = f"{pages_url}/{date_str}.html" if pages_url else ""

    # print("\nSending Telegram teaser...")
    # send_telegram_teaser(concept, brief_url)
    # print("  Delivered.")

    print("\nSending email brief...")
    email_html = render.render_email_brief(brief, date_str)
    send_email_brief(email_html, date_str)
    print("  Delivered.")
