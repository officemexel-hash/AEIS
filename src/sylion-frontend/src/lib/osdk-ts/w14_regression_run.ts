// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_regression_run (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Regression Run object type */
export interface W14RegressionRun {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  status: 'pending' | 'passed' | 'failed';  // enum from CHECK constraint
  finding_id: string;  // FK relation: w14_regression_run.finding -> w14_finding (many_to_one)
  pre_fix_run_id: string;  // FK relation: w14_regression_run.pre_fix_run -> w14_test_run (many_to_one)
  post_fix_run_id: string;  // FK relation: w14_regression_run.post_fix_run -> w14_test_run (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_REGRESSION_RUN_TYPE_ID = 'w14_regression_run';
export const W14_REGRESSION_RUN_VERSION = 'v1.0';
