"""Seithar Inoculation Engine (SIE)."""

_INOCULATIONS: dict[str, str] = {}


def inoculate(sct_code: str):
    raise NotImplementedError


def list_available() -> list[str]:
    raise NotImplementedError


def format_inoculation(result) -> str:
    raise NotImplementedError
