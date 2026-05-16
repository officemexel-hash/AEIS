// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_test_suite (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Suite object type */
export interface W14TestSuite {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  name: string;  // dedicated column (text)
  test_class: 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | 'T6' | 'T7' | 'T8' | 'T9' | 'T10' | 'T11' | 'T12' | 'T13' | 'T14' | 'T15' | 'T16' | 'T17' | 'T18' | 'T19';  // enum from CHECK constraint
  enabled: boolean;  // dedicated column (boolean)
  case_count: number;  // dedicated column (integer)
  plan_id?: string;  // FK relation: w14_test_suite.plan -> w14_test_plan (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_TEST_SUITE_TYPE_ID = 'w14_test_suite';
export const W14_TEST_SUITE_VERSION = 'v1.0';
