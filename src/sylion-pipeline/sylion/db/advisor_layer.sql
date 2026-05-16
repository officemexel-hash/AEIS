-- ============================================================================
-- AEIS Advisor Layer — PostgreSQL Schema
-- ============================================================================
-- Document version: 1.0
-- Status: Foundation DDL — do not modify without WP0 ack
-- Owner: Claude (planner)
-- Target: PostgreSQL 15+
-- Migration runner: sylion/db/pg_migration.py
-- File location: src/sylion-pipeline/sylion/db/migrations/{NNNN}_advisor_layer.sql
--
-- Design conventions:
--   1. Schema-per-module: each advisor module owns its own schema
--   2. UUIDv4 primary keys (gen_random_uuid())
--   3. JSONB for flexible/extensible payloads (with check constraints where useful)
--   4. created_at / updated_at on every mutable table (timestamptz)
--   5. Append-only audit tables (no DELETE/UPDATE allowed; enforced by trigger)
--   6. Forever retention for history (partitioned monthly for archival cost)
--   7. PG enums only for stable, small domains; everything else string + check
--   8. Foreign keys mostly within same schema; cross-schema FKs avoided
--   9. JSONB validated against proto descriptors at app layer (advisor_events.events_proto_registry)
-- ============================================================================

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";        -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- alternative UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- fuzzy search for funding/grant matching


-- ============================================================================
-- SCHEMAS (11)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS advisor_preferences;
CREATE SCHEMA IF NOT EXISTS advisor_pricing;
CREATE SCHEMA IF NOT EXISTS advisor_engine;
CREATE SCHEMA IF NOT EXISTS advisor_history;
CREATE SCHEMA IF NOT EXISTS advisor_actions;
CREATE SCHEMA IF NOT EXISTS advisor_subscription;
CREATE SCHEMA IF NOT EXISTS advisor_scaling;
CREATE SCHEMA IF NOT EXISTS advisor_funding;
CREATE SCHEMA IF NOT EXISTS advisor_evidence;
CREATE SCHEMA IF NOT EXISTS advisor_outbound;
CREATE SCHEMA IF NOT EXISTS advisor_events;

COMMENT ON SCHEMA advisor_preferences IS '3D preference matrix (user × project_type × project_domain) + catalogs';
COMMENT ON SCHEMA advisor_pricing IS 'Provider pricing adapters, profiles, ASSUMPTION-flagged tables';
COMMENT ON SCHEMA advisor_engine IS 'Issued AdvisorCards, LLM judge audit, rule engine configuration';
COMMENT ON SCHEMA advisor_history IS 'Event-sourced operator action history, learning signals (forever retention, partitioned monthly)';
COMMENT ON SCHEMA advisor_actions IS 'Card action routing audit (HG/Masterplan converters log)';
COMMENT ON SCHEMA advisor_subscription IS 'Usage metrics, subscription plans catalog, ROI calculations';
COMMENT ON SCHEMA advisor_scaling IS 'Topology recommendations, environment inventory';
COMMENT ON SCHEMA advisor_funding IS 'Funding Advisor: companies, grants, scoring profiles, history';
COMMENT ON SCHEMA advisor_evidence IS 'Evidence Packs (D3+ light, D5 full) with signatures and attachments';
COMMENT ON SCHEMA advisor_outbound IS 'Outbound adapter rules + dispatch log (Slack/email/FCM/webhook)';
COMMENT ON SCHEMA advisor_events IS 'Shared event store: proto-validated, append-only, partitioned monthly';


-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE advisor_engine.risk_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE advisor_engine.confidence_label AS ENUM ('low', 'med', 'high', 'very_high', 'certain');
CREATE TYPE advisor_engine.card_type AS ENUM ('decision', 'funding', 'security', 'scaling', 'onboarding');
CREATE TYPE advisor_engine.card_source AS ENUM ('rule_engine', 'llm_judge', 'history_match', 'council_vote', 'hybrid');
CREATE TYPE advisor_engine.decision_level AS ENUM ('D0', 'D1', 'D2', 'D3', 'D4', 'D5');
CREATE TYPE advisor_engine.priority AS ENUM ('low', 'normal', 'high', 'urgent');
CREATE TYPE advisor_engine.push_priority AS ENUM ('silent', 'low', 'normal', 'high', 'urgent');
CREATE TYPE advisor_engine.impact_confidence AS ENUM ('assumption', 'profile', 'measured');

CREATE TYPE advisor_engine.card_action AS ENUM (
  'accept', 'reject', 'modify', 'remind_later', 'not_useful',
  'convert_to_human_gate', 'convert_to_masterplan_change',
  'save_as_preference', 'dont_learn_from_this'
);

CREATE TYPE advisor_funding.grant_source AS ENUM (
  'pl_national', 'pl_regional', 'eu', 'other_country', 'private', 'custom'
);

CREATE TYPE advisor_funding.action_difficulty AS ENUM (
  'trivial', 'easy', 'moderate', 'hard', 'very_hard'
);

CREATE TYPE advisor_funding.simulation_mode AS ENUM (
  'static', 'dynamic', 'auto_generated'
);

CREATE TYPE advisor_scaling.topology_option AS ENUM (
  'local_only', 'local_plus_vps', 'vps_only', 'multi_vps', 'hybrid'
);

CREATE TYPE advisor_outbound.adapter_type AS ENUM (
  'slack', 'email', 'fcm', 'webhook', 'sms'
);

CREATE TYPE advisor_outbound.dispatch_status AS ENUM (
  'pending', 'in_flight', 'delivered', 'failed', 'dead_lettered'
);


-- ============================================================================
-- SCHEMA: advisor_preferences
-- ============================================================================

-- Catalog: project domains (14 base immutable + custom with prefix)
CREATE TABLE advisor_preferences.project_domain_catalog (
  domain_id        TEXT PRIMARY KEY,          -- e.g. 'funding', 'software', 'custom:devrel'
  display_name     TEXT NOT NULL,
  is_system        BOOLEAN NOT NULL DEFAULT false,
  is_immutable     BOOLEAN NOT NULL DEFAULT false,   -- true for 14 base domains
  description      TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by       TEXT NOT NULL DEFAULT 'system'    -- 'system' | user_id
);

COMMENT ON TABLE advisor_preferences.project_domain_catalog IS '14 base immutable domains + custom (prefix custom:*)';

