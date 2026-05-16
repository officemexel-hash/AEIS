# SYLION AEIS Runtime â€” Playwright E2E Test Suite

This directory contains browser-level end-to-end tests for the SYLION AEIS runtime
(FastAPI backend + vanilla-JS SPA). Tests use `pytest-playwright` (Python).

---

## Prerequisites

### 1. Python dependencies

```bash
pip install pytest-playwright requests
```

### 2. Playwright browser binaries

```bash
playwright install chromium
```

### 3. Running app

The tests require a live SYLION AEIS runtime on `http://127.0.0.1:8421`.

```bash
python -m sylion.server --host 127.0.0.1 --http-port 8421 &
```

Wait for the startup message (e.g. `Uvicorn running on http://127.0.0.1:8421`) before
running tests.

---

## Fresh database (recommended)

Many tests (especially `test_e2e_001_first_setup.py`) expect a clean state.
Remove the database before each full run:

```bash
rm -f ~/sylion/sylion.db ~/sylion/sylion_aeis.db
python -m sylion.server --host 127.0.0.1 --http-port 8421 &
```

> **Warning:** Deleting the DB removes all users, sessions, API keys, and pipeline data.
> Never do this on a production instance.

---

## Running the suite

### Full suite

```bash
pytest tests_e2e/ -v
```

### Single file

```bash
pytest tests_e2e/test_e2e_002_login_happy.py -v
```

### Specific test class or function

```bash
pytest tests_e2e/test_e2e_004_rate_limit.py::TestRateLimitAPI::test_sixth_attempt_returns_429 -v
```

### Custom base URL

```bash
pytest tests_e2e/ -v --base-url http://192.168.1.10:8421
```

---

## Test file index

| File | Scenario | Priority | Notes |
|---|---|---|---|
| `conftest.py` | Shared fixtures | â€” | `browser`, `page`, `base_url`, `logged_in_page` |
| `test_e2e_001_first_setup.py` | First-time setup flow | HIGH | Order-sensitive: requires empty DB |
| `test_e2e_002_login_happy.py` | Login happy path + KPI visible | HIGH | |
| `test_e2e_003_login_wrong_password.py` | Wrong password â†’ inline error | HIGH | |
| `test_e2e_004_rate_limit.py` | 5+ failed attempts â†’ 429 lockout | HIGH | GAP-003 |
| `test_e2e_005_dashboard_kpis.py` | 5 top KPI widgets visible | HIGH | GAP-001 |
| `test_e2e_006_logout.py` | Logout â†’ login redirect + cookie cleared | HIGH | GAP-012 |
| `test_e2e_007_change_password_invalidates.py` | Change pw â†’ old session 401 | CRITICAL | MEDIUM-001 regression |
| `test_e2e_008_api_keys_ui.py` | API keys panel: update + masked display | MEDIUM | GAP-006 |
| `test_e2e_009_rbac_viewer.py` | Viewer/operator â†’ 403 on owner endpoints | HIGH | GAP-010 |
| `test_e2e_010_human_gate.py` | Human gate approve flow | HIGH | GAP-009 |
| `test_e2e_011_session_expiry.py` | Expired session â†’ 401 â†’ login screen | MEDIUM | |
| `test_e2e_012_setup_idempotent.py` | Re-setup attempt â†’ 400 | MEDIUM | |

---

## Test execution order

For a fresh-DB run, execute in order:

```
001 â†’ 002 â†’ 003 â†’ 004 â†’ 005 â†’ 006 â†’ 007 â†’ 008 â†’ 009 â†’ 010 â†’ 011 â†’ 012
```

Tests 002â€“012 skip automatically if setup is not complete (`needs_setup=true`).
Test 001 skips if setup is already done.

Use `pytest-ordering` for explicit ordering:

```bash
pip install pytest-ordering
pytest tests_e2e/ -v -p no:randomly
```

---

## MEDIUM-001 â€” Security regression note

`test_e2e_007_change_password_invalidates.py` documents a known security bug:

> **MEDIUM-001:** `PUT /api/users/{user_id}` does not invalidate existing sessions
> for the target user after a password change.

The test currently **asserts the bug** (session survives = `authenticated=True`).
Once the fix is applied (add `DELETE FROM sessions WHERE user_id=?` in `app.py`
before `commit()`), invert the assertion:

```python
# Before fix (current):
assert still_authenticated is True

# After fix:
assert still_authenticated is False
```

---

## CI integration (GitHub Actions example)

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r dashboard/requirements.txt pytest-playwright requests
      - run: playwright install --with-deps chromium
      - run: |
          rm -f ~/sylion/sylion.db
          python -m sylion.server --host 127.0.0.1 --http-port 8421 &
          sleep 3
          pytest tests_e2e/ -v --timeout=60
```

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `connection refused` on port 8421 | App not started | `python -m sylion.server --host 127.0.0.1 --http-port 8421 &` |
| `test_e2e_001` skipped | DB already has admin | `rm -f ~/sylion/sylion.db` and restart |
| Tests 002â€“012 fail with login errors | Wrong `ADMIN_PASS` | Edit `ADMIN_PASS` constant at top of each file |
| Rate limit tests unstable | IP lock from prior run | Wait 10 min or restart app (clears in-memory counter) |
| DB manipulation tests skip | `sylion.db` not found | Confirm `DB_PATHS` in `test_e2e_011_session_expiry.py` |
| Human gate tests skip | No pending gates | Seed a gate via API or UI before running |
