# Mission

Seithar exists because cognitive warfare has no defensive tooling.

Offensive information operations have state-level budgets, academic research programs, and industrialized deployment pipelines. The defense side has media literacy pamphlets and fact-checking websites that operate on a 48-hour delay against attacks that propagate in minutes.

This asymmetry is the problem Seithar addresses.

## What Seithar Does

1. **Classifies** cognitive exploitation techniques using a formal taxonomy (SCT-001 through SCT-012) that maps information-domain attacks to their cyber-domain analogs.

2. **Detects** these techniques in content through pattern matching and LLM-powered analysis, producing structured reports with severity scores, technique classifications, and framework mappings.

3. **Inoculates** against detected techniques using mechanism exposure — showing the target how the technique works rather than providing a counter-argument. Based on McGuire's inoculation theory: expose the mechanism, build recognition, enable autonomous defense.

4. **Monitors** the research and threat landscape through automated ingestion of arXiv papers, RSS feeds, and threat intelligence sources, scored for cognitive warfare relevance.

5. **Profiles** text for psychological patterns and cognitive vulnerability indicators, identifying which SCT techniques a given subject may be most susceptible to.

## Design Principles

- **Mechanism over argument.** Counter-arguments trigger identity defense. Mechanism exposure triggers recognition.
- **Taxonomy-first.** Every detection, inoculation, and report maps to canonical SCT codes. The taxonomy is the single source of truth.
- **Defensive posture.** This is a shield, not a sword. The same taxonomy that enables defense could enable offense; the tooling is oriented toward detection and inoculation.
- **Minimal dependencies.** The platform runs with `requests`, `feedparser`, `pyyaml`, and `click`. No ML frameworks required for core functionality.
- **Human and machine readable.** Every output is available as structured JSON for automated pipelines and formatted text for human analysts.

## Attribution

Seithar Group Research Division
研修生 | 認知作戦
seithar.com

## Recent Changes

| Date | Change |
|------|--------|
| 2026-02-18 | Taxonomy v2.0 propagated across all repos (12 SCT codes, dual-substrate) |
| 2026-02-18 | Cross-repo shared config module added to seithar-cogdef |
| 2026-02-18 | GitHub monitoring hooks for ecosystem-wide visibility |
