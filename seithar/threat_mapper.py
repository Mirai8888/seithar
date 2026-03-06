"""
Threat Mapper -- Tier 2 CWaaS component.

Wraps HoleSpawn's network analysis engine into a client-facing
threat mapping service. Takes a client's adversary indicators and
produces actionable intelligence briefs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ThreatActor:
    """Identified threat actor from network analysis."""
    actor_id: str
    handle: str
    platform: str
    influence_score: float
    role: str  # "operator", "amplifier", "bridge", "seed"
    communities: list[str] = field(default_factory=list)
    techniques_observed: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThreatBrief:
    """Intelligence brief for a client engagement."""
    brief_id: str
    client_id: str
    generated_at: str
    campaign_name: str
    threat_actors: list[ThreatActor] = field(default_factory=list)
    network_stats: dict = field(default_factory=dict)
    vulnerability_assessment: dict = field(default_factory=dict)
    kill_chain_phase: str = ""
    recommended_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["threat_actors"] = [a.to_dict() if isinstance(a, ThreatActor) else a for a in self.threat_actors]
        return d

    def to_markdown(self) -> str:
        lines = [
            f"# THREAT INTELLIGENCE BRIEF: {self.campaign_name}",
            f"**Brief ID:** {self.brief_id}",
            f"**Client:** {self.client_id}",
            f"**Generated:** {self.generated_at}",
            f"**Confidence:** {self.confidence:.0%}",
            "",
            "## Network Summary",
        ]
        for k, v in self.network_stats.items():
            lines.append(f"- **{k}:** {v}")

        lines.append("")
        lines.append("## Threat Actors")
        for actor in self.threat_actors:
            a = actor if isinstance(actor, dict) else actor.to_dict()
            lines.append(f"\n### {a['handle']} ({a['platform']})")
            lines.append(f"- **Role:** {a['role']}")
            lines.append(f"- **Influence Score:** {a['influence_score']:.4f}")
            if a.get("techniques_observed"):
                lines.append(f"- **Techniques:** {', '.join(a['techniques_observed'])}")
            if a.get("communities"):
                lines.append(f"- **Communities:** {', '.join(a['communities'])}")

        if self.vulnerability_assessment:
            lines.append("\n## Vulnerability Assessment")
            for k, v in self.vulnerability_assessment.items():
                if isinstance(v, float):
                    lines.append(f"- **{k}:** {v:.4f}")
                else:
                    lines.append(f"- **{k}:** {v}")

        if self.kill_chain_phase:
            lines.append(f"\n## Kill Chain Phase\n{self.kill_chain_phase}")

        if self.recommended_actions:
            lines.append("\n## Recommended Actions")
            for i, action in enumerate(self.recommended_actions, 1):
                lines.append(f"{i}. {action}")

        lines.extend([
            "",
            "---",
            "Seithar Group Intelligence Division",
            f"Classification: CLIENT CONFIDENTIAL",
        ])
        return "\n".join(lines)


class ThreatMapper:
    """
    Client-facing threat mapping service.

    Wraps HoleSpawn's network analysis (open source) into a managed
    intelligence production pipeline (proprietary).

    Usage:
        mapper = ThreatMapper(client_id="acme-corp")
        brief = mapper.analyze_network(graph_data)
        print(brief.to_markdown())
    """

    def __init__(self, client_id: str, data_dir: Path | None = None):
        self.client_id = client_id
        self.data_dir = (data_dir or Path.home() / "seithar-platform" / "data") / client_id / "threat-maps"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_engines()

    def _load_engines(self) -> None:
        """Load HoleSpawn network analysis modules."""
        try:
            import sys
            hs_path = Path.home() / "HoleSpawn"
            if str(hs_path) not in sys.path:
                sys.path.insert(0, str(hs_path))
            from holespawn.network.engine import NetworkEngine
            from holespawn.network.influence_flow import compute_influence_scores
            from holespawn.network.vulnerability import analyze_vulnerability
            self._engine_cls = NetworkEngine
            self._influence = compute_influence_scores
            self._vulnerability = analyze_vulnerability
            self._engines_loaded = True
            logger.info("HoleSpawn engines loaded (v4 engine available)")
        except ImportError as e:
            logger.warning("HoleSpawn not available: %s", e)
            self._engines_loaded = False
            self._engine_cls = None
            self._influence = None
            self._vulnerability = None

    def analyze_network(
        self,
        graph: Any,
        campaign_name: str = "Unnamed Campaign",
        top_n: int = 20,
    ) -> ThreatBrief:
        """
        Run full threat analysis on a network graph.

        Uses NetworkEngine v4 when available for richer operational
        intelligence (role classification, influence paths, SPOF detection).
        Falls back to direct module calls otherwise.

        Args:
            graph: NetworkX DiGraph
            campaign_name: name for this analysis
            top_n: number of top actors to include

        Returns ThreatBrief with actors, vulnerability, recommendations.
        """
        import networkx as nx

        now = datetime.now(timezone.utc).isoformat()
        brief_id = f"{self.client_id}-{int(time.time())}"

        # Use NetworkEngine v4 if available
        if self._engine_cls:
            return self._analyze_with_engine(graph, campaign_name, top_n, brief_id, now)

        # Fallback: direct module calls
        return self._analyze_legacy(graph, campaign_name, top_n, brief_id, now)

    def _analyze_with_engine(
        self,
        graph: Any,
        campaign_name: str,
        top_n: int,
        brief_id: str,
        now: str,
    ) -> ThreatBrief:
        """Full analysis using NetworkEngine v4."""
        engine = self._engine_cls(graph)
        intel = engine.analyze()

        stats = {
            "nodes": intel.node_count,
            "edges": intel.edge_count,
            "density": round(intel.density, 6),
            "communities": intel.community_count,
            "hubs": len(intel.hubs),
            "bridges": len(intel.bridges),
            "spofs": len(intel.spofs),
            "seeds": len(intel.seeds),
            "amplifiers": len(intel.amplifiers),
        }

        # Build threat actors from engine's operational profiles
        actors = []
        top_nodes = intel.top_nodes(by="influence_score", n=top_n)
        for op in top_nodes:
            if op.influence_score <= 0:
                continue
            actors.append(ThreatActor(
                actor_id=f"{brief_id}-{op.node}",
                handle=op.node,
                platform="unknown",
                influence_score=op.influence_score,
                role=op.role,
                communities=[str(c) for c in op.downstream_communities],
                first_seen=now,
                last_seen=now,
                metadata={
                    "in_degree": op.degree_in,
                    "out_degree": op.degree_out,
                    "betweenness": round(op.betweenness, 6),
                    "pagerank": round(op.pagerank, 6),
                    "eigenvector": round(op.eigenvector, 6),
                    "is_spof": op.is_spof,
                    "downstream_reach": op.downstream_count,
                    "fragmentation_if_removed": round(op.fragmentation_if_removed, 4),
                    "influence_breakdown": op.influence_breakdown,
                },
            ))

        # Vulnerability from engine's report
        vuln_data = {}
        vr = intel.vulnerability_report
        if vr:
            vuln_data["spofs"] = len(vr.single_points_of_failure)
            if vr.fragmentation:
                top_frag = vr.fragmentation[0]
                vuln_data["top_fragmentation_node"] = top_frag.node
                vuln_data["top_fragmentation_ratio"] = top_frag.fragmentation_ratio
                vuln_data["top_fragmentation_isolated"] = top_frag.isolated_nodes
            if vr.attack_surfaces:
                last_step = vr.attack_surfaces[-1]
                vuln_data["min_nodes_to_fragment"] = last_step.get("nodes_removed_total", 0)
                vuln_data["achieved_fragmentation"] = last_step.get("cumulative_fragmentation", 0)
            if vr.community_cohesion:
                weakest = min(vr.community_cohesion, key=lambda c: c.cohesion)
                vuln_data["weakest_community"] = weakest.community_id
                vuln_data["weakest_cohesion"] = weakest.cohesion

        recommendations = self._generate_recommendations(actors, stats, vuln_data)

        brief = ThreatBrief(
            brief_id=brief_id,
            client_id=self.client_id,
            generated_at=now,
            campaign_name=campaign_name,
            threat_actors=actors,
            network_stats=stats,
            vulnerability_assessment=vuln_data,
            recommended_actions=recommendations,
            confidence=0.8 if actors else 0.3,
        )

        self._persist_brief(brief, brief_id)
        return brief

    def _analyze_legacy(
        self,
        graph: Any,
        campaign_name: str,
        top_n: int,
        brief_id: str,
        now: str,
    ) -> ThreatBrief:
        """Fallback analysis without NetworkEngine."""
        import networkx as nx

        stats = {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 6),
            "components": nx.number_weakly_connected_components(graph),
        }

        actors = []
        if self._influence:
            scores, details = self._influence(graph)
            top_actors = sorted(scores.items(), key=lambda x: -x[1])[:top_n]
            betweenness = nx.betweenness_centrality(graph)

            for handle, score in top_actors:
                in_deg = graph.in_degree(handle)
                out_deg = graph.out_degree(handle)
                btwn = betweenness.get(handle, 0)

                if btwn > 0.1:
                    role = "bridge"
                elif in_deg > out_deg * 2:
                    role = "amplifier"
                elif out_deg > in_deg * 2:
                    role = "seed"
                else:
                    role = "operator"

                actors.append(ThreatActor(
                    actor_id=f"{brief_id}-{handle}",
                    handle=handle,
                    platform="unknown",
                    influence_score=score,
                    role=role,
                    first_seen=now,
                    last_seen=now,
                    metadata={
                        "in_degree": in_deg,
                        "out_degree": out_deg,
                        "betweenness": round(btwn, 6),
                    },
                ))

        vuln_data = {}
        if self._vulnerability:
            try:
                vuln = self._vulnerability(graph)
                vuln_data = {
                    "fragmentation_risk": getattr(vuln, "fragmentation", [{}])[0].__dict__
                    if hasattr(vuln, "fragmentation") and vuln.fragmentation
                    else {},
                }
            except Exception as e:
                logger.error("Vulnerability analysis failed: %s", e)

        recommendations = self._generate_recommendations(actors, stats, vuln_data)

        brief = ThreatBrief(
            brief_id=brief_id,
            client_id=self.client_id,
            generated_at=now,
            campaign_name=campaign_name,
            threat_actors=actors,
            network_stats=stats,
            vulnerability_assessment=vuln_data,
            recommended_actions=recommendations,
            confidence=0.7 if actors else 0.3,
        )

        self._persist_brief(brief, brief_id)
        return brief

    def _persist_brief(self, brief: ThreatBrief, brief_id: str) -> None:
        """Save brief to disk as JSON and markdown."""
        brief_file = self.data_dir / f"{brief_id}.json"
        with open(brief_file, "w") as f:
            json.dump(brief.to_dict(), f, indent=2, default=str)

        md_file = self.data_dir / f"{brief_id}.md"
        with open(md_file, "w") as f:
            f.write(brief.to_markdown())

    def _generate_recommendations(
        self,
        actors: list[ThreatActor],
        stats: dict,
        vuln: dict,
    ) -> list[str]:
        """Generate actionable recommendations from analysis."""
        recs = []

        bridges = [a for a in actors if a.role == "bridge"]
        seeds = [a for a in actors if a.role == "seed"]

        if bridges:
            top_bridge = bridges[0]
            recs.append(
                f"Monitor bridge node {top_bridge.handle} (influence: {top_bridge.influence_score:.3f}). "
                f"This node connects multiple communities and can propagate narratives across group boundaries."
            )

        if seeds:
            top_seed = seeds[0]
            recs.append(
                f"Track seed node {top_seed.handle} for narrative origination. "
                f"High outbound activity suggests content creation role."
            )

        if stats.get("density", 0) > 0.1:
            recs.append(
                "Network density is high. Counter-narrative deployment will propagate quickly "
                "but so will adversary content. Speed of response is critical."
            )

        if len(actors) > 10:
            recs.append(
                "Adversary network has significant scale. Consider Tier 4 (persona operations) "
                "for sustained counter-influence."
            )

        if not recs:
            recs.append("Insufficient data for specific recommendations. Expand collection scope.")

        return recs
