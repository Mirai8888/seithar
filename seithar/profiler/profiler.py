"""Substrate profiler.

Analyzes text for psychological patterns, communication style,
thematic focus, and cognitive vulnerability indicators.
Maps to SCT vulnerability surface.
"""
import re
import math
from dataclasses import dataclass, asdict
from collections import Counter

from seithar.core.taxonomy import SCT_TAXONOMY


@dataclass
class ProfileResult:
    themes: list
    sentiment: float
    emotional_words: list
    vulnerabilities: list
    style: dict
    sct_susceptibility: list


# Sentiment lexicon (minimal, no deps)
_POSITIVE = {
    "good", "great", "excellent", "love", "best", "happy", "wonderful",
    "amazing", "beautiful", "perfect", "brilliant", "fantastic", "strong",
    "success", "win", "hope", "trust", "safe", "free", "truth",
    "progress", "improve", "gain", "positive", "right", "fair",
}

_NEGATIVE = {
    "bad", "terrible", "hate", "worst", "angry", "horrible", "awful",
    "ugly", "broken", "stupid", "fail", "fear", "danger", "threat",
    "loss", "wrong", "corrupt", "lie", "fake", "evil", "crisis",
    "destroy", "attack", "kill", "death", "war", "enemy", "toxic",
}

_EMOTIONAL = {
    "urgent", "shocking", "outrage", "terrifying", "horrifying",
    "disgusting", "incredible", "unbelievable", "devastating",
    "explosive", "furious", "heartbreaking", "alarming", "desperate",
    "betrayed", "abandoned", "helpless", "trapped", "doomed",
    "euphoric", "ecstatic", "passionate", "obsessed", "consumed",
}

# Identity markers
_IDENTITY_MARKERS = {
    "we", "us", "our", "them", "they", "those people", "real",
    "true", "patriot", "believer", "community", "movement",
}

# Authority markers
_AUTHORITY_MARKERS = {
    "expert", "professor", "doctor", "scientist", "research",
    "study", "data", "evidence", "proven", "official",
}

# Urgency markers
_URGENCY_MARKERS = {
    "now", "immediately", "urgent", "breaking", "deadline",
    "hurry", "quick", "fast", "limited", "expire",
}

# Conformity markers
_CONFORMITY_MARKERS = {
    "everyone", "nobody", "millions", "trending", "viral",
    "mainstream", "popular", "movement", "majority", "consensus",
}


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


def _extract_themes(tokens: list[str], top_n: int = 8) -> list[tuple[str, int]]:
    """Extract top themes by frequency, excluding stopwords."""
    stopwords = {
        "the", "be", "to", "of", "and", "in", "that", "have", "it",
        "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say",
        "her", "she", "or", "an", "will", "my", "one", "all", "would",
        "there", "their", "what", "so", "up", "out", "if", "about",
        "who", "get", "which", "go", "me", "when", "make", "can",
        "like", "time", "no", "just", "him", "know", "take", "people",
        "into", "year", "your", "some", "could", "them", "see",
        "other", "than", "then", "now", "look", "only", "come",
        "its", "over", "think", "also", "back", "after", "use",
        "two", "how", "our", "work", "first", "well", "way", "even",
        "new", "want", "because", "any", "these", "give", "day",
        "most", "us", "is", "are", "was", "were", "been", "has",
        "had", "did", "does", "am",
    }
    filtered = [t for t in tokens if t not in stopwords and len(t) > 2]
    counts = Counter(filtered)
    return counts.most_common(top_n)


