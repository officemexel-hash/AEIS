// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_simulation_evidence (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Simulation Evidence object type */
export interface W14SimulationEvidence {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  simulation_ref: string;  // dedicated column (text)
  trace_ref: string;  // dedicated column (text)
  layer_executed: '1' | '2' | '3' | '4';  // enum from CHECK constraint
  branch_snapshot_hash: string;  // dedicated column (text)
  sim_branch_id: string;  // FK relation: w14_simulation_evidence.sim_branch -> w14_simulation_branch (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_SIMULATION_EVIDENCE_TYPE_ID = 'w14_simulation_evidence';
export const W14_SIMULATION_EVIDENCE_VERSION = 'v1.0';
