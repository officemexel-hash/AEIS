// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_test_case (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Case object type */
export interface W14TestCase {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  evaluator: string;  // dedicated column (text)
  enabled: boolean;  // dedicated column (boolean)
  real_example?: string;  // dedicated column (text)
  requirement_id: string;  // FK relation: w14_test_case.requirement -> w14_requirement (many_to_one)
  suite_id?: string;  // FK relation: w14_test_case.suite -> w14_test_suite (many_to_one)
  persona_id?: string;  // FK relation: w14_test_case.persona -> w14_human_persona (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_TEST_CASE_TYPE_ID = 'w14_test_case';
export const W14_TEST_CASE_VERSION = 'v1.0';
