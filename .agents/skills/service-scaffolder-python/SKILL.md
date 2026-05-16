---
name: service-scaffolder-python
description: Scaffolds a Python service module following the SYLION pattern (SQLite-backed, thread-safe, EventBus integration, dataclass models, global singleton). Reads console_api.py as reference pattern.
---

# Service Scaffolder -- Python

## When to use

Invoke this skill when you need to create a new SYLION service module in Python. This includes:

- Bootstrapping a fresh module from a proto contract or module specification
- Generating the boilerplate service layer with correct SYLION patterns baked in
- Adding a new surface or domain module that needs SQLite persistence, EventBus wiring, and a thread-safe singleton

Do NOT use this skill for:

- Frontend components or Next.js pages
- Pure SQL migration scripts (use `postgres-schema-builder`)
- Test generation (use `golden-set-writer` or `contract-test-writer`)

## Inputs

| Name       | Type   | Required | Description                                           |
|------------|--------|----------|-------------------------------------------------------|
| module_id  | string | yes      | Fully qualified module ID, e.g. `sylion.surface.console_api` |
| proto_file | string | no       | Path to the `.proto` contract to derive RPC stubs from |

## Outputs

| File         | Description                                       |
|--------------|---------------------------------------------------|
| service.py   | Full service implementation with SYLION patterns  |
| __init__.py  | Package init re-exporting the singleton accessor  |

## Execution steps

1. **Read reference pattern** -- Open `console_api.py` (or the nearest equivalent in the target package) and extract the canonical structure:
   - `@dataclass` models for request/response
   - `threading.Lock` for thread safety
   - `sqlite3.connect(..., check_same_thread=False)` for persistence
   - `EventBus.publish(subject, payload)` calls after mutations
   - `_instance = None` / `get_instance()` class-level singleton

2. **Parse proto contract (optional)** -- If `proto_file` is provided, extract RPC method names, request/response message types, and field definitions. Map each RPC to a public method on the service class.

3. **Scaffold dataclass models** -- For each message type in the contract, emit a `@dataclass` with typed fields. Use Python built-in types; fall back to `Any` for complex nested messages.

4. **Scaffold service class** -- Generate the class body:
   - `__init__` -- initialise SQLite connection, create tables via `_init_db()`, acquire `threading.Lock`
   - `_init_db()` -- `CREATE TABLE IF NOT EXISTS` statements matching the dataclass fields
   - Public methods -- one per RPC, each wrapping DB operations in `with self._lock`
   - EventBus hooks -- call `self._event_bus.publish(...)` after every mutation (insert, update, delete)
   - `get_instance()` class method -- classic singleton with `_instance` class variable

5. **Generate `__init__.py`** -- Re-export the singleton accessor:
   ```python
   from .service import <ServiceName>
   get_<service_name> = <ServiceName>.get_instance
   ```

6. **Verify consistency** -- Ensure:
   - Every public method acquires `self._lock`
   - Every mutation publishes an event
   - SQL table columns match dataclass fields exactly
   - No raw secrets or credentials in generated code

7. **Run lint** -- Execute `ruff check` or equivalent on the generated files. Fix any violations before finishing.

## Safety rules

1. **No secrets in generated code** -- Never hardcode API keys, tokens, or connection strings. Use environment variables or a secrets accessor.
2. **Thread safety is mandatory** -- Every method that reads or writes shared state MUST acquire `self._lock`.
3. **Append-only events** -- Never emit UPDATE or DELETE events on the event store stream. Mutations produce new events; corrections produce compensating events.
4. **Idempotent init** -- `_init_db()` must use `CREATE TABLE IF NOT EXISTS` so repeated calls are safe.
5. **Singleton safety** -- `get_instance()` must handle the race condition (double-checked locking or module-level init).
6. **No external I/O in constructor** -- The `__init__` may open SQLite but must NOT make network calls.

## Test definition

The generated service MUST pass the following minimum test suite:

1. **Init test** -- `get_instance()` returns the same object on repeated calls.
2. **CRUD test** -- Create, read, update, delete a record end-to-end.
3. **Thread safety test** -- Spawn 10 threads, each performing a mutation; assert no data corruption.
4. **EventBus test** -- Verify that each mutation publishes the correct event subject and payload.
5. **Edge case test** -- Handle duplicate inserts, missing records, and empty inputs gracefully.

All tests use in-memory SQLite (`:memory:`) for isolation.

## Evidence definition

On completion, the skill produces:

| Artifact              | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| service.py            | The scaffolded service module                                  |
| __init__.py           | Package init with singleton accessor                           |
| lint_report.txt       | Output of `ruff check` (or equivalent) on generated files     |
| test_run.log          | Execution log of the minimum test suite (all passing)         |

## Properties

| Property      | Value  | Description                                                     |
|---------------|--------|-----------------------------------------------------------------|
| parallel-safe | true   | Each invocation targets a distinct module_id; no shared state   |
| idempotent    | true   | Re-running on the same module_id overwrites scaffolding safely  |
