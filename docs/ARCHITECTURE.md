# Architecture

Seithar is a monorepo with a plugin architecture. Each module operates independently and communicates through shared types defined in `seithar.core`.

## Module Dependency Graph

```
seithar.core (taxonomy, types, frameworks)
    ↑           ↑           ↑           ↑
scanner    inoculator     intel      profiler
    ↑           ↑           ↑           ↑
                    cli.py
```

All modules depend on `seithar.core`. No module depends on another module. The CLI orchestrates them.

## Core

- `taxonomy.py` — Single source of truth for SCT-001 through SCT-012. All other modules import technique definitions from here.
- `types.py` — Shared data types: `ScanResult`, `TechniqueMatch`, `IntelItem`, `InoculationResult`.
- `frameworks.py` — DISARM and MITRE ATT&CK mapping utilities.

## Scanner

Pattern-matching engine that detects cognitive exploitation techniques in text. Two modes:

- **Local** — Keyword/pattern matching against SCT indicators. No external dependencies.
- **LLM** — Full analysis via Claude API. Requires `ANTHROPIC_API_KEY`.

Input: text, URL, or file path. Output: `ScanResult`.

Source: `seithar-cogdef/scanner.py`

## Inoculator

Generates defensive content based on psychological inoculation theory. Exposes the mechanism of each technique rather than providing counter-arguments.

Pre-built templates for SCT-001 through SCT-007. Extensible for remaining codes.

Source: `seithar-cogdef/inoculator.py`

## Intel

Threat intelligence ingestion and scoring:

- `feeds.py` — RSS/Atom feed parsing (from ThreatMouth collectors)
- `scorer.py` — Relevance scoring against cognitive warfare keyword profiles (from ThreatMouth scorer + autoprompt)
- `arxiv.py` — arXiv paper monitoring across relevant categories (from seithar-autoprompt ingester)

## Profiler

Text-based psychological profiling: theme extraction, sentiment analysis, cognitive vulnerability assessment. Lightweight implementation using standard library only.

Source: `HoleSpawn/holespawn/profile/analyzer.py` (Python parts only, no vaderSentiment dependency)

## CLI

Unified entry point via `seithar` command. Dispatches to module-specific handlers. All commands support `--json` output for pipeline integration.

## Migration Notes

Individual repos remain active. The monorepo is the convergence point. During migration:

- `scanner.py` from seithar-cogdef has a missing `import re` — fix on import
- ThreatMouth collectors use async — simplify to sync for the monorepo
- HoleSpawn profiler depends on vaderSentiment — replace with stdlib sentiment
- seithar-autoprompt ingester is clean, minimal adaptation needed
