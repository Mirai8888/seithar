"""
Knight's Eye MCP tools — Operational awareness for the cognitive domain.

These tools give the agent EYES in the information environment:
- Network topology with role classification
- Target intelligence at a glance
- Path finding between nodes
- Cascade threshold estimation
- Operational planning surface

The Knight sees the battlefield before it moves.
"""

import json
import os
import re
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = os.path.expanduser("~/.seithar/collector.db")


def _get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _build_adjacency():
    """Build adjacency from mention patterns AND stored edges. Cached after first call."""
    db = _get_db()
    contacts = {r["handle"].lower(): dict(r) for r in db.execute(
        "SELECT * FROM contacts"
    ).fetchall()}
    
    edge_counts = defaultdict(int)

    # Source 1: @mention patterns in observation content
    rows = db.execute(
        "SELECT author_handle, content FROM observations WHERE content LIKE '%@%'"
    ).fetchall()
    
    for row in rows:
        content = row["content"] or ""
        author = (row["author_handle"] or "").lower()
        if content.startswith("RT @"):
            continue
        mentions = re.findall(r"@(\w+)", content)
        for m in mentions:
            ml = m.lower()
            if ml != author and ml in contacts:
                edge_counts[(author, ml)] += 1

    # Source 2: Stored edges table (from collector.add_edge)
    try:
        edge_rows = db.execute(
            "SELECT source_handle, target_handle, count FROM edges"
        ).fetchall()
        for row in edge_rows:
            src = (row["source_handle"] or "").lower()
            tgt = (row["target_handle"] or "").lower()
            count = row["count"] if "count" in row.keys() else 1
            if src and tgt and src != tgt:
                edge_counts[(src, tgt)] += count
    except Exception:
        pass  # edges table may not exist in older DBs
    
    return contacts, edge_counts


def _classify_role(handle, neighbors, in_weight, out_weight, contacts):
    """Classify a node's operational role from topology."""
    deg = len(neighbors.get(handle, set()))
    in_w = in_weight.get(handle, 0)
    out_w = out_weight.get(handle, 0)
    
    my_neighbors = neighbors.get(handle, set())
    if len(my_neighbors) >= 2:
        internal = sum(1 for a in my_neighbors for b in my_neighbors 
                      if a < b and b in neighbors.get(a, set()))
        possible = len(my_neighbors) * (len(my_neighbors) - 1) / 2
        clustering = internal / possible if possible > 0 else 0
    else:
        clustering = 0
    
    role = "peripheral"
    if deg >= 20 and in_w > out_w * 1.5:
        role = "hub"
    elif deg >= 10 and clustering < 0.3:
        role = "bridge"
    elif deg >= 8 and in_w < out_w * 0.5:
        role = "amplifier"
    elif deg >= 5 and in_w > out_w * 2:
        role = "gatekeeper"
    elif deg >= 15:
        role = "hub"
    
    return role, round(clustering, 4)


def _vulnerability_surface(handle, neighbors, in_weight, out_weight, contacts, clustering):
    """Compute vulnerability indicators and score."""
    deg = len(neighbors.get(handle, set()))
    followers = contacts.get(handle, {}).get("follower_count", 0) or 0
    in_w = in_weight.get(handle, 0)
    out_w = out_weight.get(handle, 0)
    
    vulns = []
    score = 0.0
    
    if deg <= 2 and followers < 5000:
        vulns.append("isolated_node")
        score += 0.4
    if in_w > 0 and out_w > 0 and in_w > out_w * 3:
        vulns.append("passive_consumer")
        score += 0.3
    if out_w > 0 and in_w > 0 and out_w > in_w * 3:
        vulns.append("broadcast_node")
        score += 0.2
    if clustering < 0.15 and deg > 3:
        vulns.append("low_clustering")
        score += 0.2
    if followers > 10000 and deg < 10:
        vulns.append("high_value_soft_target")
        score += 0.3
    if deg >= 10 and clustering < 0.2:
        vulns.append("bridge_node")
        score += 0.15
    
    return vulns, min(round(score, 3), 1.0)


# ========== MCP Tool Functions ==========

