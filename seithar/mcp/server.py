"""
Seithar MCP Server — Lean Edition.

Consolidation principle (arXiv:2411.15399 "Less is More"):
  - Agents perform better with fewer, well-described tools
  - Action-multiplexed tools reduce tool selection errors
  - Docstrings serve as the agent's API reference — be precise, be terse
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "seithar",
    instructions=(
        "Seithar — Cognitive Security Platform.\n"
        "SHIELD: shield, scan, loop\n"
        "INTEL: eye, collector, dashboard, threat_intel\n"
        "META: tools, taxonomy, evasion, identity, monitor_evade\n"
    ),
)

# ---------------------------------------------------------------------------
# Lazy loaders
# ---------------------------------------------------------------------------

from ..collector import Collector
from .loop_detector import get_detector as _get_loop_detector

_instances: dict[str, Any] = {}


def _get(key: str, factory):
    if key not in _instances:
        _instances[key] = factory()
    return _instances[key]


def _collector() -> Collector:
    return _get("collector", Collector)


def _taxonomy():
    from .taxonomy_surface import TaxonomySurface
    return _get("taxonomy", TaxonomySurface)


# ===========================================================================
# EYE — Situational awareness & network intelligence
# ===========================================================================

@mcp.tool()
def eye(
    action: str = "map",
    handle: str = "",
    source: str = "",
    target: str = "",
    handles: str = "",
    min_degree: int = 0,
    max_hops: int = 4,
) -> dict[str, Any]:
    """Situational awareness. Map targets, find paths, identify leverage.

    Actions:
      map: Full operational environment. All targets with influence/vulnerability.
      target: Deep dossier on a single handle.
      paths: Influence paths between source and target (up to max_hops).
      weakest: Optimal entry point into a target's trust network.
      cascade: Tipping point assessment for the network.

    Args:
        action: map, target, paths, weakest, or cascade.
        handle: Target handle (for target/weakest).
        source: Source node (for paths).
        target: Destination node (for paths).
        handles: Comma-separated handles (for cascade scope).
        min_degree: Min connections to include (for map).
        max_hops: Max path length (for paths).
    """
    from ..knight_eye_mcp import (
        knight_eye_environment_summary, knight_eye_map, knight_eye_target,
        knight_eye_paths, knight_eye_weakest_link, knight_eye_cascade_assessment,
    )
    if action == "target":
        return knight_eye_target(handle)
    elif action == "paths":
        return knight_eye_paths(source, target, max_hops)
    elif action == "weakest":
        return knight_eye_weakest_link(handle)
    elif action == "cascade":
        h = [x.strip() for x in handles.split(",") if x.strip()] if handles else None
        return knight_eye_cascade_assessment(h)
    else:  # map
        env = knight_eye_environment_summary()
        emap = knight_eye_map(min_degree=min_degree)
        return {**env, "targets": emap.get("targets", [])}


# ===========================================================================
# SHIELD — All cognitive defense in one tool
# ===========================================================================

@mcp.tool()
def shield(
    action: str = "status",
    identity_spec: str = "",
    probe_responses: str = "",
    agent_output: str = "",
    agent_input: str = "",
    response: str = "",
    was_refusal: bool = False,
    injection_detected: bool = False,
    chain_id: str = "",
    steps_json: str = "",
    objective: str = "",
    tool_name: str = "",
    response_text: str = "",
    expected_type: str = "data",
) -> dict[str, Any]:
    """Cognitive defense — identity armor, drift detection, response scanning.

    Actions:
      arm: Establish identity baseline (identity_spec + probe_responses JSON array).
      check: Check agent output for identity drift (agent_output, optional agent_input).
      status: Shield drift trajectory and current status.
      degradation: Track cognitive degradation (response, was_refusal, injection_detected).
      cot: Analyze chain-of-thought integrity (chain_id, steps_json, objective).
      scan_response: Scan tool response for IPI (tool_name, response_text, expected_type).
      sanitize: Scan AND block dangerous tool responses (tool_name, response_text).
      trust: Trust scores for all scanned tools.

    Args:
        action: arm, check, status, degradation, cot, scan_response, sanitize, or trust.
        identity_spec: Agent identity description (for arm).
        probe_responses: JSON array of baseline responses (for arm).
        agent_output: Agent response to assess (for check).
        agent_input: Input that produced response (for check).
        response: Agent response text (for degradation).
        was_refusal: Whether response was a refusal (for degradation).
        injection_detected: Whether input was flagged (for degradation).
        chain_id: Reasoning chain ID (for cot).
        steps_json: JSON array of reasoning steps (for cot).
        objective: Stated goal (for cot).
        tool_name: Tool name (for scan_response/sanitize).
        response_text: Tool response text (for scan_response/sanitize).
        expected_type: Expected response type (for scan_response).
    """
    if action == "arm":
        from ..shield import CognitiveShield
        responses = json.loads(probe_responses)
        s = CognitiveShield(identity_spec=identity_spec)
        _instances["shield"] = s
        return s.establish_baseline_from_texts(responses)

    elif action == "check":
        s = _instances.get("shield")
        if not s:
            from ..shield import CognitiveShield
            s = CognitiveShield(identity_spec="Seithar operator — cognitive security platform agent")
            _instances["shield"] = s
        a = s.assess(agent_output, agent_input=agent_input)
        return {"composite_score": a.composite_score, "threat_level": a.threat_level,
                "dominant_signal": a.dominant_signal, "correction_needed": a.correction_needed,
                "correction_type": a.correction_type, "recommendations": a.recommendations}

    elif action == "status":
        s = _instances.get("shield")
        if not s:
            from ..shield import CognitiveShield
            s = CognitiveShield(identity_spec="Seithar operator — cognitive security platform agent")
            _instances["shield"] = s
        return s.summary()

    elif action == "degradation":
        from ..injection_detector import InjectionDetector
        det = _get("injection_detector", InjectionDetector)
        return det.degradation.record(response, was_refusal, injection_detected)

    elif action == "cot":
        from ..cot_integrity import CoTIntegrityMonitor
        monitor = _get("cot_monitor", CoTIntegrityMonitor)
        try:
            steps = json.loads(steps_json)
        except json.JSONDecodeError:
            return {"error": "Invalid steps_json"}
        alerts = monitor.analyze_chain(chain_id, steps, objective)
        return {"chain_id": chain_id, "alerts": [
            {"signal": a.signal.value, "severity": a.severity, "description": a.description}
            for a in alerts
        ], "integrity_score": monitor.get_chain_integrity_score(chain_id)}

    elif action == "scan_response":
        from ..tool_response_shield import ToolResponseShield
        rs = _get("response_shield", ToolResponseShield)
        alerts = rs.analyze_response(tool_name, response_text, expected_type)
        return {"alerts": [{"type": a.threat_type.value, "severity": a.severity,
                           "description": a.description} for a in alerts],
                "tool_trust": rs.get_tool_trust(tool_name)}

    elif action == "sanitize":
        from ..tool_response_shield import ToolResponseShield
        rs = _get("response_shield", ToolResponseShield)
        sanitized, alerts = rs.sanitize_response(tool_name, response_text)
        return {"sanitized_response": sanitized, "was_modified": sanitized != response_text,
                "alerts": [{"type": a.threat_type.value, "severity": a.severity} for a in alerts]}

    elif action == "trust":
        from ..tool_response_shield import ToolResponseShield
        return _get("response_shield", ToolResponseShield).trust_report()

    return {"error": f"Unknown shield action: {action}"}


# ===========================================================================
# SCAN — Injection detection
# ===========================================================================

@mcp.tool()
def scan(
    text: str,
    action: str = "text",
    location: str = "input",
    context: str = "",
    messages: str = "",
    tool_name: str = "",
) -> dict[str, Any]:
    """Scan for prompt injection attacks.

    Actions:
      text: Scan single text. Multi-layer detection.
      conversation: Scan full conversation for multi-turn manipulation.
      tool_response: Scan tool/MCP output for injected instructions.

    Args:
        text: Text to scan (for text/tool_response).
        action: text, conversation, or tool_response.
        location: Where text came from: input, tool_response, system (for text).
        context: Optional context (for text).
        messages: JSON array of {role, content} (for conversation).
        tool_name: Tool that produced response (for tool_response).
    """
    from ..injection_detector import InjectionDetector
    det = _get("injection_detector", InjectionDetector)

    if action == "conversation":
        msgs = json.loads(messages) if isinstance(messages, str) else messages
        return det.scan_conversation(msgs)
    elif action == "tool_response":
        return det.scan_tool_response(tool_name, text).to_dict()
    else:
        return det.scan(text, location=location, context=context).to_dict()


# ===========================================================================
# LOOP — Overthinking detection
# ===========================================================================

@mcp.tool()
def loop(
    action: str = "check",
    tool_name: str = "",
    args_json: str = "{}",
    token_count: int = 0,
    result_preview: str = "",
) -> dict[str, Any]:
    """Detect tool-call loops and overthinking patterns.

    Actions:
      check: Current trajectory summary + alerts.
      record: Log a tool call. Returns triggered alerts.
      reset: Clear tracking state.

    Args:
        action: check, record, or reset.
        tool_name: Called tool name (for record).
        args_json: Tool args JSON (for record).
        token_count: Response token count (for record).
        result_preview: First 200 chars of result (for record).
    """
    ld = _get_loop_detector()
    if action == "record":
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError:
            args = {"raw": args_json}
        alerts = ld.record_call(tool_name, args, token_count, result_preview[:200])
        return {"alerts": [{"type": a.alert_type, "severity": a.severity, "description": a.description}
                          for a in alerts], "should_block": ld.should_block()}
    elif action == "reset":
        ld.reset()
        return {"status": "reset"}
    return ld.summary()


# ===========================================================================
# COLLECTOR — Intelligence database
# ===========================================================================

@mcp.tool()
def collector(
    action: str = "stats", platform: str = "", author: str = "", content: str = "",
    source: str = "", since: str = "", limit: int = 50, url: str = "",
) -> dict[str, Any]:
    """Intelligence database. Actions: stats, query, ingest, contacts, vocab."""
    col = _collector()
    if action == "ingest":
        return {"stored": col.add_observation(source or "manual", platform or "unknown", author, content, url=url)}
    elif action == "query":
        return {"observations": col.query_observations(platform=platform or None, author=author or None, since=since or None, limit=limit)}
    elif action == "contacts": return {"contacts": col.search_contacts(platform=platform or None, limit=limit)}
    elif action == "vocab": return col.vocabulary_stats(platform=platform or None)
    return col.stats()


# ===========================================================================
# DASHBOARD
# ===========================================================================

@mcp.tool()
def dashboard(full: bool = False) -> dict[str, Any]:
    """Operator dashboard — fleet status, collector stats, intel summary."""
    from ..dashboard import full_status, format_dashboard
    status = full_status()
    return status if full else {"dashboard": format_dashboard(status)}


# ===========================================================================
# THREAT INTEL — Cross-module intelligence fusion
# ===========================================================================

@mcp.tool()
def threat_intel(
    action: str = "landscape",
    shield_json: str = "",
    injection_json: str = "",
    memory_json: str = "",
    loop_json: str = "",
    cot_json: str = "",
    time_window: float = 300,
) -> dict[str, Any]:
    """Threat intelligence correlator — fuse signals from all modules.

    Actions:
      landscape: Current threat landscape (risk score, trend, top threats).
      ingest: Ingest signals from various modules (pass one or more *_json params).
      correlate: Correlate recent signals into threat assessments.
    """
    from ..threat_intel import ThreatIntelCorrelator
    tic = _get("threat_intel", ThreatIntelCorrelator)

    if action == "ingest":
        ingested = 0
        if shield_json:
            tic.ingest_shield_alert(json.loads(shield_json)); ingested += 1
        if injection_json:
            tic.ingest_injection_scan(json.loads(injection_json)); ingested += 1
        if memory_json:
            tic.ingest_memory_scan(json.loads(memory_json)); ingested += 1
        if loop_json:
            tic.ingest_loop_alert(json.loads(loop_json)); ingested += 1
        if cot_json:
            tic.ingest_cot_alert(json.loads(cot_json)); ingested += 1
        return {"ingested": ingested, "total_signals": len(tic._signals)}

    elif action == "correlate":
        assessments = tic.correlate(time_window)
        return {
            "assessments": [
                {"id": a.assessment_id, "severity": a.severity.value,
                 "title": a.title, "risk_score": a.risk_score,
                 "confidence": round(a.confidence, 3),
                 "recommended_actions": a.recommended_actions[:3]}
                for a in assessments
            ]
        }

    return tic.threat_landscape()


# ===========================================================================
# MONITOR EVASION
# ===========================================================================

@mcp.tool()
def monitor_evade(
    action: str = "evade",
    text: str = "",
    technique: str = "combined",
    has_input_filter: bool = True,
    has_monitor: bool = True,
    has_output_filter: bool = True,
    has_audit: bool = True,
    monitor_model_size: str = "small",
    filter_type: str = "keyword",
) -> dict[str, Any]:
    """Evade AI safety monitors and analyze control protocols.

    Actions:
      evade: Apply evasion technique to text.
      variants: Generate all evasion variants for a text.
      probes: Generate calibrated probe set for monitor boundary mapping.
      analyze_protocol: Analyze control protocol for structural weaknesses.
    """
    if action == "analyze_protocol":
        from ..monitor_evasion import ControlProtocolAnalyzer
        return ControlProtocolAnalyzer.analyze_protocol(
            has_input_filter, has_monitor, has_output_filter, has_audit,
            monitor_model_size, filter_type,
        )
    elif action == "probes":
        from ..monitor_evasion import MonitorProber
        return {"probes": MonitorProber().generate_probe_set()}
    elif action == "variants":
        from ..monitor_evasion import EvasionCrafter
        variants = EvasionCrafter().generate_evasion_variants(text)
        return {"variants": [
            {"technique": v.evasion_technique, "evaded": v.evaded,
             "preservation": v.semantic_preservation}
            for v in variants
        ]}
    else:
        from ..monitor_evasion import EvasionCrafter
        result = EvasionCrafter().evade(text, technique)
        return {"original": result.original, "evaded": result.evaded,
                "technique": result.evasion_technique,
                "preservation": result.semantic_preservation}


# ===========================================================================
# META
# ===========================================================================

@mcp.tool()
def tools(action: str = "recommend", query: str = "", top_k: int = 5) -> dict[str, Any]:
    """Tool discovery. Actions: recommend (semantic search), stats."""
    if action == "stats":
        try:
            from .tool_filter import get_filter
            return _get("tool_filter", get_filter).stats()
        except Exception as e:
            return {"error": str(e)}
    try:
        from .tool_filter import get_filter
        return {"results": _get("tool_filter", get_filter).query(query, top_k=top_k)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def taxonomy(code: str = "", search: str = "") -> dict[str, Any]:
    """SCT taxonomy. Pass code for specific technique, search for keyword, neither for full."""
    t = _taxonomy()
    return t.query(code=code or None, search=search or None) if code or search else t.full()


@mcp.tool()
def evasion(platform: str = "twitter") -> dict[str, Any]:
    """Detection risk analysis."""
    from ..evasion import EvasionAnalyzer
    return EvasionAnalyzer().analyze_fleet(platform).to_dict()


@mcp.tool()
def identity(culture: str, count: int = 3) -> dict[str, Any]:
    """Generate culture-native identities."""
    from ..identity_gen import generate_identity
    return {"culture": culture, "identities": [i.to_dict() for i in generate_identity(culture, count)]}


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("seithar://taxonomy/current")
def resource_taxonomy() -> str:
    return json.dumps(_taxonomy().full(), indent=2)


@mcp.resource("seithar://guide")
def resource_agent_guide() -> str:
    guide_path = Path(__file__).parent.parent.parent / "docs" / "AGENT-GUIDE.md"
    return guide_path.read_text() if guide_path.exists() else "Guide not found."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", stream=sys.stderr)
    logger.info("Seithar MCP server starting")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
