// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_loop_report (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Loop Report object type */
export interface W14LoopReport {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  loop_type: 'same_failure' | 'no_progress' | 'new_failures' | 'test_modification' | 'scope_drift' | 'semantic_repeat';  // enum from CHECK constraint
  attempts_n: number;  // dedicated column (integer)
  similarity_score: number;  // dedicated column (numeric)
  finding_id: string;  // FK relation: w14_loop_report.finding -> w14_finding (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_LOOP_REPORT_TYPE_ID = 'w14_loop_report';
export const W14_LOOP_REPORT_VERSION = 'v1.0';
