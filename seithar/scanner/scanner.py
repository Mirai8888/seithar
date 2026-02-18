"""Seithar Cognitive Threat Scanner (CTS)."""

_PATTERNS: dict[str, list[str]] = {}


def _strip_html(html: str) -> str:
    raise NotImplementedError


def fetch_url(url: str) -> str:
    raise NotImplementedError


def scan_text(content: str, source: str = "unknown"):
    raise NotImplementedError


def scan_url(url: str):
    raise NotImplementedError


def scan_file(path: str):
    raise NotImplementedError


def format_report(result) -> str:
    raise NotImplementedError