INSERT INTO advisor_preferences.project_domain_catalog (domain_id, display_name, is_system, is_immutable, description) VALUES
  ('funding',            'Funding',            true, true, 'Grants, subsidies, public/private financing'),
  ('software',           'Software',           true, true, 'Software development projects'),
  ('audit',              'Audit',              true, true, 'Security/compliance/code audits'),
  ('mobile',             'Mobile',             true, true, 'Mobile applications'),
  ('infrastructure',     'Infrastructure',     true, true, 'DevOps, cloud, on-prem infra'),
  ('data_analytics',     'Data Analytics',     true, true, 'Data pipelines, BI, ML'),
  ('security',           'Security',           true, true, 'Security tooling, threat modeling'),
  ('governance',         'Governance',         true, true, 'Policies, compliance frameworks'),
  ('research',           'Research',           true, true, 'R&D, exploratory work'),
  ('marketing',          'Marketing',          true, true, 'Marketing campaigns, content, growth'),
  ('legal',              'Legal',              true, true, 'Contracts, IP, regulatory'),
  ('product_management', 'Product Management', true, true, 'Roadmaps, PRDs, prioritization'),
  ('finance',            'Finance',            true, true, 'Budgets, accounting, treasury'),
  ('operations',         'Operations',         true, true, 'Ops, support, internal tooling');

-- Catalog: project types (8 base immutable + custom)
CREATE TABLE advisor_preferences.project_type_catalog (
  type_id          TEXT PRIMARY KEY,
  display_name     TEXT NOT NULL,
  is_system        BOOLEAN NOT NULL DEFAULT false,
  is_immutable     BOOLEAN NOT NULL DEFAULT false,
  description      TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by       TEXT NOT NULL DEFAULT 'system'
);

INSERT INTO advisor_preferences.project_type_catalog (type_id, display_name, is_system, is_immutable, description) VALUES
  ('research',     'Research',     true, true, 'Exploratory, lower bar for production-readiness'),
  ('production',   'Production',   true, true, 'Customer-facing, high reliability bar'),
  ('experiment',   'Experiment',   true, true, 'A/B tests, throwaway prototypes'),
  ('poc',          'PoC',          true, true, 'Proof of concept, limited scope'),
  ('migration',    'Migration',    true, true, 'Data/system migration projects'),
  ('refactor',     'Refactor',     true, true, 'Internal code improvement, no new features'),
  ('integration',  'Integration',  true, true, '3rd party integrations'),
  ('hotfix',       'Hotfix',       true, true, 'Urgent production fixes');

-- Catalog: known preference keys (extensible, but reasoned)
CREATE TABLE advisor_preferences.preference_key_catalog (
  preference_key   TEXT PRIMARY KEY,            -- e.g. 'autonomy_level', 'cost_sensitivity'
  display_name     TEXT NOT NULL,
  description      TEXT,
  value_schema     JSONB NOT NULL,              -- JSON schema for validation
  default_value    JSONB,
  is_hard_change   BOOLEAN NOT NULL DEFAULT false,  -- true = changes require operator click (no soft learning)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE advisor_preferences.preference_key_catalog IS '10+ preference types from spec; extensible';
COMMENT ON COLUMN advisor_preferences.preference_key_catalog.is_hard_change IS 'true = changing this requires operator click (e.g. autonomy_level, blocked_providers)';

INSERT INTO advisor_preferences.preference_key_catalog (preference_key, display_name, description, value_schema, default_value, is_hard_change) VALUES
  ('autonomy_level',          'Autonomy level',          'Manual / suggest / auto',
   '{"type":"string","enum":["manual","suggest","auto"]}'::jsonb, '"suggest"'::jsonb, true),
  ('cost_sensitivity',        'Cost sensitivity',        'How aggressively to optimize for cost',
   '{"type":"string","enum":["low","medium","high"]}'::jsonb, '"medium"'::jsonb, false),
  ('preferred_providers',     'Preferred model providers', 'Ordered list of preferred provider IDs',
   '{"type":"array","items":{"type":"string"}}'::jsonb, '[]'::jsonb, false),
  ('runtime_strategy',        'Runtime strategy',        'local-only / local+VPS / hybrid / VPS-only',
   '{"type":"string","enum":["local_only","local_plus_vps","hybrid","vps_only"]}'::jsonb, '"local_only"'::jsonb, true),
  ('approval_timeout_behavior','Approval timeout behavior','Auto-approve / escalate / hold',
   '{"type":"string","enum":["auto_approve","escalate","hold"]}'::jsonb, '"hold"'::jsonb, true),
  ('council_size',            'Council size',            'Default Council size for D2+ decisions',
   '{"type":"integer","minimum":1,"maximum":11}'::jsonb, '5'::jsonb, false),
  ('budget_thresholds',       'Budget thresholds',       'Per-project default cost ceilings',
   '{"type":"object"}'::jsonb, '{}'::jsonb, false),
  ('quality_speed_cost',      'Quality / Speed / Cost trade-off', 'Slider weights (must sum to 1.0)',
   '{"type":"object","properties":{"quality":{"type":"number"},"speed":{"type":"number"},"cost":{"type":"number"}}}'::jsonb,
   '{"quality":0.4,"speed":0.3,"cost":0.3}'::jsonb, false),
  ('trusted_providers',       'Trusted providers',       'Provider IDs operator explicitly trusts',
   '{"type":"array","items":{"type":"string"}}'::jsonb, '[]'::jsonb, true),
  ('blocked_providers',       'Blocked providers',       'Provider IDs operator explicitly blocks',
   '{"type":"array","items":{"type":"string"}}'::jsonb, '[]'::jsonb, true),
  ('llm_judge_routing_override','LLM judge routing override','Per-risk-level model overrides',
   '{"type":"object"}'::jsonb, '{}'::jsonb, false),
  ('cost_ceilings',           'Cost ceilings per risk',  'Per-risk-level $ ceiling for LLM calls',
   '{"type":"object","properties":{"low":{"type":"number"},"medium":{"type":"number"},"high":{"type":"number"},"critical":{"type":"number"}}}'::jsonb,
   '{"low":0.10,"medium":0.40,"high":1.60,"critical":6.00}'::jsonb, false),
  ('funding_advisor_enabled', 'Funding Advisor enabled', 'Master toggle for funding module',
   '{"type":"boolean"}'::jsonb, 'false'::jsonb, true),
  ('funding_countries',       'Funding countries',       'Hierarchical country/region filter',
   '{"type":"array"}'::jsonb, '[]'::jsonb, true),
  ('funding_token_budget_monthly','Funding monthly token budget','Separate budget for funding research',
   '{"type":"integer","minimum":0}'::jsonb, '100000'::jsonb, false),
  ('meta_recommendations_enabled','Meta-recommendations enabled','Allow advisor to recommend changes to advisor itself',
   '{"type":"boolean"}'::jsonb, 'false'::jsonb, true);

-- 3D preferences matrix
CREATE TABLE advisor_preferences.preferences (
  user_id          UUID NOT NULL,
  project_type     TEXT,                      -- NULL = wildcard (per-user level)
  project_domain   TEXT,                      -- NULL = wildcard
  preference_key   TEXT NOT NULL REFERENCES advisor_preferences.preference_key_catalog(preference_key),
  preference_value JSONB NOT NULL,
  set_by           TEXT NOT NULL,             -- 'user' | 'soft_learning' | 'system' | 'wizard'
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, COALESCE(project_type, ''), COALESCE(project_domain, ''), preference_key)
);

