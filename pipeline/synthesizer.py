"""Stage 2: Generate the full brief using Claude Sonnet.

Uses the Anthropic SDK directly (not LangChain).
Receives pre-filtered top articles with full_text, user context, and
current projects to produce a personalized, well-written brief.
"""
import json
import os
from pathlib import Path

import anthropic

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192

_SYSTEM_TEMPLATE = """\
You write a daily ML/AI morning brief for a specific reader. Here is who they are:

Role: {role}
Interview targets: {companies}
Focus areas: {focus_areas}

Their active projects:
{projects}

Your job is to take today's top articles and write a brief that feels personally curated — \
not generic ML news, but content interpreted through this person's lens. For every item, \
include one "connection to their work" observation where relevant.

Tone: direct, technically precise, zero filler. Write for a practitioner, not a student.\
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

Rules:
- Only use <b>, <i>, <a href=""> tags — nothing else
- No markdown (**bold**, ## headers, [text](url))
- Use only exact URLs from the article list — never invent or shorten URLs
- Be specific and technical, not generic\
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
    user_context_path: str = "user_context.json",
    current_projects_path: str = "current_projects.json",
) -> str:
    """Generate the brief using Claude Sonnet. Returns the formatted HTML-compatible string."""
    ctx = _load_json(user_context_path)
    proj = _load_json(current_projects_path)

    # Build system prompt
    projects_block = "\n".join(
        f"- {p['name']}: {p['description']}"
        for p in proj.get("projects", [])
    )
    system = _SYSTEM_TEMPLATE.format(
        role=ctx.get("role", "ML Engineer"),
        companies=", ".join(ctx.get("interview_target_companies", [])),
        focus_areas="\n".join(f"- {f}" for f in ctx.get("focus_areas", [])),
        projects=projects_block or "No active projects listed.",
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

    user_msg = _USER_TEMPLATE.format(
        articles_block=articles_block,
        concept=concept,
        interview_section=interview_section,
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text
