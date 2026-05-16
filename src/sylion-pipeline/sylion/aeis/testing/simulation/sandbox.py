"""L1: Transactional sandbox for W14 simulations.

Each sandbox owns:
  - a private OntologyStore backed by ``sim_<id>_*.db`` (BranchSnapshot),
  - a MockEventBus (no real subscribers, no production persistence),
  - a deterministic MockLLM (no Anthropic / OpenAI / Ollama calls).

After ``discard()`` the snapshot file is deleted (idempotent) so the
production database is untouched. ``cleanup_orphans()`` on engine boot
prunes stale ``sim_*_*.db`` files left behind by a previous crash.
"""
from __future__ import annotations

import logging
import time

from sylion.aeis.testing.branches.snapshot import (
    BranchSnapshot,
    DEFAULT_BASE_DIR,
)
from sylion.aeis.testing.ontology.store import OntologyStore
from sylion.aeis.testing.simulation.mock_bus import MockEventBus
from sylion.aeis.testing.simulation.mock_llm import MockLLM

log = logging.getLogger("sylion.aeis.testing.simulation.sandbox")


class TransactionalSandbox:
    """Isolated runtime for a single simulation.

    The sandbox is *file-backed by default* so the brief's
    ``sim_<id>_*.db`` requirement is met and crash recovery can clean
    up orphans by glob. Pass ``in_memory=True`` for unit tests where
    persistence isn't needed.
    """

    def __init__(
        self,
        simulation_id: str,
        llm_fixtures: dict[str, str] | None = None,
        in_memory: bool = False,
        snapshot_base_dir: str | None = None,
    ) -> None:
        if not simulation_id:
            raise ValueError("simulation_id is required")
        self.simulation_id = simulation_id
        self.ontology: OntologyStore | None = None
        self.event_bus: MockEventBus | None = None
        self.llm: MockLLM | None = None
        self.snapshot: BranchSnapshot | None = None
        self._llm_fixtures = llm_fixtures or {}
        self._in_memory = bool(in_memory)
        self._snapshot_base_dir = snapshot_base_dir
        self._started_at: float = 0.0
        self._discarded: bool = False
        self._action_count: int = 0
        self._cost_usd: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started_at:
            raise RuntimeError(f"sandbox {self.simulation_id} already started")
        self.event_bus = MockEventBus(simulation_id=self.simulation_id)
        if self._in_memory:
            self.ontology = OntologyStore(db_path=None, event_bus=self.event_bus)
            self.snapshot = None
        else:
            # File-backed snapshot so crash-recovery can prune by prefix.
            self.snapshot = BranchSnapshot.create_for(
                branch_id=self.simulation_id,
                base_dir=self._snapshot_base_dir,
            )
            self.ontology = OntologyStore(
                db_path=str(self.snapshot.path),
                event_bus=self.event_bus,
            )
        self.llm = MockLLM(fixtures=self._llm_fixtures)
        self._started_at = time.time()
        log.info(
            "sandbox started: %s (in_memory=%s, snapshot=%s)",
            self.simulation_id, self._in_memory,
            self.snapshot.path if self.snapshot else None,
        )

    def record_action(self, cost_usd: float = 0.0) -> None:
        self._action_count += 1
        if cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")
        self._cost_usd += cost_usd

    def metrics(self) -> dict:
        duration = (
            (time.time() - self._started_at) if self._started_at else 0.0
        )
        return {
            "simulation_id": self.simulation_id,
            "action_count": self._action_count,
            "cost_usd": self._cost_usd,
            "duration_s": duration,
            "events_buffered": self.event_bus.count() if self.event_bus else 0,
            "llm_calls": self.llm.call_count() if self.llm else 0,
            "discarded": self._discarded,
            "snapshot_path": str(self.snapshot.path) if self.snapshot else None,
        }

    def collect_evidence(self) -> dict:
        """Snapshot state for persistence to parent ontology."""
        if self.ontology is None or self.event_bus is None:
            raise RuntimeError("sandbox not started")
        return {
            "simulation_id": self.simulation_id,
            "metrics": self.metrics(),
            "event_log": self.event_bus.replay(),
            "ontology_health": self.ontology.health(),
            "snapshot_hash": self.snapshot.hash if self.snapshot else "",
            "snapshot_path": str(self.snapshot.path) if self.snapshot else "",
        }

    def discard(self) -> None:
        """Tear down sandbox state. Idempotent. Best-effort even on error."""
        if self._discarded:
            return
        try:
            if self.ontology is not None:
                try:
                    self.ontology.close()
                except Exception:  # pragma: no cover
                    log.exception("ontology close failed")
            if self.snapshot is not None:
                self.snapshot.discard()
        finally:
            self.ontology = None
            self.event_bus = None
            self.llm = None
            self._discarded = True
            log.info("sandbox discarded: %s", self.simulation_id)

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_orphans(
        active_simulation_ids: set[str],
        base_dir: str | None = None,
    ) -> list:
        """Delete sim_*_*.db files whose simulation_id isn't active.

        Use case: invoked at engine boot to prune residue from a crashed
        previous process. Returns the list of paths that were removed.
        """
        target = base_dir or str(DEFAULT_BASE_DIR)
        return BranchSnapshot.cleanup_orphans(
            active_branch_ids=active_simulation_ids,
            base_dir=target,
        )


__all__ = ["TransactionalSandbox"]
