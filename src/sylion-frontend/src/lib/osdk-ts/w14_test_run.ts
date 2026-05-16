// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_test_run (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Run object type */
export interface W14TestRun {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  status: 'running' | 'passed' | 'failed' | 'skipped' | 'error';  // enum from CHECK constraint
  duration_ms?: number;  // dedicated column (bigint)
  cost_usd: number;  // dedicated column (numeric)
  trace_ref: string;  // dedicated column (text)
  evidence_pack?: string;  // dedicated column (text)
  suite_id?: string;  // FK relation: w14_test_run.suite -> w14_test_suite (many_to_one)
  case_id?: string;  // FK relation: w14_test_run.case -> w14_test_case (many_to_one)
  branch_id: string;  // FK relation: w14_test_run.branch -> w14_branch (many_to_one)
  charter_id?: string;  // FK relation: w14_test_run.charter -> w14_test_charter (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_TEST_RUN_TYPE_ID = 'w14_test_run';
export const W14_TEST_RUN_VERSION = 'v1.0';
