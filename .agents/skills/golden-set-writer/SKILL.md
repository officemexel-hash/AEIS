---
name: golden-set-writer
description: Creates golden test sets for contract validation. Minimum 3 tests per contract. Tests init, CRUD, edge cases. Uses in-memory SQLite for isolation.
---

# Golden Set Writer

## When to use

Invoke this skill when you need to create a golden test set that validates a module's contract. This includes:

- Generating the initial test suite for a newly scaffolded service
- Writing canonical test cases that define expected behavior (the "golden" standard)
- Ensuring contract compliance for a module before integration testing
- Creating tests that serve as living documentation of correct behavior

Do NOT use this skill for:

- Integration or end-to-end tests (use `contract-test-writer`)
- Service scaffolding (use `service-scaffolder-python`)
- Schema migrations (use `postgres-schema-builder`)

## Inputs

| Name       | Type   | Required | Description                                           |
|------------|--------|----------|-------------------------------------------------------|
| module_id  | string | yes      | Fully qualified module ID, e.g. `sylion.surface.console_api` |
| proto_file | string | no       | Path to the `.proto` contract to derive test cases from |

## Outputs

| File              | Description                                           |
|-------------------|-------------------------------------------------------|
| test_golden.py    | Golden test suite with minimum 3 tests per contract   |

## Execution steps

1. **Read service source** -- Open the target module's `service.py` (or equivalent) and extract:
   - Public method signatures
   - Dataclass models
   - EventBus subjects published
   - SQLite table schemas

2. **Read proto contract (optional)** -- If `proto_file` is provided, extract RPC definitions and map them to service methods. Use the proto to determine required fields, optional fields, and expected error conditions.

3. **Design test categories** -- For each public method, design tests in these categories:

   **a. Init tests**
   - Verify singleton returns the same instance
   - Verify DB tables are created
   - Verify initial state is empty/correct

   **b. CRUD tests** (minimum one per operation)
   - Create: insert a valid record, verify it can be read back
   - Read: query by ID, query by filter, query empty result
   - Update: modify a field, verify change persisted
   - Delete: remove a record, verify it no longer exists

   **c. Edge case tests** (minimum one per method)
   - Duplicate insert (idempotency)
   - Missing record (not found / raises)
   - Empty input (validation)
   - Null/None fields (handling)
   - Maximum field lengths (boundary)
   - Concurrent access (thread safety smoke test)

4. **Write test file** -- Generate `test_golden.py` with:
   - `pytest` framework
   - `@pytest.fixture` for service setup using in-memory SQLite (`:memory:`)
   - One test class per logical entity (e.g., `TestEventStore`, `TestArtifactControl`)
   - Descriptive test names: `test_<method>_<scenario>_<expected>`
   - Assertions using plain `assert` statements
   - EventBus mock to verify published events

5. **Enforce minimum coverage** -- Ensure at least 3 tests exist per contract method:
   - 1 happy path
   - 1 edge case
   - 1 error/boundary condition

6. **Run tests** -- Execute `pytest test_golden.py -v` and verify all tests pass. Fix any failures.

7. **Document test intent** -- Each test function must have a docstring explaining:
   - What is being tested
   - What the expected outcome is
   - Why this test exists (e.g., "Verifies idempotent insert on duplicate event_id")

## Safety rules

1. **In-memory SQLite only** -- All tests must use `sqlite3.connect(":memory:")`. Never write to disk or connect to a real database.
2. **No network calls** -- Tests must not make HTTP, gRPC, or any network requests. Mock all external dependencies.
3. **No shared state between tests** -- Each test must create its own service instance or use a fixture that resets state.
4. **Deterministic** -- Tests must produce the same result on every run, regardless of execution order.
5. **No secrets** -- Test data must never contain real credentials, tokens, or API keys.
6. **Thread safety isolation** -- Thread safety tests must use fresh instances; do not share instances across thread-boundary tests.

## Test definition

The golden test suite itself is the output. It must satisfy:

1. **Minimum 3 tests per contract method** -- Happy path, edge case, error condition.
2. **100% method coverage** -- Every public method on the service class has at least one test.
3. **All tests pass** -- `pytest` exits with code 0.
4. **No flaky tests** -- Running the suite 10 times in sequence produces identical results.

## Evidence definition

On completion, the skill produces:

| Artifact              | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| test_golden.py        | The golden test suite                                          |
| pytest_report.txt     | Verbose output of `pytest test_golden.py -v`                  |
| coverage_report.txt   | Output of `pytest --cov=<module> test_golden.py` (line coverage) |

## Properties

| Property      | Value  | Description                                                     |
|---------------|--------|-----------------------------------------------------------------|
| parallel-safe | true   | Each invocation targets a distinct module_id; no shared state   |
| idempotent    | true   | Re-running overwrites the test file with identical content      |
