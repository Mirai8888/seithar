"""Shared data types for the Seithar platform."""
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class TechniqueMatch:
    """A single detected cognitive exploitation technique."""
    code: str
    name: str
    confidence: float
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """Result of scanning content for cognitive threats."""
    source: str
    matches: list[TechniqueMatch]
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntelItem:
    """A single intelligence item."""
    title: str
    url: str
    source: str
    summary: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InoculationResult:
    """Result of generating an inoculation."""
    code: str
    technique_name: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
