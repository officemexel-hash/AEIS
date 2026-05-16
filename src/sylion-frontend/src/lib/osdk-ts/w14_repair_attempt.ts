// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_repair_attempt (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Repair Attempt object type */
export interface W14RepairAttempt {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  attempt_number: number;  // dedicated column (integer)
  r_phase: 'OPEN' | 'TRIAGED' | 'REPRODUCED' | 'CLASSIFIED' | 'REPAIR_PROPOSED' | 'WAITING_FOR_HUMAN_GATE' | 'REPAIRING' | 'READY_FOR_RETEST' | 'REGRESSION_FAILED' | 'VERIFIED' | 'ESCALATED' | 'WAIVED_BY_HUMAN' | 'CLOSED';  // enum from CHECK constraint
  result: 'success' | 'failed_same' | 'failed_new' | 'regression_failed' | 'blocked_by_loop';  // enum from CHECK constraint
  files_touched_count: number;  // dedicated column (integer)
  diff_lines: number;  // dedicated column (integer)
  time_in_phase_s: number;  // dedicated column (numeric)
  cost_usd: number;  // dedicated column (numeric)
  finding_id: string;  // FK relation: w14_repair_attempt.finding -> w14_finding (many_to_one)
  patch_proposal_id?: string;  // FK relation: w14_repair_attempt.patch_proposal -> w14_patch_proposal (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_REPAIR_ATTEMPT_TYPE_ID = 'w14_repair_attempt';
export const W14_REPAIR_ATTEMPT_VERSION = 'v1.0';
