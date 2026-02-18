"""Tests for seithar.core.frameworks — DISARM and ATT&CK mappings."""
import pytest


class TestFrameworksImports:
    def test_import_module(self):
        import seithar.core.frameworks  # noqa: F401

    def test_import_disarm_phases(self):
        from seithar.core.frameworks import DISARM_PHASES  # noqa: F401

    def test_import_sct_to_disarm(self):
        from seithar.core.frameworks import SCT_TO_DISARM  # noqa: F401

    def test_import_attck_map(self):
        from seithar.core.frameworks import ATTCK_COGNITIVE_MAP  # noqa: F401

    def test_import_get_disarm_phases(self):
        from seithar.core.frameworks import get_disarm_phases  # noqa: F401

    def test_import_get_attck_techniques(self):
        from seithar.core.frameworks import get_attck_techniques  # noqa: F401

    def test_import_map_to_frameworks(self):
        from seithar.core.frameworks import map_to_frameworks  # noqa: F401


class TestFrameworksStructure:
    def test_disarm_phases_is_dict(self):
        from seithar.core.frameworks import DISARM_PHASES
        assert isinstance(DISARM_PHASES, dict)
        assert len(DISARM_PHASES) > 0

    def test_sct_to_disarm_is_dict(self):
        from seithar.core.frameworks import SCT_TO_DISARM
        assert isinstance(SCT_TO_DISARM, dict)

    def test_attck_map_is_dict(self):
        from seithar.core.frameworks import ATTCK_COGNITIVE_MAP
        assert isinstance(ATTCK_COGNITIVE_MAP, dict)


class TestFrameworksStubs:
    def test_get_disarm_phases_raises(self):
        from seithar.core.frameworks import get_disarm_phases
        with pytest.raises(NotImplementedError):
            get_disarm_phases("SCT-001")

    def test_get_attck_techniques_raises(self):
        from seithar.core.frameworks import get_attck_techniques
        with pytest.raises(NotImplementedError):
            get_attck_techniques("SCT-001")

    def test_map_to_frameworks_raises(self):
        from seithar.core.frameworks import map_to_frameworks
        with pytest.raises(NotImplementedError):
            map_to_frameworks("SCT-001")