CREATE INDEX idx_preferences_user ON advisor_preferences.preferences(user_id);
CREATE INDEX idx_preferences_lookup ON advisor_preferences.preferences(user_id, project_type, project_domain);
CREATE INDEX idx_preferences_key ON advisor_preferences.preferences(preference_key);

COMMENT ON TABLE advisor_preferences.preferences IS '3D matrix: per-user × per-project_type × per-project_domain. NULL = wildcard for fallback cascade.';
COMMENT ON COLUMN advisor_preferences.preferences.set_by IS 'Source of this row: user click, soft_learning auto-update, system default, onboarding wizard';

-- Audit log (append-only, enforced by trigger)
CREATE TABLE advisor_preferences.preferences_audit (
  audit_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL,
  project_type     TEXT,
  project_domain   TEXT,
  preference_key   TEXT NOT NULL,
  old_value        JSONB,                     -- NULL if INSERT
  new_value        JSONB,                     -- NULL if DELETE
  change_type      TEXT NOT NULL,             -- 'INSERT' | 'UPDATE' | 'DELETE' | 'RESET'
  changed_by       TEXT NOT NULL,
  changed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  reason           TEXT                       -- e.g. card_id that triggered soft learning
);

CREATE INDEX idx_pref_audit_user ON advisor_preferences.preferences_audit(user_id, changed_at DESC);
CREATE INDEX idx_pref_audit_key ON advisor_preferences.preferences_audit(preference_key, changed_at DESC);

-- Append-only enforcement
CREATE OR REPLACE FUNCTION advisor_preferences.audit_block_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'preferences_audit is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER preferences_audit_no_update BEFORE UPDATE ON advisor_preferences.preferences_audit
  FOR EACH ROW EXECUTE FUNCTION advisor_preferences.audit_block_modifications();
CREATE TRIGGER preferences_audit_no_delete BEFORE DELETE ON advisor_preferences.preferences_audit
  FOR EACH ROW EXECUTE FUNCTION advisor_preferences.audit_block_modifications();


-- ============================================================================
-- SCHEMA: advisor_pricing
-- ============================================================================

