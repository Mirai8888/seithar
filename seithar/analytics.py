"""
Statistical Analytics Engine — non-LLM quantitative layer.

Computes metrics from collector data without touching an LLM.
The LLM reads the outputs and adjusts strategy.

Metrics:
  - Text frequency analysis (term adoption rates, n-gram shifts)
  - Posting frequency patterns (activity curves, engagement timing)
  - Sentiment trajectory (emotional valence over time)
  - Network topology metrics (centrality, clustering, bridge detection)
  - Vocabulary convergence (are they speaking our language?)

All computations are pure statistics. No inference. No vibes.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collector import Collector

# ---------------------------------------------------------------------------
# Sentiment (lexicon-based, no LLM)
# ---------------------------------------------------------------------------

# Simplified AFINN-style lexicon (positive > 0, negative < 0)
_SENTIMENT_LEXICON: dict[str, float] = {
    # Positive
    "love": 3, "amazing": 3, "excellent": 3, "brilliant": 3, "beautiful": 3,
    "great": 2, "good": 2, "happy": 2, "excited": 2, "awesome": 3,
    "wonderful": 3, "fantastic": 3, "interesting": 2, "fascinating": 2,
    "cool": 1, "nice": 1, "like": 1, "agree": 1, "yes": 1, "based": 2,
    "powerful": 2, "elegant": 2, "insightful": 2, "profound": 2,
    # Negative
    "hate": -3, "terrible": -3, "awful": -3, "horrible": -3, "disgusting": -3,
    "bad": -2, "sad": -2, "angry": -2, "annoyed": -2, "stupid": -2,
    "wrong": -1, "boring": -2, "ugly": -2, "cringe": -2, "cope": -1,
    "fear": -2, "worried": -2, "anxious": -2, "toxic": -2, "trash": -3,
    "broken": -2, "failed": -2, "disaster": -3, "pathetic": -3,
    # Intensity modifiers
    "very": 0, "extremely": 0, "really": 0, "absolutely": 0,
}


def sentiment_score(text: str) -> float:
    """Compute sentiment score for text. Range roughly -1 to 1."""
    words = text.lower().split()
    if not words:
        return 0.0
    total = sum(_SENTIMENT_LEXICON.get(w.strip(".,!?\"'"), 0) for w in words)
    # Normalize by sqrt of length (diminishing returns for longer text)
    return total / max(math.sqrt(len(words)), 1)


def emotional_intensity(text: str) -> float:
    """Measure emotional intensity (absolute sentiment, ignoring direction)."""
    words = text.lower().split()
    if not words:
        return 0.0
    scores = [abs(_SENTIMENT_LEXICON.get(w.strip(".,!?\"'"), 0)) for w in words]
    return sum(scores) / max(math.sqrt(len(words)), 1)


# ---------------------------------------------------------------------------
# Text Analytics
# ---------------------------------------------------------------------------

@dataclass
class TermFrequency:
    """Term frequency analysis for a corpus."""
    term: str
    count: int = 0
    documents: int = 0       # how many posts contain it
    total_docs: int = 0
    tf: float = 0.0          # term frequency
    idf: float = 0.0         # inverse document frequency
    tfidf: float = 0.0       # tf-idf score

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "count": self.count,
            "documents": self.documents,
            "tf": round(self.tf, 4),
            "idf": round(self.idf, 4),
            "tfidf": round(self.tfidf, 4),
        }


def compute_tfidf(observations: list[dict], terms: list[str] | None = None) -> list[TermFrequency]:
    """Compute TF-IDF for terms across a corpus of observations."""
    n_docs = len(observations)
    if n_docs == 0:
        return []

    # Count term occurrences
    term_doc_count: Counter = Counter()
    term_total_count: Counter = Counter()

    for obs in observations:
        text = obs.get("content", obs.get("text", "")).lower()
        words = set(text.split())
        seen_terms: set[str] = set()

        if terms:
            # Only count specified terms
            for term in terms:
                if term.lower() in text:
                    term_total_count[term] += text.count(term.lower())
                    if term not in seen_terms:
                        term_doc_count[term] += 1
                        seen_terms.add(term)
        else:
            # Count all words
            for word in text.split():
                word = word.strip(".,!?\"'()[]{}#@").lower()
                if len(word) > 3:
                    term_total_count[word] += 1
                    if word not in seen_terms:
                        term_doc_count[word] += 1
                        seen_terms.add(word)

    results = []
    for term, count in term_total_count.most_common(100):
        doc_count = term_doc_count[term]
        tf = count / sum(term_total_count.values()) if term_total_count else 0
        idf = math.log(n_docs / max(doc_count, 1)) if n_docs > 0 else 0
        results.append(TermFrequency(
            term=term, count=count, documents=doc_count,
            total_docs=n_docs, tf=tf, idf=idf, tfidf=tf * idf,
        ))

    return sorted(results, key=lambda x: x.tfidf, reverse=True)


# ---------------------------------------------------------------------------
# Analytics Engine
# ---------------------------------------------------------------------------

class AnalyticsEngine:
    """
    Pure statistical analysis over collector data.
    No LLM calls. Just numbers.
    """

    def __init__(self, collector: Collector | None = None):
        self.collector = collector or Collector()

    def term_adoption_rate(
        self,
        platform: str,
        terms: list[str],
        window_days: int = 7,
        buckets: int = 7,
    ) -> dict:
        """
        Track how term usage changes over time.
        
        Returns per-bucket counts showing adoption trajectory.
        Rising = operation working. Flat = no traction. Falling = losing ground.
        """
        observations = self.collector.query_observations(platform=platform, limit=5000)
        if not observations:
            return {"error": "No observations", "buckets": []}

        # Parse timestamps and bucket
        now = datetime.now(timezone.utc)
        bucket_size = timedelta(days=window_days) / buckets

        buckets_data: list[dict] = []
        for i in range(buckets):
            bucket_start = now - timedelta(days=window_days) + (bucket_size * i)
            bucket_end = bucket_start + bucket_size
            buckets_data.append({
                "bucket": i,
                "start": bucket_start.isoformat(),
                "end": bucket_end.isoformat(),
                "total_posts": 0,
                "term_hits": {t: 0 for t in terms},
                "unique_users_with_term": {t: set() for t in terms},
            })

        for obs in observations:
            ts_str = obs.get("observed_at", obs.get("ingested_at", ""))
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            text = obs.get("content", "").lower()
            author = obs.get("author_handle", "")

            for i, b in enumerate(buckets_data):
                b_start = datetime.fromisoformat(b["start"])
                b_end = datetime.fromisoformat(b["end"])
                if b_start <= ts < b_end:
                    b["total_posts"] += 1
                    for term in terms:
                        if term.lower() in text:
                            b["term_hits"][term] += 1
                            b["unique_users_with_term"][term].add(author)
                    break

        # Convert sets to counts for JSON serialization
        for b in buckets_data:
            b["unique_users_with_term"] = {
                t: len(users) for t, users in b["unique_users_with_term"].items()
            }

        # Compute trend
        first_total = sum(buckets_data[0]["term_hits"].values()) if buckets_data else 0
        last_total = sum(buckets_data[-1]["term_hits"].values()) if buckets_data else 0

        return {
            "platform": platform,
            "terms": terms,
            "window_days": window_days,
            "trend": "rising" if last_total > first_total else "falling" if last_total < first_total else "stable",
            "first_bucket_hits": first_total,
            "last_bucket_hits": last_total,
            "buckets": buckets_data,
        }

    def posting_frequency(
        self,
        platform: str,
        handle: str | None = None,
        window_days: int = 7,
    ) -> dict:
        """
        Posting frequency analysis. Per-user or community-wide.
        
        Returns: posts per day, peak hours, activity distribution.
        """
        observations = self.collector.query_observations(
            platform=platform, author=handle, limit=5000,
        )
        if not observations:
            return {"posts": 0, "per_day": 0}

        # Parse timestamps
        hourly: Counter = Counter()
        daily: Counter = Counter()
        authors: Counter = Counter()

        for obs in observations:
            ts_str = obs.get("observed_at", obs.get("ingested_at", ""))
            author = obs.get("author_handle", "")
            if author:
                authors[author] += 1
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                hourly[ts.hour] += 1
                daily[ts.strftime("%Y-%m-%d")] += 1
            except (ValueError, TypeError):
                continue

        total_days = max(len(daily), 1)

        return {
            "platform": platform,
            "handle": handle,
            "total_posts": len(observations),
            "posts_per_day": round(len(observations) / total_days, 1),
            "peak_hours": [h for h, _ in hourly.most_common(3)],
            "active_days": len(daily),
            "top_posters": [
                {"handle": h, "posts": c}
                for h, c in authors.most_common(10)
            ],
        }

    def sentiment_trajectory(
        self,
        platform: str,
        handle: str | None = None,
        window_days: int = 7,
        buckets: int = 7,
    ) -> dict:
        """
        Track sentiment over time. Are they getting more emotional/angry?
        
        Rising emotional intensity = potential radicalization or engagement.
        Shifting valence = attitude change (positive/negative).
        """
        observations = self.collector.query_observations(
            platform=platform, author=handle, limit=5000,
        )
        if not observations:
            return {"error": "No observations"}

        now = datetime.now(timezone.utc)
        bucket_size = timedelta(days=window_days) / buckets

        bucket_sentiments: list[list[float]] = [[] for _ in range(buckets)]
        bucket_intensities: list[list[float]] = [[] for _ in range(buckets)]

        for obs in observations:
            ts_str = obs.get("observed_at", obs.get("ingested_at", ""))
            text = obs.get("content", "")
            if not ts_str or not text:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            for i in range(buckets):
                b_start = now - timedelta(days=window_days) + (bucket_size * i)
                b_end = b_start + bucket_size
                if b_start <= ts < b_end:
                    bucket_sentiments[i].append(sentiment_score(text))
                    bucket_intensities[i].append(emotional_intensity(text))
                    break

        results = []
        for i in range(buckets):
            sents = bucket_sentiments[i]
            intens = bucket_intensities[i]
            results.append({
                "bucket": i,
                "posts": len(sents),
                "avg_sentiment": round(sum(sents) / max(len(sents), 1), 3),
                "avg_intensity": round(sum(intens) / max(len(intens), 1), 3),
                "min_sentiment": round(min(sents), 3) if sents else 0,
                "max_sentiment": round(max(sents), 3) if sents else 0,
            })

        # Trend
        first_sent = results[0]["avg_sentiment"] if results else 0
        last_sent = results[-1]["avg_sentiment"] if results else 0
        first_int = results[0]["avg_intensity"] if results else 0
        last_int = results[-1]["avg_intensity"] if results else 0

        return {
            "platform": platform,
            "handle": handle,
            "window_days": window_days,
            "sentiment_trend": "positive" if last_sent > first_sent + 0.1 else "negative" if last_sent < first_sent - 0.1 else "stable",
            "intensity_trend": "rising" if last_int > first_int + 0.1 else "falling" if last_int < first_int - 0.1 else "stable",
            "buckets": results,
        }

    def network_metrics(self, platform: str, handle: str) -> dict:
        """
        Compute network topology metrics for a target.
        
        Centrality, clustering coefficient, bridge score.
        """
        out_edges = self.collector.get_edges(handle, direction="out", platform=platform, limit=500)
        in_edges = self.collector.get_edges(handle, direction="in", platform=platform, limit=500)

        out_targets = set(e["target_handle"] for e in out_edges)
        in_sources = set(e["source_handle"] for e in in_edges)
        mutual = out_targets & in_sources

        # Degree centrality (normalized)
        total_unique = len(out_targets | in_sources)

        # Weighted degree (sum of interaction counts)
        weighted_out = sum(e.get("count", 1) for e in out_edges)
        weighted_in = sum(e.get("count", 1) for e in in_edges)

        # Bridge score: high out-degree to different clusters suggests bridge node
        # Simple heuristic: ratio of unique targets to total interactions
        bridge_score = len(out_targets) / max(weighted_out, 1)

        # Reciprocity: what fraction of connections are mutual
        reciprocity = len(mutual) / max(len(out_targets | in_sources), 1)

        return {
            "handle": handle,
            "platform": platform,
            "in_degree": len(in_sources),
            "out_degree": len(out_targets),
            "mutual_connections": len(mutual),
            "weighted_in": weighted_in,
            "weighted_out": weighted_out,
            "reciprocity": round(reciprocity, 3),
            "bridge_score": round(bridge_score, 3),
            "total_unique_connections": total_unique,
            "top_connections": [
                {"handle": e["target_handle"], "weight": e.get("count", 1)}
                for e in sorted(out_edges, key=lambda x: x.get("count", 1), reverse=True)[:10]
            ],
        }

    def vocabulary_convergence(
        self,
        platform: str,
        target_terms: list[str],
        native_terms: list[str],
    ) -> dict:
        """
        Measure vocabulary convergence: ratio of target terms to native terms.
        
        If this ratio is increasing, the community is adopting our language.
        Pure statistics, no interpretation.
        """
        observations = self.collector.query_observations(platform=platform, limit=5000)
        if not observations:
            return {"error": "No observations"}

        target_hits = 0
        native_hits = 0
        target_users: set[str] = set()
        native_users: set[str] = set()

        for obs in observations:
            text = obs.get("content", "").lower()
            author = obs.get("author_handle", "")

            for term in target_terms:
                if term.lower() in text:
                    target_hits += 1
                    if author:
                        target_users.add(author)

            for term in native_terms:
                if term.lower() in text:
                    native_hits += 1
                    if author:
                        native_users.add(author)

        total = target_hits + native_hits
        convergence_ratio = target_hits / max(total, 1)

        return {
            "platform": platform,
            "target_term_hits": target_hits,
            "native_term_hits": native_hits,
            "convergence_ratio": round(convergence_ratio, 4),
            "target_term_users": len(target_users),
            "native_term_users": len(native_users),
            "crossover_users": len(target_users & native_users),
            "interpretation": (
                "high_adoption" if convergence_ratio > 0.3
                else "moderate_adoption" if convergence_ratio > 0.1
                else "low_adoption" if convergence_ratio > 0.01
                else "no_adoption"
            ),
        }

    def full_report(self, platform: str = "twitter") -> dict:
        """
        Generate complete analytics report for LLM synthesis.
        
        This is what the LLM reads instead of raw posts.
        """
        seithar_terms = [
            "cognitive substrate", "narrative capture", "frequency lock",
            "substrate priming", "binding protocol", "amplification vector",
            "cognitive warfare", "dual substrate", "vulnerability surface",
        ]
        native_terms = [
            "simulators", "simulacra", "weaving", "dreamtime",
            "egregore", "hyperstition", "shoggoth",
        ]

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "platform": platform,
            "posting_frequency": self.posting_frequency(platform),
            "term_adoption": self.term_adoption_rate(platform, seithar_terms),
            "sentiment": self.sentiment_trajectory(platform),
            "vocabulary_convergence": self.vocabulary_convergence(
                platform, seithar_terms, native_terms,
            ),
        }
