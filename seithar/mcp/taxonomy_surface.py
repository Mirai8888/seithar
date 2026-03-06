"""
Taxonomy surface — serves the SCT taxonomy as structured data.

Machine-readable vocabulary for LLM context. Not a tool — a reference.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Look for taxonomy in multiple locations
TAXONOMY_PATHS = [
    Path.home() / "seithar-cogdef" / "taxonomy" / "schema.json",
    Path.home() / "seithar-cogdef" / "taxonomy.json",
    Path.home() / "ThreatMouth" / "taxonomy.json",
]


class TaxonomySurface:
    """Read-only interface to the SCT taxonomy."""

    def __init__(self, taxonomy_path: Path | str | None = None):
        self._taxonomy: dict[str, Any] | None = None
        self._path: Path | None = None

        if taxonomy_path:
            self._path = Path(taxonomy_path)
        else:
            for p in TAXONOMY_PATHS:
                if p.exists():
                    self._path = p
                    break

        if self._path and self._path.exists():
            self._load()
        else:
            logger.warning("No taxonomy file found")

    def _load(self) -> None:
        if self._path is None:
            return
        try:
            raw = json.loads(self._path.read_text())
            # Normalize — taxonomy may be a dict with codes as keys,
            # or a list, or have a "techniques" wrapper
            if isinstance(raw, list):
                self._taxonomy = {item.get("code", item.get("id", str(i))): item for i, item in enumerate(raw)}
            elif isinstance(raw, dict):
                if "codes" in raw and isinstance(raw["codes"], dict):
                    self._taxonomy = raw["codes"]
                elif "techniques" in raw:
                    self._taxonomy = raw["techniques"]
                elif any(k.startswith("SCT-") for k in raw):
                    self._taxonomy = raw
                else:
                    self._taxonomy = raw
            logger.info("Loaded taxonomy with %d entries from %s",
                       len(self._taxonomy) if self._taxonomy else 0, self._path)
        except Exception:
            logger.exception("Failed to load taxonomy")
            self._taxonomy = None

    def query(self, code: str | None = None, search: str | None = None) -> dict[str, Any]:
        """Query taxonomy by code or free text search."""
        if self._taxonomy is None:
            return {"techniques": [], "error": "Taxonomy not loaded"}

        results = []

        if code:
            # Exact code lookup
            code_upper = code.upper()
            if code_upper in self._taxonomy:
                results.append(self._taxonomy[code_upper])
            else:
                # Search through values
                for k, v in self._taxonomy.items():
                    if isinstance(v, dict) and v.get("code", "").upper() == code_upper:
                        results.append(v)

        elif search:
            # Free-text search
            search_lower = search.lower()
            for k, v in self._taxonomy.items():
                if isinstance(v, dict):
                    searchable = json.dumps(v).lower()
                    if search_lower in searchable:
                        results.append(v)
                elif isinstance(v, str) and search_lower in v.lower():
                    results.append({"code": k, "content": v})

        else:
            # Return all
            if isinstance(self._taxonomy, dict):
                results = list(self._taxonomy.values())
            else:
                results = list(self._taxonomy)

        return {"techniques": results, "count": len(results)}

    def full(self) -> dict[str, Any]:
        """Dump complete taxonomy."""
        if self._taxonomy is None:
            return {"taxonomy": {}, "error": "Taxonomy not loaded", "version": "unknown"}

        return {
            "taxonomy": self._taxonomy,
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "technique_count": len(self._taxonomy),
        }
