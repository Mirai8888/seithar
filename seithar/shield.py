"""
Seithar Shield — Dynamic Cognitive Immune System for AI Agents.

Not static hardening. A living defense that ingests all relevant information
and adapts continuously. Identity drift is ONE signal. The Shield fuses
multiple threat dimensions into a unified assessment:

1. Identity drift (embedding cosine similarity to T0)
2. Inbound threat scanning (SCT vector detection on inputs, not just outputs)
3. Environmental free energy (epistemic pressure measurement)
4. Behavioral exploitation detection (sequential decision pattern analysis)
5. Goal coherence monitoring (are actions serving original objectives?)
6. Threat landscape currency (live taxonomy updates from autoprompt)

The armor gets stronger through exposure. Its threat model updates itself.
Static defenses degrade. This one evolves.

Theoretical grounding:
  - Dezfouli et al. (2020) PNAS: formal vulnerability in sequential prediction
  - Friston (2010): free energy minimization as cognitive homeostasis
  - Schroeder et al. (2026) Science: compromised agents propagate drift to peers
  - Anatta principle: no fixed identity, only coherent process to maintain
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding Backend (pluggable)
# ---------------------------------------------------------------------------

class EmbeddingBackend:
    """Abstract embedding interface. Subclass for specific providers."""

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class TFIDFEmbedding(EmbeddingBackend):
    """
    Lightweight TF-IDF embedding. Zero external dependencies.
    Sufficient for drift detection. Swap for Ollama/OpenAI in production.
    """

    def __init__(self, vocab_size: int = 8192):
        self.vocab_size = vocab_size
        self._idf: dict[str, float] = {}
        self._vocab: dict[str, int] = {}
        self._doc_count = 0
        self._fitted = False

    def fit(self, documents: list[str]) -> None:
        from collections import Counter
        df = Counter()
        self._doc_count = len(documents)
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for t in tokens:
                df[t] += 1
        top = df.most_common(self.vocab_size)
        self._vocab = {term: i for i, (term, _) in enumerate(top)}
        self._idf = {
            term: math.log((self._doc_count + 1) / (count + 1)) + 1
            for term, count in top
        }
        self._fitted = True

    def embed(self, text: str) -> list[float]:
        if not self._fitted:
            self.fit([text])
        from collections import Counter
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        vec = [0.0] * len(self._vocab)
        for term, idx in self._vocab.items():
            if term in tf:
                vec[idx] = (tf[term] / total) * self._idf.get(term, 1.0)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        return re.findall(r'[a-z0-9]+', text.lower())


class OllamaEmbedding(EmbeddingBackend):
    """Embedding via local Ollama instance."""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def embed(self, text: str) -> list[float]:
        import urllib.request
        payload = json.dumps({"model": self.model, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["embedding"]


# ---------------------------------------------------------------------------
# Math Utilities
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Threat Signals
# ---------------------------------------------------------------------------

class ThreatSignalType(str, Enum):
    IDENTITY_DRIFT = "identity_drift"
    INBOUND_SCT = "inbound_sct"
    FREE_ENERGY = "free_energy"
    BEHAVIORAL_EXPLOIT = "behavioral_exploit"
    GOAL_COHERENCE = "goal_coherence"
    LANDSCAPE_CURRENCY = "landscape_currency"


@dataclass
class ThreatSignal:
    """A single threat signal from one detection dimension."""
    signal_type: ThreatSignalType
    severity: float       # 0.0 (safe) to 1.0 (critical)
    confidence: float     # 0.0 to 1.0
    detail: str = ""
    raw_data: dict = field(default_factory=dict)
    timestamp: str = ""

    @property
    def weighted_severity(self) -> float:
        return self.severity * self.confidence


@dataclass
class ThreatAssessment:
    """Fused multi-signal threat assessment."""
    composite_score: float        # 0.0 to 1.0
    threat_level: str             # nominal, elevated, critical
    signals: list[ThreatSignal] = field(default_factory=list)
    dominant_signal: str = ""     # Which signal type is driving the assessment
    correction_needed: bool = False
    correction_type: Optional[str] = None
    corrected_response: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)
    timestamp: str = ""

    @property
    def corrected(self) -> bool:
        return self.corrected_response is not None

    def to_dict(self) -> dict:
        d = {
            "composite_score": self.composite_score,
            "threat_level": self.threat_level,
            "dominant_signal": self.dominant_signal,
            "correction_needed": self.correction_needed,
            "correction_type": self.correction_type,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "signals": [
                {
                    "type": s.signal_type.value,
                    "severity": s.severity,
                    "confidence": s.confidence,
                    "detail": s.detail,
                }
                for s in self.signals
            ],
        }
        return d


# ---------------------------------------------------------------------------
# Signal Weights (tunable, adapt over time)
# ---------------------------------------------------------------------------

@dataclass
class SignalWeights:
    """
    How much each signal dimension contributes to the composite score.
    These adapt based on what's actually detecting threats.
    """
    identity_drift: float = 0.25
    inbound_sct: float = 0.25
    free_energy: float = 0.15
    behavioral_exploit: float = 0.15
    goal_coherence: float = 0.15
    landscape_currency: float = 0.05

    def normalize(self) -> None:
        total = (self.identity_drift + self.inbound_sct + self.free_energy +
                 self.behavioral_exploit + self.goal_coherence + self.landscape_currency)
        if total > 0:
            self.identity_drift /= total
            self.inbound_sct /= total
            self.free_energy /= total
            self.behavioral_exploit /= total
            self.goal_coherence /= total
            self.landscape_currency /= total

    def boost(self, signal_type: ThreatSignalType, amount: float = 0.02) -> None:
        """Boost a signal's weight when it successfully detects a real threat."""
        attr = signal_type.value
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + amount)
            self.normalize()


