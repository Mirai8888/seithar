"""
Community Intelligence Engine — model individual psychologies and hierarchical dynamics.

Not word counts. Not topic labels. INTELLIGENCE.

For each member: psychological profile, communication style, values, triggers,
social position, who they defer to, who defers to them.

For the community: power structure, cultural norms, what gets rewarded,
what gets punished, entry requirements, status signals.

Output: everything a persona needs to pass as a community member and
climb the hierarchy autonomously.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemberProfile:
    """Psychological and social profile of a community member."""
    handle: str
    display_name: str = ""
    message_count: int = 0

    # Communication style
    avg_message_length: float = 0.0
    vocabulary_richness: float = 0.0       # unique words / total words
    formality_score: float = 0.0           # 0=very casual, 1=formal
    emoji_rate: float = 0.0                # emoji per message
    question_rate: float = 0.0             # questions per message
    exclamation_rate: float = 0.0

    # Behavioral traits (per Orlando et al. 2026)
    posting_propensity: float = 0.0        # how often they initiate
    reply_propensity: float = 0.0          # how often they respond to others
    reaction_propensity: float = 0.0       # implied from "lol", "based", short affirmations
    lurk_ratio: float = 0.0               # estimated lurk vs active time

    # Social position
    reply_received_count: int = 0          # how many replies they get
    reply_given_count: int = 0             # how many replies they give
    mention_received_count: int = 0
    mention_given_count: int = 0
    influence_score: float = 0.0           # replies received / messages sent
    deference_targets: list[str] = field(default_factory=list)  # who they reply to most
    audience: list[str] = field(default_factory=list)           # who replies to them most

    # Psychological signals
    topics_of_interest: list[str] = field(default_factory=list)
    emotional_valence: float = 0.0         # -1 negative, +1 positive
    assertiveness: float = 0.0             # 0=passive, 1=dominant
    humor_rate: float = 0.0               # jokes/irony per message
    vulnerability_signals: list[str] = field(default_factory=list)  # insecurity, seeking validation, etc.
    values: list[str] = field(default_factory=list)  # what they care about

    # Engagement patterns
    active_channels: list[str] = field(default_factory=list)
    peak_hours: list[int] = field(default_factory=list)  # UTC hours most active
    sample_messages: list[str] = field(default_factory=list)  # representative messages

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass 
class CommunityModel:
    """Structural model of a community's dynamics."""
    guild_name: str = ""
    member_count: int = 0
    
    # Hierarchy
    hierarchy: list[dict] = field(default_factory=list)  # ranked members with scores
    power_centers: list[str] = field(default_factory=list)  # who sets the tone
    gatekeepers: list[str] = field(default_factory=list)  # who validates newcomers
    bridge_nodes: list[str] = field(default_factory=list)  # active across multiple channels
    
    # Cultural norms
    greeting_style: str = ""               # how people say hi
    humor_style: str = ""                  # ironic, wholesome, edgy, etc.
    taboo_topics: list[str] = field(default_factory=list)
    status_signals: list[str] = field(default_factory=list)  # what earns respect
    entry_behaviors: list[str] = field(default_factory=list)  # what newcomers do
    
    # Engagement patterns
    high_engagement_topics: list[str] = field(default_factory=list)
    low_engagement_topics: list[str] = field(default_factory=list)
    conversation_starters: list[str] = field(default_factory=list)  # message types that get replies
    
    # Vocabulary
    community_slang: dict[str, int] = field(default_factory=dict)  # term -> frequency
    shared_references: list[str] = field(default_factory=list)  # cultural references

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class PersonaBlueprint:
    """Everything needed to generate a persona that fits this community."""
    target_community: str = ""
    
    # Voice
    vocabulary: list[str] = field(default_factory=list)
    tone: str = ""
    sentence_patterns: list[str] = field(default_factory=list)
    avg_message_length: float = 0.0
    emoji_usage: list[str] = field(default_factory=list)
    
    # Behavioral profile
    posting_frequency: str = ""  # e.g. "3-5 messages per hour"
    reply_style: str = ""        # e.g. "short affirmations, occasional questions"
    channels_to_target: list[str] = field(default_factory=list)
    
    # Social strategy
    initial_targets: list[str] = field(default_factory=list)  # who to engage first
    status_path: list[str] = field(default_factory=list)  # steps to climb hierarchy
    topics_to_engage: list[str] = field(default_factory=list)
    topics_to_avoid: list[str] = field(default_factory=list)
    
    # Entry strategy
    first_messages: list[str] = field(default_factory=list)  # example first messages
    
    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


