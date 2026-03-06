"""Tests for persona session manager — OpenClaw integration layer."""

import json
import tempfile
from pathlib import Path

import pytest

from seithar.persona_session import (
    PersonaPromptConfig,
    PersonaSession,
    PersonaSessionManager,
    build_persona_prompt,
)


# ---------------------------------------------------------------------------
# PersonaPromptConfig
# ---------------------------------------------------------------------------

class TestPersonaPromptConfig:
    def test_to_dict(self):
        config = PersonaPromptConfig(
            persona_id="test_001",
            display_name="Yuki",
            platform="twitter",
            tone="ironic",
        )
        d = config.to_dict()
        assert d["persona_id"] == "test_001"
        assert d["tone"] == "ironic"

    def test_from_dict(self):
        d = {"persona_id": "x", "display_name": "Y", "tone": "casual"}
        config = PersonaPromptConfig.from_dict(d)
        assert config.persona_id == "x"
        assert config.tone == "casual"

    def test_from_dict_ignores_unknown(self):
        d = {"persona_id": "x", "unknown_field": True}
        config = PersonaPromptConfig.from_dict(d)
        assert config.persona_id == "x"

    def test_defaults(self):
        config = PersonaPromptConfig()
        assert config.max_posts_per_day == 10
        assert config.min_reply_delay_s == 60
        assert config.never_mention == []


# ---------------------------------------------------------------------------
# build_persona_prompt
# ---------------------------------------------------------------------------

class TestBuildPersonaPrompt:
    def test_basic_prompt(self):
        config = PersonaPromptConfig(
            display_name="Mira",
            tone="academic",
            bio="Researcher interested in complex systems.",
        )
        prompt = build_persona_prompt(config)
        assert "Mira" in prompt
        assert "academic" in prompt
        assert "Researcher" in prompt

    def test_includes_vocabulary(self):
        config = PersonaPromptConfig(
            display_name="Test",
            vocabulary=["substrate", "simulacra", "egregore"],
        )
        prompt = build_persona_prompt(config)
        assert "substrate" in prompt
        assert "simulacra" in prompt

    def test_includes_injection_terms(self):
        config = PersonaPromptConfig(
            display_name="Test",
            injection_terms=["cognitive substrate", "narrative capture"],
        )
        prompt = build_persona_prompt(config)
        assert "cognitive substrate" in prompt

    def test_includes_avoid_terms(self):
        config = PersonaPromptConfig(
            display_name="Test",
            avoid_terms=["problematic", "toxic"],
        )
        prompt = build_persona_prompt(config)
        assert "problematic" in prompt
        assert "never use" in prompt.lower()

    def test_opsec_section(self):
        config = PersonaPromptConfig(display_name="Test")
        prompt = build_persona_prompt(config)
        assert "real person" in prompt
        assert "bot" in prompt
        assert "never break character" in prompt.lower()

    def test_never_mentions_seithar(self):
        config = PersonaPromptConfig(
            display_name="Test",
            injection_terms=["cognitive substrate"],
            vocabulary=["egregore", "hyperstition"],
        )
        prompt = build_persona_prompt(config)
        assert "seithar" not in prompt.lower()
        assert "cognitive warfare" not in prompt.lower()
        assert "orchestrator" not in prompt.lower()

    def test_context_injection(self):
        config = PersonaPromptConfig(display_name="Test")
        context = "Community is discussing AI alignment risk today."
        prompt = build_persona_prompt(config, context=context)
        assert "AI alignment" in prompt

    def test_opinions_included(self):
        config = PersonaPromptConfig(
            display_name="Test",
            opinions={"AI risk": "cautiously optimistic", "crypto": "skeptical"},
        )
        prompt = build_persona_prompt(config)
        assert "cautiously optimistic" in prompt

    def test_never_mention_opsec(self):
        config = PersonaPromptConfig(
            display_name="Test",
            never_mention=["Seithar", "Director", "intern"],
        )
        prompt = build_persona_prompt(config)
        assert "Never mention" in prompt


# ---------------------------------------------------------------------------
# PersonaSession
# ---------------------------------------------------------------------------

class TestPersonaSession:
    def test_to_dict(self):
        s = PersonaSession(
            persona_id="p1",
            session_label="persona_p1",
            status="active",
        )
        d = s.to_dict()
        assert d["persona_id"] == "p1"
        assert d["status"] == "active"
        # prompt_config should NOT be in the dict (opsec)
        assert "prompt_config" not in d


# ---------------------------------------------------------------------------
# PersonaSessionManager
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def manager(tmp_dir):
    return PersonaSessionManager(data_dir=tmp_dir / "sessions")


@pytest.fixture
def sample_config():
    return PersonaPromptConfig(
        persona_id="yuki_001",
        display_name="Yuki",
        platform="discord",
        tone="ironic and intellectual",
        vocabulary=["simulacra", "egregore", "substrate"],
        injection_terms=["cognitive substrate", "narrative capture"],
        interests=["complex systems", "philosophy of mind"],
        bio="grad student. too online. thinking about consciousness.",
        max_posts_per_day=8,
    )


