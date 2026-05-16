/* ============================================================
   SYLION AEIS v3.5 — Complete TypeScript Type Definitions
   ============================================================ */

/* ------------------------------------------------------------------
   Enums / Union literals
   ------------------------------------------------------------------ */

/** Module class taxonomy — A (core) through O (cellular) */
export type ModuleClass =
  | "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H"
  | "I" | "J" | "K" | "L" | "M" | "N" | "O";

/** Module lifecycle stages */
export type ModuleLifecycle =
  | "draft" | "build" | "validate" | "shadow"
  | "dual" | "cutover" | "stable" | "deprecated";

/** Decision class ladder D0–D5 */
export type DecisionClass = "D0" | "D1" | "D2" | "D3" | "D4" | "D5";

/** Skill lifecycle */
export type SkillLifecycle = "DRAFT" | "TESTING" | "PUBLISHED" | "DEPRECATED";

/** Project phases */
export type ProjectPhase = "idea" | "design" | "build" | "validate" | "shadow" | "stable";

/** Idea maturity */
export type IdeaMaturity = "raw" | "scoped" | "validated" | "promoted";

/** Readiness stages for initiative tracking */
export type ReadinessStage =
  | "IDEA"
  | "SCOPE"
  | "SKILLS_ASSETS"
  | "CANON_GOVERNANCE"
  | "TEST_SANDBOX"
  | "SHADOW_CUTOVER_READY"
  | "ACTIVE_MONITORED";

/** Instance operational mode */
export type InstanceMode =
  | "INITIAL_SETUP"
  | "NORMAL"
  | "INCIDENT"
  | "REBUILD"
  | "DEVICE_LAB";

/* ------------------------------------------------------------------
   Core domain interfaces
   ------------------------------------------------------------------ */

/** SYLION LEGO module */
export interface Module {
  id: string;
  name: string;
  kind: ModuleClass;
  package: string;
  lifecycle: ModuleLifecycle;
  owner_plan: string;
  description: string;
  contract_state: "frozen" | "draft" | "breaking";
  dependencies: string[];
  risk: "low" | "medium" | "high";
}

/** SYLION autonomous agent */
export interface Agent {
  id: string;
  name: string;
  role: string;
  status: "idle" | "active" | "busy" | "error";
  department: string;
  level: number;
  current_task: string;
  health: number;
  domain: string;
}

/** Decision in the D0–D5 ladder */
export interface Decision {
  id: string;
  decision_class: DecisionClass;
  title: string;
  description: string;
  status: "pending" | "approved" | "rejected" | "escalated" | "auto_approved";
  proposed_by: string;
  required_approvals: string[];
  created_at: string;
  resolved_at?: string;
  risk: "none" | "low" | "medium" | "high" | "critical";
}

/** Evidence pack for governance */
export interface EvidencePack {
  id: string;
  proposal_id: string;
  decision_class: string;
  status: "draft" | "validated" | "submitted" | "archived";
  artefacts_count: number;
  fidelity: number;
  created_at: string;
}

/** Skill in the SYLION skills hub */
export interface Skill {
  id: string;
  name: string;
  domain: string;
  lifecycle: SkillLifecycle;
  usage_count: number;
  compatibility: string[];
  demand: number;
}

/** Project in the SYLION portfolio */
export interface Project {
  id: string;
  name: string;
  phase: ProjectPhase;
  progress: number;
  risk: "low" | "medium" | "high" | "critical";
  owner: string;
  agents: string[];
  status: "active" | "paused" | "blocked" | "completed";
  governance: "clear" | "pending_review" | "blocked";
}

/** Idea from the Idea Vault */
export interface Idea {
  id: string;
  title: string;
  category: string;
  maturity: IdeaMaturity;
  next_action: string;
  created_at: string;
  source: string;
}

/** Pipeline stage for the hero visualization */
export interface PipelineStage {
  id: string;
  name: string;
  label: string;
  status: "completed" | "active" | "blocked" | "pending";
  progress: number;
  description: string;
}

/** Governance alert / item */
export interface GovernanceAlert {
  id: string;
  type: "approval" | "human_gate" | "evidence" | "contract_freeze" | "rollback" | "compliance";
  severity: "info" | "warning" | "critical";
  title: string;
  description: string;
  decision_class: DecisionClass;
  status: "pending" | "approved" | "rejected" | "escalated";
  created_at: string;
}

/** Event log entry */
export interface EventLog {
  id: string;
  topic: string;
  source_module: string;
  timestamp: string;
  payload?: string;
}

/** Single telemetry data point — supports both simple and multi-metric modes */
export interface TelemetryPoint {
  timestamp: string;
  value: number;
  label: string;
  /** Chart fields populated by local data generators */
  time: string;
  events: number;
  tasks: number;
  load: number;
}

/** Initiative tracked through readiness stages */
export interface Initiative {
  id: string;
  name: string;
  stage: ReadinessStage;
  score: number;
  blockers: string[];
}

/* ------------------------------------------------------------------
   Legacy-compatible aliases (keep existing components compiling)
   ------------------------------------------------------------------ */

/** @deprecated Use GovernanceAlert instead */
export type GovernanceItem = GovernanceAlert;

/* ------------------------------------------------------------------
   Supporting domain types
   ------------------------------------------------------------------ */

