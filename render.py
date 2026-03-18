import html as _html
import os
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

DOCS_DIR = Path("docs")
TEMPLATES_DIR = Path("templates")


def get_github_pages_url() -> str:
    """Derive the GitHub Pages base URL from the Actions environment."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    return "https://911-mickie.github.io/Daily-Briefs"


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)


# Matches lines like: 📰 <b>TOP NEWS</b>  or  📰 TOP NEWS
_SECTION_HEADER_RE = re.compile(
    r'^(?:📰|📄|💡|🔗|💼|🧠|🏆|📊|🎯)\s+(?:<b>)?[A-Z][A-Z &/()\-]+(?:</b>)?(?:\s+\([^)]+\))?$'
)


def _format_content(content: str) -> str:
    """Convert LLM text output (with Telegram HTML tags) into browser-friendly HTML."""
    # Replace Unicode section divider lines
    content = re.sub(r'━+', '<hr class="divider">', content)

    # Collapse 3+ consecutive newlines to 2
    content = re.sub(r'\n{3,}', '\n\n', content)

    blocks = content.split('\n\n')
    parts = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = [l.strip() for l in block.split('\n')]

        # Separate <hr> lines from content lines
        non_hr = [l for l in lines if l and not re.match(r'^<hr\b', l)]
        hr_only = all(re.match(r'^<hr\b', l) for l in lines if l)

        if hr_only:
            # Pure divider block — drop it, section headers imply the break
            continue
        elif len(non_hr) == 1 and _SECTION_HEADER_RE.match(_html.unescape(non_hr[0])):
            # Section header (possibly surrounded by <hr> lines) — strip <b> tags,
            # decode HTML entities (e.g. &amp; → &), badge CSS handles emphasis
            clean = re.sub(r'</?b>', '', _html.unescape(non_hr[0]))
            parts.append(f'<div class="section-header">{clean}</div>')
        else:
            # Regular content block — drop stray <hr> lines that were sandwiched in
            content_lines = [l for l in lines if not re.match(r'^<hr\b', l)]
            block = '<br>\n'.join(content_lines)
            parts.append(f'<p>{block}</p>')

    # Replace arrow separators in Q&A lines with a styled label
    _qa_re = re.compile(r'^<p><b>(Q\d+):</b>\s*(.*?)\s*→\s*(.*?)\s*</p>$')
    processed = []
    for part in parts:
        m = _qa_re.search(part)
        if m:
            q_num, question, answer = m.group(1), m.group(2), m.group(3)
            processed.append(
                f'<div class="qa-card">'
                f'<p class="qa-question">{question}</p>'
                f'<p class="qa-answer">{answer}</p>'
                f'</div>'
            )
        else:
            processed.append(part)
    parts = processed

    # Post-process: wrap news items / concept blocks in card divs
    result = []
    in_card = False
    after_header = False
    for part in parts:
        is_bullet = part.startswith('<p>') and '•' in part[:30]
        is_header = part.startswith('<div class="section-header">')
        is_para = part.startswith('<p>') or part.startswith('<div class="qa-card">')

        if is_bullet:
            if in_card:
                result.append('</div>')
            result.append('<div class="news-card">')
            in_card = True
            after_header = False
            result.append(part)
        elif is_header:
            if in_card:
                result.append('</div>')
                in_card = False
            after_header = True
            result.append(part)
        elif after_header and is_para and not in_card:
            # First paragraph after a section header with no bullet — start a card
            result.append('<div class="news-card">')
            in_card = True
            after_header = False
            result.append(part)
        else:
            result.append(part)

    if in_card:
        result.append('</div>')

    return '\n'.join(result)


def render_daily_brief(content: str, date_str: str) -> str:
    """Render the daily brief HTML for GitHub Pages and write it to docs/<date_str>.html."""
    DOCS_DIR.mkdir(exist_ok=True)
    html = _env().get_template("brief.html.j2").render(
        content=_format_content(content),
        date=date_str,
        base_url=get_github_pages_url(),
    )
    output_path = DOCS_DIR / f"{date_str}.html"
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def render_email_brief(content: str, date_str: str) -> str:
    """Render the email-specific HTML (embedded CSS, absolute URLs). Returns HTML string."""
    html = _env().get_template("email_brief.html.j2").render(
        content=_format_content(content),
        date=date_str,
        base_url=get_github_pages_url(),
    )
    return html


def render_email_brief_from_formatted(formatted_content: str, date_str: str) -> str:
    """Like render_email_brief but skips _format_content (content is already processed)."""
    html = _env().get_template("email_brief.html.j2").render(
        content=formatted_content,
        date=date_str,
        base_url=get_github_pages_url(),
    )
    return html


def render_index() -> None:
    """Rebuild docs/index.html with links to all past briefs."""
    DOCS_DIR.mkdir(exist_ok=True)
    dates = sorted(
        [p.stem for p in DOCS_DIR.glob("????-??-??.html")],
        reverse=True,
    )
    html = _env().get_template("index.html.j2").render(
        dates=dates,
        base_url=get_github_pages_url(),
    )
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
