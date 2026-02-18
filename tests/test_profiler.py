"""Tests for seithar.profiler."""
import pytest
from seithar.profiler.profiler import (
    profile_text, _tokenize, _extract_themes,
    _compute_sentiment, _find_emotional_words,
    _assess_vulnerabilities, _compute_style, format_profile,
)


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World! Test 123.")
        assert "hello" in tokens
        assert "world" in tokens

    def test_empty(self):
        assert _tokenize("") == []

    def test_strips_punctuation(self):
        tokens = _tokenize("don't stop! now?")
        assert all(t.isalnum() for t in tokens)


class TestSentiment:
    def test_positive(self):
        score = _compute_sentiment(["good", "great", "love"])
        assert score > 0

    def test_negative(self):
        score = _compute_sentiment(["bad", "terrible", "hate"])
        assert score < 0

    def test_neutral(self):
        score = _compute_sentiment(["the", "cat", "sat"])
        assert score == 0.0

    def test_empty(self):
        assert _compute_sentiment([]) == 0.0


class TestThemes:
    def test_extracts_common(self):
        tokens = ["security"] * 5 + ["threat"] * 3 + ["the"] * 10
        themes = _extract_themes(tokens, top_n=3)
        names = [t[0] for t in themes]
        assert "security" in names

    def test_empty(self):
        assert _extract_themes([]) == []


class TestEmotional:
    def test_finds_emotional(self):
        tokens = ["urgent", "cat", "shocking", "dog"]
        result = _find_emotional_words(tokens)
        assert "urgent" in result
        assert "shocking" in result
        assert "cat" not in result


class TestVulnerabilities:
    def test_returns_list(self):
        style = {"exclamation_density": 0.0}
        result = _assess_vulnerabilities(["urgent", "now", "act"], 0.0, style)
        assert isinstance(result, list)

    def test_detects_urgency(self):
        style = {"exclamation_density": 0.0}
        result = _assess_vulnerabilities(["urgent", "now", "deadline"], -0.1, style)
        codes = [v["code"] for v in result]
        assert "SCT-006" in codes

    def test_empty_input(self):
        result = _assess_vulnerabilities([], 0.0, {})
        assert result == []


class TestProfileText:
    def test_returns_dict(self):
        result = profile_text("This is a test of the profiler system.")
        assert isinstance(result, dict)
        assert "themes" in result
        assert "sentiment" in result
        assert "vulnerabilities" in result
        assert "style" in result

    def test_detects_emotional_content(self):
        result = profile_text("URGENT! Shocking revelations! Terrifying truth exposed!")
        assert len(result["emotional_words"]) > 0

    def test_format_profile(self):
        result = profile_text("This is a test.")
        formatted = format_profile(result)
        assert "SEITHAR SUBSTRATE PROFILE" in formatted


class TestStyle:
    def test_computes_style(self):
        text = "Short. Very short. Extremely short sentences!"
        tokens = _tokenize(text)
        style = _compute_style(text, tokens)
        assert "avg_sentence_length" in style
        assert "sentence_count" in style
        assert style["sentence_count"] >= 3
