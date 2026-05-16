// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_release_candidate (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Release Candidate object type */
export interface W14ReleaseCandidate {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  project_ref: string;  // dedicated column (text)
  gate_status: 'NOT_TESTED' | 'TESTING_IN_PROGRESS' | 'BLOCKED_BY_FINDINGS' | 'BLOCKED_BY_GOVERNANCE' | 'READY_FOR_RELEASE_CANDIDATE' | 'RELEASE_CANDIDATE' | 'READY_FOR_PRODUCTION' | 'PRODUCTION_RELEASED' | 'ROLLBACK_REQUIRED' | 'ARCHIVED';  // enum from CHECK constraint
  evidence_pack?: string;  // dedicated column (text)
  unresolved_finding_count: number;  // dedicated column (integer)
  blocker_count: number;  // dedicated column (integer)
  branch_id: string;  // FK relation: w14_release_candidate.branch -> w14_branch (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_RELEASE_CANDIDATE_TYPE_ID = 'w14_release_candidate';
export const W14_RELEASE_CANDIDATE_VERSION = 'v1.0';
