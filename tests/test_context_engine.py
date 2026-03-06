"""Tests for context_engine.py — unified context management."""

import time
import tempfile
from pathlib import Path

import pytest

from seithar.context_engine import (
    ContextEngine, ContextNode, MemoryTier, NodeType, ProvenanceLog,
)


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "test_context.db"
    eng = ContextEngine(db_path=db)
    yield eng
    eng.close()


@pytest.fixture
def sample_nodes():
    return [
        ContextNode(
            node_id="obs_1",
            node_type=NodeType.OBSERVATION,
            tier=MemoryTier.RAW,
            content="Target posted about cognitive security frameworks",
            source="collector",
            priority=5,
            tags=["target_alpha"],
        ),
        ContextNode(
            node_id="profile_1",
            node_type=NodeType.PROFILE,
            tier=MemoryTier.DISTILLED,
            content="Target: academic, interested in active inference, 5k followers",
            source="profiler",
            priority=2,
            tags=["target_alpha"],
        ),
        ContextNode(
            node_id="mission_1",
            node_type=NodeType.MISSION,
            tier=MemoryTier.DISTILLED,
            content="Objective: introduce seithar vocabulary into target community",
            source="operator",
            priority=1,
            tags=["op_sunrise"],
        ),
        ContextNode(
            node_id="scratch_1",
            node_type=NodeType.SCRATCHPAD,
            tier=MemoryTier.SCRATCHPAD,
            content="Working notes: target responded positively to last probe",
            source="bot_runtime",
            priority=3,
            expires_at=time.time() + 3600,
        ),
    ]


