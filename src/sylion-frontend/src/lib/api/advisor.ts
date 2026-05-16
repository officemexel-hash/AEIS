/**
 * SYLION AEIS Advisor — typed REST client.
 *
 * Endpoints map to mobile_gateway (sylion.aeis.advisor.mobile_gateway) prefixed
 * /api/v1/advisor/*. The UI must render live API data or honest empty/error
 * states; Advisor decisions must not be synthesized as demo data.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const ADVISOR_PREFIX = "/api/v1/advisor";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const { headers, ...rest } = opts ?? {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: { "Content-Type": "application/json", ...headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`advisor ${res.status}: ${text}`);
  }
  const text = await res.text();
  if (!text.trim()) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

// ---------------------------------------------------------------------------
// Types — mirror sylion.aeis.advisor.engine._models dataclasses
// ---------------------------------------------------------------------------

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type ConfidenceLabel = "low" | "med" | "high" | "very_high" | "certain";
export type DLevel = "D0" | "D1" | "D2" | "D3" | "D4" | "D5";
export type CardType = "decision" | "funding" | "security" | "scaling" | "onboarding";
export type CardSource = "rule_engine" | "llm_judge" | "history_match" | "council_vote" | "hybrid";
export type Priority = "low" | "normal" | "high" | "urgent";
export type PushPriority = "silent" | "low" | "normal" | "high" | "urgent";

export type CardAction =
  | "accept"
  | "reject"
  | "modify"
  | "remind_later"
  | "not_useful"
  | "convert_to_human_gate"
  | "convert_to_masterplan_change"
  | "save_as_preference"
  | "dont_learn_from_this";

export interface AdvisorCardHeader {
  card_id: string;
  schema_version: string;
  card_type: CardType;
  parent_card_id?: string;
  title: string;
  rationale: string;
  confidence_score: number;
  confidence_label: ConfidenceLabel;
  sources: CardSource[];
  risk_level: RiskLevel;
  risk_explanation?: string;
  project_domain: string;
  project_type?: string;
  project_id?: string;
  idea_id?: string;
  d_level: DLevel;
  evidence_pack_id?: string;
  history_based: boolean;
  related_history_card_ids: string[];
  historical_acceptance_rate: number;
  created_at: number;
  updated_at: number;
  expires_at?: number;
  priority: Priority;
  tags: string[];
  dont_learn: boolean;
  human_gate_required: boolean;
  mobile_allowed: boolean;
  requires_biometric: boolean;
  push_priority: PushPriority;
  audit_trail_id: string;
  llm_judge_audit_id?: string;
  operator_id: string;
  emitting_module: string;
  used_local_fallback: boolean;
  local_fallback_reason?: string;
}

export interface DecisionCardBody {
  recommendation: string;
  expected_benefit: string;
  expected_downside: string;
  quality_impact: string;
  cost_impact: Impact;
  token_impact: Impact;
  time_impact: Impact;
  alternatives: Alternative[];
  recommendation_type: string;
  metadata: Record<string, string>;
  source_data_ids: string[];
  assumption_note: string;
}

export interface Impact {
  absolute_value: string;
  unit: string;
  delta_vs_baseline_pct: number;
  baseline_label: string;
  estimate_confidence: "assumption" | "profile" | "measured";
  is_assumption: boolean;
  source_label: string;
}

export interface Alternative {
  title: string;
  short_description: string;
  cost_delta_vs_primary: Impact;
  time_delta_vs_primary: Impact;
  risk_level: RiskLevel;
  confidence_score: number;
  trade_off_summary: string;
}

export interface FundingCardBody {
  suggestion_type: string;
  headline_recommendation: string;
  grant_program_id: string;
  grant_program_name: string;
  grant_source: string;
  country: string;
  region: string;
  grant_amount_min?: { amount: string; currency: string };
  grant_amount_max?: { amount: string; currency: string };
  eligibility_score: number;
  eligibility_breakdown: EligibilityComponent[];
  eligibility_floor_breached: boolean;
  current_match_summary: string;
  gaps_to_qualify: string[];
  recommended_actions: RecommendedAction[];
  consortium_required: boolean;
  consortium_suggestions: ConsortiumSuggestion[];
  application_deadline: number;
  time_to_prepare_seconds: number;
  deadline_at_risk: boolean;
  static_simulations: SimulationScenario[];
  dynamic_simulations: SimulationScenario[];
  auto_simulations: SimulationScenario[];
  match_confidence: number;
  scoring_profile_id: string;
}

export interface EligibilityComponent {
  component_id: string;
  component_name: string;
  weight_in_grant: number;
  score: number;
  hard_floor: number;
  floor_breached: boolean;
  explanation: string;
  driving_factors: string[];
}

export interface RecommendedAction {
  action_id: string;
  description: string;
  difficulty: "trivial" | "easy" | "moderate" | "hard" | "very_hard";
  estimated_time_seconds: number;
  estimated_cost?: { amount: string; currency: string };
  expected_score_delta: number;
  requires_third_party: boolean;
  third_party_type?: string;
}

export interface ConsortiumSuggestion {
  suggestion_id: string;
  entity_type: string;
  suggested_name?: string;
  required_qualifications: string[];
  region_constraint?: string;
  rationale: string;
}

export interface SimulationScenario {
  scenario_id: string;
  label: string;
  mode: "static" | "dynamic" | "auto_generated";
  changes: Array<{ field_path: string; from_value: string; to_value: string; explanation: string }>;
  resulting_eligibility_score: number;
  resulting_breakdown: EligibilityComponent[];
  cost_to_implement?: { amount: string; currency: string };
  time_to_implement_seconds: number;
}

export interface AdvisorCardEnvelope {
  envelope_version: string;
  header: AdvisorCardHeader;
  body: DecisionCardBody | FundingCardBody | Record<string, unknown>;
}

export interface EvidencePack {
  evidence_pack_id: string;
  card_id: string;
  d_level: DLevel;
  pack_template: "d3_light" | "d5_full";
  decision_class: string;
  domain: string;
  rationale: string;
  rollback_plan: string;
  fidelity_test: string;
  confidence_breakdown: {
    council_match: number;
    history_match: number;
    pricing_quality: number;
    historical_acceptance_rate: number;
    used_local_fallback: boolean;
    raw_score: number;
    final_score: number;
  };
  historical_acceptance_rate: number;
  llm_judge_audit_ids: string[];
  simulation_results: unknown[];
  council_vote_id?: string;
  risk_analysis?: Record<string, unknown>;
  compliance_check?: Record<string, unknown>;
  sentinel_signoffs?: Record<string, unknown>;
  attachments: unknown[];
  created_by: string;
  created_at: number;
  finalized_at?: number;
  status: "draft" | "finalized" | "rejected";
  signatures: Array<{
    signature_id: string;
    signer_id: string;
    signer_role: string;
    signed_at: number;
  }>;
}

export interface HandleActionResponse {
  action_event_id: string;
  recorded_at: number;
  soft_learning_triggered: boolean;
  hard_learning_pending_confirmation: boolean;
  created_human_gate_ticket_id?: string;
  created_masterplan_proposal_id?: string;
  saved_preference_id?: string;
}

export interface OnboardingState {
  step: number;
  completed_steps: number[];
  values: Record<string, unknown>;
  completed_at?: number;
  phase1_completed_at?: number;
  phase1_acceptance?: Phase1AcceptanceReport;
  workspace_bootstrap?: Phase1WorkspaceBootstrap;
}

export interface Phase1StorageValidation {
  path: string;
  ok: boolean;
  writable: boolean;
  sqlite_ok: boolean;
  would_create: boolean;
  probe_path?: string;
  missing_parents?: string[];
  free_gb?: number;
  write_mbps?: number;
  warnings: string[];
  errors: string[];
}

export interface Phase1SystemCheck {
  status: "ok" | "warning" | "error";
  workspace_default: string;
  disk: { path: string; free_gb?: number; min_required_gb: number; recommended_gb: number };
  ram: { status: string; min_required_gb: number; recommended_gb: number };
  gpu: { status: string; class: string };
  local_models: { count: number; ollama_reachable: boolean; models: Array<Record<string, unknown>> };
  backend: { health: string };
}

export interface Phase1ModelGate {
  passed: boolean;
  local_model_count: number;
  has_api_key: boolean;
  demo_mode: boolean;
  required: string;
  local_probe: {
    provider: string;
    reachable: boolean;
    count: number;
    models: Array<Record<string, unknown>>;
    functional_check?: Record<string, unknown>;
  };
}

export interface Phase1AcceptanceCheck {
  key: string;
  ok: boolean;
  label: string;
  detail?: unknown;
}

export interface Phase1AcceptanceReport {
  operator_id: string;
  accepted: boolean;
  passed: number;
  total: number;
  checks: Phase1AcceptanceCheck[];
}

export interface Phase1WorkspaceBootstrap {
  workspace_path: string;
  folders: string[];
}

export interface PreferenceEntry {
  user_id: string;
  project_type: string | null;
  project_domain: string | null;
  preference_key: string;
  preference_value: unknown;
  set_by: string;
  updated_at: number;
}

export interface GrantProgram {
  program_id: string;
  program_code?: string;
  display_name: string;
  source: string;
  country: string;
  region?: string;
  managing_body?: string;
  amount_min_usd?: number;
  amount_max_usd?: number;
  call_open_at?: number;
  call_close_at?: number;
  is_active: boolean;
}

export interface ProjectLifecyclePhase {
  hook_id: string;
  hook_event_type: string;
  status: "pending" | "in_progress" | "approved" | "blocked";
  cards: AdvisorCardEnvelope[];
  last_event_at?: number;
}

export interface ProjectLifecycleState {
  project_id: string;
  project_type: string;
  project_domain: string;
  phases: ProjectLifecyclePhase[];
}

export interface AdvisorConfigurationCounts {
  api_keys: number;
  local_models: number;
  routing_rules: number;
  skills: number;
}

// ---------------------------------------------------------------------------
// Client methods
// ---------------------------------------------------------------------------

export const advisorApi = {
  // Cards
  listCards: (params?: { operator_id?: string; project_id?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.operator_id) qs.set("operator_id", params.operator_id);
    if (params?.project_id) qs.set("project_id", params.project_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<{ cards: AdvisorCardEnvelope[] }>(`${ADVISOR_PREFIX}/cards${suffix}`);
  },
  getCard: (cardId: string) =>
    request<AdvisorCardEnvelope>(`${ADVISOR_PREFIX}/cards/${encodeURIComponent(cardId)}`),
  handleAction: (
    cardId: string,
    action: CardAction,
    payload?: {
      operator_note?: string;
      modified_recommendation?: string;
      preference_key?: string;
      preference_project_type?: string;
      preference_project_domain?: string;
      preference_value?: unknown;
      dont_learn_flag?: boolean;
    },
    biometricVerified = false,
  ) =>
    request<HandleActionResponse>(`${ADVISOR_PREFIX}/cards/${encodeURIComponent(cardId)}/actions`, {
      method: "POST",
      headers: biometricVerified ? { "X-Biometric-Verified": "true" } : {},
      body: JSON.stringify({ action, ...payload }),
    }),

  // Evidence
  getEvidencePack: (packId: string) =>
    request<EvidencePack>(`${ADVISOR_PREFIX}/evidence/${encodeURIComponent(packId)}`),
  finalizeEvidencePack: (packId: string, edits?: Partial<EvidencePack>) =>
    request<{ ok: boolean }>(`${ADVISOR_PREFIX}/evidence/${encodeURIComponent(packId)}/finalize`, {
      method: "POST",
      body: JSON.stringify(edits ?? {}),
    }),
  signEvidencePack: (packId: string, signature: string, signerRole: string) =>
    request<{ signature_id: string }>(`${ADVISOR_PREFIX}/evidence/${encodeURIComponent(packId)}/sign`, {
      method: "POST",
      body: JSON.stringify({ signature_payload: signature, signer_role: signerRole }),
    }),

  // Onboarding
  getOnboardingState: () => request<OnboardingState>(`${ADVISOR_PREFIX}/onboarding/state`),
  saveOnboardingStep: (step: number, values: Record<string, unknown>) =>
    request<OnboardingState>(`${ADVISOR_PREFIX}/onboarding/step/${step}`, {
      method: "PUT",
      body: JSON.stringify({ values }),
    }),
  completeOnboarding: (values: Record<string, unknown>) =>
    request<OnboardingState>(`${ADVISOR_PREFIX}/onboarding/complete`, {
      method: "POST",
      body: JSON.stringify({ values }),
    }),
  phase1SystemCheck: () =>
    request<Phase1SystemCheck>(`${ADVISOR_PREFIX}/onboarding/phase1/system-check`),
  validatePhase1Storage: (path: string) =>
    request<Phase1StorageValidation>(`${ADVISOR_PREFIX}/onboarding/phase1/storage/validate`, {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  phase1ModelGate: (runTest = false) =>
    request<Phase1ModelGate>(
      `${ADVISOR_PREFIX}/onboarding/phase1/model-gate${runTest ? "?run_test=true" : ""}`,
    ),
  completePhase1: (values: Record<string, unknown>) =>
    request<OnboardingState>(`${ADVISOR_PREFIX}/onboarding/phase1/complete`, {
      method: "POST",
      body: JSON.stringify({ values }),
    }),
  phase1AcceptanceTest: () =>
    request<Phase1AcceptanceReport>(`${ADVISOR_PREFIX}/onboarding/phase1/acceptance-test`),
  resetOnboarding: () =>
    request<OnboardingState>(`${ADVISOR_PREFIX}/onboarding/state`, {
      method: "DELETE",
    }),

  // Preferences
  listPreferences: (userId: string) =>
    request<{ preferences: PreferenceEntry[] }>(
      `${ADVISOR_PREFIX}/preferences?user_id=${encodeURIComponent(userId)}`,
    ),
  setPreference: async (
    userId: string,
    key: string,
    value: unknown,
    scope?: { project_type?: string | null; project_domain?: string | null },
  ) => {
    const response = await request<PreferenceEntry & { result?: { success?: boolean; error_message?: string; status?: string } }>(
      `${ADVISOR_PREFIX}/preferences/${encodeURIComponent(key)}`,
      {
        method: "PUT",
        body: JSON.stringify({ user_id: userId, value, ...scope }),
      },
    );
    if (response.result && response.result.success === false) {
      throw new Error(response.result.error_message || response.result.status || `preference ${key} was not saved`);
    }
    return response;
  },
  resetPreference: (userId: string, key: string) =>
    request<{ ok: boolean }>(`${ADVISOR_PREFIX}/preferences/${encodeURIComponent(key)}`, {
      method: "DELETE",
      body: JSON.stringify({ user_id: userId }),
    }),
  preferenceAudit: (userId: string, key?: string) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (key) qs.set("key", key);
    return request<{ entries: Array<Record<string, unknown>> }>(
      `${ADVISOR_PREFIX}/preferences/audit?${qs}`,
    );
  },
  getConfigurationCounts: () =>
    request<AdvisorConfigurationCounts>(`${ADVISOR_PREFIX}/preferences/counts`),

  // Project lifecycle
  getProjectLifecycle: (projectId: string) =>
    request<ProjectLifecycleState>(
      `${ADVISOR_PREFIX}/projects/${encodeURIComponent(projectId)}/lifecycle`,
    ),

  // Operator monitoring dashboard
  getMonitoringSnapshot: () =>
    request<{
      projects: Array<{
        project_id: string;
        project_name: string;
        project_type: string;
        project_domain: string;
        active_phase: string;
        active_cards: number;
        accept_rate: number;
        spend_usd_month: number;
        budget_usd_month: number;
      }>;
      throughput: Array<{ ts: number; emitted: number; accepted: number; rejected: number }>;
      cost_vs_budget: { spend_usd: number; budget_usd: number; per_project: Record<string, { spend: number; budget: number }> };
      council_activity: Array<{ ts: number; votes: number }>;
      subscription_recommendations: AdvisorCardEnvelope[];
      alerts: Array<{ id: string; severity: RiskLevel; title: string; card_id?: string }>;
    }>(`${ADVISOR_PREFIX}/monitoring/snapshot`),

  // Funding
  listGrants: (filters?: { country?: string; region?: string }) => {
    const qs = new URLSearchParams();
    if (filters?.country) qs.set("country", filters.country);
    if (filters?.region) qs.set("region", filters.region);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<{ grants: GrantProgram[] }>(`${ADVISOR_PREFIX}/funding/grants${suffix}`);
  },
  getFundingDeadlines: () =>
    request<{ deadlines: Array<{ grant_program_id: string; display_name: string; deadline: number; days_remaining: number }> }>(
      `${ADVISOR_PREFIX}/funding/deadlines`,
    ),
};

// ---------------------------------------------------------------------------
// Empty states used by hooks when backend is unreachable.
// ---------------------------------------------------------------------------

export const DEFAULT_OPERATOR_ID = "00000000-0000-0000-0000-000000000001";

export const advisorEmptyStates = {
  cards: (): AdvisorCardEnvelope[] => [],

  evidencePack: (_packId: string): EvidencePack | null => null,

  monitoringSnapshot: () => ({
    projects: [] as Array<{
      project_id: string; project_name: string; project_type: string; project_domain: string;
      active_phase: string; active_cards: number; accept_rate: number;
      spend_usd_month: number; budget_usd_month: number;
    }>,
    throughput: [] as Array<{ ts: number; emitted: number; accepted: number; rejected: number }>,
    cost_vs_budget: { spend_usd: 0, budget_usd: 0, per_project: {} as Record<string, { spend: number; budget: number }> },
    council_activity: [] as Array<{ ts: number; votes: number }>,
    subscription_recommendations: [] as unknown[],
    alerts: [] as Array<{ id: string; severity: RiskLevel; title: string; card_id?: string }>,
  }),

  projectLifecycle: (_projectId: string): ProjectLifecycleState | null => null,
};
