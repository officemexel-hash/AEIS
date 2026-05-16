# Ontology demo manifests (`_demos/`)

This directory holds **non-production** sample data and tutorial type
definitions for SYLION v2 ontology.

## Contents

| File | What it is | Type definition |
|------|------------|-----------------|
| `customer_demos.yaml` | 5 sample CRM rows (Polish names) | `../customer.yaml` |
| `project_demos.yaml`  | 5 sample project rows | `../project.yaml` |
| `vehicle_demos.yaml`  | 5 sample fleet rows (with VINs) | `../vehicle.yaml` |
| `idea_demos.yaml`     | 5 sample IdeaVault entries | `../idea.yaml` |
| `school_domain_types.yaml` | 5 example ObjectType definitions for an education domain | (none — these *are* type definitions, simplified) |

## What they are NOT

- **Not loaded** into the production registry by any code path.
- **Not** authoritative test fixtures — golden tests live in `src/sylion-pipeline/tests/`.
- **Not** OSDK examples — those will live in `docs/v2/operator_guide/` once curated.

## What they are FOR

1. **Operator onboarding** — quick "looks like" data for screenshots, demos, and tutorials.
2. **Manual smoke tests** — operator can paste a row into the apply API to see the round-trip.
3. **Authoring reference** — `school_domain_types.yaml` shows the minimal shape of a new ObjectType when an operator wants to add their own domain.

## Provenance

Curated from `docs/v2/_drafts/ollama_batch/` (Polish-text generation pass, 2026-04-27).
Each file includes a `# Source:` header pointing back to the original draft.
See `docs/v2/_drafts/INTEGRATION_LOG.md` for the curation log.

## Related ADRs

- **ADR-001** — five architectural decisions (manifest format, parking W19, ...).
- **ADR-002** — multi-model routing matrix (this content was produced by routed local models).
