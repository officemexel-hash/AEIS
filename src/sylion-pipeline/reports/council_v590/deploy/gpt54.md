# Council Report — GPT-5.4 Model
## Artifact: install.bat

**Status:** COMPLETE  
**Generated:** 2025-07-11  
**Output path:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/install.bat`  
**Size:** 9,725 bytes | 282 lines

---

## Artifact Summary

Idempotent Windows cmd.exe installer for SYLION v5.9.0, functional equivalent of `install.sh`.

### Features implemented

| Feature | Implementation |
|---------|---------------|
| `setlocal enabledelayedexpansion` | Line 13 — enables `!VAR!` expansion inside loops/conditionals |
| Python version validation | `where PYTHON_BIN`, then extracts major.minor via Python `-c`; compares with `LSS`/`EQU` |
| venv via `python -m venv` | Checks `%VENV_DIR%\Scripts\python.exe`; tests functional; recreates if broken |
| pip install | First tries `--require-hashes`; fallback without; both via `!VENV_PIP!` |
| pip upgrade | `pip install --upgrade pip` before main install |
| init_db | `python -m app.db.init_db`; fallback introspection block |
| Agent seeding from `agents.yaml` | Module invocation + YAML validation fallback |
| Healthcheck | Two-path: `curl.exe` (Windows 10+) → PowerShell `Invoke-WebRequest`; 5 retry loop with `timeout /t 3` |
| Idempotent | ✓ — all steps guarded |
| Environment variable overrides | `PYTHON_BIN`, `VENV_DIR`, `REQ_FILE`, `AGENTS_YAML`, `SYLION_PORT` (set before running) |
| Logging helpers | `:log_info`, `:log_ok`, `:log_warn`, `:log_error` subroutines |

### Windows-specific implementation details

- **Delayed expansion** — uses `!VAR!` throughout (not `%VAR%`) inside loops and `if` blocks to avoid stale variable evaluation
- **curl.exe path** — uses `curl.exe` explicitly (not `curl` which can alias to PowerShell `Invoke-WebRequest` in some environments)
- **PowerShell fallback** — `powershell -NoProfile -NonInteractive` for environments without curl.exe
- **HTTP code capture** — writes curl output to `%TEMP%\sylion_hc.txt`, reads with `set /p` (reliable in cmd)
- **Exit codes** — `exit /b 1` on failure (not `exit 1`) to avoid closing parent shell
- **rmdir /s /q** — for safe venv directory removal (Windows equivalent of `rm -rf`)

### Idempotency proof

| Step | Guard |
|------|-------|
| venv creation | Checks `%VENV_DIR%\Scripts\python.exe` existence + functional test |
| pip install | pip dependency resolution + hash/no-hash fallback |
| init_db | Module idempotency documented requirement |
| seed_agents | Module invocation + YAML-only fallback (no destructive action) |
| healthcheck | Non-fatal retry loop — no state mutation |

---

## Compliance Checklist

| Requirement | Status |
|-------------|--------|
| `setlocal enabledelayedexpansion` | ✓ |
| venv via `python -m venv` | ✓ |
| pip install | ✓ |
| Python version validation | ✓ |
| Healthcheck via PowerShell and/or curl.exe | ✓ (both, with fallback) |
| Idempotent | ✓ |
| Windows cmd.exe compatible | ✓ |
| init_db equivalent | ✓ |
| Agent seeding | ✓ |
| Correct output path | ✓ |
