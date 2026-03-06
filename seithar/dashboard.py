"""
Operator Dashboard — fleet overview and command surface.

Produces structured status reports for the operator.
This is the "bot manager" view -- see everything, command anything.

Usage:
    python3 -m seithar.dashboard
    python3 -m seithar.dashboard --full
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .orchestrator import Orchestrator
from .collector import Collector
from .bot_runtime import Phase


def fleet_overview() -> dict:
    """High-level fleet status for operator."""
    orch = Orchestrator()
    fleet = orch.fleet_status()

    instances = []
    for inst in fleet["instances"]:
        runtime_config = inst.get("metrics", {}).get("_runtime_config", {})
        last_cycle = inst.get("metrics", {}).get("last_cycle", {})
        instances.append({
            "id": inst["instance_id"],
            "persona": inst["persona_id"][:12],
            "platform": inst["platform"],
            "status": inst["status"],
            "phase": runtime_config.get("phase", "unknown"),
            "targets": runtime_config.get("targets", []),
            "last_observed": last_cycle.get("observed", 0),
            "last_heartbeat": inst.get("last_heartbeat", "never"),
        })

    return {
        "total": fleet["total"],
        "active": fleet["active"],
        "by_phase": _count_by(instances, "phase"),
        "by_platform": _count_by(instances, "platform"),
        "by_status": _count_by(instances, "status"),
        "instances": instances,
    }


def collector_overview() -> dict:
    """Collector DB stats for operator."""
    collector = Collector()
    stats = collector.stats()
    return stats


def intelligence_summary() -> dict:
    """Summary of collected intelligence."""
    collector = Collector()

    # Top contacts by observation count
    top_contacts = collector.search_contacts(limit=10)

    # Vocabulary stats
    vocab = collector.vocabulary_stats()

    # Recent observations
    recent = collector.query_observations(limit=5)

    return {
        "top_contacts": [
            {"handle": c["handle"], "platform": c["platform"]}
            for c in top_contacts
        ],
        "vocabulary": vocab,
        "recent_observations": len(recent),
    }


def full_status() -> dict:
    """Complete operator dashboard."""
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fleet": fleet_overview(),
        "collector": collector_overview(),
        "intelligence": intelligence_summary(),
    }


def _count_by(items: list[dict], key: str) -> dict:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


def format_dashboard(status: dict) -> str:
    """Format dashboard for text output."""
    fleet = status["fleet"]
    collector = status["collector"]
    intel = status["intelligence"]

    lines = [
        "=" * 56,
        "  SEITHAR FLEET COMMAND",
        f"  {status['timestamp']}",
        "=" * 56,
        "",
        f"  FLEET: {fleet['active']}/{fleet['total']} active",
    ]

    if fleet["by_phase"]:
        phases = " | ".join(f"{k}: {v}" for k, v in fleet["by_phase"].items())
        lines.append(f"  Phases: {phases}")
    if fleet["by_platform"]:
        plats = " | ".join(f"{k}: {v}" for k, v in fleet["by_platform"].items())
        lines.append(f"  Platforms: {plats}")

    lines.append("")

    for inst in fleet["instances"]:
        phase_icon = {
            "lurk": "👁",
            "light": "💬",
            "full": "⚡",
            "dormant": "💤",
            "burned": "🔥",
        }.get(inst["phase"], "❓")
        targets_str = ", ".join(inst["targets"][:3]) if inst["targets"] else "none"
        lines.append(
            f"  {phase_icon} {inst['id'][:20]:<20} "
            f"{inst['platform']:<10} {inst['phase']:<8} "
            f"obs:{inst['last_observed']:<4} targets: {targets_str}"
        )

    lines.extend([
        "",
        "  COLLECTOR:",
        f"    Observations: {collector.get('observations', 0)}",
        f"    Contacts: {collector.get('contacts', 0)}",
        f"    Edges: {collector.get('edges', 0)}",
        f"    Vocab signals: {collector.get('vocabulary_signals', 0)}",
        "",
        f"  INTELLIGENCE:",
        f"    Vocab hits: {intel['vocabulary'].get('total_signals', 0)}",
        f"    Unique terms: {intel['vocabulary'].get('unique_terms', 0)}",
        f"    Top targets: {', '.join(c['handle'] for c in intel['top_contacts'][:5]) or 'none'}",
        "",
        "=" * 56,
    ])

    return "\n".join(lines)


def main():
    full = "--full" in sys.argv
    status = full_status()

    if full:
        print(json.dumps(status, indent=2, default=str))
    else:
        print(format_dashboard(status))


if __name__ == "__main__":
    main()
