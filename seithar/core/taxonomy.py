"""
Seithar Cognitive Defense Taxonomy — Single Source of Truth.

SCT-001 through SCT-012: canonical definitions of cognitive exploitation
techniques mapped to cyber and cognitive analogs.

This module is the authoritative reference for all SCT codes across
the Seithar platform. All other modules import from here.

Will contain:
    - SCTechnique dataclass (frozen)
    - SCT_TAXONOMY dict mapping codes to SCTechnique instances
    - SEVERITY_LABELS dict
    - get_technique(code) lookup
    - list_techniques() -> list
    - validate_taxonomy() integrity check

Source: seithar-cogdef/scanner.py SCT_TAXONOMY dict (all 12 codes)
"""
