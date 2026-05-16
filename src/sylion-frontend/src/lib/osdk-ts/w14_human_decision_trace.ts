// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_human_decision_trace (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Human Decision Trace object type */
export interface W14HumanDecisionTrace {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  simulation_ref: string;  // dedicated column (text)
  decision_count: number;  // dedicated column (integer)
  persona_id: string;  // FK relation: w14_human_decision_trace.persona -> w14_human_persona (many_to_one)
  scenario_id?: string;  // FK relation: w14_human_decision_trace.scenario -> w14_human_scenario (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_HUMAN_DECISION_TRACE_TYPE_ID = 'w14_human_decision_trace';
export const W14_HUMAN_DECISION_TRACE_VERSION = 'v1.0';
