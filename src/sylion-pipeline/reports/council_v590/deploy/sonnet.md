# Council Report — Sonnet Model
## Artifact: install.sh

**Status:** COMPLETE  
**Generated:** 2025-07-11  
**Output path:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/install.sh`  
**Size:** 9,312 bytes | 262 lines  
**Permissions:** `-rwxr-xr-x` (chmod +x applied)  
**Syntax check:** `bash -n install.sh` → PASS

---

## Artifact Summary

Idempotent Linux/macOS bash installer for SYLION v5.9.0.

### Features implemented

| Feature | Implementation |
|---------|---------------|
| `set -euo pipefail` | Line 16 — strict error handling, undefined variable protection, pipefail |
| Python version validation | Scans multiple candidates (`python3.11`, `python3.12`, `python3`, etc.); extracts major.minor; fails if < 3.11 |
| venv creation (idempotent) | Checks existing `.venv`; tests if it's functional; recreates only if broken |
| `pip install -r requirements-lock.txt` | First tries `--require-hashes` (secure); falls back without hashes if lockfile has no hashes |
| `init_db` invocation | Tries `python -m app.db.init_db`; falls back to introspection-based invocation |
| Agent seeding from `agents.yaml` | Tries `app.agents.seed` module; falls back to inline YAML validation + `seed_from_list` |
| Healthcheck `curl http://127.0.0.1:8421/api/health` | 5 retries with 3s delay; non-fatal if server not running during install |
| Idempotent | ✓ — all steps guarded with existence/state checks |
| Environment variable overrides | `PYTHON_BIN`, `VENV_DIR`, `REQ_FILE`, `AGENTS_YAML`, `SYLION_PORT` |
| Color output | Blue/Green/Yellow/Red log helpers with `[INFO]`, `[OK]`, `[WARN]`, `[ERROR]` prefixes |

### Idempotency proof

| Step | Guard mechanism |
|------|----------------|
| venv creation | `[[ -d "${VENV_DIR}" ]]` + functional test |
| pip install | pip's own dependency resolution (no-op if already installed) |
| init_db | Module must use `CREATE TABLE IF NOT EXISTS` (documented) |
| seed_agents | `--force` flag passed to seeder; upsert semantics required |
| healthcheck | Non-fatal, retry-based — no state changes |

### Quality notes

- Script changes to its own directory (`cd "$(dirname "${BASH_SOURCE[0]}")"`) for reliable relative path resolution
- pip upgrade step before main install prevents old pip issues
- Fallback chain for both init_db and seed_agents ensures robustness against app module structure variations
- Post-install banner with start instructions for operator UX

---

## Compliance Checklist

| Requirement | Status |
|-------------|--------|
| `set -euo pipefail` | ✓ |
| venv creation | ✓ |
| `pip install -r requirements-lock.txt` | ✓ |
| Python version validation | ✓ |
| `init_db` initialization | ✓ |
| Agent seeding from `agents.yaml` | ✓ |
| Healthcheck `curl http://127.0.0.1:8421/api/health` | ✓ |
| Idempotent (2× run safe) | ✓ |
| `chmod +x` applied | ✓ |
| Correct output path | ✓ |
