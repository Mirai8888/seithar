"""
Seithar Cognitive Defense Taxonomy — Single Source of Truth.

SCT-001 through SCT-012: canonical definitions of cognitive exploitation
techniques mapped to cyber and cognitive analogs.

Canonical source: taxonomy.json at repo root (synced from seithar-cogdef).
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SCTechnique:
    """A single cognitive exploitation technique."""
    code: str
    name: str
    description: str


SCT_TAXONOMY: dict[str, SCTechnique] = {
    "SCT-001": SCTechnique("SCT-001", "Emotional Hijacking", "Exploiting affective processing to bypass rational evaluation."),
    "SCT-002": SCTechnique("SCT-002", "Information Asymmetry Exploitation", "Leveraging what the target does not know."),
    "SCT-003": SCTechnique("SCT-003", "Authority Fabrication", "Manufacturing trust signals the source does not legitimately possess."),
    "SCT-004": SCTechnique("SCT-004", "Social Proof Manipulation", "Weaponizing herd behavior and conformity instincts."),
    "SCT-005": SCTechnique("SCT-005", "Identity Targeting", "Attacks calibrated to the target's self-concept and group affiliations."),
    "SCT-006": SCTechnique("SCT-006", "Temporal Manipulation", "Exploiting time pressure, temporal context, or scheduling."),
    "SCT-007": SCTechnique("SCT-007", "Recursive Infection", "Self-replicating patterns where the target becomes the vector."),
    "SCT-008": SCTechnique("SCT-008", "Direct Substrate Intervention", "Physical/electrical modification of neural hardware bypassing informational processing."),
    "SCT-009": SCTechnique("SCT-009", "Chemical Substrate Disruption", "Pharmacological modification of neurochemical operating environment."),
    "SCT-010": SCTechnique("SCT-010", "Sensory Channel Manipulation", "Exploiting perceptual processing through sensory overload or deprivation."),
    "SCT-011": SCTechnique("SCT-011", "Trust Infrastructure Destruction", "Systematic dismantling of epistemic trust networks."),
    "SCT-012": SCTechnique("SCT-012", "Commitment Escalation & Self-Binding", "Engineering progressive commitment that becomes self-reinforcing."),
}

SEVERITY_LABELS: dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}


def get_technique(code: str) -> SCTechnique | None:
    """Look up a technique by SCT code. Returns None if not found."""
    return SCT_TAXONOMY.get(code)


def list_techniques() -> list[SCTechnique]:
    """Return all techniques as a list."""
    return list(SCT_TAXONOMY.values())


def validate_taxonomy() -> bool:
    """Validate taxonomy integrity. Returns True if valid."""
    codes = set()
    for code, tech in SCT_TAXONOMY.items():
        assert code == tech.code, f"Key {code} != technique code {tech.code}"
        assert code not in codes, f"Duplicate code {code}"
        codes.add(code)
    expected = {f"SCT-{i:03d}" for i in range(1, 13)}
    assert codes == expected, f"Missing or extra codes: {codes ^ expected}"
    return True