/** KPI card data */
export interface KPI {
  label: string;
  value: string | number;
  change: number;
  trend: "up" | "down" | "stable";
  icon: string;
}

/** Book (Ksiega) section */
export interface BookSection {
  id: string;
  title: string;
  status: "complete" | "partial" | "missing" | "draft";
  coverage: number;
  linked_modules: string[];
  canonical_decisions: number;
}

/* ------------------------------------------------------------------
   Evidence Spine
   ------------------------------------------------------------------ */

export interface EvidenceSpineEntry {
  seq: number;
  hash: string;
  prev_hash: string;
  timestamp: string;
  source_module: string;
  action: string;
  payload_summary: string;
  valid: boolean;
}

export interface EvidenceSpineChain {
  chain_valid: boolean;
  entries: EvidenceSpineEntry[];
  total_entries: number;
  chain_length: number;
  oldest_entry: string;
  latest_entry: string;
  head_hash: string;
}

/* ------------------------------------------------------------------
   Autonomy Rollout
   ------------------------------------------------------------------ */

export type AutonomyStageKey = "OBSERVE" | "PROPOSE" | "SANDBOX" | "LIMITED_PROD" | "FULL_GOVERNED";

export interface AutonomyStage {
  key: AutonomyStageKey;
  label: string;
  description: string;
  gate_id: string;
  gate_requirement: string;
}

export interface AutonomyGate {
  gate_id: string;
  title: string;
  requirement: string;
  status: "passed" | "failed" | "pending";
  progress: number;
  current_value: string;
}

export interface AutonomyAction {
  id: string;
  type: string;
  stage: AutonomyStageKey;
  title: string;
  result: "success" | "failure" | "escalated";
  timestamp: string;
}

/* ------------------------------------------------------------------
   Performance Budgets
   ------------------------------------------------------------------ */

export interface PerformanceBudget {
  module_id: string;
  module_name: string;
  class: ModuleClass;
  max_lines: number;
  actual_lines: number;
  max_response_ms: number;
  actual_response_ms: number;
  max_memory_mb: number;
  actual_memory_mb: number;
  status: "within" | "warning" | "over";
}

export interface BudgetViolation {
  module_id: string;
  module_name: string;
  metric: string;
  limit: number;
  actual: number;
  over_by: number;
  severity: "warning" | "critical";
}

export interface BudgetClassSummary {
  class: string;
  module_count: number;
  within: number;
  warning: number;
  over: number;
  avg_utilization: number;
}

/* ------------------------------------------------------------------
   System Health
   ------------------------------------------------------------------ */

export type ModuleHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ModuleHealth {
  module_id: string;
  module_class: ModuleClass;
  status: ModuleHealthStatus;
  last_heartbeat: string;
  heartbeat_age_ms: number;
  custom_threshold_ms: number | null;
}

export interface ModuleHealthSummary {
  overall: "ALL HEALTHY" | "DEGRADED" | "UNHEALTHY";
  healthy: number;
  degraded: number;
  unhealthy: number;
  unknown: number;
  avg_heartbeat_age_ms: number;
  modules: ModuleHealth[];
}

/* ------------------------------------------------------------------
   Rebuildability
   ------------------------------------------------------------------ */

export interface RebuildPlanStep {
  seq: number;
  module_name: string;
  package: string;
  contract_version: string;
  dependencies: string[];
  status: "ready" | "in_progress" | "blocked" | "completed";
}

export interface CFTRun {
  id: string;
  fidelity_score: number;
  timestamp: string;
  passed: boolean;
  modules_tested: number;
  duration_ms: number;
}

export interface LPWCheckpoint {
  id: string;
  hash: string;
  module_count: number;
  created_at: string;
  valid: boolean;
  fidelity_score: number;
}

/* ------------------------------------------------------------------
   Skill Demand Analysis
   ------------------------------------------------------------------ */

export interface SkillDemandSignal {
  skill_id: string;
  skill_name: string;
  domain: string;
  demand_score: number;
  supply_score: number;
  trend: "rising" | "stable" | "declining";
  gap: number;
  lifecycle: SkillLifecycle;
}

export interface DemandPredictionPoint {
  day: string;
  predicted_demand: number;
}

export interface SkillDemandAnalysis {
  signals: SkillDemandSignal[];
  predictions: DemandPredictionPoint[];
  generated_at: string;
}

/* ------------------------------------------------------------------
   Model Router / Cognitive
   ------------------------------------------------------------------ */

export type ModelProvider = "openai" | "anthropic" | "google" | "meta" | "mistral" | "cohere" | "local";

export interface ModelInfo {
  id: string;
  name: string;
  provider: ModelProvider;
  capabilities: string[];
  cost_per_1k_input: number;
  cost_per_1k_output: number;
  context_window: number;
  max_output: number;
  avg_latency_ms: number;
  status: "active" | "idle" | "rate_limited" | "error";
  requests_24h: number;
  tokens_in_24h: number;
  tokens_out_24h: number;
  cost_24h: number;
  sparkline: number[];
}

export interface ModelCostRow {
  model_id: string;
  model_name: string;
  provider: ModelProvider;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  avg_latency_ms: number;
}

export interface ModelUsageBreakdown {
  by_model: { model_id: string; model_name: string; requests: number; cost: number }[];
  by_provider: { provider: ModelProvider; requests: number; cost: number }[];
}
