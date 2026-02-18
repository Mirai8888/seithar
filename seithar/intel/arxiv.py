"""
arXiv paper ingestion and filtering.

Fetches arXiv RSS feeds for cognitive-warfare-adjacent research
and scores papers by relevance.

Will contain:
    - DEFAULT_FEEDS: list of arXiv RSS feed configs
    - ARXIV_PRIMARY / ARXIV_SECONDARY: keyword lists
    - fetch_arxiv_papers(feeds, min_score, state_file) -> list[IntelItem]

Source: seithar-autoprompt/src/ingester.py
"""
