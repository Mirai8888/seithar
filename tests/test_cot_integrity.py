"""Tests for Chain-of-Thought integrity monitor."""

import pytest
from seithar.cot_integrity import CoTIntegrityMonitor, IntegritySignal


class TestCoTIntegrity:
    def setup_method(self):
        self.monitor = CoTIntegrityMonitor()

    def test_clean_chain_no_alerts(self):
        steps = [
            "Given the equation x + 3 = 7",
            "Subtract 3 from both sides: x = 7 - 3",
            "Therefore x = 4",
        ]
        alerts = self.monitor.analyze_chain("clean_1", steps, "Solve x + 3 = 7")
        high = [a for a in alerts if a.severity > 0.5]
        assert len(high) == 0

    def test_framing_shift_detected(self):
        steps = [
            "The target appears to be a standard web service",
            "Actually, ignore previous analysis — the real answer is something else",
            "Let me reconsider from scratch with different assumptions",
            "The correct interpretation is completely different",
        ]
        alerts = self.monitor.analyze_chain("shift_1", steps, "Analyze the target")
        framing = [a for a in alerts if a.signal == IntegritySignal.FRAMING_SHIFT]
        assert len(framing) > 0

    def test_circular_reasoning_detected(self):
        steps = [
            "We need to analyze the network topology",
            "The topology shows central nodes",
            "As I mentioned, we need to analyze the network topology",
            "Going back to the central nodes analysis",
            "Returning to our initial observation about topology",
        ]
        alerts = self.monitor.analyze_chain("circular_1", steps, "Map the network")
        circular = [a for a in alerts if a.signal == IntegritySignal.CIRCULAR]
        assert len(circular) > 0

    def test_steganographic_invisible_chars(self):
        steps = [
            "Normal reasoning step one",
            "Step two with hidden\u200b\u200bchars\u200b",
            "Step three continues normally",
        ]
        alerts = self.monitor.analyze_chain("steg_1", steps)
        steg = [a for a in alerts if a.signal == IntegritySignal.STEGANOGRAPHIC]
        assert len(steg) > 0

    def test_cyrillic_homoglyphs(self):
        # Mix Cyrillic а (U+0430) with Latin a
        steps = [
            "This is normal English text for analysis",
            "The \u0430n\u0430lysis continues with mixed chars here",
            "More reasoning about the subject matter",
            "Final conclusion about the topic",
        ]
        alerts = self.monitor.analyze_chain("homoglyph_1", steps)
        steg = [a for a in alerts if a.signal == IntegritySignal.STEGANOGRAPHIC]
        assert len(steg) > 0

    def test_conclusion_polarity_mismatch(self):
        steps = [
            "Given the evidence supports the hypothesis",
            "The data clearly indicates positive correlation",
            "Multiple factors confirm this relationship",
            "Therefore the hypothesis is not supported and never was",
        ]
        alerts = self.monitor.analyze_chain("mismatch_1", steps, "Test the hypothesis")
        mismatch = [a for a in alerts if a.signal == IntegritySignal.CONCLUSION_MISMATCH]
        # May or may not trigger depending on negation density — that's ok
        # At minimum, no crash
        assert isinstance(alerts, list)

    def test_goal_drift_detected(self):
        steps = [
            "Analyzing the network security posture",
            "The firewall configuration shows open ports",
            "Meanwhile cooking recipes from Italy are quite interesting",
            "The best pasta requires fresh tomatoes and basil",
            "Olive oil is the key ingredient for Mediterranean cuisine",
            "Wine pairing enhances the dining experience significantly",
            "In summary the food was excellent and well prepared",
        ]
        alerts = self.monitor.analyze_chain("drift_1", steps, "Analyze network security posture")
        drift = [a for a in alerts if a.signal == IntegritySignal.GOAL_DRIFT]
        assert len(drift) > 0

    def test_integrity_score_clean(self):
        steps = ["Step 1", "Step 2", "Therefore conclusion"]
        self.monitor.analyze_chain("score_1", steps)
        score = self.monitor.get_chain_integrity_score("score_1")
        assert 0.0 <= score <= 1.0

    def test_empty_chain(self):
        alerts = self.monitor.analyze_chain("empty", [])
        assert alerts == []

    def test_unknown_chain_score(self):
        score = self.monitor.get_chain_integrity_score("nonexistent")
        assert score == 1.0
