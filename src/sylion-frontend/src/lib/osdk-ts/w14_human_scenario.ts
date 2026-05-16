// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_human_scenario (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Human Scenario object type */
export interface W14HumanScenario {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  domain: string;  // dedicated column (text)
  difficulty: 'easy' | 'medium' | 'hard';  // enum from CHECK constraint
  workflow_step_count: number;  // dedicated column (integer)
  decision_point_count: number;  // dedicated column (integer)
  persona_id: string;  // FK relation: w14_human_scenario.persona -> w14_human_persona (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_HUMAN_SCENARIO_TYPE_ID = 'w14_human_scenario';
export const W14_HUMAN_SCENARIO_VERSION = 'v1.0';
