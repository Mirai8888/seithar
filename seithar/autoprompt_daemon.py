"""
Autoprompt Daemon — persistent streaming research ingestion.

Not a cron job. A live feed. Polls arxiv RSS at configurable intervals,
scores papers on arrival, routes edit proposals into the context engine
and self-edit pipeline immediately. High-scoring papers trigger Telegram alerts.

Architecture:
    arxiv RSS (continuous poll)
        ↓
    ingester (score + filter)
        ↓
    context_engine (mount as nodes)
        ↓
    self_edit (route proposals)
        ↓
    shield (update threat landscape)
        ↓
    telegram (alert on high-scoring papers)

Usage:
    python3 -m seithar.autoprompt_daemon          # foreground
    python3 -m seithar.autoprompt_daemon --daemon  # background
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add autoprompt to path
AUTOPROMPT_DIR = Path.home() / "seithar-autoprompt"
if str(AUTOPROMPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOPROMPT_DIR))

POLL_INTERVAL_S = 1800  # 30 minutes
ALERT_THRESHOLD = 10     # score >= this triggers Telegram alert
STATE_FILE = Path.home() / ".seithar" / "autoprompt_daemon_state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_poll": 0, "papers_ingested": 0, "cycles_run": 0}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ingest_papers() -> list[dict]:
    """Run the autoprompt ingester and return scored papers."""
    try:
        os.chdir(str(AUTOPROMPT_DIR))
        from src.ingester import load_config, fetch_papers
        config = load_config(str(AUTOPROMPT_DIR / "config.yaml"))
        papers = fetch_papers(config)
        return papers
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        return []


def _mount_to_context_engine(papers: list[dict]) -> int:
    """Mount papers as context nodes in the engine."""
    try:
        from seithar.context_engine import ContextEngine, ContextNode, NodeType, MemoryTier

        engine = ContextEngine()
        mounted = 0
        for paper in papers:
            node_id = f"paper_{paper.get('id', '').split('/')[-1]}"
            content = (
                f"Title: {paper['title']}\n"
                f"Score: {paper['score']}\n"
                f"Keywords: {', '.join(paper.get('matched_keywords', []))}\n"
                f"Summary: {paper.get('summary', '')}\n"
                f"Link: {paper.get('link', '')}"
            )
            node = ContextNode(
                node_id=node_id,
                node_type=NodeType.OBSERVATION,
                tier=MemoryTier.RAW,
                content=content,
                source="autoprompt",
                priority=max(1, 10 - paper["score"]),  # higher score = higher priority
                tags=["research", "autoprompt"] + paper.get("matched_keywords", [])[:5],
            )
            engine.mount(node)
            mounted += 1
        engine.close()
        return mounted
    except Exception as e:
        logger.error("Context engine mount failed: %s", e)
        return 0


def _run_self_edit_cycle() -> dict:
    """Run the self-edit cycle on latest report."""
    try:
        # —
        return None
    except Exception as e:
        logger.error("Self-edit cycle failed: %s", e)
        return {"error": str(e)}


def _generate_report(papers: list[dict]) -> str:
    """Generate report and save to autoprompt output dir."""
    try:
        os.chdir(str(AUTOPROMPT_DIR))
        from src.ingester import load_config
        from src.differ import find_prompt_files, generate_suggestions

        config = load_config(str(AUTOPROMPT_DIR / "config.yaml"))
        prompts_dir = config.get("prompts_dir", "../")
        prompt_files = find_prompt_files(prompts_dir)
        suggestions = generate_suggestions(papers, prompt_files)

        output_dir = AUTOPROMPT_DIR / "output"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        report = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "papers_found": len(papers),
            "suggestions_generated": len(suggestions),
            "papers": papers[:20],
            "suggestions": suggestions,
        }
        json_path = output_dir / f"report-{timestamp}.json"
        json_path.write_text(json.dumps(report, indent=2))
        return str(json_path)
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        return ""


def _alert_high_scoring(papers: list[dict]) -> list[dict]:
    """Return papers above alert threshold."""
    return [p for p in papers if p["score"] >= ALERT_THRESHOLD]


def run_once() -> dict:
    """Execute one full ingestion + routing cycle."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "papers_found": 0,
        "papers_mounted": 0,
        "high_scoring": [],
        "self_edit": {},
        "report_path": "",
    }

    # 1. Ingest
    papers = _ingest_papers()
    result["papers_found"] = len(papers)

    if not papers:
        return result

    # 2. Generate report (creates the JSON that self-edit consumes)
    result["report_path"] = _generate_report(papers)

    # 3. Mount to context engine
    result["papers_mounted"] = _mount_to_context_engine(papers)

    # 4. Run self-edit cycle
    result["self_edit"] = _run_self_edit_cycle()

    # 5. Flag high-scoring
    result["high_scoring"] = _alert_high_scoring(papers)

    return result