CREATE TABLE advisor_pricing.providers (
  provider_id      TEXT PRIMARY KEY,          -- e.g. 'anthropic', 'openai', 'google', 'ollama_local'
  display_name     TEXT NOT NULL,
  is_local         BOOLEAN NOT NULL DEFAULT false,
  is_active        BOOLEAN NOT NULL DEFAULT true,
  metadata_url     TEXT,                      -- live pricing endpoint (if any)
  metadata_auth    JSONB,                     -- auth config (encrypted at app layer)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE advisor_pricing.provider_models (
  model_id         TEXT PRIMARY KEY,          -- e.g. 'claude-sonnet-4-6', 'gpt-5'
  provider_id      TEXT NOT NULL REFERENCES advisor_pricing.providers(provider_id),
  display_name     TEXT NOT NULL,
  context_window   INTEGER,                   -- tokens
  is_local         BOOLEAN NOT NULL DEFAULT false,
  capabilities     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ['code', 'long_context', 'vision', ...]
  is_default_judge BOOLEAN NOT NULL DEFAULT false,      -- can be used as LLM-as-judge
  is_default_local BOOLEAN NOT NULL DEFAULT false,      -- preferred local fallback
  is_deprecated    BOOLEAN NOT NULL DEFAULT false,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_provider_models_provider ON advisor_pricing.provider_models(provider_id);

-- Pricing tables (with ASSUMPTION flag)
CREATE TABLE advisor_pricing.pricing_tables (
  pricing_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id             TEXT NOT NULL REFERENCES advisor_pricing.provider_models(model_id),
  input_tokens_usd_per_million  NUMERIC(20, 8),       -- nullable if assumption
  output_tokens_usd_per_million NUMERIC(20, 8),
  cache_hit_tokens_usd_per_million NUMERIC(20, 8),
  source               advisor_engine.impact_confidence NOT NULL,  -- assumption / profile / measured
  source_url           TEXT,
  is_assumption        BOOLEAN NOT NULL DEFAULT false,
  assumption_note      TEXT,
  effective_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_until      TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pricing_model_active ON advisor_pricing.pricing_tables(model_id) WHERE effective_until IS NULL;

COMMENT ON TABLE advisor_pricing.pricing_tables IS 'Pricing per model. Multiple rows per model possible across time. effective_until=NULL means current.';
COMMENT ON COLUMN advisor_pricing.pricing_tables.is_assumption IS 'When true, no live data backed this; advisor MUST flag estimates as ASSUMPTION';

-- Pricing history (every pricing read attempt logged)
CREATE TABLE advisor_pricing.pricing_history (
  history_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id         TEXT NOT NULL,
  fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  source           advisor_engine.impact_confidence NOT NULL,
  raw_response     JSONB,
  resolved_pricing_id UUID REFERENCES advisor_pricing.pricing_tables(pricing_id),
  is_assumption    BOOLEAN NOT NULL DEFAULT false,
  error_message    TEXT
);

CREATE INDEX idx_pricing_history_model ON advisor_pricing.pricing_history(model_id, fetched_at DESC);


-- ============================================================================
-- SCHEMA: advisor_engine
-- ============================================================================

-- Issued cards (the AdvisorCard recommendations themselves)
CREATE TABLE advisor_engine.recommendations (
  card_id              UUID PRIMARY KEY,
  envelope_version     TEXT NOT NULL,
  schema_version       TEXT NOT NULL,
  card_type            advisor_engine.card_type NOT NULL,
  parent_card_id       UUID REFERENCES advisor_engine.recommendations(card_id),

  -- Header fields denormalized for query speed
  title                TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  confidence_score     DOUBLE PRECISION NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
  confidence_label     advisor_engine.confidence_label NOT NULL,
  sources              advisor_engine.card_source[] NOT NULL,
  risk_level           advisor_engine.risk_level NOT NULL,
  risk_explanation     TEXT,
  project_domain       TEXT NOT NULL,
  project_type         TEXT,
  project_id           UUID,
  idea_id              UUID,
  d_level              advisor_engine.decision_level NOT NULL,
  evidence_pack_id     UUID,                  -- → advisor_evidence.evidence_packs
  history_based        BOOLEAN NOT NULL DEFAULT false,
  related_history_card_ids UUID[] DEFAULT '{}',
  historical_acceptance_rate DOUBLE PRECISION CHECK (historical_acceptance_rate >= 0.0 AND historical_acceptance_rate <= 1.0),
  expires_at           TIMESTAMPTZ,
  priority             advisor_engine.priority NOT NULL DEFAULT 'normal',
  tags                 TEXT[] DEFAULT '{}',
  dont_learn           BOOLEAN NOT NULL DEFAULT false,
  human_gate_required  BOOLEAN NOT NULL DEFAULT false,
  mobile_allowed       BOOLEAN NOT NULL DEFAULT true,
  requires_biometric   BOOLEAN NOT NULL DEFAULT false,
  push_priority        advisor_engine.push_priority NOT NULL DEFAULT 'normal',
  used_local_fallback  BOOLEAN NOT NULL DEFAULT false,
  local_fallback_reason TEXT,
  audit_trail_id       UUID NOT NULL,
  llm_judge_audit_id   UUID,                  -- → advisor_engine.llm_judge_audit
  operator_id          UUID NOT NULL,
  emitting_module      TEXT NOT NULL,

  -- Body stored as JSONB (deserialized to proto AdvisorCardEnvelope at app layer)
  body_jsonb           JSONB NOT NULL,

  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Validation invariants
  CONSTRAINT confidence_label_matches_score CHECK (
    (confidence_score < 0.50 AND confidence_label = 'low') OR
    (confidence_score >= 0.50 AND confidence_score < 0.75 AND confidence_label = 'med') OR
    (confidence_score >= 0.75 AND confidence_score < 0.90 AND confidence_label = 'high') OR
    (confidence_score >= 0.90 AND confidence_score < 0.98 AND confidence_label = 'very_high') OR
    (confidence_score >= 0.98 AND confidence_label = 'certain')
  ),
  CONSTRAINT d5_requires_evidence_pack CHECK (
    d_level <> 'D5' OR evidence_pack_id IS NOT NULL
  )
);

CREATE INDEX idx_recommendations_operator_created ON advisor_engine.recommendations(operator_id, created_at DESC);
CREATE INDEX idx_recommendations_project ON advisor_engine.recommendations(project_id, created_at DESC) WHERE project_id IS NOT NULL;
CREATE INDEX idx_recommendations_idea ON advisor_engine.recommendations(idea_id, created_at DESC) WHERE idea_id IS NOT NULL;
CREATE INDEX idx_recommendations_type_risk ON advisor_engine.recommendations(card_type, risk_level);
CREATE INDEX idx_recommendations_domain_risk ON advisor_engine.recommendations(project_domain, risk_level);
CREATE INDEX idx_recommendations_unresolved ON advisor_engine.recommendations(operator_id, created_at DESC) WHERE expires_at IS NULL OR expires_at > now();

COMMENT ON TABLE advisor_engine.recommendations IS 'Every issued AdvisorCard. Denormalized header for indexing; full body in body_jsonb.';

-- LLM judge audit (full prompt + response, forever retention per D5)
CREATE TABLE advisor_engine.llm_judge_audit (
  audit_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id              UUID,                  -- nullable if call was aborted before card emit
  operator_id          UUID NOT NULL,
  judge_purpose        TEXT NOT NULL,         -- 'rationale' | 'alternatives_ranking' | 'risk_assessment' | 'funding_scoring' | 'consortium_matching' | 'other'
  model_id             TEXT NOT NULL REFERENCES advisor_pricing.provider_models(model_id),
  prompt_full          TEXT NOT NULL,         -- complete prompt (no truncation)
  response_full        TEXT NOT NULL,         -- complete response
  prompt_tokens        INTEGER NOT NULL,
  response_tokens      INTEGER NOT NULL,
  cost_usd             NUMERIC(20, 8) NOT NULL,
  latency_ms           INTEGER NOT NULL,
  was_local_fallback   BOOLEAN NOT NULL DEFAULT false,
  fallback_reason      TEXT,
  parent_audit_id      UUID REFERENCES advisor_engine.llm_judge_audit(audit_id),  -- for ensemble calls
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_audit_card ON advisor_engine.llm_judge_audit(card_id) WHERE card_id IS NOT NULL;
CREATE INDEX idx_llm_audit_operator_created ON advisor_engine.llm_judge_audit(operator_id, created_at DESC);
CREATE INDEX idx_llm_audit_purpose_model ON advisor_engine.llm_judge_audit(judge_purpose, model_id);

COMMENT ON TABLE advisor_engine.llm_judge_audit IS 'Full prompt+response for every LLM-as-judge call. Forever retention per audit policy.';

-- Append-only on llm_judge_audit
CREATE OR REPLACE FUNCTION advisor_engine.audit_block_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'llm_judge_audit is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER llm_judge_audit_no_update BEFORE UPDATE ON advisor_engine.llm_judge_audit
  FOR EACH ROW EXECUTE FUNCTION advisor_engine.audit_block_modifications();
CREATE TRIGGER llm_judge_audit_no_delete BEFORE DELETE ON advisor_engine.llm_judge_audit
  FOR EACH ROW EXECUTE FUNCTION advisor_engine.audit_block_modifications();

-- Rule definitions (rule engine config — versioned, hot-reloadable)
CREATE TABLE advisor_engine.rule_definitions (
  rule_id              TEXT PRIMARY KEY,      -- e.g. 'split_large_module'
  version              INTEGER NOT NULL DEFAULT 1,
  description          TEXT NOT NULL,
  hook_event_pattern   TEXT NOT NULL,         -- regex matching aeis.advisor.*.* events
  precondition         JSONB NOT NULL,        -- declarative DSL (eval'd at app layer)
  recommendation_type  TEXT NOT NULL,         -- maps to RecommendationType enum
  default_d_level      advisor_engine.decision_level NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT true,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Rule firing history (which rule fired, what context, did it produce a card)
CREATE TABLE advisor_engine.rule_firing_history (
  firing_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id              TEXT NOT NULL,
  rule_version         INTEGER NOT NULL,
  triggering_event_id  UUID NOT NULL,         -- → advisor_events.events
  context_jsonb        JSONB NOT NULL,
  produced_card_id     UUID,                  -- NULL if rule fired but no card emitted (e.g. confidence too low)
  decision_taken       TEXT NOT NULL,         -- 'emit' | 'skip_low_confidence' | 'skip_blocked_provider' | etc.
  fired_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rule_firing_rule ON advisor_engine.rule_firing_history(rule_id, fired_at DESC);
CREATE INDEX idx_rule_firing_event ON advisor_engine.rule_firing_history(triggering_event_id);


-- ============================================================================
-- SCHEMA: advisor_history (event-sourced, partitioned monthly, forever retention)
-- ============================================================================

-- Card actions (operator interactions with cards — append-only)
CREATE TABLE advisor_history.card_actions (
  action_event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id              UUID NOT NULL,
  operator_id          UUID NOT NULL,
  action               advisor_engine.card_action NOT NULL,
  operator_note        TEXT,
  modified_recommendation TEXT,               -- for action='modify'
  context_jsonb        JSONB,                 -- snapshot of context when action taken
  created_human_gate_ticket_id UUID,
  created_masterplan_proposal_id UUID,
  saved_preference_id  UUID,
  triggered_soft_learning BOOLEAN NOT NULL DEFAULT false,
  triggered_hard_learning_request BOOLEAN NOT NULL DEFAULT false,
  performed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (performed_at);

-- Initial partitions (more added by maintenance job; partition manager script in WP6)
CREATE TABLE advisor_history.card_actions_2026_04 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE advisor_history.card_actions_2026_05 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE advisor_history.card_actions_2026_06 PARTITION OF advisor_history.card_actions
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_card_actions_card ON advisor_history.card_actions(card_id);
CREATE INDEX idx_card_actions_operator ON advisor_history.card_actions(operator_id, performed_at DESC);
CREATE INDEX idx_card_actions_action ON advisor_history.card_actions(action);

-- Append-only enforcement
CREATE OR REPLACE FUNCTION advisor_history.block_modifications()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'advisor_history tables are append-only';
END;
$$ LANGUAGE plpgsql;

-- Note: triggers attached per partition by partition manager (WP6)

-- Learning signals (aggregated inputs to soft learning)
CREATE TABLE advisor_history.learning_signals (
  signal_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  signal_type          TEXT NOT NULL,         -- 'card_acceptance' | 'card_rejection' | 'preference_save' | 'pattern_match' | 'dont_learn_flag'
  preference_key       TEXT,                  -- if signal hints at preference change
  context_project_type TEXT,
  context_project_domain TEXT,
  signal_strength      DOUBLE PRECISION NOT NULL CHECK (signal_strength >= 0.0 AND signal_strength <= 1.0),
  source_card_id       UUID,
  source_action_event_id UUID,
  applied_to_preference BOOLEAN NOT NULL DEFAULT false,
  applied_at           TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_learning_signals_operator ON advisor_history.learning_signals(operator_id, created_at DESC);
CREATE INDEX idx_learning_signals_unapplied ON advisor_history.learning_signals(operator_id) WHERE NOT applied_to_preference;


-- ============================================================================
-- SCHEMA: advisor_actions (action routing audit)
-- ============================================================================

CREATE TABLE advisor_actions.action_routes_audit (
  route_audit_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id              UUID NOT NULL,
  action               advisor_engine.card_action NOT NULL,
  routed_to_module     TEXT NOT NULL,         -- e.g. 'human_gate', 'masterplan', 'preferences'
  routed_target_id     UUID,                  -- ID created in target module
  payload_sent_jsonb   JSONB NOT NULL,
  response_jsonb       JSONB,
  status               TEXT NOT NULL,         -- 'success' | 'failed' | 'pending'
  error_message        TEXT,
  routed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_action_routes_card ON advisor_actions.action_routes_audit(card_id);


-- ============================================================================
-- SCHEMA: advisor_subscription
-- ============================================================================

CREATE TABLE advisor_subscription.usage_metrics (
  metric_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  provider_id          TEXT NOT NULL REFERENCES advisor_pricing.providers(provider_id),
  model_id             TEXT NOT NULL,
  period_start         TIMESTAMPTZ NOT NULL,
  period_end           TIMESTAMPTZ NOT NULL,
  total_input_tokens   BIGINT NOT NULL DEFAULT 0,
  total_output_tokens  BIGINT NOT NULL DEFAULT 0,
  total_cost_usd       NUMERIC(20, 8) NOT NULL DEFAULT 0,
  call_count           INTEGER NOT NULL DEFAULT 0,
  recorded_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_usage_metrics_op_provider ON advisor_subscription.usage_metrics(operator_id, provider_id, period_start DESC);

CREATE TABLE advisor_subscription.subscription_plans (
  plan_id              TEXT PRIMARY KEY,      -- e.g. 'anthropic_pro', 'openai_team'
  provider_id          TEXT NOT NULL REFERENCES advisor_pricing.providers(provider_id),
  display_name         TEXT NOT NULL,
  monthly_price_usd    NUMERIC(20, 8) NOT NULL,
  included_tokens      BIGINT,
  rate_limits          JSONB,
  benefits             JSONB,                 -- structured list of features
  source_url           TEXT,
  is_assumption        BOOLEAN NOT NULL DEFAULT false,
  effective_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_until      TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE advisor_subscription.roi_calculations (
  calc_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  plan_id              TEXT NOT NULL,
  observation_window_days INTEGER NOT NULL,
  observed_monthly_cost_usd NUMERIC(20, 8) NOT NULL,
  predicted_savings_usd NUMERIC(20, 8) NOT NULL,
  break_even_days      INTEGER,               -- NULL if plan never breaks even
  recommendation_card_id UUID,
  computed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE INDEX idx_active_subscriptions_operator
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

CREATE INDEX idx_quota_usage_lookup
  ON advisor_subscription.quota_usage(subscription_id, period_start);


-- ============================================================================
-- SCHEMA: advisor_scaling
-- ============================================================================

CREATE TABLE advisor_scaling.env_inventory (
  env_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  env_name             TEXT NOT NULL,
  topology             advisor_scaling.topology_option NOT NULL,
  provider             TEXT,                  -- 'local' | 'aws' | 'hetzner' | etc.
  spec_jsonb           JSONB NOT NULL,        -- CPU, RAM, GPU, etc.
  is_active            BOOLEAN NOT NULL DEFAULT true,
  cost_per_hour_usd    NUMERIC(20, 8),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE advisor_scaling.topology_history (
  history_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  project_id           UUID,
  topology             advisor_scaling.topology_option NOT NULL,
  env_count            INTEGER NOT NULL,
  was_recommended      BOOLEAN NOT NULL DEFAULT false,
  recommendation_card_id UUID,
  effective_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_until      TIMESTAMPTZ
);


-- ============================================================================
-- SCHEMA: advisor_funding (opt-in module)
-- ============================================================================

-- Companies (own + third-party)
CREATE TABLE advisor_funding.companies (
  company_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  is_own               BOOLEAN NOT NULL DEFAULT true,
  legal_name           TEXT NOT NULL,
  legal_form           TEXT,                  -- e.g. 'sp_z_o_o', 'sa', 'jdg', 'fundacja', 'limited_uk'
  registration_number  TEXT,                  -- KRS / CEIDG / etc.
  tax_id               TEXT,                  -- NIP
  statistical_id       TEXT,                  -- REGON
  pkd_codes            TEXT[],
  country              TEXT NOT NULL,         -- ISO 3166-1 alpha-2
  region               TEXT,                  -- ISO 3166-2 (e.g. PL-MZ)
  size_category        TEXT,                  -- 'micro' | 'small' | 'medium' | 'large'
  employee_count       INTEGER,
  annual_revenue_usd   NUMERIC(20, 2),
  founding_date        DATE,
  is_msme              BOOLEAN,               -- MŚP status
  description          TEXT,
  rd_budget_history    JSONB,                 -- [{year, budget_usd, ...}]
  innovation_certifications JSONB,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_companies_operator ON advisor_funding.companies(operator_id);
CREATE INDEX idx_companies_country_region ON advisor_funding.companies(country, region);
CREATE INDEX idx_companies_pkd ON advisor_funding.companies USING gin(pkd_codes);

-- Persons related to company
CREATE TABLE advisor_funding.company_persons (
  person_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           UUID NOT NULL REFERENCES advisor_funding.companies(company_id) ON DELETE CASCADE,
  full_name            TEXT NOT NULL,
  role                 TEXT NOT NULL,         -- 'president' | 'owner' | 'beneficial_owner' | 'team_member' | 'advisor'
  ownership_pct        NUMERIC(5, 2),
  experience_summary   TEXT,
  experience_years     INTEGER,
  qualifications       JSONB,                 -- list of degrees, certifications
  team_role            TEXT,                  -- e.g. 'CTO', 'lead_researcher'
  is_kp                BOOLEAN NOT NULL DEFAULT false,  -- key personnel for grant
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_company_persons_company ON advisor_funding.company_persons(company_id);
CREATE INDEX idx_company_persons_role ON advisor_funding.company_persons(role);

-- Grant programs catalog
CREATE TABLE advisor_funding.grant_programs (
  program_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_code         TEXT UNIQUE,           -- e.g. 'FENG_2.1', 'HORIZON_EIC_ACCELERATOR'
  display_name         TEXT NOT NULL,
  source               advisor_funding.grant_source NOT NULL,
  country              TEXT NOT NULL,
  region               TEXT,                  -- regional grants only
  managing_body        TEXT,                  -- 'PARP' | 'NCBR' | 'European Commission' | 'custom'
  description          TEXT,
  amount_min_usd       NUMERIC(20, 2),
  amount_max_usd       NUMERIC(20, 2),
  call_open_at         TIMESTAMPTZ,
  call_close_at        TIMESTAMPTZ,
  source_url           TEXT,
  source_documents     JSONB,                 -- attached PDFs/files (stored externally; URIs here)
  scoring_profile_id   UUID,                  -- FK below
  custom_criteria      JSONB,                 -- non-scored hard requirements (legal form, MŚP only, etc.)
  is_active            BOOLEAN NOT NULL DEFAULT true,
  is_user_loaded       BOOLEAN NOT NULL DEFAULT false,  -- true = operator loaded manually
  loaded_by            UUID,                  -- operator_id when is_user_loaded
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_grant_programs_country_region ON advisor_funding.grant_programs(country, region);
CREATE INDEX idx_grant_programs_active_open ON advisor_funding.grant_programs(call_close_at) WHERE is_active AND call_close_at > now();
CREATE INDEX idx_grant_programs_text ON advisor_funding.grant_programs USING gin(to_tsvector('simple', display_name || ' ' || COALESCE(description, '')));

-- Universal scoring components catalog (append-only)
CREATE TABLE advisor_funding.scoring_components (
  component_id         TEXT PRIMARY KEY,      -- e.g. 'eligibility', 'thematic_alignment'
  display_name         TEXT NOT NULL,
  description          TEXT,
  measurement_dsl      JSONB NOT NULL,        -- DSL describing how to compute the component
  is_system            BOOLEAN NOT NULL DEFAULT true,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO advisor_funding.scoring_components (component_id, display_name, description, measurement_dsl) VALUES
  ('eligibility',           'Eligibility',           'Formal criteria: legal form, MŚP, branch, location, age',  '{}'::jsonb),
  ('thematic_alignment',    'Thematic Alignment',    'Match between idea and grant call topic',                '{}'::jsonb),
  ('capacity',              'Capacity',              'Team experience, R&D budget, references',                '{}'::jsonb),
  ('competitive_position',  'Competitive Position',  'Comparison vs benchmark applicants in past calls',       '{}'::jsonb),
  ('regional_fit',          'Regional Fit',          'Company location vs regional grant requirements',        '{}'::jsonb),
  ('consortium_readiness',  'Consortium Readiness',  'Required consortium partners present or readily found',  '{}'::jsonb),
  ('timeline_fit',          'Timeline Fit',          'Time-to-deadline vs project/company readiness',          '{}'::jsonb);

-- Per-grant scoring profiles (the L1 insight)
CREATE TABLE advisor_funding.scoring_profiles (
  profile_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id           UUID NOT NULL REFERENCES advisor_funding.grant_programs(program_id),
  version              INTEGER NOT NULL DEFAULT 1,
  components           JSONB NOT NULL,        -- [{component_id, weight, hard_floor}, ...]
  custom_criteria      JSONB,                 -- additional grant-specific rules (DSL)
  total_weight         NUMERIC(5, 2) NOT NULL,    -- should sum to 100.00
  is_active            BOOLEAN NOT NULL DEFAULT true,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT total_weight_sums_to_100 CHECK (total_weight = 100.00)
);

CREATE INDEX idx_scoring_profiles_program ON advisor_funding.scoring_profiles(program_id) WHERE is_active;

-- Wire scoring_profile_id back into grant_programs (deferred FK)
ALTER TABLE advisor_funding.grant_programs
  ADD CONSTRAINT fk_grant_programs_scoring_profile
  FOREIGN KEY (scoring_profile_id) REFERENCES advisor_funding.scoring_profiles(profile_id);

-- Scoring history (per company × idea × grant × time)
CREATE TABLE advisor_funding.scoring_history (
  scoring_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  company_id           UUID REFERENCES advisor_funding.companies(company_id),
  idea_id              UUID,                  -- → IdeaVault
  program_id           UUID NOT NULL REFERENCES advisor_funding.grant_programs(program_id),
  scoring_profile_id   UUID NOT NULL REFERENCES advisor_funding.scoring_profiles(profile_id),
  total_score          DOUBLE PRECISION NOT NULL CHECK (total_score >= 0.0 AND total_score <= 100.0),
  component_breakdown  JSONB NOT NULL,        -- per-component scores
  eligibility_floor_breached BOOLEAN NOT NULL DEFAULT false,
  triggering_event     TEXT,                  -- 'idea_change' | 'company_data_update' | 'grant_data_refresh' | 'simulation' | 'manual_recalc'
  card_id              UUID,                  -- → advisor_engine.recommendations (if card was emitted)
  llm_judge_audit_id   UUID,
  computed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scoring_history_lookup ON advisor_funding.scoring_history(company_id, idea_id, program_id, computed_at DESC);
CREATE INDEX idx_scoring_history_operator ON advisor_funding.scoring_history(operator_id, computed_at DESC);

-- Consortium pool (potential partners — internal directory)
CREATE TABLE advisor_funding.consortium_pool (
  partner_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name         TEXT NOT NULL,
  entity_type          TEXT NOT NULL,         -- 'research_institution' | 'sme' | 'ngo' | 'industry_partner'
  country              TEXT,
  region               TEXT,
  qualifications       JSONB,
  contact_info         JSONB,
  added_by             UUID,
  notes                TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Funding research token usage tracking (separate budget enforcement)
CREATE TABLE advisor_funding.research_logs (
  log_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id          UUID NOT NULL,
  research_purpose     TEXT NOT NULL,         -- 'grant_discovery' | 'scoring_assessment' | 'consortium_search' | 'simulation'
  prompt_tokens        INTEGER NOT NULL,
  response_tokens      INTEGER NOT NULL,
  cost_usd             NUMERIC(20, 8) NOT NULL,
  model_id             TEXT NOT NULL,
  external_research    BOOLEAN NOT NULL DEFAULT false,  -- true if web/external search used
  related_card_id      UUID,
  performed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_research_logs_operator_period ON advisor_funding.research_logs(operator_id, performed_at DESC);


-- ============================================================================
-- SCHEMA: advisor_evidence
-- ============================================================================

CREATE TABLE advisor_evidence.evidence_packs (
  evidence_pack_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  card_id              UUID NOT NULL UNIQUE,
  d_level              advisor_engine.decision_level NOT NULL,
  pack_template        TEXT NOT NULL,         -- 'd3_light' | 'd5_full'
  decision_class       TEXT NOT NULL,        -- e.g. 'subscription_purchase', 'production_deploy', 'scaling_decision'
  domain               TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  rollback_plan        TEXT NOT NULL,
  fidelity_test        TEXT NOT NULL,         -- how to verify success post-decision
  confidence_breakdown JSONB NOT NULL,        -- { council_match, history_match, pricing_quality, historical_acceptance_rate }
  historical_acceptance_rate DOUBLE PRECISION,
  llm_judge_audit_ids  UUID[] DEFAULT '{}',
  simulation_results   JSONB,                 -- for funding cards
  council_vote_id      UUID,                  -- if Council voted
  attachments          JSONB DEFAULT '[]'::jsonb,  -- list of attachment refs
  created_by           UUID NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  finalized_at         TIMESTAMPTZ,
  status               TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'finalized' | 'rejected'
  CONSTRAINT pack_template_valid CHECK (pack_template IN ('d3_light', 'd5_full'))
);

CREATE INDEX idx_evidence_packs_card ON advisor_evidence.evidence_packs(card_id);
CREATE INDEX idx_evidence_packs_class ON advisor_evidence.evidence_packs(decision_class, created_at DESC);

CREATE TABLE advisor_evidence.evidence_pack_signatures (
  signature_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evidence_pack_id     UUID NOT NULL REFERENCES advisor_evidence.evidence_packs(evidence_pack_id) ON DELETE CASCADE,
  signer_id            UUID NOT NULL,
  signer_role          TEXT NOT NULL,         -- 'operator' | 'council_member' | 'governance' | 'sentinel'
  signature_payload    TEXT NOT NULL,         -- cryptographic signature
  signed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_signatures_pack ON advisor_evidence.evidence_pack_signatures(evidence_pack_id);


-- ============================================================================
-- SCHEMA: advisor_outbound
-- ============================================================================

CREATE TABLE advisor_outbound.adapters_config (
  adapter_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  adapter_type         advisor_outbound.adapter_type NOT NULL,
  display_name         TEXT NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT true,
  config_jsonb         JSONB NOT NULL,        -- channel/webhook URL/SMTP creds (encrypted at app layer)
  rate_limit_per_min   INTEGER,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE advisor_outbound.dispatch_rules (
  rule_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_name            TEXT NOT NULL,
  match_event_pattern  TEXT NOT NULL,         -- regex matching aeis.advisor.*.*
  match_predicate      JSONB NOT NULL,        -- DSL: e.g. {"risk_level": "high"}
  dispatch_to          UUID[] NOT NULL,       -- adapter_ids to dispatch to
  template             TEXT,                  -- mustache-style template for the message
  is_active            BOOLEAN NOT NULL DEFAULT true,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE advisor_outbound.dispatches (
  dispatch_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id              UUID NOT NULL REFERENCES advisor_outbound.dispatch_rules(rule_id),
  adapter_id           UUID NOT NULL REFERENCES advisor_outbound.adapters_config(adapter_id),
  source_event_id      UUID NOT NULL,
  status               advisor_outbound.dispatch_status NOT NULL DEFAULT 'pending',
  payload_jsonb        JSONB NOT NULL,
  attempt_count        INTEGER NOT NULL DEFAULT 0,
  last_error           TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  delivered_at         TIMESTAMPTZ,
  failed_at            TIMESTAMPTZ
);

CREATE INDEX idx_dispatches_status_pending ON advisor_outbound.dispatches(status) WHERE status IN ('pending', 'in_flight');
CREATE INDEX idx_dispatches_source_event ON advisor_outbound.dispatches(source_event_id);


-- ============================================================================
-- SCHEMA: advisor_events (shared event store)
-- ============================================================================

CREATE TABLE advisor_events.proto_registry (
  event_type           TEXT PRIMARY KEY,      -- e.g. 'aeis.advisor.engine.recommendation_emitted'
  proto_message_type   TEXT NOT NULL,         -- e.g. 'sylion.aeis.advisor.v1.RecommendationEmittedEvent'
  proto_descriptor     BYTEA NOT NULL,        -- serialized proto descriptor for runtime validation
  proto_version        INTEGER NOT NULL DEFAULT 1,
  is_internal          BOOLEAN NOT NULL DEFAULT true,    -- false for outbound events
  is_active            BOOLEAN NOT NULL DEFAULT true,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  deprecated_at        TIMESTAMPTZ
);

-- Main event store (partitioned monthly, forever retention)
CREATE TABLE advisor_events.events (
  event_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_no          BIGSERIAL NOT NULL,
  event_type           TEXT NOT NULL REFERENCES advisor_events.proto_registry(event_type),
  payload_jsonb        JSONB NOT NULL,        -- proto-validated at ingestion
  payload_proto        BYTEA,                 -- optional binary proto for high-perf consumers
  produced_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  producer_module      TEXT NOT NULL,         -- e.g. 'sylion.aeis.advisor.engine'
  correlation_id       UUID,                  -- ties multi-event flows
  causation_id         UUID,                  -- which event caused this one
  operator_id          UUID,                  -- nullable for system events
  project_id           UUID,
  trace_id             TEXT                   -- OpenTelemetry trace
) PARTITION BY RANGE (produced_at);

CREATE TABLE advisor_events.events_2026_04 PARTITION OF advisor_events.events
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE advisor_events.events_2026_05 PARTITION OF advisor_events.events
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE advisor_events.events_2026_06 PARTITION OF advisor_events.events
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_events_type_produced ON advisor_events.events(event_type, produced_at DESC);
CREATE INDEX idx_events_correlation ON advisor_events.events(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX idx_events_operator ON advisor_events.events(operator_id, produced_at DESC) WHERE operator_id IS NOT NULL;
CREATE INDEX idx_events_project ON advisor_events.events(project_id, produced_at DESC) WHERE project_id IS NOT NULL;

-- Validation failure log
CREATE TABLE advisor_events.validation_failures (
  failure_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  attempted_event_type TEXT NOT NULL,
  attempted_payload    JSONB NOT NULL,
  validation_errors    JSONB NOT NULL,
  producer_module      TEXT NOT NULL,
  failed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_validation_failures_type ON advisor_events.validation_failures(attempted_event_type, failed_at DESC);


-- ============================================================================
-- HELPER FUNCTIONS (preference resolution cascade)
-- ============================================================================

CREATE OR REPLACE FUNCTION advisor_preferences.resolve_preference(
  p_user_id UUID,
  p_project_type TEXT,
  p_project_domain TEXT,
  p_preference_key TEXT
) RETURNS JSONB AS $$
DECLARE
  v_value JSONB;
BEGIN
  -- Level 1: most specific (user, type, domain)
  SELECT preference_value INTO v_value
  FROM advisor_preferences.preferences
  WHERE user_id = p_user_id
    AND project_type = p_project_type
    AND project_domain = p_project_domain
    AND preference_key = p_preference_key;
  IF v_value IS NOT NULL THEN RETURN v_value; END IF;

  -- Level 2: (user, type, NULL)
  SELECT preference_value INTO v_value
  FROM advisor_preferences.preferences
  WHERE user_id = p_user_id
    AND project_type = p_project_type
    AND project_domain IS NULL
    AND preference_key = p_preference_key;
  IF v_value IS NOT NULL THEN RETURN v_value; END IF;

  -- Level 3: (user, NULL, domain)
  SELECT preference_value INTO v_value
  FROM advisor_preferences.preferences
  WHERE user_id = p_user_id
    AND project_type IS NULL
    AND project_domain = p_project_domain
    AND preference_key = p_preference_key;
  IF v_value IS NOT NULL THEN RETURN v_value; END IF;

  -- Level 4: (user, NULL, NULL) — per-user default
  SELECT preference_value INTO v_value
  FROM advisor_preferences.preferences
  WHERE user_id = p_user_id
    AND project_type IS NULL
    AND project_domain IS NULL
    AND preference_key = p_preference_key;
  IF v_value IS NOT NULL THEN RETURN v_value; END IF;

  -- Level 5: system default from catalog
  SELECT default_value INTO v_value
  FROM advisor_preferences.preference_key_catalog
  WHERE preference_key = p_preference_key;
  RETURN v_value;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION advisor_preferences.resolve_preference IS '4-level fallback cascade + system default. Used by advisor.engine to resolve effective preference.';


-- ============================================================================
-- LISTEN/NOTIFY infrastructure
-- ============================================================================

CREATE OR REPLACE FUNCTION advisor_events.notify_event_inserted()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify(
    'advisor_events_' || TG_TABLE_NAME,
    json_build_object(
      'event_id', NEW.event_id,
      'event_type', NEW.event_type,
      'sequence_no', NEW.sequence_no,
      'produced_at', NEW.produced_at
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: triggers attached per partition by partition manager script (WP6)


-- ============================================================================
-- GRANTS (placeholder — adjust per existing RBAC convention)
-- ============================================================================

-- The advisor_* schemas are owned by the advisor service role.
-- Adjust grants per existing sylion RBAC patterns (see existing migrations).

-- ============================================================================
-- END OF MIGRATION


-- ============================================================================
-- SCHEMA: advisor_orchestration  (Section J — Meta-Orchestration Config)
-- Added: 2026-04-26  Owner: Claude (Section J)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS advisor_orchestration;
COMMENT ON SCHEMA advisor_orchestration IS 'Meta-orchestration controls: LLM routing, Council rules, auditor cadence, fixer protocol, dispatch, test catalog, team formation, event map, inter-model conversations';

-- Generic KV store for all J1-J9 config blobs (simple, avoids 8 separate tables)
CREATE TABLE IF NOT EXISTS advisor_orchestration.config_kv (
  config_key   TEXT PRIMARY KEY,
  config_value JSONB NOT NULL DEFAULT '{}',
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- J6: Test catalog entries
CREATE TABLE IF NOT EXISTS advisor_orchestration.test_catalog (
  test_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  module       TEXT NOT NULL,
  suite        TEXT NOT NULL,
  test_type    TEXT NOT NULL CHECK (test_type IN ('golden', 'integration', 'e2e', 'sim')),
  status       TEXT NOT NULL DEFAULT 'never_run' CHECK (status IN ('pass', 'fail', 'skip', 'never_run')),
  last_run_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_test_catalog_module ON advisor_orchestration.test_catalog(module);
CREATE INDEX IF NOT EXISTS idx_test_catalog_status ON advisor_orchestration.test_catalog(status);

-- J6: Test catalog runs
CREATE TABLE IF NOT EXISTS advisor_orchestration.test_catalog_runs (
  run_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  test_id      UUID REFERENCES advisor_orchestration.test_catalog(test_id),
  suite        TEXT,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'pass', 'fail')),
  output       TEXT,
  triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_test_runs_test_id ON advisor_orchestration.test_catalog_runs(test_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_status ON advisor_orchestration.test_catalog_runs(status);

-- J7: Team formation rules
CREATE TABLE IF NOT EXISTS advisor_orchestration.team_formation_rules (
  rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trigger_pattern TEXT NOT NULL,
  agent_types     JSONB NOT NULL DEFAULT '[]',
  lifetime        TEXT NOT NULL DEFAULT 'ephemeral' CHECK (lifetime IN ('ephemeral', 'persistent')),
  action          TEXT NOT NULL DEFAULT 'spawn_audit_team',
  enabled         BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- J7: Active teams
CREATE TABLE IF NOT EXISTS advisor_orchestration.active_teams (
  team_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id      UUID REFERENCES advisor_orchestration.team_formation_rules(rule_id),
  agent_types  JSONB NOT NULL DEFAULT '[]',
  current_task TEXT,
  lifetime     TEXT NOT NULL DEFAULT 'ephemeral',
  formed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  disbanded_at TIMESTAMPTZ
);

-- ============================================================================
-- END OF ORCHESTRATION EXTENSION
-- ============================================================================


-- ============================================================================
-- ORCHESTRATION INTEGRATION PATCH (Codex, 2026-04-26)
-- ============================================================================

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

ALTER TABLE advisor_orchestration.test_catalog
  ADD COLUMN IF NOT EXISTS operator_id UUID,
  ADD COLUMN IF NOT EXISTS last_run_output TEXT,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE advisor_orchestration.test_catalog_runs
  ADD COLUMN IF NOT EXISTS operator_id UUID;

ALTER TABLE advisor_orchestration.team_formation_rules
  ADD COLUMN IF NOT EXISTS operator_id UUID,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

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
  conversation_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id            UUID NOT NULL UNIQUE,
  enabled                BOOLEAN NOT NULL DEFAULT false,
  max_turns              INTEGER NOT NULL DEFAULT 4,
  arbiter_model_id       TEXT,
  disagreement_voting    BOOLEAN NOT NULL DEFAULT true,
  recent_conversations   JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE advisor_orchestration.active_teams
  ADD COLUMN IF NOT EXISTS operator_id UUID;