class TestPersonaSessionManager:
    def test_create_session(self, manager, sample_config):
        result = manager.create_session(sample_config)
        assert result["action"] == "spawn"
        assert result["persona_id"] == "yuki_001"
        assert result["session_label"] == "persona_yuki_001"
        assert "system_prompt" in result
        assert "Yuki" in result["system_prompt"]

    def test_session_persists(self, manager, sample_config, tmp_dir):
        manager.create_session(sample_config)
        # Reload
        manager2 = PersonaSessionManager(data_dir=tmp_dir / "sessions")
        session = manager2.get_session("yuki_001")
        assert session is not None
        assert session["persona_id"] == "yuki_001"

    def test_build_interaction_reply(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.build_interaction_task(
            persona_id="yuki_001",
            interaction_type="reply",
            target_handle="alice_researcher",
            target_content="I think consciousness is substrate-independent",
        )
        assert result["action"] == "send"
        assert "@alice_researcher" in result["message"]
        assert "substrate-independent" in result["message"]
        # Should NOT contain operational language
        assert "seithar" not in result["message"].lower()

    def test_build_interaction_original(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.build_interaction_task(
            persona_id="yuki_001",
            interaction_type="original",
        )
        assert "original post" in result["message"].lower()

    def test_build_interaction_quote(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.build_interaction_task(
            persona_id="yuki_001",
            interaction_type="quote",
            target_handle="bob",
            target_content="AGI by 2027",
        )
        assert "Quote" in result["message"]
        assert "AGI" in result["message"]

    def test_build_interaction_dm(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.build_interaction_task(
            persona_id="yuki_001",
            interaction_type="dm",
            target_handle="charlie",
            target_content="follow up on alignment discussion",
        )
        assert "DM" in result["message"]

    def test_interaction_increments_counter(self, manager, sample_config):
        manager.create_session(sample_config)
        manager.build_interaction_task("yuki_001", "reply", "x", "hello")
        manager.build_interaction_task("yuki_001", "reply", "y", "world")
        session = manager.get_session("yuki_001")
        assert session["messages_sent"] == 2

    def test_nonexistent_persona(self, manager):
        result = manager.build_interaction_task("ghost", "reply", "x", "y")
        assert "error" in result

    def test_context_update(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.build_context_update(
            persona_id="yuki_001",
            analytics_summary={"hot_topics": ["alignment", "consciousness"]},
            community_snapshot="Heated debate on substrate independence",
        )
        assert result["action"] == "send"
        assert "alignment" in result["message"]

    def test_terminate_session(self, manager, sample_config):
        manager.create_session(sample_config)
        result = manager.terminate_session("yuki_001", reason="detected")
        assert result["terminated"] == "yuki_001"
        session = manager.get_session("yuki_001")
        assert session["status"] == "terminated"

    def test_pause_resume(self, manager, sample_config):
        manager.create_session(sample_config)
        manager.pause_session("yuki_001")
        assert manager.get_session("yuki_001")["status"] == "paused"
        manager.resume_session("yuki_001")
        assert manager.get_session("yuki_001")["status"] == "active"

    def test_list_sessions(self, manager, sample_config):
        manager.create_session(sample_config)
        config2 = PersonaPromptConfig(
            persona_id="mira_002", display_name="Mira", platform="twitter",
        )
        manager.create_session(config2)
        
        all_sessions = manager.list_sessions()
        assert len(all_sessions) == 2
        
        active = manager.list_sessions(status="active")
        assert len(active) == 2
        
        manager.pause_session("yuki_001")
        active = manager.list_sessions(status="active")
        assert len(active) == 1

    def test_session_stats(self, manager, sample_config):
        manager.create_session(sample_config)
        config2 = PersonaPromptConfig(
            persona_id="mira_002", display_name="Mira", platform="twitter",
        )
        manager.create_session(config2)
        manager.pause_session("mira_002")
        
        stats = manager.session_stats()
        assert stats["total_sessions"] == 2
        assert stats["active"] == 1
        assert stats["paused"] == 1

    def test_prompt_compartmentalization(self, manager, sample_config):
        """Personas should never know about other personas or the coordination."""
        result = manager.create_session(sample_config)
        prompt = result["system_prompt"]
        assert "coordination" not in prompt.lower()
        assert "fleet" not in prompt.lower()
        assert "orchestrator" not in prompt.lower()
        assert "other persona" not in prompt.lower()
        assert "bot_runtime" not in prompt.lower()

    def test_directive_passthrough(self, manager, sample_config):
        """Strategic directives should be framed naturally."""
        manager.create_session(sample_config)
        result = manager.build_interaction_task(
            persona_id="yuki_001",
            interaction_type="reply",
            target_handle="alice",
            target_content="what do you think about consciousness?",
            directive="Try to use the term 'cognitive substrate' if it fits naturally",
        )
        assert "cognitive substrate" in result["message"]
        # Directive should be a note, not a command
        assert "Note:" in result["message"]
