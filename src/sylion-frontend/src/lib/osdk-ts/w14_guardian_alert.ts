// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_guardian_alert (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Guardian Alert object type */
export interface W14GuardianAlert {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  guardian: 'sot_guardian' | 'masterplan_guardian' | 'test_integrity_guardian' | 'mock_fallback_guardian' | 'evidence_guardian' | 'gate_guardian' | 'council_guardian' | 'release_guardian' | 'loop_guardian' | 'llm_drift_guardian' | 'cost_sentinel' | 'pii_guardian' | 'trace_completeness_guardian';  // enum from CHECK constraint
  severity: 'P0' | 'P1' | 'P2' | 'P3' | 'P4';  // enum from CHECK constraint
  source_event?: string;  // dedicated column (text)
  acknowledged: boolean;  // dedicated column (boolean)
  reason: string;  // dedicated column (text)
  finding_id?: string;  // FK relation: w14_guardian_alert.finding -> w14_finding (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_GUARDIAN_ALERT_TYPE_ID = 'w14_guardian_alert';
export const W14_GUARDIAN_ALERT_VERSION = 'v1.0';
