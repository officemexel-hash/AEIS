---
name: postgres-schema-builder
description: Creates PostgreSQL migration scripts with CREATE TABLE, indexes, constraints, JSONB columns, and proper types. Follows sylion/db/pg_migration.py pattern.
---

# PostgreSQL Schema Builder

## When to use

Invoke this skill when you need to create or evolve a PostgreSQL schema for a SYLION module. This includes:

- Generating the initial `CREATE TABLE` migration for a new module
- Adding indexes, constraints, and JSONB columns to support event sourcing, projections, or domain models
- Evolving an existing schema with additive migrations (new columns, new indexes)
- Producing migration scripts that follow the SYLION `pg_migration.py` pattern

Do NOT use this skill for:

- SQLite-backed services (use `service-scaffolder-python`)
- Test generation (use `golden-set-writer` or `contract-test-writer`)
- Data seeding or fixture generation

## Inputs

| Name              | Type   | Required | Description                                                        |
|-------------------|--------|----------|--------------------------------------------------------------------|
| module_id         | string | yes      | Fully qualified module ID, e.g. `sylion.surface.event_sourcing_store` |
| schema_definition | object | yes      | Structured schema specification (tables, columns, types, indexes, constraints) |

### schema_definition structure

```json
{
  "tables": [
    {
      "name": "events",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "nullable": false},
        {"name": "aggregate_id", "type": "UUID", "nullable": false},
        {"name": "event_type", "type": "TEXT", "nullable": false},
        {"name": "payload", "type": "JSONB", "nullable": false},
        {"name": "created_at", "type": "TIMESTAMPTZ", "nullable": false, "default": "NOW()"}
      ],
      "primary_key": ["id"],
      "indexes": [
        {"name": "idx_events_aggregate", "columns": ["aggregate_id"], "unique": false},
        {"name": "idx_events_type_created", "columns": ["event_type", "created_at"], "unique": false}
      ],
      "constraints": [
        {"name": "chk_payload_not_empty", "type": "CHECK", "expression": "payload != '{}'::jsonb"}
      ]
    }
  ]
}
```

## Outputs

| File           | Description                                              |
|----------------|----------------------------------------------------------|
| migration.sql  | Idempotent migration script with CREATE/INDEX/CONSTRAINT |

## Execution steps

1. **Read reference pattern** -- Open `sylion/db/pg_migration.py` (or the nearest equivalent) and extract the canonical migration structure:
   - Migration header with module ID, version, and timestamp
   - `CREATE TABLE IF NOT EXISTS` for each table
   - Explicit column types (prefer `BIGSERIAL`, `UUID`, `TEXT`, `JSONB`, `TIMESTAMPTZ`)
   - `CREATE INDEX IF NOT EXISTS` for declared indexes
   - `ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS` for constraints
   - Down-migration in a transaction block at the end

2. **Parse schema_definition** -- Validate the input object:
   - Every table must have at least one column
   - Every table must have a primary key
   - Column types must be valid PostgreSQL types
   - Index names must be unique within the migration

3. **Generate up-migration** -- Emit SQL in this order:
   - Transaction begin
   - `CREATE SCHEMA IF NOT EXISTS` for module namespace (if applicable)
   - `CREATE TABLE IF NOT EXISTS` statements (respect foreign key ordering)
   - `CREATE INDEX IF NOT EXISTS` statements (concurrently-safe)
   - `ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS` statements
   - Transaction commit

4. **Generate down-migration** -- Emit a commented rollback block:
   - Drop constraints in reverse order
   - Drop indexes
   - Drop tables in reverse dependency order
   - All wrapped in a transaction

5. **Add metadata comments** -- Prepend the migration file with:
   ```sql
   -- Migration: <module_id>
   -- Version: 001
   -- Created: <ISO-8601 timestamp>
   -- Description: Initial schema for <module_id>
   ```

6. **Validate SQL** -- Run a syntax check (dry-run with `EXPLAIN` or equivalent). Fix any errors before finishing.

7. **Lint** -- Ensure:
   - No bare `DROP TABLE` without `IF EXISTS`
   - No `ALTER TABLE ... DROP COLUMN` in up-migrations (additive only)
   - All JSONB columns have a sensible default or constraint
   - Timestamp columns use `TIMESTAMPTZ`, not `TIMESTAMP`

## Safety rules

1. **Additive only** -- Up-migrations must only ADD tables, columns, indexes, and constraints. Never DROP or ALTER existing columns.
2. **Idempotent** -- Every statement uses `IF NOT EXISTS` / `IF EXISTS` so re-running is safe.
3. **No secrets** -- Migration scripts must never contain credentials, connection strings, or raw secrets.
4. **Transactional** -- The entire up-migration must be wrapped in a single transaction.
5. **JSONB defaults** -- JSONB columns must either have a default (`'{}'::jsonb`) or a NOT NULL constraint with a CHECK.
6. **Proper timestamp types** -- Always use `TIMESTAMPTZ`. Never use `TIMESTAMP` without timezone.
7. **No data migration** -- This skill generates DDL only. Data migrations require a separate, reviewed script (D3+ decision).

## Test definition

The generated migration MUST pass the following minimum test suite:

1. **Syntax test** -- Migration file parses without errors in `psql --dry-run` or equivalent.
2. **Idempotency test** -- Running the migration twice produces no errors and no duplicate objects.
3. **Round-trip test** -- Running up-migration then down-migration leaves the schema in the original state.
4. **Constraint test** -- Declared constraints reject invalid data (e.g., empty JSONB where CHECK forbids it).
5. **Index test** -- Declared indexes exist and are used by query planner for relevant queries.

## Evidence definition

On completion, the skill produces:

| Artifact              | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| migration.sql         | The generated migration script (up + down)                     |
| syntax_check.log      | Output of the SQL syntax validation                            |
| idempotency_test.log  | Log of running the migration twice                             |

## Properties

| Property      | Value  | Description                                                        |
|---------------|--------|--------------------------------------------------------------------|
| parallel-safe | true   | Each invocation targets a distinct module_id; no shared state      |
| idempotent    | true   | Re-running produces identical output; IF NOT EXISTS guards         |
