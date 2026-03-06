"""Tests for community intelligence engine."""

import json
import tempfile
from pathlib import Path

import pytest

from seithar.community_intel import (
    CommunityIntelEngine,
    MemberProfile,
    CommunityModel,
    PersonaBlueprint,
)


@pytest.fixture
def sample_observations():
    return [
        {"content": "yo whats good everyone", "author": "alice", "display_name": "Alice", "channel": "general", "observed_at": "2026-02-22T01:00:00"},
        {"content": "gm gm", "author": "bob", "display_name": "Bob", "channel": "general", "observed_at": "2026-02-22T01:01:00"},
        {"content": "has anyone seen the new milady drop? the traits are insane", "author": "alice", "display_name": "Alice", "channel": "general", "observed_at": "2026-02-22T01:02:00"},
        {"content": "yeah the art is fire 🔥🔥", "author": "charlie", "display_name": "Charlie", "channel": "general", "observed_at": "2026-02-22T01:03:00"},
        {"content": "I think the floor is gonna pump tbh", "author": "alice", "display_name": "Alice", "channel": "trading", "observed_at": "2026-02-22T01:04:00"},
        {"content": "based alice always calling it", "author": "bob", "display_name": "Bob", "channel": "general", "observed_at": "2026-02-22T01:05:00"},
        {"content": "lol you guys are wild. anyone wanna play minecraft later?", "author": "charlie", "display_name": "Charlie", "channel": "general", "observed_at": "2026-02-22T01:06:00"},
        {"content": "the vibes in here are immaculate fr fr", "author": "dave", "display_name": "Dave", "channel": "general", "observed_at": "2026-02-22T01:07:00"},
        {"content": "just copped a rare, feeling goated", "author": "alice", "display_name": "Alice", "channel": "trading", "observed_at": "2026-02-22T01:08:00"},
        {"content": "<@alice> congrats queen 👑", "author": "bob", "display_name": "Bob", "channel": "general", "observed_at": "2026-02-22T01:09:00"},
        {"content": "ngl i wish i had more eth to buy more", "author": "charlie", "display_name": "Charlie", "channel": "trading", "observed_at": "2026-02-22T01:10:00"},
        {"content": "this community is the best thing on discord honestly", "author": "dave", "display_name": "Dave", "channel": "general", "observed_at": "2026-02-22T01:11:00"},
        {"content": "ok hear me out... what if we did a group buy?", "author": "alice", "display_name": "Alice", "channel": "general", "observed_at": "2026-02-22T01:12:00"},
        {"content": "W idea", "author": "bob", "display_name": "Bob", "channel": "general", "observed_at": "2026-02-22T01:13:00"},
        {"content": "im down", "author": "charlie", "display_name": "Charlie", "channel": "general", "observed_at": "2026-02-22T01:14:00"},
        {"content": "lets gooo", "author": "dave", "display_name": "Dave", "channel": "general", "observed_at": "2026-02-22T01:15:00"},
        {"content": "you should all listen to this new track btw", "author": "alice", "display_name": "Alice", "channel": "music", "observed_at": "2026-02-22T01:16:00"},
        {"content": "alice always has the best recs fr", "author": "dave", "display_name": "Dave", "channel": "music", "observed_at": "2026-02-22T01:17:00"},
        {"content": "bruh this slaps", "author": "charlie", "display_name": "Charlie", "channel": "music", "observed_at": "2026-02-22T01:18:00"},
        {"content": "anyone else feeling bearish on the broader market tho?", "author": "bob", "display_name": "Bob", "channel": "trading", "observed_at": "2026-02-22T01:19:00"},
    ]


class TestMemberProfiles:
    def test_builds_profiles(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        assert "alice" in profiles
        assert "charlie" in profiles
        assert profiles["alice"].message_count == 6

    def test_vocabulary_richness(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        # Alice has varied messages, should have decent richness
        assert profiles["alice"].vocabulary_richness > 0.3

    def test_topics_extracted(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        # Alice talks about milady, floor, traits
        alice_topics = profiles["alice"].topics_of_interest
        assert len(alice_topics) > 0

    def test_vulnerability_signals(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        # Charlie says "ngl" and "i wish" — should pick up vulnerability
        charlie = profiles["charlie"]
        assert len(charlie.vulnerability_signals) > 0

    def test_active_channels(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        # Alice posts in general, trading, music
        assert len(profiles["alice"].active_channels) >= 2

    def test_min_messages_filter(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=10)
        # Nobody has 10+ messages in this small sample
        assert len(profiles) == 0

    def test_mention_tracking(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        # Bob mentions alice
        assert "alice" in profiles["bob"].deference_targets or profiles["bob"].mention_given_count > 0


class TestCommunityModel:
    def test_builds_model(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        assert model.member_count > 0
        assert len(model.hierarchy) > 0

    def test_hierarchy_ranked(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        # Should have ranked members
        assert model.hierarchy[0]["handle"] in profiles

    def test_community_slang(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        assert len(model.community_slang) > 0


class TestPersonaBlueprint:
    def test_generates_blueprint(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        bp = engine.generate_persona_blueprint(profiles, model)
        assert bp.tone
        assert bp.vocabulary
        assert len(bp.status_path) > 0

    def test_target_rank_newcomer(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        bp = engine.generate_persona_blueprint(profiles, model, target_rank="newcomer")
        assert "Lurk" in bp.status_path[0]

    def test_target_rank_high(self, sample_observations):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        profiles = engine.build_member_profiles(sample_observations, min_messages=3)
        model = engine.build_community_model(profiles, sample_observations)
        bp = engine.generate_persona_blueprint(profiles, model, target_rank="high")
        assert any("initiating" in s.lower() for s in bp.status_path)


class TestDeduplication:
    def test_removes_exact_dupes(self):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        obs = [
            {"content": "same message", "author": "user1", "channel": "gen", "display_name": "", "observed_at": ""},
            {"content": "same message", "author": "user1", "channel": "gen", "display_name": "", "observed_at": ""},
            {"content": "different message", "author": "user1", "channel": "gen", "display_name": "", "observed_at": ""},
        ]
        deduped = engine._deduplicate(obs)
        assert len(deduped) == 2

    def test_keeps_same_content_different_author(self):
        engine = CommunityIntelEngine.__new__(CommunityIntelEngine)
        obs = [
            {"content": "gm", "author": "user1", "channel": "gen", "display_name": "", "observed_at": ""},
            {"content": "gm", "author": "user2", "channel": "gen", "display_name": "", "observed_at": ""},
        ]
        deduped = engine._deduplicate(obs)
        assert len(deduped) == 2
