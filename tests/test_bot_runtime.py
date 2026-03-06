"""Tests for bot_runtime module."""

import time
import pytest
from seithar.bot_runtime import BotRuntime, BotConfig, Phase, CycleResult


class MockConnector:
    platform = "mock"
    
    def __init__(self, posts=None, mentions=None):
        self._posts = posts or []
        self._mentions = mentions or []
    
    def fetch_timeline(self, count=50):
        return self._posts[:count]
    
    def fetch_mentions(self):
        return self._mentions
    
    def fetch_dms(self):
        return []
    
    def post(self, text, reply_to=None):
        return {"id": "mock_post_1", "text": text}
    
    def like(self, post_id):
        return {"status": "ok"}
    
    def follow(self, user_id):
        return {"status": "ok"}
    
    def get_profile(self, user_id):
        return {"id": user_id}
    
    def search(self, query, count=20):
        return []


class TestBotConfig:
    def test_defaults(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter")
        assert cfg.phase == Phase.LURK
        assert cfg.lurk_hours == 48.0
        assert cfg.max_daily_posts == 10

    def test_to_dict(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter")
        d = cfg.to_dict()
        assert d["instance_id"] == "BOT-1"
        assert d["phase"] == "lurk"

    def test_from_dict(self):
        d = {"instance_id": "BOT-2", "persona_id": "p2", "platform": "discord", "phase": "full"}
        cfg = BotConfig.from_dict(d)
        assert cfg.phase == Phase.ENGAGE_FULL
        assert cfg.platform == "discord"

    def test_from_dict_ignores_extra_keys(self):
        d = {"instance_id": "BOT-3", "persona_id": "p3", "platform": "telegram", "unknown_key": True}
        cfg = BotConfig.from_dict(d)
        assert cfg.instance_id == "BOT-3"


class TestPhases:
    def test_lurk_when_no_start(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter")
        rt = BotRuntime(cfg)
        assert rt.in_lurk_phase is True
        assert rt.can_engage is False

    def test_lurk_when_recent_start(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter", started_at=time.time())
        rt = BotRuntime(cfg)
        assert rt.in_lurk_phase is True

    def test_not_lurk_after_48h(self):
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="twitter",
            started_at=time.time() - (49 * 3600),
        )
        rt = BotRuntime(cfg)
        assert rt.in_lurk_phase is False
        assert rt.can_engage is True

    def test_auto_phase_lurk(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter", started_at=time.time())
        rt = BotRuntime(cfg)
        assert rt.auto_phase() == Phase.LURK

    def test_auto_phase_light(self):
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="twitter",
            started_at=time.time() - (49 * 3600),
        )
        rt = BotRuntime(cfg)
        assert rt.auto_phase() == Phase.ENGAGE_LIGHT

    def test_auto_phase_full(self):
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="twitter",
            started_at=time.time() - (73 * 3600),
        )
        rt = BotRuntime(cfg)
        assert rt.auto_phase() == Phase.ENGAGE_FULL

    def test_burned_stays_burned(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter", phase=Phase.BURNED)
        rt = BotRuntime(cfg)
        assert rt.auto_phase() == Phase.BURNED
        assert rt.can_engage is False

    def test_dormant_no_engage(self):
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="twitter",
            phase=Phase.DORMANT, started_at=time.time() - (100 * 3600),
        )
        rt = BotRuntime(cfg)
        assert rt.can_engage is False

    def test_daily_limit_blocks_engage(self):
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="twitter",
            started_at=time.time() - (73 * 3600),
            total_posts_today=10,
        )
        rt = BotRuntime(cfg)
        assert rt.can_engage is False


class TestObservation:
    def test_observe_empty_without_connector(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="twitter")
        rt = BotRuntime(cfg)
        assert rt.observe() == []

    def test_observe_collects_posts(self):
        posts = [
            {"author": "user1", "text": "hello world", "id": "t1", "timestamp": "2026-01-01"},
            {"author": "user2", "text": "testing 123", "id": "t2", "timestamp": "2026-01-01"},
        ]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg, connector=conn)
        obs = rt.observe()
        assert len(obs) == 2
        assert obs[0]["author"] == "user1"

    def test_observe_tracks_contacts(self):
        posts = [
            {"author": "alice", "text": "hi", "id": "t1", "timestamp": ""},
            {"author": "alice", "text": "again", "id": "t2", "timestamp": ""},
            {"author": "bob", "text": "hey", "id": "t3", "timestamp": ""},
        ]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg, connector=conn)
        rt.observe()
        assert len(rt._contacts) == 2
        assert rt._contacts["alice"]["engagement_count"] == 2

    def test_observe_tracks_keywords(self):
        posts = [
            {"author": "user1", "text": "the cognitive substrate is interesting", "id": "t1", "timestamp": ""},
        ]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock", keywords=["cognitive substrate", "narrative"])
        rt = BotRuntime(cfg, connector=conn)
        rt.observe()
        assert len(rt._vocab_hits) == 1
        assert rt._vocab_hits[0]["term"] == "cognitive substrate"

    def test_observe_tracks_mention_edges(self):
        mentions = [
            {"author": "user1", "text": "@bot hi", "id": "m1", "timestamp": ""},
        ]
        conn = MockConnector(mentions=mentions)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg, connector=conn)
        rt.observe()
        assert len(rt._edges) == 1
        assert rt._edges[0]["from"] == "user1"


