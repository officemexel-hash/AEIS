"""advisor orchestration_config schema patch.

Revision ID: phase4_0002_orchestration
Revises: phase3_0002_advisor_layer
Create Date: 2026-04-26
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "phase4_0002_orchestration"
down_revision: str | Sequence[str] | None = "phase3_0002_advisor_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS advisor_orchestration;

        CREATE TABLE IF NOT EXISTS advisor_orchestration.llm_judge_routing (
          config_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id          UUID NOT NULL,
          recommendation_type  TEXT NOT NULL,
          risk_level           TEXT NOT NULL,
          model_id             TEXT NOT NULL,
          enabled              BOOLEAN NOT NULL DEFAULT true,
          created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(operator_id, recommendation_type, risk_level)
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.council_rules (
          rule_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id             UUID NOT NULL UNIQUE,
          rank_weights            JSONB NOT NULL DEFAULT '[]'::jsonb,
          critic_gate_enabled     BOOLEAN NOT NULL DEFAULT true,
          critic_gate_threshold   DOUBLE PRECISION NOT NULL DEFAULT 0.6,
          quorum_min              INTEGER NOT NULL DEFAULT 3,
          quorum_type             TEXT NOT NULL DEFAULT 'majority',
          sentinel_requirements   JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.auditor_cadence (
          cadence_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id             UUID NOT NULL UNIQUE,
          tick_frequency_seconds  INTEGER NOT NULL DEFAULT 300,
          enabled_dimensions      JSONB NOT NULL DEFAULT '[]'::jsonb,
          phase_boundary_cron     TEXT NOT NULL DEFAULT '0 */4 * * *',
          last_audit_at           TIMESTAMPTZ,
          last_10_audits          JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.fixer_protocol (
          protocol_id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id                         UUID NOT NULL UNIQUE,
          retry_budgets                       JSONB NOT NULL DEFAULT '[]'::jsonb,
          escalation_path                     JSONB NOT NULL DEFAULT '[]'::jsonb,
          max_nogo_iterations                 INTEGER NOT NULL DEFAULT 3,
          auto_revert_on_critical_security    BOOLEAN NOT NULL DEFAULT true,
          created_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.dispatch_config (
          dispatch_id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id                    UUID NOT NULL UNIQUE,
          parallelism_mode               TEXT NOT NULL DEFAULT 'wide',
          max_simultaneous               INTEGER,
          stage_allocation_rules         JSONB NOT NULL DEFAULT '[]'::jsonb,
          cost_ceiling_usd_per_hour      NUMERIC(20, 8),
          sub_agent_permission_by_type   JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.test_catalog (
          test_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id      UUID NOT NULL,
          name             TEXT NOT NULL,
          module           TEXT NOT NULL,
          suite            TEXT NOT NULL,
          test_type        TEXT NOT NULL CHECK (test_type IN ('golden', 'integration', 'e2e', 'sim')),
          status           TEXT NOT NULL DEFAULT 'never_run' CHECK (status IN ('pass', 'fail', 'skip', 'never_run')),
          last_run_at      TIMESTAMPTZ,
          last_run_output  TEXT,
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.test_catalog_runs (
          run_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id   UUID NOT NULL,
          test_id       UUID REFERENCES advisor_orchestration.test_catalog(test_id),
          suite         TEXT,
          status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'pass', 'fail')),
          output        TEXT,
          triggered_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          completed_at  TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.team_formation_rules (
          rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id     UUID NOT NULL,
          trigger_pattern TEXT NOT NULL,
          agent_types     JSONB NOT NULL DEFAULT '[]'::jsonb,
          lifetime        TEXT NOT NULL DEFAULT 'ephemeral' CHECK (lifetime IN ('ephemeral', 'persistent')),
          action          TEXT NOT NULL DEFAULT 'spawn_audit_team',
          enabled         BOOLEAN NOT NULL DEFAULT true,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.active_teams (
          team_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id   UUID NOT NULL,
          rule_id       UUID REFERENCES advisor_orchestration.team_formation_rules(rule_id),
          agent_types   JSONB NOT NULL DEFAULT '[]'::jsonb,
          current_task  TEXT,
          lifetime      TEXT NOT NULL DEFAULT 'ephemeral',
          formed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          disbanded_at  TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.event_map_cache (
          cache_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id     UUID NOT NULL UNIQUE,
          nodes           JSONB NOT NULL DEFAULT '[]'::jsonb,
          edges           JSONB NOT NULL DEFAULT '[]'::jsonb,
          generated_at    TIMESTAMPTZ,
          source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS advisor_orchestration.inter_model_conversations (
          conversation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id          UUID NOT NULL UNIQUE,
          enabled              BOOLEAN NOT NULL DEFAULT false,
          max_turns            INTEGER NOT NULL DEFAULT 4,
          arbiter_model_id     TEXT,
          disagreement_voting  BOOLEAN NOT NULL DEFAULT true,
          recent_conversations JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP SCHEMA IF EXISTS advisor_orchestration CASCADE;
        """
    )
