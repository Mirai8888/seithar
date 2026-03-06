"""
Persistent Sensor Grid -- Tier 1 CWaaS component.

Wraps seithar-cogdef scanner into a continuous monitoring service.
Ingests client data sources, scans continuously, emits alerts.

The scanner is open source. This orchestration layer is not.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ThreatAlert:
    """A detected cognitive threat in the client's environment."""
    alert_id: str
    timestamp: str
    source: str
    source_type: str  # "url", "text", "feed_item", "social_post"
    severity: float
    classification: str
    techniques: list[dict] = field(default_factory=list)
    content_hash: str = ""
    content_preview: str = ""
    raw_scanner_output: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_critical(self) -> bool:
        return self.severity >= 7.0

    @property
    def is_actionable(self) -> bool:
        return self.severity >= 4.0


@dataclass
class SensorConfig:
    """Configuration for a client sensor deployment."""
    client_id: str
    client_name: str
    sources: list[dict] = field(default_factory=list)
    scan_interval_seconds: int = 300  # 5 minutes default
    severity_threshold: float = 3.0
    alert_callback: Callable[[ThreatAlert], None] | None = None
    data_dir: Path = field(default_factory=lambda: Path.home() / "seithar-platform" / "data")
    max_content_preview: int = 200


class ContentDeduplicator:
    """Tracks seen content to avoid duplicate alerts."""

    def __init__(self, ttl_seconds: int = 86400):
        self._seen: dict[str, float] = {}
        self._ttl = ttl_seconds

    def is_duplicate(self, content_hash: str) -> bool:
        now = time.time()
        # Purge expired
        expired = [h for h, t in self._seen.items() if now - t > self._ttl]
        for h in expired:
            del self._seen[h]
        return content_hash in self._seen

    def mark_seen(self, content_hash: str) -> None:
        self._seen[content_hash] = time.time()

    @property
    def seen_count(self) -> int:
        return len(self._seen)


class IntentDriftTracker:
    """
    Stateful multi-turn intent drift detection for content sources.

    Inspired by DeepContext (arXiv:2602.16935, SS3.1, Eq. 4-7):
    tracks severity trajectories per source over sliding windows,
    detecting gradual escalation patterns that single-pass scanning misses.

    The paper shows GRU-based stateful tracking catches multi-turn
    jailbreaks at F1=0.84 with MTTD=4.24 turns. We adapt the core
    insight -- monotonic severity escalation over a window signals
    adversarial intent drift -- to content source monitoring.
    """

    def __init__(self, window_size: int = 5, drift_threshold: float = 0.6):
        # Per-source severity history
        # Ref: DeepContext SS4.3.1 -- MTTD of ~4-5 turns as detection window
        self._history: dict[str, list[tuple[float, float]]] = {}  # source -> [(timestamp, severity)]
        self._window = window_size
        self._drift_threshold = drift_threshold

    def record(self, source: str, severity: float) -> None:
        """Record a scan result severity for a source."""
        if source not in self._history:
            self._history[source] = []
        self._history[source].append((time.time(), severity))
        # Keep only recent window
        self._history[source] = self._history[source][-self._window * 3:]

    def check_drift(self, source: str) -> dict | None:
        """
        Check if a source shows adversarial intent drift.

        Returns drift info dict if detected, None otherwise.

        Detection logic (adapted from DeepContext SS3.1, Eq. 4):
        - Monotonic or near-monotonic severity increase over window
        - Each step increases severity (allowing 1 dip for noise)
        - Final severity must exceed drift_threshold
        """
        history = self._history.get(source, [])
        if len(history) < self._window:
            return None

        recent = [s for _, s in history[-self._window:]]

        # Count upward steps
        increases = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
        # Near-monotonic: allow at most 1 non-increase in window
        # Ref: DeepContext SS4.3.1 -- intent drift is not perfectly monotonic
        is_escalating = increases >= (self._window - 2)

        if not is_escalating:
            return None

        if recent[-1] < self._drift_threshold:
            return None

        # Calculate drift magnitude
        drift_magnitude = recent[-1] - recent[0]
        if drift_magnitude <= 0:
            return None

        return {
            "source": source,
            "window": recent,
            "drift_magnitude": round(drift_magnitude, 3),
            "final_severity": round(recent[-1], 3),
            "detection": "intent_drift",
            "reference": "DeepContext arXiv:2602.16935 SS3.1",
        }


