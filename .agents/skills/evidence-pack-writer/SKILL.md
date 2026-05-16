---
name: evidence-pack-writer
description: Creates Evidence Pack for D3+ decisions. Includes decision_id, class, rationale, rollback_plan, fidelity_test, and timestamp. Every D3+ decision MUST have an evidence pack.
---

# Evidence Pack Writer

## When to use

Invoke this skill when a D3+ decision has been made or is being proposed and requires a formal evidence pack. This includes:

- Documenting a D3 (Significant), D4 (Major), or D5 (Critical) decision
- Creating the evidence artifact required before a Council vote
- Recording the rationale, rollback plan, and fidelity test for a consequential architectural or operational change
- Producing the audit trail for governance review

Do NOT use this skill for:

- D0 (Trivial), D1 (Minor), or D2 (Moderate) decisions (these do not require formal evidence packs)
- Test generation (use `golden-set-writer` or `contract-test-writer`)
- Service scaffolding (use `service-scaffolder-python`)

## Inputs

| Name           | Type   | Required | Description                                                      |
|----------------|--------|----------|------------------------------------------------------------------|
| decision_id    | string | yes      | Unique identifier for the decision (e.g., `D-2026-0042`)        |
| decision_class | string | yes      | Decision class: D3, D4, or D5                                    |
| rationale      | string | yes      | Human-readable explanation of why this decision is necessary     |

## Outputs

| File               | Description                                              |
|--------------------|----------------------------------------------------------|
| evidence_pack.json | Structured evidence pack for the decision                |

## Execution steps

1. **Validate decision class** -- Confirm `decision_class` is one of `D3`, `D4`, or `D5`. If the class is D0-D2, reject the invocation with a clear message: "Evidence packs are only required for D3+ decisions. This decision is classified as <class>."

2. **Check for existing pack** -- Search the evidence pack directory for an existing file matching `decision_id`. If found:
   - Log a warning: "Evidence pack for <decision_id> already exists. This will create a NEW version."
   - Append a `previous_versions` array entry pointing to the prior pack
   - Do NOT overwrite the existing file; create a new file with a version suffix

3. **Construct evidence pack** -- Build the JSON structure:

   ```json
   {
     "decision_id": "<decision_id>",
     "decision_class": "<decision_class>",
     "rationale": "<rationale>",
     "rollback_plan": {
       "strategy": "<ROLLBACK | MITIGATE | ACCEPT>",
       "steps": [],
       "estimated_time": "<duration>",
       "data_loss_risk": "<NONE | PARTIAL | FULL>",
       "tested": false
     },
     "fidelity_test": {
       "description": "<how to verify the decision was correctly applied>",
       "pre_conditions": [],
       "steps": [],
       "expected_outcome": "",
       "automated": false
     },
     "timestamp": "<ISO-8601 UTC>",
     "author": "<invoker or system>",
     "status": "DRAFT",
     "council_required": true,
     "council_votes": [],
     "tags": []
   }
   ```

4. **Generate rollback plan** -- Based on the decision class and rationale, propose a rollback strategy:
   - D3: Default `MITIGATE`. Document mitigation steps.
   - D4: Default `ROLLBACK`. Document rollback steps and estimated time.
   - D5: Require explicit `ACCEPT` only if rollback is impossible. Document why rollback is not feasible.
   - Set `tested: false` -- the author must confirm rollback has been tested before setting to `true`.

5. **Generate fidelity test** -- Based on the rationale, propose a test that verifies:
   - The decision was correctly applied
   - The system behaves as expected after the change
   - The change does not introduce regressions
   - Set `automated: false` -- the author must provide automation if applicable.

6. **Set metadata** -- Populate:
   - `timestamp`: Current UTC time in ISO-8601 format
   - `author`: The invoking agent or user
   - `status`: Always `DRAFT` initially (must be promoted to `REVIEWED` after Council approval)
   - `council_required`: Always `true` for D3+
   - `council_votes`: Empty array (populated during Council review)
   - `tags`: Extract keywords from rationale for searchability

7. **Validate JSON** -- Ensure the output is valid JSON and all required fields are present. Reject if any required field is missing.

8. **Write file** -- Save to the evidence pack directory with filename pattern:
   - `<decision_id>_evidence_pack.json`
   - If versioned: `<decision_id>_evidence_pack_v2.json`

## Safety rules

1. **Every D3+ decision MUST have an evidence pack** -- No exceptions. If a D3+ decision is detected without a pack, this skill MUST be invoked.
2. **Never overwrite existing packs** -- Previous versions are immutable. Always create a new version.
3. **Rollback plan is mandatory** -- Every evidence pack must have a non-empty rollback plan. `ACCEPT` (no rollback) is only valid for D5 with explicit justification.
4. **Fidelity test is mandatory** -- Every evidence pack must include a testable verification plan.
5. **No secrets in evidence packs** -- Never include raw credentials, tokens, or connection strings in rationale, rollback plans, or fidelity tests. Use references (e.g., "secret ref: vault://path/to/key").
6. **Status starts as DRAFT** -- The pack must not be marked `APPROVED` until Council has voted. Any pack with `status: APPROVED` but empty `council_votes` is invalid.
7. **Timestamp is immutable** -- Once set, the creation timestamp must never be modified in subsequent versions.

## Test definition

The evidence pack generation must pass:

1. **Schema validation** -- Output JSON conforms to the evidence pack schema (all required fields present, correct types).
2. **Decision class guard** -- Invoking with D0-D2 returns an error and produces no file.
3. **Idempotency guard** -- Re-invoking with the same `decision_id` creates a versioned file, never overwrites.
4. **Rollback plan completeness** -- Every generated pack has a non-empty rollback plan with at least one step.
5. **Fidelity test completeness** -- Every generated pack has a fidelity test with at least one verification step.
6. **No secrets leakage** -- Scan the output for common secret patterns (API keys, tokens, passwords). Reject if found.

## Evidence definition

On completion, the skill produces:

| Artifact                    | Description                                                |
|-----------------------------|------------------------------------------------------------|
| evidence_pack.json          | The structured evidence pack for the decision              |
| evidence_pack_log.txt       | Log of the generation process (validations, warnings)      |
| previous_versions.json      | (If versioned) List of previous pack file paths            |

## Properties

| Property      | Value   | Description                                                        |
|---------------|---------|--------------------------------------------------------------------|
| parallel-safe | true    | Each invocation targets a distinct decision_id; no shared state    |
| idempotent    | false   | Re-invoking creates a NEW version; packs are append-only artifacts |
