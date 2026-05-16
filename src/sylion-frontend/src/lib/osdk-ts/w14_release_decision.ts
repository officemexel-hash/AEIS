// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_release_decision (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Release Decision object type */
export interface W14ReleaseDecision {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  hg_ticket: string;  // dedicated column (text)
  council_session?: string;  // dedicated column (text)
  outcome: 'approved' | 'rejected' | 'deferred' | 'rollback';  // enum from CHECK constraint
  signature_count: number;  // dedicated column (integer)
  release_candidate_id: string;  // FK relation: w14_release_decision.release_candidate -> w14_release_candidate (many_to_one)
  charter_id?: string;  // FK relation: w14_release_decision.charter -> w14_test_charter (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_RELEASE_DECISION_TYPE_ID = 'w14_release_decision';
export const W14_RELEASE_DECISION_VERSION = 'v1.0';
