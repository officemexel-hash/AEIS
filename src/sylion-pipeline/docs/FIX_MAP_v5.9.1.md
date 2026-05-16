# FIX MAP v5.9.1 — Traceability Matrix

**Generated:** 2026-04-19  
**Source:** [FINDINGS_MATRIX_v591.md](../../council/v590_reaudit/consolidated/FINDINGS_MATRIX_v591.md)  
**Method:** 32 sub-agents × 5 audit waves = 160+ council reports (4 AI models)

---

## Summary

- Findings audited: **54**
- Fixes applied: **48**
- Fixes deferred: **6** (with justification — see Deferred section)

---

## Legend

- 🔴 CRITICAL  🟠 HIGH  🟡 MEDIUM  🟢 LOW  ⚪ INFO/DEAD

---

## Fixes

| Fix ID | Sev | Finding ID | File:Line | Finding Description | Fix Description | ADR | Test | Audit Report |
|--------|-----|------------|-----------|---------------------|-----------------|-----|------|--------------|
| FIX-v591-01 | 🔴 | P0-1 SEC-001 | `dashboard/db.py:1082-1085` | 4 live API keys hardcoded (OpenAI, Anthropic, Perplexity, Google) in source and released zip | Zero out `_DEFAULT_API_KEYS` to `""`; rotate all 4 keys; rebuild zip without secrets | — | test_no_hardcoded_api_keys | sec_keys/REPORT.md |
| FIX-v591-02 | 🔴 | P0-2 FIND-1 | `fact_checker.py:159,172` + `config.py:130,161` | Default model `claude-sonnet-4-5-20250929` does not exist — Layer 5 anti-hallucination throws `InvalidRequestError` at runtime | Change model ID to `anthropic/claude-sonnet-4-6`; add env override `FACT_CHECKER_MODEL_ID` | — | test_fact_checker_model_valid | fact_checker/REPORT.md |
| FIX-v591-03 | 🔴 | P0-3 F-01 | `install.sh:130-132`, `install.bat:139-145` | Step 4 calls `python -m app.db.init_db` — package `app/` does not exist; clean-slate install aborts | Patch to `PYTHONPATH="dashboard" python -c "import db; db.init_db()"` | — | test_install_sh_step4 | install_sh/REPORT.md |
| FIX-v591-04 | 🔴 | P0-4 F-02 | README, RUNBOOK, install.sh, FAQ | Python version inconsistency: 3.10 / 3.11 / 3.12 across docs | Normalize all references to `>=3.11` (tested on 3.12) | — | test_docs_python_version_consistent | full_install_e2e/REPORT.md |
| FIX-v591-05 | 🔴 | P0-5 CRIT-01 | `dashboard/db.py get_conn()` | 2× PRAGMA per connection = 0.667 ms overhead × 137 calls ≈ 91 ms per request | Execute PRAGMA once per process with cached flag; skip on subsequent connections | ADR-0011 (pragma-cached-once-per-process) | test_pragma_runs_once_per_process | performance/REPORT.md |
| FIX-v591-06 | 🟠 | P1-1 REG-1 | `app.py:5787-5791, 5910-5914` | FIX-10 uses `assert all(...)` — bypassed via `python3 -O` (PYTHONOPTIMIZE=1) | Replace both `assert` blocks with `if not …: raise ValueError(…)` | ADR-0012 (assert-replaced-with-valueerror) | test_fix10_valueerror_not_assert | fix10_assert/REPORT.md |
| FIX-v591-07 | 🟠 | P1-2 BUG-001 | `app.py:780-870` `get_dashboard` | 7 COUNT queries in `get_dashboard`; test `test_api_dashboard_query_count_reduced` expects <6 → FAIL when fixture repaired | Consolidate into UNION ALL with `'__total__'` sentinel; reduce to single query | ADR-0008 (dashboard-query-consolidation) | test_dashboard_query_count_lt_6 | bug001/REPORT.md |
| FIX-v591-08 | 🟠 | P1-3 MEDIUM-001 | `app.py:708-741` `PUT /api/users/{id}` | Password change does not invalidate existing sessions — pass-the-cookie attack window up to 24 h | `DELETE FROM sessions WHERE user_id=?` on password update; add `POST /api/auth/logout-all` endpoint | ADR-0010 (session-invalidation-on-password-change) | test_session_invalidated_on_password_change | session_invalidation/REPORT.md |
| FIX-v591-09 | 🟠 | P1-4 C-01 | `app.py /api/auth/setup` | TOCTOU race — 5 concurrent requests create 5 admin accounts from 1 setup_token | Add `threading.Lock` + `BEGIN IMMEDIATE` before SELECT/DELETE | — | test_setup_toctou_race | concurrency/REPORT.md |
| FIX-v591-10 | 🟠 | P1-5 SEC-PII-1 | 6 doc files (README, FAQ, TROUBLESHOOTING PL+DE, ONBOARDING PL+DE) | Real email `robert.skorupka@icloud.com` in released zip | Replace all occurrences with `support@sylion.example` | — | test_no_pii_email_in_docs | secrets_pii/REPORT.md |
| FIX-v591-11 | 🟠 | P1-6 CVE-1 | `requirements-lock.txt` litellm 1.67.4.post1 | CVE-2026-35030 CRITICAL 9.4 — auth bypass via OIDC JWT cache | Upgrade litellm to `>=1.83.0` | — | test_deps_litellm_version | cve/REPORT.md |
| FIX-v591-12 | 🟠 | P1-7 CVE-2 | `requirements-lock.txt` starlette 0.46.2 | CVE-2025-62727 HIGH — quadratic DoS via Range header | Upgrade starlette to `>=0.49.1`; bump fastapi to `>=0.136` | — | test_deps_starlette_version | cve/REPORT.md |
| FIX-v591-13 | 🟠 | P1-8 CVE-3 | `requirements-lock.txt` python-multipart 0.0.20 | CVE-2026-24486 HIGH 7.5 — path traversal on file upload | Upgrade python-multipart to `>=0.0.26` | — | test_deps_multipart_version | cve/REPORT.md |
| FIX-v591-14 | 🟠 | P1-9 CVE-4 | `requirements-lock.txt` pypdf 5.4.0 | 22 CVE/GHSA DoS vulnerabilities | Upgrade pypdf to `>=6.10.2` | — | test_deps_pypdf_version | cve/REPORT.md |
| FIX-v591-15 | 🟠 | P1-10 PIX-1 | `dashboard/db.py:1349` + `pixel_provision.py:46` | DB seed hardcodes `"pixel8"`; `EXPECTED_MODEL="Pixel 9"` never enforced — main historical regression | Change seed to `"pixel9"`; add model validation; handle `"unauthorized"` device state | — | test_pixel9_seed_and_validation | pixel_detection/REPORT.md |
| FIX-v591-16 | 🟠 | P1-11 ISSUE-RT-01 | `start.py` + `app.py lifespan` | `init_db()` called twice — prints 2 setup tokens; first token becomes stale | Single call with idempotency flag; suppress duplicate token output | — | test_init_db_called_once | runtime/REPORT.md |
| FIX-v591-17 | 🟡 | P2-1 CSRF-01 | `app.py:484-485, 639-640` | `Secure` cookie flag defaults `False`; TLS deploy sends session cookie in plaintext | Default `Secure=True` in production; allow env override `SESSION_COOKIE_SECURE=0` for local dev | ADR-0009 (secure-cookie-default) | test_session_cookie_secure_flag | csrf_cors/REPORT.md |
| FIX-v591-18 | 🟡 | P2-2 CSRF-03 | `app.py /api/baselines/upload` | Multipart upload endpoint has no CSRF token (protected only by SameSite=Strict) | Add X-CSRF-Token double-submit pattern to upload endpoint | — | test_upload_csrf_token_required | csrf_cors/REPORT.md |
| FIX-v591-19 | 🟡 | P2-3 CORS-02 | `app.py` CORS config | CORS origins list lacks HTTPS variants — TLS reverse-proxy deployment fails CORS checks | Auto-generate `https://` variants for each `http://` origin in `ALLOWED_ORIGINS` | — | test_cors_https_origins | csrf_cors/REPORT.md |
| FIX-v591-20 | 🟡 | P2-4 C-02 | `app.py login()` | Hash upgrade race: 10 concurrent logins → 10× Argon2 re-hash + 10 audit entries | Compare-and-swap in `UPDATE` (check affected rows before re-hashing) | — | test_hash_upgrade_no_race | concurrency/REPORT.md |
| FIX-v591-21 | 🟡 | P2-5 C-03 | `app.py audit_log()` | `conn.commit()` inside login transaction — crash leaves hash saved but session not created | Pass `autocommit=False` parameter; commit only after full login success | — | test_audit_log_atomic_commit | concurrency/REPORT.md |
| FIX-v591-22 | 🟡 | P2-6 RT-ERR-1 | `app.py:5401,5459,5562` | `traceback.format_exc()[-500:]` returned in provision endpoint responses | Log traceback locally only; return generic error message to client | — | test_no_traceback_in_response | error_handling/REPORT.md |
| FIX-v591-23 | 🟡 | P2-7 BKUP-1 | `db.py` backup naming | Backup filename contains `v5.9.0`; ROLLBACK_PLAN references `v5.8.9` — operator finds 0 files during rollback | Synchronize backup filename template with ROLLBACK_PLAN | — | test_backup_filename_matches_rollback | migrations/REPORT.md |
| FIX-v591-24 | 🟡 | P2-8 TOK-1 | `app.py` + `db.py` setup_token flow | `setup_token` regenerates on every restart before setup completes — any restart during onboarding breaks flow | Persist token until setup is completed or explicit expiry; do not regenerate if token already exists | ADR-0013 (setup-token-persistence) | test_setup_token_persists_across_restart | runtime/REPORT.md |
| FIX-v591-25 | 🟡 | P2-9 EP-1 | `app.py:5620` `/api/agents/prompts` | Route shadowed by `/api/agents/{agent_id}` catch-all → always 404 | Move `/api/agents/prompts` route registration before `/{agent_id}` | — | test_agents_prompts_route_not_shadowed | endpoint_matrix/REPORT.md |
| FIX-v591-26 | 🟡 | P2-10 EP-2 | `app.py:6409` `/api/agents/pipeline-graph` | Same route-conflict pattern as EP-1 → always 404 | Move `/api/agents/pipeline-graph` before `/{agent_id}` catch-all | — | test_pipeline_graph_route_not_shadowed | endpoint_matrix/REPORT.md |
| FIX-v591-27 | 🟡 | P2-11 EP-3 | `app.py /api/health/deep` | Hangs for 180 s (blocking subprocess, no async wrapper) | Wrap in `asyncio.create_subprocess_exec` with `asyncio.wait_for` timeout guard | — | test_health_deep_timeout | endpoint_matrix/REPORT.md |
| FIX-v591-28 | 🟡 | P2-12 EP-4 | `app.py DELETE /api/models/{id}` | Returns HTTP 200 for non-existent model ID (silent no-op) | Check `cursor.rowcount` after DELETE; return 404 if 0 rows affected | — | test_delete_model_404_on_missing | endpoint_matrix/REPORT.md |
| FIX-v591-29 | 🟡 | P2-13 FIX-02-SHAPE | `app.py /api/dashboard` | Missing top-level keys `costs`, `guards`, `security` vs v5.8.8 baseline JSON shape | Add `costs`, `guards`, `security` keys with empty/default values to dashboard response | — | test_dashboard_shape_baseline | fix02_deepdive/REPORT.md |
| FIX-v591-30 | 🟡 | P2-14 RODO-1 | Docs PL/DE | 2 HIGH + 5 MEDIUM RODO/KSeF compliance findings in audit; RoPA incomplete | Update RoPA sections; add user-facing retention policy; align PRIVACY_POLICY_PL/DE | — | test_rodo_compliance_docs_present | rodo/REPORT.md |
| FIX-v591-31 | 🟡 | P2-15 UI-FALSE-ENC | Dashboard HTML templates | UI claims "data encrypted in database" — keys are stored as plaintext SQLite | Correct UI text to accurately reflect plaintext storage or implement Fernet encryption | — | test_ui_encryption_claim_accurate | documents/REPORT.md |
| FIX-v591-32 | 🟡 | P2-16 DOC-LINK | FAQ, CHANGELOG | 8 dead links (`FIX_MAP.md`, `docs/advanced/` paths) | Fix all 8 broken paths to match actual file locations | — | test_doc_links_resolve | documents/REPORT.md |
| FIX-v591-33 | 🟡 | P2-17 MAN-PYTHON | QUICKSTART_PL, QUICKSTART_DE, FAQ | Commands `python -m sylion serve/migrate`, `pip install -r requirements.txt` do not exist | Replace with real executable commands per install guide | — | test_quickstart_commands_valid | manual/REPORT.md |
| FIX-v591-34 | 🟡 | P2-18 MAN-URL | QUICKSTART_PL, QUICKSTART_DE | Placeholder `git clone https://github.com/your-org/sylion.git` | Remove placeholder or replace with real repository URL | — | test_no_placeholder_git_url | manual/REPORT.md |
| FIX-v591-35 | 🟢 | P3-1 BUG-002 | `app.py prune_sessions()` | `cutoff` uses `-30d` bug (sign error) — not exploitable but logically wrong | Correct cutoff calculation to use proper negative delta | — | test_prune_sessions_cutoff_correct | bug002/REPORT.md |
| FIX-v591-36 | 🟢 | P3-2 C-04 | `app.py _HASH_BACKEND` | `_HASH_BACKEND` set without lock (CPython GIL-safe but not formally thread-safe) | Add double-check locking around backend initialization | — | test_hash_backend_thread_safe | concurrency/REPORT.md |
| FIX-v591-37 | 🟢 | P3-3 DC-1..18 | Multiple files | 18 unused imports (ruff F401) | Run `ruff --fix` to remove all unused imports | — | test_ruff_f401_clean | dead_code/REPORT.md |
| FIX-v591-38 | 🟢 | P3-4 DC-19..32 | Multiple files | 14 unused variables (F841) — `user = require_role(...)` pattern throughout | Replace with explicit `_ = require_role(...)` | — | test_ruff_f841_clean | dead_code/REPORT.md |
| FIX-v591-39 | 🟢 | P3-5 DC-33 | `dashboard/db.py` | Duplicate import `Optional as Opt` | Remove duplicate import | — | test_no_duplicate_optional_import | dead_code/REPORT.md |
| FIX-v591-40 | 🟢 | P3-6 DC-34 | repo root | Missing `.gitignore`; `__pycache__/` committed to repo | Add `.gitignore` covering `__pycache__/`, `*.pyc`, `.env`, `*.db` | — | test_gitignore_exists | dead_code/REPORT.md |
| FIX-v591-41 | 🟢 | P3-7 ADR-002-NEG | `docs/adr/ADR-0002-doc-scope-mismatch.md` | ADR-002 missing Negative Consequences section | Add Negative Consequences section or renumber to clarify scope | — | test_adr_002_has_negative_section | adr/REPORT.md |
| FIX-v591-42 | 🟢 | P3-8 ADR-NUM | `docs/adr/` | 3-digit ADR numbering (ADR-001) inconsistent with 4-digit standard (ADR-0001) | Normalize all ADR filenames and references to 4-digit format | — | test_adr_numbering_consistent | adr/REPORT.md |
| FIX-v591-43 | 🟢 | P3-9 CHG-RLN | `docs/CHANGELOG_v5.9.0.md`, RELEASE_NOTES | 0 of 11 fixes overlap between CHANGELOG and RELEASE_NOTES | Align CHANGELOG and RELEASE_NOTES so all shipped fixes appear in both | — | test_changelog_release_notes_aligned | adr/REPORT.md |
| FIX-v591-44 | 🟢 | P3-10 BACK-LIC | repo root | Missing `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES` files | Apply drafts from `legal/` directory to repo root | — | test_license_files_present | legal/REPORT.md |
| FIX-v591-45 | 🟢 | P3-11 PHANTOM-LOG | `file_verification.py:336,344` | `log.warning(...)` instead of `logger.warning(...)` → `NameError` at runtime in hallucination guard | Replace `log.warning` with `logger.warning` (2-line fix) | — | test_file_verification_no_nameerror | books_phantom/REPORT.md |
| FIX-v591-46 | 🟢 | P3-12 WS-DEPR | `app.py`, `start.py` | `asyncio.get_event_loop()` emits DeprecationWarning on Python 3.12 | Replace with `asyncio.get_running_loop()` | — | test_no_get_event_loop_deprecation | runtime/REPORT.md |
| FIX-v591-47 | 🟢 | P3-13 ZIP-STRUC | Release zip | Missing `MANIFEST.json` in zip root; not single-directory structure | Add `MANIFEST.json` with version/hash metadata; enforce single top-level dir in zip | — | test_zip_has_manifest | zip_integrity/REPORT.md |
| FIX-v591-48 | 🟢 | P3-14 MAN-DE-MISS | `docs/` | Missing `ONBOARDING_CHECKLIST_DE.md` | Generate German onboarding checklist parallel to PL version | — | test_onboarding_checklist_de_exists | manual/REPORT.md |

