"""History test conftest — installs SQLite-backed PG pool shim and seeds schema.

Per `08_audit_revisions.md` Revision 2 the history module is PG-only in
production. Tests use an in-memory SQLite-backed shim of the shared PG pool;
schema is recreated per-test for isolation.

NOTE: `advisor_history.card_emissions` is not currently in the canonical PG
schema (`sylion/db/advisor_layer.sql`). The history service writes to it via
`insert_card_emission`; surfacing this as a schema gap for the canonical SQL
is tracked outside this fix scope (Codex-owned schema).
"""

from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


_HISTORY_TEST_SCHEMA = """
CREATE TABLE advisor_history_card_actions (
  action_event_id      UUID PRIMARY KEY,
  card_id              UUID NOT NULL,
  operator_id          UUID NOT NULL,
  action               TEXT NOT NULL,
  operator_note        TEXT,
  modified_recommendation TEXT,
  context_jsonb        JSONB,
  created_human_gate_ticket_id UUID,
  created_masterplan_proposal_id UUID,
  saved_preference_id  UUID,
  triggered_soft_learning BOOLEAN NOT NULL DEFAULT 0,
  triggered_hard_learning_request BOOLEAN NOT NULL DEFAULT 0,
  performed_at         TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_history_learning_signals (
  signal_id            UUID PRIMARY KEY,
  operator_id          UUID NOT NULL,
  signal_type          TEXT NOT NULL,
  preference_key       TEXT,
  context_project_type TEXT,
  context_project_domain TEXT,
  signal_strength      DOUBLE PRECISION NOT NULL,
  source_card_id       UUID,
  source_action_event_id UUID,
  applied_to_preference BOOLEAN NOT NULL DEFAULT 0,
  applied_at           TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL,
  hard_change_status   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE advisor_history_card_emissions (
  card_id              UUID PRIMARY KEY,
  operator_id          UUID NOT NULL,
  recommendation_type  TEXT,
  project_type         TEXT,
  project_domain       TEXT,
  risk_level           TEXT,
  emitted_at           TIMESTAMPTZ NOT NULL
);
"""


_NAME_REWRITES: dict[str, str] = {
    "advisor_history.card_actions": "advisor_history_card_actions",
    "advisor_history.learning_signals": "advisor_history_learning_signals",
    "advisor_history.card_emissions": "advisor_history_card_emissions",
}


@pytest.fixture(autouse=True)
def _history_pg_pool(monkeypatch):
    from sylion.aeis.advisor.history.service import reset_history_service

    reset_history_service()

    pool = install_test_pool(monkeypatch)

    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _NAME_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    pool.execute_script(_HISTORY_TEST_SCHEMA)

    yield pool

    pool.close()
    reset_history_service()
