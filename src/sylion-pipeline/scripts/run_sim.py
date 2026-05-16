#!/usr/bin/env python3
"""CLI runner for AEIS advisor simulator framework.

Usage:
    python -m scripts.run_sim --persona p1_solo_indie --mode static --scenarios 50
    python -m scripts.run_sim --persona all --mode dynamic --duration 300
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure sylion-pipeline is on path when run directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sylion.sim.personas import PERSONAS, get_persona, list_persona_ids
from sylion.sim.runner import SimRunner
from sylion.sim.scenarios import STATIC_SCENARIOS, generate_dynamic_scenarios

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scripts.run_sim")


def _output_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Project root is three levels above scripts/ (scripts/ is in src/sylion-pipeline/)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    base = project_root / "docs" / "claude_parallel" / "aeis_advisor" / "_handoff" / "sim_results" / ts
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_report(base_dir: Path, persona_id: str, mode: str, report: dict) -> Path:
    persona_dir = base_dir / persona_id
    persona_dir.mkdir(parents=True, exist_ok=True)
    out_path = persona_dir / f"{mode}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.info("Wrote report: %s", out_path)
    return out_path


def _run_single(runner: SimRunner, persona_id: str, mode: str, args: argparse.Namespace) -> dict:
    persona = get_persona(persona_id)
    log.info("Running %s / %s ...", persona.id, mode)
    t0 = time.perf_counter()

    if mode == "static":
        scenarios = STATIC_SCENARIOS
        if args.scenarios and args.scenarios > len(scenarios):
            # Replicate scenarios to reach requested count
            extra = args.scenarios - len(scenarios)
            scenarios = scenarios + generate_dynamic_scenarios(extra, seed=hash(persona_id) % 2**31)
        elif args.scenarios and args.scenarios < len(scenarios):
            scenarios = scenarios[: args.scenarios]
        report = runner.run_static(persona, scenarios=scenarios)
    elif mode == "dynamic":
        report = runner.run_dynamic(persona, duration_sec=args.duration)
    elif mode == "ai_generated":
        report = runner.run_ai_generated(persona, llm_model=args.llm_model)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    elapsed = time.perf_counter() - t0
    report_dict = report.to_dict()
    report_dict["run_metadata"] = {
        "elapsed_sec": round(elapsed, 2),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "persona_name": persona.name,
        "mode": mode,
    }
    log.info(
        "Finished %s / %s in %.1fs | scenarios=%d cards=%d latency_avg=%.1fms accuracy=%.2f",
        persona.id,
        mode,
        elapsed,
        report_dict["scenarios_run"],
        report_dict["cards_emitted"],
        report_dict["decision_latency_avg"],
        report_dict["accuracy"],
    )
    return report_dict


def main() -> int:
    parser = argparse.ArgumentParser(description="AEIS Advisor Simulator")
    parser.add_argument("--persona", required=True, help="Persona ID or 'all'")
    parser.add_argument("--mode", required=True, choices=["static", "dynamic", "ai_generated", "all"])
    parser.add_argument("--scenarios", type=int, default=50, help="Number of static scenarios (default 50)")
    parser.add_argument("--duration", type=int, default=300, help="Dynamic duration in seconds (default 300)")
    parser.add_argument("--llm-model", default="qwen2.5:7b-instruct", help="Ollama model for AI mode")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override output directory")
    args = parser.parse_args()

    # Disable external API keys so the engine uses local stubs
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("GOOGLE_API_KEY", "")
    os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
    os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")

    runner = SimRunner()
    out_dir = args.output_dir or _output_dir()

    persona_ids = list_persona_ids() if args.persona == "all" else [args.persona]
    modes = ["static", "dynamic", "ai_generated"] if args.mode == "all" else [args.mode]

    all_reports: list[dict] = []
    for pid in persona_ids:
        for mode in modes:
            try:
                report = _run_single(runner, pid, mode, args)
                _write_report(out_dir, pid, mode, report)
                all_reports.append(report)
            except Exception:
                log.exception("Failed %s / %s", pid, mode)

    # Aggregate summary
    if all_reports:
        summary = _aggregate(all_reports)
        summary_path = out_dir / "aggregate_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        log.info("Aggregate summary: %s", summary_path)

    log.info("All runs complete. Results in %s", out_dir)
    return 0


def _aggregate(reports: list[dict]) -> dict:
    from collections import defaultdict

    by_persona: dict[str, list[dict]] = defaultdict(list)
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        by_persona[r["persona_id"]].append(r)
        by_mode[r["mode"]].append(r)

    def _avg(key: str, items: list[dict]) -> float:
        vals = [i[key] for i in items if isinstance(i.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    persona_summary = {}
    for pid, items in by_persona.items():
        persona_summary[pid] = {
            "avg_decision_latency_ms": round(_avg("decision_latency_avg", items), 2),
            "total_cards": sum(i["cards_emitted"] for i in items),
            "total_hg_triggered": sum(i["hg_triggered_count"] for i in items),
            "total_council_used": sum(i["council_used_count"] for i in items),
            "avg_accuracy": round(_avg("accuracy", items), 3),
        }

    mode_summary = {}
    for mode, items in by_mode.items():
        mode_summary[mode] = {
            "avg_decision_latency_ms": round(_avg("decision_latency_avg", items), 2),
            "total_cards": sum(i["cards_emitted"] for i in items),
            "avg_accuracy": round(_avg("accuracy", items), 3),
            "hg_trigger_rate": round(
                sum(i["hg_triggered_count"] for i in items) / max(sum(i["cards_emitted"] for i in items), 1), 4
            ),
        }

    return {
        "total_runs": len(reports),
        "persona_summary": persona_summary,
        "mode_summary": mode_summary,
    }


if __name__ == "__main__":
    sys.exit(main())
