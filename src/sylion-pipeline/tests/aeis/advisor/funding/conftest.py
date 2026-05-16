"""Funding test conftest — installs SQLite-backed PG pool shim and seeds schema.

Per `08_audit_revisions.md` Revision 2 the funding module is PG-only in
production. Tests use an in-memory SQLite-backed shim of the shared PG pool;
schema is recreated per-test for isolation.
"""

from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


# SQLite-translatable subset of the canonical advisor_funding tables defined in
# `sylion/db/advisor_layer.sql`. Custom enums and array columns are not
# represented (tests assert behaviour against scalar columns + JSONB text).
_FUNDING_TEST_SCHEMA = """
CREATE TABLE advisor_funding_companies (
  company_id           UUID PRIMARY KEY,
  operator_id          UUID NOT NULL,
  is_own               BOOLEAN NOT NULL DEFAULT 1,
  legal_name           TEXT NOT NULL,
  legal_form           TEXT,
  registration_number  TEXT,
  tax_id               TEXT,
  statistical_id       TEXT,
  pkd_codes            JSONB,
  country              TEXT NOT NULL,
  region               TEXT,
  size_category        TEXT,
  employee_count       INTEGER,
  annual_revenue_usd   DOUBLE PRECISION,
  founding_date        TEXT,
  is_msme              BOOLEAN,
  description          TEXT,
  rd_budget_history    JSONB,
  innovation_certifications JSONB,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_company_persons (
  person_id            UUID PRIMARY KEY,
  company_id           UUID NOT NULL,
  full_name            TEXT NOT NULL,
  role                 TEXT NOT NULL,
  ownership_pct        DOUBLE PRECISION,
  experience_summary   TEXT,
  experience_years     INTEGER,
  qualifications       JSONB,
  team_role            TEXT,
  is_kp                BOOLEAN NOT NULL DEFAULT 0,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_grant_programs (
  program_id           UUID PRIMARY KEY,
  program_code         TEXT,
  display_name         TEXT NOT NULL,
  source               TEXT NOT NULL,
  country              TEXT NOT NULL,
  region               TEXT,
  managing_body        TEXT,
  description          TEXT,
  amount_min_usd       DOUBLE PRECISION,
  amount_max_usd       DOUBLE PRECISION,
  call_open_at         TIMESTAMPTZ,
  call_close_at        TIMESTAMPTZ,
  source_url           TEXT,
  source_documents     JSONB,
  scoring_profile_id   UUID,
  custom_criteria      JSONB,
  is_active            BOOLEAN NOT NULL DEFAULT 1,
  is_user_loaded       BOOLEAN NOT NULL DEFAULT 0,
  loaded_by            UUID,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_scoring_components (
  component_id         TEXT PRIMARY KEY,
  display_name         TEXT NOT NULL,
  description          TEXT,
  measurement_dsl      JSONB NOT NULL,
  is_system            BOOLEAN NOT NULL DEFAULT 1,
  created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_scoring_profiles (
  profile_id           UUID PRIMARY KEY,
  program_id           UUID NOT NULL,
  version              INTEGER NOT NULL DEFAULT 1,
  components           JSONB NOT NULL,
  custom_criteria      JSONB,
  total_weight         DOUBLE PRECISION NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT 1,
  created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_scoring_history (
  scoring_id           UUID PRIMARY KEY,
  operator_id          UUID NOT NULL,
  company_id           UUID,
  idea_id              UUID,
  program_id           UUID NOT NULL,
  scoring_profile_id   UUID NOT NULL,
  total_score          DOUBLE PRECISION NOT NULL,
  component_breakdown  JSONB NOT NULL,
  eligibility_floor_breached BOOLEAN NOT NULL DEFAULT 0,
  triggering_event     TEXT,
  card_id              UUID,
  llm_judge_audit_id   UUID,
  computed_at          TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_consortium_pool (
  partner_id           UUID PRIMARY KEY,
  display_name         TEXT NOT NULL,
  entity_type          TEXT NOT NULL,
  country              TEXT,
  region               TEXT,
  qualifications       JSONB,
  contact_info         JSONB,
  added_by             UUID,
  notes                TEXT,
  created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_funding_research_logs (
  log_id               UUID PRIMARY KEY,
  operator_id          UUID NOT NULL,
  research_purpose     TEXT NOT NULL,
  prompt_tokens        INTEGER NOT NULL,
  response_tokens      INTEGER NOT NULL,
  cost_usd             DOUBLE PRECISION NOT NULL,
  model_id             TEXT NOT NULL,
  external_research    BOOLEAN NOT NULL DEFAULT 0,
  related_card_id      UUID,
  performed_at         TIMESTAMPTZ NOT NULL
);
"""


_NAME_REWRITES: dict[str, str] = {
    "advisor_funding.companies": "advisor_funding_companies",
    "advisor_funding.company_persons": "advisor_funding_company_persons",
    "advisor_funding.grant_programs": "advisor_funding_grant_programs",
    "advisor_funding.scoring_components": "advisor_funding_scoring_components",
    "advisor_funding.scoring_profiles": "advisor_funding_scoring_profiles",
    "advisor_funding.scoring_history": "advisor_funding_scoring_history",
    "advisor_funding.consortium_pool": "advisor_funding_consortium_pool",
    "advisor_funding.research_logs": "advisor_funding_research_logs",
}


@pytest.fixture(autouse=True)
def _funding_pg_pool(monkeypatch):
    from sylion.aeis.advisor.funding import reset_funding_service

    reset_funding_service()

    pool = install_test_pool(monkeypatch)

    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _NAME_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    pool.execute_script(_FUNDING_TEST_SCHEMA)

    yield pool

    pool.close()
    reset_funding_service()
