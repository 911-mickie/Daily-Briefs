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
    return ""


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)


def _format_content(content: str) -> str:
    """Convert LLM text output (with Telegram HTML tags) into browser-friendly HTML."""
    # Replace Unicode section divider lines with a styled <hr>
    content = re.sub(r'━+', '<hr class="divider">', content)
    # Newlines → <br> so layout works without white-space:pre-wrap
    content = content.replace('\n', '<br>\n')
    return content


def render_daily_brief(content: str, date_str: str) -> str:
    """Render the daily brief HTML and write it to docs/<date_str>.html.

    Returns the file path written.
    """
    DOCS_DIR.mkdir(exist_ok=True)
    html = _env().get_template("brief.html.j2").render(
        content=_format_content(content),
        date=date_str,
        base_url=get_github_pages_url(),
    )
    output_path = DOCS_DIR / f"{date_str}.html"
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


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
