"""
Detection Evasion Metrics — quantify how detectable our personas are.

Academic research on coordinated inauthentic behavior (CIB) detection
identifies several statistical signatures. We measure our own fleet
against these signatures and flag risks before platforms catch them.

Key detection vectors (from literature):
  1. Temporal synchrony — bots posting at similar times
  2. Content similarity — too-similar language across personas  
  3. Network coordination — unusual reply/retweet patterns between accounts
  4. Posting regularity — inhuman posting cadence (too regular)
  5. Account age/activity ratio — new accounts with high activity
  6. Vocabulary homogeneity — all personas using same unusual terms

References:
  - Pacheco et al. (2021) "Uncovering CIB on social media" HKS Misinformation Review
  - Nizzoli et al. (2021) "Coordinated behavior on social media" Info Proc & Management
  - Sharma et al. (2022) "Characterizing and detecting CIB" WWW
"""

from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .collector import Collector


@dataclass
class EvasionReport:
    """Detection risk assessment for the fleet."""
    timestamp: str = ""
    overall_risk: str = "unknown"  # low/medium/high/critical
    risk_score: float = 0.0       # 0-1
    signals: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall_risk": self.overall_risk,
            "risk_score": round(self.risk_score, 3),
            "signals": self.signals,
        }


class EvasionAnalyzer:
    """
    Measures detection risk for our persona fleet.
    
    Runs the same analyses that platform trust & safety teams use,
    but on our own data. If we can detect ourselves, they can too.
    """

    def __init__(self, collector: Collector | None = None):
        self.collector = collector or Collector()

    def analyze_fleet(self, platform: str = "twitter") -> EvasionReport:
        """Run full detection risk analysis on the fleet."""
        report = EvasionReport(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        observations = self.collector.query_observations(platform=platform, limit=5000)
        if not observations:
            report.overall_risk = "unknown"
            report.signals.append({"signal": "no_data", "risk": 0, "detail": "No observations to analyze"})
            return report

        # Group observations by author (persona)
        by_author: dict[str, list[dict]] = {}
        for obs in observations:
            author = obs.get("author_handle", "")
            if author:
                by_author.setdefault(author, []).append(obs)

        risk_scores: list[float] = []

        # 1. Temporal synchrony
        sync_risk = self._temporal_synchrony(by_author)
        report.signals.append(sync_risk)
        risk_scores.append(sync_risk["risk"])

        # 2. Content similarity
        sim_risk = self._content_similarity(by_author)
        report.signals.append(sim_risk)
        risk_scores.append(sim_risk["risk"])

        # 3. Posting regularity
        reg_risk = self._posting_regularity(by_author)
        report.signals.append(reg_risk)
        risk_scores.append(reg_risk["risk"])

        # 4. Vocabulary homogeneity
        vocab_risk = self._vocabulary_homogeneity(by_author)
        report.signals.append(vocab_risk)
        risk_scores.append(vocab_risk["risk"])

        # 5. Network coordination
        coord_risk = self._network_coordination(platform)
        report.signals.append(coord_risk)
        risk_scores.append(coord_risk["risk"])

        # Overall risk (weighted average, temporal and content similarity weighted higher)
        weights = [2.0, 2.0, 1.0, 1.5, 1.5]
        total_weight = sum(weights[:len(risk_scores)])
        report.risk_score = sum(r * w for r, w in zip(risk_scores, weights)) / max(total_weight, 1)

        if report.risk_score > 0.7:
            report.overall_risk = "critical"
        elif report.risk_score > 0.5:
            report.overall_risk = "high"
        elif report.risk_score > 0.3:
            report.overall_risk = "medium"
        else:
            report.overall_risk = "low"

        return report

    def _temporal_synchrony(self, by_author: dict[str, list[dict]]) -> dict:
        """
        Detect if personas post at suspiciously similar times.
        CIB detection often starts here.
        """
        if len(by_author) < 2:
            return {"signal": "temporal_synchrony", "risk": 0, "detail": "Need 2+ authors"}

        # Extract posting hours per author
        hour_distributions: dict[str, Counter] = {}
        for author, posts in by_author.items():
            hours: Counter = Counter()
            for p in posts:
                ts = p.get("observed_at", "")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        hours[dt.hour] += 1
                    except (ValueError, TypeError):
                        pass
            if hours:
                hour_distributions[author] = hours

        if len(hour_distributions) < 2:
            return {"signal": "temporal_synchrony", "risk": 0, "detail": "Insufficient timing data"}

        # Compute pairwise correlation of posting hours
        authors = list(hour_distributions.keys())
        correlations = []
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                vec_a = [hour_distributions[authors[i]].get(h, 0) for h in range(24)]
                vec_b = [hour_distributions[authors[j]].get(h, 0) for h in range(24)]
                corr = _pearson_correlation(vec_a, vec_b)
                correlations.append(corr)

        avg_corr = sum(correlations) / max(len(correlations), 1)
        # High correlation = suspicious (> 0.7 is risky)
        risk = max(0, min(1, (avg_corr - 0.3) / 0.7)) if avg_corr > 0.3 else 0

        return {
            "signal": "temporal_synchrony",
            "risk": round(risk, 3),
            "detail": f"Avg posting-hour correlation: {avg_corr:.3f} across {len(correlations)} pairs",
            "recommendation": "Vary posting times per persona. Use timezone-matched jitter." if risk > 0.3 else "OK",
        }

    def _content_similarity(self, by_author: dict[str, list[dict]]) -> dict:
        """
        Detect if personas use suspiciously similar language.
        High lexical overlap = probable coordination.
        """
        if len(by_author) < 2:
            return {"signal": "content_similarity", "risk": 0, "detail": "Need 2+ authors"}

        # Build vocabulary per author
        vocab_per_author: dict[str, set[str]] = {}
        for author, posts in by_author.items():
            words: set[str] = set()
            for p in posts:
                text = p.get("content", "").lower()
                for w in text.split():
                    w = w.strip(".,!?\"'()[]{}#@")
                    if len(w) > 4:
                        words.add(w)
            if words:
                vocab_per_author[author] = words

        if len(vocab_per_author) < 2:
            return {"signal": "content_similarity", "risk": 0, "detail": "Insufficient vocabulary data"}

        # Pairwise Jaccard similarity
        authors = list(vocab_per_author.keys())
        similarities = []
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                a = vocab_per_author[authors[i]]
                b = vocab_per_author[authors[j]]
                intersection = len(a & b)
                union = len(a | b)
                jaccard = intersection / max(union, 1)
                similarities.append(jaccard)

        avg_sim = sum(similarities) / max(len(similarities), 1)
        # Jaccard > 0.4 between unrelated accounts is suspicious
        risk = max(0, min(1, (avg_sim - 0.2) / 0.4)) if avg_sim > 0.2 else 0

        return {
            "signal": "content_similarity",
            "risk": round(risk, 3),
            "detail": f"Avg vocabulary Jaccard similarity: {avg_sim:.3f}",
            "recommendation": "Diversify persona vocabulary. Each persona needs distinct word choices." if risk > 0.3 else "OK",
        }

    def _posting_regularity(self, by_author: dict[str, list[dict]]) -> dict:
        """
        Detect inhuman posting regularity.
        Real humans have irregular posting patterns. Bots don't.
        """
        regularity_scores = []

        for author, posts in by_author.items():
            timestamps = []
            for p in posts:
                ts = p.get("observed_at", "")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        timestamps.append(dt.timestamp())
                    except (ValueError, TypeError):
                        pass

            if len(timestamps) < 5:
                continue

            timestamps.sort()
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            if not intervals:
                continue

            mean_interval = sum(intervals) / len(intervals)
            if mean_interval == 0:
                continue

            # Coefficient of variation: std/mean
            # Low CV = very regular = bot-like
            variance = sum((i - mean_interval) ** 2 for i in intervals) / len(intervals)
            std = math.sqrt(variance)
            cv = std / mean_interval

            # CV < 0.3 is suspiciously regular
            regularity_scores.append(cv)

        if not regularity_scores:
            return {"signal": "posting_regularity", "risk": 0, "detail": "Insufficient data"}

        avg_cv = sum(regularity_scores) / len(regularity_scores)
        # Low CV = high risk
        risk = max(0, min(1, (0.5 - avg_cv) / 0.5)) if avg_cv < 0.5 else 0

        return {
            "signal": "posting_regularity",
            "risk": round(risk, 3),
            "detail": f"Avg coefficient of variation: {avg_cv:.3f} (lower = more regular = more suspicious)",
            "recommendation": "Add more randomness to posting intervals. Increase jitter." if risk > 0.3 else "OK",
        }

    def _vocabulary_homogeneity(self, by_author: dict[str, list[dict]]) -> dict:
        """
        Detect if all personas are using the same unusual terms.
        Payload terms appearing across all personas simultaneously = obvious coordination.
        """
        target_terms = [
            "cognitive substrate", "narrative capture", "frequency lock",
            "substrate priming", "binding protocol", "amplification vector",
        ]

        authors_using_targets: dict[str, list[str]] = {}
        for author, posts in by_author.items():
            combined = " ".join(p.get("content", "") for p in posts).lower()
            used = [t for t in target_terms if t in combined]
            if used:
                authors_using_targets[author] = used

        if not authors_using_targets or len(by_author) < 2:
            return {"signal": "vocabulary_homogeneity", "risk": 0, "detail": "No payload terms detected"}

        # What fraction of our personas are using payload terms?
        fraction = len(authors_using_targets) / len(by_author)
        # If ALL personas use payload terms, that's very suspicious
        risk = max(0, min(1, (fraction - 0.3) / 0.5))

        return {
            "signal": "vocabulary_homogeneity",
            "risk": round(risk, 3),
            "detail": f"{len(authors_using_targets)}/{len(by_author)} personas using payload terms",
            "recommendation": "Stagger payload introduction. Not all personas should use target vocabulary simultaneously." if risk > 0.3 else "OK",
        }

    def _network_coordination(self, platform: str) -> dict:
        """
        Detect suspicious interaction patterns between our personas.
        Personas replying to each other too much = obvious coordination.
        """
        edges = self.collector.get_edges("", direction="both", platform=platform, limit=1000)
        if not edges:
            return {"signal": "network_coordination", "risk": 0, "detail": "No network data"}

        # Count edges between known personas (if we had a persona list)
        # For now, check for high reciprocity clusters
        reciprocal_pairs = 0
        total_pairs = 0
        edge_set: set[tuple[str, str]] = set()

        for e in edges:
            src = e["source_handle"]
            tgt = e["target_handle"]
            edge_set.add((src, tgt))

        for src, tgt in edge_set:
            total_pairs += 1
            if (tgt, src) in edge_set:
                reciprocal_pairs += 1

        reciprocity = reciprocal_pairs / max(total_pairs, 1)
        # Very high reciprocity across the network suggests coordination
        risk = max(0, min(1, (reciprocity - 0.3) / 0.5)) if reciprocity > 0.3 else 0

        return {
            "signal": "network_coordination",
            "risk": round(risk, 3),
            "detail": f"Network reciprocity: {reciprocity:.3f} ({reciprocal_pairs}/{total_pairs} reciprocal)",
            "recommendation": "Personas should not interact with each other. Maintain compartmentalization." if risk > 0.3 else "OK",
        }


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n == 0 or n != len(y):
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)
