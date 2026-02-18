"""arXiv paper ingestion and filtering."""

DEFAULT_FEEDS: list[dict] = [
    {"url": "https://rss.arxiv.org/rss/cs.CY", "category": "cs.CY"},
    {"url": "https://rss.arxiv.org/rss/cs.SI", "category": "cs.SI"},
]

ARXIV_PRIMARY: list[str] = ["cognitive warfare", "disinformation"]
ARXIV_SECONDARY: list[str] = ["misinformation", "propaganda"]


def fetch_arxiv_papers(feeds=None, min_score=0.0, state_file=None) -> list:
    raise NotImplementedError
