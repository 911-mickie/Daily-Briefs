"""Stage 2: Generate the full brief using Claude Sonnet.

Uses the Anthropic SDK directly (not LangChain).
Receives pre-filtered top articles with full_text and focus areas
to produce a practitioner-focused daily brief.
"""
import json
import os
from pathlib import Path

import anthropic

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 10240

_SYSTEM_TEMPLATE = """\
You write a daily morning brief for a mixed technical audience. \
The primary audience is an AI/ML practitioner who cares about:

{focus_areas}

The brief also includes sections for a Java/Spring Boot and Database practitioner.

Your job is to take today's top articles and write a brief that feels curated for \
practitioners who ship real systems — not generic news, but content filtered and interpreted \
for engineers who build production systems.

Tone: direct, technically precise, zero filler. Write for practitioners, not students.\
"""

_USER_TEMPLATE = """\
Here are today's top articles (each has a URL — use EXACT URLs only, never invent or shorten them):

{articles_block}

Write the brief using HTML formatting. Use ONLY these tags:
- <b>text</b> for bold
- <i>text</i> for italic
- <a href="URL">text</a> for links — exact URLs from the list above only

Structure exactly like this:

━━━━━━━━━━━━━━━━━━━
📰 <b>TOP NEWS</b>
━━━━━━━━━━━━━━━━━━━

Pick the 5 most important news/product/announcement items (not papers). For each:

• <b><a href="EXACT_URL">Title</a></b>
<i>What happened:</i> 2-3 sentences of substance — be specific, include numbers or technical details where available.
<i>Why it matters:</i> One sharp sentence for an ML practitioner.
<i>Interview angle:</i> One sentence on how this connects to ML interviews or production systems.

━━━━━━━━━━━━━━━━━━━
📄 <b>PAPERS & RESEARCH</b>
━━━━━━━━━━━━━━━━━━━

Pick the 5 most relevant research papers or technical findings. For each:

• <b><a href="EXACT_URL">Paper title</a></b>
3-4 sentences: what problem they tackled, their approach, key result, and why it matters — in plain English.
<i>Interview angle:</i> One sentence on the concept an interviewer might probe here.

━━━━━━━━━━━━━━━━━━━
💡 <b>CONCEPT REFRESHER</b>
━━━━━━━━━━━━━━━━━━━

Today's concept: {concept}

<b>{concept}</b>
4-5 sentences: definition, intuition, when it matters in practice, one common misconception.
<b>Q1:</b> [sharp interview question] → <i>[one-line answer]</i>
<b>Q2:</b> [sharp interview question] → <i>[one-line answer]</i>
<b>Q3:</b> [deeper follow-up question] → <i>[one-line answer]</i>
{interview_section}
━━━━━━━━━━━━━━━━━━━
🔗 <b>QUICK LINKS</b>
━━━━━━━━━━━━━━━━━━━

List the remaining articles as one-line bullets with links — just title and one clause explaining relevance.

{java_db_sections}Rules:
- Only use <b>, <i>, <a href=""> tags — nothing else
- No markdown (**bold**, ## headers, [text](url))
- Use only exact URLs from the article list — never invent or shorten URLs
- Be specific and technical, not generic\
"""

_JAVA_DB_SECTION_TEMPLATE = """\
━━━━━━━━━━━━━━━━━━━
☕ <b>JAVA & SPRING BOOT</b>
━━━━━━━━━━━━━━━━━━━

Here are the latest Java/Spring Boot articles:

{java_block}

Pick the 3-4 most useful items. For each:

• <b><a href="EXACT_URL">Title</a></b>
<i>What's new:</i> 2-3 sentences — be specific about the feature, API change, or technique.
<i>Why it matters:</i> One sentence on practical impact for a Spring Boot developer.

━━━━━━━━━━━━━━━━━━━
🗄️ <b>DATABASE CORNER</b>
━━━━━━━━━━━━━━━━━━━

Here are the latest database articles:

{db_block}

Pick the 3-4 most useful items. For each:

• <b><a href="EXACT_URL">Title</a></b>
<i>What's new:</i> 2-3 sentences — be specific about the concept, optimization, or feature.
<i>Practical takeaway:</i> One sentence on what a developer should do differently.

"""

_INTERVIEW_SECTION_TEMPLATE = """\

━━━━━━━━━━━━━━━━━━━
🎯 <b>INTERVIEW SPOTLIGHT</b> (this week)
━━━━━━━━━━━━━━━━━━━

Community interview experiences this week:

{posts_block}

Identify 2-3 key questions or patterns seen across these posts. For each:
• <b>What was asked:</b> [the question or pattern]
<i>How to approach it:</i> One sharp, actionable sentence.

"""


def _load_json(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def generate(
    articles: list[dict],
    concept: str,
    interview_posts: list[dict] | None = None,
    java_articles: list[dict] | None = None,
    db_articles: list[dict] | None = None,
    user_context_path: str = "user_context.json",
) -> str:
    """Generate the brief using Claude Sonnet. Returns the formatted HTML-compatible string."""
    ctx = _load_json(user_context_path)

    # Build system prompt
    system = _SYSTEM_TEMPLATE.format(
        focus_areas="\n".join(f"- {f}" for f in ctx.get("focus_areas", [])),
    )

    # Build articles block (include full_text, capped per article)
    articles_block = "\n\n".join(
        f"[{i+1}] [{a['source']}] {a['title']}\nURL: {a['link']}\n"
        + (a.get("full_text") or a.get("summary", ""))[:2_000]
        for i, a in enumerate(articles)
    )

    # Build optional interview section
    interview_section = ""
    if interview_posts:
        posts_block = "\n\n".join(
            f"[{p['source']}] {p['title']}\nURL: {p['link']}\n{p.get('summary', '')[:400]}"
            for p in interview_posts
        )
        interview_section = _INTERVIEW_SECTION_TEMPLATE.format(posts_block=posts_block)

    # Build optional Java & Database sections
    java_db_sections = ""
    if java_articles or db_articles:
        java_block = "\n\n".join(
            f"[{i+1}] [{a['source']}] {a['title']}\nURL: {a['link']}\n"
            + (a.get("full_text") or a.get("summary", ""))[:1_500]
            for i, a in enumerate(java_articles or [])
        ) or "No Java articles today."

        db_block = "\n\n".join(
            f"[{i+1}] [{a['source']}] {a['title']}\nURL: {a['link']}\n"
            + (a.get("full_text") or a.get("summary", ""))[:1_500]
            for i, a in enumerate(db_articles or [])
        ) or "No database articles today."

        java_db_sections = _JAVA_DB_SECTION_TEMPLATE.format(
            java_block=java_block,
            db_block=db_block,
        )

    user_msg = _USER_TEMPLATE.format(
        articles_block=articles_block,
        concept=concept,
        interview_section=interview_section,
        java_db_sections=java_db_sections,
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text
