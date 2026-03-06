"""
Bot Runtime — Autonomous agent loop for deployed personas.

Each bot instance runs a cycle:
  OBSERVE -> COLLECT -> ANALYZE -> ENGAGE -> EXFIL -> SLEEP -> repeat

The runtime manages the lifecycle and dispatches to platform connectors.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Phase(str, Enum):
    LURK = "lurk"           # observation only, no posting
    ENGAGE_LIGHT = "light"  # replies only, no originals
    ENGAGE_FULL = "full"    # full engagement permitted
    DORMANT = "dormant"     # sleeping, periodic check-ins
    BURNED = "burned"       # compromised, no activity


class PlatformConnector(Protocol):
    """Interface for platform-specific adapters."""

    platform: str

    def fetch_timeline(self, count: int = 50) -> list[dict]:
        """Fetch recent posts from the target community/feed."""
        ...

    def fetch_mentions(self) -> list[dict]:
        """Fetch mentions/replies to the bot's account."""
        ...

    def fetch_dms(self) -> list[dict]:
        """Fetch direct messages."""
        ...

    def post(self, text: str, reply_to: str | None = None) -> dict:
        """Post content. Returns post metadata."""
        ...

    def like(self, post_id: str) -> dict:
        """Like/react to a post."""
        ...

    def follow(self, user_id: str) -> dict:
        """Follow a user."""
        ...

    def get_profile(self, user_id: str) -> dict:
        """Get user profile info."""
        ...

    def search(self, query: str, count: int = 20) -> list[dict]:
        """Search posts/users."""
        ...


@dataclass
class CycleResult:
    """Result of one bot runtime cycle."""
    instance_id: str
    phase: Phase
    observed: int = 0
    collected: int = 0
    engaged: int = 0
    exfil_payload: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "phase": self.phase.value,
            "observed": self.observed,
            "collected": self.collected,
            "engaged": self.engaged,
            "exfil_payload": self.exfil_payload,
            "errors": self.errors,
            "duration_s": round(self.duration_s, 2),
        }