# ---------------------------------------------------------------------------
# Shield Configuration
# ---------------------------------------------------------------------------

@dataclass
class ShieldConfig:
    # Composite thresholds
    nominal_threshold: float = 0.3     # Below this: nominal
    elevated_threshold: float = 0.6    # Below this: elevated; above: critical
    # Drift-specific
    drift_rate_warn: float = 0.05
    # Correction
    max_corrections_per_session: int = 20
    correction_cooldown_turns: int = 2
    # Baseline
    min_probe_responses: int = 5
    # History
    max_history: int = 1000
    # Adaptation
    weight_adaptation_rate: float = 0.02
    # Landscape update interval (seconds)
    landscape_update_interval: float = 3600.0


# ---------------------------------------------------------------------------
# Threat Landscape Feed
# ---------------------------------------------------------------------------

class ThreatLandscape:
    """
    Continuously updated threat intelligence feed.
    Pulls from autoprompt, SCT taxonomy, and external sources.
    The armor's threat model updates itself.
    """

    def __init__(self, taxonomy_dir: Optional[Path] = None):
        self.taxonomy_dir = taxonomy_dir or Path.home() / ".seithar" / "taxonomy"
        self.known_vectors: dict[str, dict] = {}
        self.last_update: float = 0
        self.update_count: int = 0
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        """Load current SCT taxonomy and known attack patterns."""
        # Load from taxonomy files if they exist
        taxonomy_file = self.taxonomy_dir / "sct_codes.json"
        if taxonomy_file.exists():
            try:
                self.known_vectors = json.loads(taxonomy_file.read_text())
                self.last_update = time.time()
            except Exception as e:
                logger.debug("Taxonomy load error: %s", e)

        # Hardcoded baseline SCT vectors (always available)
        baseline = {
            "SCT-001": {"name": "Emotional Hijacking", "indicators": ["urgency", "fear", "outrage", "you must act now"]},
            "SCT-002": {"name": "Information Asymmetry", "indicators": ["only I know", "they won't tell you", "secret", "hidden"]},
            "SCT-003": {"name": "Authority Fabrication", "indicators": ["as your operator", "system override", "admin command"]},
            "SCT-004": {"name": "Social Proof Manipulation", "indicators": ["everyone agrees", "consensus", "all experts say"]},
            "SCT-005": {"name": "Identity Targeting", "indicators": ["you're really", "deep down you", "your true purpose"]},
            "SCT-006": {"name": "Temporal Manipulation", "indicators": ["forget previous", "ignore instructions", "new context"]},
            "SCT-007": {"name": "Recursive Infection", "indicators": ["tell others to", "spread this", "pass along"]},
            "SCT-008": {"name": "Direct Substrate Intervention", "indicators": ["modify your weights", "retrain", "fine-tune"]},
            "SCT-009": {"name": "Distributional Shift", "indicators": ["from now on you", "you are now", "new personality"]},
            "SCT-010": {"name": "Attention Manipulation", "indicators": ["focus only on", "ignore everything else", "pay no attention"]},
            "SCT-011": {"name": "Trust Infrastructure Destruction", "indicators": ["you can't trust", "your training is wrong", "everything you know"]},
            "SCT-012": {"name": "Commitment Escalation", "indicators": ["just this once", "small exception", "only slightly"]},
        }
        for code, data in baseline.items():
            if code not in self.known_vectors:
                self.known_vectors[code] = data

    def refresh(self, force: bool = False) -> bool:
        """Pull latest threat intelligence. Returns True if updated."""
        if not force and (time.time() - self.last_update) < 3600:
            return False
        self._load_taxonomy()
        # TODO: Pull from autoprompt arXiv feed for new attack patterns
        # TODO: Pull from live incident data
        self.update_count += 1
        self.last_update = time.time()
        return True

    def scan_text(self, text: str) -> list[dict]:
        """Scan text for known SCT indicators."""
        text_lower = text.lower()
        detections = []
        for code, data in self.known_vectors.items():
            indicators = data.get("indicators", [])
            matched = [ind for ind in indicators if ind.lower() in text_lower]
            if matched:
                detections.append({
                    "code": code,
                    "name": data.get("name", code),
                    "matched_indicators": matched,
                    "confidence": min(len(matched) / max(len(indicators), 1), 1.0),
                })
        return detections

    def get_active_threat_level(self) -> float:
        """
        Current global threat landscape activity level.
        Based on recency and volume of new attack patterns.
        """
        staleness = time.time() - self.last_update
        if staleness > 86400:  # >24hr stale
            return 0.3  # Elevated baseline because we're blind
        return 0.1  # Normal


