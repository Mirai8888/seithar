"""Tests for detection evasion analyzer."""

import time
import pytest
from datetime import datetime, timezone, timedelta

from seithar.evasion import EvasionAnalyzer, EvasionReport, _pearson_correlation
from seithar.collector import Collector


@pytest.fixture
def collector(tmp_path):
    return Collector(db_path=tmp_path / "test.db")


@pytest.fixture
def analyzer(collector):
    return EvasionAnalyzer(collector=collector)


class TestPearsonCorrelation:
    def test_perfect(self):
        assert abs(_pearson_correlation([1, 2, 3], [1, 2, 3]) - 1.0) < 0.01

    def test_inverse(self):
        assert abs(_pearson_correlation([1, 2, 3], [3, 2, 1]) - (-1.0)) < 0.01

    def test_zero(self):
        assert abs(_pearson_correlation([1, 1, 1], [1, 2, 3])) < 0.01

    def test_empty(self):
        assert _pearson_correlation([], []) == 0.0


class TestEvasionReport:
    def test_to_dict(self):
        r = EvasionReport(overall_risk="low", risk_score=0.15)
        d = r.to_dict()
        assert d["overall_risk"] == "low"
        assert d["risk_score"] == 0.15


class TestFleetAnalysis:
    def test_no_data(self, analyzer):
        report = analyzer.analyze_fleet("twitter")
        assert report.overall_risk == "unknown"

    def test_single_author(self, analyzer, collector):
        for i in range(5):
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="persona1", content=f"Post {i}",
            )
        report = analyzer.analyze_fleet("twitter")
        # Single author can't have coordination signals
        assert report.risk_score <= 0.5

    def test_diverse_personas(self, analyzer, collector):
        # Two personas with different content and timing
        now = datetime.now(timezone.utc)
        for i in range(10):
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="persona_a",
                content=f"Unique content about topic alpha number {i}",
                observed_at=(now - timedelta(hours=i * 3 + 1)).isoformat(),
            )
        for i in range(10):
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="persona_b",
                content=f"Different subject on theme beta iteration {i}",
                observed_at=(now - timedelta(hours=i * 5 + 2)).isoformat(),
            )
        report = analyzer.analyze_fleet("twitter")
        assert report.overall_risk in ("low", "medium", "unknown")

    def test_suspicious_same_content(self, analyzer, collector):
        # Two personas posting very similar content
        now = datetime.now(timezone.utc)
        for i in range(10):
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="bot_a",
                content=f"cognitive substrate narrative capture frequency lock post {i}",
                observed_at=(now - timedelta(hours=i)).isoformat(),
            )
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="bot_b",
                content=f"cognitive substrate narrative capture binding protocol post {i}",
                observed_at=(now - timedelta(hours=i)).isoformat(),
            )
        report = analyzer.analyze_fleet("twitter")
        # Should flag content similarity and vocabulary homogeneity
        content_signal = next((s for s in report.signals if s["signal"] == "content_similarity"), None)
        vocab_signal = next((s for s in report.signals if s["signal"] == "vocabulary_homogeneity"), None)
        assert content_signal is not None
        assert vocab_signal is not None

    def test_recommendations_present(self, analyzer, collector):
        now = datetime.now(timezone.utc)
        for persona in ["a", "b"]:
            for i in range(5):
                collector.add_observation(
                    source="bot", platform="twitter",
                    author_handle=f"persona_{persona}",
                    content=f"Post {i} from {persona}",
                    observed_at=(now - timedelta(hours=i)).isoformat(),
                )
        report = analyzer.analyze_fleet("twitter")
        for signal in report.signals:
            assert "detail" in signal
