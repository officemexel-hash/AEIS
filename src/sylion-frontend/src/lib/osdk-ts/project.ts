// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: project (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** Project object type */
export interface Project {
  id: string;  // UUID v4
  title: string;  // dedicated column (text)
  status: 'draft' | 'definition_in_progress' | 'active' | 'paused' | 'completed' | 'archived' | 'deleted';  // enum from CHECK constraint
  idea?: string;  // dedicated column (text)
  owner_id: string;  // dedicated column (uuid)
  deadline?: string;  // dedicated column (timestamptz)
  budget_usd?: number;  // dedicated column (numeric)
  customer_id?: string;  // FK relation: project.customer -> customer (many_to_one)
  parent_idea_id?: string;  // FK relation: project.parent_idea -> idea (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const PROJECT_TYPE_ID = 'project';
export const PROJECT_VERSION = 'v1.0';
