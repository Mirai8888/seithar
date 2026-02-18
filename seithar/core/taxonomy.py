"""
Seithar Cognitive Defense Taxonomy — Single Source of Truth.

SCT-001 through SCT-012: canonical definitions of cognitive exploitation
techniques mapped to cyber and cognitive analogs.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SCTechnique:
    """A single cognitive exploitation technique."""
    code: str
    name: str
    description: str


SCT_TAXONOMY: dict[str, SCTechnique] = {
    "SCT-001": SCTechnique("SCT-001", "Narrative Injection", "Insertion of false or misleading narratives into information streams to shape perception."),
    "SCT-002": SCTechnique("SCT-002", "Emotional Amplification", "Deliberate amplification of emotional content to override rational analysis."),
    "SCT-003": SCTechnique("SCT-003", "Authority Spoofing", "Impersonation or fabrication of authoritative sources to lend false credibility."),
    "SCT-004": SCTechnique("SCT-004", "Consensus Manufacturing", "Creation of artificial consensus through coordinated inauthentic behavior."),
    "SCT-005": SCTechnique("SCT-005", "Identity Fragmentation", "Exploitation of identity-group divisions to weaken collective coherence."),
    "SCT-006": SCTechnique("SCT-006", "Attention Hijacking", "Redirection of public attention away from critical issues toward decoys."),
    "SCT-007": SCTechnique("SCT-007", "Trust Erosion", "Systematic degradation of trust in institutions, media, or interpersonal relationships."),
    "SCT-008": SCTechnique("SCT-008", "Cognitive Overload", "Flooding targets with contradictory or excessive information to induce paralysis."),
    "SCT-009": SCTechnique("SCT-009", "Memetic Weaponization", "Packaging exploitative content in viral memetic formats for rapid spread."),
    "SCT-010": SCTechnique("SCT-010", "Temporal Manipulation", "Exploiting timing — urgency, delay, or synchronization — to maximize cognitive impact."),
    "SCT-011": SCTechnique("SCT-011", "Platform Exploitation", "Abuse of platform algorithms and affordances to amplify cognitive attacks."),
    "SCT-012": SCTechnique("SCT-012", "Epistemic Closure", "Sealing targets within self-reinforcing information environments that resist correction."),
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