class TestExfil:
    def test_exfil_payload_structure(self):
        posts = [{"author": "user1", "text": "hello", "id": "t1", "timestamp": ""}]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg, connector=conn)
        rt.observe()
        payload = rt.build_exfil_payload()
        assert "contacts" in payload
        assert "vocabulary_signals" in payload
        assert "network_edges" in payload
        assert "raw_content" in payload
        assert "stats" in payload
        assert payload["stats"]["total_observed"] == 1
        assert payload["stats"]["unique_contacts"] == 1

    def test_exfil_empty_when_no_observations(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg)
        payload = rt.build_exfil_payload()
        assert payload["stats"]["total_observed"] == 0


class TestCycle:
    def test_run_cycle(self):
        posts = [
            {"author": "u1", "text": "substrate priming example", "id": "1", "timestamp": ""},
            {"author": "u2", "text": "normal post", "id": "2", "timestamp": ""},
        ]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(
            instance_id="BOT-1", persona_id="p1", platform="mock",
            keywords=["substrate"],
        )
        rt = BotRuntime(cfg, connector=conn)
        result = rt.run_cycle()
        assert isinstance(result, CycleResult)
        assert result.observed == 2
        assert result.collected == 2
        assert result.errors == []
        assert result.phase == Phase.LURK

    def test_cycle_result_to_dict(self):
        r = CycleResult(instance_id="BOT-1", phase=Phase.LURK, observed=5)
        d = r.to_dict()
        assert d["instance_id"] == "BOT-1"
        assert d["phase"] == "lurk"
        assert d["observed"] == 5


class TestLifecycle:
    def test_burn(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg)
        rt.burn("detected by moderator")
        assert cfg.phase == Phase.BURNED

    def test_clear_observations(self):
        posts = [{"author": "u1", "text": "hi", "id": "1", "timestamp": ""}]
        conn = MockConnector(posts=posts)
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock")
        rt = BotRuntime(cfg, connector=conn)
        rt.observe()
        assert len(rt._observations) > 0
        rt.clear_observations()
        assert len(rt._observations) == 0
        assert len(rt._contacts) == 0

    def test_reset_daily_counters(self):
        cfg = BotConfig(instance_id="BOT-1", persona_id="p1", platform="mock", total_posts_today=8)
        rt = BotRuntime(cfg)
        rt.reset_daily_counters()
        assert cfg.total_posts_today == 0
