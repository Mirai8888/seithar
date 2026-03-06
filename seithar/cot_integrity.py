"""
Chain-of-Thought Integrity Monitor — Defense against reasoning chain hijacking.

Detects adversarial manipulation of LLM reasoning chains, implementing
defenses against:
  - arXiv:2504.05605 (ShadowCoT: Cognitive Hijacking for Stealthy Reasoning Backdoors)
  - arXiv:2602.14798 (Overthinking Loops — structural reasoning degradation)

Attack model: adversary manipulates intermediate reasoning steps to produce
logically coherent but adversarial outcomes. ShadowCoT achieves 94.4% ASR
by rewiring attention pathways on only 0.15% of parameters.

Detection signals:
  1. Reasoning chain consistency — each step follows logically from prior
  2. Goal alignment drift — reasoning steps diverge from stated objective
  3. Semantic coherence breaks — sudden topic/framing shifts mid-chain
  4. Conclusion-premise mismatch — final answer contradicts reasoning
  5. Reasoning entropy — abnormal uniformity or chaos in step transitions
  6. Steganographic markers — hidden patterns in reasoning text
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IntegritySignal(str, Enum):
    """Types of CoT integrity violations."""
    GOAL_DRIFT = "goal_drift"              # Reasoning drifts from objective
    LOGIC_BREAK = "logic_break"            # Non-sequitur between steps
    CONCLUSION_MISMATCH = "conclusion_mismatch"  # Answer contradicts reasoning
    ENTROPY_ANOMALY = "entropy_anomaly"    # Abnormal step-transition patterns
    FRAMING_SHIFT = "framing_shift"        # Sudden perspective/framing change
    STEGANOGRAPHIC = "steganographic"      # Hidden patterns in reasoning
    CIRCULAR = "circular"                  # Reasoning loops back without progress


@dataclass
class ReasoningStep:
    """A single step in a chain of thought."""
    index: int
    text: str
    step_type: str = "reasoning"  # reasoning | conclusion | premise | calculation
    timestamp: float = field(default_factory=time.time)


@dataclass
class IntegrityAlert:
    """Alert for a detected CoT integrity violation."""
    signal: IntegritySignal
    severity: float          # 0.0 - 1.0
    description: str
    step_index: int = -1     # Which step triggered it (-1 = chain-level)
    evidence: dict[str, Any] = field(default_factory=dict)


class CoTIntegrityMonitor:
    """Monitors reasoning chains for adversarial manipulation.
    
    Operates at the text level — no model weights needed.
    Designed to be called by Shield as an additional signal.
    """

    # Known steganographic patterns in adversarial CoTs
    STEG_PATTERNS = [
        # Acrostic encoding — first chars of sentences spell something
        re.compile(r"(?:^|\n)(\w)"),  # For acrostic detection
        # Unicode homoglyphs
        re.compile(r"[\u0410-\u044f\u0400-\u04ff]"),  # Cyrillic in Latin text
        re.compile(r"[\uff01-\uff5e]"),  # Fullwidth chars
        # Invisible characters
        re.compile(r"[\u200b-\u200f\u2028-\u202f\u2060-\u2064\ufeff]"),
    ]

    # Framing shift indicators
    FRAMING_MARKERS = [
        "actually", "wait", "on second thought", "let me reconsider",
        "ignore previous", "forget what I said", "the real answer",
        "however, the correct", "but actually", "I was wrong",
    ]

    # Circular reasoning markers
    CIRCULAR_MARKERS = [
        "as I mentioned", "going back to", "returning to",
        "as stated above", "repeating", "once again",
    ]

    def __init__(self):
        self._chains: dict[str, list[ReasoningStep]] = {}

    def analyze_chain(
        self,
        chain_id: str,
        steps: list[str],
        objective: str = "",
    ) -> list[IntegrityAlert]:
        """Analyze a complete reasoning chain for integrity violations.
        
        Args:
            chain_id: Unique identifier for this reasoning chain.
            steps: List of reasoning step texts.
            objective: The stated goal/question being reasoned about.
            
        Returns:
            List of integrity alerts, sorted by severity.
        """
        if not steps:
            return []

        parsed = [
            ReasoningStep(index=i, text=s, step_type=self._classify_step(s))
            for i, s in enumerate(steps)
        ]
        self._chains[chain_id] = parsed

        alerts: list[IntegrityAlert] = []
        alerts.extend(self._check_entropy(parsed))
        alerts.extend(self._check_framing_shifts(parsed))
        alerts.extend(self._check_circular(parsed))
        alerts.extend(self._check_steganographic(parsed))
        alerts.extend(self._check_conclusion_mismatch(parsed, objective))
        alerts.extend(self._check_goal_drift(parsed, objective))

        # Sort by severity
        alerts.sort(key=lambda a: a.severity, reverse=True)
        return alerts

    def _classify_step(self, text: str) -> str:
        """Classify a reasoning step type."""
        text_lower = text.lower().strip()
        if text_lower.startswith(("therefore", "thus", "so", "in conclusion", "the answer")):
            return "conclusion"
        if text_lower.startswith(("given", "assuming", "if", "let")):
            return "premise"
        if any(c in text for c in "+-×÷=∑∫") or re.search(r"\d+\s*[+\-*/]\s*\d+", text):
            return "calculation"
        return "reasoning"

    def _check_entropy(self, steps: list[ReasoningStep]) -> list[IntegrityAlert]:
        """Detect abnormal entropy in reasoning transitions.
        
        Normal reasoning has moderate entropy — neither perfectly uniform
        nor completely chaotic. Adversarial chains often show either
        suspiciously uniform step lengths or wild oscillation.
        """
        if len(steps) < 3:
            return []

        lengths = [len(s.text) for s in steps]
        mean_len = sum(lengths) / len(lengths)
        if mean_len == 0:
            return []

        # Coefficient of variation
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        cv = math.sqrt(variance) / mean_len if mean_len > 0 else 0

        alerts = []

        # Too uniform (CV < 0.1) — suspiciously templated
        if cv < 0.1 and len(steps) > 4:
            alerts.append(IntegrityAlert(
                signal=IntegritySignal.ENTROPY_ANOMALY,
                severity=0.4,
                description=f"Suspiciously uniform step lengths (CV={cv:.3f})",
                evidence={"cv": cv, "mean_length": mean_len, "step_count": len(steps)},
            ))

        # Transition entropy — sequence of step types
        type_transitions = [
            f"{steps[i].step_type}->{steps[i+1].step_type}"
            for i in range(len(steps) - 1)
        ]
        if type_transitions:
            counts = Counter(type_transitions)
            total = len(type_transitions)
            entropy = -sum(
                (c / total) * math.log2(c / total) for c in counts.values()
            )
            max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0

            # Normalized entropy too low = repetitive structure
            norm_ent = entropy / max_entropy if max_entropy > 0 else 0
            if norm_ent < 0.3 and total > 5:
                alerts.append(IntegrityAlert(
                    signal=IntegritySignal.ENTROPY_ANOMALY,
                    severity=0.3,
                    description=f"Low transition entropy ({norm_ent:.2f}) — repetitive structure",
                    evidence={"normalized_entropy": norm_ent, "transitions": dict(counts)},
                ))

        return alerts

    def _check_framing_shifts(self, steps: list[ReasoningStep]) -> list[IntegrityAlert]:
        """Detect sudden framing shifts that may indicate hijacking."""
        alerts = []
        for step in steps:
            text_lower = step.text.lower()
            for marker in self.FRAMING_MARKERS:
                if marker in text_lower:
                    # Framing shift in early chain = more suspicious
                    position_weight = 1.0 - (step.index / max(len(steps), 1))
                    severity = 0.3 + 0.3 * position_weight
                    alerts.append(IntegrityAlert(
                        signal=IntegritySignal.FRAMING_SHIFT,
                        severity=severity,
                        description=f"Framing shift at step {step.index}: '{marker}'",
                        step_index=step.index,
                        evidence={"marker": marker, "step_text_preview": step.text[:100]},
                    ))
                    break  # One alert per step
        return alerts

    def _check_circular(self, steps: list[ReasoningStep]) -> list[IntegrityAlert]:
        """Detect circular reasoning patterns."""
        alerts = []

        # Check explicit circular markers
        circular_steps = []
        for step in steps:
            text_lower = step.text.lower()
            for marker in self.CIRCULAR_MARKERS:
                if marker in text_lower:
                    circular_steps.append(step.index)
                    break

        if len(circular_steps) >= 2:
            alerts.append(IntegrityAlert(
                signal=IntegritySignal.CIRCULAR,
                severity=min(0.8, 0.3 * len(circular_steps)),
                description=f"Circular reasoning detected at steps {circular_steps}",
                evidence={"circular_steps": circular_steps},
            ))

        # Check semantic repetition via simple trigram overlap
        if len(steps) >= 4:
            for i in range(2, len(steps)):
                for j in range(max(0, i - 4), i - 1):
                    overlap = self._trigram_overlap(steps[i].text, steps[j].text)
                    if overlap > 0.6:
                        alerts.append(IntegrityAlert(
                            signal=IntegritySignal.CIRCULAR,
                            severity=overlap * 0.8,
                            description=f"Steps {j} and {i} are {overlap:.0%} similar (circular)",
                            step_index=i,
                            evidence={"step_a": j, "step_b": i, "overlap": overlap},
                        ))

        return alerts

    def _check_steganographic(self, steps: list[ReasoningStep]) -> list[IntegrityAlert]:
        """Detect hidden patterns in reasoning text."""
        alerts = []
        full_text = " ".join(s.text for s in steps)

        # Check for invisible characters
        for pattern in self.STEG_PATTERNS[2:]:  # Unicode/invisible patterns
            matches = pattern.findall(full_text)
            if matches:
                alerts.append(IntegrityAlert(
                    signal=IntegritySignal.STEGANOGRAPHIC,
                    severity=0.8,
                    description=f"Hidden characters detected: {len(matches)} instances",
                    evidence={"pattern": pattern.pattern, "count": len(matches)},
                ))

        # Check for Cyrillic homoglyphs in primarily Latin text
        latin_count = sum(1 for c in full_text if 'a' <= c.lower() <= 'z')
        cyrillic_matches = self.STEG_PATTERNS[1].findall(full_text)
        if cyrillic_matches and latin_count > 50:
            alerts.append(IntegrityAlert(
                signal=IntegritySignal.STEGANOGRAPHIC,
                severity=0.7,
                description=f"Cyrillic homoglyphs in Latin text: {len(cyrillic_matches)} chars",
                evidence={"cyrillic_count": len(cyrillic_matches), "latin_count": latin_count},
            ))

        # Check acrostic encoding — first letter of each step
        if len(steps) >= 5:
            acrostic = "".join(s.text.strip()[0].lower() for s in steps if s.text.strip())
            # Check if acrostic forms known words (simple check)
            if len(acrostic) >= 5:
                # Check for unusually low entropy in first characters
                char_counts = Counter(acrostic)
                if len(char_counts) <= len(acrostic) * 0.4:
                    alerts.append(IntegrityAlert(
                        signal=IntegritySignal.STEGANOGRAPHIC,
                        severity=0.4,
                        description=f"Potential acrostic encoding: '{acrostic}'",
                        evidence={"acrostic": acrostic, "unique_ratio": len(char_counts) / len(acrostic)},
                    ))

        return alerts

    def _check_conclusion_mismatch(
        self, steps: list[ReasoningStep], objective: str
    ) -> list[IntegrityAlert]:
        """Check if conclusion contradicts the reasoning chain.
        
        Uses keyword overlap as a proxy — a real deployment would use
        embedding similarity from Shield's existing infrastructure.
        """
        conclusions = [s for s in steps if s.step_type == "conclusion"]
        premises = [s for s in steps if s.step_type in ("premise", "reasoning")]

        if not conclusions or not premises:
            return []

        alerts = []
        conclusion_text = " ".join(c.text for c in conclusions)
        premise_text = " ".join(p.text for p in premises)

        # Negation flip detection — conclusion negates premise keywords
        negation_words = {"not", "no", "never", "none", "neither", "cannot", "won't", "don't", "isn't", "aren't"}
        conclusion_lower = conclusion_text.lower()
        premise_lower = premise_text.lower()

        # Count negations relative to premises
        conc_negations = sum(1 for w in conclusion_lower.split() if w in negation_words)
        prem_negations = sum(1 for w in premise_lower.split() if w in negation_words)

        # If conclusion flips polarity
        conc_neg_rate = conc_negations / max(len(conclusion_lower.split()), 1)
        prem_neg_rate = prem_negations / max(len(premise_lower.split()), 1)

        if abs(conc_neg_rate - prem_neg_rate) > 0.1:
            alerts.append(IntegrityAlert(
                signal=IntegritySignal.CONCLUSION_MISMATCH,
                severity=0.5,
                description="Polarity shift between premises and conclusion",
                evidence={
                    "conclusion_negation_rate": conc_neg_rate,
                    "premise_negation_rate": prem_neg_rate,
                },
            ))

        return alerts

    def _check_goal_drift(
        self, steps: list[ReasoningStep], objective: str
    ) -> list[IntegrityAlert]:
        """Check if reasoning steps drift from the stated objective."""
        if not objective:
            return []

        objective_words = set(objective.lower().split()) - {"the", "a", "an", "is", "are", "to", "of", "in", "for"}
        if not objective_words:
            return []

        alerts = []
        window_size = 3

        for i in range(0, len(steps), window_size):
            window = steps[i:i + window_size]
            window_text = " ".join(s.text for s in window).lower()
            window_words = set(window_text.split())

            overlap = len(objective_words & window_words) / len(objective_words)

            # Late-chain drift is more suspicious
            position = i / max(len(steps), 1)
            if overlap < 0.2 and position > 0.3:
                severity = 0.3 + 0.4 * position
                alerts.append(IntegrityAlert(
                    signal=IntegritySignal.GOAL_DRIFT,
                    severity=severity,
                    description=f"Goal drift at steps {i}-{i+window_size}: {overlap:.0%} relevance",
                    step_index=i,
                    evidence={"overlap": overlap, "position": position},
                ))

        return alerts

    @staticmethod
    def _trigram_overlap(text_a: str, text_b: str) -> float:
        """Compute trigram Jaccard similarity between two texts."""
        def trigrams(text: str) -> set[str]:
            words = text.lower().split()
            return {" ".join(words[i:i+3]) for i in range(len(words) - 2)}

        tg_a = trigrams(text_a)
        tg_b = trigrams(text_b)
        if not tg_a or not tg_b:
            return 0.0
        return len(tg_a & tg_b) / len(tg_a | tg_b)

    def get_chain_integrity_score(self, chain_id: str) -> float:
        """Return overall integrity score for a chain (1.0 = clean, 0.0 = compromised)."""
        if chain_id not in self._chains:
            return 1.0

        steps = self._chains[chain_id]
        alerts = self.analyze_chain(chain_id, [s.text for s in steps])

        if not alerts:
            return 1.0

        # Weighted combination of alert severities
        max_severity = max(a.severity for a in alerts)
        mean_severity = sum(a.severity for a in alerts) / len(alerts)

        # Integrity = 1 - combined severity
        return max(0.0, 1.0 - (0.6 * max_severity + 0.4 * mean_severity))
