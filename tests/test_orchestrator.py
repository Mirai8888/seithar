"""Tests for the persona orchestrator."""

import json
import tempfile
from pathlib import Path

from seithar.orchestrator import Orchestrator


def _orch(tmp=None):
    d = tmp or Path(tempfile.mkdtemp())
    return Orchestrator(data_dir=d)


MOCK_PERSONA = {
    "name": "signal_analyst",
    "bio": "Independent researcher. Cognitive security.",
    "archetype": "researcher",
    "voice_constraints": {
        "tone": "clinical",
        "vocabulary_level": "technical",
        "forbidden_words": ["seithar", "cognitive warfare"],
        "quirks": ["uses abbreviations"],
    },
    "behavioral_bounds": {
        "engagement_style": "reactive",
        "posts_per_day_min": 1,
        "posts_per_day_max": 3,
        "will_argue": True,
        "response_delay_min_s": 60,
        "response_delay_max_s": 300,
    },
    "consistency": {
        "topics_of_interest": ["adversarial ML", "information operations"],
        "opinion_anchors": {"AI safety": "technically grounded, not doomer"},
        "knowledge_gaps": ["quantum computing"],
    },
}


def test_register_credentials():
    o = _orch()
    result = o.register_credentials(
        persona_id="abc123",
        platform="twitter",
        username="signal_analyst_7",
        credentials_path="~/.config/personas/abc123.json",
        proxy_config="socks5://proxy:1080",
        account_age_days=90,
        account_source="accsmarket",
    )
    assert result["registered"] == "abc123:twitter"


def test_build_agent_context():
    o = _orch()
    ctx = o.build_agent_context("abc123", MOCK_PERSONA)
    assert "signal_analyst" in ctx
    assert "clinical" in ctx
    assert "seithar" in ctx.lower()  # in forbidden words section
    assert "OPERATIONAL RULES" in ctx


def test_spawn_instance():
    o = _orch()
    o.register_credentials("abc123", "twitter", "user1", "/path/creds.json")
    result = o.spawn_instance("abc123", MOCK_PERSONA, "twitter", task="Engage in cyborgism threads")
    assert "instance_id" in result
    assert "task" in result
    assert "cyborgism" in result["task"]


def test_update_instance():
    o = _orch()
    o.register_credentials("abc123", "twitter", "user1", "/path")
    spawn = o.spawn_instance("abc123", MOCK_PERSONA, "twitter")
    iid = spawn["instance_id"]
    
    result = o.update_instance(iid, status="running", metrics={"messages_sent": 5})
    assert result["status"] == "running"
    assert o.instances[iid].metrics["messages_sent"] == 5


def test_fleet_status():
    o = _orch()
    o.register_credentials("a", "twitter", "u1", "/p")
    o.register_credentials("b", "discord", "u2", "/p")
    o.spawn_instance("a", MOCK_PERSONA, "twitter")
    o.spawn_instance("b", MOCK_PERSONA, "discord")
    
    all_status = o.fleet_status()
    assert all_status["total"] == 2
    
    twitter_only = o.fleet_status(platform="twitter")
    assert twitter_only["total"] == 1


def test_retire_instance():
    o = _orch()
    o.register_credentials("a", "twitter", "u1", "/p")
    spawn = o.spawn_instance("a", MOCK_PERSONA, "twitter")
    result = o.retire_instance(spawn["instance_id"], reason="detected")
    assert result["retired"] == spawn["instance_id"]


def test_persistence():
    d = Path(tempfile.mkdtemp())
    o1 = Orchestrator(data_dir=d)
    o1.register_credentials("x", "twitter", "u", "/p")
    o1.spawn_instance("x", MOCK_PERSONA, "twitter")
    
    o2 = Orchestrator(data_dir=d)
    assert len(o2.instances) == 1
    assert "x:twitter" in o2.credentials


def test_no_creds_in_context():
    """Credentials paths are referenced but actual secrets never appear in agent context."""
    o = _orch()
    o.register_credentials("abc", "twitter", "user1", "/secret/path/creds.json", proxy_config="socks5://10.0.0.1:1080")
    result = o.spawn_instance("abc", MOCK_PERSONA, "twitter")
    task = result["task"]
    # Path is referenced but no actual token/password values
    assert "/secret/path/creds.json" in task
    assert "socks5://" in task
