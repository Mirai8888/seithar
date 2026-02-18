"""Threat intelligence relevance scoring."""

DEFAULT_PRIMARY: list[str] = [
    "cognitive warfare", "disinformation", "information operations",
    "influence operations", "psychological operations", "psyops",
    "prompt injection", "jailbreak", "adversarial attack", "red teaming",
    "cognitive security", "propaganda", "social engineering", "deception",
    "manipulation",
]

DEFAULT_SECONDARY: list[str] = [
    "misinformation", "narrative", "social media manipulation",
    "bot network", "troll farm", "astroturfing",
    "prompt engineering", "alignment", "RLHF", "memetic",
    "vulnerability", "exploit", "inoculation", "persuasion",
    "framing", "cognitive bias", "radicalization", "deepfake",
    "LLM safety", "guardrail", "adversarial", "trust",
    "decision-making", "reinforcement learning",
]

PRIMARY_WEIGHT = 3
SECONDARY_WEIGHT = 1
TITLE_MULTIPLIER = 2


def score_item(item, primary_keywords=None, secondary_keywords=None) -> tuple[float, list[str]]:
    """Score an item dict with 'title' and 'summary' keys.

    Returns (score, list_of_matched_keywords).
    """
    if item is None:
        return 0.0, []

    primary = primary_keywords or DEFAULT_PRIMARY
    secondary = secondary_keywords or DEFAULT_SECONDARY

    title = (item.get("title", "") or "").lower()
    summary = (item.get("summary", "") or "").lower()
    text = f"{title} {summary}"

    score = 0.0
    matched = []

    for kw in primary:
        if kw.lower() in text:
            pts = PRIMARY_WEIGHT
            if kw.lower() in title:
                pts *= TITLE_MULTIPLIER
            score += pts
            matched.append(f"+{kw}")

    for kw in secondary:
        if kw.lower() in text:
            pts = SECONDARY_WEIGHT
            if kw.lower() in title:
                pts *= TITLE_MULTIPLIER
            score += pts
            matched.append(kw)

    return score, matched
