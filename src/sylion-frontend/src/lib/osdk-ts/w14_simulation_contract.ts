// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_simulation_contract (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Simulation Contract object type */
export interface W14SimulationContract {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  simulation_ref: string;  // dedicated column (text)
  sot_version: string;  // dedicated column (text)
  masterplan_version: string;  // dedicated column (text)
  source_project: string;  // dedicated column (text)
  branch_id: string;  // FK relation: w14_simulation_contract.branch -> w14_branch (many_to_one)
  test_charter_id?: string;  // FK relation: w14_simulation_contract.test_charter -> w14_test_charter (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_SIMULATION_CONTRACT_TYPE_ID = 'w14_simulation_contract';
export const W14_SIMULATION_CONTRACT_VERSION = 'v1.0';
