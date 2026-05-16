// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_test_charter (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Charter object type */
export interface W14TestCharter {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  source_of_truth_version: string;  // dedicated column (text)
  masterplan_version: string;  // dedicated column (text)
  status: 'draft' | 'proposed' | 'approved' | 'rejected' | 'archived';  // enum from CHECK constraint
  hg_ticket?: string;  // dedicated column (text)
  council_session?: string;  // dedicated column (text)
  project_id: string;  // FK relation: w14_test_charter.project -> project (many_to_one)
  idea_id?: string;  // FK relation: w14_test_charter.idea -> idea (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_TEST_CHARTER_TYPE_ID = 'w14_test_charter';
export const W14_TEST_CHARTER_VERSION = 'v1.0';
