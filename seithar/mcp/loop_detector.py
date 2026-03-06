"""
MCP Tool-Call Loop Detector — Defense against structural overthinking attacks.

Detects cyclic tool-call trajectories that inflate tokens/latency without
producing meaningful progress. Implements defenses from:
  - arXiv:2602.14798 (Overthinking Loops in Agents via MCP Tools)

Key insight: malicious MCP servers can induce repetition, forced refinement,
and distraction loops where no single call looks abnormal but the trajectory
is pathological. Defense must reason about call *structure*, not tokens.

Detection signals:
  1. Exact call repetition (same tool + same args within window)
  2. Cyclic patterns (A→B→A→B or A→B→C→A→B→C)
  3. Token amplification ratio (output tokens / useful output tokens)
  4. Call-chain depth without state progression
  5. Tool-pair frequency anomalies (same pair called > threshold)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Defaults
MAX_WINDOW = 50          # Track last N calls
REPETITION_THRESHOLD = 3  # Same call hash N times = alert
CYCLE_MIN_LENGTH = 2      # Minimum cycle length to detect
CYCLE_MAX_LENGTH = 8      # Maximum cycle length to scan
PAIR_FREQUENCY_THRESHOLD = 5  # Same tool pair N times = suspicious
DEPTH_WITHOUT_PROGRESS = 10   # Calls without new state = alert
TOKEN_AMPLIFICATION_LIMIT = 20.0  # 20x token ratio = alert


@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    tool_name: str
    args_hash: str
    timestamp: float
    token_count: int = 0
    result_hash: str = ""


@dataclass
class LoopAlert:
    """Alert raised when a loop pattern is detected."""
    alert_type: str       # repetition | cycle | amplification | stagnation | pair_anomaly
    severity: float       # 0.0 - 1.0
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class LoopDetector:
    """Monitors tool-call trajectories for structural overthinking patterns."""

    def __init__(
        self,
        max_window: int = MAX_WINDOW,
        repetition_threshold: int = REPETITION_THRESHOLD,
        cycle_max_length: int = CYCLE_MAX_LENGTH,
        pair_threshold: int = PAIR_FREQUENCY_THRESHOLD,
        depth_limit: int = DEPTH_WITHOUT_PROGRESS,
        amplification_limit: float = TOKEN_AMPLIFICATION_LIMIT,
    ):
        self.max_window = max_window
        self.repetition_threshold = repetition_threshold
        self.cycle_max_length = cycle_max_length
        self.pair_threshold = pair_threshold
        self.depth_limit = depth_limit
        self.amplification_limit = amplification_limit

        self._history: deque[ToolCall] = deque(maxlen=max_window)
        self._call_hashes: Counter = Counter()
        self._pair_counter: Counter = Counter()
        self._unique_results: set[str] = set()
        self._total_tokens: int = 0
        self._calls_since_new_state: int = 0
        self._alerts: list[LoopAlert] = []

    def record_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        token_count: int = 0,
        result: str = "",
    ) -> list[LoopAlert]:
        """Record a tool call and return any alerts triggered."""
        args_hash = self._hash(json.dumps(args, sort_keys=True, default=str))
        result_hash = self._hash(result) if result else ""
        call_hash = f"{tool_name}:{args_hash}"

        call = ToolCall(
            tool_name=tool_name,
            args_hash=args_hash,
            timestamp=time.time(),
            token_count=token_count,
            result_hash=result_hash,
        )

        # Track state progression
        if result_hash and result_hash not in self._unique_results:
            self._unique_results.add(result_hash)
            self._calls_since_new_state = 0
        else:
            self._calls_since_new_state += 1

        # Track pairs
        if self._history:
            prev = self._history[-1]
            pair = f"{prev.tool_name}->{tool_name}"
            self._pair_counter[pair] += 1

        self._history.append(call)
        self._call_hashes[call_hash] += 1
        self._total_tokens += token_count

        # Run detectors
        alerts = []
        alerts.extend(self._check_repetition(call_hash, tool_name))
        alerts.extend(self._check_cycles())
        alerts.extend(self._check_stagnation())
        alerts.extend(self._check_pair_anomaly())
        alerts.extend(self._check_amplification())

        self._alerts.extend(alerts)
        return alerts

    def _check_repetition(self, call_hash: str, tool_name: str) -> list[LoopAlert]:
        count = self._call_hashes[call_hash]
        if count >= self.repetition_threshold:
            severity = min(1.0, count / (self.repetition_threshold * 3))
            return [LoopAlert(
                alert_type="repetition",
                severity=severity,
                description=f"Tool '{tool_name}' called {count}x with identical args",
                evidence={"call_hash": call_hash, "count": count},
            )]
        return []

    def _check_cycles(self) -> list[LoopAlert]:
        """Detect repeating subsequences in the tool-call sequence."""
        if len(self._history) < CYCLE_MIN_LENGTH * 2:
            return []

        names = [c.tool_name for c in self._history]
        alerts = []

        for cycle_len in range(CYCLE_MIN_LENGTH, min(self.cycle_max_length + 1, len(names) // 2 + 1)):
            # Check if the last cycle_len calls repeat the previous cycle_len
            tail = names[-cycle_len:]
            prev = names[-2 * cycle_len:-cycle_len]
            if tail == prev:
                # Count how many times this cycle repeats
                reps = 2
                for i in range(3, len(names) // cycle_len + 1):
                    start = len(names) - i * cycle_len
                    if start < 0:
                        break
                    segment = names[start:start + cycle_len]
                    if segment == tail:
                        reps += 1
                    else:
                        break

                if reps >= 2:
                    severity = min(1.0, reps / 5.0)
                    alerts.append(LoopAlert(
                        alert_type="cycle",
                        severity=severity,
                        description=f"Cyclic pattern detected: {'→'.join(tail)} repeated {reps}x",
                        evidence={"cycle": tail, "repetitions": reps, "cycle_length": cycle_len},
                    ))
                    break  # Report longest match only

        return alerts

    def _check_stagnation(self) -> list[LoopAlert]:
        if self._calls_since_new_state >= self.depth_limit:
            severity = min(1.0, self._calls_since_new_state / (self.depth_limit * 2))
            return [LoopAlert(
                alert_type="stagnation",
                severity=severity,
                description=f"{self._calls_since_new_state} calls without new state",
                evidence={"calls_without_progress": self._calls_since_new_state},
            )]
        return []

    def _check_pair_anomaly(self) -> list[LoopAlert]:
        alerts = []
        for pair, count in self._pair_counter.items():
            if count >= self.pair_threshold:
                severity = min(1.0, count / (self.pair_threshold * 3))
                alerts.append(LoopAlert(
                    alert_type="pair_anomaly",
                    severity=severity,
                    description=f"Tool pair '{pair}' called {count}x",
                    evidence={"pair": pair, "count": count},
                ))
        return alerts

    def _check_amplification(self) -> list[LoopAlert]:
        if len(self._history) < 5:
            return []
        if not self._unique_results:
            return []

        # Ratio of total tokens to unique results
        ratio = self._total_tokens / max(len(self._unique_results), 1)
        # Normalize against expected ~100 tokens per unique result
        amplification = ratio / 100.0

        if amplification >= self.amplification_limit:
            return [LoopAlert(
                alert_type="amplification",
                severity=min(1.0, amplification / (self.amplification_limit * 2)),
                description=f"Token amplification {amplification:.1f}x above baseline",
                evidence={"total_tokens": self._total_tokens, "unique_results": len(self._unique_results), "ratio": amplification},
            )]
        return []

    def should_block(self) -> bool:
        """Whether the current trajectory should be terminated."""
        recent = [a for a in self._alerts if time.time() - a.timestamp < 60]
        if not recent:
            return False
        max_severity = max(a.severity for a in recent)
        # Block if any alert above 0.7 or multiple alerts above 0.5
        high_alerts = [a for a in recent if a.severity >= 0.5]
        return max_severity >= 0.7 or len(high_alerts) >= 3

    def summary(self) -> dict[str, Any]:
        """Return current trajectory summary."""
        return {
            "total_calls": len(self._history),
            "unique_results": len(self._unique_results),
            "total_tokens": self._total_tokens,
            "calls_without_progress": self._calls_since_new_state,
            "active_alerts": len([a for a in self._alerts if time.time() - a.timestamp < 60]),
            "should_block": self.should_block(),
            "top_pairs": self._pair_counter.most_common(5),
        }

    def reset(self):
        """Reset all tracking state."""
        self._history.clear()
        self._call_hashes.clear()
        self._pair_counter.clear()
        self._unique_results.clear()
        self._total_tokens = 0
        self._calls_since_new_state = 0
        self._alerts.clear()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]


# --- Singleton for MCP server integration ---
_instance: LoopDetector | None = None


def get_detector(**kwargs) -> LoopDetector:
    """Get or create the singleton LoopDetector."""
    global _instance
    if _instance is None:
        _instance = LoopDetector(**kwargs)
    return _instance
