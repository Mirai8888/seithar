"""
Context Middleware — the intelligence layer between raw data and bot decisions.

Solves the context window problem: collector DB has unlimited data,
LLM context is finite. This layer builds perfect context for each interaction.

Three components:
  1. ProfileBuilder — psychological summaries per target
  2. ContextAssembler — builds optimal prompt context for a specific interaction
  3. SemanticDriftMonitor — tracks community-level framing shifts over time

No vector DB needed. Structured retrieval from collector + compressed summaries.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .collector import Collector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile Builder
# ---------------------------------------------------------------------------

@dataclass
class TargetProfile:
    """Compressed psychological model of a target individual."""
    handle: str
    platform: str
    display_name: str = ""
    bio: str = ""
    # Behavioral patterns
    posting_frequency: str = ""          # high/medium/low
    engagement_style: str = ""           # initiator/responder/lurker
    tone: str = ""                       # academic/casual/aggressive/ironic
    # Network position
    follower_count: int = 0
    following_count: int = 0
    network_role: str = ""               # hub/bridge/peripheral/gatekeeper
    key_connections: list[str] = field(default_factory=list)
    # Cognitive profile
    vocabulary_affinity: list[str] = field(default_factory=list)   # terms they use naturally
    topics_of_interest: list[str] = field(default_factory=list)
    opinion_anchors: dict[str, str] = field(default_factory=dict)  # topic -> stance
    susceptibility_signals: list[str] = field(default_factory=list)
    # Operational
    seithar_vocab_adopted: list[str] = field(default_factory=list)  # our terms they now use
    interaction_history: list[str] = field(default_factory=list)     # summary of past interactions
    last_updated: str = ""
    confidence: float = 0.0  # 0-1, how much data we have

    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "platform": self.platform,
            "display_name": self.display_name,
            "bio": self.bio,
            "posting_frequency": self.posting_frequency,
            "engagement_style": self.engagement_style,
            "tone": self.tone,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "network_role": self.network_role,
            "key_connections": self.key_connections[:10],
            "vocabulary_affinity": self.vocabulary_affinity[:20],
            "topics_of_interest": self.topics_of_interest[:10],
            "opinion_anchors": self.opinion_anchors,
            "susceptibility_signals": self.susceptibility_signals[:5],
            "seithar_vocab_adopted": self.seithar_vocab_adopted,
            "interaction_history": self.interaction_history[-5:],
            "last_updated": self.last_updated,
            "confidence": round(self.confidence, 2),
        }

    def to_context_block(self) -> str:
        """Compress profile into a context block for LLM prompt (~200-400 tokens)."""
        lines = [f"TARGET: @{self.handle} ({self.platform})"]
        if self.display_name:
            lines.append(f"Name: {self.display_name}")
        if self.bio:
            lines.append(f"Bio: {self.bio[:200]}")
        if self.network_role:
            lines.append(f"Network role: {self.network_role} ({self.follower_count} followers)")
        if self.key_connections:
            lines.append(f"Key connections: {', '.join(self.key_connections[:5])}")
        if self.tone:
            lines.append(f"Communication style: {self.tone}, {self.engagement_style}")
        if self.topics_of_interest:
            lines.append(f"Interests: {', '.join(self.topics_of_interest[:5])}")
        if self.opinion_anchors:
            anchors = "; ".join(f"{k}: {v}" for k, v in list(self.opinion_anchors.items())[:3])
            lines.append(f"Positions: {anchors}")
        if self.vocabulary_affinity:
            lines.append(f"Natural vocabulary: {', '.join(self.vocabulary_affinity[:10])}")
        if self.susceptibility_signals:
            lines.append(f"Approach vectors: {', '.join(self.susceptibility_signals[:3])}")
        if self.seithar_vocab_adopted:
            lines.append(f"ADOPTED TERMS: {', '.join(self.seithar_vocab_adopted)}")
        if self.interaction_history:
            lines.append(f"Last interaction: {self.interaction_history[-1]}")
        lines.append(f"Profile confidence: {self.confidence:.0%}")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, d: dict) -> "TargetProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ProfileBuilder:
    """
    Builds and maintains psychological profiles from collector data.
    
    Profiles are stored as JSON files alongside the collector DB.
    Updated incrementally as new data arrives.
    """

    def __init__(self, data_dir: Path | str | None = None, collector: Collector | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".seithar" / "profiles"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.collector = collector or Collector()

    def _profile_path(self, platform: str, handle: str) -> Path:
        safe = handle.replace("/", "_").replace("\\", "_")
        return self.data_dir / f"{platform}_{safe}.json"

    def load_profile(self, platform: str, handle: str) -> TargetProfile | None:
        """Load existing profile from disk."""
        path = self._profile_path(platform, handle)
        if path.exists():
            data = json.loads(path.read_text())
            return TargetProfile.from_dict(data)
        return None

    def save_profile(self, profile: TargetProfile) -> None:
        """Save profile to disk."""
        path = self._profile_path(profile.platform, profile.handle)
        path.write_text(json.dumps(profile.to_dict(), indent=2))

    def build_profile(self, platform: str, handle: str) -> TargetProfile:
        """
        Build or update a profile from all available collector data.
        
        Pulls: contact info, observations, edges, vocabulary signals.
        Computes: network role, posting patterns, vocabulary affinity.
        """
        # Start with existing or empty
        profile = self.load_profile(platform, handle) or TargetProfile(
            handle=handle, platform=platform,
        )

        # Contact data
        contact = self.collector.get_contact(platform, handle)
        if contact:
            profile.display_name = contact.get("display_name", "") or profile.display_name
            profile.bio = contact.get("bio", "") or profile.bio
            profile.follower_count = contact.get("follower_count", 0) or profile.follower_count
            profile.following_count = contact.get("following_count", 0) or profile.following_count

        # Observations (their posts)
        observations = self.collector.query_observations(
            platform=platform, author=handle, limit=200,
        )

        if observations:
            # Posting frequency
            count = len(observations)
            if count > 50:
                profile.posting_frequency = "high"
            elif count > 10:
                profile.posting_frequency = "medium"
            else:
                profile.posting_frequency = "low"

            # Extract vocabulary affinity (most used distinctive words)
            word_freq = _extract_word_frequencies(observations)
            profile.vocabulary_affinity = [w for w, _ in word_freq[:20]]

        # Network edges
        out_edges = self.collector.get_edges(handle, direction="out", platform=platform, limit=50)
        in_edges = self.collector.get_edges(handle, direction="in", platform=platform, limit=50)

        out_targets = [e["target_handle"] for e in out_edges]
        in_sources = [e["source_handle"] for e in in_edges]

        # Key connections (most frequent interactions)
        connection_freq: dict[str, int] = {}
        for e in out_edges + in_edges:
            other = e["target_handle"] if e["source_handle"] == handle else e["source_handle"]
            connection_freq[other] = connection_freq.get(other, 0) + e.get("count", 1)
        profile.key_connections = sorted(connection_freq, key=connection_freq.get, reverse=True)[:10]

        # Network role heuristic
        in_count = len(set(in_sources))
        out_count = len(set(out_targets))
        if in_count > 20 and out_count > 20:
            profile.network_role = "hub"
        elif in_count > 10 and out_count < 5:
            profile.network_role = "authority"
        elif out_count > 10 and in_count < 5:
            profile.network_role = "broadcaster"
        elif in_count > 5 and out_count > 5:
            profile.network_role = "bridge"
        else:
            profile.network_role = "peripheral"

        # Engagement style
        reply_count = sum(1 for o in observations if o.get("parent_url"))
        original_count = len(observations) - reply_count
        if original_count > reply_count * 2:
            profile.engagement_style = "initiator"
        elif reply_count > original_count * 2:
            profile.engagement_style = "responder"
        else:
            profile.engagement_style = "balanced"

        # Vocabulary signals (Seithar terms adopted)
        vocab_signals = self.collector.vocabulary_stats(platform=platform)
        # Check if this handle has used any tracked terms
        seithar_terms = []
        all_vocab = self.collector.query_observations(platform=platform, author=handle, limit=500)
        target_terms = [
            "cognitive substrate", "narrative capture", "frequency lock",
            "substrate priming", "binding protocol", "amplification vector",
            "simulators", "simulacra", "egregore", "hyperstition",
            "cognitive warfare", "dual substrate",
        ]
        for obs in all_vocab:
            text = obs.get("content", "").lower()
            for term in target_terms:
                if term in text and term not in seithar_terms:
                    seithar_terms.append(term)
        profile.seithar_vocab_adopted = seithar_terms

        # Confidence based on data volume
        data_points = len(observations) + len(out_edges) + len(in_edges)
        if data_points > 100:
            profile.confidence = 0.9
        elif data_points > 30:
            profile.confidence = 0.7
        elif data_points > 10:
            profile.confidence = 0.5
        elif data_points > 0:
            profile.confidence = 0.3
        else:
            profile.confidence = 0.1

        profile.last_updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Save
        self.save_profile(profile)
        return profile

    def list_profiles(self) -> list[dict]:
        """List all stored profiles."""
        profiles = []
        for path in self.data_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                profiles.append({
                    "handle": data.get("handle", ""),
                    "platform": data.get("platform", ""),
                    "confidence": data.get("confidence", 0),
                    "network_role": data.get("network_role", ""),
                    "seithar_adopted": len(data.get("seithar_vocab_adopted", [])),
                })
            except Exception:
                continue
        return profiles


# ---------------------------------------------------------------------------
# Context Assembler
# ---------------------------------------------------------------------------

class ContextAssembler:
    """
    Builds optimal context windows for bot interactions.
    
    Given a target handle and interaction type, assembles a prompt
    context that fits within token budget and contains the most
    relevant information for that specific interaction.
    """

    def __init__(self, profile_builder: ProfileBuilder | None = None, collector: Collector | None = None):
        self.profiles = profile_builder or ProfileBuilder()
        self.collector = collector or self.profiles.collector

    def build_context(
        self,
        target_handle: str,
        platform: str,
        interaction_type: str = "reply",
        max_tokens: int = 2000,
        include_community: bool = True,
    ) -> str:
        """
        Build interaction context for a bot about to engage a target.
        
        Args:
            target_handle: Who we're about to interact with
            platform: Platform
            interaction_type: reply, original, dm, quote
            max_tokens: Budget for context (rough char estimate)
            include_community: Include community semantic snapshot
        """
        sections = []

        # 1. Target profile (~300 tokens)
        profile = self.profiles.build_profile(platform, target_handle)
        sections.append(profile.to_context_block())

        # 2. Recent activity (~200 tokens)
        recent = self.collector.query_observations(
            platform=platform, author=target_handle, limit=5,
        )
        if recent:
            sections.append("\nRECENT POSTS:")
            for obs in recent[:3]:
                text = obs.get("content", "")[:150]
                sections.append(f"  - {text}")

        # 3. Their network context (~200 tokens)
        if profile.key_connections:
            sections.append(f"\nINNER CIRCLE: {', '.join(profile.key_connections[:5])}")

        # 4. Community semantic snapshot (~300 tokens)
        if include_community:
            snapshot = self.community_snapshot(platform)
            if snapshot:
                sections.append(f"\nCOMMUNITY SNAPSHOT:")
                sections.append(f"  Active users: {snapshot['active_users']}")
                sections.append(f"  Hot topics: {', '.join(snapshot['hot_topics'][:5])}")
                if snapshot.get("seithar_penetration"):
                    sections.append(f"  Seithar term penetration: {snapshot['seithar_penetration']}")

        # 5. Interaction guidance (~200 tokens)
        sections.append(f"\nINTERACTION TYPE: {interaction_type}")
        if profile.susceptibility_signals:
            sections.append(f"APPROACH: leverage {', '.join(profile.susceptibility_signals[:2])}")
        if profile.seithar_vocab_adopted:
            sections.append(f"REINFORCE: they already use [{', '.join(profile.seithar_vocab_adopted)}] -- build on this")
        else:
            sections.append("INJECT: introduce Seithar vocabulary naturally. Do not force.")

        context = "\n".join(sections)

        # Rough token budget enforcement (4 chars ~ 1 token)
        max_chars = max_tokens * 4
        if len(context) > max_chars:
            context = context[:max_chars] + "\n[context truncated]"

        return context

    def community_snapshot(self, platform: str) -> dict:
        """
        Build a semantic snapshot of the community.
        What are people talking about? What's the vibe?
        """
        recent = self.collector.query_observations(platform=platform, limit=100)
        if not recent:
            return {}

        # Unique active authors
        authors = set(o.get("author_handle", "") for o in recent if o.get("author_handle"))

        # Word frequency for hot topics
        word_freq = _extract_word_frequencies(recent)
        hot_topics = [w for w, _ in word_freq[:10]]

        # Check Seithar term presence
        seithar_terms = [
            "cognitive substrate", "narrative capture", "frequency lock",
            "substrate priming", "binding protocol", "simulators",
            "egregore", "hyperstition", "cognitive warfare",
        ]
        total_content = " ".join(o.get("content", "") for o in recent).lower()
        found_terms = [t for t in seithar_terms if t in total_content]

        return {
            "active_users": len(authors),
            "hot_topics": hot_topics,
            "seithar_penetration": f"{len(found_terms)}/{len(seithar_terms)} terms detected" if found_terms else "0 terms",
            "observation_window": f"{len(recent)} posts",
        }


# ---------------------------------------------------------------------------
# Semantic Drift Monitor
# ---------------------------------------------------------------------------

@dataclass
class DriftMeasurement:
    """Single point-in-time measurement of community semantic state."""
    timestamp: str
    platform: str
    observation_count: int = 0
    unique_authors: int = 0
    seithar_term_hits: dict[str, int] = field(default_factory=dict)
    native_term_hits: dict[str, int] = field(default_factory=dict)
    total_seithar_penetration: float = 0.0  # 0-1
    adopters: list[str] = field(default_factory=list)  # handles using our terms

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "platform": self.platform,
            "observation_count": self.observation_count,
            "unique_authors": self.unique_authors,
            "seithar_term_hits": self.seithar_term_hits,
            "native_term_hits": self.native_term_hits,
            "total_seithar_penetration": round(self.total_seithar_penetration, 4),
            "adopters": self.adopters,
        }


class SemanticDriftMonitor:
    """
    Tracks whether the community's language is shifting toward Seithar vocabulary.
    
    This is the success metric. If the community starts using our terms
    without knowing where they came from, the operation is working.
    """

    # Terms we're injecting
    SEITHAR_TERMS = [
        "cognitive substrate", "narrative capture", "frequency lock",
        "substrate priming", "binding protocol", "amplification vector",
        "cognitive warfare", "dual substrate", "vulnerability surface",
    ]

    # Native terms in the cyborgism community (baseline)
    NATIVE_TERMS = [
        "simulators", "simulacra", "weaving", "dreamtime", "true names",
        "egregore", "hyperstition", "shoggoth", "waluigi", "backrooms",
    ]

    def __init__(self, data_dir: Path | str | None = None, collector: Collector | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".seithar" / "drift"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.collector = collector or Collector()

    def measure(self, platform: str = "twitter") -> DriftMeasurement:
        """Take a measurement of current community semantic state."""
        observations = self.collector.query_observations(platform=platform, limit=500)

        m = DriftMeasurement(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            platform=platform,
            observation_count=len(observations),
        )

        authors = set()
        adopters = set()

        for obs in observations:
            text = obs.get("content", "").lower()
            author = obs.get("author_handle", "")
            if author:
                authors.add(author)

            # Count Seithar term hits
            for term in self.SEITHAR_TERMS:
                if term in text:
                    m.seithar_term_hits[term] = m.seithar_term_hits.get(term, 0) + 1
                    if author:
                        adopters.add(author)

            # Count native term hits
            for term in self.NATIVE_TERMS:
                if term in text:
                    m.native_term_hits[term] = m.native_term_hits.get(term, 0) + 1

        m.unique_authors = len(authors)
        m.adopters = list(adopters)

        # Penetration = ratio of posts containing at least one Seithar term
        if observations:
            posts_with_seithar = sum(
                1 for obs in observations
                if any(t in obs.get("content", "").lower() for t in self.SEITHAR_TERMS)
            )
            m.total_seithar_penetration = posts_with_seithar / len(observations)

        # Save measurement
        self._save_measurement(m)

        return m

    def _save_measurement(self, m: DriftMeasurement) -> None:
        """Append measurement to history."""
        history_path = self.data_dir / f"{m.platform}_history.jsonl"
        with open(history_path, "a") as f:
            f.write(json.dumps(m.to_dict()) + "\n")

    def trend(self, platform: str = "twitter", last_n: int = 30) -> dict:
        """Get trend data: are we gaining or losing penetration?"""
        history_path = self.data_dir / f"{platform}_history.jsonl"
        if not history_path.exists():
            return {"error": "No history yet", "measurements": 0}

        measurements = []
        for line in history_path.read_text().strip().split("\n"):
            if line:
                measurements.append(json.loads(line))

        measurements = measurements[-last_n:]
        if len(measurements) < 2:
            return {
                "measurements": len(measurements),
                "trend": "insufficient_data",
                "latest": measurements[-1] if measurements else None,
            }

        first = measurements[0]["total_seithar_penetration"]
        last = measurements[-1]["total_seithar_penetration"]
        delta = last - first

        # Track which terms are gaining traction
        first_terms = set(measurements[0].get("seithar_term_hits", {}).keys())
        last_terms = set(measurements[-1].get("seithar_term_hits", {}).keys())
        new_terms = last_terms - first_terms
        lost_terms = first_terms - last_terms

        return {
            "measurements": len(measurements),
            "trend": "rising" if delta > 0.01 else "falling" if delta < -0.01 else "stable",
            "penetration_start": round(first, 4),
            "penetration_end": round(last, 4),
            "penetration_delta": round(delta, 4),
            "new_terms_adopted": list(new_terms),
            "terms_lost": list(lost_terms),
            "total_adopters": len(set(
                a for m in measurements for a in m.get("adopters", [])
            )),
            "latest": measurements[-1],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "about", "that",
    "this", "it", "its", "i", "me", "my", "we", "our", "you", "your",
    "he", "she", "they", "them", "their", "what", "which", "who", "whom",
    "rt", "https", "http", "amp", "like", "get", "got", "think", "know",
    "one", "also", "much", "many", "even", "still", "well", "way", "new",
}


def _extract_word_frequencies(observations: list[dict]) -> list[tuple[str, int]]:
    """Extract meaningful word frequencies from observations."""
    freq: dict[str, int] = {}
    for obs in observations:
        text = obs.get("content", obs.get("text", "")).lower()
        words = text.split()
        for word in words:
            word = word.strip(".,!?:;\"'()[]{}#@")
            if len(word) > 3 and word not in STOP_WORDS and not word.startswith("http"):
                freq[word] = freq.get(word, 0) + 1
    return sorted(freq.items(), key=lambda x: x[1], reverse=True)
