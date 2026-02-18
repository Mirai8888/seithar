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


class TestScannerStubs:
    """All stub functions must exist with correct signatures and raise NotImplementedError."""

    def test_scan_text_raises(self):
        from seithar.scanner.scanner import scan_text
        with pytest.raises(NotImplementedError):
            scan_text("test content", "test source")

    def test_scan_url_raises(self):
        from seithar.scanner.scanner import scan_url
        with pytest.raises(NotImplementedError):
            scan_url("https://example.com")

    def test_scan_file_raises(self):
        from seithar.scanner.scanner import scan_file
        with pytest.raises(NotImplementedError):
            scan_file("/tmp/test.txt")

    def test_fetch_url_raises(self):
        from seithar.scanner.scanner import fetch_url
        with pytest.raises(NotImplementedError):
            fetch_url("https://example.com")

    def test_format_report_raises(self):
        from seithar.scanner.scanner import format_report
        with pytest.raises(NotImplementedError):
            format_report(None)

    def test_strip_html_raises(self):
        from seithar.scanner.scanner import _strip_html
        with pytest.raises(NotImplementedError):
            _strip_html("<p>test</p>")


class TestScannerPatterns:
    def test_patterns_is_dict(self):
        from seithar.scanner.scanner import _PATTERNS
        assert isinstance(_PATTERNS, dict)
