"""
DISARM and MITRE ATT&CK mapping utilities.

Maps Seithar SCT codes to external framework identifiers for
interoperability with existing threat intelligence infrastructure.

Will contain:
    - DISARM_PHASES dict (TA01-TA12)
    - SCT_TO_DISARM mapping
    - ATTCK_COGNITIVE_MAP mapping
    - get_disarm_phases(sct_code) -> list[dict]
    - get_attck_techniques(sct_code) -> list[str]
    - map_to_frameworks(sct_code) -> dict
"""
