"""
Context Engine — unified context management with provenance, memory tiers, and token budgets.

Inspired by arXiv:2512.05470 "Everything is Context" file-system abstraction.
All context sources (memory, tools, observations, human notes, scratchpads)
are mounted as uniform context nodes with metadata and access logging.

Architecture:
    ContextNode     — single context artifact with metadata + provenance
    MemoryTier      — raw / distilled / scratchpad separation
    ContextEngine   — assembles, delivers, evaluates context under token constraints
    ProvenanceLog   — immutable audit trail of context assembly decisions

Every context assembly is logged: what sources were used, what was trimmed,
what token budget was allocated, and what the output quality score was.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    """Memory separation: raw history, distilled knowledge, ephemeral scratchpad."""
    RAW = "raw"              # Full conversation history, observations
    DISTILLED = "distilled"  # Long-term profiles, learned patterns, compressed knowledge
    SCRATCHPAD = "scratchpad" # Per-operation ephemeral notes, discarded after use


class NodeType(str, Enum):
    """Types of context artifacts."""
    OBSERVATION = "observation"   # Raw scraped content
    PROFILE = "profile"           # Target/community profile
    MEMORY = "memory"             # Persistent memory entry
    TOOL_OUTPUT = "tool_output"   # Result from tool execution
    HUMAN_NOTE = "human_note"     # Director/operator input
    SCRATCHPAD = "scratchpad"     # Ephemeral working memory
    MISSION = "mission"           # Active mission context
    PERSONA = "persona"           # Persona configuration


@dataclass
class ContextNode:
    """Single context artifact with metadata and provenance."""
    node_id: str
    node_type: NodeType
    tier: MemoryTier
    content: str
    source: str                          # Origin: collector, tool, human, etc.
    created_at: float = 0.0
    expires_at: float = 0.0              # 0 = never expires
    priority: int = 5                    # 1 (highest) to 10 (lowest)
    token_estimate: int = 0
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.token_estimate:
            self.token_estimate = len(self.content) // 4  # rough estimate

    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "type": self.node_type.value,
            "tier": self.tier.value,
            "source": self.source,
            "created_at": self.created_at,
            "priority": self.priority,
            "tokens": self.token_estimate,
            "tags": self.tags,
            "content_hash": hashlib.sha256(self.content.encode()).hexdigest()[:16],
        }


PROVENANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS context_assemblies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assembly_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    purpose TEXT NOT NULL,
    target TEXT DEFAULT '',
    token_budget INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL,
    nodes_considered INTEGER NOT NULL,
    nodes_included INTEGER NOT NULL,
    nodes_trimmed INTEGER NOT NULL,
    node_ids TEXT NOT NULL,
    trimmed_ids TEXT DEFAULT '[]',
    quality_score REAL DEFAULT 0.0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS context_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    node_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL DEFAULT 0.0,
    priority INTEGER DEFAULT 5,
    token_estimate INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    access_count INTEGER DEFAULT 0,
    last_accessed REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS memory_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assembly_id TEXT NOT NULL,
    action TEXT NOT NULL,
    node_id TEXT NOT NULL,
    reason TEXT DEFAULT '',
    timestamp REAL NOT NULL
);
"""


class ProvenanceLog:
    """Immutable audit trail for context assembly decisions."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or Path.home() / ".seithar" / "context.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(PROVENANCE_SCHEMA)
        self._conn.commit()

    def log_assembly(
        self,
        assembly_id: str,
        purpose: str,
        target: str,
        token_budget: int,
        tokens_used: int,
        nodes_considered: list[ContextNode],
        nodes_included: list[ContextNode],
        nodes_trimmed: list[ContextNode],
        quality_score: float = 0.0,
        metadata: dict | None = None,
    ) -> None:
        self._conn.execute(
            """INSERT INTO context_assemblies
            (assembly_id, timestamp, purpose, target, token_budget, tokens_used,
             nodes_considered, nodes_included, nodes_trimmed, node_ids, trimmed_ids,
             quality_score, metadata)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                assembly_id, purpose, target, token_budget, tokens_used,
                len(nodes_considered), len(nodes_included), len(nodes_trimmed),
                json.dumps([n.node_id for n in nodes_included]),
                json.dumps([n.node_id for n in nodes_trimmed]),
                quality_score,
                json.dumps(metadata or {}),
            ),
        )
        self._conn.commit()

    def log_memory_update(self, assembly_id: str, action: str, node_id: str, reason: str = "") -> None:
        self._conn.execute(
            "INSERT INTO memory_updates (assembly_id, action, node_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (assembly_id, action, node_id, reason, time.time()),
        )
        self._conn.commit()

    def get_assembly_history(self, limit: int = 20) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM context_assemblies ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self._conn.close()


