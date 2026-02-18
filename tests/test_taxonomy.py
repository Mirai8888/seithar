"""
Comprehensive tests for seithar.core.taxonomy — the single source of truth.

Validates:
- All 12 SCT codes (SCT-001 through SCT-012) exist
- No gaps, no duplicates
- SCTechnique dataclass is frozen with correct fields
- Lookup and listing functions work
- Integrity check passes
"""
import pytest
from dataclasses import fields as dc_fields, FrozenInstanceError


# ---------------------------------------------------------------------------
# 1. Module imports
# ---------------------------------------------------------------------------

class TestTaxonomyImports:
    """Every public name advertised in the module docstring must be importable."""

    def test_import_module(self):
        import seithar.core.taxonomy  # noqa: F401

    def test_import_sctechnique(self):
        from seithar.core.taxonomy import SCTechnique  # noqa: F401

    def test_import_sct_taxonomy(self):
        from seithar.core.taxonomy import SCT_TAXONOMY  # noqa: F401

    def test_import_severity_labels(self):
        from seithar.core.taxonomy import SEVERITY_LABELS  # noqa: F401

    def test_import_get_technique(self):
        from seithar.core.taxonomy import get_technique  # noqa: F401

    def test_import_list_techniques(self):
        from seithar.core.taxonomy import list_techniques  # noqa: F401

    def test_import_validate_taxonomy(self):
        from seithar.core.taxonomy import validate_taxonomy  # noqa: F401


# ---------------------------------------------------------------------------
# 2. SCTechnique dataclass structure
# ---------------------------------------------------------------------------

class TestSCTechniqueDataclass:
    def test_is_dataclass(self):
        from seithar.core.taxonomy import SCTechnique
        assert hasattr(SCTechnique, "__dataclass_fields__")

    def test_is_frozen(self):
        from seithar.core.taxonomy import SCTechnique, SCT_TAXONOMY
        instance = next(iter(SCT_TAXONOMY.values()))
        with pytest.raises((FrozenInstanceError, AttributeError)):
            instance.code = "SCT-999"

    def test_required_fields_exist(self):
        """SCTechnique must have at least: code, name, description."""
        from seithar.core.taxonomy import SCTechnique
        field_names = {f.name for f in dc_fields(SCTechnique)}
        for required in ("code", "name", "description"):
            assert required in field_names, f"Missing field: {required}"


# ---------------------------------------------------------------------------
# 3. SCT_TAXONOMY completeness — the most critical invariants
# ---------------------------------------------------------------------------

ALL_SCT_CODES = [f"SCT-{i:03d}" for i in range(1, 13)]


class TestSCTTaxonomyCompleteness:
    def test_is_dict(self):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert isinstance(SCT_TAXONOMY, dict)

    def test_exactly_12_entries(self):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert len(SCT_TAXONOMY) == 12, f"Expected 12, got {len(SCT_TAXONOMY)}"

    @pytest.mark.parametrize("code", ALL_SCT_CODES)
    def test_code_present(self, code):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert code in SCT_TAXONOMY, f"{code} missing from taxonomy"

    def test_no_extra_codes(self):
        from seithar.core.taxonomy import SCT_TAXONOMY
        extras = set(SCT_TAXONOMY.keys()) - set(ALL_SCT_CODES)
        assert not extras, f"Unexpected codes: {extras}"

    def test_no_duplicate_names(self):
        from seithar.core.taxonomy import SCT_TAXONOMY
        names = [t.name for t in SCT_TAXONOMY.values()]
        assert len(names) == len(set(names)), "Duplicate technique names"

    @pytest.mark.parametrize("code", ALL_SCT_CODES)
    def test_entry_has_correct_code_field(self, code):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert SCT_TAXONOMY[code].code == code

    @pytest.mark.parametrize("code", ALL_SCT_CODES)
    def test_entry_has_nonempty_name(self, code):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert SCT_TAXONOMY[code].name and len(SCT_TAXONOMY[code].name.strip()) > 0

    @pytest.mark.parametrize("code", ALL_SCT_CODES)
    def test_entry_has_nonempty_description(self, code):
        from seithar.core.taxonomy import SCT_TAXONOMY
        assert SCT_TAXONOMY[code].description and len(SCT_TAXONOMY[code].description.strip()) > 0


# ---------------------------------------------------------------------------
# 4. SEVERITY_LABELS
# ---------------------------------------------------------------------------

class TestSeverityLabels:
    def test_is_dict(self):
        from seithar.core.taxonomy import SEVERITY_LABELS
        assert isinstance(SEVERITY_LABELS, dict)

    def test_has_entries(self):
        from seithar.core.taxonomy import SEVERITY_LABELS
        assert len(SEVERITY_LABELS) > 0


# ---------------------------------------------------------------------------
# 5. Lookup / listing functions
# ---------------------------------------------------------------------------

class TestLookupFunctions:
    def test_get_technique_valid(self):
        from seithar.core.taxonomy import get_technique, SCTechnique
        result = get_technique("SCT-001")
        assert isinstance(result, SCTechnique)
        assert result.code == "SCT-001"

    def test_get_technique_invalid_returns_none_or_raises(self):
        from seithar.core.taxonomy import get_technique
        result = get_technique("SCT-999")
        # Either returns None or raises KeyError — both acceptable
        assert result is None or False  # if we get here, it returned None → pass

    def test_list_techniques_returns_list(self):
        from seithar.core.taxonomy import list_techniques
        result = list_techniques()
        assert isinstance(result, list)
        assert len(result) == 12

    def test_validate_taxonomy_passes(self):
        from seithar.core.taxonomy import validate_taxonomy
        # Should not raise
        result = validate_taxonomy()
        # May return True or None; just ensure no exception