def knight_eye_map(platform="twitter", min_degree=0):
    """
    Full operational map of the information environment.
    Returns all nodes with role, influence, vulnerability, and edge summary.
    This is the Knight's primary situational awareness tool.
    """
    contacts, edge_counts = _build_adjacency()
    
    neighbors = defaultdict(set)
    in_weight = defaultdict(int)
    out_weight = defaultdict(int)
    
    for (src, tgt), w in edge_counts.items():
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)
        out_weight[src] += w
        in_weight[tgt] += w
    
    db = _get_db()
    obs_counts = {}
    for r in db.execute(
        "SELECT LOWER(author_handle) as h, COUNT(*) as c FROM observations GROUP BY LOWER(author_handle)"
    ).fetchall():
        obs_counts[r["h"]] = r["c"]
    
    nodes = []
    for handle, contact in contacts.items():
        h = handle.lower()
        deg = len(neighbors.get(h, set()))
        if deg < min_degree:
            continue
        
        role, clustering = _classify_role(h, neighbors, in_weight, out_weight, contacts)
        vulns, vuln_score = _vulnerability_surface(h, neighbors, in_weight, out_weight, contacts, clustering)
        
        followers = contact.get("follower_count", 0) or 0
        obs = obs_counts.get(h, 0)
        
        nodes.append({
            "handle": contact.get("handle", h),
            "display_name": contact.get("display_name", ""),
            "role": role,
            "followers": followers,
            "observations": obs,
            "degree": deg,
            "clustering": clustering,
            "mentions_in": in_weight.get(h, 0),
            "mentions_out": out_weight.get(h, 0),
            "vulnerability_score": vuln_score,
            "vulnerabilities": vulns,
        })
    
    nodes.sort(key=lambda n: -n["degree"])
    
    role_counts = defaultdict(int)
    for n in nodes:
        role_counts[n["role"]] += 1
    
    return {
        "environment": {
            "total_targets": len(nodes),
            "total_edges": len(edge_counts),
            "total_observations": sum(obs_counts.values()),
            "role_distribution": dict(role_counts),
            "high_vulnerability_count": sum(1 for n in nodes if n["vulnerability_score"] > 0.3),
        },
        "targets": nodes,
    }


def knight_eye_target(handle):
    """
    Deep intelligence on a single target. Everything needed to plan engagement.
    Returns: profile, network position, vulnerability surface, top connections,
    recent content sample, and recommended SCT vectors.
    """
    contacts, edge_counts = _build_adjacency()
    h = handle.lower()
    
    if h not in contacts:
        return {"error": f"Target '{handle}' not found in collector"}
    
    neighbors = defaultdict(set)
    in_weight = defaultdict(int)
    out_weight = defaultdict(int)
    for (src, tgt), w in edge_counts.items():
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)
        out_weight[src] += w
        in_weight[tgt] += w
    
    role, clustering = _classify_role(h, neighbors, in_weight, out_weight, contacts)
    vulns, vuln_score = _vulnerability_surface(h, neighbors, in_weight, out_weight, contacts, clustering)
    
    contact = contacts[h]
    
    # Top connections with context
    connections = []
    for n in neighbors.get(h, set()):
        w_to = edge_counts.get((h, n), 0)
        w_from = edge_counts.get((n, h), 0)
        n_contact = contacts.get(n, {})
        n_role, _ = _classify_role(n, neighbors, in_weight, out_weight, contacts)
        connections.append({
            "handle": n_contact.get("handle", n),
            "display_name": n_contact.get("display_name", ""),
            "role": n_role,
            "mentions_to_target": w_from,
            "mentions_from_target": w_to,
            "total_weight": w_to + w_from,
        })
    connections.sort(key=lambda c: -c["total_weight"])
    
    # Recent content
    db = _get_db()
    recent = db.execute(
        "SELECT content, observed_at FROM observations WHERE LOWER(author_handle) = ? ORDER BY observed_at DESC LIMIT 15",
        (h,)
    ).fetchall()
    
    # SCT vector recommendations based on vulnerability surface
    sct_recs = []
    if "passive_consumer" in vulns:
        sct_recs.append({"vector": "SCT-005", "name": "Identity Targeting", "rationale": "Passive consumer -- mirror their consumption patterns, build rapport through shared interest"})
        sct_recs.append({"vector": "SCT-004", "name": "Social Proof", "rationale": "Already influenced by network consensus -- amplify desired narrative through their trusted connections"})
    if "isolated_node" in vulns:
        sct_recs.append({"vector": "SCT-005", "name": "Identity Targeting", "rationale": "Isolated -- direct engagement high leverage, no competing social proof"})
        sct_recs.append({"vector": "SCT-012", "name": "Commitment Escalation", "rationale": "Isolation means less corrective pressure from network -- escalation easier"})
    if "bridge_node" in vulns:
        sct_recs.append({"vector": "SCT-004", "name": "Social Proof", "rationale": "Bridge node -- turning this target propagates influence across clusters"})
    if "high_value_soft_target" in vulns:
        sct_recs.append({"vector": "SCT-005", "name": "Identity Targeting", "rationale": "High follower count but low network density -- direct engagement, high amplification potential"})
    if "broadcast_node" in vulns:
        sct_recs.append({"vector": "SCT-007", "name": "Recursive Infection", "rationale": "Broadcaster -- if turned, will amplify the narrative organically to their audience"})
    if not sct_recs:
        sct_recs.append({"vector": "SCT-005", "name": "Identity Targeting", "rationale": "Default approach -- build rapport through mirroring before escalation"})
        sct_recs.append({"vector": "SCT-012", "name": "Commitment Escalation", "rationale": "Standard graduated compliance sequence"})
    
    return {
        "target": {
            "handle": contact.get("handle", h),
            "display_name": contact.get("display_name", ""),
            "bio": contact.get("bio", ""),
            "followers": contact.get("follower_count", 0) or 0,
            "following": contact.get("following_count", 0) or 0,
            "first_seen": contact.get("first_seen", ""),
            "last_seen": contact.get("last_seen", ""),
        },
        "network_position": {
            "role": role,
            "degree": len(neighbors.get(h, set())),
            "clustering_coefficient": clustering,
            "mentions_received": in_weight.get(h, 0),
            "mentions_sent": out_weight.get(h, 0),
            "in_out_ratio": round(in_weight.get(h, 1) / max(out_weight.get(h, 1), 1), 2),
        },
        "vulnerability_surface": {
            "score": vuln_score,
            "indicators": vulns,
            "recommended_sct_vectors": sct_recs,
        },
        "top_connections": connections[:20],
        "recent_content": [{"content": r["content"][:500], "date": r["observed_at"]} for r in recent],
    }


