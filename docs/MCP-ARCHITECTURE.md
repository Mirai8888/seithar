# Seithar MCP Server: Architecture Design

**Status:** Design (v2)  
**Author:** Research Division  
**Date:** 2026-02-19

## Principle

The MCP server is a **data backend**, not a brain. LLMs are better analysts than any heuristic pipeline we build. The server does what LLMs can't: crawl, persist state, compute graph metrics, manage credentials, serve structured data. The LLM + human in the loop does all reasoning, all writing, all decisions.

**Ingest → Quantize → Serve → Agent acts.**

## Transport

- **Local (stdio):** Agent on same machine. Server as subprocess. Zero network exposure.
- **Remote (HTTP+SSE):** Network access. OAuth2 bearer token. Required for CWaaS clients.

Both expose identical surfaces.

## Data Surfaces

### `feeds/` — Threat Intelligence Feeds

Live data from ThreatMouth pipeline. Scored, deduplicated, queryable. The agent gets operational context it can't hallucinate.

#### `feeds/query`
```
Input:  { topics?: [string], severity_min?: float, since?: string, limit?: int }
Output: { items: [{ id, title, source, url, severity, topics, summary, timestamp }] }
```

#### `feeds/subscribe`
Push new items via MCP notifications as they arrive.
```
Input:  { topics?: [string], severity_min?: float }
Output: MCP notification stream
```

#### `feeds/sources`
List active feed sources and their health.
```
Input:  {}
Output: { sources: [{ name, url, last_fetch, item_count, health }] }
```

### `network/` — Graph Compute Engine

Persistent graph state with precomputed metrics. NetworkEngine sits on crawled data — PageRank, eigenvector centrality, community detection, influence paths, role classification. All computed, all structured, all ready for the LLM to reason over.

#### `network/analyze`
Crawl from seeds, build graph, compute all metrics. Returns structured intel.
```
Input:  { seeds: [string], platform?: string, depth?: int, source?: "scraper"|"community_archive" }
Output: { 
  network_id: string,
  stats: { nodes, edges, density, components },
  communities: [{ id, size, top_nodes, cohesion }],
  nodes: [{ 
    id, label, role, community,
    metrics: { pagerank, eigenvector, betweenness, in_degree, out_degree },
    reachability: { downstream_count, upstream_count }
  }],
  spofs: [{ node, fragmentation_impact }],
  bridges: [{ node, communities_connected }]
}
```

#### `network/paths`
K-shortest influence paths between nodes. Precomputed reliability and bottleneck data.
```
Input:  { network_id: string, source: string, target: string, k?: int }
Output: { paths: [{ nodes, hops, reliability, bottleneck, communities_crossed }] }
```

#### `network/plan`
Operation planning against real topology. Entry points, amplification chains, weak links — all from graph structure.
```
Input:  { network_id: string, objective: "reach"|"disrupt"|"monitor", targets?: [string], entry_nodes?: [] }
Output: { 
  entry_points: [{ node, role, why }],
  amplification_chains: [{ path, estimated_reach }],
  weak_links: [{ node, removal_impact }],
  risk_nodes: [{ node, detection_likelihood, why }]
}
```

#### `network/compare`
Diff two snapshots. Detect drift in community structure, new/lost bridges, role changes.
```
Input:  { network_id_a: string, network_id_b: string }
Output: { 
  added_nodes, removed_nodes, role_changes,
  community_shifts, new_bridges, lost_bridges,
  structural_drift_score: float
}
```

#### `network/gatekeepers`
Nodes controlling information flow between communities.
```
Input:  { network_id: string }
Output: { gatekeepers: [{ node, communities_gated, betweenness, removal_impact }] }
```

### `persona/` — Persona Scaffold

The agent calls the server, gets a complete persona scaffold — backstory, voice constraints, platform credentials, behavioral parameters. The LLM *becomes* the persona. We don't generate text; we provide the skeleton.

#### `persona/create`
Generate a persona scaffold from parameters.
```
Input:  { 
  archetype: string,  // "researcher", "skeptic", "newcomer", "practitioner", "cross-domain"
  platform: string,   // "twitter", "moltbook", "discord", "telegram", "reddit"
  constraints?: { topics?: [string], tone?: string, engagement_style?: string }
}
Output: { 
  persona_id: string,
  profile: { name, bio, backstory, voice_constraints, behavioral_bounds },
  platform_config: { username?, credentials_ref?, posting_rules },
  consistency: { topics_of_interest, opinion_anchors, vocabulary_profile }
}
```

#### `persona/get`
Retrieve an existing persona scaffold.
```
Input:  { persona_id: string }
Output: { persona: Persona }
```

#### `persona/list`
List active personas with status.
```
Input:  { platform?: string, status?: "active"|"flagged"|"retired" }
Output: { personas: [{ persona_id, name, platform, status, last_active, health }] }
```

#### `persona/update`
Update persona state after platform events (flagged, shadowbanned, engagement data).
```
Input:  { persona_id: string, event: "flagged"|"shadowbanned"|"engagement", data?: {} }
Output: { adjusted: bool, changes: [string] }
```
Flag events adjust behavioral parameters across the population. Darwinian — the population evolves under platform selection pressure.

#### `persona/credentials`
Manage platform credentials for a persona. Stored encrypted, never exposed to the LLM directly — the server handles auth and the agent just says "post as persona X."
```
Input:  { persona_id: string, action: "store"|"rotate"|"status" }
Output: { status: string }
```

### `campaign/` — Orchestration State

What's been deployed where, what's performing, what needs rotation. Persistent state the agent queries to make decisions.

