// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_human_persona (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Human Persona object type */
export interface W14HumanPersona {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  name: string;  // dedicated column (text)
  capability_level: 'beginner' | 'intermediate' | 'expert';  // enum from CHECK constraint
  error_proneness: number;  // dedicated column (numeric)
  attention_span_min: number;  // dedicated column (integer)
  trust_in_ai_baseline: number;  // dedicated column (numeric)
  risk_tolerance: 'low' | 'medium' | 'high';  // enum from CHECK constraint
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_HUMAN_PERSONA_TYPE_ID = 'w14_human_persona';
export const W14_HUMAN_PERSONA_VERSION = 'v1.0';
