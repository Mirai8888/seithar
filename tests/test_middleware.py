"""Tests for middleware: ProfileBuilder, ContextAssembler, SemanticDriftMonitor."""

import json
import time
import pytest
from pathlib import Path

from seithar.middleware import (
    TargetProfile, ProfileBuilder, ContextAssembler,
    SemanticDriftMonitor, DriftMeasurement, _extract_word_frequencies,
)
from seithar.collector import Collector


@pytest.fixture
def collector(tmp_path):
    return Collector(db_path=tmp_path / "test.db")


@pytest.fixture
def profile_builder(tmp_path, collector):
    return ProfileBuilder(data_dir=tmp_path / "profiles", collector=collector)


@pytest.fixture
def drift_monitor(tmp_path, collector):
    return SemanticDriftMonitor(data_dir=tmp_path / "drift", collector=collector)


class TestTargetProfile:
    def test_to_dict(self):
        p = TargetProfile(handle="repligate", platform="twitter", confidence=0.7)
        d = p.to_dict()
        assert d["handle"] == "repligate"
        assert d["confidence"] == 0.7

    def test_from_dict(self):
        d = {"handle": "test", "platform": "twitter", "tone": "academic"}
        p = TargetProfile.from_dict(d)
        assert p.tone == "academic"

    def test_to_context_block(self):
        p = TargetProfile(
            handle="repligate", platform="twitter",
            network_role="hub", follower_count=5000,
            tone="academic", engagement_style="initiator",
            topics_of_interest=["simulators", "AI", "consciousness"],
            vocabulary_affinity=["substrate", "weaving"],
            seithar_vocab_adopted=["cognitive substrate"],
            confidence=0.8,
        )
        block = p.to_context_block()
        assert "@repligate" in block
        assert "hub" in block
        assert "cognitive substrate" in block
        assert "ADOPTED" in block

    def test_context_block_minimal(self):
        p = TargetProfile(handle="unknown", platform="twitter", confidence=0.1)
        block = p.to_context_block()
        assert "@unknown" in block
        assert "10%" in block


class TestProfileBuilder:
    def test_save_and_load(self, profile_builder):
        p = TargetProfile(handle="test_user", platform="twitter", tone="ironic")
        profile_builder.save_profile(p)
        loaded = profile_builder.load_profile("twitter", "test_user")
        assert loaded is not None
        assert loaded.tone == "ironic"

    def test_load_nonexistent(self, profile_builder):
        assert profile_builder.load_profile("twitter", "nobody") is None

    def test_build_profile_empty(self, profile_builder):
        p = profile_builder.build_profile("twitter", "new_user")
        assert p.handle == "new_user"
        assert p.confidence == 0.1  # no data

    def test_build_profile_with_observations(self, profile_builder, collector):
        # Seed data
        for i in range(15):
            collector.add_observation(
                source="scraper", platform="twitter",
                author_handle="active_user",
                content=f"Post about simulators and cognitive substrate #{i}",
            )
        collector.add_edge(
            platform="twitter", source_handle="active_user",
            target_handle="friend1", edge_type="reply",
        )
        
        p = profile_builder.build_profile("twitter", "active_user")
        assert p.confidence >= 0.5
        assert p.posting_frequency == "medium"
        assert len(p.vocabulary_affinity) > 0

    def test_build_profile_detects_seithar_vocab(self, profile_builder, collector):
        collector.add_observation(
            source="scraper", platform="twitter",
            author_handle="adopter",
            content="I think the cognitive substrate model explains this well",
        )
        p = profile_builder.build_profile("twitter", "adopter")
        assert "cognitive substrate" in p.seithar_vocab_adopted

    def test_list_profiles(self, profile_builder):
        p1 = TargetProfile(handle="user1", platform="twitter", confidence=0.5)
        p2 = TargetProfile(handle="user2", platform="discord", confidence=0.8)
        profile_builder.save_profile(p1)
        profile_builder.save_profile(p2)
        profiles = profile_builder.list_profiles()
        assert len(profiles) == 2

    def test_network_role_detection(self, profile_builder, collector):
        # Hub: many in + many out
        for i in range(25):
            collector.add_edge(
                platform="twitter", source_handle=f"fan{i}",
                target_handle="hub_user", edge_type="reply",
            )
            collector.add_edge(
                platform="twitter", source_handle="hub_user",
                target_handle=f"target{i}", edge_type="reply",
            )
        p = profile_builder.build_profile("twitter", "hub_user")
        assert p.network_role == "hub"


