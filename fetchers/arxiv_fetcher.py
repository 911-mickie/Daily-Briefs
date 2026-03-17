"""Fetch recent papers from Arxiv API and community-upvoted papers from HF Papers."""
import feedparser
import httpx
from bs4 import BeautifulSoup

_ARXIV_BASE = "http://export.arxiv.org/api/query"
_HF_PAPERS_URL = "https://huggingface.co/papers"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DailyBriefs/2.0)"}

# Arxiv categories and keywords tuned for the user's focus areas
_ARXIV_QUERY = (
    "(cat:cs.LG OR cat:cs.AI OR cat:cs.CL)"
    " AND (ti:\"language model\" OR ti:RAG OR ti:\"multi-agent\""
    " OR ti:transformer OR ti:\"retrieval augmented\" OR ti:agent"
    " OR ti:\"instruction tuning\" OR ti:\"fine-tuning\")"
)


def _fetch_arxiv(max_results: int = 8) -> list[dict]:
    """Query the Arxiv API and return recent matching papers."""
    params = {
        "search_query": _ARXIV_QUERY,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    try:
        resp = httpx.get(_ARXIV_BASE, params=params, timeout=10, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        papers = []
        for entry in feed.entries:
            authors = ", ".join(a.get("name", "") for a in entry.get("authors", [])[:3])
            if len(entry.get("authors", [])) > 3:
                authors += " et al."
            papers.append({
                "title":   entry.get("title", "").replace("\n", " ").strip(),
                "summary": entry.get("summary", "").replace("\n", " ").strip()[:600],
                "source":  "Arxiv",
                "link":    entry.get("link", ""),
                "tier":    3,
                "authors": authors,
            })
        return papers
    except Exception as e:
        print(f"  [arxiv warn] {e}")
        return []


def _fetch_hf_papers(max_results: int = 5) -> list[dict]:
    """Scrape the HuggingFace daily papers page for community-upvoted entries."""
    try:
        resp = httpx.get(_HF_PAPERS_URL, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select('a[href*="/papers/"]')
        seen, papers = set(), []
        for a in links:
            href = a.get("href", "")
            if not href.startswith("/papers/2"):  # only actual paper IDs
                continue
            if href in seen:
                continue
            title = a.get_text(strip=True)
            # Skip empty text and upvote counts / UI strings
            if not title or len(title) < 15:
                continue
            seen.add(href)
            papers.append({
                "title":   title,
                "summary": "",   # no abstract on listing page
                "source":  "HuggingFace Papers",
                "link":    f"https://huggingface.co{href}",
                "tier":    3,
                "authors": "",
            })
            if len(papers) >= max_results:
                break
        return papers
    except Exception as e:
        print(f"  [hf-papers warn] {e}")
        return []


def fetch() -> list[dict]:
    """Return combined list of papers from Arxiv and HF Papers."""
    arxiv  = _fetch_arxiv(max_results=8)
    hf     = _fetch_hf_papers(max_results=5)
    print(f"  Papers: {len(arxiv)} from Arxiv, {len(hf)} from HF Papers")
    return arxiv + hf
