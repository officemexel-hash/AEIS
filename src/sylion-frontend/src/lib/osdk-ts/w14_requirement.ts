// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_requirement (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Test Requirement object type */
export interface W14Requirement {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  source: 'SoT' | 'Masterplan' | 'HumanDecision' | 'CouncilDecision';  // enum from CHECK constraint
  source_ref: string;  // dedicated column (text)
  criticality: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';  // enum from CHECK constraint
  test_required: boolean;  // dedicated column (boolean)
  description: string;  // dedicated column (text)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_REQUIREMENT_TYPE_ID = 'w14_requirement';
export const W14_REQUIREMENT_VERSION = 'v1.0';
