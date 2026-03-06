"""Tests for dynamic tool filtering."""
import pytest
from pathlib import Path

CATALOG = Path(__file__).parent.parent / "data" / "tool_catalog.json"

pytestmark = pytest.mark.skipif(
    not CATALOG.exists(),
    reason="tool_catalog.json not built"
)


def _filter():
    from seithar.mcp.tool_filter import ToolFilter
    tf = ToolFilter(catalog_path=CATALOG)
    tf.build_index()
    return tf


class TestToolFilter:
    def test_loads_all_tools(self):
        tf = _filter()
        assert tf.stats()["total_tools"] >= 20  # Catalog may lag server

    def test_query_returns_top_k(self):
        tf = _filter()
        results = tf.query("scrape a website", top_k=5)
        assert len(results) == 5
        assert results[0]["score"] > results[-1]["score"]

    def test_recon_surfaces_for_scraping(self):
        tf = _filter()
        results = tf.query("scrape this URL and extract emails")
        names = [r["name"] for r in results]
        assert "recon" in names

    def test_shield_surfaces_for_defense(self):
        tf = _filter()
        results = tf.query("check if agent is under attack")
        names = [r["name"] for r in results]
        assert any(n in names for n in ["shield", "scan", "evasion"])

    def test_deanon_surfaces_for_identity(self):
        tf = _filter()
        results = tf.query("identify this anonymous user")
        names = [r["name"] for r in results]
        assert any(n.startswith("deanon") for n in names)

    def test_filter_tools_reduces_list(self):
        tf = _filter()
        all_tools = [{"name": t} for t in tf.tool_names()]
        filtered = tf.filter_tools("manage personas", all_tools, top_k=5)
        assert len(filtered) == 5
        assert len(filtered) < len(all_tools)