def _compute_sentiment(tokens: list[str]) -> float:
    """Compute sentiment score (-1.0 to 1.0)."""
    if not tokens:
        return 0.0
    pos = sum(1 for t in tokens if t in _POSITIVE)
    neg = sum(1 for t in tokens if t in _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


def _find_emotional_words(tokens: list[str]) -> list[str]:
    """Find emotionally charged words."""
    return sorted(set(t for t in tokens if t in _EMOTIONAL))


def _compute_style(text: str, tokens: list[str]) -> dict:
    """Analyze communication style."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    
    exclamations = text.count('!')
    questions = text.count('?')
    caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
    
    unique_ratio = len(set(tokens)) / max(len(tokens), 1)
    
    return {
        "avg_sentence_length": round(avg_sentence_len, 1),
        "sentence_count": len(sentences),
        "exclamation_density": round(exclamations / max(len(sentences), 1), 2),
        "question_density": round(questions / max(len(sentences), 1), 2),
        "caps_emphasis": caps_words,
        "vocabulary_diversity": round(unique_ratio, 2),
    }


def _assess_vulnerabilities(tokens: list[str], sentiment: float, style: dict) -> list[dict]:
    """Map text patterns to SCT vulnerability surface."""
    vulns = []
    token_set = set(tokens)
    
    # SCT-001: Emotional Hijacking susceptibility
    emotional_count = len([t for t in tokens if t in _EMOTIONAL])
    if emotional_count > 0 or style.get("exclamation_density", 0) > 0.3:
        vulns.append({
            "code": "SCT-001",
            "name": "Emotional Hijacking",
            "indicator": "high emotional word density or exclamation usage",
            "score": min(1.0, round(emotional_count / max(len(tokens), 1) * 20 + style.get("exclamation_density", 0), 2))
        })
    
    # SCT-002: Information Asymmetry
    authority_count = len(token_set & _AUTHORITY_MARKERS)
    if authority_count > 0:
        vulns.append({
            "code": "SCT-002",
            "name": "Information Asymmetry Exploitation",
            "indicator": "authority/evidence language without specific citations",
            "score": round(min(1.0, authority_count * 0.25), 2)
        })
    
    # SCT-004: Social Proof
    conformity_count = len(token_set & _CONFORMITY_MARKERS)
    if conformity_count > 0:
        vulns.append({
            "code": "SCT-004",
            "name": "Social Proof Manipulation",
            "indicator": "consensus/popularity language",
            "score": round(min(1.0, conformity_count * 0.3), 2)
        })
    
    # SCT-005: Identity Targeting
    identity_count = len(token_set & _IDENTITY_MARKERS)
    if identity_count >= 2:
        vulns.append({
            "code": "SCT-005",
            "name": "Identity Targeting",
            "indicator": "in-group/out-group framing",
            "score": round(min(1.0, identity_count * 0.2), 2)
        })
    
    # SCT-006: Temporal Manipulation
    urgency_count = len(token_set & _URGENCY_MARKERS)
    if urgency_count > 0:
        vulns.append({
            "code": "SCT-006",
            "name": "Temporal Manipulation",
            "indicator": "urgency/deadline language",
            "score": round(min(1.0, urgency_count * 0.3), 2)
        })
    
    # SCT-011: Trust Erosion
    distrust_words = {"fake", "lie", "corrupt", "conspiracy", "cover", "hidden"}
    distrust_count = len(token_set & distrust_words)
    if distrust_count > 0 or sentiment < -0.5:
        vulns.append({
            "code": "SCT-011",
            "name": "Trust Infrastructure Destruction",
            "indicator": "institutional distrust language or extreme negative sentiment",
            "score": round(min(1.0, distrust_count * 0.3 + max(0, -sentiment * 0.5)), 2)
        })
    
    vulns.sort(key=lambda v: v["score"], reverse=True)
    return vulns


def profile_text(text: str) -> dict:
    """Profile text for cognitive patterns and SCT vulnerability surface.
    
    Returns structured profile with themes, sentiment, style analysis,
    and mapped vulnerability indicators.
    """
    tokens = _tokenize(text)
    themes = _extract_themes(tokens)
    sentiment = _compute_sentiment(tokens)
    emotional = _find_emotional_words(tokens)
    style = _compute_style(text, tokens)
    vulns = _assess_vulnerabilities(tokens, sentiment, style)
    
    result = ProfileResult(
        themes=themes,
        sentiment=sentiment,
        emotional_words=emotional,
        vulnerabilities=vulns,
        style=style,
        sct_susceptibility=[v["code"] for v in vulns if v["score"] >= 0.3],
    )
    
    return asdict(result)


def format_profile(result: dict) -> str:
    """Format a profile result for terminal output."""
    lines = [
        "=" * 60,
        "SEITHAR SUBSTRATE PROFILE",
        "=" * 60,
        "",
        f"SENTIMENT: {result['sentiment']} ({'positive' if result['sentiment'] > 0 else 'negative' if result['sentiment'] < 0 else 'neutral'})",
        "",
        "THEMES:",
    ]
    for theme, count in result.get("themes", []):
        lines.append(f"  {theme}: {count}")
    
    lines.append("")
    lines.append("COMMUNICATION STYLE:")
    for k, v in result.get("style", {}).items():
        lines.append(f"  {k}: {v}")
    
    if result.get("emotional_words"):
        lines.append("")
        lines.append(f"EMOTIONAL MARKERS: {', '.join(result['emotional_words'])}")
    
    if result.get("vulnerabilities"):
        lines.append("")
        lines.append("SCT VULNERABILITY SURFACE:")
        for v in result["vulnerabilities"]:
            bar_len = int(v["score"] * 10)
            bar = "#" * bar_len + "." * (10 - bar_len)
            lines.append(f"  [{bar}] {v['code']} {v['name']} ({v['score']})")
            lines.append(f"         {v['indicator']}")
    
    if result.get("sct_susceptibility"):
        lines.append("")
        lines.append(f"PRIMARY SUSCEPTIBILITY: {', '.join(result['sct_susceptibility'])}")
    
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
