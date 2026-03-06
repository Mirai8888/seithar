"""Tests for the Collector intelligence database."""

import json
import tempfile
from pathlib import Path

import pytest

from seithar.collector import Collector


@pytest.fixture
def col(tmp_path):
    return Collector(db_path=tmp_path / "test_collector.db")


class TestObservations:
    def test_add_and_query(self, col):
        row_id = col.add_observation("bot1", "twitter", "repligate", "simulators are real", url="https://x.com/1")
        assert row_id >= 1
        results = col.query_observations(platform="twitter")
        assert len(results) == 1
        assert results[0]["author_handle"] == "repligate"

    def test_query_by_author(self, col):
        col.add_observation("bot1", "twitter", "repligate", "post 1")
        col.add_observation("bot1", "twitter", "deepfates", "post 2")
        results = col.query_observations(author="repligate")
        assert len(results) == 1

    def test_query_limit(self, col):
        for i in range(10):
            col.add_observation("bot1", "twitter", f"user{i}", f"post {i}")
        results = col.query_observations(limit=5)
        assert len(results) == 5


class TestContacts:
    def test_upsert_new(self, col):
        result = col.upsert_contact("twitter", "repligate", display_name="janus", bio="quasi-fictional")
        assert result["status"] == "upserted"
        contact = col.get_contact("twitter", "repligate")
        assert contact["display_name"] == "janus"

    def test_upsert_update(self, col):
        col.upsert_contact("twitter", "repligate", follower_count=100)
        col.upsert_contact("twitter", "repligate", follower_count=200)
        contact = col.get_contact("twitter", "repligate")
        assert contact["follower_count"] == 200

    def test_search_by_tag(self, col):
        col.upsert_contact("twitter", "repligate", tags=["target"])
        col.upsert_contact("twitter", "deepfates", tags=["neutral"])
        results = col.search_contacts(tag="target")
        assert len(results) == 1
        assert results[0]["handle"] == "repligate"


class TestEdges:
    def test_add_edge(self, col):
        result = col.add_edge("twitter", "repligate", "deepfates", "follows")
        assert result["type"] == "follows"

    def test_increment_edge(self, col):
        col.add_edge("twitter", "a", "b", "replied_to")
        col.add_edge("twitter", "a", "b", "replied_to")
        edges = col.get_edges("a", direction="out")
        assert edges[0]["count"] == 2

    def test_get_edges_direction(self, col):
        col.add_edge("twitter", "a", "b", "follows")
        col.add_edge("twitter", "c", "a", "follows")
        out = col.get_edges("a", direction="out")
        assert len(out) == 1
        inp = col.get_edges("a", direction="in")
        assert len(inp) == 1
        both = col.get_edges("a", direction="both")
        assert len(both) == 2


class TestVocabulary:
    def test_add_and_stats(self, col):
        col.add_vocabulary_signal("twitter", "repligate", "cognitive warfare", is_target_vocab=True)
        col.add_vocabulary_signal("twitter", "deepfates", "cognitive warfare", is_target_vocab=True)
        col.add_vocabulary_signal("twitter", "repligate", "substrate", is_target_vocab=True)
        stats = col.vocabulary_stats()
        assert stats["total_signals"] == 3
        assert stats["unique_users"] == 2

    def test_stats_by_term(self, col):
        col.add_vocabulary_signal("twitter", "a", "cognitive warfare")
        col.add_vocabulary_signal("twitter", "b", "substrate")
        stats = col.vocabulary_stats(term="cognitive warfare")
        assert stats["total_signals"] == 1


class TestBulkIngest:
    def test_ingest_bot_report(self, col):
        report = {
            "raw_content": [
                {"author": "repligate", "text": "simulators are the real deal", "url": "https://x.com/1"},
                {"author": "deepfates", "text": "weaving a new narrative", "url": "https://x.com/2"},
            ],
            "contacts": [
                {"handle": "repligate", "engagement_type": "reply", "sentiment": "positive"},
            ],
            "network_edges": [
                {"from": "repligate", "to": "deepfates", "type": "replied_to"},
            ],
            "vocabulary_signals": [
                {"term": "cognitive warfare", "user": "repligate", "context": "this is basically cognitive warfare"},
            ],
        }
        result = col.ingest_bot_report("persona_8c46", "twitter", report)
        assert result["ingested"]["observations"] == 2
        assert result["ingested"]["contacts"] == 1
        assert result["ingested"]["edges"] == 1
        assert result["ingested"]["vocabulary"] == 1

    def test_stats_after_ingest(self, col):
        col.add_observation("manual", "twitter", "test", "hello")
        col.upsert_contact("twitter", "test")
        stats = col.stats()
        assert stats["observations"] == 1
        assert stats["contacts"] == 1


class TestPayloads:
    def test_record_and_update(self, col):
        pid = col.record_payload("persona_8c46", "twitter", "vocabulary_injection", "cognitive warfare is real", "repligate")
        assert pid >= 1
        result = col.update_payload_outcome(pid, "amplified", {"likes": 5, "quotes": 2})
        assert result["outcome"] == "amplified"