def knight_eye_paths(source, target, max_hops=4):
    """
    Find influence paths between two nodes.
    Returns shortest paths and the nodes along each path.
    Critical for: identifying entry points, planning persona deployment routes,
    finding the weakest link in a target's trust network.
    """
    contacts, edge_counts = _build_adjacency()
    s, t = source.lower(), target.lower()
    
    if s not in contacts:
        return {"error": f"Source '{source}' not found"}
    if t not in contacts:
        return {"error": f"Target '{target}' not found"}
    
    neighbors = defaultdict(set)
    for (src, tgt), w in edge_counts.items():
        if w >= 3:  # minimum weight threshold
            neighbors[src].add(tgt)
            neighbors[tgt].add(src)
    
    # BFS for shortest paths
    from collections import deque
    queue = deque([(s, [s])])
    visited = {s}
    paths = []
    
    while queue and len(paths) < 5:
        node, path = queue.popleft()
        if len(path) > max_hops + 1:
            break
        if node == t:
            paths.append(path)
            continue
        for n in neighbors.get(node, set()):
            if n not in visited:
                visited.add(n)
                queue.append((n, path + [n]))
    
    # Annotate paths with node info
    result_paths = []
    for path in paths:
        annotated = []
        for h in path:
            c = contacts.get(h, {})
            annotated.append({
                "handle": c.get("handle", h),
                "display_name": c.get("display_name", ""),
                "followers": c.get("follower_count", 0) or 0,
            })
        result_paths.append({
            "hops": len(path) - 1,
            "path": annotated,
        })
    
    return {
        "source": source,
        "target": target,
        "paths_found": len(result_paths),
        "paths": result_paths,
    }