class ContextEngine:
    """
    Assembles, delivers, and evaluates context under token constraints.

    Context Constructor: mounts sources, builds node pool
    Context Loader: selects and packs nodes within token budget
    Context Evaluator: scores output quality, updates memory tiers
    """

    def __init__(self, db_path: str | Path | None = None):
        self.provenance = ProvenanceLog(db_path)
        self._nodes: dict[str, ContextNode] = {}
        self._assembly_counter = 0
        self._load_persisted_nodes()

    def _load_persisted_nodes(self) -> None:
        """Load non-expired nodes from the provenance DB."""
        try:
            cur = self.provenance._conn.execute(
                "SELECT node_id, node_type, tier, source, content, created_at, "
                "expires_at, priority, token_estimate, metadata, tags FROM context_nodes"
            )
            now = time.time()
            for row in cur.fetchall():
                expires = row[6]
                if expires > 0 and now > expires:
                    continue
                node = ContextNode(
                    node_id=row[0],
                    node_type=NodeType(row[1]),
                    tier=MemoryTier(row[2]),
                    source=row[3],
                    content=row[4],
                    created_at=row[5],
                    expires_at=expires,
                    priority=row[7],
                    token_estimate=row[8],
                    metadata=json.loads(row[9]) if row[9] else {},
                    tags=json.loads(row[10]) if row[10] else [],
                )
                self._nodes[node.node_id] = node
        except Exception as e:
            logger.debug("No persisted nodes to load: %s", e)

    def mount(self, node: ContextNode) -> None:
        """Mount a context node into the engine."""
        self._nodes[node.node_id] = node
        self.provenance._conn.execute(
            """INSERT OR REPLACE INTO context_nodes
            (node_id, node_type, tier, source, content, created_at, expires_at,
             priority, token_estimate, metadata, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node.node_id, node.node_type.value, node.tier.value,
                node.source, node.content, node.created_at, node.expires_at,
                node.priority, node.token_estimate,
                json.dumps(node.metadata), json.dumps(node.tags),
            ),
        )
        self.provenance._conn.commit()

    def unmount(self, node_id: str) -> None:
        """Remove a context node."""
        self._nodes.pop(node_id, None)
        self.provenance._conn.execute("DELETE FROM context_nodes WHERE node_id = ?", (node_id,))
        self.provenance._conn.commit()

    def get(self, node_id: str) -> ContextNode | None:
        """Retrieve a node and log access."""
        node = self._nodes.get(node_id)
        if node and not node.is_expired():
            self.provenance._conn.execute(
                "UPDATE context_nodes SET access_count = access_count + 1, last_accessed = ? WHERE node_id = ?",
                (time.time(), node_id),
            )
            self.provenance._conn.commit()
            return node
        return None

    def query(
        self,
        node_type: NodeType | None = None,
        tier: MemoryTier | None = None,
        tags: list[str] | None = None,
        max_priority: int = 10,
    ) -> list[ContextNode]:
        """Query mounted nodes with filters."""
        now = time.time()
        results = []
        for node in self._nodes.values():
            if node.is_expired():
                continue
            if node_type and node.node_type != node_type:
                continue
            if tier and node.tier != tier:
                continue
            if node.priority > max_priority:
                continue
            if tags and not any(t in node.tags for t in tags):
                continue
            results.append(node)
        return sorted(results, key=lambda n: n.priority)

    def assemble(
        self,
        purpose: str,
        target: str = "",
        token_budget: int = 4000,
        required_types: list[NodeType] | None = None,
        required_tags: list[str] | None = None,
        tier_filter: MemoryTier | None = None,
    ) -> tuple[str, str]:
        """
        Assemble context within token budget. Returns (assembly_id, context_text).

        Selects nodes by priority, respects token budget, logs provenance.
        """
        self._assembly_counter += 1
        assembly_id = f"ctx_{int(time.time())}_{self._assembly_counter}"

        # Gather candidates
        candidates = self.query(tier=tier_filter, tags=required_tags)
        if required_types:
            typed = []
            for rt in required_types:
                typed.extend(self.query(node_type=rt, tier=tier_filter))
            # Merge and deduplicate
            seen = set()
            merged = []
            for n in typed + candidates:
                if n.node_id not in seen:
                    seen.add(n.node_id)
                    merged.append(n)
            candidates = sorted(merged, key=lambda n: n.priority)

        # Pack within budget
        included = []
        trimmed = []
        tokens_used = 0

        for node in candidates:
            if tokens_used + node.token_estimate <= token_budget:
                included.append(node)
                tokens_used += node.token_estimate
            else:
                trimmed.append(node)

        # Build context text
        sections = []
        for node in included:
            header = f"[{node.node_type.value.upper()}:{node.source}]"
            sections.append(f"{header}\n{node.content}")

        context_text = "\n\n".join(sections)

        # Log provenance
        self.provenance.log_assembly(
            assembly_id=assembly_id,
            purpose=purpose,
            target=target,
            token_budget=token_budget,
            tokens_used=tokens_used,
            nodes_considered=candidates,
            nodes_included=included,
            nodes_trimmed=trimmed,
        )

        return assembly_id, context_text

    def evaluate(self, assembly_id: str, quality_score: float, feedback: str = "") -> None:
        """Post-output evaluation. Updates assembly quality and triggers memory updates."""
        self.provenance._conn.execute(
            "UPDATE context_assemblies SET quality_score = ?, metadata = json_set(metadata, '$.feedback', ?) WHERE assembly_id = ?",
            (quality_score, feedback, assembly_id),
        )
        self.provenance._conn.commit()

        # If quality was poor, log for review
        if quality_score < 0.5:
            self.provenance.log_memory_update(
                assembly_id, "flag_low_quality", "", f"score={quality_score}: {feedback}"
            )

    def distill(self, node_id: str, distilled_content: str, reason: str = "") -> str:
        """Promote a raw node to distilled tier with compressed content."""
        old = self._nodes.get(node_id)
        if not old:
            return ""

        new_id = f"distilled_{node_id}"
        distilled = ContextNode(
            node_id=new_id,
            node_type=old.node_type,
            tier=MemoryTier.DISTILLED,
            content=distilled_content,
            source=f"distilled_from:{node_id}",
            priority=min(old.priority, 3),  # distilled = higher priority
            metadata={**old.metadata, "distilled_from": node_id, "reason": reason},
            tags=old.tags,
        )
        self.mount(distilled)
        self.provenance.log_memory_update("manual", "distill", node_id, reason)
        return new_id

    def create_scratchpad(self, operation_id: str, content: str = "", ttl_seconds: int = 3600) -> str:
        """Create an ephemeral scratchpad node for an operation."""
        node_id = f"scratch_{operation_id}"
        node = ContextNode(
            node_id=node_id,
            node_type=NodeType.SCRATCHPAD,
            tier=MemoryTier.SCRATCHPAD,
            content=content,
            source=f"operation:{operation_id}",
            expires_at=time.time() + ttl_seconds,
            priority=2,
        )
        self.mount(node)
        return node_id

    def update_scratchpad(self, node_id: str, content: str) -> bool:
        """Update scratchpad content."""
        node = self._nodes.get(node_id)
        if not node or node.tier != MemoryTier.SCRATCHPAD:
            return False
        node.content = content
        node.token_estimate = len(content) // 4
        self.mount(node)  # re-persist
        return True

    def gc(self) -> int:
        """Garbage collect expired nodes."""
        expired = [nid for nid, n in self._nodes.items() if n.is_expired()]
        for nid in expired:
            self.unmount(nid)
        return len(expired)

    def stats(self) -> dict:
        """Engine statistics."""
        nodes = list(self._nodes.values())
        by_tier = {}
        by_type = {}
        for n in nodes:
            by_tier[n.tier.value] = by_tier.get(n.tier.value, 0) + 1
            by_type[n.node_type.value] = by_type.get(n.node_type.value, 0) + 1

        return {
            "total_nodes": len(nodes),
            "by_tier": by_tier,
            "by_type": by_type,
            "total_tokens": sum(n.token_estimate for n in nodes),
            "assemblies": self.provenance.get_assembly_history(1)[0]["id"]
            if self.provenance.get_assembly_history(1) else 0,
        }

    def close(self):
        self.provenance.close()
