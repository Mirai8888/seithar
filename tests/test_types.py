"""Tests for seithar.core.types — shared data types."""
import pytest


class TestTypesImports:
    def test_import_module(self):
        import seithar.core.types  # noqa: F401

    def test_import_technique_match(self):
        from seithar.core.types import TechniqueMatch  # noqa: F401

    def test_import_scan_result(self):
        from seithar.core.types import ScanResult  # noqa: F401

    def test_import_intel_item(self):
        from seithar.core.types import IntelItem  # noqa: F401

    def test_import_inoculation_result(self):
        from seithar.core.types import InoculationResult  # noqa: F401


class TestTypesStructure:
    def test_technique_match_is_dataclass(self):
        from seithar.core.types import TechniqueMatch
        assert hasattr(TechniqueMatch, "__dataclass_fields__")

    def test_scan_result_is_dataclass(self):
        from seithar.core.types import ScanResult
        assert hasattr(ScanResult, "__dataclass_fields__")

    def test_intel_item_is_dataclass(self):
        from seithar.core.types import IntelItem
        assert hasattr(IntelItem, "__dataclass_fields__")

    def test_inoculation_result_is_dataclass(self):
        from seithar.core.types import InoculationResult
        assert hasattr(InoculationResult, "__dataclass_fields__")


class TestToDict:
    """All types should have to_dict() for JSON serialization."""

    @pytest.mark.parametrize("cls_name", [
        "TechniqueMatch", "ScanResult", "IntelItem", "InoculationResult"
    ])
    def test_has_to_dict(self, cls_name):
        import seithar.core.types as mod
        cls = getattr(mod, cls_name)
        assert hasattr(cls, "to_dict") and callable(getattr(cls, "to_dict"))