def knight_eye_cascade_assessment(community_handles=None):
    """
    Estimate cascade threshold for the mapped network or a subset.
    Based on Master Context cascade threshold theory:
    - Network topology (eigenvector centrality proxy)
    - Belief coherence (vocabulary convergence)
    - Structural vulnerability (bridge node density)
    
    Returns: cascade_proximity score (0-1), identified leverage points,
    recommended intervention sequence.
    """
    contacts, edge_counts = _build_adjacency()
    
    neighbors = defaultdict(set)
    in_weight = defaultdict(int)
    for (src, tgt), w in edge_counts.items():
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)
        in_weight[tgt] += w
    
    if community_handles:
        target_set = {h.lower() for h in community_handles}
    else:
        target_set = set(contacts.keys())
    
    # Eigenvector centrality proxy: iterative weight propagation
    scores = {h: 1.0 for h in target_set}
    for _ in range(10):
        new_scores = {}
        for h in target_set:
            s = sum(scores.get(n, 0) for n in neighbors.get(h, set()) if n in target_set)
            new_scores[h] = s
        # Normalize
        max_s = max(new_scores.values()) if new_scores else 1
        scores = {h: s / max_s if max_s > 0 else 0 for h, s in new_scores.items()}
    
    # Bridge density: proportion of nodes with low clustering
    bridge_count = 0
    total_with_edges = 0
    for h in target_set:
        deg = len(neighbors.get(h, set()) & target_set)
        if deg < 2:
            continue
        total_with_edges += 1
        my_n = neighbors.get(h, set()) & target_set
        internal = sum(1 for a in my_n for b in my_n if a < b and b in neighbors.get(a, set()))
        possible = len(my_n) * (len(my_n) - 1) / 2
        if possible > 0 and internal / possible < 0.2:
            bridge_count += 1
    
    bridge_density = bridge_count / total_with_edges if total_with_edges > 0 else 0
    
    # Leverage points: top eigenvector centrality nodes that are also bridges
    leverage_points = []
    for h in sorted(scores, key=lambda x: -scores.get(x, 0))[:20]:
        c = contacts.get(h, {})
        deg = len(neighbors.get(h, set()) & target_set)
        my_n = neighbors.get(h, set()) & target_set
        if len(my_n) >= 2:
            internal = sum(1 for a in my_n for b in my_n if a < b and b in neighbors.get(a, set()))
            possible = len(my_n) * (len(my_n) - 1) / 2
            clust = internal / possible if possible > 0 else 0
        else:
            clust = 0
        
        leverage_points.append({
            "handle": c.get("handle", h),
            "display_name": c.get("display_name", ""),
            "eigenvector_centrality": round(scores.get(h, 0), 4),
            "degree": deg,
            "clustering": round(clust, 4),
            "is_bridge": clust < 0.2 and deg > 3,
            "followers": c.get("follower_count", 0) or 0,
        })
    
    # Cascade proximity: higher bridge density + concentrated centrality = closer to cascade
    centrality_concentration = sum(s**2 for s in scores.values()) / max(len(scores), 1)
    cascade_proximity = min(1.0, bridge_density * 0.5 + centrality_concentration * 3 + 0.1)
    
    return {
        "cascade_assessment": {
            "proximity_score": round(cascade_proximity, 3),
            "interpretation": (
                "HIGH - network is structurally vulnerable to cascade" if cascade_proximity > 0.6
                else "MODERATE - cascade possible with sustained pressure at leverage points" if cascade_proximity > 0.3
                else "LOW - network is resilient, distributed topology"
            ),
            "bridge_density": round(bridge_density, 3),
            "centrality_concentration": round(centrality_concentration, 4),
            "community_size": len(target_set),
        },
        "leverage_points": leverage_points[:10],
        "recommended_sequence": [
            "1. Establish personas in orbit of top leverage points (bridge nodes with high centrality)",
            "2. Build trust through SCT-005 mirroring over 2-4 week lurk period",
            "3. Monitor free energy -- wait for natural epistemic stress event",
            "4. Apply SCT-012 escalation through leverage points during high-FE window",
            "5. Deploy SCT-004 social proof amplification once 2+ leverage points have shifted",
            "6. Measure cascade propagation through network monitoring",
        ],
    }


