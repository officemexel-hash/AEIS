// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: customer (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** Customer object type */
export interface Customer {
  id: string;  // UUID v4
  name: string;  // dedicated column (text)
  email: string;  // dedicated column (text)
  phone?: string;  // dedicated column (text)
  company?: string;  // dedicated column (text)
  status: 'draft' | 'active' | 'archived';  // enum from CHECK constraint
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const CUSTOMER_TYPE_ID = 'customer';
export const CUSTOMER_VERSION = 'v1.0';
