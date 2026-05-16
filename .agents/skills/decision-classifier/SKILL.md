---
name: decision-classifier
description: >
  Classifies architectural and implementation decisions into the SYLION D0-D5
  decision ladder. D3+ decisions require Council approval, evidence submission,
  and a documented rollback plan before execution.
---

# Decision Classifier

## When to Use

- Before making any structural change to a module (rename, move, split, merge).
- When evaluating a new dependency, library, or external service integration.
- When altering cross-cutting concerns (auth, logging, caching, event bus).
- When changing public API contracts, protobuf definitions, or database schemas.
- Any time a change touches more than one module boundary.

## Decision Ladder

| Level | Label         | Scope                        | Requirements                         |
|-------|---------------|------------------------------|--------------------------------------|
| D0    | Trivial       | Single file, no API change   | None                                 |
| D1    | Low           | Single module, internal only | PR description                       |
| D2    | Medium        | 2-3 modules, internal API    | PR + rationale                       |
| D3    | High          | Cross-module, public API     | Council + Evidence + Rollback plan   |
| D4    | Critical      | Architecture-level change    | Council + Evidence + Rollback plan   |
| D5    | Existential   | System-wide paradigm shift   | Council + Evidence + Rollback + ADR  |

## Inputs

| Name               | Type   | Required | Description                                        |
|--------------------|--------|----------|----------------------------------------------------|
| change_description | string | Yes      | Natural-language description of the proposed change |
| affected_modules   | list   | Yes      | List of module IDs that will be modified            |

## Outputs

| Name              | Type   | Description                                                        |
|-------------------|--------|--------------------------------------------------------------------|
| decision_class    | string | One of D0, D1, D2, D3, D4, D5                                     |
| rationale         | string | Explanation of why this classification was chosen                  |
| required_evidence | list   | Evidence artifacts required before execution (empty for D0-D2)     |

## Execution Steps

1. **Parse inputs** -- Read `change_description` and `affected_modules`.
2. **Scope analysis** -- Count affected modules. Check if public API surface is touched.
3. **Risk assessment** -- Evaluate blast radius: data migration, downtime, breaking contracts.
4. **Classify** -- Apply the decision ladder rules:
   - 1 module, no API change, no cross-cutting -> D0 or D1.
   - 2-3 modules, internal only -> D2.
   - Public API or cross-module contract -> D3.
   - Architecture-level (event bus, auth, DB schema) -> D4.
   - System-wide paradigm shift -> D5.
5. **Generate rationale** -- Write a one-paragraph justification.
6. **List required evidence** -- For D3+, enumerate required artifacts:
   - Evidence pack (benchmarks, test results, migration plan).
   - Rollback plan with concrete revert steps.
   - Council sign-off record.
7. **Return output** -- Emit `decision_class`, `rationale`, `required_evidence`.

## Safety Rules

- **D3+ decisions must never be auto-approved.** The classifier only recommends; a human Council member must explicitly sign off.
- If the classifier cannot determine the level with confidence, it must default to the **higher** classification.
- Every D3+ decision must have a rollback plan that has been tested or verified as reversible.
- The classifier must log its reasoning to `results/decisions/` for audit trail.
- Parallel invocations must not mutate shared state; all output is written to isolated files keyed by decision ID.

## Properties

- **parallel-safe**: true -- Multiple decisions can be classified simultaneously without conflict.
- **idempotent**: true -- Re-classifying the same change with identical inputs produces the same output.
- **deterministic**: true -- Same inputs always yield the same classification.
