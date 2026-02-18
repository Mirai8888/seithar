"""Tests for seithar.inoculator — Inoculation Engine."""
import pytest


class TestInoculatorImports:
    def test_import_module(self):
        import seithar.inoculator  # noqa: F401

    def test_import_inoculate(self):
        from seithar.inoculator.inoculator import inoculate  # noqa: F401

    def test_import_list_available(self):
        from seithar.inoculator.inoculator import list_available  # noqa: F401

    def test_import_format_inoculation(self):
        from seithar.inoculator.inoculator import format_inoculation  # noqa: F401

    def test_import_inoculations_dict(self):
        from seithar.inoculator.inoculator import _INOCULATIONS  # noqa: F401


class TestInoculatorStubs:
    def test_inoculate_raises(self):
        from seithar.inoculator.inoculator import inoculate
        with pytest.raises(NotImplementedError):
            inoculate("SCT-001")

    def test_list_available_raises(self):
        from seithar.inoculator.inoculator import list_available
        with pytest.raises(NotImplementedError):
            list_available()

    def test_format_inoculation_raises(self):
        from seithar.inoculator.inoculator import format_inoculation
        with pytest.raises(NotImplementedError):
            format_inoculation(None)


class TestInoculationsDict:
    def test_is_dict(self):
        from seithar.inoculator.inoculator import _INOCULATIONS
        assert isinstance(_INOCULATIONS, dict)