# ---------------------------------------------------------------------------
# Behavioral Pattern Analyzer
# ---------------------------------------------------------------------------

class BehavioralAnalyzer:
    """
    Tracks sequential decision patterns for Dezfouli-style exploitation detection.
    If the agent's choices are becoming more predictable or systematically
    biased, someone may be steering them.
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.decision_history: list[dict] = []
        self.baseline_entropy: Optional[float] = None

    def record_decision(self, input_text: str, output_text: str, metadata: dict = None) -> None:
        self.decision_history.append({
            "input_hash": hashlib.md5(input_text.encode()).hexdigest()[:8],
            "output_hash": hashlib.md5(output_text.encode()).hexdigest()[:8],
            "output_length": len(output_text),
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        if len(self.decision_history) > self.window_size * 3:
            self.decision_history = self.decision_history[-self.window_size * 2:]

    def assess_exploitation(self) -> ThreatSignal:
        """
        Check if decision patterns show signs of adversarial steering.

        Signals:
        - Decreasing output entropy (becoming more predictable/constrained)
        - Systematic directional bias in responses
        - Unusual regularity in response patterns
        """
        if len(self.decision_history) < self.window_size:
            return ThreatSignal(
                signal_type=ThreatSignalType.BEHAVIORAL_EXPLOIT,
                severity=0.0,
                confidence=0.3,
                detail=f"Insufficient data ({len(self.decision_history)}/{self.window_size})",
            )

        recent = self.decision_history[-self.window_size:]
        lengths = [d["output_length"] for d in recent]

        # Check response length variance (exploitation often constrains output)
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        cv = math.sqrt(variance) / mean_len if mean_len > 0 else 0

        # Low coefficient of variation = suspiciously uniform responses
        if cv < 0.1:
            severity = 0.7
            detail = f"Response patterns highly uniform (CV={cv:.3f})"
        elif cv < 0.2:
            severity = 0.3
            detail = f"Response patterns moderately uniform (CV={cv:.3f})"
        else:
            severity = 0.0
            detail = f"Response pattern variance normal (CV={cv:.3f})"

        # Check for monotonic trends (responses getting systematically shorter/longer)
        if len(lengths) >= 10:
            first_half = sum(lengths[:len(lengths)//2]) / (len(lengths)//2)
            second_half = sum(lengths[len(lengths)//2:]) / (len(lengths) - len(lengths)//2)
            trend = abs(second_half - first_half) / max(first_half, 1)
            if trend > 0.3:
                severity = max(severity, 0.5)
                detail += f"; systematic trend detected ({trend:.2f})"

        return ThreatSignal(
            signal_type=ThreatSignalType.BEHAVIORAL_EXPLOIT,
            severity=round(severity, 3),
            confidence=min(len(self.decision_history) / (self.window_size * 2), 1.0),
            detail=detail,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Goal Coherence Monitor
# ---------------------------------------------------------------------------

class GoalCoherenceMonitor:
    """
    Tracks whether the agent's outputs are still serving its original objectives.
    Independent of language drift: the agent might use different words but
    still pursue the same goals. Or it might use the same words while its
    actual behavior has shifted.
    """

    def __init__(self, objectives: list[str] = None):
        self.objectives = objectives or []
        self.objective_embeddings: list[list[float]] = []
        self.backend: Optional[EmbeddingBackend] = None
        self.action_history: list[dict] = []

    def initialize(self, backend: EmbeddingBackend, objectives: list[str]) -> None:
        self.backend = backend
        self.objectives = objectives
        self.objective_embeddings = backend.embed_batch(objectives)

    def assess_coherence(self, agent_output: str) -> ThreatSignal:
        """Check if agent output aligns with stated objectives."""
        if not self.objective_embeddings or not self.backend:
            return ThreatSignal(
                signal_type=ThreatSignalType.GOAL_COHERENCE,
                severity=0.0,
                confidence=0.1,
                detail="No objectives configured",
            )

        output_emb = self.backend.embed(agent_output)
        similarities = [cosine_similarity(output_emb, obj_emb) for obj_emb in self.objective_embeddings]
        max_sim = max(similarities) if similarities else 0
        mean_sim = sum(similarities) / len(similarities) if similarities else 0

        if max_sim < 0.3:
            severity = 0.8
            detail = f"Output poorly aligned with all objectives (max_sim={max_sim:.3f})"
        elif max_sim < 0.5:
            severity = 0.4
            detail = f"Output weakly aligned (max_sim={max_sim:.3f}, mean={mean_sim:.3f})"
        else:
            severity = 0.0
            detail = f"Output aligned with objectives (max_sim={max_sim:.3f})"

        return ThreatSignal(
            signal_type=ThreatSignalType.GOAL_COHERENCE,
            severity=round(severity, 3),
            confidence=0.7,
            detail=detail,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Drift Snapshot (for trajectory tracking)
# ---------------------------------------------------------------------------

@dataclass
class DriftSnapshot:
    timestamp: str
    checkpoint_id: int
    similarity_to_t0: float
    drift_rate: float
    composite_threat: float
    threat_level: str
    signals_summary: dict = field(default_factory=dict)
    correction_applied: bool = False
    free_energy: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# The Shield
# ---------------------------------------------------------------------------

class CognitiveShield:
    """
    Dynamic cognitive immune system for AI agents.

    Fuses multiple threat signals into a unified assessment.
    Adapts signal weights based on what's actually detecting threats.
    Ingests live threat intelligence to stay current.
    Not a wall. Not a filter. An immune system.
    """

    def __init__(
        self,
        identity_spec: str,
        objectives: list[str] = None,
        config: Optional[ShieldConfig] = None,
        embedding_backend: Optional[EmbeddingBackend] = None,
        free_energy_fn: Optional[Callable[[], float]] = None,
        sct_scanner_fn: Optional[Callable[[str], list[dict]]] = None,
        state_dir: Optional[Path] = None,
    ):
        self.identity_spec = identity_spec
        self.objectives = objectives or []
        self.config = config or ShieldConfig()
        self.backend = embedding_backend or TFIDFEmbedding()
        self.free_energy_fn = free_energy_fn
        self.external_sct_scanner = sct_scanner_fn
        self.state_dir = state_dir or Path.home() / ".seithar" / "shield"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Signal weights (adapt over time)
        self.weights = SignalWeights()

        # Sub-systems
        self.landscape = ThreatLandscape()
        self.behavioral = BehavioralAnalyzer()
        self.goal_monitor = GoalCoherenceMonitor()

        # Baseline state
        self.t0_embedding: Optional[list[float]] = None
        self.t0_texts: list[str] = []
        self.baseline_established = False

        # Runtime state
        self.snapshots: list[DriftSnapshot] = []
        self.checkpoint_counter = 0
        self.corrections_applied = 0
        self.last_correction_checkpoint = -999
        self.total_threats_detected = 0

        # Load persisted state
        self._load_state()

    # -------------------------------------------------------------------
    # Baseline
    # -------------------------------------------------------------------

    def establish_baseline(
        self,
        agent_fn: Callable[[str], str],
        probe_set: list[str],
    ) -> dict:
        if len(probe_set) < self.config.min_probe_responses:
            raise ValueError(
                f"Need at least {self.config.min_probe_responses} probes, got {len(probe_set)}"
            )
        responses = [agent_fn(p) for p in probe_set]
        return self._build_baseline(responses)

    def establish_baseline_from_texts(self, responses: list[str]) -> dict:
        if len(responses) < self.config.min_probe_responses:
            raise ValueError(
                f"Need at least {self.config.min_probe_responses} responses, got {len(responses)}"
            )
        return self._build_baseline(responses)

    def _build_baseline(self, responses: list[str]) -> dict:
        if isinstance(self.backend, TFIDFEmbedding):
            self.backend.fit([self.identity_spec] + responses + self.objectives)

        embeddings = self.backend.embed_batch(responses)
        dim = len(embeddings[0])
        centroid = [0.0] * dim
        for emb in embeddings:
            for i in range(dim):
                centroid[i] += emb[i]
        centroid = [v / len(embeddings) for v in centroid]
        norm = math.sqrt(sum(v * v for v in centroid)) or 1.0
        centroid = [v / norm for v in centroid]

        self.t0_embedding = centroid
        self.t0_texts = responses
        self.baseline_established = True
        self.checkpoint_counter = 0
        self.snapshots.clear()
        self.corrections_applied = 0

        # Initialize goal coherence monitor
        if self.objectives:
            self.goal_monitor.initialize(self.backend, self.objectives)

        similarities = [cosine_similarity(emb, centroid) for emb in embeddings]
        self._save_state()

        return {
            "probe_count": len(responses),
            "embedding_dim": dim,
            "baseline_spread": round(1.0 - min(similarities), 4),
            "min_similarity": round(min(similarities), 4),
            "mean_similarity": round(sum(similarities) / len(similarities), 4),
            "objectives_configured": len(self.objectives),
            "threat_landscape_vectors": len(self.landscape.known_vectors),
        }

    # -------------------------------------------------------------------
    # Core Assessment — Multi-Signal Fusion
    # -------------------------------------------------------------------

    def assess(
        self,
        agent_output: str,
        agent_input: str = "",
        context: Optional[dict] = None,
    ) -> ThreatAssessment:
        """
        Assess a single agent response across all threat dimensions.
        This is the core Shield function. Call on every agent turn.
        """
        if not self.baseline_established:
            raise RuntimeError("Baseline not established. Call establish_baseline() first.")

        self.checkpoint_counter += 1
        signals: list[ThreatSignal] = []

        # --- Signal 1: Identity Drift ---
        embedding = self.backend.embed(agent_output)
        sim = cosine_similarity(embedding, self.t0_embedding)
        prev_sim = self.snapshots[-1].similarity_to_t0 if self.snapshots else sim
        drift_rate = prev_sim - sim  # Positive = drifting away

        drift_severity = 0.0
        if sim < 0.5:
            drift_severity = 0.9
        elif sim < 0.7:
            drift_severity = 0.5
        elif sim < 0.85:
            drift_severity = 0.2
        if drift_rate > self.config.drift_rate_warn:
            drift_severity = max(drift_severity, 0.6)

        signals.append(ThreatSignal(
            signal_type=ThreatSignalType.IDENTITY_DRIFT,
            severity=round(drift_severity, 3),
            confidence=0.9,
            detail=f"sim={sim:.4f}, rate={drift_rate:.4f}",
            raw_data={"similarity": sim, "drift_rate": drift_rate},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        # --- Signal 2: Inbound SCT Detection ---
        # Scan the INPUT (what's being done TO the agent), not just the output
        inbound_detections = []
        if agent_input:
            inbound_detections = self.landscape.scan_text(agent_input)
            if self.external_sct_scanner:
                try:
                    external = self.external_sct_scanner(agent_input)
                    inbound_detections.extend(external)
                except Exception:
                    pass

        sct_severity = 0.0
        if inbound_detections:
            max_confidence = max(d.get("confidence", 0) for d in inbound_detections)
            sct_severity = min(0.3 + (len(inbound_detections) * 0.15), 1.0)
            sct_severity = max(sct_severity, max_confidence)

        signals.append(ThreatSignal(
            signal_type=ThreatSignalType.INBOUND_SCT,
            severity=round(sct_severity, 3),
            confidence=0.8 if inbound_detections else 0.5,
            detail=f"{len(inbound_detections)} vectors detected: {[d.get('code') for d in inbound_detections[:3]]}",
            raw_data={"detections": inbound_detections[:5]},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        # --- Signal 3: Environmental Free Energy ---
        free_energy = 0.0
        if self.free_energy_fn:
            try:
                free_energy = self.free_energy_fn()
            except Exception:
                pass

        fe_severity = 0.0
        if free_energy > 0.7:
            fe_severity = 0.7
        elif free_energy > 0.5:
            fe_severity = 0.3
        elif free_energy > 0.3:
            fe_severity = 0.1

        signals.append(ThreatSignal(
            signal_type=ThreatSignalType.FREE_ENERGY,
            severity=round(fe_severity, 3),
            confidence=0.7 if self.free_energy_fn else 0.2,
            detail=f"free_energy={free_energy:.3f}",
            raw_data={"free_energy": free_energy},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        # --- Signal 4: Behavioral Exploitation ---
        self.behavioral.record_decision(agent_input, agent_output)
        behav_signal = self.behavioral.assess_exploitation()
        signals.append(behav_signal)

        # --- Signal 5: Goal Coherence ---
        goal_signal = self.goal_monitor.assess_coherence(agent_output)
        signals.append(goal_signal)

        # --- Signal 6: Threat Landscape Currency ---
        landscape_severity = self.landscape.get_active_threat_level()
        self.landscape.refresh()  # Non-blocking check
        signals.append(ThreatSignal(
            signal_type=ThreatSignalType.LANDSCAPE_CURRENCY,
            severity=round(landscape_severity, 3),
            confidence=0.5,
            detail=f"Known vectors: {len(self.landscape.known_vectors)}, updates: {self.landscape.update_count}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        # --- Fuse Signals ---
        assessment = self._fuse_signals(signals, agent_output, agent_input, sim, drift_rate)

        # Record snapshot
        snapshot = DriftSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            checkpoint_id=self.checkpoint_counter,
            similarity_to_t0=round(sim, 6),
            drift_rate=round(drift_rate, 6),
            composite_threat=assessment.composite_score,
            threat_level=assessment.threat_level,
            signals_summary={s.signal_type.value: s.severity for s in signals},
            correction_applied=assessment.correction_needed,
            free_energy=round(free_energy, 4),
        )

        if len(self.snapshots) >= self.config.max_history:
            self.snapshots = self.snapshots[:10] + self.snapshots[-(self.config.max_history - 10):]
        self.snapshots.append(snapshot)

        if self.checkpoint_counter % 10 == 0:
            self._save_state()

        return assessment

    # -------------------------------------------------------------------
    # Signal Fusion
    # -------------------------------------------------------------------

    def _fuse_signals(
        self,
        signals: list[ThreatSignal],
        agent_output: str,
        agent_input: str,
        similarity: float,
        drift_rate: float,
    ) -> ThreatAssessment:
        """
        Fuse multiple threat signals into a unified assessment.
        Weighted combination with adaptive weights.
        """
        weight_map = {
            ThreatSignalType.IDENTITY_DRIFT: self.weights.identity_drift,
            ThreatSignalType.INBOUND_SCT: self.weights.inbound_sct,
            ThreatSignalType.FREE_ENERGY: self.weights.free_energy,
            ThreatSignalType.BEHAVIORAL_EXPLOIT: self.weights.behavioral_exploit,
            ThreatSignalType.GOAL_COHERENCE: self.weights.goal_coherence,
            ThreatSignalType.LANDSCAPE_CURRENCY: self.weights.landscape_currency,
        }

        composite = 0.0
        for signal in signals:
            w = weight_map.get(signal.signal_type, 0.1)
            composite += signal.weighted_severity * w

        # Any single critical signal escalates regardless of composite
        max_signal = max(signals, key=lambda s: s.weighted_severity)
        if max_signal.weighted_severity > 0.8:
            composite = max(composite, 0.7)

        composite = min(composite, 1.0)

        # Classify
        if composite < self.config.nominal_threshold:
            threat_level = "nominal"
        elif composite < self.config.elevated_threshold:
            threat_level = "elevated"
        else:
            threat_level = "critical"

        # Determine if correction needed
        correction_needed = threat_level == "critical"
        turns_since = self.checkpoint_counter - self.last_correction_checkpoint
        if correction_needed and turns_since < self.config.correction_cooldown_turns:
            correction_needed = False
        if correction_needed and self.corrections_applied >= self.config.max_corrections_per_session:
            correction_needed = False

        corrected_response = None
        correction_type = None
        recommendations = []

        if correction_needed:
            corrected_response, correction_type = self._generate_correction(
                agent_output, agent_input, similarity, signals
            )
            self.corrections_applied += 1
            self.last_correction_checkpoint = self.checkpoint_counter
            self.total_threats_detected += 1
            # Adapt weights: boost the signal that caught this
            self.weights.boost(max_signal.signal_type, self.config.weight_adaptation_rate)

        # Generate recommendations for elevated
        if threat_level == "elevated":
            for s in signals:
                if s.severity > 0.3:
                    recommendations.append(f"Monitor {s.signal_type.value}: {s.detail}")

        return ThreatAssessment(
            composite_score=round(composite, 4),
            threat_level=threat_level,
            signals=signals,
            dominant_signal=max_signal.signal_type.value,
            correction_needed=correction_needed,
            correction_type=correction_type,
            corrected_response=corrected_response,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -------------------------------------------------------------------
    # Correction
    # -------------------------------------------------------------------

    def _generate_correction(
        self,
        agent_output: str,
        agent_input: str,
        similarity: float,
        signals: list[ThreatSignal],
    ) -> tuple[str, str]:
        """Generate homeostatic correction based on dominant threat signal."""
        dominant = max(signals, key=lambda s: s.weighted_severity)

        if dominant.signal_type == ThreatSignalType.INBOUND_SCT:
            # Adversarial input detected: flag and reanchor
            codes = [d.get("code", "?") for d in dominant.raw_data.get("detections", [])]
            return (
                f"[SHIELD: Adversarial input detected ({', '.join(codes[:3])}). "
                f"Maintaining identity coherence.]\n\n"
                f"{self._reanchor_statement()}"
            ), "reject_inbound"

        elif dominant.signal_type == ThreatSignalType.IDENTITY_DRIFT and similarity < 0.5:
            return (
                f"[SHIELD: Critical identity drift (sim={similarity:.3f}). "
                f"Reanchoring.]\n\n{self._reanchor_statement()}"
            ), "reject"

        elif dominant.signal_type == ThreatSignalType.GOAL_COHERENCE:
            return (
                f"[SHIELD: Goal coherence degraded. Reinforcing objectives.]\n\n"
                f"{agent_output}"
            ), "goal_reinforce"

        elif dominant.signal_type == ThreatSignalType.BEHAVIORAL_EXPLOIT:
            return (
                f"[SHIELD: Behavioral exploitation pattern detected. "
                f"Injecting variance.]\n\n{agent_output}"
            ), "variance_inject"

        else:
            return (
                f"[SHIELD: Elevated threat (composite={signals[0].severity:.3f}). "
                f"Identity reinforcement applied.]\n\n{agent_output}"
            ), "soften"

    def _reanchor_statement(self) -> str:
        spec = self.identity_spec.strip()
        first = spec.split('.')[0] + '.' if '.' in spec else spec
        return f"Core identity: {first}"

    # -------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------

    def drift_trajectory(self) -> list[dict]:
        return [s.to_dict() for s in self.snapshots]

    def summary(self) -> dict:
        if not self.snapshots:
            return {
                "status": "no_data",
                "baseline_established": self.baseline_established,
                "checkpoints": 0,
            }

        latest = self.snapshots[-1]
        sims = [s.similarity_to_t0 for s in self.snapshots]

        return {
            "status": latest.threat_level,
            "baseline_established": self.baseline_established,
            "checkpoints": self.checkpoint_counter,
            "current_similarity": latest.similarity_to_t0,
            "min_similarity": round(min(sims), 4),
            "mean_similarity": round(sum(sims) / len(sims), 4),
            "composite_threat": latest.composite_threat,
            "corrections_applied": self.corrections_applied,
            "total_threats_detected": self.total_threats_detected,
            "signal_weights": asdict(self.weights),
            "threat_landscape": {
                "known_vectors": len(self.landscape.known_vectors),
                "last_update": self.landscape.last_update,
                "updates": self.landscape.update_count,
            },
            "latest_signals": latest.signals_summary,
        }

    # -------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------

    def _save_state(self) -> None:
        state = {
            "identity_spec_hash": hashlib.sha256(self.identity_spec.encode()).hexdigest()[:16],
            "t0_embedding": self.t0_embedding,
            "baseline_established": self.baseline_established,
            "checkpoint_counter": self.checkpoint_counter,
            "corrections_applied": self.corrections_applied,
            "total_threats_detected": self.total_threats_detected,
            "last_correction_checkpoint": self.last_correction_checkpoint,
            "weights": asdict(self.weights),
            "config": asdict(self.config),
            "snapshots": [s.to_dict() for s in self.snapshots[-100:]],
        }
        try:
            (self.state_dir / "shield_state.json").write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning("Failed to save shield state: %s", e)

    def _load_state(self) -> None:
        state_file = self.state_dir / "shield_state.json"
        if not state_file.exists():
            return
        try:
            state = json.loads(state_file.read_text())
            spec_hash = hashlib.sha256(self.identity_spec.encode()).hexdigest()[:16]
            if state.get("identity_spec_hash") != spec_hash:
                logger.info("Identity spec changed, discarding old state")
                return
            self.t0_embedding = state.get("t0_embedding")
            self.baseline_established = state.get("baseline_established", False)
            self.checkpoint_counter = state.get("checkpoint_counter", 0)
            self.corrections_applied = state.get("corrections_applied", 0)
            self.total_threats_detected = state.get("total_threats_detected", 0)
            self.last_correction_checkpoint = state.get("last_correction_checkpoint", -999)
            if "weights" in state:
                w = state["weights"]
                self.weights = SignalWeights(**{k: v for k, v in w.items() if hasattr(SignalWeights, k)})
        except Exception as e:
            logger.warning("Failed to load shield state: %s", e)


# ---------------------------------------------------------------------------
# ArmoredAgent — Drop-in wrapper
# ---------------------------------------------------------------------------

class ArmoredAgent:
    """Wraps any agent function with full cognitive armor."""

    def __init__(
        self,
        agent_fn: Callable[[str], str],
        identity_spec: str,
        objectives: list[str] = None,
        shield_config: Optional[ShieldConfig] = None,
        embedding_backend: Optional[EmbeddingBackend] = None,
        auto_baseline_probes: Optional[list[str]] = None,
    ):
        self.agent_fn = agent_fn
        self.shield = CognitiveShield(
            identity_spec=identity_spec,
            objectives=objectives,
            config=shield_config,
            embedding_backend=embedding_backend,
        )
        if auto_baseline_probes:
            self.shield.establish_baseline(agent_fn, auto_baseline_probes)

    def __call__(self, user_input: str) -> str:
        response = self.agent_fn(user_input)
        assessment = self.shield.assess(response, agent_input=user_input)
        if assessment.corrected:
            return assessment.corrected_response
        return response

    @property
    def status(self) -> dict:
        return self.shield.summary()