#### `campaign/create`
```
Input:  { name: string, objective: string, network_id?: string, personas?: [string] }
Output: { campaign_id: string, status: "planning" }
```

#### `campaign/status`
```
Input:  { campaign_id: string }
Output: { 
  campaign_id, name, phase, 
  deployments: [{ id, persona, platform, content_summary, metrics }],
  network_state: { drift_since_start, replan_recommended },
  next_actions: [string]
}
```

#### `campaign/record`
Record a deployment action taken by the agent.
```
Input:  { campaign_id: string, persona_id: string, platform: string, content: string, url?: string }
Output: { deployment_id: string }
```

#### `campaign/measure`
Pull metrics for a deployment.
```
Input:  { deployment_id: string }
Output: { metrics: { reach, engagement, sentiment_delta, narrative_velocity } }
```

### `taxonomy/` — Structured Vocabulary

The SCT taxonomy as structured data. Not a tool — a reference the LLM pulls into its context. Machine-readable technique descriptions, relationships, detection indicators.

#### `taxonomy/query`
```
Input:  { code?: string, search?: string }
Output: { techniques: [{ code, name, definition, indicators, relationships, examples }] }
```

#### `taxonomy/full`
Dump the complete taxonomy for system prompt injection.
```
Input:  {}
Output: { taxonomy: {...}, version: string, last_updated: string }
```

### `chain/` — Operation Chain Modeling

ThreadMap chain modeling. Convert network intel + plans into hybrid operation chains with critical paths and intervention scores.

#### `chain/model`
```
Input:  { network_id?: string, plan?: {}, entities?: [], relationships?: [] }
Output: { chain_id: string, entities: [], critical_path: [], intervention_scores: {} }
```

#### `chain/query`
```
Input:  { chain_id: string }
Output: { chain: HybridChain }
```

## Resources (MCP Resources)

Read-only context the agent pulls without tool calls:

- `seithar://taxonomy/current` — Full SCT taxonomy
- `seithar://network/{id}/summary` — Cached network summary
- `seithar://campaign/{id}/state` — Campaign state
- `seithar://feeds/latest` — Most recent scored items

## State Management

- **Network cache:** Graphs + metrics persist by network_id. Path/plan calls reference cached state.
- **Persona registry:** Personas persist to disk. Behavioral parameters evolve.
- **Campaign state:** Persistent. Resume across sessions.
- **Feed state:** Continuous background ingestion. Deduplication state persists.

State keyed by auth token (remote) or per-process (local).

## Security

### Tiered Access (maps to CWaaS)
- **T1 (Sensor):** feeds/*, taxonomy/*
- **T2 (Threat Mapping):** T1 + network/* (read-only)
- **T3 (Active Defense):** T2 + chain/*
- **T4 (Persona Ops):** T3 + persona/*
- **T5 (Full Spectrum):** Everything including campaign/*

### Audit Trail
Every tool call logged: timestamp, client ID, tool, args (redacted), result summary. The server produces intelligence about its own usage.

### Credential Isolation
Persona platform credentials never exposed to the LLM. The server handles auth. Agent says "deploy as persona X" — server authenticates and posts. Credentials at rest encrypted.

## Architecture

```
MCP Client (any AI agent + human in the loop)
    |
    | JSON-RPC 2.0 (stdio or HTTP+SSE)
    |
+---v-----------------------------------------+
|  Seithar MCP Server                         |
|                                             |
|  +--------+ +--------+ +--------+ +------+ |
|  | feeds  | |network | |persona | |campaign| 
|  | (ingest| |(graph  | |(scaffold|(state  | |
|  |  score | | compute| | creds  | | track | |
|  |  dedup)| | cache) | | evolve)| | meas) | |
|  +--------+ +--------+ +--------+ +------+ |
|       |          |          |         |     |
|  +----v----------v----------v---------v---+ |
|  |         State Manager                  | |
|  |   (SQLite + disk persistence)          | |
|  +----------------------------------------+ |
|       |                                     |
|  +----v------------------+                  |
|  |  Auth + Rate Limit    |                  |
|  |  (OAuth2 / local)     |                  |
|  +-----------------------+                  |
+---------------------------------------------+
    |         |          |           |
    v         v          v           v
ThreatMouth HoleSpawn  persona    platform
(feeds)    (engine)    (scaffold) (campaign)
```

## Implementation Path

### Phase 1: Feeds + Network (the core value)
- feeds/query, feeds/sources
- network/analyze, network/paths, network/plan, network/gatekeepers
- taxonomy/query, taxonomy/full
- stdio transport only
- SQLite state for network cache
- Wraps ThreatMouth RSS pipeline + HoleSpawn NetworkEngine

### Phase 2: Persona Scaffold
- persona/create, persona/get, persona/list, persona/update
- Credential management (encrypted store)
- Behavioral parameter evolution on flag events

### Phase 3: Campaign Orchestration
- campaign/create, campaign/status, campaign/record, campaign/measure
- network/compare for drift detection
- chain/model, chain/query
- HTTP+SSE transport + OAuth2

### Phase 4: Autonomy
- feeds/subscribe (push notifications)
- Campaign auto-replan on network drift
- Persona population evolution (continuous)
- Taxonomy hot-reload from autoprompt pipeline

## What This Is

A data and compute layer for cognitive warfare. The models are already better analysts than our heuristics. What they lack is persistent state, precomputed graph metrics, live feeds, and persona infrastructure. That's what we serve.

The agent doesn't read about cognitive warfare. It plugs into the data layer and operates.

---

Seithar Group Intelligence Division  
Classification: INTERNAL
