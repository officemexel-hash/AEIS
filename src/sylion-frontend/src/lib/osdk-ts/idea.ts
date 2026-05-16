// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: idea (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** Idea object type */
export interface Idea {
  id: string;  // UUID v4
  title: string;  // dedicated column (text)
  description: string;  // dedicated column (text)
  author: string;  // dedicated column (text)
  status: 'draft' | 'clarification' | 'submitted' | 'council_review' | 'approved' | 'rejected' | 'implemented' | 'archived';  // enum from CHECK constraint
  priority: number;  // dedicated column (integer)
  category?: string;  // dedicated column (text)
  domain?: string;  // dedicated column (text)
  tags?: string;  // dedicated column (text)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const IDEA_TYPE_ID = 'idea';
export const IDEA_VERSION = 'v1.0';
