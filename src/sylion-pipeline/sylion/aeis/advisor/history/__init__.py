"""SYLION AEIS Advisor — History module.

Event-sourced learning loop:
- records `card_actions` append-only (per partition in PG; single table in SQLite MVP)
- aggregates `learning_signals` from operator behaviour (rolling window of 5)
- exposes confidence components (history_match, historical_acceptance) to the engine
- runs soft learning (auto-apply) and hard learning (operator-confirmed) flows
- honours `dont_learn=true` cards by emitting `skip_learning_recorded` and
  skipping signal aggregation entirely

Architecture refs:
- master_spec §4 lifecycle 14-16; §9.3 soft learning rules
- 02_postgresql_schema.sql `advisor_history.*`
- 03_module_manifests.md §9
- 07_event_taxonomy.md §4.9
- 08_audit_revisions.md (BINDING — sync-first, threading.Lock singletons, MVP SQLite)
"""

from sylion.aeis.advisor.history.service import (
    AdvisorHistoryService,
    get_history_service,
    reset_history_service,
)

__all__ = ["AdvisorHistoryService", "get_history_service", "reset_history_service"]
