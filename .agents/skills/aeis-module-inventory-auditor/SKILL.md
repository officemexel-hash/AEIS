---
name: aeis-module-inventory-auditor
description: Use when building or revising the AEIS module census from code, frontend routes, contracts, prompts, addons, skills, and legacy surfaces. Produces evidence-first inventory inputs for CODEX_AEIS_MODULE_INVENTORY.md before any architectural conclusions.
---

# AEIS Module Inventory Auditor

Use this skill at the start of the AEIS audit and any time the module census must be refreshed.

## Goals

- Build the module list from code and wiring, not from old documentation.
- Separate real modules from generated artifacts, caches, results, and uploads.
- Treat backend packages, frontend routes, contracts, skills, addons, prompts, and legacy dashboard surfaces as separate audit inputs.
- Cross-check the census against `docs/claude_system_audit/`, but never let Claude's audit override code or runtime facts.

## Workflow

1. Run `scripts/collect_inventory.py --output docs/codex_system_audit/_inventory_snapshot.json`.
2. Review the JSON counts and lists for:
   - backend packages and modules under `src/sylion-pipeline/sylion`
   - API route files
   - frontend `page.tsx` routes under `src/sylion-frontend/src/app`
   - proto contracts
   - repo skills under `.agents/skills`
   - prompt-only assets in repo root
   - legacy dashboard files
3. Manually verify candidate modules that can be missed by directory heuristics:
   - top-level addons
   - hybrid workspace flows
   - operator/mobile placeholders
   - root entrypoints and legacy services outside `sylion/`
4. Classify each candidate as one of:
   - `backend_package`
   - `backend_module`
   - `api_route`
   - `frontend_route`
   - `contract_proto`
   - `repo_skill`
   - `addon`
   - `legacy_dashboard`
   - `prompt_only`
   - `entrypoint`
5. Promote only evidence-backed items into `CODEX_AEIS_MODULE_INVENTORY.md`.

## Inclusion Rules

- Include every real module, even if experimental, undocumented, or partially wired.
- Include mobile and funding separately.
- Include laboratory modules such as `cellular`, `sdr`, `vps`, `container`, and `devices.artifact_deployer`.
- Exclude caches and generated/runtime-only folders from module counts:
  - `.git`
  - `.claude/worktrees`
  - `.next`
  - `node_modules`
  - `__pycache__`
  - `.pytest_cache`
  - `results`
  - `output`
  - `workspace_uploads`

## Required Output Fields

Every promoted inventory row should aim to capture:

- module name
- path
- type
- layer hint
- canonical status
- runtime evidence status
- API/UI/test presence
- Human Gate touchpoint
- notes on plan-only vs code-backed

## Cross-check Rules

- Compare with `docs/claude_system_audit/CLAUDE_AEIS_MODULE_INVENTORY.md`.
- Record disagreements explicitly.
- If Claude says a module is missing but code exists, mark it as `DISAGREEMENT_PENDING_RUNTIME`.
- If Claude says a module is live but you only find stubs, mark it as `CLAUDE_OVERSTATED`.

## Script

Use `scripts/collect_inventory.py` for the deterministic first pass. Do not treat its output as final truth without manual review.
