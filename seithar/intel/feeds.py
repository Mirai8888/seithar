"""RSS/Atom feed ingestion for threat intelligence."""


def _clean_html(text: str) -> str:
    raise NotImplementedError


def fetch_rss_feed(url: str, source_name: str = "unknown", max_items: int = 50) -> list:
    raise NotImplementedError
