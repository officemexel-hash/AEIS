// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_human_near_miss (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Human Near Miss object type */
export interface W14HumanNearMiss {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  blocked_successfully: boolean;  // dedicated column (boolean)
  operator_message_quality_score: number;  // dedicated column (numeric)
  future_risk: 'low' | 'medium' | 'high';  // enum from CHECK constraint
  suggested_ui_improvement: string;  // dedicated column (text)
  scenario_id?: string;  // FK relation: w14_human_near_miss.scenario -> w14_human_scenario (many_to_one)
  error_injection_id: string;  // FK relation: w14_human_near_miss.error_injection -> w14_human_error_injection (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_HUMAN_NEAR_MISS_TYPE_ID = 'w14_human_near_miss';
export const W14_HUMAN_NEAR_MISS_VERSION = 'v1.0';
