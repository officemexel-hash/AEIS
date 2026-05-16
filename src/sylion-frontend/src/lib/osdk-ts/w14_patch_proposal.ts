// AUTO-GENERATED -- do not edit manually
// Generated from W15 manifest: w14_patch_proposal (v1.0)
// by sylion.aeis_v2.ontology.osdk_ts_gen

/** W14 Patch Proposal object type */
export interface W14PatchProposal {
  id: string;  // UUID v4
  legacy_w14_id: string;  // dedicated column (text)
  status: 'draft' | 'proposed' | 'approved' | 'rejected' | 'applied' | 'reverted';  // enum from CHECK constraint
  diff_lines_added: number;  // dedicated column (integer)
  diff_lines_removed: number;  // dedicated column (integer)
  proposed_by: string;  // dedicated column (text)
  files_touched_count: number;  // dedicated column (integer)
  finding_id: string;  // FK relation: w14_patch_proposal.finding -> w14_finding (many_to_one)
  branch_id: string;  // FK relation: w14_patch_proposal.branch -> w14_branch (many_to_one)
  extension?: Record<string, unknown>;  // JSONB extension
  created_at?: string;  // ISO datetime
  updated_at?: string;  // ISO datetime
}

export const W14_PATCH_PROPOSAL_TYPE_ID = 'w14_patch_proposal';
export const W14_PATCH_PROPOSAL_VERSION = 'v1.0';
