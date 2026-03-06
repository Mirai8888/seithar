"""
Seithar Data Collector — persistent scraping and intelligence storage.

Every bot, every scraper, every feed dumps here. Single source of truth.
SQLite backend, structured for query by the MCP server.

Tables:
    observations  — raw scraped content (tweets, posts, messages)
    contacts      — profiled accounts across platforms
    edges         — social graph edges (follows, replies, mentions, quotes)
    vocabulary    — tracked vocabulary usage signals
    payloads      — delivered payloads and their outcomes
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,          -- bot persona_id, scraper name, or 'manual'
    platform TEXT NOT NULL,        -- twitter, discord, telegram, moltbook
    author_handle TEXT NOT NULL,
    author_id TEXT DEFAULT '',
    content TEXT NOT NULL,
    url TEXT DEFAULT '',
    parent_url TEXT DEFAULT '',    -- reply-to URL if applicable
    observed_at TEXT NOT NULL,     -- ISO timestamp
    ingested_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'     -- JSON blob for platform-specific fields
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    follower_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    profile_data TEXT DEFAULT '{}',  -- JSON: interests, vocabulary, sentiment
    tags TEXT DEFAULT '[]',          -- JSON array: target, ally, neutral, etc.
    UNIQUE(platform, handle)
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    source_handle TEXT NOT NULL,
    target_handle TEXT NOT NULL,
    edge_type TEXT NOT NULL,       -- follows, replied_to, mentioned, quoted, liked
    weight REAL DEFAULT 1.0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    UNIQUE(platform, source_handle, target_handle, edge_type)
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    term TEXT NOT NULL,
    context TEXT DEFAULT '',       -- surrounding text
    url TEXT DEFAULT '',
    observed_at TEXT NOT NULL,
    is_target_vocab INTEGER DEFAULT 0  -- 1 if this is a Seithar target term
);

CREATE TABLE IF NOT EXISTS payloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    payload_type TEXT NOT NULL,    -- vocabulary_injection, framing, bridge_concept
    content TEXT NOT NULL,
    target_handle TEXT DEFAULT '',
    delivered_at TEXT NOT NULL,
    engagement TEXT DEFAULT '{}',  -- JSON: likes, replies, quotes received
    outcome TEXT DEFAULT 'pending' -- pending, amplified, ignored, backfired
);

CREATE INDEX IF NOT EXISTS idx_obs_platform ON observations(platform);
CREATE INDEX IF NOT EXISTS idx_obs_author ON observations(author_handle);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_contacts_platform ON contacts(platform, handle);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_handle);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_handle);
CREATE INDEX IF NOT EXISTS idx_vocab_term ON vocabulary(term);
CREATE INDEX IF NOT EXISTS idx_vocab_handle ON vocabulary(handle);
"""


