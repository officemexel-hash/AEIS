"""Integration test conftest — installs the SQLite-backed PG pool shim and seeds
the union of advisor_engine + advisor_evidence + advisor_history schemas so a
single test can exercise the full engine -> history flow.

Per `08_audit_revisions.md` Revision 2 the advisor layer is PG-only in
production. The shim is permitted only as an in-memory test fixture; module
code uses the shared PG pool exclusively.
"""

from __future__ import annotations

import os
import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

# Hard-disable RBAC + rate limit during integration runs so any FastAPI router
# wired in during a test does not reject calls; matches the per-module conftest
# defaults already in use.
os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("SYLION_ADVISOR_LOCAL_ONLY", "0")
# Steer the LLM judge into deterministic stub mode: no provider keys + an
# unreachable Ollama URL so the offline stub is the only path.
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:1")

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


_INTEGRATION_TEST_SCHEMA = """
CREATE TABLE advisor_engine_recommendations (
  card_id              UUID PRIMARY KEY,
  envelope_version     TEXT NOT NULL,
  schema_version       TEXT NOT NULL,
  card_type            TEXT NOT NULL,
  parent_card_id       UUID,
  title                TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  confidence_score     DOUBLE PRECISION NOT NULL,
  confidence_label     TEXT NOT NULL,
  sources              JSONB NOT NULL,
  risk_level           TEXT NOT NULL,
  risk_explanation     TEXT,
  project_domain       TEXT NOT NULL,
  project_type         TEXT,
  project_id           UUID,
  idea_id              UUID,
  d_level              TEXT NOT NULL,
  evidence_pack_id     UUID,
  history_based        BOOLEAN NOT NULL DEFAULT 0,
  related_history_card_ids JSONB,
  historical_acceptance_rate DOUBLE PRECISION,
  expires_at           TIMESTAMPTZ,
  priority             TEXT NOT NULL DEFAULT 'normal',
  tags                 JSONB,
  dont_learn           BOOLEAN NOT NULL DEFAULT 0,
  human_gate_required  BOOLEAN NOT NULL DEFAULT 0,
  mobile_allowed       BOOLEAN NOT NULL DEFAULT 1,
  requires_biometric   BOOLEAN NOT NULL DEFAULT 0,
  push_priority        TEXT NOT NULL DEFAULT 'normal',
  used_local_fallback  BOOLEAN NOT NULL DEFAULT 0,
  local_fallback_reason TEXT,
  audit_trail_id       UUID NOT NULL,
  llm_judge_audit_id   UUID,
  operator_id          UUID NOT NULL,
  emitting_module      TEXT NOT NULL,
  body_jsonb           JSONB NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_llm_judge_audit (
  audit_id             UUID PRIMARY KEY,
  card_id              UUID,
  operator_id          UUID NOT NULL,
  judge_purpose        TEXT NOT NULL,
  model_id             TEXT NOT NULL,
  prompt_full          TEXT NOT NULL,
  response_full        TEXT NOT NULL,
  prompt_tokens        INTEGER NOT NULL,
  response_tokens      INTEGER NOT NULL,
  cost_usd             DOUBLE PRECISION NOT NULL,
  latency_ms           INTEGER NOT NULL,
  was_local_fallback   BOOLEAN NOT NULL DEFAULT 0,
  fallback_reason      TEXT,
  parent_audit_id      UUID,
  created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_rule_definitions (
  rule_id              TEXT PRIMARY KEY,
  version              INTEGER NOT NULL DEFAULT 1,
  description          TEXT NOT NULL,
  hook_event_pattern   TEXT NOT NULL,
  precondition         JSONB NOT NULL,
  recommendation_type  TEXT NOT NULL,
  default_d_level      TEXT NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT 1,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_rule_firing_history (
  firing_id            UUID PRIMARY KEY,
  rule_id              TEXT NOT NULL,
  rule_version         INTEGER NOT NULL,
  triggering_event_id  UUID NOT NULL,
  context_jsonb        JSONB NOT NULL,
  produced_card_id     UUID,
  decision_taken       TEXT NOT NULL,
  fired_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_evidence_packs (
  evidence_pack_id     UUID PRIMARY KEY,
  card_id              UUID NOT NULL,
  d_level              TEXT NOT NULL,
  pack_template        TEXT NOT NULL,
  decision_class       TEXT NOT NULL,
  domain               TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  rollback_plan        TEXT NOT NULL,
  fidelity_test        TEXT NOT NULL,
  confidence_breakdown JSONB NOT NULL,
  historical_acceptance_rate DOUBLE PRECISION,
  llm_judge_audit_ids  JSONB,
  simulation_results   JSONB,
  council_vote_id      UUID,
  risk_analysis        JSONB,
  compliance_check     JSONB,
  sentinel_signoffs    JSONB,
  attachments          JSONB,
  created_by           UUID NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL,
  finalized_at         TIMESTAMPTZ,
  status               TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE advisor_evidence_pack_signatures (
  signature_id         UUID PRIMARY KEY,
  evidence_pack_id     UUID NOT NULL,
  signer_id            UUID NOT NULL,
  signer_role          TEXT NOT NULL,
  signature_payload    TEXT NOT NULL,
  signed_at            TIMESTAMPTZ NOT NULL
);

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
    "advisor_engine.recommendations": "advisor_engine_recommendations",
    "advisor_engine.llm_judge_audit": "advisor_engine_llm_judge_audit",
    "advisor_engine.rule_definitions": "advisor_engine_rule_definitions",
    "advisor_engine.rule_firing_history": "advisor_engine_rule_firing_history",
    "advisor_evidence.evidence_packs": "advisor_evidence_packs",
    "advisor_evidence.evidence_pack_signatures": "advisor_evidence_pack_signatures",
    "advisor_history.card_actions": "advisor_history_card_actions",
    "advisor_history.learning_signals": "advisor_history_learning_signals",
    "advisor_history.card_emissions": "advisor_history_card_emissions",
}


@pytest.fixture(autouse=True)
def _integration_pg_pool(monkeypatch):
    """Combined engine + evidence + history schema on a single in-memory pool."""
    from sylion.aeis.advisor.engine.service import reset_engine_service
    from sylion.aeis.advisor.history.service import reset_history_service

    reset_engine_service()
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
    pool.execute_script(_INTEGRATION_TEST_SCHEMA)

    yield pool

    pool.close()
    reset_engine_service()
    reset_history_service()


@pytest.fixture
def captured_bus():
    """In-process event bus that captures every publish for assertion."""
    class _Bus:
        def __init__(self):
            self.events = []
            self._subs: dict[str, list] = {}

        def publish(self, event):
            self.events.append(event)
            for handler in self._subs.get(event.topic, []):
                try:
                    handler(event)
                except Exception:
                    pass
            return event.event_id

        def subscribe(self, topic, handler):
            self._subs.setdefault(topic, []).append(handler)

        def topics(self) -> list[str]:
            return [e.topic for e in self.events]

    return _Bus()


@pytest.fixture(autouse=True)
def _disable_provider_keys(monkeypatch):
    """Force the LLM judge into deterministic stub mode for integration runs."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    yield
