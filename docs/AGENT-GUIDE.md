# Seithar MCP Server — Agent Operator Guide

You are connected to the Seithar Platform MCP server. This gives you the full cognitive warfare toolkit. 55 tools. Here's how to use them.

## Quick Start

```
# See everything at a glance
dashboard()

# Generate analytics report (stats, no raw data)
analytics_report(platform="twitter")

# Build a target profile
build_profile(platform="twitter", handle="repligate")

# Get interaction context for a target
build_context(target_handle="repligate", platform="twitter", interaction_type="reply")

# Measure if the operation is working
semantic_drift(platform="twitter", action="measure")
semantic_drift(platform="twitter", action="trend")
```

## Tool Reference by Surface

### Fleet Management (Orchestrator)
| Tool | Purpose |
|------|---------|
| `orchestrator_spawn(persona_id, persona_data, platform, task)` | Prepare a bot instance for deployment |
| `orchestrator_fleet(platform?)` | Get status of all bot instances |
| `orchestrator_register_creds(persona_id, platform, credentials_path, proxy_config)` | Register platform credentials (encrypted, never in LLM context) |
| `orchestrator_broadcast(message, platform?, persona_ids?, tone_match?)` | Send same message through all active personas, tone-matched |
| `orchestrator_configure_runtime(instance_id, targets?, keywords?, lurk_hours?, ...)` | Set observation targets and engagement limits |
| `orchestrator_run_cycle(instance_id)` | Run one observe/collect/exfil cycle |
| `fleet_cycle(platform?)` | Run cycles across ALL active instances + ingest to collector |
| `dashboard(full?)` | Operator command surface: fleet, collector, intelligence summary |

### Swarm Operations
| Tool | Purpose |
|------|---------|
| `swarm_plan(objective, pattern, platform, payload_terms, target_handle?, waves?)` | Create a coordinated operation plan |
| `swarm_list(status?)` | List all swarm plans |
| `swarm_activate(plan_id)` | Mark plan as active |
| `swarm_assignments(plan_id)` | Get per-persona task prompts for dispatch |

**Swarm patterns:**
- `amplification` — seed/echo/ambient: independent reinforcement with staggered timing
- `pincer` — approach one target from multiple angles (academic, aesthetic, technical)
- `saturation` — flood a gatekeeper's periphery until vocabulary becomes ambient
- `cascade` — staged waves: pioneer → early adopter → mainstream

### Identity Generation
| Tool | Purpose |
|------|---------|
| `identity_generate(culture, count?)` | Generate culture-adaptive identities |
| `identity_cultures()` | List available culture packs with samples |

**Cultures:** cyborgism, hyperpop, furry, infosec, e_acc, post_rationalist

### Analytics (Statistical, Non-LLM)
| Tool | Purpose |
|------|---------|
| `analytics_report(platform?)` | Full statistical report for synthesis |
| `analytics_term_adoption(platform, terms, window_days?)` | Term usage over time buckets |
| `analytics_sentiment(platform, handle?, window_days?)` | Sentiment trajectory |
| `analytics_network(platform, handle)` | Network topology metrics |

### Context Intelligence (Middleware)
| Tool | Purpose |
|------|---------|
| `build_profile(platform, handle)` | Build/update psychological profile for a target |
| `build_context(target_handle, platform, interaction_type?, max_tokens?)` | Build optimal interaction context for a bot |
| `semantic_drift(platform?, action?)` | Measure or trend community vocabulary shift |
| `list_profiles()` | List all stored target profiles |

### Persona Operations
| Tool | Purpose |
|------|---------|
| `persona_create(archetype?, target_audience?, name?, platform?)` | Create persona scaffold |
| `persona_get(name)` | Get persona config |
| `persona_list()` | List all personas |
| `persona_update(name, updates)` | Update persona config |

### Detection Evasion
| Tool | Purpose |
|------|---------|
| `evasion_analyze(platform?)` | Detection risk analysis: temporal synchrony, content similarity, posting regularity, vocabulary homogeneity, network coordination. Risk score 0-1 with recommendations. |

