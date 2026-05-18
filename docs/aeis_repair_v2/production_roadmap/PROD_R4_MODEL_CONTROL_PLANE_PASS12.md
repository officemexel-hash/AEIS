# PROD R4 ModelControlPlane PASS1/PASS2

Date: 2026-05-18
Roadmap items: `C.4 Model council global plane`, `Luka 4 Model Plane Split`
Decision pack: `results/decisions/PROD-D3-MODEL-CONTROL-PLANE_evidence_pack.json`
Status: `FROZEN_2X` for unified provider/model/routing/budget/council control facade

## Scope

This freeze covers:

- New `sylion.cognitive.model_control_plane.ModelControlPlane` as one facade over:
  - provider registry state,
  - `ModelRegistry`,
  - `ModelRouter`,
  - `ModelBudgetManager`,
  - council model assignment config.
- Provider registration writes provider metadata and registers each declared model in both `ModelRegistry` and `ModelRouter`.
- Routing config requires primary and fallback models to exist in `ModelRegistry`.
- Route resolution checks `ModelBudgetManager.check_budget()` before returning a selected model.
- Budget-blocked primary models fall back to the next configured model.
- Council config requires every role assignment to reference a registered `ModelRegistry.model_id`.
- API endpoints:
  - `POST /api/v1/model-control-plane/providers`
  - `GET /api/v1/model-control-plane/providers`
  - `POST /api/v1/model-control-plane/budgets`
  - `POST /api/v1/model-control-plane/routing`
  - `GET /api/v1/model-control-plane/routing`
  - `POST /api/v1/model-control-plane/routing/resolve`
  - `POST /api/v1/model-control-plane/council-config`
  - `GET /api/v1/model-control-plane/council-config`
  - `GET /api/v1/model-control-plane/snapshot`
- Existing budget contract repaired: unlimited budgets now expose `remaining_daily` and `remaining_monthly` as `inf`, matching the existing test contract.
- API budget responses sanitize non-finite internal values to JSON-safe `null`, so HTTP serialization remains valid.

## Files Changed

- `src/sylion-pipeline/sylion/cognitive/model_control_plane.py`
- `src/sylion-pipeline/sylion/api/model_control_plane_routes.py`
- `src/sylion-pipeline/sylion/api/router.py`
- `src/sylion-pipeline/sylion/api/model_budget_routes.py`
- `src/sylion-pipeline/sylion/api/monitoring_budget_routes.py`
- `src/sylion-pipeline/sylion/cognitive/__init__.py`
- `src/sylion-pipeline/sylion/monitoring/model_budget.py`
- `src/sylion-pipeline/tests/test_model_control_plane.py`

## Verification PASS1

Initial run found an existing budget contract bug:

```text
FAILED test_model_budget.py::TestCheckBudget::test_unlimited_when_zero
FAILED test_model_budget.py::TestCheckBudget::test_nonexistent_model_allowed
```

Repair applied:

```text
ModelBudgetManager.check_budget now returns float("inf") for remaining_daily and remaining_monthly when the budget is unlimited or missing. API routes sanitize those internal values to JSON-safe null.
```

Final PASS1 after repair:

```text
python -m pytest src\sylion-pipeline\tests\test_model_control_plane.py src\sylion-pipeline\tests\test_model_registry.py src\sylion-pipeline\tests\test_model_router.py src\sylion-pipeline\tests\test_model_budget.py src\sylion-pipeline\tests\test_model_runtime_policy.py src\sylion-pipeline\tests\test_council_model_policy.py src\sylion-pipeline\tests\test_provider_catalog_routes.py src\sylion-pipeline\tests\test_monitoring_budget_routes.py -q
232 passed, 6 warnings

python -m compileall -q src\sylion-pipeline\sylion\cognitive\model_control_plane.py src\sylion-pipeline\sylion\api\model_control_plane_routes.py src\sylion-pipeline\sylion\api\model_budget_routes.py src\sylion-pipeline\sylion\api\monitoring_budget_routes.py src\sylion-pipeline\sylion\monitoring\model_budget.py src\sylion-pipeline\sylion\api\router.py
PASS
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\test_model_control_plane.py src\sylion-pipeline\tests\test_model_registry.py src\sylion-pipeline\tests\test_model_router.py src\sylion-pipeline\tests\test_model_budget.py src\sylion-pipeline\tests\test_model_runtime_policy.py src\sylion-pipeline\tests\test_council_model_policy.py src\sylion-pipeline\tests\test_provider_catalog_routes.py src\sylion-pipeline\tests\test_monitoring_budget_routes.py -q
232 passed, 6 warnings

git diff --check
PASS
```

Known warnings are historical deprecation warnings from legacy security/vault imports.

## Boundary

This freeze establishes the single control facade and enforces registered-model and budget checks for ModelControlPlane routes. It does not yet migrate every legacy LLM call site, advisor preference override, council workflow or provider call to resolve models exclusively through `ModelControlPlane.resolve_route()`. That call-site migration remains a follow-up production roadmap slice.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-MODEL-CONTROL-PLANE_evidence_pack.json
```

Expected rollback time: 25 minutes.
Data loss risk: `LOW`; provider, route and council config rows can remain inert if code is rolled back.
