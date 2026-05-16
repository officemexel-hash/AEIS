// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_evaluation_suite (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Evaluation Suite object type */
export interface W14EvaluationSuite {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  target_function: string;  // dedicated column (text)
  target_module: string;  // dedicated column (text)
  test_case_count: number;  // dedicated column (integer)
  metric_count: number;  // dedicated column (integer)
  baseline_run_id?: string;  // FK relation: w14_evaluation_suite.baseline_run -> w14_test_run (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_EVALUATION_SUITE_TYPE_ID = 'w14_evaluation_suite';
export const W14_EVALUATION_SUITE_VERSION = 'v1.0';