class Collector:
    """Persistent intelligence collection database."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path.home() / ".seithar" / "collector.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ----- Observations -----

    def add_observation(
        self,
        source: str,
        platform: str,
        author_handle: str,
        content: str,
        url: str = "",
        parent_url: str = "",
        observed_at: str = "",
        author_id: str = "",
        metadata: dict | None = None,
    ) -> int:
        """Store a raw scraped observation (tweet, post, message)."""
        now = self._now()
        cur = self._conn.execute(
            "INSERT INTO observations (source, platform, author_handle, author_id, content, url, parent_url, observed_at, ingested_at, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (source, platform, author_handle, author_id, content, url, parent_url, observed_at or now, now, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return cur.lastrowid

    def query_observations(
        self,
        platform: str | None = None,
        author: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query stored observations with filters."""
        clauses, params = [], []
        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        if author:
            clauses.append("author_handle = ?")
            params.append(author)
        if since:
            clauses.append("observed_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM observations {where} ORDER BY observed_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    # ----- Contacts -----

    def upsert_contact(
        self,
        platform: str,
        handle: str,
        display_name: str = "",
        bio: str = "",
        follower_count: int = 0,
        following_count: int = 0,
        profile_data: dict | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Insert or update a contact profile."""
        now = self._now()
        existing = self._conn.execute(
            "SELECT * FROM contacts WHERE platform = ? AND handle = ?",
            (platform, handle),
        ).fetchone()

        if existing:
            self._conn.execute(
                "UPDATE contacts SET display_name=?, bio=?, follower_count=?, following_count=?, last_seen=?, profile_data=?, tags=? WHERE platform=? AND handle=?",
                (display_name or existing["display_name"], bio or existing["bio"],
                 follower_count or existing["follower_count"],
                 following_count or existing["following_count"],
                 now, json.dumps(profile_data or json.loads(existing["profile_data"])),
                 json.dumps(tags or json.loads(existing["tags"])),
                 platform, handle),
            )
        else:
            self._conn.execute(
                "INSERT INTO contacts (platform, handle, display_name, bio, follower_count, following_count, first_seen, last_seen, profile_data, tags) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (platform, handle, display_name, bio, follower_count, following_count, now, now, json.dumps(profile_data or {}), json.dumps(tags or [])),
            )
        self._conn.commit()
        return {"platform": platform, "handle": handle, "status": "upserted"}

    def get_contact(self, platform: str, handle: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM contacts WHERE platform = ? AND handle = ?",
            (platform, handle),
        ).fetchone()
        return dict(row) if row else None

    def search_contacts(self, platform: str | None = None, tag: str | None = None, limit: int = 50) -> list[dict]:
        clauses, params = [], []
        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM contacts {where} ORDER BY last_seen DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    # ----- Edges -----

    def add_edge(
        self,
        platform: str,
        source_handle: str,
        target_handle: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> dict:
        """Add or increment a social graph edge."""
        now = self._now()
        existing = self._conn.execute(
            "SELECT * FROM edges WHERE platform=? AND source_handle=? AND target_handle=? AND edge_type=?",
            (platform, source_handle, target_handle, edge_type),
        ).fetchone()

        if existing:
            self._conn.execute(
                "UPDATE edges SET count=count+1, weight=?, last_seen=? WHERE id=?",
                (weight, now, existing["id"]),
            )
        else:
            self._conn.execute(
                "INSERT INTO edges (platform, source_handle, target_handle, edge_type, weight, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
                (platform, source_handle, target_handle, edge_type, weight, now, now),
            )
        self._conn.commit()
        return {"edge": f"{source_handle}->{target_handle}", "type": edge_type}

    def get_edges(self, handle: str, direction: str = "both", platform: str | None = None, limit: int = 100) -> list[dict]:
        clauses, params = [], []
        if direction == "out":
            clauses.append("source_handle = ?")
            params.append(handle)
        elif direction == "in":
            clauses.append("target_handle = ?")
            params.append(handle)
        else:
            clauses.append("(source_handle = ? OR target_handle = ?)")
            params.extend([handle, handle])
        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        where = f"WHERE {' AND '.join(clauses)}"
        rows = self._conn.execute(
            f"SELECT * FROM edges {where} ORDER BY count DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    # ----- Vocabulary -----

    def add_vocabulary_signal(
        self,
        platform: str,
        handle: str,
        term: str,
        context: str = "",
        url: str = "",
        observed_at: str = "",
        is_target_vocab: bool = False,
    ) -> int:
        now = self._now()
        cur = self._conn.execute(
            "INSERT INTO vocabulary (platform, handle, term, context, url, observed_at, is_target_vocab) VALUES (?,?,?,?,?,?,?)",
            (platform, handle, term, context, url, observed_at or now, 1 if is_target_vocab else 0),
        )
        self._conn.commit()
        return cur.lastrowid

    def vocabulary_stats(self, term: str | None = None, platform: str | None = None) -> dict:
        """Get vocabulary adoption statistics."""
        clauses, params = [], []
        if term:
            clauses.append("term = ?")
            params.append(term)
        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        total = self._conn.execute(f"SELECT COUNT(*) FROM vocabulary {where}", params).fetchone()[0]
        unique_users = self._conn.execute(f"SELECT COUNT(DISTINCT handle) FROM vocabulary {where}", params).fetchone()[0]

        top_terms = self._conn.execute(
            f"SELECT term, COUNT(*) as cnt, COUNT(DISTINCT handle) as users FROM vocabulary {where} GROUP BY term ORDER BY cnt DESC LIMIT 20",
            params,
        ).fetchall()

        return {
            "total_signals": total,
            "unique_users": unique_users,
            "top_terms": [{"term": r[0], "count": r[1], "unique_users": r[2]} for r in top_terms],
        }

    # ----- Payloads -----

    def record_payload(
        self,
        persona_id: str,
        platform: str,
        payload_type: str,
        content: str,
        target_handle: str = "",
    ) -> int:
        now = self._now()
        cur = self._conn.execute(
            "INSERT INTO payloads (persona_id, platform, payload_type, content, target_handle, delivered_at) VALUES (?,?,?,?,?,?)",
            (persona_id, platform, payload_type, content, target_handle, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_payload_outcome(self, payload_id: int, outcome: str, engagement: dict | None = None) -> dict:
        self._conn.execute(
            "UPDATE payloads SET outcome=?, engagement=? WHERE id=?",
            (outcome, json.dumps(engagement or {}), payload_id),
        )
        self._conn.commit()
        return {"payload_id": payload_id, "outcome": outcome}

    # ----- Stats -----

    def stats(self) -> dict:
        """Overall collection statistics."""
        obs = self._conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        contacts = self._conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        edges = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        vocab = self._conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
        payloads = self._conn.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]
        return {
            "observations": obs,
            "contacts": contacts,
            "edges": edges,
            "vocabulary_signals": vocab,
            "payloads": payloads,
        }

    # ----- Bulk ingest (from bot exfil reports) -----

    def ingest_bot_report(self, persona_id: str, platform: str, report: dict) -> dict:
        """
        Ingest a structured exfiltration report from a bot.
        
        Expected format matches the agent context exfil spec:
        {
            "contacts": [{"handle": "", "engagement_type": "", "sentiment": ""}],
            "vocabulary_signals": [{"term": "", "user": "", "context": ""}],
            "network_edges": [{"from": "", "to": "", "type": ""}],
            "raw_content": [{"author": "", "text": "", "url": ""}]
        }
        """
        counts = {"observations": 0, "contacts": 0, "edges": 0, "vocabulary": 0}

        for item in report.get("raw_content", []):
            self.add_observation(
                source=persona_id, platform=platform,
                author_handle=item.get("author", ""),
                content=item.get("text", ""),
                url=item.get("url", ""),
            )
            counts["observations"] += 1

        for item in report.get("contacts", []):
            self.upsert_contact(
                platform=platform,
                handle=item.get("handle", ""),
                profile_data={"engagement_type": item.get("engagement_type"), "sentiment": item.get("sentiment")},
            )
            counts["contacts"] += 1

        for item in report.get("network_edges", []):
            self.add_edge(
                platform=platform,
                source_handle=item.get("from", ""),
                target_handle=item.get("to", ""),
                edge_type=item.get("type", "interaction"),
            )
            counts["edges"] += 1

        for item in report.get("vocabulary_signals", []):
            self.add_vocabulary_signal(
                platform=platform,
                handle=item.get("user", ""),
                term=item.get("term", ""),
                context=item.get("context", ""),
                is_target_vocab=True,
            )
            counts["vocabulary"] += 1

        return {"ingested": counts, "source": persona_id}

    def close(self):
        self._conn.close()