def daemon_loop():
    """Main daemon loop. Runs until killed."""
    state = _load_state()
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        logger.info("Received signal %s, shutting down", sig)
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger.info("Autoprompt daemon started. Poll interval: %ds, alert threshold: %d",
                POLL_INTERVAL_S, ALERT_THRESHOLD)

    while running:
        now = time.time()
        elapsed = now - state["last_poll"]

        if elapsed >= POLL_INTERVAL_S:
            logger.info("Starting ingestion cycle...")
            result = run_once()

            state["last_poll"] = now
            state["papers_ingested"] += result["papers_found"]
            state["cycles_run"] += 1
            _save_state(state)

            logger.info(
                "Cycle complete: %d papers, %d mounted, %d high-scoring",
                result["papers_found"],
                result["papers_mounted"],
                len(result["high_scoring"]),
            )

            # Log high-scoring papers
            for paper in result["high_scoring"]:
                logger.warning(
                    "HIGH SCORE [%d]: %s — %s",
                    paper["score"], paper["title"][:80], paper.get("link", ""),
                )

        # Sleep in short intervals so we can catch signals
        for _ in range(min(60, POLL_INTERVAL_S)):
            if not running:
                break
            time.sleep(1)

    logger.info("Autoprompt daemon stopped. Cycles: %d, Papers: %d",
                state["cycles_run"], state["papers_ingested"])


def status() -> dict:
    """Return daemon status."""
    state = _load_state()
    return {
        "last_poll": datetime.fromtimestamp(state["last_poll"], tz=timezone.utc).isoformat()
        if state["last_poll"] else "never",
        "papers_ingested": state["papers_ingested"],
        "cycles_run": state["cycles_run"],
        "poll_interval_s": POLL_INTERVAL_S,
        "alert_threshold": ALERT_THRESHOLD,
        "autoprompt_dir": str(AUTOPROMPT_DIR),
        "state_file": str(STATE_FILE),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autoprompt streaming daemon")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--interval", type=int, default=1800, help="Poll interval in seconds")
    parser.add_argument("--threshold", type=int, default=10, help="Alert score threshold")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[autoprompt-daemon] %(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    global POLL_INTERVAL_S, ALERT_THRESHOLD
    POLL_INTERVAL_S = args.interval
    ALERT_THRESHOLD = args.threshold

    if args.status:
        s = status()
        for k, v in s.items():
            print(f"  {k}: {v}")
        return

    if args.once:
        result = run_once()
        print(f"Papers: {result['papers_found']}")
        print(f"Mounted: {result['papers_mounted']}")
        print(f"High-scoring: {len(result['high_scoring'])}")
        for p in result["high_scoring"]:
            print(f"  [{p['score']}] {p['title'][:80]}")
        if result["self_edit"]:
            se = result["self_edit"]
            print(f"Self-edit: {se.get('proposals_generated', 0)} proposals, {se.get('tasks_generated', 0)} tasks")
        return

    if args.daemon:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"Daemon started with PID {pid}")
            return
        os.setsid()

    daemon_loop()


if __name__ == "__main__":
    main()
