# ADR-0019: install.sh and install.bat Step 4 Module Path Fix

**Status:** Accepted
**Date:** 2026-04-19
**Author:** deployment-council + pre-deploy-council (v5.9.1 re-audit)

## Context

Finding F-01 (P0-3 — CRITICAL) identified that step 4 of both `install.sh` (lines 130–132) and `install.bat` (lines 139–145) attempted to initialise the database using:

```bash
python -m app.db.init_db
```

The `app/` package does not exist in the SYLION directory structure. The actual database module is located at `dashboard/db.py` with the function `init_db()`. Running the installer on a clean machine therefore aborted before the database was created — making the official installation path completely non-functional.

This was the third CRITICAL finding in the re-audit and meant that a user following the documented installation procedure would arrive at an unusable system without a meaningful error message (just `ModuleNotFoundError: No module named 'app'`).

Options considered:
- **I1** — Fix the module path to `dashboard.db` (`python -m dashboard.db`) — but `db.py` uses relative imports
- **I2** — Use `PYTHONPATH` injection: `PYTHONPATH=dashboard python -c "import db; db.init_db()"` (chosen)
- **I3** — Add an `app/` shim package that re-exports `dashboard.db` (adds indirection)
- **I4** — Create a dedicated `scripts/init_db.py` top-level script

## Decision

Fix both scripts to use the following pattern, consistent with how `start.py` already invokes `init_db()`:

**`install.sh` (step 4):**
```bash
echo "Step 4: Initialising database..."
PYTHONPATH="${INSTALL_DIR}/dashboard" python -c "import db; db.init_db()" \
  || { echo "ERROR: Database init failed"; exit 1; }
```

**`install.bat` (step 4):**
```batch
echo Step 4: Initialising database...
set PYTHONPATH=%INSTALL_DIR%\dashboard
python -c "import db; db.init_db()" || exit /b 1
```

Both scripts now also verify the database file exists post-init and abort with a clear message if it does not.

## Consequences

### Positive
- Clean-slate installation now completes successfully end-to-end. E2E install test added to `tests/test_install_e2e.sh`.
- Both Windows and Linux/macOS install paths are fixed simultaneously.

### Negative
- The `PYTHONPATH` injection is fragile if the project directory structure changes (e.g., if `dashboard/` is renamed or flattened). This is noted as tech debt; a proper entry-point script (`pyproject.toml` `[scripts]`) is the long-term fix.

### Neutral
- `install.sh` error handling upgraded to `set -euo pipefail` throughout as part of this change (previously `set -e` only).

## Alternatives Considered

- **I3 (app/ shim)**: Adds a permanently misleading package name to the codebase. Rejected.
- **I4 (scripts/init_db.py)**: Clean solution but requires creating and maintaining a new file. `PYTHONPATH` injection is simpler for a patch release and matches the pattern already used in `start.py`.

## References

- `install.sh` — lines 130–132 (patched)
- `install.bat` — lines 139–145 (patched)
- `dashboard/start.py` — reference implementation of PYTHONPATH pattern
- `dashboard/db.py` — `init_db()` function
- Finding F-01 in `FINDINGS_MATRIX_v591.md`
- `council/install_sh/REPORT.md` — prepared diff
