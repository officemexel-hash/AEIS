"""advisor subscription quota schema patch.

Revision ID: phase4_0003_subscription_quota
Revises: phase4_0002_orchestration
Create Date: 2026-04-27
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "phase4_0003_subscription_quota"
down_revision: str | Sequence[str] | None = "phase4_0002_orchestration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS advisor_subscription.active_subscriptions (
          subscription_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          operator_id          UUID NOT NULL,
          provider_id          TEXT NOT NULL,
          plan_id              TEXT NOT NULL,
          monthly_quota_tokens BIGINT,
          monthly_quota_usd    NUMERIC(10, 2),
          reset_day_of_month   INT NOT NULL DEFAULT 1,
          models_covered       TEXT[],
          active_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
          active_until         TIMESTAMPTZ,
          monthly_fee_usd      NUMERIC(10, 2),
          is_active            BOOLEAN NOT NULL DEFAULT true
        );

        CREATE INDEX IF NOT EXISTS idx_active_subscriptions_operator
          ON advisor_subscription.active_subscriptions(operator_id, is_active);

        CREATE TABLE IF NOT EXISTS advisor_subscription.quota_usage (
          usage_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          subscription_id      UUID NOT NULL REFERENCES advisor_subscription.active_subscriptions(subscription_id),
          period_start         TIMESTAMPTZ NOT NULL,
          period_end           TIMESTAMPTZ NOT NULL,
          tokens_consumed      BIGINT NOT NULL DEFAULT 0,
          usd_consumed         NUMERIC(10, 4) NOT NULL DEFAULT 0,
          call_count           INT NOT NULL DEFAULT 0,
          last_call_at         TIMESTAMPTZ,
          UNIQUE(subscription_id, period_start)
        );

        CREATE INDEX IF NOT EXISTS idx_quota_usage_lookup
          ON advisor_subscription.quota_usage(subscription_id, period_start);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS advisor_subscription.quota_usage")
    op.execute("DROP TABLE IF EXISTS advisor_subscription.active_subscriptions")
