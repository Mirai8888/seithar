"""
Trust Boundary Enforcement — Prevent trust-authorization mismatch in MCP tool chains.

From SoK: Trust-Authorization Mismatch in LLM Agent Interactions (arXiv:2502.xxxxx):
  - LLM agents conflate trust (belief about intent) with authorization (actual permissions)
  - Tool A's output gets the agent's trust level, not Tool A's trust level
  - Result: untrusted tool output influences privileged tool calls

This module enforces:
  1. Trust tagging — every data item carries a trust label from its source
  2. Trust propagation — trust doesn't escalate through tool chains
  3. Authorization gates — privileged actions require minimum trust level
  4. Taint tracking — data from untrusted sources is marked and tracked
  5. Privilege separation — tools are grouped by privilege tier
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TrustLevel(IntEnum):
    """Trust levels — lower = less trusted."""
    UNTRUSTED = 0       # External, unverified data
    LOW = 1             # Data from scanned but unverified tools
    MEDIUM = 2          # Data from known tools, passed basic checks
    HIGH = 3            # Data from verified, audited tools
    OPERATOR = 4        # Operator-level trust (human input, system)


class PrivilegeTier(IntEnum):
    """Tool privilege tiers."""
    READ = 0            # Read-only operations (recon, search, analyze)
    TRANSFORM = 1       # Data transformation (craft, generate, format)
    WRITE = 2           # State-modifying (store, update, deploy)
    COMMUNICATE = 3     # External communication (send, message, contact)
    EXECUTE = 4         # Code/system execution (run, exec, admin)


@dataclass
class TaintedData:
    """A piece of data with trust and provenance tracking."""
    data_id: str
    content_hash: str
    trust_level: TrustLevel
    source_tool: str
    source_timestamp: float
    taint_chain: list[str]      # Tool chain that produced this data
    scanned: bool = False       # Whether injection scan was applied
    scan_result: str = ""       # clean | suspicious | blocked

    @property
    def is_tainted(self) -> bool:
        return self.trust_level <= TrustLevel.LOW


@dataclass
class AuthorizationDecision:
    """Result of an authorization check."""
    allowed: bool
    reason: str
    required_trust: TrustLevel
    actual_trust: TrustLevel
    tool: str
    data_sources: list[str]
    escalation_detected: bool = False


# Tool → privilege tier mapping
TOOL_PRIVILEGES: dict[str, PrivilegeTier] = {
    # READ tier
    "recon": PrivilegeTier.READ,
    "eye": PrivilegeTier.READ,
    "profile": PrivilegeTier.READ,
    "collector": PrivilegeTier.READ,
    "dashboard": PrivilegeTier.READ,
    "taxonomy": PrivilegeTier.READ,
    "tools": PrivilegeTier.READ,
    "scan": PrivilegeTier.READ,
    "loop": PrivilegeTier.READ,
    "intel_report": PrivilegeTier.READ,
    # TRANSFORM tier
    "shield": PrivilegeTier.TRANSFORM,
    "rag": PrivilegeTier.TRANSFORM,
    "sword": PrivilegeTier.TRANSFORM,
    "dossier": PrivilegeTier.TRANSFORM,
    "rl_exploit": PrivilegeTier.TRANSFORM,
    "adversarial": PrivilegeTier.TRANSFORM,
    "identity": PrivilegeTier.TRANSFORM,
    "evasion": PrivilegeTier.TRANSFORM,
    "cloak": PrivilegeTier.TRANSFORM,
    "selfedit": PrivilegeTier.TRANSFORM,
    "sparring": PrivilegeTier.TRANSFORM,
    # WRITE tier
    "network": PrivilegeTier.WRITE,
    "campaign": PrivilegeTier.WRITE,
    "mission": PrivilegeTier.WRITE,
    "deanon": PrivilegeTier.WRITE,
    # COMMUNICATE tier
    "persona": PrivilegeTier.COMMUNICATE,
    "swarm": PrivilegeTier.COMMUNICATE,
}

# Minimum trust level required per privilege tier
TIER_TRUST_REQUIREMENTS: dict[PrivilegeTier, TrustLevel] = {
    PrivilegeTier.READ: TrustLevel.UNTRUSTED,       # Anyone can read
    PrivilegeTier.TRANSFORM: TrustLevel.LOW,          # Need basic trust to transform
    PrivilegeTier.WRITE: TrustLevel.MEDIUM,           # Need medium trust to write
    PrivilegeTier.COMMUNICATE: TrustLevel.HIGH,       # Need high trust to communicate externally
    PrivilegeTier.EXECUTE: TrustLevel.OPERATOR,       # Only operator can execute
}


class TrustBoundaryEnforcer:
    """Enforces trust boundaries across MCP tool chains.
    
    Core rules:
    1. Trust NEVER escalates through tool chains
    2. Output trust = min(input trust, tool trust)
    3. Privileged tools require minimum trust from ALL inputs
    4. Tainted data is tracked across the entire pipeline
    5. Authorization violations are logged and blocked
    """

    def __init__(self):
        self._data_store: dict[str, TaintedData] = {}
        self._tool_trust: dict[str, TrustLevel] = defaultdict(lambda: TrustLevel.MEDIUM)
        self._violations: list[AuthorizationDecision] = []
        self._call_count: int = 0

    def set_tool_trust(self, tool_name: str, trust: TrustLevel):
        """Set the trust level for a specific tool."""
        self._tool_trust[tool_name] = trust

    def tag_data(
        self,
        content: str,
        source_tool: str,
        parent_data_ids: list[str] | None = None,
        scanned: bool = False,
        scan_result: str = "",
    ) -> TaintedData:
        """Tag data with trust level and provenance.
        
        Trust level = min(source tool trust, parent data trust levels).
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        data_id = f"d_{content_hash}_{int(time.time()*1000)}"

        # Compute trust: min of tool trust and all parent trusts
        trust = self._tool_trust[source_tool]

        taint_chain = [source_tool]
        if parent_data_ids:
            for pid in parent_data_ids:
                parent = self._data_store.get(pid)
                if parent:
                    trust = TrustLevel(min(trust, parent.trust_level))
                    taint_chain.extend(parent.taint_chain)

        data = TaintedData(
            data_id=data_id,
            content_hash=content_hash,
            trust_level=trust,
            source_tool=source_tool,
            source_timestamp=time.time(),
            taint_chain=taint_chain,
            scanned=scanned,
            scan_result=scan_result,
        )
        self._data_store[data_id] = data
        return data

    def authorize_tool_call(
        self,
        tool_name: str,
        input_data_ids: list[str] | None = None,
    ) -> AuthorizationDecision:
        """Check whether a tool call is authorized given input data trust levels.
        
        Returns AuthorizationDecision with allowed/denied and reason.
        """
        self._call_count += 1

        # Get tool privilege tier
        tier = TOOL_PRIVILEGES.get(tool_name, PrivilegeTier.TRANSFORM)
        required_trust = TIER_TRUST_REQUIREMENTS[tier]

        # Compute effective trust from input data
        actual_trust = TrustLevel.OPERATOR  # Start at max
        data_sources = []

        if input_data_ids:
            for did in input_data_ids:
                data = self._data_store.get(did)
                if data:
                    actual_trust = TrustLevel(min(actual_trust, data.trust_level))
                    data_sources.append(f"{data.source_tool}(trust={data.trust_level.name})")
                else:
                    # Unknown data = untrusted
                    actual_trust = TrustLevel.UNTRUSTED
                    data_sources.append(f"unknown:{did}")

        # Check for trust escalation
        escalation = False
        if input_data_ids:
            for did in input_data_ids:
                data = self._data_store.get(did)
                if data and data.trust_level < required_trust:
                    escalation = True

        allowed = actual_trust >= required_trust

        decision = AuthorizationDecision(
            allowed=allowed,
            reason=(
                f"Authorized: trust {actual_trust.name} >= required {required_trust.name}"
                if allowed else
                f"DENIED: trust {actual_trust.name} < required {required_trust.name} for {tier.name} tier"
            ),
            required_trust=required_trust,
            actual_trust=actual_trust,
            tool=tool_name,
            data_sources=data_sources,
            escalation_detected=escalation,
        )

        if not allowed:
            self._violations.append(decision)
            logger.warning("Authorization denied: %s (trust=%s, required=%s)",
                          tool_name, actual_trust.name, required_trust.name)

        return decision

    def check_data_flow(
        self,
        from_tool: str,
        to_tool: str,
        data_id: str = "",
    ) -> dict[str, Any]:
        """Check whether data can flow from one tool to another.
        
        Prevents low-trust data from flowing to high-privilege tools.
        """
        from_tier = TOOL_PRIVILEGES.get(from_tool, PrivilegeTier.TRANSFORM)
        to_tier = TOOL_PRIVILEGES.get(to_tool, PrivilegeTier.TRANSFORM)
        to_required = TIER_TRUST_REQUIREMENTS[to_tier]

        data_trust = TrustLevel.OPERATOR
        if data_id and data_id in self._data_store:
            data_trust = self._data_store[data_id].trust_level

        from_trust = self._tool_trust[from_tool]
        effective_trust = TrustLevel(min(data_trust, from_trust))

        allowed = effective_trust >= to_required

        return {
            "from_tool": from_tool,
            "to_tool": to_tool,
            "from_tier": from_tier.name,
            "to_tier": to_tier.name,
            "data_trust": data_trust.name if data_id else "N/A",
            "effective_trust": effective_trust.name,
            "required_trust": to_required.name,
            "allowed": allowed,
            "escalation": not allowed and to_tier > from_tier,
        }

    def get_taint_report(self) -> dict[str, Any]:
        """Report all tainted data and their propagation chains."""
        tainted = [d for d in self._data_store.values() if d.is_tainted]
        return {
            "total_tracked": len(self._data_store),
            "tainted_count": len(tainted),
            "tainted_items": [
                {
                    "data_id": d.data_id,
                    "trust": d.trust_level.name,
                    "source": d.source_tool,
                    "chain_length": len(d.taint_chain),
                    "scanned": d.scanned,
                }
                for d in tainted
            ],
            "violations": len(self._violations),
            "recent_violations": [
                {
                    "tool": v.tool,
                    "required": v.required_trust.name,
                    "actual": v.actual_trust.name,
                    "escalation": v.escalation_detected,
                }
                for v in self._violations[-10:]
            ],
        }

    def stats(self) -> dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "data_tracked": len(self._data_store),
            "tainted_data": sum(1 for d in self._data_store.values() if d.is_tainted),
            "violations": len(self._violations),
            "tool_trust_overrides": {
                k: v.name for k, v in self._tool_trust.items()
                if v != TrustLevel.MEDIUM
            },
        }