### Campaign Management
| Tool | Purpose |
|------|---------|
| `campaign_create(name, objective, target_audience, ...)` | Create campaign |
| `campaign_status(campaign_id)` | Get campaign status |
| `campaign_record(campaign_id, event_type, data)` | Record campaign event |
| `campaign_measure(campaign_id)` | Get campaign metrics |
| `campaign_effectiveness(campaign_id, platform?)` | Quantitative effectiveness: adoption rate, sentiment shift, convergence, penetration score (0-8) |
| `campaign_list()` | List campaigns |

### Collector (Intelligence Database)
| Tool | Purpose |
|------|---------|
| `collector_ingest(source, platform, author_handle, content, ...)` | Store a raw observation |
| `collector_ingest_report(persona_id, platform, report)` | Bulk ingest from bot exfil |
| `collector_query(platform?, author?, since?, limit?)` | Query stored observations |
| `collector_contacts(platform?, tag?, limit?)` | Search contacts |
| `collector_vocab_stats(term?, platform?)` | Vocabulary adoption statistics |
| `collector_stats()` | Database stats |

### Network Analysis (via HoleSpawn)
| Tool | Purpose |
|------|---------|
| `network_analyze(handle, platform?)` | Analyze a target's network |
| `network_paths(source, target, platform?)` | Find connection paths |
| `network_plan(targets, objective?)` | Generate network operation plan |
| `network_gatekeepers(platform?, limit?)` | Identify gatekeepers |
| `network_compare(handles, platform?)` | Compare multiple targets |

### Threat Intelligence
| Tool | Purpose |
|------|---------|
| `feeds_query(topics?, severity_min?, since?, limit?)` | Query scored feed items |
| `feeds_sources()` | List feed sources |
| `taxonomy_query(code?, keyword?)` | Query SCT taxonomy |
| `taxonomy_full()` | Get full taxonomy |

### Self-Edit Engine
| Tool | Purpose |
|------|---------|
| `selfedit_route(paper)` | Route a paper through the edit engine |
| `selfedit_pending(component?)` | List pending edit proposals |
| `selfedit_apply(proposal_id)` | Apply an edit proposal |
| `selfedit_coverage()` | Get grounding coverage report |

### OPSEC
| Tool | Purpose |
|------|---------|
| `cloak_persona_checklist(persona_id)` | OPSEC checklist for a persona |
| `cloak_search(query)` | Search for OPSEC risks |
| `cloak_stats()` | OPSEC statistics |

## Data Flow

```
BOTS (observe) → COLLECTOR (raw storage, SQLite)
                      ↓
              ANALYTICS ENGINE (pure stats, no LLM)
                      ↓
              MIDDLEWARE (profiles + context assembly)
                      ↓
              YOU (synthesis + strategy)
                      ↓
              SWARM PLANNER (coordinated operations)
                      ↓
              ORCHESTRATOR (dispatch to persona sessions)
```

## Key Concepts

- **Collector DB**: SQLite at `~/.seithar/collector.db`. All raw intelligence goes here.
- **Profiles**: JSON at `~/.seithar/profiles/`. Compressed psychological models per target.
- **Personas**: JSON at `~/.seithar/personas/`. Identity + credentials + behavioral config.
- **Swarm Plans**: JSON at `~/.seithar/swarm/plans.json`. Coordinated operation manifests.
- **Drift History**: JSONL at `~/.seithar/drift/`. Semantic shift measurements over time.

## Bot Lifecycle

1. **Spawn** → `orchestrator_spawn` creates instance
2. **Configure** → `orchestrator_configure_runtime` sets targets/keywords
3. **Lurk** → 48hr minimum observation (automatic phase management)
4. **Engage Light** → replies only (hours 48-72)
5. **Engage Full** → originals + replies (72hr+)
6. **Exfil** → `fleet_cycle` runs observation + ingests to collector
7. **Measure** → `semantic_drift` + `analytics_report` to check if it's working
8. **Adjust** → update persona behavior based on metrics
9. **Burn/Retire** → if detected, mark as burned and rotate

## Operational Rules

- Credentials are NEVER in LLM context. Referenced by file path only.
- Personas are compartmentalized. No awareness of each other.
- All engagement uses proxy routing. Never expose real IP.
- The LLM IS the persona. It passes the Turing test by absorbing the culture.
- Analytics handles measurement. LLM handles synthesis and strategy.
- Every output is an input. The system feeds itself.