---

## Deferred

| Defer ID | Finding ID | Sev | Reason | Target |
|----------|------------|-----|--------|--------|
| DEFER-01 | INFO-1 BUG-003 | ⚪ | FIX-05 guard placement is dead code but harmless; cleanup optional, not blocking | v5.9.2 optional cleanup |
| DEFER-02 | INFO-2 Book | ⚪ | `BookGuardian` documentation gap — informational, not a code defect | v5.9.2 docs |
| DEFER-03 | INFO-3 WebRTC | ⚪ | RTP/SRTP media plane absent — signaling OK, media is future work; not a regression | v5.10 |
| DEFER-04 | INFO-4 Mudi-WG | ⚪ | WireGuard + kill-switch not implemented; user decision: local offline pipeline, not in scope | v5.10 |
| DEFER-05 | INFO-5 Code-Upload | ⚪ | Upload does not trigger auto-pipeline — feature gap, not a bug | v5.10 |
| DEFER-06 | INFO-6 FIX-verify | ⚪ | FIX-01, 03, 04, 06, 07, 08, 09, 11 from v5.9.0 verified OK — no action required | — |

---

## Coverage by Cluster

| Cluster | Fixes | Description |
|---------|-------|-------------|
| A — dashboard/db.py | FIX-v591-05, 15, 23, 24, 39 | PRAGMA caching, Pixel 9 seed, backup naming, setup_token, duplicate import |
| B — dashboard/app.py | FIX-v591-06, 07, 08, 09, 16, 17, 18, 19, 20, 21, 22, 25, 26, 27, 28, 29, 35, 36, 37, 38, 46 | Security, concurrency, routing, error handling, dead code |
| C — standalone files | FIX-v591-02, 03, 04, 10, 15 (pixel_provision.py), 45, 46, 40 | fact_checker, install scripts, docs, file_verification, .gitignore |
| D — dependencies | FIX-v591-11, 12, 13, 14 | 4 CVE package upgrades |
| E — docs/legal | FIX-v591-10, 30, 31, 32, 33, 34, 41, 42, 43, 44, 48 | PII removal, RODO, UI text, broken links, ADR gaps, license files |
| F — operational | FIX-v591-16 (start.py), 23 (rollback sync) | init_db idempotency, SRE fixes |
| G — tests | FIX-v591-06 test, 07 test, 08 test, 15 test | Regression test suite additions |
| H — release/zip | FIX-v591-01, 47 | API key removal, MANIFEST.json |

---

## Cross-references

- [CHANGELOG_v5.9.1.md](./CHANGELOG_v5.9.1.md)
- [CHANGELOG_v5.9.0.md](./CHANGELOG_v5.9.0.md)
- [REAUDIT_v590_REPORT_PL.md](./REAUDIT_v590_REPORT_PL.md) *(SECURITY_REAUDIT_v5.9.0.md)*
- [REAUDIT_v590_REPORT_DE.md](./REAUDIT_v590_REPORT_DE.md)
- [FIX_MAP_v5.9.0.md](./FIX_MAP_v5.9.0.md)
- [RODO_COMPLIANCE.md](./RODO_COMPLIANCE.md)
- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)
- [adr/](./adr/)
- [Source findings: FINDINGS_MATRIX_v591.md](../../council/v590_reaudit/consolidated/FINDINGS_MATRIX_v591.md)
- [Fix plan: FIX_PLAN_v591.md](../../council/v590_reaudit/consolidated/FIX_PLAN_v591.md)
