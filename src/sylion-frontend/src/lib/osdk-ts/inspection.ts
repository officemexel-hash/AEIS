// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: inspection (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** Inspection object type */
export interface Inspection {
  id: string;  // UUID v4
  inspector: string;  // dedicated column (text)
  inspected_at: string;  // dedicated column (timestamptz)
  findings_count: number;  // dedicated column (integer)
  verdict: 'draft' | 'passed' | 'conditional' | 'failed' | 'void';  // enum from CHECK constraint
  notes?: string;  // dedicated column (text)
  vehicle_id?: string;  // FK relation: inspection.vehicle -> vehicle (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const INSPECTION_TYPE_ID = 'inspection';
export const INSPECTION_VERSION = 'v1.0';