def knight_eye_weakest_link(target_handle):
    """
    Find the weakest link in a target's trust network.
    Per Master Context: 'The Knight doesn't always engage the target directly.
    Network graph analysis identifies which node in the target's trust network
    is most accessible and most influential.'
    
    Returns the optimal entry point to reach the target through their network.
    """
    contacts, edge_counts = _build_adjacency()
    h = target_handle.lower()
    
    if h not in contacts:
        return {"error": f"Target '{target_handle}' not found"}
    
    neighbors = defaultdict(set)
    in_weight = defaultdict(int)
    out_weight = defaultdict(int)
    for (src, tgt), w in edge_counts.items():
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)
        out_weight[src] += w
        in_weight[tgt] += w
    
    # Get target's direct connections
    target_neighbors = neighbors.get(h, set())
    
    candidates = []
    for n in target_neighbors:
        c = contacts.get(n, {})
        role, clustering = _classify_role(n, neighbors, in_weight, out_weight, contacts)
        vulns, vuln_score = _vulnerability_surface(n, neighbors, in_weight, out_weight, contacts, clustering)
        
        # Edge weight to target (how much influence does this node have on target?)
        influence_on_target = edge_counts.get((n, h), 0)  # their mentions of target
        target_listens = edge_counts.get((h, n), 0)  # target mentions them
        
        # Accessibility score: higher vuln + lower degree = easier to engage
        deg = len(neighbors.get(n, set()))
        accessibility = vuln_score * 0.4 + (1 - min(deg / 50, 1)) * 0.3 + 0.3 * (1 - clustering)
        
        # Influence score: how much does the target listen to this node?
        influence = target_listens / max(in_weight.get(h, 1), 1)
        
        # Combined: accessible AND influential on target
        entry_score = accessibility * 0.5 + influence * 0.5
        
        candidates.append({
            "handle": c.get("handle", n),
            "display_name": c.get("display_name", ""),
            "role": role,
            "entry_score": round(entry_score, 4),
            "accessibility": round(accessibility, 4),
            "influence_on_target": round(influence, 4),
            "vulnerability_score": vuln_score,
            "vulnerabilities": vulns,
            "target_mentions_them": target_listens,
            "they_mention_target": influence_on_target,
            "degree": deg,
            "followers": c.get("follower_count", 0) or 0,
        })
    
    candidates.sort(key=lambda c: -c["entry_score"])
    
    best = candidates[0] if candidates else None
    
    return {
        "target": target_handle,
        "target_network_size": len(target_neighbors),
        "weakest_link": best,
        "top_entry_points": candidates[:10],
        "recommendation": (
            f"Optimal entry: @{best['handle']} (score {best['entry_score']:.3f}). "
            f"Role: {best['role']}. Vulns: {', '.join(best['vulnerabilities']) or 'none'}. "
            f"Target mentions them {best['target_mentions_them']} times -- established trust channel."
            if best else "No connections found for this target."
        ),
    }


def knight_eye_environment_summary():
    """
    Executive operational summary. One-call situational awareness.
    What the Knight needs before any planning begins.
    """
    contacts, edge_counts = _build_adjacency()
    
    neighbors = defaultdict(set)
    in_weight = defaultdict(int)
    out_weight = defaultdict(int)
    for (src, tgt), w in edge_counts.items():
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)
        out_weight[src] += w
        in_weight[tgt] += w
    
    db = _get_db()
    total_obs = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    
    # Top hubs
    hubs = []
    bridges = []
    vulnerable = []
    
    for h, c in contacts.items():
        role, clustering = _classify_role(h, neighbors, in_weight, out_weight, contacts)
        vulns, vuln_score = _vulnerability_surface(h, neighbors, in_weight, out_weight, contacts, clustering)
        
        entry = {
            "handle": c.get("handle", h),
            "display_name": c.get("display_name", ""),
            "role": role,
            "degree": len(neighbors.get(h, set())),
            "followers": c.get("follower_count", 0) or 0,
            "vuln_score": vuln_score,
        }
        
        if role == "hub":
            hubs.append(entry)
        if role == "bridge":
            bridges.append(entry)
        if vuln_score > 0.3:
            vulnerable.append(entry)
    
    hubs.sort(key=lambda x: -x["degree"])
    bridges.sort(key=lambda x: -x["degree"])
    vulnerable.sort(key=lambda x: -x["vuln_score"])
    
    return {
        "environment": {
            "total_targets": len(contacts),
            "total_relationship_edges": len(edge_counts),
            "total_observations": total_obs,
            "collection_platforms": list(set(
                r[0] for r in db.execute("SELECT DISTINCT platform FROM observations").fetchall()
            )),
        },
        "key_hubs": hubs[:5],
        "bridge_nodes": bridges[:5],
        "highest_vulnerability": vulnerable[:5],
        "operational_readiness": {
            "data_sufficient": total_obs > 10000,
            "network_mapped": len(edge_counts) > 100,
            "targets_profiled": len(contacts) > 10,
            "recommendation": (
                "Environment mapped. Sufficient data for operation planning."
                if total_obs > 10000 and len(edge_counts) > 100
                else "Insufficient data. Continue collection before planning operations."
            ),
        },
    }
