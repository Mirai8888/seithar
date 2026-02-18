"""DISARM and MITRE ATT&CK mapping utilities."""

DISARM_PHASES: dict[str, str] = {
    "TA01": "Plan Strategy",
    "TA02": "Plan Objectives",
    "TA03": "Develop People",
    "TA04": "Develop Networks",
    "TA05": "Microtarget",
    "TA06": "Develop Content",
    "TA07": "Channel Selection",
    "TA08": "Pump Priming",
    "TA09": "Deliver Content",
    "TA10": "Drive Online Harms",
    "TA11": "Drive Offline Harms",
    "TA12": "Persist in the Information Environment",
}

SCT_TO_DISARM: dict[str, list[str]] = {}

ATTCK_COGNITIVE_MAP: dict[str, list[str]] = {}


def get_disarm_phases(sct_code: str) -> list[dict]:
    raise NotImplementedError


def get_attck_techniques(sct_code: str) -> list[str]:
    raise NotImplementedError


def map_to_frameworks(sct_code: str) -> dict:
    raise NotImplementedError
