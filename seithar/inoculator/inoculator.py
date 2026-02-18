"""
Seithar Inoculation Engine (SIE).

Generates defensive counter-content that inoculates targets against
specific cognitive exploitation techniques. Based on psychological
inoculation theory (McGuire, 1964).

Seithar approach: expose the MECHANISM, not a counter-argument.
Counter-arguments trigger identity defense. Mechanism exposure
triggers recognition — the only sustainable defense.

Will contain:
    - _INOCULATIONS dict: pre-built templates for SCT-001 through SCT-007
    - inoculate(sct_code) -> InoculationResult
    - list_available() -> list[str]
    - format_inoculation(result) -> str

Source: seithar-cogdef/inoculator.py
"""
