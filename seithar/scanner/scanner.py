"""
Seithar Cognitive Threat Scanner (CTS).

Automated analysis of content for cognitive exploitation vectors.
Maps findings to the Seithar Cognitive Defense Taxonomy (SCT-001
through SCT-012) and DISARM framework.

Supports local pattern matching (no API key) and LLM-powered
deep analysis (requires ANTHROPIC_API_KEY).

Will contain:
    - _PATTERNS dict: keyword patterns per SCT code for local analysis
    - _strip_html(html) -> str
    - fetch_url(url) -> str
    - scan_text(content, source) -> ScanResult
    - scan_url(url) -> ScanResult
    - scan_file(path) -> ScanResult
    - format_report(result) -> str

Source: seithar-cogdef/scanner.py
Known issue: original is missing `import re` — fix during migration.
"""
