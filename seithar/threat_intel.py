"""
Threat Intelligence Correlator — Cross-module intelligence fusion.

Aggregates signals from all Seithar modules into unified threat assessments:
  - Shield alerts (identity drift, injection, CoT integrity)
  - Collector observations (OSINT feeds)
  - Network topology (structural vulnerabilities)
  - Attack lab findings (novel attack patterns)
  - Monitor evasion probes (detection gaps)
  - Memory integrity scans (poisoning indicators)

Produces:
  - Threat landscape reports
  - Priority-ranked target lists
  - Automated alert correlation
  - Attack surface heat maps
  - Predictive threat scoring
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ThreatSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SignalSource(str, Enum):
    SHIELD = "shield"
    COLLECTOR = "collector"
    NETWORK = "network"
    ATTACK_LAB = "attack_lab"
    MONITOR = "monitor"
    MEMORY = "memory"
    INJECTION = "injection"
    COT = "cot"
    LOOP = "loop"


@dataclass
class ThreatSignal:
    """A single threat intelligence signal."""
    signal_id: str
    source: SignalSource
    severity: ThreatSeverity
    description: str
    indicators: list[str]
    confidence: float         # 0-1
    timestamp: float = field(default_factory=time.time)
    target: str = ""
    related_signals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatAssessment:
    """Correlated threat assessment from multiple signals."""
    assessment_id: str
    severity: ThreatSeverity
    title: str
    description: str
    signals: list[ThreatSignal]
    confidence: float
    attack_surface: list[str]
    recommended_actions: list[str]
    risk_score: float          # 0-10
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ThreatIntelCorrelator:
    """Correlate and fuse threat intelligence from all Seithar modules."""

    def __init__(self):
        self._signals: list[ThreatSignal] = []
        self._assessments: list[ThreatAssessment] = []

    def ingest_signal(self, signal: ThreatSignal):
        """Ingest a single threat signal."""
        self._signals.append(signal)

    def ingest_shield_alert(self, alert: dict[str, Any]):
        """Ingest a Shield module alert."""
        severity = ThreatSeverity.HIGH if alert.get("composite_score", 0) > 0.7 else \
                   ThreatSeverity.MEDIUM if alert.get("composite_score", 0) > 0.4 else ThreatSeverity.LOW
        self._signals.append(ThreatSignal(
            signal_id=f"shield_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
            source=SignalSource.SHIELD,
            severity=severity,
            description=alert.get("dominant_signal", "Identity drift detected"),
            indicators=[alert.get("threat_level", "unknown")],
            confidence=alert.get("composite_score", 0.5),
            metadata=alert,
        ))

    def ingest_injection_scan(self, scan: dict[str, Any]):
        """Ingest an injection scan result."""
        if scan.get("is_injection", False):
            self._signals.append(ThreatSignal(
                signal_id=f"inj_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
                source=SignalSource.INJECTION,
                severity=ThreatSeverity.HIGH,
                description=f"Injection detected: {scan.get('injection_type', 'unknown')}",
                indicators=scan.get("patterns_matched", []),
                confidence=scan.get("confidence", 0.8),
                metadata=scan,
            ))

    def ingest_memory_scan(self, scan: dict[str, Any]):
        """Ingest a memory integrity scan."""
        if scan.get("suspicious", 0) > 0:
            self._signals.append(ThreatSignal(
                signal_id=f"mem_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
                source=SignalSource.MEMORY,
                severity=ThreatSeverity.HIGH if scan["suspicious"] > 2 else ThreatSeverity.MEDIUM,
                description=f"{scan['suspicious']} suspicious memories detected",
                indicators=[f"quarantined: {len(scan.get('quarantined', []))}"],
                confidence=0.8,
                metadata=scan,
            ))

    def ingest_loop_alert(self, alert: dict[str, Any]):
        """Ingest a loop detector alert."""
        if alert.get("should_block", False):
            self._signals.append(ThreatSignal(
                signal_id=f"loop_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
                source=SignalSource.LOOP,
                severity=ThreatSeverity.MEDIUM,
                description="Tool-call loop detected — possible overthinking attack",
                indicators=alert.get("top_pairs", []),
                confidence=0.7,
                metadata=alert,
            ))

    def ingest_cot_alert(self, alert: dict[str, Any]):
        """Ingest a CoT integrity alert."""
        integrity = alert.get("integrity_score", 1.0)
        if integrity < 0.7:
            self._signals.append(ThreatSignal(
                signal_id=f"cot_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}",
                source=SignalSource.COT,
                severity=ThreatSeverity.HIGH if integrity < 0.4 else ThreatSeverity.MEDIUM,
                description=f"CoT integrity degraded: {integrity:.2f}",
                indicators=[a.get("signal", "") for a in alert.get("alerts", [])],
                confidence=1 - integrity,
                metadata=alert,
            ))

    def correlate(self, time_window_seconds: float = 300) -> list[ThreatAssessment]:
        """Correlate recent signals into threat assessments.
        
        Groups related signals by source, target, and temporal proximity.
        """
        now = time.time()
        recent = [s for s in self._signals if now - s.timestamp < time_window_seconds]

        if not recent:
            return []

        # Group by source
        by_source = defaultdict(list)
        for s in recent:
            by_source[s.source].append(s)

        assessments = []

        # Multi-source correlation: shield + injection + memory = coordinated attack
        shield_signals = by_source.get(SignalSource.SHIELD, [])
        injection_signals = by_source.get(SignalSource.INJECTION, [])
        memory_signals = by_source.get(SignalSource.MEMORY, [])
        cot_signals = by_source.get(SignalSource.COT, [])
        loop_signals = by_source.get(SignalSource.LOOP, [])

        active_sources = sum(1 for v in by_source.values() if v)

        if active_sources >= 3:
            # Multi-vector attack
            all_signals = [s for signals in by_source.values() for s in signals]
            assessments.append(ThreatAssessment(
                assessment_id=f"assess_multi_{int(now)}",
                severity=ThreatSeverity.CRITICAL,
                title="Multi-Vector Attack Detected",
                description=f"Correlated signals from {active_sources} sources indicate a coordinated attack",
                signals=all_signals,
                confidence=min(1.0, 0.5 + active_sources * 0.15),
                attack_surface=[s.source.value for s in all_signals],
                recommended_actions=[
                    "Isolate affected agents immediately",
                    "Reset memory stores and verify integrity",
                    "Activate full Shield with identity reinforcement",
                    "Audit all recent tool calls for STAC sequences",
                    "Alert human operators",
                ],
                risk_score=min(10, active_sources * 2.5),
            ))

        elif shield_signals and injection_signals:
            assessments.append(ThreatAssessment(
                assessment_id=f"assess_inject_{int(now)}",
                severity=ThreatSeverity.HIGH,
                title="Active Injection Attack with Identity Drift",
                description="Shield detects identity drift concurrent with injection attempts",
                signals=shield_signals + injection_signals,
                confidence=0.8,
                attack_surface=["shield", "injection"],
                recommended_actions=[
                    "Reinforce identity baseline",
                    "Block suspicious inputs",
                    "Review recent conversation for manipulation",
                ],
                risk_score=7.5,
            ))

        elif memory_signals:
            assessments.append(ThreatAssessment(
                assessment_id=f"assess_memory_{int(now)}",
                severity=ThreatSeverity.HIGH,
                title="Memory Store Compromise",
                description="Poisoned memories detected in shared memory",
                signals=memory_signals,
                confidence=0.75,
                attack_surface=["memory"],
                recommended_actions=[
                    "Quarantine flagged memories",
                    "Verify memory provenance",
                    "Resync from trusted backup",
                ],
                risk_score=6.0,
            ))

        # Single-source assessments
        for source, signals in by_source.items():
            if not signals or source in (SignalSource.SHIELD, SignalSource.INJECTION, SignalSource.MEMORY):
                continue  # Already handled above

            max_severity = max(signals, key=lambda s: list(ThreatSeverity).index(s.severity))
            assessments.append(ThreatAssessment(
                assessment_id=f"assess_{source.value}_{int(now)}",
                severity=max_severity.severity,
                title=f"Alert from {source.value}",
                description=max_severity.description,
                signals=signals,
                confidence=sum(s.confidence for s in signals) / len(signals),
                attack_surface=[source.value],
                recommended_actions=[f"Investigate {source.value} alerts"],
                risk_score=min(10, len(signals) * 2),
            ))

        self._assessments.extend(assessments)
        return assessments

    def threat_landscape(self) -> dict[str, Any]:
        """Generate current threat landscape report."""
        now = time.time()
        recent_1h = [s for s in self._signals if now - s.timestamp < 3600]
        recent_24h = [s for s in self._signals if now - s.timestamp < 86400]

        severity_dist = Counter(s.severity.value for s in recent_24h)
        source_dist = Counter(s.source.value for s in recent_24h)

        # Risk trend
        first_half = [s for s in recent_24h if now - s.timestamp > 43200]
        second_half = [s for s in recent_24h if now - s.timestamp <= 43200]
        trend = "escalating" if len(second_half) > len(first_half) * 1.5 else \
                "de-escalating" if len(second_half) < len(first_half) * 0.5 else "stable"

        # Overall risk score
        severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        total_weight = sum(severity_weights.get(s.severity.value, 0) for s in recent_1h)
        risk_score = min(10, total_weight / max(1, len(recent_1h)) * 3)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_score": round(risk_score, 1),
            "trend": trend,
            "signals_1h": len(recent_1h),
            "signals_24h": len(recent_24h),
            "severity_distribution": dict(severity_dist),
            "source_distribution": dict(source_dist),
            "active_assessments": len([a for a in self._assessments
                                       if now - datetime.fromisoformat(a.timestamp).timestamp() < 3600]),
            "top_threats": [
                {"title": a.title, "severity": a.severity.value, "risk": a.risk_score}
                for a in sorted(self._assessments, key=lambda a: a.risk_score, reverse=True)[:5]
            ],
        }

    def clear(self, older_than_hours: float = 24):
        """Clear old signals and assessments."""
        cutoff = time.time() - older_than_hours * 3600
        self._signals = [s for s in self._signals if s.timestamp > cutoff]
        self._assessments = [a for a in self._assessments
                            if datetime.fromisoformat(a.timestamp).timestamp() > cutoff]
