"""
RSS/Atom feed ingestion for threat intelligence.

Fetches and parses feeds, returning structured IntelItems.

Will contain:
    - _clean_html(text) -> str
    - _parse_date(entry) -> datetime | None
    - fetch_rss_feed(url, source_name, max_items) -> list[IntelItem]

Source: ThreatMouth/threatmouth/collectors/rss.py (simplified, no async)
"""
