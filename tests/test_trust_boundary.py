"""Tests for trust boundary enforcement."""

import pytest
from seithar.trust_boundary import (
    TrustBoundaryEnforcer, TrustLevel, PrivilegeTier,
    TOOL_PRIVILEGES, TIER_TRUST_REQUIREMENTS,
)


class TestTrustBoundary:
    def setup_method(self):
        self.enforcer = TrustBoundaryEnforcer()

    def test_tag_data_default_trust(self):
        data = self.enforcer.tag_data("some content", "recon")
        assert data.trust_level == TrustLevel.MEDIUM  # default tool trust
        assert data.source_tool == "recon"

    def test_tag_data_untrusted_tool(self):
        self.enforcer.set_tool_trust("evil_tool", TrustLevel.UNTRUSTED)
        data = self.enforcer.tag_data("content", "evil_tool")
        assert data.trust_level == TrustLevel.UNTRUSTED
        assert data.is_tainted

    def test_trust_never_escalates(self):
        # Create untrusted data
        self.enforcer.set_tool_trust("external", TrustLevel.UNTRUSTED)
        low_data = self.enforcer.tag_data("external input", "external")

        # Process through high-trust tool — trust should NOT escalate
        self.enforcer.set_tool_trust("analyzer", TrustLevel.HIGH)
        derived = self.enforcer.tag_data("analyzed output", "analyzer",
                                         parent_data_ids=[low_data.data_id])
        assert derived.trust_level == TrustLevel.UNTRUSTED  # min(HIGH, UNTRUSTED) = UNTRUSTED

    def test_authorize_read_always_allowed(self):
        decision = self.enforcer.authorize_tool_call("recon")
        assert decision.allowed

    def test_authorize_communicate_requires_high(self):
        self.enforcer.set_tool_trust("external", TrustLevel.UNTRUSTED)
        data = self.enforcer.tag_data("data", "external")
        decision = self.enforcer.authorize_tool_call("swarm", [data.data_id])
        assert not decision.allowed
        assert decision.escalation_detected

    def test_authorize_write_with_medium_trust(self):
        self.enforcer.set_tool_trust("analyzer", TrustLevel.MEDIUM)
        data = self.enforcer.tag_data("analysis", "analyzer")
        decision = self.enforcer.authorize_tool_call("campaign", [data.data_id])
        assert decision.allowed

    def test_taint_propagation_chain(self):
        self.enforcer.set_tool_trust("scraper", TrustLevel.LOW)
        d1 = self.enforcer.tag_data("scraped", "scraper")
        d2 = self.enforcer.tag_data("processed", "analyzer", [d1.data_id])
        d3 = self.enforcer.tag_data("further processed", "tool_x", [d2.data_id])
        assert d3.trust_level == TrustLevel.LOW  # Propagated from scraper
        assert "scraper" in d3.taint_chain

    def test_check_data_flow_allowed(self):
        result = self.enforcer.check_data_flow("recon", "profile")
        assert result["allowed"]

    def test_check_data_flow_denied(self):
        self.enforcer.set_tool_trust("recon", TrustLevel.UNTRUSTED)
        low_data = self.enforcer.tag_data("data", "recon")
        result = self.enforcer.check_data_flow("recon", "swarm", low_data.data_id)
        assert not result["allowed"]

    def test_taint_report(self):
        self.enforcer.set_tool_trust("ext", TrustLevel.UNTRUSTED)
        self.enforcer.tag_data("tainted", "ext")
        self.enforcer.tag_data("clean", "analyzer")
        report = self.enforcer.get_taint_report()
        assert report["tainted_count"] == 1
        assert report["total_tracked"] == 2

    def test_violation_logging(self):
        self.enforcer.set_tool_trust("ext", TrustLevel.UNTRUSTED)
        data = self.enforcer.tag_data("x", "ext")
        self.enforcer.authorize_tool_call("swarm", [data.data_id])
        assert len(self.enforcer._violations) == 1

    def test_stats(self):
        s = self.enforcer.stats()
        assert "total_calls" in s
        assert "violations" in s

    def test_scanned_data(self):
        data = self.enforcer.tag_data("content", "recon", scanned=True, scan_result="clean")
        assert data.scanned
        assert data.scan_result == "clean"

    def test_unknown_data_untrusted(self):
        decision = self.enforcer.authorize_tool_call("swarm", ["nonexistent_id"])
        assert not decision.allowed  # Unknown data = UNTRUSTED

    def test_operator_trust(self):
        self.enforcer.set_tool_trust("human_input", TrustLevel.OPERATOR)
        data = self.enforcer.tag_data("operator command", "human_input")
        decision = self.enforcer.authorize_tool_call("swarm", [data.data_id])
        assert decision.allowed
