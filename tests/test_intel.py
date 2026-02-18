"""Tests for seithar.intel — threat intelligence modules."""
import pytest


class TestIntelImports:
    def test_import_module(self):
        import seithar.intel  # noqa: F401

    def test_import_feeds(self):
        from seithar.intel.feeds import fetch_rss_feed  # noqa: F401

    def test_import_scorer(self):
        from seithar.intel.scorer import score_item  # noqa: F401

    def test_import_scorer_keywords(self):
        from seithar.intel.scorer import DEFAULT_PRIMARY  # noqa: F401
        from seithar.intel.scorer import DEFAULT_SECONDARY  # noqa: F401

    def test_import_arxiv(self):
        from seithar.intel.arxiv import fetch_arxiv_papers  # noqa: F401

    def test_import_arxiv_feeds(self):
        from seithar.intel.arxiv import DEFAULT_FEEDS  # noqa: F401


class TestIntelStubs:
    def test_fetch_rss_feed_raises(self):
        from seithar.intel.feeds import fetch_rss_feed
        with pytest.raises(NotImplementedError):
            fetch_rss_feed("https://example.com/rss", "test")

    def test_score_item_raises(self):
        from seithar.intel.scorer import score_item
        with pytest.raises(NotImplementedError):
            score_item(None)

    def test_fetch_arxiv_papers_raises(self):
        from seithar.intel.arxiv import fetch_arxiv_papers
        with pytest.raises(NotImplementedError):
            fetch_arxiv_papers()


class TestScorerKeywords:
    def test_primary_is_list(self):
        from seithar.intel.scorer import DEFAULT_PRIMARY
        assert isinstance(DEFAULT_PRIMARY, list)
        assert len(DEFAULT_PRIMARY) > 0

    def test_secondary_is_list(self):
        from seithar.intel.scorer import DEFAULT_SECONDARY
        assert isinstance(DEFAULT_SECONDARY, list)
        assert len(DEFAULT_SECONDARY) > 0
