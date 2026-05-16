# SYLION AEIS -- Dependency Audit Report

**Generated**: 2026-04-20
**Scanner**: `scripts/check_imports.py`
**Config**: `.import-linter.yml`
**Rule source**: Ksiega v3.5 / Masterplan R2.5

## Summary

| Metric | Value |
|---|---|
| Files scanned | 129 |
| Sylion imports checked | 601 |
| **Violations found** | **3** |
| Compliance rate | 99.5% |

## Violations

### 1. `sylion.core` -> `sylion.governance` (3 imports)

**File**: `core/lifecycle_gates.py:35`

```python
from sylion.governance.council_workflow import CouncilWorkflow, SessionStatus
```

**Why it violates**: Core (Class A: Kernel) is the bottom layer. It must not import from any domain package. Governance is Class E. The import creates a circular dependency risk: `core -> governance -> core`.

**Imported symbols**:
- `CouncilWorkflow` -- used for council approval checks at cutover gates
- `SessionStatus` -- used to check council session status

**Remediation options**:
1. **Extract interface to core**: Move `CouncilWorkflow` / `SessionStatus` protocol definitions into `sylion.core.contract_registry` as a Contract. `lifecycle_gates.py` imports the contract; `governance.council_workflow` provides the implementation.
2. **EventBus pattern**: `lifecycle_gates.py` emits a `council.approval.requested` event and listens for `council.approval.responded`, eliminating the direct import.
3. **Move lifecycle_gates.py**: Since lifecycle gates inherently bridge core modules with governance, move the file from `sylion.core` to a dedicated boundary package (e.g. `sylion.contracts.lifecycle_gates`).

## Architecture Compliance Map

All packages below import ONLY from `sylion.core` (kernel) or within their own boundary. The API facade (`sylion.api`) correctly imports from all packages.

| Package | Class | Imports from core | Cross-package imports | Status |
|---|---|---|---|---|
| `sylion.core` | A (Kernel) | -- | governance (3) | VIOLATION |
| `sylion.governance` | E | Yes (event_bus, decision_gate_engine, evidence_spine) | None | PASS |
| `sylion.memory` | D | Yes (event_bus, evidence_spine) | None | PASS |
| `sylion.cognitive` | B | Yes (event_bus) | None | PASS |
| `sylion.execution` | C | Yes (event_bus) | None | PASS |
| `sylion.security` | F | Yes (event_bus) | None | PASS |
| `sylion.efficiency` | G | Yes (event_bus) | None | PASS |
| `sylion.aeis` | H | Yes (event_bus) | None | PASS |
| `sylion.skills` | I | Yes (event_bus) | None | PASS |
| `sylion.surface` | J | Yes (event_bus) | None | PASS |
| `sylion.rebuild` | K | Yes (event_bus) | None | PASS |
| `sylion.quality` | L | Yes (event_bus) | None | PASS |
| `sylion.devices` | -- | Yes (event_bus) | None | PASS |
| `sylion.sdr` | -- | Yes (event_bus) | None | PASS |
| `sylion.cellular` | -- | Yes (event_bus) | None | PASS |
| `sylion.api` | Facade | Yes (event_bus, contracts, etc.) | All (allowed) | PASS |
| `sylion.db` | Infra | None | None | PASS |
| `sylion.contracts` | Infra | None | None | PASS |

## Recommendations

1. **Fix the single violation** in `core/lifecycle_gates.py` using one of the remediation options above. This brings the codebase to 100% R2.5 compliance.
2. **Add to CI**: Run `python scripts/check_imports.py` as a CI gate to prevent regressions.
3. **Integrate `import-linter`**: The `.import-linter.yml` config is ready for the `lint-imports` CLI tool (from the `import-linter` PyPI package) for teams that prefer the standard tooling over the custom script.