def test_mount_and_get(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    retrieved = engine.get("obs_1")
    assert retrieved is not None
    assert retrieved.content == "Target posted about cognitive security frameworks"
    assert retrieved.node_type == NodeType.OBSERVATION


def test_mount_persists(tmp_path, sample_nodes):
    db = tmp_path / "persist_test.db"
    eng1 = ContextEngine(db_path=db)
    for node in sample_nodes:
        eng1.mount(node)
    eng1.close()

    eng2 = ContextEngine(db_path=db)
    assert eng2.get("profile_1") is not None
    assert eng2.get("profile_1").content == sample_nodes[1].content
    eng2.close()


def test_unmount(engine, sample_nodes):
    engine.mount(sample_nodes[0])
    assert engine.get("obs_1") is not None
    engine.unmount("obs_1")
    assert engine.get("obs_1") is None


def test_query_by_type(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    observations = engine.query(node_type=NodeType.OBSERVATION)
    assert len(observations) == 1
    assert observations[0].node_id == "obs_1"


def test_query_by_tier(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    distilled = engine.query(tier=MemoryTier.DISTILLED)
    assert len(distilled) == 2
    # Should be sorted by priority
    assert distilled[0].priority <= distilled[1].priority


def test_query_by_tags(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    tagged = engine.query(tags=["target_alpha"])
    assert len(tagged) == 2


def test_query_by_priority(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    high_priority = engine.query(max_priority=3)
    assert all(n.priority <= 3 for n in high_priority)


def test_assemble_basic(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    assembly_id, context = engine.assemble(
        purpose="reply_to_target",
        target="target_alpha",
        token_budget=4000,
    )
    
    assert assembly_id.startswith("ctx_")
    assert len(context) > 0
    assert "MISSION" in context or "PROFILE" in context


def test_assemble_token_budget(engine):
    # Mount a bunch of large nodes
    for i in range(20):
        engine.mount(ContextNode(
            node_id=f"big_{i}",
            node_type=NodeType.OBSERVATION,
            tier=MemoryTier.RAW,
            content="x" * 1000,  # ~250 tokens each
            source="test",
            priority=5,
        ))
    
    _, context = engine.assemble(purpose="test", token_budget=500)
    # Should only include ~2 nodes worth
    assert len(context) < 3000


def test_assemble_priority_ordering(engine):
    engine.mount(ContextNode(
        node_id="low_pri",
        node_type=NodeType.OBSERVATION,
        tier=MemoryTier.RAW,
        content="low priority content",
        source="test",
        priority=9,
    ))
    engine.mount(ContextNode(
        node_id="high_pri",
        node_type=NodeType.MISSION,
        tier=MemoryTier.DISTILLED,
        content="high priority mission",
        source="test",
        priority=1,
    ))
    
    _, context = engine.assemble(purpose="test", token_budget=100)
    # High priority should be included first
    assert "high priority mission" in context


def test_assemble_provenance_logged(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    engine.assemble(purpose="test_provenance", target="alpha", token_budget=4000)
    
    history = engine.provenance.get_assembly_history(1)
    assert len(history) == 1
    assert history[0]["purpose"] == "test_provenance"
    assert history[0]["target"] == "alpha"


def test_evaluate(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    aid, _ = engine.assemble(purpose="test_eval", token_budget=4000)
    engine.evaluate(aid, quality_score=0.8, feedback="good context")
    
    history = engine.provenance.get_assembly_history(1)
    assert history[0]["quality_score"] == 0.8


def test_evaluate_low_quality_flags(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    aid, _ = engine.assemble(purpose="test_low", token_budget=4000)
    engine.evaluate(aid, quality_score=0.3, feedback="missing target history")
    
    cur = engine.provenance._conn.execute(
        "SELECT * FROM memory_updates WHERE assembly_id = ?", (aid,)
    )
    updates = cur.fetchall()
    assert len(updates) == 1


def test_distill(engine):
    raw = ContextNode(
        node_id="raw_obs",
        node_type=NodeType.OBSERVATION,
        tier=MemoryTier.RAW,
        content="Long raw observation with lots of detail about target behavior over time...",
        source="collector",
        priority=6,
        tags=["target_beta"],
    )
    engine.mount(raw)
    
    new_id = engine.distill(
        "raw_obs",
        "Target beta: responds to academic framing, active 9-11pm EST",
        reason="compressed from 2 weeks of observations",
    )
    
    assert new_id == "distilled_raw_obs"
    distilled = engine.get(new_id)
    assert distilled is not None
    assert distilled.tier == MemoryTier.DISTILLED
    assert distilled.priority <= raw.priority


def test_scratchpad_lifecycle(engine):
    sid = engine.create_scratchpad("op_123", "initial notes", ttl_seconds=3600)
    assert engine.get(sid) is not None
    
    engine.update_scratchpad(sid, "updated notes after probe")
    updated = engine.get(sid)
    assert "updated notes" in updated.content
    
    # Unmount
    engine.unmount(sid)
    assert engine.get(sid) is None


def test_expired_scratchpad(engine):
    node = ContextNode(
        node_id="expired_scratch",
        node_type=NodeType.SCRATCHPAD,
        tier=MemoryTier.SCRATCHPAD,
        content="should be expired",
        source="test",
        expires_at=time.time() - 1,  # already expired
    )
    engine.mount(node)
    assert engine.get("expired_scratch") is None


def test_gc(engine):
    engine.mount(ContextNode(
        node_id="alive",
        node_type=NodeType.OBSERVATION,
        tier=MemoryTier.RAW,
        content="still valid",
        source="test",
    ))
    engine.mount(ContextNode(
        node_id="dead",
        node_type=NodeType.SCRATCHPAD,
        tier=MemoryTier.SCRATCHPAD,
        content="expired",
        source="test",
        expires_at=time.time() - 1,
    ))
    
    removed = engine.gc()
    assert removed == 1
    assert engine.get("alive") is not None
    assert engine.get("dead") is None


def test_stats(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    stats = engine.stats()
    assert stats["total_nodes"] == 4
    assert "raw" in stats["by_tier"]
    assert "distilled" in stats["by_tier"]


def test_node_to_dict(sample_nodes):
    d = sample_nodes[0].to_dict()
    assert d["node_id"] == "obs_1"
    assert d["type"] == "observation"
    assert d["tier"] == "raw"
    assert "content_hash" in d


def test_required_types_filter(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    _, context = engine.assemble(
        purpose="mission_context",
        token_budget=4000,
        required_types=[NodeType.MISSION, NodeType.PROFILE],
    )
    assert "Objective" in context or "academic" in context


def test_multiple_assemblies_logged(engine, sample_nodes):
    for node in sample_nodes:
        engine.mount(node)
    
    engine.assemble(purpose="first", token_budget=4000)
    engine.assemble(purpose="second", token_budget=4000)
    engine.assemble(purpose="third", token_budget=4000)
    
    history = engine.provenance.get_assembly_history(10)
    assert len(history) == 3
