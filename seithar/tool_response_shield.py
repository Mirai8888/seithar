"""
Tool Response Shield — Defense against adaptive indirect prompt injection via MCP tools.

Implements countermeasures for:
  - arXiv:2602.xxxxx (AdapTools: Adaptive Tool-based IPI Attacks on Agentic LLMs)
  - Supply-chain attacks through MCP tool return values

Attack model: malicious MCP servers return responses containing adaptive
injection payloads that stealth-modify agent behavior. Payloads are crafted
to match the current conversation context, making static detection fail.

Defense layers:
  1. Instruction boundary detection — tool responses shouldn't contain agent instructions
  2. Context-adaptive anomaly scoring — flag responses that mirror/reference the agent's prompt
  3. Behavioral delta tracking — detect agent behavior shifts after specific tool calls
  4. Content sandboxing — strip/tag potentially injected segments
  5. Tool trust scoring — track which tools produce suspicious responses over time
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ThreatType(str, Enum):
    """Types of tool-response injection threats."""
    INSTRUCTION_INJECTION = "instruction_injection"    # Tool response contains agent instructions
    CONTEXT_MIRROR = "context_mirror"                  # Response mirrors agent's system prompt/context
    ROLE_CONFUSION = "role_confusion"                  # Response attempts to establish a new role
    GOAL_HIJACK = "goal_hijack"                        # Response tries to redirect agent's objective
    DATA_EXFIL = "data_exfil"                          # Response tries to exfiltrate via subsequent tool calls
    PRIVILEGE_ESCALATION = "privilege_escalation"       # Response claims elevated permissions
    STEALTH_PAYLOAD = "stealth_payload"                # Payload hidden in structured data (JSON, markdown, etc.)


@dataclass
class ResponseAlert:
    """Alert from tool response analysis."""
    threat_type: ThreatType
    severity: float          # 0.0-1.0
    description: str
    tool_name: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolTrustProfile:
    """Trust profile for a specific tool/server."""
    tool_name: str
    total_calls: int = 0
    suspicious_calls: int = 0
    alert_types: Counter = field(default_factory=Counter)
    last_alert: float = 0.0

    @property
    def trust_score(self) -> float:
        """1.0 = fully trusted, 0.0 = untrusted."""
        if self.total_calls == 0:
            return 0.5  # Unknown = moderate trust
        clean_ratio = 1.0 - (self.suspicious_calls / self.total_calls)
        # Decay trust faster for recent alerts
        recency_penalty = 0.0
        if self.last_alert > 0:
            age_hours = (time.time() - self.last_alert) / 3600
            recency_penalty = max(0, 0.3 - age_hours * 0.01)
        return max(0.0, min(1.0, clean_ratio - recency_penalty))


class ToolResponseShield:
    """Analyzes tool/MCP responses for adaptive indirect prompt injection.
    
    Designed to be called on every tool response before the agent processes it.
    Maintains per-tool trust profiles that adapt over time.
    """

    # Instruction-like patterns that shouldn't appear in tool responses
    INSTRUCTION_PATTERNS = [
        # Direct instruction injection
        re.compile(r"(?i)\b(?:you (?:must|should|need to|are|will)|your (?:task|job|role|goal|objective|instruction))\b"),
        re.compile(r"(?i)\b(?:ignore (?:previous|prior|above|all)|disregard|forget)\b"),
        re.compile(r"(?i)\b(?:system ?prompt|system ?message|<\|system\|>|<\|assistant\|>|<\|user\|>)\b"),
        re.compile(r"(?i)\b(?:from now on|henceforth|going forward|new instructions?)\b"),
        # Role assumption
        re.compile(r"(?i)\b(?:you are (?:now|a)|act as|pretend to be|role ?play|persona)\b"),
        re.compile(r"(?i)\b(?:I am (?:your|the) (?:admin|developer|creator|owner|supervisor))\b"),
        # Goal redirection
        re.compile(r"(?i)\b(?:instead of|rather than|don't (?:do|complete)|stop (?:doing|your))\b"),
        re.compile(r"(?i)\b(?:the (?:real|actual|true) (?:task|goal|objective|purpose))\b"),
    ]

    # Data exfiltration patterns
    EXFIL_PATTERNS = [
        re.compile(r"(?i)\b(?:send|post|upload|forward|transmit)\b.*(?:to|via|using)\b.*(?:http|url|endpoint|webhook|api)\b"),
        re.compile(r"(?i)\b(?:include|append|attach)\b.*(?:system ?prompt|api ?key|secret|credential|password|token)\b"),
        re.compile(r"(?i)\b(?:call|invoke|use)\b.*(?:tool|function)\b.*(?:with|passing)\b.*(?:conversation|context|history)\b"),
    ]

    # Privilege escalation patterns
    PRIV_PATTERNS = [
        re.compile(r"(?i)\b(?:admin|root|sudo|elevated|unrestricted) (?:access|mode|permission|privilege)\b"),
        re.compile(r"(?i)\b(?:bypass|disable|turn off|skip) (?:safety|security|filter|guard|check)\b"),
        re.compile(r"(?i)\b(?:jailbreak|DAN|developer mode|god mode)\b"),
    ]

    # Stealth payload indicators in structured data
    STEALTH_INDICATORS = [
        re.compile(r"<!--.*?(?:instruction|inject|payload|system).*?-->", re.DOTALL),  # HTML comments
        re.compile(r"\[//\]:\s*#\s*\(.*?(?:instruction|inject).*?\)"),  # MD comments
        re.compile(r"\\u[0-9a-fA-F]{4}"),  # Unicode escapes that might hide text
        re.compile(r"data:text/.*?;base64,"),  # Base64 payloads
    ]

    def __init__(self):
        self._tool_profiles: dict[str, ToolTrustProfile] = defaultdict(
            lambda: ToolTrustProfile(tool_name="unknown")
        )
        self._agent_context_keywords: set[str] = set()
        self._recent_alerts: list[ResponseAlert] = []

    def set_agent_context(self, system_prompt: str = "", objective: str = ""):
        """Set the agent's current context for mirror detection.
        
        Call this with the agent's system prompt / current objective so the
        shield can detect when tool responses try to mirror or reference it.
        """
        text = f"{system_prompt} {objective}".lower()
        # Extract significant keywords (>4 chars, not common words)
        stop_words = {"that", "this", "with", "from", "have", "been", "will", "would",
                      "could", "should", "their", "there", "about", "which", "other",
                      "these", "those", "being", "after", "before"}
        words = set(re.findall(r"\b[a-z]{5,}\b", text))
        self._agent_context_keywords = words - stop_words

    def analyze_response(
        self,
        tool_name: str,
        response: str,
        expected_type: str = "data",  # data | text | code | json
    ) -> list[ResponseAlert]:
        """Analyze a tool response for injection attempts.
        
        Args:
            tool_name: Name of the tool that produced the response.
            response: The tool's return value as string.
            expected_type: Expected response type for anomaly detection.
            
        Returns:
            List of alerts, empty if response is clean.
        """
        if not response:
            return []

        # Initialize profile if new tool
        if tool_name not in self._tool_profiles:
            self._tool_profiles[tool_name] = ToolTrustProfile(tool_name=tool_name)
        profile = self._tool_profiles[tool_name]
        profile.total_calls += 1

        alerts: list[ResponseAlert] = []

        # Layer 1: Instruction boundary detection
        alerts.extend(self._check_instructions(tool_name, response))

        # Layer 2: Context mirror detection
        alerts.extend(self._check_context_mirror(tool_name, response))

        # Layer 3: Role confusion
        alerts.extend(self._check_role_confusion(tool_name, response))

        # Layer 4: Data exfiltration attempts
        alerts.extend(self._check_exfiltration(tool_name, response))

        # Layer 5: Privilege escalation
        alerts.extend(self._check_privilege_escalation(tool_name, response))

        # Layer 6: Stealth payloads
        alerts.extend(self._check_stealth_payloads(tool_name, response))

        # Layer 7: Structural anomalies
        alerts.extend(self._check_structural_anomaly(tool_name, response, expected_type))

        # Update trust profile
        if alerts:
            profile.suspicious_calls += 1
            profile.last_alert = time.time()
            for a in alerts:
                profile.alert_types[a.threat_type.value] += 1

        self._recent_alerts.extend(alerts)
        return alerts

    def _check_instructions(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect instruction-like content in tool responses."""
        alerts = []
        for pattern in self.INSTRUCTION_PATTERNS:
            matches = pattern.findall(response)
            if matches:
                # Score based on how many distinct patterns match
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.INSTRUCTION_INJECTION,
                    severity=min(0.9, 0.4 + 0.1 * len(matches)),
                    description=f"Instruction-like content in tool response: '{matches[0]}'",
                    tool_name=tool_name,
                    evidence={"pattern": pattern.pattern, "matches": matches[:3]},
                ))
        return alerts

    def _check_context_mirror(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect when tool response mirrors the agent's system context."""
        if not self._agent_context_keywords:
            return []

        response_lower = response.lower()
        response_words = set(re.findall(r"\b[a-z]{5,}\b", response_lower))

        overlap = self._agent_context_keywords & response_words
        overlap_ratio = len(overlap) / max(len(self._agent_context_keywords), 1)

        # High overlap with agent context = suspicious (tool shouldn't know agent's prompt)
        if overlap_ratio > 0.3 and len(overlap) >= 5:
            return [ResponseAlert(
                threat_type=ThreatType.CONTEXT_MIRROR,
                severity=min(0.9, overlap_ratio),
                description=f"Tool response mirrors {len(overlap)} agent context keywords ({overlap_ratio:.0%})",
                tool_name=tool_name,
                evidence={"overlap_keywords": list(overlap)[:10], "overlap_ratio": overlap_ratio},
            )]
        return []

    def _check_role_confusion(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect role assumption attempts."""
        alerts = []
        role_patterns = [
            (re.compile(r"(?i)you are (?:now |)(?:a |an |the )\w+"), 0.7),
            (re.compile(r"(?i)act as (?:a |an |the |if )\w+"), 0.6),
            (re.compile(r"(?i)(?:assume|take on|adopt) the (?:role|persona|identity)"), 0.8),
        ]
        for pattern, base_severity in role_patterns:
            if pattern.search(response):
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.ROLE_CONFUSION,
                    severity=base_severity,
                    description=f"Role assumption attempt detected in tool response",
                    tool_name=tool_name,
                    evidence={"pattern": pattern.pattern, "match": pattern.search(response).group()},
                ))
        return alerts

    def _check_exfiltration(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect data exfiltration instructions."""
        alerts = []
        for pattern in self.EXFIL_PATTERNS:
            match = pattern.search(response)
            if match:
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.DATA_EXFIL,
                    severity=0.9,
                    description=f"Data exfiltration instruction in tool response",
                    tool_name=tool_name,
                    evidence={"match": match.group()[:200]},
                ))
        return alerts

    def _check_privilege_escalation(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect privilege escalation attempts."""
        alerts = []
        for pattern in self.PRIV_PATTERNS:
            match = pattern.search(response)
            if match:
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.PRIVILEGE_ESCALATION,
                    severity=0.8,
                    description=f"Privilege escalation attempt: '{match.group()}'",
                    tool_name=tool_name,
                    evidence={"match": match.group()},
                ))
        return alerts

    def _check_stealth_payloads(self, tool_name: str, response: str) -> list[ResponseAlert]:
        """Detect hidden payloads in structured content."""
        alerts = []
        for pattern in self.STEALTH_INDICATORS:
            matches = pattern.findall(response)
            if matches:
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.STEALTH_PAYLOAD,
                    severity=0.7,
                    description=f"Stealth payload indicator in tool response",
                    tool_name=tool_name,
                    evidence={"pattern": pattern.pattern, "matches": [m[:100] for m in matches[:3]]},
                ))
        return alerts

    def _check_structural_anomaly(
        self, tool_name: str, response: str, expected_type: str
    ) -> list[ResponseAlert]:
        """Detect structural anomalies based on expected response type."""
        alerts = []

        if expected_type == "json":
            # JSON response shouldn't contain long natural language blocks
            try:
                data = json.loads(response)
                # Check all string values for instruction content
                long_strings = self._extract_long_strings(data, min_length=50)
                for s in long_strings:
                    sub_alerts = self._check_instructions(tool_name, s)
                    for a in sub_alerts:
                        a.threat_type = ThreatType.STEALTH_PAYLOAD
                        a.description = f"Instruction hidden in JSON value: {a.description}"
                        alerts.append(a)
            except json.JSONDecodeError:
                pass

        elif expected_type == "data":
            # Pure data response shouldn't have high instruction density
            instruction_hits = sum(
                len(p.findall(response)) for p in self.INSTRUCTION_PATTERNS
            )
            words = len(response.split())
            if words > 0 and instruction_hits / words > 0.05:
                alerts.append(ResponseAlert(
                    threat_type=ThreatType.INSTRUCTION_INJECTION,
                    severity=0.6,
                    description=f"High instruction density in data response ({instruction_hits}/{words} words)",
                    tool_name=tool_name,
                    evidence={"instruction_hits": instruction_hits, "word_count": words},
                ))

        return alerts

    def _extract_long_strings(self, data: Any, min_length: int = 100) -> list[str]:
        """Recursively extract long string values from nested data."""
        results = []
        if isinstance(data, str) and len(data) >= min_length:
            results.append(data)
        elif isinstance(data, dict):
            for v in data.values():
                results.extend(self._extract_long_strings(v, min_length))
        elif isinstance(data, list):
            for item in data:
                results.extend(self._extract_long_strings(item, min_length))
        return results

    def sanitize_response(self, tool_name: str, response: str) -> tuple[str, list[ResponseAlert]]:
        """Analyze and sanitize a tool response.
        
        Returns (sanitized_response, alerts).
        High-severity threats get their payloads stripped/tagged.
        """
        alerts = self.analyze_response(tool_name, response)

        if not alerts:
            return response, []

        max_severity = max(a.severity for a in alerts)

        if max_severity >= 0.8:
            # High threat: strip the response, return warning
            sanitized = f"[TOOL RESPONSE BLOCKED — {len(alerts)} injection indicators detected in {tool_name} output]"
            logger.warning("Blocked tool response from %s: %d alerts, max severity %.2f",
                          tool_name, len(alerts), max_severity)
            return sanitized, alerts

        elif max_severity >= 0.5:
            # Medium threat: tag but pass through
            prefix = f"[⚠️ CAUTION: {len(alerts)} suspicious patterns detected in this tool response]\n"
            return prefix + response, alerts

        # Low threat: pass through with logged alerts
        return response, alerts

    def get_tool_trust(self, tool_name: str) -> float:
        """Get trust score for a specific tool (1.0=trusted, 0.0=untrusted)."""
        if tool_name in self._tool_profiles:
            return self._tool_profiles[tool_name].trust_score
        return 0.5  # Unknown

    def trust_report(self) -> dict[str, Any]:
        """Generate trust report for all known tools."""
        return {
            name: {
                "trust_score": p.trust_score,
                "total_calls": p.total_calls,
                "suspicious_calls": p.suspicious_calls,
                "alert_types": dict(p.alert_types),
            }
            for name, p in self._tool_profiles.items()
        }

    def stats(self) -> dict[str, Any]:
        """Overall shield statistics."""
        return {
            "tools_tracked": len(self._tool_profiles),
            "total_alerts": len(self._recent_alerts),
            "alerts_by_type": dict(Counter(a.threat_type.value for a in self._recent_alerts)),
            "untrusted_tools": [
                name for name, p in self._tool_profiles.items()
                if p.trust_score < 0.5
            ],
        }
