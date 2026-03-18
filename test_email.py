"""Quick test: send the most recent brief to yourself only."""
import os

# Load .env manually
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Override recipients to just yourself for testing
os.environ["GMAIL_RECIPIENTS"] = os.environ["GMAIL_USER"]

from pathlib import Path
from bs4 import BeautifulSoup
import render
from brief import send_email_brief

# Prefer raw .txt brief (available after running brief.py with latest code)
txt_files = sorted(Path("docs").glob("????-??-??.txt"))
html_files = sorted(Path("docs").glob("????-??-??.html"),
                    key=lambda p: p.stem)
html_files = [p for p in html_files if p.stem != "index"]

if txt_files:
    latest = txt_files[-1]
    date_str = latest.stem
    print(f"Using raw brief text: {latest}")
    email_html = render.render_email_brief(latest.read_text(encoding="utf-8"), date_str)
elif html_files:
    latest = html_files[-1]
    date_str = latest.stem
    print(f"No .txt found — extracting content from: {latest}")
    soup = BeautifulSoup(latest.read_text(encoding="utf-8"), "html.parser")
    main = soup.find("main")
    formatted_content = main.decode_contents() if main else "<p>Could not extract content.</p>"
    email_html = render.render_email_brief_from_formatted(formatted_content, date_str)
else:
    print("No brief files found in docs/. Run brief.py first.")
    exit(1)

print(f"Sending to {os.environ['GMAIL_RECIPIENTS']} ...")
send_email_brief(email_html, date_str)
print("Done. Check your inbox.")
