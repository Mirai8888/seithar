"""Seithar Cognitive Threat Scanner (CTS).

Migrated from seithar-cogdef/scanner.py with fixes.
"""
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from seithar.core.taxonomy import SCT_TAXONOMY, SEVERITY_LABELS


# ─── Pattern database for local analysis ──────────────────────────────

_PATTERNS: dict[str, list[str]] = {
    "SCT-001": [
        "urgent", "immediately", "act now", "breaking", "shocking",
        "outrage", "horrifying", "terrifying", "you won't believe",
        "before it's too late", "last chance", "emergency",
        "fear", "anger", "disgusting", "alarming",
    ],
    "SCT-002": [
        "studies show", "experts say", "research proves", "data shows",
        "according to sources", "insiders report", "leaked",
        "classified", "exposed", "revealed",
    ],
    "SCT-003": [
        "dr.", "professor", "expert", "leading", "renowned",
        "prestigious", "award-winning", "world-class",
        "top scientist", "senior analyst",
    ],
    "SCT-004": [
        "everyone knows", "millions of people", "trending", "viral",
        "join the", "movement", "community", "don't miss out",
        "everybody is", "most people", "growing number",
    ],
    "SCT-005": [
        "as a", "people like you", "your generation", "real patriots",
        "true believers", "if you care about", "anyone who",
        "our people", "they are", "those people",
    ],
    "SCT-006": [
        "deadline", "limited time", "act before", "window closing",
        "time is running out", "expires", "only today",
    ],
    "SCT-007": [
        "share this", "spread the word", "retweet", "tell everyone",
        "they don't want you to know", "the media won't report",
        "banned", "censored", "what they don't want you to see",
        "go viral", "wake up",
    ],
    "SCT-008": [
        "behavioral changes", "procedure", "implant", "stimulation",
    ],
    "SCT-009": [
        "dopamine", "addictive", "compulsive", "doom scrolling",
        "can't stop", "hooked",
    ],
    "SCT-010": [
        "information overload", "flooding", "overwhelm",
        "notification", "constant stream", "algorithm",
    ],
    "SCT-011": [
        "don't trust", "fake news", "they're lying", "cover up",
        "conspiracy", "deep state", "controlled opposition",
        "can't trust anyone", "all corrupt", "fabricated",
        "dangerous", "threat", "invasion",
    ],
    "SCT-012": [
        "you already agreed", "you committed", "sunk cost",
        "you've come this far", "no turning back", "loyalty test",
        "prove yourself",
    ],
}


def _strip_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_url(url: str) -> str:
    """Fetch and extract text content from a URL."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'SeitharCTS/1.0 (cognitive-defense-scanner)'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    return _strip_html(html)[:10000]


def scan_text(content: str, source: str = "unknown") -> dict:
    """Scan text for cognitive exploitation patterns. Returns structured report."""
    content_lower = content.lower()
    detections = []

    for code, patterns in _PATTERNS.items():
        matched = [p for p in patterns if p in content_lower]
        if len(matched) >= 1:
            tech = SCT_TAXONOMY.get(code)
            name = tech.name if tech else code
            confidence = min(len(matched) / max(len(patterns) * 0.3, 1), 1.0)
            detections.append({
                "code": code,
                "name": name,
                "confidence": round(confidence, 2),
                "evidence": f"Matched: {', '.join(matched[:5])}",
            })

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    severity = min(10, round(sum(d["confidence"] * 2.5 for d in detections), 1))

    return {
        "threat_classification": detections[0]["name"] if detections else "Benign",
        "severity": severity,
        "techniques": detections,
        "mode": "local_pattern_matching",
        "_metadata": {
            "scanner": "SeitharCTS/1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "content_length": len(content),
        },
    }


def scan_url(url: str) -> dict:
    """Fetch a URL and scan its content."""
    content = fetch_url(url)
    return scan_text(content, source=url)


def scan_file(path: str) -> dict:
    """Read a file and scan its content."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()[:10000]
    return scan_text(content, source=path)


def format_report(report: dict) -> str:
    """Format a scan report for terminal output."""
    if report is None:
        return "No report data."

    lines = [
        "╔══════════════════════════════════════════════════╗",
        "║  SEITHAR COGNITIVE THREAT SCANNER                ║",
        "╚══════════════════════════════════════════════════╝",
        "",
    ]

    severity = report.get("severity", 0)
    sev_int = int(severity) if isinstance(severity, (int, float)) else 0
    sev_int = max(0, min(10, sev_int))
    bar = "█" * sev_int + "░" * (10 - sev_int)
    label = SEVERITY_LABELS.get(sev_int, "Unknown")

    lines.append(f"  CLASSIFICATION: {report.get('threat_classification', 'Unknown')}")
    lines.append(f"  SEVERITY: [{bar}] {severity}/10 — {label}")
    lines.append("")

    techniques = report.get("techniques", [])
    if techniques:
        lines.append("  TECHNIQUES DETECTED:")
        lines.append("")
        for t in techniques:
            conf = t.get("confidence", 0)
            lines.append(f"    ▸ {t.get('name', '?')} ({t.get('code', '?')}) [{conf:.0%}]")
            if "evidence" in t:
                lines.append(f"      {t['evidence'][:120]}")
            lines.append("")
    else:
        lines.append("  No cognitive exploitation patterns detected.")
        lines.append("")

    meta = report.get("_metadata", {})
    lines.append(f"  Source: {meta.get('source', 'unknown')}")
    lines.append(f"  Mode: {report.get('mode', 'unknown')}")
    lines.append("")
    lines.append("────────────────────────────────────────────────────")
    lines.append("研修生 | Seithar Group Research Division")
    lines.append("────────────────────────────────────────────────────")

    return "\n".join(lines)
