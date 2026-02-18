"""Tests for seithar.scanner — Cognitive Threat Scanner."""
import pytest


class TestScannerImports:
    def test_import_module(self):
        import seithar.scanner  # noqa: F401

    def test_import_scan_text(self):
        from seithar.scanner.scanner import scan_text  # noqa: F401

    def test_import_scan_url(self):
        from seithar.scanner.scanner import scan_url  # noqa: F401

    def test_import_scan_file(self):
        from seithar.scanner.scanner import scan_file  # noqa: F401

    def test_import_fetch_url(self):
        from seithar.scanner.scanner import fetch_url  # noqa: F401

    def test_import_format_report(self):
        from seithar.scanner.scanner import format_report  # noqa: F401

    def test_import_strip_html(self):
        from seithar.scanner.scanner import _strip_html  # noqa: F401

    def test_import_patterns(self):
        from seithar.scanner.scanner import _PATTERNS  # noqa: F401


class TestScannerFunctional:
    def test_scan_text_returns_dict(self):
        from seithar.scanner.scanner import scan_text
        result = scan_text("This is a test", "test")
        assert isinstance(result, dict)
        assert "techniques" in result

    def test_scan_text_detects_threats(self):
        from seithar.scanner.scanner import scan_text
        result = scan_text("URGENT act now before it's too late! Share this immediately!", "test")
        assert len(result["techniques"]) > 0

    def test_scan_text_benign(self):
        from seithar.scanner.scanner import scan_text
        result = scan_text("The weather is nice today.", "test")
        assert result["threat_classification"] == "Benign" or len(result["techniques"]) == 0

    def test_strip_html(self):
        from seithar.scanner.scanner import _strip_html
        assert "hello" in _strip_html("<p>hello</p>")

    def test_format_report_none(self):
        from seithar.scanner.scanner import format_report
        result = format_report(None)
        assert isinstance(result, str)

    def test_format_report_dict(self):
        from seithar.scanner.scanner import format_report
        report = {"threat_classification": "Benign", "severity": 0, "techniques": [], "_metadata": {"source": "test"}, "mode": "test"}
        result = format_report(report)
        assert "SEITHAR" in result


class TestScannerPatterns:
    def test_patterns_is_dict(self):
        from seithar.scanner.scanner import _PATTERNS
        assert isinstance(_PATTERNS, dict)

    def test_patterns_has_entries(self):
        from seithar.scanner.scanner import _PATTERNS
        assert len(_PATTERNS) > 0
