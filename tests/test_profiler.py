"""Tests for seithar.profiler — substrate profiler."""
import pytest


class TestProfilerImports:
    def test_import_module(self):
        import seithar.profiler  # noqa: F401

    def test_import_profile_text(self):
        from seithar.profiler.profiler import profile_text  # noqa: F401

    def test_import_profile_result(self):
        from seithar.profiler.profiler import ProfileResult  # noqa: F401

    def test_import_internal_functions(self):
        from seithar.profiler.profiler import _tokenize  # noqa: F401
        from seithar.profiler.profiler import _extract_themes  # noqa: F401
        from seithar.profiler.profiler import _compute_sentiment  # noqa: F401
        from seithar.profiler.profiler import _find_emotional_words  # noqa: F401
        from seithar.profiler.profiler import _assess_vulnerabilities  # noqa: F401


class TestProfilerStubs:
    def test_profile_text_raises(self):
        from seithar.profiler.profiler import profile_text
        with pytest.raises(NotImplementedError):
            profile_text("some text to profile")

    def test_tokenize_raises(self):
        from seithar.profiler.profiler import _tokenize
        with pytest.raises(NotImplementedError):
            _tokenize("test")

    def test_extract_themes_raises(self):
        from seithar.profiler.profiler import _extract_themes
        with pytest.raises(NotImplementedError):
            _extract_themes(["test"], 5)

    def test_compute_sentiment_raises(self):
        from seithar.profiler.profiler import _compute_sentiment
        with pytest.raises(NotImplementedError):
            _compute_sentiment(["test"])

    def test_find_emotional_words_raises(self):
        from seithar.profiler.profiler import _find_emotional_words
        with pytest.raises(NotImplementedError):
            _find_emotional_words(["test"])

    def test_assess_vulnerabilities_raises(self):
        from seithar.profiler.profiler import _assess_vulnerabilities
        with pytest.raises(NotImplementedError):
            _assess_vulnerabilities([], 0.0, [])


class TestProfileResult:
    def test_is_dataclass(self):
        from seithar.profiler.profiler import ProfileResult
        assert hasattr(ProfileResult, "__dataclass_fields__")
