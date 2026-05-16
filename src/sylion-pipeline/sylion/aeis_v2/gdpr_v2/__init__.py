"""SYLION AEIS v2 — GDPR DSR (Data Subject Request) handler.

Sprint 2 day 5 deliverable per ADR-001 #6 (GDPR compliance plane).

GDPR Articles 15-20 require controllers to honour 4 actions on demand:

    * Article 15 — ACCESS         (export everything we hold)
    * Article 16 — RECTIFICATION  (correct inaccurate data)
    * Article 17 — ERASURE        (right to be forgotten)
    * Article 20 — PORTABILITY    (export in machine-readable format)

This package exposes a minimal MVP service driven by an in-memory user
data store; production deployments inject a Postgres-backed store via
:func:`set_data_store`. Every action emits an audit JSONL row to
``logs/v2/gdpr_dsr.jsonl`` so the data protection officer (DPO) has an
append-only ledger of every DSR processed.

Erasure follows a soft-delete + 30-day hard-purge pattern so accidental
requests can be reverted within the GDPR controller-response window
(Article 12.3 — one month). The hard-purge cron is intentionally NOT
in this module — it lives in ``aeis_v2/gdpr_v2/hard_purge.py`` (TODO,
sprint 2 day 6).
"""

from sylion.aeis_v2.gdpr_v2.dsr import (
    DSR_ACTIONS,
    DsrAuditEntry,
    DsrResult,
    DsrService,
    InMemoryUserDataStore,
    UserDataStore,
    get_dsr_service,
    reset_dsr_service,
    set_dsr_service,
)
from sylion.aeis_v2.gdpr_v2.hard_purge import (
    DEFAULT_GRACE_PERIOD_S,
    HardPurgeCron,
    PurgeableInMemoryStore,
    PurgeableStore,
    PurgeReport,
)
from sylion.aeis_v2.gdpr_v2.pg_store import (
    DEFAULT_POOL_MAX_SIZE,
    DEFAULT_POOL_MIN_SIZE,
    PG_SCHEMA_DDL,
    PgUserDataStore,
)

__all__ = [
    "DEFAULT_GRACE_PERIOD_S",
    "DEFAULT_POOL_MAX_SIZE",
    "DEFAULT_POOL_MIN_SIZE",
    "DSR_ACTIONS",
    "DsrAuditEntry",
    "DsrResult",
    "DsrService",
    "HardPurgeCron",
    "InMemoryUserDataStore",
    "PG_SCHEMA_DDL",
    "PgUserDataStore",
    "PurgeableInMemoryStore",
    "PurgeableStore",
    "PurgeReport",
    "UserDataStore",
    "get_dsr_service",
    "reset_dsr_service",
    "set_dsr_service",
]
