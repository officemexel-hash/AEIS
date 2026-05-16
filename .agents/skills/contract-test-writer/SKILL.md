---
name: contract-test-writer
description: Writes integration tests validating module contract compliance. Verifies all RPC methods, edge cases, error handling, and thread safety.
---

# Contract Test Writer

## When to use

Invoke this skill when you need to write integration tests that verify a SYLION module complies with its declared contract. This includes:

- Validating that every RPC method in the proto contract is correctly implemented
- Testing error handling, timeout behavior, and edge cases across module boundaries
- Verifying thread safety under concurrent load
- Ensuring EventBus integration works correctly (events are published with correct subjects and payloads)
- Regression testing after contract or implementation changes

Do NOT use this skill for:

- Unit-level golden tests (use `golden-set-writer`)
- Service scaffolding (use `service-scaffolder-python`)
- Schema migrations (use `postgres-schema-builder`)

## Inputs

| Name       | Type   | Required | Description                                           |
|------------|--------|----------|-------------------------------------------------------|
| module_id  | string | yes      | Fully qualified module ID, e.g. `sylion.surface.command_bus` |
| proto_file | string | no       | Path to the `.proto` contract defining the RPC surface |

## Outputs

| File               | Description                                                  |
|--------------------|--------------------------------------------------------------|
| test_contract.py   | Integration test suite validating full contract compliance   |

## Execution steps

1. **Read proto contract** -- Open `proto_file` and extract:
   - All RPC method names and their request/response types
   - Field types, cardinality (required/optional/repeated)
   - Service-level options and annotations
   - Streaming semantics (client-streaming, server-streaming, bidi, unary)

2. **Read service implementation** -- Open the target module's `service.py` and map:
   - RPC methods to Python method implementations
   - Error types raised for each failure mode
   - EventBus subjects published per method
   - SQLite tables touched per method

3. **Design test matrix** -- For each RPC method, create a test matrix:

   **a. Happy path tests**
   - Valid input produces correct output type and values
   - Response fields match expected shape
   - Side effects (DB writes, event publishes) are correct

   **b. Error handling tests**
   - Missing required fields raise the correct error type
   - Invalid field values raise validation errors
   - Non-existent records return not-found (not exception)
   - Duplicate operations behave idempotently

   **c. Edge case tests**
   - Empty collections (empty repeated fields)
   - Maximum field lengths
   - Unicode and special characters in string fields
   - Null/None handling for optional fields
   - Concurrent mutations on the same entity

   **d. Thread safety tests**
   - Spawn N threads (N >= 10), each calling a mutation RPC
   - Verify no data corruption, no lost updates
   - Verify event ordering is consistent
   - Verify singleton instance is safe under concurrent access

   **e. Contract compliance tests**
   - Every RPC in the proto has at least one test
   - Response messages conform to proto schema
   - Error codes match declared gRPC status codes
   - Streaming RPCs produce correct sequence of responses

4. **Write test file** -- Generate `test_contract.py` with:
   - `pytest` framework with `pytest-asyncio` for async methods
   - `@pytest.fixture` for service initialization (in-memory SQLite)
   - `unittest.mock.patch` for EventBus and external dependencies
   - One test class per RPC method group
   - Parameterized tests using `@pytest.mark.parametrize` for input variations
   - Explicit assertions on response shape, side effects, and error types

5. **Wire EventBus assertions** -- For each mutation test:
   - Capture calls to `EventBus.publish`
   - Assert the correct subject is used
   - Assert the payload contains expected fields
   - Assert publish is called exactly once (or the expected number of times)

6. **Run tests** -- Execute `pytest test_contract.py -v --tb=short` and verify:
   - All tests pass
   - No warnings related to unclosed connections or resources
   - No skipped tests without explicit `pytest.mark.skip` with reason

7. **Generate coverage report** -- Run `pytest --cov=<module> test_contract.py --cov-report=term-missing` and verify:
   - Line coverage >= 80% for the service module
   - All public methods are covered
   - Branch coverage for error paths

## Safety rules

1. **No production databases** -- Tests must use in-memory SQLite or a test-only PostgreSQL instance. Never connect to production or staging databases.
2. **No network calls** -- Mock all gRPC clients, HTTP clients, and external service calls. Tests must run offline.
3. **No flaky tests** -- All tests must be deterministic. Use fixed timestamps, seeds, and mock return values.
4. **No secret leakage** -- Test fixtures must use dummy values for credentials, tokens, and API keys.
5. **Clean teardown** -- Every test must clean up its own state. Fixtures must close connections and release resources.
6. **No test interdependence** -- Each test must be independently runnable. No test may depend on state created by another test.
7. **Thread safety contracts** -- Thread safety tests must document the expected concurrency model (optimistic locking, mutex, etc.).

## Test definition

The contract test suite must satisfy:

1. **100% RPC coverage** -- Every method defined in the proto contract has at least one test.
2. **Error path coverage** -- Every declared error code has at least one test that triggers it.
3. **Thread safety validation** -- At least one concurrent access test per stateful method.
4. **EventBus verification** -- Every mutation test verifies the correct event is published.
5. **All tests pass** -- `pytest` exits with code 0 on a clean environment.

## Evidence definition

On completion, the skill produces:

| Artifact              | Description                                                      |
|-----------------------|------------------------------------------------------------------|
| test_contract.py      | The integration test suite                                       |
| pytest_report.txt     | Verbose output of `pytest test_contract.py -v`                   |
| coverage_report.txt   | Coverage report showing line and branch coverage                 |
| contract_matrix.csv   | CSV mapping each RPC method to its test cases and coverage       |

## Properties

| Property      | Value  | Description                                                     |
|---------------|--------|-----------------------------------------------------------------|
| parallel-safe | true   | Each invocation targets a distinct module_id; no shared state   |
| idempotent    | true   | Re-running overwrites the test file with identical content      |
