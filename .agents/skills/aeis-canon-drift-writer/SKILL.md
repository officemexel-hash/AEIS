---
name: aeis-canon-drift-writer
description: Use when comparing AEIS code/runtime reality against canon sources, project prompts, and another model's audit. Produces evidence-based drift findings and explicitly records where Claude's audit is correct, incomplete, or overstated.
---

# AEIS Canon Drift Writer

Use this skill when writing drift and disagreement analysis.

## Sources Priority

1. code
2. runtime
3. API
4. UI
5. tests
6. documentation
7. other model audit (`docs/claude_system_audit/`) as secondary evidence only

## Canon Inputs

- `SYLION_AEIS_Dokumentacja_v3_5.pdf`
- `AEIS_Distributed_Build_Architecture.pdf`
- `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`
- `AEIS_Funding_Autopilot_prompt.txt`

## Drift Types

- `MISSING_IN_RUNTIME`
- `DOC_ONLY`
- `PROMPT_ONLY`
- `PARTIAL_WIRING`
- `DUPLICATE_IMPL`
- `LEGACY_PARALLEL_STACK`
- `CLAUDE_UNDERCALLED`
- `CLAUDE_OVERCALLED`

## Workflow

1. Start from canon expectation.
2. Prove real implementation state from code and runtime.
3. Compare with Claude's claim.
4. Record:
   - what canon says
   - what code says
   - what runtime says
   - what Claude said
   - Codex verdict

## Output Targets

- `CODEX_AEIS_CANON_VS_REALITY.md`
- `CODEX_AEIS_DOCUMENTATION_DRIFT_MAP.md`
- `CODEX_AEIS_REPAIR_BACKLOG.md`
