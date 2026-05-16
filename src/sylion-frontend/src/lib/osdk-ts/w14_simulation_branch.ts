// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_simulation_branch (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Simulation Branch object type */
export interface W14SimulationBranch {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  state: 'open' | 'merged' | 'discarded';  // enum from CHECK constraint
  discard_reason?: string;  // dedicated column (text)
  snapshot_db_path?: string;  // dedicated column (text)
  parent_branch_id?: string;  // FK relation: w14_simulation_branch.parent_branch -> w14_branch (many_to_one)
  contract_id: string;  // FK relation: w14_simulation_branch.contract -> w14_simulation_contract (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_SIMULATION_BRANCH_TYPE_ID = 'w14_simulation_branch';
export const W14_SIMULATION_BRANCH_VERSION = 'v1.0';
