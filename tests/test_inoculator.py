"""Tests for seithar.inoculator."""
import pytest
from seithar.inoculator.inoculator import inoculate, list_available, format_inoculation


class TestInoculate:
    def test_valid_code(self):
        result = inoculate("SCT-001")
        assert result["code"] == "SCT-001"
        assert "inoculation" in result
        assert "mechanism" in result["inoculation"]
        assert "recognition_signals" in result["inoculation"]
        assert "defense" in result["inoculation"]
        assert "example" in result["inoculation"]

    def test_all_codes(self):
        for i in range(1, 13):
            code = f"SCT-{i:03d}"
            result = inoculate(code)
            assert result["code"] == code
            assert "inoculation" in result

    def test_unknown_code(self):
        result = inoculate("SCT-999")
        assert "error" in result

    def test_case_insensitive(self):
        result = inoculate("sct-001")
        assert result["code"] == "SCT-001"


class TestListAvailable:
    def test_returns_list(self):
        available = list_available()
        assert isinstance(available, list)
        assert len(available) == 12

    def test_all_sct_codes(self):
        available = list_available()
        for i in range(1, 13):
            assert f"SCT-{i:03d}" in available


class TestFormat:
    def test_format_valid(self):
        result = inoculate("SCT-001")
        formatted = format_inoculation(result)
        assert "INOCULATION" in formatted
        assert "SCT-001" in formatted
        assert "MECHANISM" in formatted
        assert "DEFENSE" in formatted

    def test_format_error(self):
        result = inoculate("SCT-999")
        formatted = format_inoculation(result)
        assert "Error" in formatted
