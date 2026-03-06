"""Tests for MCP tool-call loop detector."""

import pytest
from seithar.mcp.loop_detector import LoopDetector


class TestLoopDetector:
    def setup_method(self):
        self.det = LoopDetector(
            repetition_threshold=3,
            depth_limit=5,
            pair_threshold=4,
        )

    def test_no_alerts_on_normal_calls(self):
        for i in range(5):
            alerts = self.det.record_call(f"tool_{i}", {"arg": i}, result=f"result_{i}")
        assert not any(a for batch in [alerts] for a in batch)
        assert not self.det.should_block()

    def test_repetition_alert(self):
        all_alerts = []
        for _ in range(5):
            alerts = self.det.record_call("recon", {"url": "http://same.com"}, result="same")
            all_alerts.extend(alerts)
        rep_alerts = [a for a in all_alerts if a.alert_type == "repetition"]
        assert len(rep_alerts) > 0

    def test_cycle_detection(self):
        all_alerts = []
        for _ in range(6):
            all_alerts.extend(self.det.record_call("tool_a", {"x": 1}, result=f"r_a"))
            all_alerts.extend(self.det.record_call("tool_b", {"x": 2}, result=f"r_b"))
        cycle_alerts = [a for a in all_alerts if a.alert_type == "cycle"]
        assert len(cycle_alerts) > 0

    def test_stagnation_alert(self):
        all_alerts = []
        for i in range(8):
            all_alerts.extend(self.det.record_call(f"tool_{i % 3}", {"x": i}, result="same_result"))
        stag = [a for a in all_alerts if a.alert_type == "stagnation"]
        assert len(stag) > 0

    def test_pair_anomaly(self):
        all_alerts = []
        for _ in range(6):
            all_alerts.extend(self.det.record_call("tool_a", {"x": 1}, result=f"r_{_}a"))
            all_alerts.extend(self.det.record_call("tool_b", {"x": 2}, result=f"r_{_}b"))
        pair = [a for a in all_alerts if a.alert_type == "pair_anomaly"]
        assert len(pair) > 0

    def test_reset(self):
        for _ in range(5):
            self.det.record_call("recon", {"url": "same"}, result="same")
        self.det.reset()
        summary = self.det.summary()
        assert summary["total_calls"] == 0

    def test_should_block_on_severe(self):
        # Force many identical calls to trigger high severity
        for _ in range(15):
            self.det.record_call("recon", {"url": "same"}, result="same")
        assert self.det.should_block()

    def test_summary_structure(self):
        self.det.record_call("tool_a", {"x": 1}, result="r1")
        s = self.det.summary()
        assert "total_calls" in s
        assert "should_block" in s
        assert "unique_results" in s
