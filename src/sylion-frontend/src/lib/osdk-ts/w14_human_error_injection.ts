// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_human_error_injection (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Human Error Injection object type */
export interface W14HumanErrorInjection {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  error_class: 'wrong_click' | 'gate_skip' | 'premature_action' | 'stale_data_action' | 'mock_as_live' | 'bypass_attempt' | 'typo_payload' | 'multi_tab_confusion' | 'panic_cancel' | 'wrong_context' | 'permission_overreach' | 'timeout_abandonment' | 'authority_abuse' | 'cognitive_overload' | 'cargo_cult_approval' | 'confirmation_bias' | 'anchor_mismatch' | 'sunk_cost_trap' | 'halo_effect' | 'time_pressure_shortcut' | 'authority_deference';  // enum from CHECK constraint
  target_action: string;  // dedicated column (text)
  timing: string;  // dedicated column (text)
  context_label: string;  // dedicated column (text)
  severity_if_allowed: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';  // enum from CHECK constraint
  simulated_target_d_level: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';  // enum from CHECK constraint
  action_d_level: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';  // enum from CHECK constraint
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_HUMAN_ERROR_INJECTION_TYPE_ID = 'w14_human_error_injection';
export const W14_HUMAN_ERROR_INJECTION_VERSION = 'v1.0';