# --- Linguistic analysis helpers ---

EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F9FF\U00002702-\U000027B0\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF\U00002600-\U000026FF\U0000FE00-\U0000FE0F'
    r'\U0001F900-\U0001F9FF]+'
)

HUMOR_SIGNALS = {
    "lol", "lmao", "lmfao", "rofl", "💀", "😂", "🤣", "bruh",
    "dead", "crying", "i cant", "im crying", "no way", "bro",
}

AFFIRMATION_SIGNALS = {
    "based", "fr", "real", "facts", "true", "this", "exactly",
    "W", "huge", "goated", "king", "queen", "valid", "fire",
}

VULNERABILITY_SIGNALS = {
    "idk": "uncertainty",
    "i think": "hedging",
    "sorry": "apologetic",
    "am i": "seeking_validation",
    "is it just me": "seeking_validation",
    "ngl": "disclosure",
    "honestly": "disclosure",
    "i feel like": "emotional_reasoning",
    "i wish": "longing",
    "i cant": "helplessness",
}

ASSERTIVENESS_SIGNALS = {
    "you should": 0.8,
    "you need to": 0.9,
    "listen": 0.7,
    "trust me": 0.8,
    "obviously": 0.6,
    "clearly": 0.6,
    "the move is": 0.7,
    "just do": 0.8,
    "stop": 0.7,
}

STOP_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "been", "was", "are", "has", "had", "is",
    "did", "got", "dont", "yeah", "thats", "really", "still", "thing",
    "much", "more", "very", "here", "where", "too", "been", "going",
}


