// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_release_readiness_report (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Release Readiness Report object type */
export interface W14ReleaseReadinessReport {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  evidence_tier_used: 'H0' | 'H1' | 'H2' | 'H3' | 'H4';  // enum from CHECK constraint
  human_comprehension_score: number;  // dedicated column (numeric)
  blocker_count: number;  // dedicated column (integer)
  warning_count: number;  // dedicated column (integer)
  recommendation_count: number;  // dedicated column (integer)
  release_candidate_id: string;  // FK relation: w14_release_readiness_report.release_candidate -> w14_release_candidate (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_RELEASE_READINESS_REPORT_TYPE_ID = 'w14_release_readiness_report';
export const W14_RELEASE_READINESS_REPORT_VERSION = 'v1.0';
