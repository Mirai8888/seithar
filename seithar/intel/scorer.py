"""
Threat intelligence relevance scoring.

Scores IntelItems against keyword profiles for cognitive warfare relevance.

Will contain:
    - DEFAULT_PRIMARY: list[str] — high-value cognitive warfare keywords
    - DEFAULT_SECONDARY: list[str] — supporting keywords
    - score_item(item, primary_keywords, secondary_keywords, ...) -> float

Sources: ThreatMouth/threatmouth/scorer.py, seithar-autoprompt/src/ingester.py
"""
