# PROD R4 SkillIntegrationLayer PASS1/PASS2

Date: 2026-05-18
Roadmap items: `C.3 Skills runtime integration`, `Luka 3 Skills Split`
Decision pack: `results/decisions/PROD-D3-SKILL-INTEGRATION-LAYER_evidence_pack.json`
Status: `FROZEN_2X` for pipeline-step execution, dispatch execution, demand consumption and Evidence Spine registration

## Scope

This freeze covers:

- New `sylion.skills.integration.SkillIntegrationLayer` as the bridge between skills runtime, pipeline steps, dispatch and evidence.
- `SkillExecutionContext` fields: `skill_id`, `inputs`, `project_id`, `pipeline_id`, `step_id`, `dispatch_source`, `actor_id`, `retention_policy`.
- Pipeline skill execution through `execute_pipeline_step(...)`, including `project_id`, `pipeline_id` and `step_id` propagation into runtime inputs.
- Dispatch skill execution through `dispatch(...)`, including `dispatch_source` propagation for J5-style dispatch.
- Every integrated skill execution registers an Evidence Spine JSON artifact with `artifact_type=skill_execution`, source `skills.pipeline` or `skills.dispatch`, checksum and metadata.
- Demand signal consumption through `record_demand_and_analyze(...)`, which records a signal and immediately returns the current demand analysis report.
- Event emission for `skill.integration.executed` and `skill.integration.demand_consumed` when an event bus is supplied.
- Public hook: `sylion.skills.get_skill_integration_layer`.
- API endpoints:
  - `POST /api/v1/skills/integration/pipeline-step`
  - `POST /api/v1/skills/integration/dispatch`
  - `POST /api/v1/skills/integration/demand`

## Files Changed

- `src/sylion-pipeline/sylion/skills/integration.py`
- `src/sylion-pipeline/sylion/skills/demand_signal.py`
- `src/sylion-pipeline/sylion/skills/__init__.py`
- `src/sylion-pipeline/sylion/api/skills_routes.py`
- `src/sylion-pipeline/tests/skills/test_integration_layer.py`
- `src/sylion-pipeline/tests/skills/test_routes.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\skills src\sylion-pipeline\tests\test_skills_runtime.py src\sylion-pipeline\tests\test_skills_registry.py src\sylion-pipeline\tests\test_skills_executor.py src\sylion-pipeline\tests\test_demand_signal.py -q
154 passed, 4 warnings

python -m compileall -q src\sylion-pipeline\sylion\skills\integration.py src\sylion-pipeline\sylion\api\skills_routes.py src\sylion-pipeline\sylion\skills\demand_signal.py
PASS
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\skills src\sylion-pipeline\tests\test_skills_runtime.py src\sylion-pipeline\tests\test_skills_registry.py src\sylion-pipeline\tests\test_skills_executor.py src\sylion-pipeline\tests\test_demand_signal.py -q
154 passed, 4 warnings

git diff --check
PASS
```

Known warnings are historical deprecation warnings from `sylion.security.__init__`.

## Boundary

This freeze establishes the integration layer, API surface and evidence contract. It does not yet make every W10 pipeline step, W16 execution path or J5 dispatch rule automatically choose skills in production. Those orchestration call sites still need to be migrated to call `SkillIntegrationLayer` as a follow-up production roadmap slice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-SKILL-INTEGRATION-LAYER_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE` for code rollback; recorded `skill_execution` Evidence Spine artifacts can remain immutable audit artifacts.
