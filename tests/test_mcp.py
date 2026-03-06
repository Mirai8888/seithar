"""Tests for public MCP components."""
import pytest

from seithar.mcp.taxonomy_surface import TaxonomySurface


class TestTaxonomy:
    def setup_method(self):
        self.tax = TaxonomySurface()

    def test_full(self):
        result = self.tax.full()
        assert "taxonomy" in result

    def test_query_by_code(self):
        result = self.tax.query(code="SCT-001")
        assert result is not None

    def test_query_by_search(self):
        result = self.tax.query(search="identity")
        assert result is not None
