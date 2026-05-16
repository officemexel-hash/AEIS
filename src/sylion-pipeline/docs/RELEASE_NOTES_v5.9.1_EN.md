# SYLION v5.9.1 — Hardening Patch (Release Notes, EN)

**Release date:** 2026-04-19
**Codename:** *Hardening Patch*
**Release type:** PATCH (SemVer 5.9.0 → 5.9.1)
**Previous release:** v5.9.0 (*Breakthrough — 18 Skills Audit*, 2026-04-18)
**Nature:** bugfix + security hardening only. **No API changes. No breaking changes.**

## TL;DR

Post-audit patch. 4-model council (Opus 4.7 / Sonnet 4.6 / GPT-5.4 / Gemini 3.1 Pro) plus
14 domain skills produced 18 reports identifying 33 findings in v5.9.0. This release closes
**13 of them**, including all BLOCKER findings except one deliberately deferred (F-001).

---

## Security fixes

| ID    | Severity | Summary                                                                      |
|-------|:--------:|------------------------------------------------------------------------------|
| F-002 | HIGH     | Rate limiter bypassed behind reverse-proxy — uvicorn now uses `--proxy-headers`. New Caddyfile example in `RUNBOOK_DEPLOY.md §3.5`. |
| F-010 | HIGH     | Silent fallback from Argon2id to SHA-256 — now raises `RuntimeError`. `argon2-cffi>=23.1.0` is now a hard requirement. |
| F-015 | MEDIUM   | `SESSION_COOKIE_SECURE` default changed from `"0"` to `"1"`.                 |
| F-009 | MEDIUM   | Replaced `assert column in ALLOWED_COLUMNS` with `raise ValueError` (safe under `python -O`). |
| F-019 | MEDIUM   | Added `idx_sessions_expires_at` via migration v1→v2 (automatic, PRAGMA user_version). |
| F-026 | LOW      | `except Exception: pass` narrowed to `except (sqlite3.Error, OSError)` + logging. |

---

## Operational fixes (SRE / Deploy)

| ID    | Severity | Summary                                                                      |
|-------|:--------:|------------------------------------------------------------------------------|
| F-004, F-005, F-006 | HIGH | Complete rewrite of `rollback.sh` (261 → 327 lines). Staged restore with `PRAGMA integrity_check` **before** overwriting production DB. WAL/SHM aware. Searches `$HOME/sylion/backups/`, `./backups/`, `/var/backups/sylion/`. New `--dry-run` mode. |
| F-007 | MEDIUM | Fixed 9 entry-point references: `app.main:app` → `dashboard.app:app` in `RUNBOOK_DEPLOY.md`. |
| F-008 | MEDIUM | `INCIDENT_RESPONSE.md` rewritten for Caddy (was nginx). Port 8000 → 8421. `/health` → `/api/health`. |
| F-016, F-023 | LOW | Python version unified across all docs — 3.12 is now the minimum **required** version. |

---

## Documentation fixes

| ID    | Summary                                                                              |
|-------|--------------------------------------------------------------------------------------|
| F-003 | Previous "hallucinated" Release Notes v5.9.0 superseded by this document and `RELEASE_NOTES_v5.9.0_CORRECTED_EN.md`. |
| F-017 | `QUICKSTART_PL/DE.md` now warn about `your-org/sylion.git` placeholder + `SYLION_REPO_URL` env var. |
| F-018 | Typo fix in `FAQ_DE.md`: "Datenbanksperfehler" → "Datenbanksperrfehler".             |
| F-025 | Test filenames in `CHANGELOG_v5.9.0.md` corrected to match actual files.             |
| F-022 | Removed `.github/workflows/validate-manifest.yml` (violated user constraint C-103 — no CI/CD in repo). |

---

## CVE patches in dependencies

| Package            | v5.9.0   | v5.9.1   | Rationale                                           |
|--------------------|---------:|---------:|-----------------------------------------------------|
| `starlette`        | `0.46.2` | `0.47.2` | Path traversal patch in `StaticFiles`               |
| `python-multipart` | `0.0.20` | `0.0.21` | DoS via malformed multipart boundary                |
| `pypdf`            | `5.4.0`  | `5.5.0`  | Infinite loop fix in `EncodedStreamObject`          |

All three are patch-level upgrades — zero API changes. Lockfile hashes regenerated.

---

## NOT fixed (deliberate deferrals)

### F-001 — Hardcoded API keys in `dashboard/db.py:1081-1086` (CRITICAL)

**Status:** Operator decision (HumanGate 2026-04-19): keys have not yet been rotated,
deferred to v5.9.2.

**MANDATORY before deployment:** Rotate all 4 API keys (OpenAI, Anthropic, Perplexity, Google)
at their respective provider dashboards, then configure them via `.env` only. Verify that
no literals remain in `dashboard/db.py:1081-1086`.

---

## Upgrade from v5.9.0

```bash
# 1. Backup DB
sqlite3 ~/sylion/sylion.db ".backup '~/sylion/backups/sylion-pre-v591-$(date +%Y%m%d-%H%M%S).db.bak'"

# 2. Stop service
sudo systemctl stop sylion

# 3. Unpack package
cd /opt/sylion
unzip /path/to/SYLION_v591.zip -d /tmp/sylion-v591
rsync -a --delete /tmp/sylion-v591/sylion-pipeline/ /opt/sylion/sylion-pipeline/

# 4. Update dependencies (argon2-cffi is NOW mandatory)
source .venv/bin/activate
pip install -r requirements-lock.txt --upgrade

# 5. ROTATE API KEYS (F-001) — critical, do this NOW

# 6. Update Caddyfile (template in RUNBOOK_DEPLOY.md §3.5.2)
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 7. Start service
sudo systemctl start sylion

# 8. Verify rate limiter: 6 login attempts, expect 5× 401 + 1× 429
```

### Rollback

```bash
sudo systemctl stop sylion
./rollback.sh --dry-run     # preview
./rollback.sh               # execute
sudo systemctl start sylion
```

`rollback.sh` will restore the most recent valid backup with `PRAGMA integrity_check`
verification **before** swapping the database file.

---

## Compliance

- **GDPR:** No changes to personal data processing.
- **KSeF / JPK (PL):** No changes to invoice modules.
- **HGB / GoBD (DE):** No changes to audit_log retention (10 years).
- **Cross-border PL↔DE:** No changes to SCCs / transfer pricing.

Full audit trail: `docs/council-reports/FIX_MAP_v5.9.1.md`.

---

## Audit reports (18 skills, in `docs/council-reports/`)

**4-model council:** OPUS_kodreviewer, SONNET_cvewatcher, GPT_opsauditor, GEMINI_qasentinel.
**Wave 2 (6 skills):** SECURITY_PENTEST, RODO_COMPLIANCE, PERFORMANCE, MIGRATION, PR_REVIEW, DOCS_CONSISTENCY.
**Wave 3 (8 skills):** FINOPS, DEPLOY_PLAN, SRE_RUNBOOKS, E2E_TESTING, KOD_AUDIT, SZACHISTA_CONSTRAINTS, TESTGEN_COVERAGE, USERMANUAL_REVIEW, LOOP_MONITOR.
**Consolidated:** FIX_MAP_v5.9.1.md — 33 findings → 13 resolved in this release.

---

## Contact

Issues / bugs: `${SYLION_ONCALL_CONTACT}`
Key rotation (F-001): must be completed before deploy. See `docs/ROLLBACK_PLAN.md` if in doubt.
