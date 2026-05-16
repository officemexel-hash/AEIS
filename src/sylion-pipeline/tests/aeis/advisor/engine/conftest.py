"""Engine test conftest — installs SQLite-backed PG pool shim and seeds schema.

Per `08_audit_revisions.md` Revision 2 the engine module is PG-only in
production. Tests use an in-memory SQLite-backed shim of the shared PG pool;
schema is recreated per-test for isolation.
"""

from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


# SQLite-translatable subset of the canonical advisor_engine + advisor_evidence
# tables defined in `sylion/db/advisor_layer.sql`. Custom enums, array columns,
# triggers, and partitioning are not represented here (tests assert behaviour
# against scalar columns only). UUID/JSONB/BOOLEAN/TIMESTAMPTZ stay as-is and
# are translated by the shim.
_ENGINE_TEST_SCHEMA = """
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
"""


# Map dotted PG names used by module SQL to flat SQLite table names.
# We rewrite the shim's translate_query to also rewrite schema-qualified names.
_NAME_REWRITES: dict[str, str] = {
    "advisor_engine.recommendations": "advisor_engine_recommendations",
    "advisor_engine.llm_judge_audit": "advisor_engine_llm_judge_audit",
    "advisor_engine.rule_definitions": "advisor_engine_rule_definitions",
    "advisor_engine.rule_firing_history": "advisor_engine_rule_firing_history",
    "advisor_evidence.evidence_packs": "advisor_evidence_packs",
    "advisor_evidence.evidence_pack_signatures": "advisor_evidence_pack_signatures",
}


@pytest.fixture(autouse=True)
def _engine_pg_pool(monkeypatch):
    # Reset engine service singleton so it re-init's against the new pool.
    from sylion.aeis.advisor.engine.service import reset_engine_service

    reset_engine_service()
    monkeypatch.setenv("SYLION_ALLOW_LLM_STUB", "1")

    # Force test pool BEFORE any module code touches the pool.
    pool = install_test_pool(monkeypatch)

    # Patch the shim's query translator to rewrite schema-qualified names.
    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _NAME_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    # Now seed the test schema.
    pool.execute_script(_ENGINE_TEST_SCHEMA)

    yield pool

    pool.close()
    reset_engine_service()
