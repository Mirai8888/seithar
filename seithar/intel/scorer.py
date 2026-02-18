"""Threat intelligence relevance scoring."""

DEFAULT_PRIMARY: list[str] = [
    "cognitive warfare", "disinformation", "information operations",
    "influence operations", "psychological operations", "psyops",
]

DEFAULT_SECONDARY: list[str] = [
    "misinformation", "propaganda", "narrative", "social media manipulation",
    "bot network", "troll farm", "astroturfing",
]


def score_item(item, primary_keywords=None, secondary_keywords=None) -> float:
    raise NotImplementedError
