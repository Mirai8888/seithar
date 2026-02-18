"""RSS/Atom feed ingestion for threat intelligence."""
import re


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def fetch_rss_feed(url: str, source_name: str = "unknown", max_items: int = 50) -> list:
    """Fetch an RSS feed and return list of item dicts."""
    import feedparser
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "id": entry.get("id", entry.get("link", "")),
            "title": entry.get("title", "").strip(),
            "summary": _clean_html(entry.get("summary", ""))[:500],
            "link": entry.get("link", ""),
            "source": source_name,
        })
    return items