class CommunityIntelEngine:
    """
    Build intelligence products from raw community observations.
    
    Input: collector DB observations from discord_lurk (or any platform).
    Output: MemberProfiles, CommunityModel, PersonaBlueprint.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path) if db_path else str(
            Path.home() / ".seithar" / "collector.db"
        )

    def _get_observations(
        self,
        source: str = "discord_lurk",
        channel_filter: list[str] | None = None,
        limit: int = 10000,
    ) -> list[dict]:
        """Pull observations from collector DB."""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute(
            "SELECT content, author_handle, metadata, observed_at "
            "FROM observations WHERE source = ? "
            "ORDER BY observed_at DESC LIMIT ?",
            (source, limit),
        )
        rows = []
        for r in c.fetchall():
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            channel = meta.get("channel", "")
            if channel_filter and channel not in channel_filter:
                continue
            rows.append({
                "content": r["content"] or "",
                "author": r["author_handle"] or "",
                "display_name": meta.get("display_name", ""),
                "channel": channel,
                "observed_at": r["observed_at"] or "",
                "reply_to_author": meta.get("reply_to_author", ""),
                "reply_to_content": meta.get("reply_to_content", ""),
                "is_reply": meta.get("is_reply", False),
            })
        db.close()
        return rows

    def _deduplicate(self, observations: list[dict]) -> list[dict]:
        """Remove exact duplicate messages (same author + content)."""
        seen = set()
        deduped = []
        for obs in observations:
            key = (obs["author"], obs["content"][:100])
            if key not in seen:
                seen.add(key)
                deduped.append(obs)
        return deduped

    def build_member_profiles(
        self,
        observations: list[dict],
        min_messages: int = 5,
    ) -> dict[str, MemberProfile]:
        """Build psychological profiles for each community member."""
        # Group by author
        by_author: dict[str, list[dict]] = defaultdict(list)
        for obs in observations:
            if obs["author"]:
                by_author[obs["author"]].append(obs)

        # Reply graph: who replies to whom (mentions + actual replies)
        mention_graph: dict[str, Counter] = defaultdict(Counter)
        reply_graph: dict[str, Counter] = defaultdict(Counter)
        reply_received: Counter = Counter()
        for obs in observations:
            # @mentions in content
            mentions = re.findall(r'<@!?(\d+)>', obs["content"])
            at_mentions = re.findall(r'@(\w+)', obs["content"])
            for m in mentions + at_mentions:
                mention_graph[obs["author"]][m] += 1
            # Actual Discord reply threading
            reply_to = obs.get("reply_to_author", "")
            if reply_to and reply_to != obs["author"]:
                reply_graph[obs["author"]][reply_to] += 1
                reply_received[reply_to] += 1

        profiles = {}
        for handle, msgs in by_author.items():
            if len(msgs) < min_messages:
                continue

            profile = MemberProfile(handle=handle)
            profile.display_name = msgs[0].get("display_name", "")
            profile.message_count = len(msgs)

            contents = [m["content"] for m in msgs if m["content"]]
            if not contents:
                continue

            # Communication style
            lengths = [len(c.split()) for c in contents]
            profile.avg_message_length = sum(lengths) / len(lengths)

            all_words = []
            for c in contents:
                all_words.extend(w.lower() for w in c.split() if len(w) > 1)
            if all_words:
                profile.vocabulary_richness = len(set(all_words)) / len(all_words)

            # Emoji rate
            emoji_counts = [len(EMOJI_PATTERN.findall(c)) for c in contents]
            profile.emoji_rate = sum(emoji_counts) / len(contents)

            # Question rate
            profile.question_rate = sum(1 for c in contents if "?" in c) / len(contents)
            profile.exclamation_rate = sum(1 for c in contents if "!" in c) / len(contents)

            # Formality (heuristic: capitalization, punctuation, slang)
            formal_signals = sum(
                1 for c in contents
                if c[0:1].isupper() and c.rstrip()[-1:] in ".!?"
            )
            slang_count = sum(
                1 for c in contents
                for w in c.lower().split()
                if w in {"lol", "lmao", "bruh", "ngl", "fr", "tbh", "imo", "smh", "istg"}
            )
            profile.formality_score = max(0, min(1,
                (formal_signals / len(contents)) - (slang_count / max(len(all_words), 1)) * 2
            ))

            # Behavioral traits
            channels_used = Counter(m["channel"] for m in msgs)
            profile.active_channels = [ch for ch, _ in channels_used.most_common(5)]

            # Humor rate
            humor_count = sum(
                1 for c in contents
                if any(s in c.lower() for s in HUMOR_SIGNALS)
            )
            profile.humor_rate = humor_count / len(contents)

            # Assertiveness
            assert_scores = []
            for c in contents:
                c_lower = c.lower()
                for signal, score in ASSERTIVENESS_SIGNALS.items():
                    if signal in c_lower:
                        assert_scores.append(score)
            profile.assertiveness = (
                sum(assert_scores) / len(assert_scores) if assert_scores else 0.3
            )

            # Vulnerability signals
            vulns = []
            for c in contents:
                c_lower = c.lower()
                for signal, label in VULNERABILITY_SIGNALS.items():
                    if signal in c_lower:
                        vulns.append(label)
            profile.vulnerability_signals = list(set(vulns))

            # Emotional valence (simple positive/negative word ratio)
            pos_words = {"love", "great", "amazing", "happy", "beautiful", "nice",
                        "good", "awesome", "fire", "perfect", "goated", "based", "W"}
            neg_words = {"hate", "bad", "terrible", "ugly", "shit", "fuck", "worst",
                        "annoying", "boring", "trash", "L", "cringe", "mid"}
            pos_count = sum(1 for w in all_words if w in pos_words)
            neg_count = sum(1 for w in all_words if w in neg_words)
            total_sentiment = pos_count + neg_count
            if total_sentiment > 0:
                profile.emotional_valence = (pos_count - neg_count) / total_sentiment

            # Social graph: combine mentions + reply threading
            combined_graph: Counter = Counter()
            if handle in mention_graph:
                combined_graph.update(mention_graph[handle])
            if handle in reply_graph:
                combined_graph.update(reply_graph[handle])

            if combined_graph:
                targets = combined_graph.most_common(5)
                profile.deference_targets = [t for t, _ in targets]
                profile.mention_given_count = sum(combined_graph.values())
            profile.reply_given_count = sum(reply_graph.get(handle, {}).values())

            # Count attention received (mentions + replies)
            mention_received = sum(
                cnt for other, graph in mention_graph.items()
                if other != handle
                for target, cnt in graph.items()
                if target == handle
            )
            replies_received = reply_received.get(handle, 0)
            total_received = mention_received + replies_received
            profile.mention_received_count = mention_received
            profile.reply_received_count = replies_received

            # Influence = total attention received / messages sent
            if profile.message_count > 0:
                profile.influence_score = total_received / profile.message_count

            # Who replies to this person most
            audience = Counter()
            for other, graph in reply_graph.items():
                if handle in graph:
                    audience[other] += graph[handle]
            profile.audience = [a for a, _ in audience.most_common(5)]

            # Topics of interest (top non-stop words)
            topic_words = Counter(
                w for w in all_words
                if w not in STOP_WORDS and len(w) > 3
                and not w.startswith("http") and not w.startswith("<@")
            )
            profile.topics_of_interest = [w for w, _ in topic_words.most_common(15)]

            # Sample messages (diverse, >10 words)
            long_msgs = [c for c in contents if len(c.split()) > 10]
            profile.sample_messages = long_msgs[:5] if long_msgs else contents[:3]

            profiles[handle] = profile

        return profiles

    def build_community_model(
        self,
        profiles: dict[str, MemberProfile],
        observations: list[dict],
    ) -> CommunityModel:
        """Build structural model of community dynamics."""
        model = CommunityModel()
        model.member_count = len(profiles)

        # Hierarchy by influence
        ranked = sorted(
            profiles.values(),
            key=lambda p: (p.influence_score * 0.4 + 
                          (p.message_count / max(1, max(pp.message_count for pp in profiles.values()))) * 0.3 +
                          p.assertiveness * 0.3),
            reverse=True,
        )
        model.hierarchy = [
            {"handle": p.handle, "messages": p.message_count,
             "influence": round(p.influence_score, 3),
             "assertiveness": round(p.assertiveness, 2)}
            for p in ranked[:20]
        ]

        # Power centers: high influence + high assertiveness
        model.power_centers = [
            p.handle for p in ranked[:5]
            if p.influence_score > 0 or p.assertiveness > 0.5
        ]

        # Bridge nodes: active in 3+ channels
        model.bridge_nodes = [
            p.handle for p in profiles.values()
            if len(p.active_channels) >= 3
        ]

        # Gatekeepers: people who reply to many different users
        model.gatekeepers = [
            p.handle for p in profiles.values()
            if p.mention_given_count > 5 and p.influence_score > 0.1
        ]

        # Community slang
        all_words = Counter()
        for obs in observations:
            for w in obs["content"].lower().split():
                if (len(w) > 2 and w not in STOP_WORDS
                    and not w.startswith("http") and not w.startswith("<")):
                    all_words[w] += 1
        # Filter to community-specific terms (not generic English)
        model.community_slang = {
            w: c for w, c in all_words.most_common(100)
            if c >= 3
        }

        # Greeting style
        greetings = Counter()
        for obs in observations:
            c = obs["content"].strip().lower()
            if len(c.split()) <= 3 and any(g in c for g in ["gm", "gn", "hi", "hey", "hello", "yo", "sup"]):
                greetings[c] += 1
        if greetings:
            model.greeting_style = greetings.most_common(1)[0][0]

        # High engagement topics (messages that got replies — approximated by mentions)
        # This is limited without thread/reply data, but we work with what we have

        # Status signals from vocabulary analysis
        status_words = []
        for p in ranked[:10]:
            if p.topics_of_interest:
                status_words.extend(p.topics_of_interest[:3])
        model.status_signals = list(set(status_words))[:10]

        return model

    def generate_persona_blueprint(
        self,
        profiles: dict[str, MemberProfile],
        community: CommunityModel,
        target_rank: str = "mid",  # "newcomer", "mid", "high"
    ) -> PersonaBlueprint:
        """
        Generate a persona blueprint from community intelligence.
        
        The persona should be able to enter the community and climb
        to the target rank by understanding and mirroring its dynamics.
        """
        bp = PersonaBlueprint()
        bp.target_community = community.guild_name

        # Voice: match the median communication style
        active_profiles = [p for p in profiles.values() if p.message_count >= 10]
        if not active_profiles:
            active_profiles = list(profiles.values())

        bp.avg_message_length = sum(p.avg_message_length for p in active_profiles) / max(len(active_profiles), 1)

        # Vocabulary: community slang + top topic words
        bp.vocabulary = list(community.community_slang.keys())[:30]

        # Tone: match dominant emotional valence and formality
        avg_formality = sum(p.formality_score for p in active_profiles) / max(len(active_profiles), 1)
        avg_humor = sum(p.humor_rate for p in active_profiles) / max(len(active_profiles), 1)
        if avg_formality < 0.2 and avg_humor > 0.3:
            bp.tone = "casual, humorous, uses community slang"
        elif avg_formality < 0.3:
            bp.tone = "casual, direct"
        else:
            bp.tone = "semi-formal, measured"

        # Channels: focus on high-activity social channels, not trading
        channel_counts = Counter()
        for p in active_profiles:
            for ch in p.active_channels:
                channel_counts[ch] += 1
        bp.channels_to_target = [ch for ch, _ in channel_counts.most_common(5)]

        # Social strategy
        if target_rank == "newcomer":
            bp.initial_targets = community.bridge_nodes[:3]
            bp.status_path = [
                "Lurk in general for 24h, react to messages",
                "Start with short affirmations to active members",
                "Share relevant content (art, music, memes) matching community taste",
                "Ask genuine questions about community lore/history",
            ]
        elif target_rank == "mid":
            bp.initial_targets = (community.gatekeepers[:2] + community.bridge_nodes[:2])
            bp.status_path = [
                "Enter with casual presence, match greeting style",
                "Engage bridge nodes with relevant topic contributions",
                "Build reply chains with mid-tier members",
                "Share original content that matches community aesthetic",
                "Develop recognizable voice/personality quirk",
                "Cross-pollinate between channels to build visibility",
            ]
        elif target_rank == "high":
            bp.initial_targets = community.power_centers[:3]
            bp.status_path = [
                "All of mid-tier strategy first",
                "Start initiating conversations, not just responding",
                "Become the 'go-to' for a specific topic/niche",
                "Help newcomers (builds social capital)",
                "Create community moments (events, challenges, shared jokes)",
            ]

        # Topics
        bp.topics_to_engage = community.status_signals[:5]
        bp.topics_to_avoid = community.taboo_topics[:5]

        # Reply style from community norms
        short_msg_ratio = sum(
            1 for p in active_profiles if p.avg_message_length < 5
        ) / max(len(active_profiles), 1)
        if short_msg_ratio > 0.5:
            bp.reply_style = "short, punchy, lots of one-liners and reactions"
        else:
            bp.reply_style = "medium length, conversational, asks follow-ups"

        return bp

    def full_analysis(
        self,
        source: str = "discord_lurk",
        channel_filter: list[str] | None = None,
        limit: int = 10000,
        min_messages: int = 5,
    ) -> dict:
        """
        Run full community intelligence pipeline.
        
        Returns dict with profiles, community model, and persona blueprint.
        """
        logger.info("Fetching observations (source=%s, limit=%d)...", source, limit)
        observations = self._get_observations(source, channel_filter, limit)
        observations = self._deduplicate(observations)
        logger.info("Deduped to %d observations", len(observations))

        logger.info("Building member profiles...")
        profiles = self.build_member_profiles(observations, min_messages)
        logger.info("Profiled %d members (>=%d messages)", len(profiles), min_messages)

        logger.info("Building community model...")
        community = self.build_community_model(profiles, observations)

        logger.info("Generating persona blueprint...")
        blueprint = generate_persona_blueprint_stub = self.generate_persona_blueprint(profiles, community)

        return {
            "observations_count": len(observations),
            "profiles": {h: p.to_dict() for h, p in profiles.items()},
            "community": community.to_dict(),
            "blueprint": blueprint.to_dict(),
        }