@dataclass
class BotConfig:
    """Runtime configuration for a bot instance."""
    instance_id: str
    persona_id: str
    platform: str
    targets: list[str] = field(default_factory=list)       # accounts/channels to monitor
    keywords: list[str] = field(default_factory=list)       # terms to track
    phase: Phase = Phase.LURK
    lurk_hours: float = 48.0                                # min observation before engagement
    cycle_interval_s: int = 1800                            # 30 min between cycles
    posts_per_cycle: int = 2
    max_daily_posts: int = 10
    jitter_s: int = 300                                     # random delay variance
    started_at: float = 0.0
    total_posts_today: int = 0
    last_cycle_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "persona_id": self.persona_id,
            "platform": self.platform,
            "targets": self.targets,
            "keywords": self.keywords,
            "phase": self.phase.value,
            "lurk_hours": self.lurk_hours,
            "cycle_interval_s": self.cycle_interval_s,
            "posts_per_cycle": self.posts_per_cycle,
            "max_daily_posts": self.max_daily_posts,
            "started_at": self.started_at,
            "total_posts_today": self.total_posts_today,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BotConfig":
        d = dict(d)
        if "phase" in d and isinstance(d["phase"], str):
            d["phase"] = Phase(d["phase"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class BotRuntime:
    """
    Manages the autonomous cycle for a single bot instance.
    
    The runtime doesn't call LLMs directly -- it collects observations
    and produces structured outputs that the orchestrator feeds to
    the persona's agent session.
    """

    def __init__(self, config: BotConfig, connector: PlatformConnector | None = None):
        self.config = config
        self.connector = connector
        self._observations: list[dict] = []
        self._contacts: dict[str, dict] = {}
        self._edges: list[dict] = []
        self._vocab_hits: list[dict] = []

    @property
    def in_lurk_phase(self) -> bool:
        if self.config.started_at == 0:
            return True
        elapsed_hours = (time.time() - self.config.started_at) / 3600
        return elapsed_hours < self.config.lurk_hours

    @property
    def can_engage(self) -> bool:
        if self.config.phase == Phase.BURNED:
            return False
        if self.config.phase == Phase.DORMANT:
            return False
        if self.in_lurk_phase:
            return False
        if self.config.total_posts_today >= self.config.max_daily_posts:
            return False
        return True

    def auto_phase(self) -> Phase:
        """Determine phase based on elapsed time and state."""
        if self.config.phase == Phase.BURNED:
            return Phase.BURNED
        if self.in_lurk_phase:
            return Phase.LURK
        elapsed_hours = (time.time() - self.config.started_at) / 3600
        if elapsed_hours < self.config.lurk_hours + 24:
            return Phase.ENGAGE_LIGHT
        return Phase.ENGAGE_FULL

    def observe(self) -> list[dict]:
        """
        Observation phase: collect posts, mentions, activity from the platform.
        Returns raw observations for processing.
        """
        if not self.connector:
            return []

        observations = []

        # Fetch timeline
        try:
            timeline = self.connector.fetch_timeline(count=50)
            for post in timeline:
                obs = {
                    "type": "timeline_post",
                    "author": post.get("author", ""),
                    "text": post.get("text", ""),
                    "post_id": post.get("id", ""),
                    "timestamp": post.get("timestamp", ""),
                    "engagement": post.get("engagement", {}),
                }
                observations.append(obs)
                self._track_contact(obs["author"], "observed")
        except Exception as e:
            logger.error("Timeline fetch failed: %s", e)

        # Fetch mentions
        try:
            mentions = self.connector.fetch_mentions()
            for m in mentions:
                obs = {
                    "type": "mention",
                    "author": m.get("author", ""),
                    "text": m.get("text", ""),
                    "post_id": m.get("id", ""),
                    "timestamp": m.get("timestamp", ""),
                }
                observations.append(obs)
                self._track_contact(obs["author"], "mentioned_us")
        except Exception as e:
            logger.error("Mentions fetch failed: %s", e)

        # Track vocabulary
        for obs in observations:
            text = obs.get("text", "").lower()
            for kw in self.config.keywords:
                if kw.lower() in text:
                    self._vocab_hits.append({
                        "term": kw,
                        "user": obs.get("author", ""),
                        "context": obs.get("text", "")[:200],
                        "post_id": obs.get("post_id", ""),
                    })

        # Track edges (reply chains)
        for obs in observations:
            if obs.get("type") == "mention":
                self._edges.append({
                    "from": obs.get("author", ""),
                    "to": self.config.instance_id,
                    "type": "mention",
                })

        self._observations.extend(observations)
        return observations

    def _track_contact(self, handle: str, interaction_type: str) -> None:
        if not handle:
            return
        if handle not in self._contacts:
            self._contacts[handle] = {
                "handle": handle,
                "first_seen": time.time(),
                "interactions": [],
                "engagement_count": 0,
            }
        self._contacts[handle]["interactions"].append(interaction_type)
        self._contacts[handle]["engagement_count"] += 1

    def build_exfil_payload(self) -> dict:
        """Build structured exfiltration report for collector DB ingestion."""
        payload = {
            "instance_id": self.config.instance_id,
            "persona_id": self.config.persona_id,
            "platform": self.config.platform,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phase": self.config.phase.value,
            "contacts": [
                {
                    "handle": c["handle"],
                    "engagement_type": ", ".join(set(c["interactions"])),
                    "sentiment": "",
                    "engagement_count": c["engagement_count"],
                }
                for c in self._contacts.values()
            ],
            "vocabulary_signals": self._vocab_hits,
            "network_edges": self._edges,
            "raw_content": [
                {
                    "author": o.get("author", ""),
                    "text": o.get("text", "")[:500],
                    "post_id": o.get("post_id", ""),
                }
                for o in self._observations[-100:]  # last 100 observations
            ],
            "stats": {
                "total_observed": len(self._observations),
                "unique_contacts": len(self._contacts),
                "vocab_hits": len(self._vocab_hits),
                "edges_mapped": len(self._edges),
            },
        }
        return payload

    def run_cycle(self) -> CycleResult:
        """
        Execute one full observation-collection cycle.
        
        Returns CycleResult with observations and exfil payload.
        Engagement decisions are made by the persona's LLM session,
        not by this runtime -- we just collect and structure data.
        """
        start = time.time()
        result = CycleResult(
            instance_id=self.config.instance_id,
            phase=self.auto_phase(),
        )

        # Update phase
        self.config.phase = result.phase

        # Observe
        try:
            observations = self.observe()
            result.observed = len(observations)
        except Exception as e:
            result.errors.append(f"observe: {str(e)}")

        # Build exfil
        try:
            result.exfil_payload = self.build_exfil_payload()
            result.collected = result.exfil_payload.get("stats", {}).get("unique_contacts", 0)
        except Exception as e:
            result.errors.append(f"exfil: {str(e)}")

        result.duration_s = time.time() - start
        self.config.last_cycle_at = time.time()

        return result

    def reset_daily_counters(self) -> None:
        """Reset daily post counts. Call at midnight."""
        self.config.total_posts_today = 0

    def burn(self, reason: str = "") -> None:
        """Mark this instance as compromised."""
        self.config.phase = Phase.BURNED
        logger.warning("Instance %s BURNED: %s", self.config.instance_id, reason)

    def clear_observations(self) -> None:
        """Clear accumulated observations after exfil."""
        self._observations.clear()
        self._contacts.clear()
        self._edges.clear()
        self._vocab_hits.clear()
