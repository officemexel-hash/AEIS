// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_branch (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Branch object type */
export interface W14Branch {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  branch_type: 'simulation' | 'repair' | 'test' | 'release';  // enum from CHECK constraint
  parent_branch_ref?: string;  // dedicated column (text)
  project_ref: string;  // dedicated column (text)
  sot_version: string;  // dedicated column (text)
  masterplan_version: string;  // dedicated column (text)
  state: 'open' | 'merged' | 'discarded';  // enum from CHECK constraint
  created_by: string;  // dedicated column (text)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_BRANCH_TYPE_ID = 'w14_branch';
export const W14_BRANCH_VERSION = 'v1.0';
