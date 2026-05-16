/**
 * W14 Test Center API client.
 *
 * Thin typed wrappers over /api/v1/testing/* endpoints exposed by
 * src/sylion-pipeline/sylion/api/testing_routes.py. Mirrors the calling
 * convention of lib/api/client.ts (request<T>) so the existing useApi
 * hook can drive every page.
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`testing-api ${res.status}: ${text}`);
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
// Domain types (mirror sylion/aeis/testing/ontology/objects.py)
// ---------------------------------------------------------------------------

export type Severity = "P0" | "P1" | "P2" | "P3" | "P4";
export type DLevel = "D0" | "D1" | "D2" | "D3" | "D4" | "D5";
export type RStatus =
  | "OPEN"
  | "TRIAGED"
  | "REPRODUCED"
  | "CLASSIFIED"
  | "REPAIR_PROPOSED"
  | "WAITING_FOR_HUMAN_GATE"
  | "REPAIRING"
  | "READY_FOR_RETEST"
  | "REGRESSION_FAILED"
  | "VERIFIED"
  | "ESCALATED"
  | "WAIVED_BY_HUMAN"
  | "CLOSED";
export type ReleaseStatus =
  | "release_candidate"
  | "production_ready"
  | "blocked";

export interface TestCharter {
  charter_id: string;
  project_id: string;
  status: string;
  source_of_truth_version: string;
  masterplan_version: string;
  required_test_classes: string[];
  required_personas: string[];
  required_evidence: string[];
  release_blockers: string[];
  approval: { d_level?: DLevel; human_gate_required?: boolean };
  hg_ticket_id?: string | null;
  council_session_id?: string | null;
  created_at: number;
  approved_at?: number | null;
}

export interface Finding {
  finding_id: string;
  severity: Severity;
  d_level: DLevel;
  r_status: RStatus;
  title: string;
  description: string;
  discovered_by: string;
  ticket_id?: string | null;
  created_at: number;
  closed_at?: number | null;
}

export interface ReleaseGateResult {
  status: ReleaseStatus;
  checklist_results: Record<string, boolean>;
  blockers: string[];
}

export interface TruthAlignmentRow {
  feature_id: string;
  sot: { present: boolean; ref?: string };
  masterplan: { present: boolean; ref?: string };
  runtime: { present: boolean; ref?: string };
  api: { present: boolean; ref?: string };
  ui: { present: boolean; data_source?: string };
  test: { present: boolean; ref?: string };
  docs: { present: boolean; ref?: string };
  aligned: boolean;
  drift: string[];
}

export interface GuardianAlert {
  alert_id: string;
  guardian: string;
  severity: Severity;
  reason: string;
  evidence_link: Record<string, unknown>;
  finding_id?: string | null;
  acknowledged: boolean;
  created_at: number;
}

export interface HumanPersona {
  persona_id: string;
  name: string;
  capability_level: "beginner" | "intermediate" | "expert";
  expertise_domains: string[];
  error_proneness: number;
  attention_span_min: number;
  trust_in_ai_baseline: number;
  risk_tolerance: "low" | "medium" | "high";
  dynamic_state: Record<string, number>;
  behavior_modifiers: Record<string, unknown>;
}

export interface SimulationRun {
  run_id: string;
  simulation_id: string;
  branch_id: string;
  status: "running" | "passed" | "failed" | "skipped" | "error";
  started_at: number;
  completed_at?: number | null;
  duration_ms?: number | null;
  cost_usd?: number;
  trace_id: string;
}

export interface LoopReport {
  report_id: string;
  finding_id: string;
  loop_type: string;
  attempts_n: number;
  similarity_score: number;
  suspected_root_cause: string[];
  blocked_actions: string[];
  required_decision: Record<string, unknown>;
  created_at: number;
}

export interface RepairSession {
  session_id: string;
  finding_id: string;
  branch_id: string;
  last_phase: RStatus;
  attempt_count: number;
  blocked: boolean;
  block_reason?: string | null;
  loop_report_id?: string | null;
  started_at: number;
  completed_at?: number | null;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export const testingApi = {
  // Charters
  listCharters: (projectId?: string) =>
    request<{ kind: string; items: TestCharter[] }>(
      `/api/v1/testing/testcharter${
        projectId ? `?filter_project_id=${encodeURIComponent(projectId)}` : ""
      }`,
    ),

  // Findings
  listFindings: (severity?: Severity) =>
    request<{ kind: string; items: Finding[] }>(
      `/api/v1/testing/finding${
        severity ? `?filter_severity=${severity}` : ""
      }`,
    ),

  // Release gate
  evaluateRelease: (projectId: string) =>
    request<ReleaseGateResult>(
      `/api/v1/testing/release-gate/${encodeURIComponent(projectId)}`,
    ),

  // Truth alignment
  truthAlignment: (featureId?: string) =>
    request<{ rows: TruthAlignmentRow[] }>(
      `/api/v1/testing/truth-alignment${
        featureId ? `?feature_id=${encodeURIComponent(featureId)}` : ""
      }`,
    ),

  // Guardians
  guardianAlerts: () =>
    request<{ kind: string; items: GuardianAlert[] }>(
      `/api/v1/testing/guardianalert`,
    ),

  // Personas
  personas: () =>
    request<{ kind: string; items: HumanPersona[] }>(
      `/api/v1/testing/humanpersona`,
    ),

  // Simulation runs
  simulationRuns: (limit?: number) =>
    request<{ kind: string; items: SimulationRun[] }>(
      `/api/v1/testing/testrun${limit ? `?limit=${limit}` : ""}`,
    ),

  // Loop reports
  loopReports: () =>
    request<{ kind: string; items: LoopReport[] }>(
      `/api/v1/testing/loopreport`,
    ),

  // Repair sessions
  repairSessions: () =>
    request<{ kind: string; items: RepairSession[] }>(
      `/api/v1/testing/repairattempt`,
    ),

  // Catalog (rehosted from orchestration/tests)
  testCatalog: () =>
    request<{ items: Array<Record<string, unknown>> }>(
      `/api/v1/testing/objects`,
    ),

  // Health
  health: () =>
    request<{ ok: boolean; counts: Record<string, number> }>(
      `/api/v1/testing/health`,
    ),
};
