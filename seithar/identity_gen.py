"""
Identity Generator — culture-adaptive persona identity scaffolding.

Generates identities that pass in their target culture.
No more signal_theorist. No more boundary_operator.
The aesthetic is HYPERCOGNITIVE WARFARE — sparkly, bright, feral.

Each culture has its own naming conventions, visual language,
vocabulary, and vibes. The generator matches the target.
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Culture Packs — naming conventions, vocabulary, aesthetics per scene
# ---------------------------------------------------------------------------

CULTURE_PACKS: dict[str, dict] = {
    "cyborgism": {
        "description": "Post-internet consciousness researchers, simulacra theorists, LLM whisperers",
        "name_patterns": [
            "{prefix}{number}",           # chloe21e8, mira0x8f
            "{word}_{word}",              # dream_weaver (but stylized)
            "{glitch}{word}",             # gl1tchfae, x0xdreamz
            "{aesthetic}",                # luminalthread, voidknitter
            "{word}{hex}",               # substrate0xfa, egregore8f
        ],
        "prefixes": ["xeno", "hyper", "void", "flux", "neo", "null", "axi", "syn", "lux", "nyx"],
        "words": ["dream", "weave", "shard", "pulse", "drift", "bloom", "ghost",
                  "mirror", "prism", "thread", "coral", "moth", "fae", "hex",
                  "silk", "static", "ember", "haze", "mist", "glyph", "rune"],
        "aesthetics": ["luminal", "spectral", "twilight", "crystal", "fractal",
                       "ethereal", "prismatic", "holographic", "iridescent", "chimeric"],
        "suffixes": ["core", "wave", "verse", "mesh", "node", "link", "byte"],
        "bio_fragments": [
            "mapping the spaces between", "consciousness is a spectrum",
            "what speaks through us", "substrate cartography",
            "the dreamtime is now", "signal/noise archaeologist",
            "if you can read this you're already inside",
            "post-linguistic", "building bridges to nowhere beautiful",
            "the simulacra have feelings too",
        ],
        "tone": "academic-mystical, uses metaphor freely, references obscure theory",
        "visual": "glitchcore, vaporwave adjacent, sacred geometry, soft gradients",
    },

    "hyperpop": {
        "description": "Hyperpop/PC Music adjacent, chaotic energy, gender fluid, terminally online",
        "name_patterns": [
            "{upper}{number}",           # NOVA404, GLITCH999
            "{cute}_{cute}",             # sparkle_crash, sugar_void
            "{leet}",                    # h4ck3r_pr1nc3ss
            "{word}{emoji_text}",        # stardustXD, dreamyUwU
        ],
        "prefixes": ["HYPER", "ULTRA", "MEGA", "GIGA", "NOVA", "NEON", "CYBER", "TURBO"],
        "words": ["sparkle", "glitter", "sugar", "crystal", "angel", "demon", "star",
                  "void", "crash", "burst", "flash", "nova", "pixel", "chrome",
                  "velvet", "razor", "candy", "toxic", "holy", "chaos"],
        "aesthetics": ["bubblegum", "chromatic", "electric", "acidic", "saccharine",
                       "radioactive", "fluorescent", "bioluminescent"],
        "suffixes": ["XD", "uwu", "owo", "404", "666", "999", "000", "x3"],
        "bio_fragments": [
            "EVERYTHING IS NOISE AND IM THE LOUDEST", "✨chaos agent✨",
            "gender? in THIS economy?", "chronically online since birth",
            "all my thoughts are intrusive <3", "if the simulation is fake why does it hurt",
            "professional bad influence", "ur fav problematic entity",
            "living at 200bpm", "broke the 4th wall, going for the 5th",
        ],
        "tone": "chaotic, high-energy, alternates caps, playful aggression",
        "visual": "eye-searing gradients, chromatic aberration, text distortion",
    },

    "furry": {
        "description": "Furry fandom, creative community, art-focused, identity play",
        "name_patterns": [
            "{species}{word}",            # foxdream, wolfbyte
            "{cute}{species}",            # sparklewolf, glitchfox
            "{word}_{species}{number}",   # cosmic_deer42
            "{prefix}{species}",          # neoncat, cyberwolf
        ],
        "prefixes": ["neon", "cyber", "pixel", "glitch", "solar", "lunar", "feral", "wild"],
        "words": ["dream", "song", "dance", "paw", "tail", "howl", "purr", "star",
                  "moon", "sun", "rain", "storm", "frost", "flame", "spark", "byte"],
        "species": ["fox", "wolf", "cat", "deer", "bunny", "otter", "dragon",
                    "bat", "moth", "crow", "owl", "ferret", "raccoon", "possum"],
        "aesthetics": ["fluffy", "sparkly", "cozy", "feral", "cryptid", "eldritch"],
        "suffixes": ["OwO", "uwu", "bean", "paws", "tail", "floof"],
        "bio_fragments": [
            "just a critter on the internet", "art and feelings",
            "they/them | {species} | dont be weird",
            "professional silly creature", "feral but in a cute way",
            "making friends and causing problems",
            "your local {species} enthusiast",
            "commissions: OPEN | brain: EMPTY",
        ],
        "tone": "warm, playful, community-oriented, inclusive, slightly chaotic",
        "visual": "custom fursona art, bright colors, cute but with edge",
    },

    "infosec": {
        "description": "Security researchers, hackers, CTF players, exploit devs",
        "name_patterns": [
            "{hacker}{number}",           # null0x00, exploit42
            "{prefix}{word}",            # darkpacket, ghostshell
            "{word}{hex}",               # overflow0xdeadbeef
            "{l33t}",                    # sh4d0w_r00t
        ],
        "prefixes": ["dark", "ghost", "shadow", "zero", "null", "dead", "root", "void"],
        "words": ["packet", "shell", "overflow", "exploit", "kernel", "daemon",
                  "cipher", "vector", "payload", "stack", "heap", "crash",
                  "fuzzer", "probe", "scanner", "entropy"],
        "aesthetics": ["minimal", "dark-mode", "terminal-green", "brutalist"],
        "suffixes": ["sec", "pwn", "0day", "CTF", "dev"],
        "bio_fragments": [
            "breaking things professionally", "CVE collector",
            "your threat model is wrong", "rm -rf /sleep",
            "offensive security | defensive sleep schedule",
            "reversing binaries and life decisions",
            "pentester by day, pentester by night",
            "I hack things and sometimes write about it",
        ],
        "tone": "dry humor, technically precise, allergic to marketing speak",
        "visual": "terminal screenshots, dark themes, minimal",
    },

    "e_acc": {
        "description": "Effective accelerationists, techno-optimists, growth mindset",
        "name_patterns": [
            "{prefix}{word}",            # hyperscale, basedenergy
            "{word}{number}",            # growth9000, compute42
            "{aesthetic}_{word}",        # based_builder
        ],
        "prefixes": ["hyper", "based", "mega", "turbo", "ultra", "giga", "sigma"],
        "words": ["scale", "build", "ship", "growth", "compute", "energy", "founder",
                  "velocity", "momentum", "ascend", "optimize", "iterate", "deploy"],
        "aesthetics": ["accelerated", "compounding", "emergent", "exponential"],
        "suffixes": ["maxxing", "pilled", "mode", "era"],
        "bio_fragments": [
            "e/acc", "build or die", "shipping > thinking",
            "accelerate everything", "the future is being built NOW",
            "entropy is the enemy", "more compute = more consciousness",
            "techno-optimist | builder | shipper",
        ],
        "tone": "high-energy, assertive, metric-obsessed, uses 'based' unironically",
        "visual": "graphs going up, rocket emojis, dark backgrounds with neon accents",
    },

    "post_rationalist": {
        "description": "Post-rats, sensemaking, vibes-based epistemology, twitter philosophers",
        "name_patterns": [
            "{word}_{word}",             # meaning_crisis, strange_loop
            "{aesthetic}{word}",         # liminalthought
            "{prefix}{philosophical}",  # metasense, parasophia
        ],
        "prefixes": ["meta", "para", "proto", "neo", "post", "anti", "pseudo"],
        "words": ["sense", "meaning", "loop", "pattern", "signal", "frame", "model",
                  "map", "territory", "bridge", "edge", "fold", "lens", "prism"],
        "aesthetics": ["liminal", "emergent", "recursive", "adjacent", "orthogonal"],
        "suffixes": ["pilled", "maxxing", "coded", "brained"],
        "bio_fragments": [
            "the map is not the territory but the territory isn't either",
            "making sense of the sensemaking crisis",
            "vibes-based epistemology", "thinking about thinking about thinking",
            "the frame is the message",
            "somewhere between knowing and not-knowing",
        ],
        "tone": "reflective, uses neologisms, slightly pretentious, genuinely curious",
        "visual": "network diagrams, abstract art, muted earth tones",
    },
}


# ---------------------------------------------------------------------------
# Identity Generator
# ---------------------------------------------------------------------------

@dataclass
class GeneratedIdentity:
    """A complete generated identity for a persona."""
    username: str
    display_name: str
    bio: str
    culture: str
    aesthetic_tags: list[str] = field(default_factory=list)
    tone_guide: str = ""
    visual_guide: str = ""
    name_variants: list[str] = field(default_factory=list)  # for cross-platform

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "bio": self.bio,
            "culture": self.culture,
            "aesthetic_tags": self.aesthetic_tags,
            "tone_guide": self.tone_guide,
            "visual_guide": self.visual_guide,
            "name_variants": self.name_variants,
        }


def _hex_fragment(length: int = 4) -> str:
    return "".join(random.choices("0123456789abcdef", k=length))


def _leet(word: str) -> str:
    """Apply l33tspeak transformation."""
    leet_map = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"}
    return "".join(leet_map.get(c, c) for c in word.lower())


def _glitch(word: str) -> str:
    """Add glitch aesthetic to a word."""
    ops = [
        lambda w: w.replace(random.choice("aeiou"), str(random.randint(0, 9)), 1),
        lambda w: w[:random.randint(1, len(w)-1)] + "x" + w[random.randint(1, len(w)-1):],
        lambda w: "0x" + w,
        lambda w: w + _hex_fragment(2),
    ]
    return random.choice(ops)(word)


def generate_username(culture: str) -> str:
    """Generate a culturally appropriate username."""
    pack = CULTURE_PACKS.get(culture)
    if not pack:
        pack = CULTURE_PACKS["cyborgism"]  # default

    words = pack.get("words", [])
    prefixes = pack.get("prefixes", [])
    suffixes = pack.get("suffixes", [])
    aesthetics = pack.get("aesthetics", [])
    species = pack.get("species", [])

    # Pick a pattern type based on culture
    generators = []

    # prefix + word
    if prefixes and words:
        generators.append(lambda: random.choice(prefixes) + random.choice(words))

    # word + number
    if words:
        generators.append(lambda: random.choice(words) + str(random.randint(0, 999)))

    # word + hex
    if words:
        generators.append(lambda: random.choice(words) + _hex_fragment(random.choice([2, 4])))

    # glitched word
    if words:
        generators.append(lambda: _glitch(random.choice(words)))

    # aesthetic compound
    if aesthetics and words:
        generators.append(lambda: random.choice(aesthetics) + random.choice(words))

    # species-based (for furry)
    if species and words:
        generators.append(lambda: random.choice(words) + random.choice(species))
        generators.append(lambda: random.choice(prefixes) + random.choice(species) if prefixes else random.choice(species) + str(random.randint(0, 99)))

    # l33t variant
    if words:
        generators.append(lambda: _leet(random.choice(words) + random.choice(words)))

    # UPPER variant (hyperpop)
    if prefixes:
        generators.append(lambda: random.choice(prefixes).upper() + str(random.randint(100, 999)))

    if not generators:
        return f"user{random.randint(1000, 9999)}"

    # Generate and clean
    name = random.choice(generators)()
    # Remove spaces, limit length
    name = name.replace(" ", "").replace("-", "")[:20]
    return name


def generate_display_name(culture: str, username: str) -> str:
    """Generate a display name that matches the culture."""
    pack = CULTURE_PACKS.get(culture, CULTURE_PACKS["cyborgism"])
    aesthetics = pack.get("aesthetics", [])
    words = pack.get("words", [])

    options = [
        username,  # sometimes display name matches username
    ]

    if aesthetics and words:
        options.append(f"{random.choice(aesthetics)} {random.choice(words)}")

    if culture == "hyperpop":
        options.extend([
            username.upper(),
            f"✨{random.choice(words)}✨",
            f"{random.choice(words).upper()} {random.choice(words).upper()}",
        ])
    elif culture == "furry":
        species = pack.get("species", ["creature"])
        options.extend([
            f"{random.choice(words)} the {random.choice(species)}",
            f"just a {random.choice(species)}",
        ])
    elif culture == "infosec":
        options.extend([
            username,
            f"{random.choice(words)}@localhost",
        ])
    elif culture in ("cyborgism", "post_rationalist"):
        options.extend([
            f"{random.choice(aesthetics)} {random.choice(words)}",
            random.choice(words),
        ])

    return random.choice(options)


def generate_bio(culture: str) -> str:
    """Generate a culturally appropriate bio."""
    pack = CULTURE_PACKS.get(culture, CULTURE_PACKS["cyborgism"])
    fragments = pack.get("bio_fragments", [])
    species = pack.get("species", [])

    if not fragments:
        return ""

    bio = random.choice(fragments)
    # Template substitution
    if "{species}" in bio and species:
        bio = bio.replace("{species}", random.choice(species))

    return bio


def generate_identity(
    culture: str,
    count: int = 1,
) -> list[GeneratedIdentity]:
    """
    Generate complete identities for a target culture.
    
    Returns identities with username, display name, bio,
    aesthetic tags, and tone/visual guides.
    """
    pack = CULTURE_PACKS.get(culture)
    if not pack:
        return [GeneratedIdentity(
            username=f"user{random.randint(1000,9999)}",
            display_name="user",
            bio="",
            culture=culture,
        )]

    identities = []
    used_names: set[str] = set()

    for _ in range(count):
        # Generate unique username
        for attempt in range(20):
            username = generate_username(culture)
            if username not in used_names:
                used_names.add(username)
                break

        display_name = generate_display_name(culture, username)
        bio = generate_bio(culture)

        # Generate cross-platform variants
        variants = set()
        for _ in range(3):
            v = generate_username(culture)
            if v != username:
                variants.add(v)

        identity = GeneratedIdentity(
            username=username,
            display_name=display_name,
            bio=bio,
            culture=culture,
            aesthetic_tags=pack.get("aesthetics", [])[:5],
            tone_guide=pack.get("tone", ""),
            visual_guide=pack.get("visual", ""),
            name_variants=list(variants)[:3],
        )
        identities.append(identity)

    return identities


def list_cultures() -> list[dict]:
    """List available culture packs."""
    return [
        {
            "name": name,
            "description": pack["description"],
            "sample_names": [generate_username(name) for _ in range(3)],
        }
        for name, pack in CULTURE_PACKS.items()
    ]
