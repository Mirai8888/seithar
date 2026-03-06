"""Tests for analytics engine."""

import time
import pytest
from datetime import datetime, timezone

from seithar.analytics import (
    AnalyticsEngine, sentiment_score, emotional_intensity,
    compute_tfidf, TermFrequency,
)
from seithar.collector import Collector


@pytest.fixture
def collector(tmp_path):
    return Collector(db_path=tmp_path / "test.db")


@pytest.fixture
def engine(collector):
    return AnalyticsEngine(collector=collector)


class TestSentiment:
    def test_positive(self):
        assert sentiment_score("this is amazing and brilliant") > 0

    def test_negative(self):
        assert sentiment_score("this is terrible and awful") < 0

    def test_neutral(self):
        assert abs(sentiment_score("the cat sat on the mat")) < 0.5

    def test_empty(self):
        assert sentiment_score("") == 0.0

    def test_intensity_high(self):
        assert emotional_intensity("I love and hate this amazing terrible thing") > 0

    def test_intensity_neutral(self):
        assert emotional_intensity("the report was submitted yesterday") < 0.5


class TestTfIdf:
    def test_basic(self):
        obs = [
            {"content": "cognitive substrate is the key"},
            {"content": "substrate substrate everywhere"},
            {"content": "normal conversation here"},
        ]
        results = compute_tfidf(obs)
        assert len(results) > 0
        terms = [r.term for r in results]
        assert "substrate" in terms

    def test_specific_terms(self):
        obs = [
            {"content": "cognitive substrate model"},
            {"content": "narrative capture in action"},
            {"content": "normal post"},
        ]
        results = compute_tfidf(obs, terms=["cognitive substrate", "narrative capture"])
        assert len(results) == 2

    def test_empty(self):
        assert compute_tfidf([]) == []


class TestTermAdoption:
    def test_no_observations(self, engine):
        result = engine.term_adoption_rate("twitter", ["test"])
        assert "error" in result

    def test_with_data(self, engine, collector):
        now = datetime.now(timezone.utc).isoformat()
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="cognitive substrate is real",
            observed_at=now,
        )
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u2", content="normal post",
            observed_at=now,
        )
        result = engine.term_adoption_rate("twitter", ["cognitive substrate"], window_days=1, buckets=1)
        assert result["trend"] in ("rising", "falling", "stable")
        assert len(result["buckets"]) == 1


class TestPostingFrequency:
    def test_no_data(self, engine):
        result = engine.posting_frequency("twitter")
        assert result["posts"] == 0

    def test_with_data(self, engine, collector):
        for i in range(5):
            collector.add_observation(
                source="s", platform="twitter",
                author_handle=f"user{i % 2}",
                content=f"post {i}",
            )
        result = engine.posting_frequency("twitter")
        assert result["total_posts"] == 5
        assert len(result["top_posters"]) == 2

    def test_per_user(self, engine, collector):
        for i in range(3):
            collector.add_observation(
                source="s", platform="twitter",
                author_handle="alice", content=f"post {i}",
            )
        result = engine.posting_frequency("twitter", handle="alice")
        assert result["total_posts"] == 3


class TestSentimentTrajectory:
    def test_no_data(self, engine):
        result = engine.sentiment_trajectory("twitter")
        assert "error" in result

    def test_with_data(self, engine, collector):
        now = datetime.now(timezone.utc).isoformat()
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="this is amazing and wonderful",
            observed_at=now,
        )
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u2", content="this is terrible and awful",
            observed_at=now,
        )
        result = engine.sentiment_trajectory("twitter", window_days=1, buckets=1)
        assert len(result["buckets"]) == 1
        assert result["sentiment_trend"] in ("positive", "negative", "stable")


class TestNetworkMetrics:
    def test_no_edges(self, engine):
        result = engine.network_metrics("twitter", "nobody")
        assert result["in_degree"] == 0
        assert result["out_degree"] == 0

    def test_with_edges(self, engine, collector):
        for i in range(5):
            collector.add_edge(
                platform="twitter", source_handle="hub",
                target_handle=f"target{i}", edge_type="reply",
            )
        for i in range(3):
            collector.add_edge(
                platform="twitter", source_handle=f"fan{i}",
                target_handle="hub", edge_type="reply",
            )
        # One mutual
        collector.add_edge(
            platform="twitter", source_handle="target0",
            target_handle="hub", edge_type="reply",
        )
        result = engine.network_metrics("twitter", "hub")
        assert result["out_degree"] == 5
        assert result["in_degree"] >= 3
        assert result["mutual_connections"] >= 1
        assert result["reciprocity"] > 0


class TestVocabularyConvergence:
    def test_no_data(self, engine):
        result = engine.vocabulary_convergence("twitter", ["test"], ["native"])
        assert "error" in result

    def test_no_adoption(self, engine, collector):
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="just talking about simulators",
        )
        result = engine.vocabulary_convergence(
            "twitter", ["cognitive substrate"], ["simulators"],
        )
        assert result["convergence_ratio"] == 0.0
        assert result["interpretation"] == "no_adoption"

    def test_some_adoption(self, engine, collector):
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="cognitive substrate model is real",
        )
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u2", content="simulators everywhere",
        )
        result = engine.vocabulary_convergence(
            "twitter", ["cognitive substrate"], ["simulators"],
        )
        assert result["convergence_ratio"] == 0.5
        assert result["interpretation"] == "high_adoption"

    def test_crossover_users(self, engine, collector):
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="convert",
            content="simulators and cognitive substrate both explain this",
        )
        result = engine.vocabulary_convergence(
            "twitter", ["cognitive substrate"], ["simulators"],
        )
        assert result["crossover_users"] == 1


class TestFullReport:
    def test_empty(self, engine):
        report = engine.full_report("twitter")
        assert "timestamp" in report
        assert "posting_frequency" in report
        assert "term_adoption" in report
        assert "sentiment" in report
        assert "vocabulary_convergence" in report
