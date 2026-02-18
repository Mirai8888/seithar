"""arXiv paper ingestion and filtering."""
from datetime import datetime, timezone

from seithar.intel.feeds import fetch_rss_feed
from seithar.intel.scorer import score_item, DEFAULT_PRIMARY, DEFAULT_SECONDARY

DEFAULT_FEEDS: list[dict] = [
    {"url": "https://export.arxiv.org/rss/cs.CL", "category": "cs.CL"},
    {"url": "https://export.arxiv.org/rss/cs.AI", "category": "cs.AI"},
    {"url": "https://export.arxiv.org/rss/cs.CR", "category": "cs.CR"},
    {"url": "https://export.arxiv.org/rss/cs.CY", "category": "cs.CY"},
    {"url": "https://export.arxiv.org/rss/cs.MA", "category": "cs.MA"},
]

ARXIV_PRIMARY: list[str] = DEFAULT_PRIMARY
ARXIV_SECONDARY: list[str] = DEFAULT_SECONDARY


def fetch_arxiv_papers(feeds=None, min_score: float = 2.0, state_file=None) -> list:
    """Fetch papers from arXiv RSS feeds, score, and return sorted results."""
    feeds = feeds or DEFAULT_FEEDS
    results = []

    for feed_cfg in feeds:
        url = feed_cfg["url"]
        name = feed_cfg.get("category", feed_cfg.get("name", "unknown"))
        try:
            items = fetch_rss_feed(url, source_name=name, max_items=100)
        except Exception as e:
            print(f"  [warn] Failed to fetch {name}: {e}")
            continue

        for item in items:
            sc, matched = score_item(item)
            if sc >= min_score:
                results.append({
                    "title": item["title"],
                    "link": item["link"],
                    "source": name,
                    "summary": item.get("summary", "")[:300],
                    "score": sc,
                    "matched_keywords": matched,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
