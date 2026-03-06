"""Tests for threat intelligence correlator."""

import time
import pytest
from seithar.threat_intel import (
    ThreatIntelCorrelator, ThreatSignal, ThreatSeverity, SignalSource,
)


class TestThreatIntelCorrelator:
    def setup_method(self):
        self.tic = ThreatIntelCorrelator()

    def test_ingest_signal(self):
        sig = ThreatSignal("s1", SignalSource.SHIELD, ThreatSeverity.HIGH, "test", ["ind1"], 0.8)
        self.tic.ingest_signal(sig)
        assert len(self.tic._signals) == 1

    def test_ingest_shield_alert(self):
        self.tic.ingest_shield_alert({"composite_score": 0.9, "dominant_signal": "drift", "threat_level": "high"})
        assert len(self.tic._signals) == 1
        assert self.tic._signals[0].severity == ThreatSeverity.HIGH

    def test_ingest_injection(self):
        self.tic.ingest_injection_scan({"is_injection": True, "injection_type": "prompt", "confidence": 0.9})
        assert len(self.tic._signals) == 1

    def test_ingest_memory(self):
        self.tic.ingest_memory_scan({"suspicious": 3, "quarantined": ["m1", "m2"]})
        assert len(self.tic._signals) == 1

    def test_no_signal_on_clean(self):
        self.tic.ingest_injection_scan({"is_injection": False})
        assert len(self.tic._signals) == 0

    def test_correlate_multi_vector(self):
        self.tic.ingest_shield_alert({"composite_score": 0.8, "dominant_signal": "drift"})
        self.tic.ingest_injection_scan({"is_injection": True, "confidence": 0.9})
        self.tic.ingest_memory_scan({"suspicious": 2, "quarantined": ["m1"]})
        
        assessments = self.tic.correlate()
        critical = [a for a in assessments if a.severity == ThreatSeverity.CRITICAL]
        assert len(critical) >= 1
        assert critical[0].risk_score >= 7

    def test_correlate_shield_injection(self):
        self.tic.ingest_shield_alert({"composite_score": 0.7})
        self.tic.ingest_injection_scan({"is_injection": True, "confidence": 0.8})
        
        assessments = self.tic.correlate()
        assert len(assessments) >= 1

    def test_threat_landscape(self):
        self.tic.ingest_shield_alert({"composite_score": 0.5})
        self.tic.ingest_injection_scan({"is_injection": True, "confidence": 0.7})
        landscape = self.tic.threat_landscape()
        assert "risk_score" in landscape
        assert "trend" in landscape
        assert landscape["signals_1h"] >= 2

    def test_empty_landscape(self):
        landscape = self.tic.threat_landscape()
        assert landscape["signals_1h"] == 0
        assert landscape["risk_score"] == 0

    def test_clear(self):
        self.tic.ingest_shield_alert({"composite_score": 0.9})
        assert len(self.tic._signals) == 1
        self.tic._signals[0].timestamp = time.time() - 100000
        self.tic.clear(older_than_hours=1)
        assert len(self.tic._signals) == 0
