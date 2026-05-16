#!/usr/bin/env python3
"""
SYLION BudgetGuard — Global Daily Cost Cap

Prevents runaway billing from autonomous pipeline execution.
Per-agent caps already exist in LoopGuard; this module enforces a GLOBAL daily limit.

Architecture:
  - Tracks cumulative cost across ALL agents in a pipeline run
  - Tracks daily cost across multiple pipeline runs (persistent)
  - When daily cap is reached: HALT pipeline + CRITICAL escalation
  - Supports soft warnings at configurable thresholds (e.g. 80%)

Integration:
  - orchestrator.py: init and call record_cost() after each agent run
  - config.py: max_cost_usd_per_day, budget_warning_threshold
  - supervisor.py: GateLevel.CRITICAL on budget exceeded
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("budget_guard")


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

class HumanGateProtocol(Protocol):
    def request_approval(self, request: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CostEntry:
    """Single cost record from an agent run."""
    agent_id: str
    stage: str
    cost_usd: float
    elapsed_sec: float
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "stage": self.stage,
            "cost_usd": self.cost_usd,
            "elapsed_sec": self.elapsed_sec,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CostEntry:
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


@dataclass
class DailyBudgetState:
    """Persistent daily budget state."""
    date: str                                    # ISO date string YYYY-MM-DD
    total_cost_usd: float = 0.0
    entries: list[CostEntry] = field(default_factory=list)
    budget_exceeded: bool = False
    warning_issued: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "total_cost_usd": self.total_cost_usd,
            "budget_exceeded": self.budget_exceeded,
            "warning_issued": self.warning_issued,
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }


# ---------------------------------------------------------------------------
# BudgetGuard
# ---------------------------------------------------------------------------

class BudgetGuard:
    """Global daily cost cap enforcer.

    Usage in orchestrator:
        from budget_guard import BudgetGuard

        budget = BudgetGuard(
            max_cost_usd_per_day=50.0,
            human_gate=human_gate,
            log_dir=results_dir / "budget",
        )

        # After each agent run:
        budget.record_cost(agent_id, stage, cost_usd, elapsed)
        if budget.is_exceeded:
            # Pipeline must halt
            ...
    """

    def __init__(
        self,
        max_cost_usd_per_day: float = 50.0,
        warning_threshold: float = 0.80,
        human_gate: HumanGateProtocol | None = None,
        log_dir: Path | None = None,
    ) -> None:
        self.max_cost_usd_per_day = max_cost_usd_per_day
        self.warning_threshold = warning_threshold
        self.human_gate = human_gate
        self.log_dir = log_dir or Path("results/budget")

        self._today = date.today().isoformat()
        self._state = DailyBudgetState(date=self._today)
        self._pipeline_cost = 0.0  # Current pipeline run cost
        self._lock = threading.Lock()  # T-08: thread-safety for record_cost

        # Try to load existing daily state
        self._load_daily_state()

        logger.info(
            "BudgetGuard initialized — daily cap=$%.2f, warning at %.0f%%, "
            "today's spend so far=$%.4f",
            self.max_cost_usd_per_day,
            self.warning_threshold * 100,
            self._state.total_cost_usd,
        )

    # ------------------------------------------------------------------
    # Record cost
    # ------------------------------------------------------------------

    def record_cost(
        self, agent_id: str, stage: str,
        cost_usd: float, elapsed_sec: float = 0.0,
    ) -> bool:
        """Record agent cost and check against budget.

        Returns True if within budget, False if exceeded.
        Thread-safe via self._lock (T-08).
        """
        with self._lock:  # T-08: protect shared state from concurrent access
            # Ensure we're still on the right day
            today = date.today().isoformat()
            if today != self._today:
                self._rotate_day(today)

            entry = CostEntry(
                agent_id=agent_id, stage=stage,
                cost_usd=cost_usd, elapsed_sec=elapsed_sec,
            )
            self._state.entries.append(entry)
            self._state.total_cost_usd += cost_usd
            self._pipeline_cost += cost_usd

            # Persist
            self._save_daily_state()

            # Check warning threshold
            ratio = self._state.total_cost_usd / self.max_cost_usd_per_day
            if ratio >= self.warning_threshold and not self._state.warning_issued:
                self._state.warning_issued = True
                logger.warning(
                    "BudgetGuard WARNING: daily spend at $%.4f / $%.2f (%.0f%%)",
                    self._state.total_cost_usd,
                    self.max_cost_usd_per_day,
                    ratio * 100,
                )

            # Check hard limit
            if self._state.total_cost_usd >= self.max_cost_usd_per_day:
                self._state.budget_exceeded = True
                logger.critical(
                    "BudgetGuard EXCEEDED: daily spend $%.4f >= cap $%.2f — HALT",
                    self._state.total_cost_usd,
                    self.max_cost_usd_per_day,
                )
                self._on_budget_exceeded()
                return False

            logger.debug(
                "BudgetGuard: +$%.4f (%s/%s) → daily total $%.4f / $%.2f",
                cost_usd, agent_id, stage,
                self._state.total_cost_usd, self.max_cost_usd_per_day,
            )
            return True

    # ------------------------------------------------------------------
    # Budget exceeded handler
    # ------------------------------------------------------------------

    def _on_budget_exceeded(self) -> None:
        """Handle budget exceeded — escalate to Human Gate."""
        if not self.human_gate:
            return

        try:
            from supervisor import GateRequest, GateLevel
        except ImportError:
            logger.error("Cannot escalate — supervisor module not available.")
            return

        top_agents = self._get_top_spenders(5)
        top_str = "\n".join(
            f"  - {a}: ${c:.4f}" for a, c in top_agents
        )

        gate_request = GateRequest(
            id=f"budget-exceeded-{self._today}",
            agent_name="budget_guard",
            stage="BUDGET_GUARD",
            level=GateLevel.CRITICAL,
            title="PRZEKROCZONO DZIENNY BUDŻET API",
            description=(
                f"Globalny dzienny limit kosztów został osiągnięty!\n\n"
                f"Limit: ${self.max_cost_usd_per_day:.2f}\n"
                f"Wydano: ${self._state.total_cost_usd:.4f}\n"
                f"Agentów w tym dniu: {len(self._state.entries)}\n\n"
                f"Top 5 najdroższych agentów:\n{top_str}\n\n"
                f"Pipeline MUSI zostać wstrzymany do zatwierdzenia "
                f"przez administratora."
            ),
            action_plan=[
                {"step": "1. Przejrzyj koszty — czy są uzasadnione?"},
                {"step": "2. Jeśli tak: podnieś limit lub kontynuuj jutro"},
                {"step": "3. Jeśli nie: zbadaj runaway agent(s)"},
            ],
            risk_assessment=(
                "Dalsze uruchamianie pipeline'u bez kontroli budżetowej "
                "może prowadzić do niekontrolowanych kosztów API."
            ),
            proposed_commands=[],
            metadata={
                "daily_state": self._state.to_dict(),
                "pipeline_cost": self._pipeline_cost,
            },
        )

        try:
            self.human_gate.request_approval(gate_request)
        except Exception as e:
            logger.error("Failed to escalate budget to Human Gate: %s", e)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_exceeded(self) -> bool:
        return self._state.budget_exceeded

    @property
    def daily_total(self) -> float:
        return self._state.total_cost_usd

    @property
    def daily_remaining(self) -> float:
        return max(0, self.max_cost_usd_per_day - self._state.total_cost_usd)

    @property
    def pipeline_cost(self) -> float:
        return self._pipeline_cost

    @property
    def utilization_pct(self) -> float:
        if self.max_cost_usd_per_day <= 0:
            return 0.0
        return (self._state.total_cost_usd / self.max_cost_usd_per_day) * 100

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _get_top_spenders(self, n: int = 5) -> list[tuple[str, float]]:
        """Get top N agents by cost."""
        by_agent: dict[str, float] = {}
        for entry in self._state.entries:
            by_agent[entry.agent_id] = by_agent.get(entry.agent_id, 0) + entry.cost_usd
        return sorted(by_agent.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_cost_by_stage(self) -> dict[str, float]:
        """Get cost breakdown by pipeline stage."""
        by_stage: dict[str, float] = {}
        for entry in self._state.entries:
            by_stage[entry.stage] = by_stage.get(entry.stage, 0) + entry.cost_usd
        return by_stage

    def get_cost_by_agent(self) -> dict[str, float]:
        """Get cost breakdown by agent."""
        by_agent: dict[str, float] = {}
        for entry in self._state.entries:
            by_agent[entry.agent_id] = by_agent.get(entry.agent_id, 0) + entry.cost_usd
        return by_agent

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _rotate_day(self, new_day: str) -> None:
        """Handle day rollover — archive old state, start fresh."""
        logger.info(
            "BudgetGuard: day rotated %s → %s (yesterday: $%.4f)",
            self._today, new_day, self._state.total_cost_usd,
        )
        self._save_daily_state()  # Final save of old day
        self._today = new_day
        self._state = DailyBudgetState(date=new_day)
        self._pipeline_cost = 0.0

    def _save_daily_state(self) -> None:
        """Save current daily state to disk."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            path = self.log_dir / f"budget_{self._today}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("Failed to save budget state: %s", e)

    def _load_daily_state(self) -> None:
        """Load today's state if it exists (resume after restart)."""
        try:
            path = self.log_dir / f"budget_{self._today}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._state.total_cost_usd = data.get("total_cost_usd", 0.0)
                self._state.budget_exceeded = data.get("budget_exceeded", False)
                self._state.warning_issued = data.get("warning_issued", False)
                entries_data = data.get("entries", [])
                self._state.entries = [CostEntry.from_dict(e) for e in entries_data]
                logger.info(
                    "BudgetGuard: resumed from %s — $%.4f spent today",
                    path, self._state.total_cost_usd,
                )
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load daily state: %s — starting fresh", e)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def export_report(self) -> dict[str, Any]:
        """Export full budget state as dict."""
        return {
            "max_cost_usd_per_day": self.max_cost_usd_per_day,
            "warning_threshold": self.warning_threshold,
            "daily_total": self.daily_total,
            "daily_remaining": self.daily_remaining,
            "pipeline_cost": self.pipeline_cost,
            "utilization_pct": self.utilization_pct,
            "is_exceeded": self.is_exceeded,
            "cost_by_agent": self.get_cost_by_agent(),
            "cost_by_stage": self.get_cost_by_stage(),
            "state": self._state.to_dict(),
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests() -> None:
    import tempfile
    import unittest

    class TestBudgetGuard(unittest.TestCase):

        def setUp(self):
            self.tmpdir = tempfile.mkdtemp()
            self.log_dir = Path(self.tmpdir) / "budget"

        def tearDown(self):
            import shutil
            shutil.rmtree(self.tmpdir, ignore_errors=True)

        def test_01_init(self):
            b = BudgetGuard(max_cost_usd_per_day=50.0, log_dir=self.log_dir)
            self.assertEqual(b.daily_total, 0.0)
            self.assertFalse(b.is_exceeded)
            self.assertEqual(b.daily_remaining, 50.0)
            print("  ✓ test_01: init OK")

        def test_02_record_cost_within_budget(self):
            b = BudgetGuard(max_cost_usd_per_day=10.0, log_dir=self.log_dir)
            ok = b.record_cost("auditor_claude", "Stage 2", 2.50, 120.0)
            self.assertTrue(ok)
            self.assertEqual(b.daily_total, 2.50)
            self.assertEqual(b.daily_remaining, 7.50)
            print("  ✓ test_02: record within budget")

        def test_03_exceed_budget(self):
            b = BudgetGuard(max_cost_usd_per_day=5.0, log_dir=self.log_dir)
            b.record_cost("agent_1", "s1", 3.0)
            ok = b.record_cost("agent_2", "s2", 3.0)
            self.assertFalse(ok)
            self.assertTrue(b.is_exceeded)
            print("  ✓ test_03: exceed budget detected")

        def test_04_warning_threshold(self):
            b = BudgetGuard(
                max_cost_usd_per_day=10.0,
                warning_threshold=0.80,
                log_dir=self.log_dir,
            )
            b.record_cost("a1", "s1", 7.0)
            b.record_cost("a2", "s1", 1.5)  # 8.5 / 10 = 85% → warning
            self.assertTrue(b._state.warning_issued)
            self.assertFalse(b.is_exceeded)
            print("  ✓ test_04: warning threshold triggers")

        def test_05_persistence(self):
            b = BudgetGuard(max_cost_usd_per_day=50.0, log_dir=self.log_dir)
            b.record_cost("a1", "s1", 5.0)
            b.record_cost("a2", "s2", 3.0)

            # Load fresh instance — should resume
            b2 = BudgetGuard(max_cost_usd_per_day=50.0, log_dir=self.log_dir)
            self.assertAlmostEqual(b2.daily_total, 8.0, places=2)
            print("  ✓ test_05: persistence across restarts")

        def test_06_cost_breakdown(self):
            b = BudgetGuard(max_cost_usd_per_day=50.0, log_dir=self.log_dir)
            b.record_cost("claude", "audit", 2.0)
            b.record_cost("gpt", "audit", 3.0)
            b.record_cost("claude", "patch", 1.5)

            by_agent = b.get_cost_by_agent()
            self.assertAlmostEqual(by_agent["claude"], 3.5)
            self.assertAlmostEqual(by_agent["gpt"], 3.0)

            by_stage = b.get_cost_by_stage()
            self.assertAlmostEqual(by_stage["audit"], 5.0)
            self.assertAlmostEqual(by_stage["patch"], 1.5)
            print("  ✓ test_06: cost breakdown by agent/stage")

        def test_07_human_gate_escalation(self):
            escalated = []

            class MockGate:
                def request_approval(self, req):
                    escalated.append(req)
                    return req

            b = BudgetGuard(
                max_cost_usd_per_day=5.0,
                human_gate=MockGate(),
                log_dir=self.log_dir,
            )
            b.record_cost("a1", "s1", 6.0)  # Exceeds
            self.assertEqual(len(escalated), 1)
            from supervisor import GateLevel
            self.assertEqual(escalated[0].level, GateLevel.CRITICAL)
            print("  ✓ test_07: Human Gate CRITICAL escalation on budget exceeded")

        def test_08_export_report(self):
            b = BudgetGuard(max_cost_usd_per_day=50.0, log_dir=self.log_dir)
            b.record_cost("a1", "s1", 5.0)
            report = b.export_report()
            self.assertEqual(report["daily_total"], 5.0)
            self.assertFalse(report["is_exceeded"])
            self.assertAlmostEqual(report["utilization_pct"], 10.0)
            print("  ✓ test_08: export_report works")

    print("=" * 60)
    print("BudgetGuard — self-tests")
    print("=" * 60)
    unittest.main(module=__name__, argv=[""], exit=False, verbosity=0)
    print("=" * 60)


if __name__ == "__main__":
    _run_tests()
