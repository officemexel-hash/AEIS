// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_test_plan (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Plan object type */
export interface W14TestPlan {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  estimated_duration_s: number;  // dedicated column (integer)
  suite_count: number;  // dedicated column (integer)
  parallel_group_count: number;  // dedicated column (integer)
  charter_id: string;  // FK relation: w14_test_plan.charter -> w14_test_charter (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_TEST_PLAN_TYPE_ID = 'w14_test_plan';
export const W14_TEST_PLAN_VERSION = 'v1.0';