class SensorGrid:
    """
    Continuous cognitive threat monitoring for a client environment.

    Wraps the seithar-cogdef scanner (open source) into a managed,
    persistent monitoring service (proprietary).

    Usage:
        config = SensorConfig(
            client_id="acme-corp",
            client_name="ACME Corporation",
            sources=[
                {"type": "rss", "url": "https://news.ycombinator.com/rss"},
                {"type": "url_list", "urls": ["https://example.com/blog"]},
                {"type": "social", "platform": "twitter", "query": "@acmecorp"},
            ],
            alert_callback=my_alert_handler,
        )
        sensor = SensorGrid(config)
        sensor.run()  # blocking, or
        alerts = sensor.scan_once()  # single pass
    """

    def __init__(self, config: SensorConfig, scanner=None):
        self.config = config
        self.dedup = ContentDeduplicator()
        self.drift_tracker = IntentDriftTracker()
        self.alerts: list[ThreatAlert] = []
        self._scanner = scanner
        self._running = False
        self._scan_count = 0
        self._alert_count = 0
        self._drift_alert_count = 0
        self._last_scan: datetime | None = None

        # Ensure data directory
        self.data_dir = config.data_dir / config.client_id
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._load_scanner()

    def _load_scanner(self) -> None:
        """Load the cogdef scanner. Falls back to import from installed location."""
        if self._scanner is not None:
            return

        try:
            # Try importing from seithar-cogdef
            import sys
            cogdef_path = Path.home() / "seithar-cogdef"
            if str(cogdef_path) not in sys.path:
                sys.path.insert(0, str(cogdef_path))
            from scanner import SeitharScanner
            self._scanner = SeitharScanner()
            logger.info("Scanner loaded from seithar-cogdef")
        except ImportError:
            logger.warning("Scanner not available. Install seithar-cogdef.")
            self._scanner = None

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _scan_text(self, text: str, source: str, source_type: str) -> ThreatAlert | None:
        """Scan a piece of text and return alert if above threshold."""
        if not self._scanner:
            return None

        content_hash = self._hash_content(text)
        if self.dedup.is_duplicate(content_hash):
            return None

        self.dedup.mark_seen(content_hash)

        try:
            result = self._scanner.scan(text)
        except Exception as e:
            logger.error("Scanner error on %s: %s", source, e)
            return None

        severity = result.get("severity", 0)

        # Record severity for intent drift tracking
        # Ref: DeepContext arXiv:2602.16935 SS3.1 -- stateful tracking
        self.drift_tracker.record(source, severity)

        # Check for multi-turn intent drift even on sub-threshold items
        # A source showing gradual escalation is suspicious even before
        # individual items cross the threshold
        drift = self.drift_tracker.check_drift(source)
        if drift and severity < self.config.severity_threshold:
            # Elevate: intent drift detected but individual item below threshold
            # Ref: DeepContext SS4.3.1 -- early detection before MTTD
            severity = max(severity, self.config.severity_threshold)
            result["drift_elevated"] = True
            result["drift_info"] = drift
            logger.warning(
                "DRIFT DETECTED [%s] magnitude=%.2f final=%.2f -- elevating alert",
                source, drift["drift_magnitude"], drift["final_severity"],
            )

        if severity < self.config.severity_threshold:
            return None

        classification = result.get("threat_classification", "Unknown")
        if drift:
            classification = f"{classification} [intent_drift]"
            self._drift_alert_count += 1

        alert = ThreatAlert(
            alert_id=f"{self.config.client_id}-{content_hash}-{int(time.time())}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            source_type=source_type,
            severity=severity,
            classification=classification,
            techniques=result.get("techniques", []),
            content_hash=content_hash,
            content_preview=text[:self.config.max_content_preview],
            raw_scanner_output=result,
        )

        return alert

    def _fetch_rss(self, source_config: dict) -> list[tuple[str, str]]:
        """Fetch RSS feed items. Returns list of (text, url) tuples."""
        import urllib.request
        import xml.etree.ElementTree as ET

        url = source_config["url"]
        items = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SeitharSensor/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                tree = ET.parse(resp)
                root = tree.getroot()

                # Handle both RSS and Atom
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for item in root.iter("item"):
                    title = item.findtext("title", "")
                    desc = item.findtext("description", "")
                    link = item.findtext("link", "")
                    items.append((f"{title}\n{desc}", link or url))

                for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                    title = entry.findtext("atom:title", "", ns)
                    summary = entry.findtext("atom:summary", "", ns)
                    link_el = entry.find("atom:link", ns)
                    link = link_el.get("href", url) if link_el is not None else url
                    items.append((f"{title}\n{summary}", link))

        except Exception as e:
            logger.error("RSS fetch failed for %s: %s", url, e)

        return items

    def _fetch_url_list(self, source_config: dict) -> list[tuple[str, str]]:
        """Fetch content from a list of URLs."""
        import urllib.request

        items = []
        for url in source_config.get("urls", []):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SeitharSensor/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    text = resp.read().decode("utf-8", errors="replace")[:10000]
                    items.append((text, url))
            except Exception as e:
                logger.error("URL fetch failed for %s: %s", url, e)
        return items

    def scan_source(self, source_config: dict) -> list[ThreatAlert]:
        """Scan a single source configuration. Returns alerts."""
        alerts = []
        source_type = source_config.get("type", "unknown")

        if source_type == "rss":
            items = self._fetch_rss(source_config)
        elif source_type == "url_list":
            items = self._fetch_url_list(source_config)
        elif source_type == "text":
            items = [(source_config["content"], source_config.get("label", "direct_text"))]
        else:
            logger.warning("Unknown source type: %s", source_type)
            return alerts

        for text, source_url in items:
            if not text or len(text.strip()) < 20:
                continue
            alert = self._scan_text(text, source_url, source_type)
            if alert:
                alerts.append(alert)

        return alerts

    def scan_once(self) -> list[ThreatAlert]:
        """Single scan pass across all configured sources."""
        self._scan_count += 1
        self._last_scan = datetime.now(timezone.utc)
        scan_alerts = []

        for source in self.config.sources:
            try:
                alerts = self.scan_source(source)
                scan_alerts.extend(alerts)
            except Exception as e:
                logger.error("Source scan failed: %s", e)

        # Process alerts
        for alert in scan_alerts:
            self._alert_count += 1
            self.alerts.append(alert)
            self._persist_alert(alert)

            if self.config.alert_callback:
                try:
                    self.config.alert_callback(alert)
                except Exception as e:
                    logger.error("Alert callback failed: %s", e)

            if alert.is_critical:
                logger.warning(
                    "CRITICAL THREAT [%s] severity=%.1f src=%s",
                    alert.classification, alert.severity, alert.source
                )

        return scan_alerts

    def run(self, max_cycles: int | None = None) -> None:
        """
        Run continuous monitoring loop.

        Args:
            max_cycles: stop after N cycles (None = run forever)
        """
        self._running = True
        cycles = 0
        logger.info(
            "Sensor grid online for %s. %d sources, interval=%ds",
            self.config.client_name,
            len(self.config.sources),
            self.config.scan_interval_seconds,
        )

        while self._running:
            self.scan_once()
            cycles += 1
            if max_cycles and cycles >= max_cycles:
                break
            time.sleep(self.config.scan_interval_seconds)

    def stop(self) -> None:
        self._running = False

    def _persist_alert(self, alert: ThreatAlert) -> None:
        """Save alert to disk."""
        alert_file = self.data_dir / f"{alert.alert_id}.json"
        with open(alert_file, "w") as f:
            json.dump(alert.to_dict(), f, indent=2)

    def status(self) -> dict:
        """Current sensor status."""
        return {
            "client_id": self.config.client_id,
            "client_name": self.config.client_name,
            "sources": len(self.config.sources),
            "scan_count": self._scan_count,
            "alert_count": self._alert_count,
            "dedup_cache_size": self.dedup.seen_count,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "running": self._running,
            "scanner_loaded": self._scanner is not None,
            "drift_alerts": self._drift_alert_count,
        }

    def get_alerts(
        self,
        min_severity: float = 0,
        limit: int = 50,
        since: datetime | None = None,
    ) -> list[dict]:
        """Query stored alerts with filters."""
        filtered = self.alerts
        if min_severity > 0:
            filtered = [a for a in filtered if a.severity >= min_severity]
        if since:
            since_str = since.isoformat()
            filtered = [a for a in filtered if a.timestamp >= since_str]
        return [a.to_dict() for a in filtered[-limit:]]
