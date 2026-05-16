// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_finding (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Finding object type */
export interface W14Finding {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  severity: 'P0' | 'P1' | 'P2' | 'P3' | 'P4';  // enum from CHECK constraint
  r_status: 'OPEN' | 'TRIAGED' | 'REPRODUCED' | 'CLASSIFIED' | 'REPAIR_PROPOSED' | 'WAITING_FOR_HUMAN_GATE' | 'REPAIRING' | 'READY_FOR_RETEST' | 'REGRESSION_FAILED' | 'VERIFIED' | 'ESCALATED' | 'WAIVED_BY_HUMAN' | 'CLOSED';  // enum from CHECK constraint
  d_level: 'D0' | 'D1' | 'D2' | 'D3' | 'D4' | 'D5';  // enum from CHECK constraint
  title: string;  // dedicated column (text)
  discovered_by: string;  // dedicated column (text)
  ticket?: string;  // dedicated column (text)
  requirement_id?: string;  // FK relation: w14_finding.requirement -> w14_requirement (many_to_one)
  test_run_id?: string;  // FK relation: w14_finding.test_run -> w14_test_run (many_to_one)
  guardian_alert_id?: string;  // FK relation: w14_finding.guardian_alert -> w14_guardian_alert (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_FINDING_TYPE_ID = 'w14_finding';
export const W14_FINDING_VERSION = 'v1.0';
