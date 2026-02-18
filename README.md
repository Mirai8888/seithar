# Seithar

Cognitive warfare defense and analysis platform.

Scanner, inoculator, threat intelligence, substrate profiling. Unified tooling for identifying, classifying, and countering cognitive exploitation techniques in content.

## Status

Scaffold. Structure approved. Code migration pending.

## Install

```
pip install seithar
```

Or from source:

```
git clone https://github.com/Mirai8888/seithar.git
cd seithar
pip install -e .
```

## Planned Commands

```bash
seithar scan <url>               # Scan content for cognitive threats
seithar scan --text "..."        # Scan raw text
seithar inoculate SCT-001        # Generate inoculation for a technique
seithar intel --arxiv             # Fetch relevant arXiv papers
seithar intel --feed <url>        # Fetch and score an RSS feed
seithar taxonomy                  # Print the full SCT taxonomy
seithar profile --text "..."      # Profile text for cognitive patterns
```

## Taxonomy

The Seithar Cognitive Defense Taxonomy (SCT) defines 12 canonical cognitive exploitation techniques:

| Code | Technique |
|------|-----------|
| SCT-001 | Emotional Hijacking |
| SCT-002 | Information Asymmetry Exploitation |
| SCT-003 | Authority Fabrication |
| SCT-004 | Social Proof Manipulation |
| SCT-005 | Identity Targeting |
| SCT-006 | Temporal Manipulation |
| SCT-007 | Recursive Infection |
| SCT-008 | Direct Substrate Intervention |
| SCT-009 | Chemical Substrate Disruption |
| SCT-010 | Sensory Channel Manipulation |
| SCT-011 | Trust Infrastructure Destruction |
| SCT-012 | Commitment Escalation & Self-Binding |

Full definitions: [docs/TAXONOMY.md](docs/TAXONOMY.md)

## Architecture

Monorepo with plugin architecture. Each module operates independently through shared types in `seithar.core`.

- **Core** — Canonical taxonomy, framework mappings (DISARM, ATT&CK), shared types
- **Scanner** — Pattern-matching and LLM-powered cognitive threat detection
- **Inoculator** — Mechanism-exposure-based psychological inoculation generation
- **Intel** — RSS/Atom feed ingestion, arXiv monitoring, relevance scoring
- **Profiler** — Psychological and behavioral profiling from text

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Source Repositories

This monorepo consolidates tooling from:

- [seithar-cogdef](https://github.com/Mirai8888/seithar-cogdef) — Cognitive defense scanner and inoculator
- [ThreatMouth](https://github.com/Mirai8888/ThreatMouth) — Adversarial awareness maintenance system
- [seithar-autoprompt](https://github.com/Mirai8888/seithar-autoprompt) — Research paper monitoring
- [HoleSpawn](https://github.com/Mirai8888/HoleSpawn) — Substrate profiling and experience generation

## License

MIT

---

研修生 | Seithar Group Research Division
認知作戦 | seithar.com
