"""Stage 1: Score and filter articles using Groq/Llama (fast, cheap).

Sends only title + source + short summary to the LLM — no full_text needed
for relevance scoring. Returns the top N articles with full_text intact.
"""
import json
import os

from groq import Groq

_MODEL = "openai/gpt-oss-120b"

_PROMPT_TEMPLATE = """\
You are a relevance filter for a daily ML/AI brief. The reader is an ML engineer preparing \
for interviews at Microsoft, Amazon, Adobe, and Salesforce.

Score each article 1-10 based on how useful it would be for someone focused on:
- RAG pipelines and retrieval systems
- Multi-agent systems and agentic workflows
- Transformers, LLMs, and production ML systems
- Code understanding and generation (builds a codebase Q&A / coding agent)
- OCR and document intelligence (uses Nemotron Parse, GLM-OCR)
- Vision models and multimodal AI
- Interview prep for ML/AI roles at big tech

Score 9-10: directly relevant to focus areas or breaking news
Score 7-8: solid ML/AI content worth reading
Score 4-6: tangentially related or niche
Score 1-3: off-topic, marketing, or non-technical

Articles:
{articles_block}

Respond with ONLY valid JSON (no markdown):
{{"scores": [{{"id": 1, "score": 8}}, {{"id": 2, "score": 5}}, ...]}}"""


def score_and_filter(articles: list[dict], n: int = 10) -> list[dict]:
    """Score all articles and return the top N by relevance score.

    Falls back to returning the first N articles if scoring fails.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    articles_block = "\n".join(
        f"[{i+1}] [{a['source']}] {a['title']}\n{(a.get('summary') or '')[:200]}"
        for i, a in enumerate(articles)
    )

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": _PROMPT_TEMPLATE.format(articles_block=articles_block)}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2048,
        )
        data = json.loads(response.choices[0].message.content)
        scores: list[dict] = data.get("scores", [])

        # Map id → score (ids are 1-indexed in the prompt)
        score_map = {s["id"]: s["score"] for s in scores if "id" in s and "score" in s}
        scored = sorted(
            enumerate(articles, start=1),
            key=lambda t: score_map.get(t[0], 0),
            reverse=True,
        )
        top = [article for _, article in scored[:n]]
        print(f"  Scorer: kept top {len(top)} of {len(articles)} articles")
        return top

    except Exception as e:
        print(f"  [scorer warn] Scoring failed ({e}), using first {n} articles")
        return articles[:n]
