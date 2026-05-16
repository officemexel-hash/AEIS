// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: vehicle (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** Vehicle object type */
export interface Vehicle {
  id: string;  // UUID v4
  vin: string;  // dedicated column (text)
  plate: string;  // dedicated column (text)
  make: string;  // dedicated column (text)
  model: string;  // dedicated column (text)
  year: number;  // dedicated column (integer)
  mileage_km?: number;  // dedicated column (bigint)
  owner_id?: string;  // FK relation: vehicle.owner -> customer (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const VEHICLE_TYPE_ID = 'vehicle';
export const VEHICLE_VERSION = 'v1.0';
