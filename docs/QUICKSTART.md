# Quickstart

Scaffold stage. Code migration pending Director review.

## Structure

```
seithar/
├── README.md
├── LICENSE
├── pyproject.toml
├── MISSION.md
├── seithar/
│   ├── __init__.py
│   ├── cli.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── taxonomy.py        # SCT-001 through SCT-012
│   │   ├── frameworks.py      # DISARM, ATT&CK mappings
│   │   └── types.py           # Shared data types
│   ├── scanner/
│   │   ├── __init__.py
│   │   └── scanner.py         # Cognitive threat detection
│   ├── inoculator/
│   │   ├── __init__.py
│   │   └── inoculator.py      # Inoculation generation
│   ├── intel/
│   │   ├── __init__.py
│   │   ├── feeds.py           # RSS/feed ingestion
│   │   ├── scorer.py          # Relevance scoring
│   │   └── arxiv.py           # arXiv paper monitoring
│   └── profiler/
│       ├── __init__.py
│       └── profiler.py        # Substrate profiling
├── tests/
│   ├── test_taxonomy.py
│   ├── test_scanner.py
│   ├── test_inoculator.py
│   └── test_feeds.py
└── docs/
    ├── TAXONOMY.md
    ├── ARCHITECTURE.md
    └── QUICKSTART.md
```

## Next Steps

1. Director reviews scaffold structure
2. Code migration from source repos
3. Tests
4. First release
