"""Tests for identity generator."""

import pytest
from seithar.identity_gen import (
    generate_username, generate_display_name, generate_bio,
    generate_identity, list_cultures, GeneratedIdentity,
    CULTURE_PACKS, _hex_fragment, _leet, _glitch,
)


class TestHelpers:
    def test_hex_fragment(self):
        h = _hex_fragment(4)
        assert len(h) == 4
        assert all(c in "0123456789abcdef" for c in h)

    def test_leet(self):
        assert _leet("hacker") == "h4ck3r"
        assert _leet("elite") == "3l173"

    def test_glitch(self):
        result = _glitch("dream")
        assert isinstance(result, str)
        assert len(result) > 0


class TestUsernameGeneration:
    def test_cyborgism(self):
        for _ in range(20):
            name = generate_username("cyborgism")
            assert len(name) > 0
            assert len(name) <= 20
            assert " " not in name
            # Should NOT look like LLM slop
            assert "signal_theorist" not in name
            assert "boundary_operator" not in name

    def test_hyperpop(self):
        for _ in range(20):
            name = generate_username("hyperpop")
            assert len(name) > 0
            assert len(name) <= 20

    def test_furry(self):
        for _ in range(20):
            name = generate_username("furry")
            assert len(name) > 0

    def test_infosec(self):
        for _ in range(20):
            name = generate_username("infosec")
            assert len(name) > 0

    def test_e_acc(self):
        for _ in range(10):
            name = generate_username("e_acc")
            assert len(name) > 0

    def test_post_rationalist(self):
        for _ in range(10):
            name = generate_username("post_rationalist")
            assert len(name) > 0

    def test_unknown_culture_defaults(self):
        name = generate_username("nonexistent_culture")
        assert len(name) > 0

    def test_uniqueness(self):
        names = {generate_username("cyborgism") for _ in range(50)}
        # Should have reasonable variety (not all the same)
        assert len(names) > 10


class TestDisplayName:
    def test_generates(self):
        name = generate_display_name("cyborgism", "voidthread0x8f")
        assert len(name) > 0

    def test_hyperpop_style(self):
        names = [generate_display_name("hyperpop", "NOVA404") for _ in range(10)]
        assert any(n for n in names)

    def test_furry_style(self):
        names = [generate_display_name("furry", "sparklewolf") for _ in range(10)]
        assert any(n for n in names)


class TestBio:
    def test_cyborgism_bio(self):
        bio = generate_bio("cyborgism")
        assert len(bio) > 0

    def test_furry_bio_template(self):
        # Should fill in {species} template
        bios = [generate_bio("furry") for _ in range(20)]
        assert any("{species}" not in b for b in bios)

    def test_unknown_culture(self):
        bio = generate_bio("nonexistent")
        # Falls back to cyborgism default, so still generates a bio
        assert isinstance(bio, str)


class TestIdentityGeneration:
    def test_single_identity(self):
        ids = generate_identity("cyborgism", count=1)
        assert len(ids) == 1
        identity = ids[0]
        assert identity.username
        assert identity.display_name
        assert identity.bio
        assert identity.culture == "cyborgism"
        assert identity.tone_guide
        assert identity.visual_guide

    def test_multiple_identities(self):
        ids = generate_identity("hyperpop", count=5)
        assert len(ids) == 5
        usernames = [i.username for i in ids]
        # All should be unique
        assert len(set(usernames)) == 5

    def test_cross_platform_variants(self):
        ids = generate_identity("infosec", count=1)
        assert len(ids[0].name_variants) > 0

    def test_to_dict(self):
        ids = generate_identity("cyborgism", count=1)
        d = ids[0].to_dict()
        assert "username" in d
        assert "display_name" in d
        assert "bio" in d
        assert "culture" in d
        assert "aesthetic_tags" in d

    def test_all_cultures(self):
        for culture in CULTURE_PACKS:
            ids = generate_identity(culture, count=3)
            assert len(ids) == 3
            for identity in ids:
                assert identity.username
                assert identity.culture == culture


class TestListCultures:
    def test_lists_all(self):
        cultures = list_cultures()
        assert len(cultures) == len(CULTURE_PACKS)
        for c in cultures:
            assert "name" in c
            assert "description" in c
            assert "sample_names" in c
            assert len(c["sample_names"]) == 3