class TestContextAssembler:
    def test_build_context_minimal(self, profile_builder):
        ca = ContextAssembler(profile_builder, collector=profile_builder.collector)
        ctx = ca.build_context("new_target", "twitter")
        assert "@new_target" in ctx
        assert "INTERACTION TYPE: reply" in ctx

    def test_build_context_with_data(self, profile_builder, collector):
        collector.add_observation(
            source="bot", platform="twitter",
            author_handle="target1",
            content="Exploring the nature of simulacra in AI systems",
        )
        ca = ContextAssembler(profile_builder, collector=collector)
        ctx = ca.build_context("target1", "twitter", interaction_type="quote")
        assert "INTERACTION TYPE: quote" in ctx
        assert "RECENT POSTS" in ctx

    def test_context_respects_token_budget(self, profile_builder, collector):
        # Fill with lots of data
        for i in range(100):
            collector.add_observation(
                source="bot", platform="twitter",
                author_handle="verbose_user",
                content=f"Long post about topic {i} " * 20,
            )
        ca = ContextAssembler(profile_builder, collector=collector)
        ctx = ca.build_context("verbose_user", "twitter", max_tokens=500)
        assert len(ctx) <= 2100  # 500 * 4 + some slack

    def test_community_snapshot(self, profile_builder, collector):
        collector.add_observation(
            source="bot", platform="twitter",
            author_handle="user1", content="simulators are real",
        )
        collector.add_observation(
            source="bot", platform="twitter",
            author_handle="user2", content="cognitive substrate theory",
        )
        ca = ContextAssembler(profile_builder, collector=collector)
        snapshot = ca.community_snapshot("twitter")
        assert snapshot["active_users"] == 2
        assert "terms detected" in snapshot["seithar_penetration"]
        # At least cognitive substrate should be detected
        assert snapshot["seithar_penetration"] != "0 terms"


class TestSemanticDriftMonitor:
    def test_measure_empty(self, drift_monitor):
        m = drift_monitor.measure("twitter")
        assert m.observation_count == 0
        assert m.total_seithar_penetration == 0.0

    def test_measure_with_native_terms(self, drift_monitor, collector):
        collector.add_observation(
            source="scraper", platform="twitter",
            author_handle="user1", content="simulators are the base reality",
        )
        collector.add_observation(
            source="scraper", platform="twitter",
            author_handle="user2", content="weaving through the dreamtime",
        )
        m = drift_monitor.measure("twitter")
        assert m.observation_count == 2
        assert m.unique_authors == 2
        assert "simulators" in m.native_term_hits

    def test_measure_detects_seithar_adoption(self, drift_monitor, collector):
        collector.add_observation(
            source="scraper", platform="twitter",
            author_handle="convert1", content="the cognitive substrate model is fascinating",
        )
        m = drift_monitor.measure("twitter")
        assert "cognitive substrate" in m.seithar_term_hits
        assert "convert1" in m.adopters
        assert m.total_seithar_penetration > 0

    def test_trend_insufficient_data(self, drift_monitor):
        result = drift_monitor.trend("twitter")
        assert result.get("error") or result.get("trend") == "insufficient_data"

    def test_trend_with_history(self, drift_monitor, collector):
        # First measurement: no seithar terms
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="normal conversation about simulators",
        )
        drift_monitor.measure("twitter")

        # Second measurement: seithar term appears
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u2", content="cognitive substrate is interesting",
        )
        drift_monitor.measure("twitter")

        trend = drift_monitor.trend("twitter")
        assert trend["measurements"] == 2
        assert trend["penetration_end"] > trend["penetration_start"]

    def test_measurement_persistence(self, drift_monitor, collector):
        collector.add_observation(
            source="s", platform="twitter",
            author_handle="u1", content="test post",
        )
        drift_monitor.measure("twitter")
        
        history_path = drift_monitor.data_dir / "twitter_history.jsonl"
        assert history_path.exists()
        lines = history_path.read_text().strip().split("\n")
        assert len(lines) == 1


class TestHelpers:
    def test_extract_word_frequencies(self):
        observations = [
            {"content": "cognitive substrate is the foundation"},
            {"content": "substrate substrate substrate"},
            {"content": "hello world test"},
        ]
        freq = _extract_word_frequencies(observations)
        words = [w for w, _ in freq]
        assert "substrate" in words
        # "is" and "the" should be filtered
        assert "the" not in words

    def test_extract_empty(self):
        assert _extract_word_frequencies([]) == []
