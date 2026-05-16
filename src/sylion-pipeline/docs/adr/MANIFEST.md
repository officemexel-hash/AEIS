# ADR MANIFEST — SYLION Architecture Decision Records

**Projekt:** SYLION  
**Ostatnia aktualizacja:** 2026-04-19  
**Wersja:** 5.9.2  

Wszystkie decyzje architektoniczne projektu SYLION posortowane chronologicznie.  
Format Nygard (Kontekst / Decyzja / Status / Konsekwencje).

---

## ADR zatwierdzone (Accepted)

| Nr | Tytuł | Wersja | Status | Data |
|----|-------|--------|--------|------|
| [ADR-0001](ADR-0001-seed-agents-guard.md) | Zachowanie defense-in-depth guardu w `_seed_agents` | v5.8.8.1 | Accepted | 2026-04-18 |
| [ADR-0002](ADR-0002-doc-scope-mismatch.md) | Korekta zakresu dokumentacji v5.8.x | v5.8.8.1 | Accepted | 2026-04-18 |
| [ADR-0003](ADR-0003-migration-framework.md) | Framework migracji schematu SQLite (PRAGMA user_version) | v5.8.8.1 | Accepted | 2026-04-18 |
| [ADR-0004](ADR-0004-rate-limiting.md) | Rate limiting dla endpointów auth (login/setup) | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0005](ADR-0005-password-hashing.md) | bcrypt jako jedyny algorytm haszowania haseł | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0006](ADR-0006-backup-non-fatal.md) | Backup non-fatal na read-only filesystemie | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0007](ADR-0007-batch-imports.md) | Batch import przez subprocess (13 forków → 1) | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0008](ADR-0008-dashboard-query-consolidation.md) | Konsolidacja zapytań dashboard (15 → 5) | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0009](ADR-0009-secure-cookie-default.md) | Secure cookie jako domyślny standard (HttpOnly + SameSite) | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0010](ADR-0010-session-invalidation-on-password-change.md) | Unieważnienie sesji przy zmianie hasła | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0011](ADR-0011-pragma-cached-once-per-process.md) | PRAGMA cached raz na proces | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0012](ADR-0012-assert-replaced-with-valueerror.md) | Zastąpienie `assert` przez `ValueError`/`RuntimeError` | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0013](ADR-0013-setup-token-persistence.md) | Persystencja tokenu setup przez restart | v5.9.0 | Accepted | 2026-04-18 |
| [ADR-0014](ADR-0014-setup-lock-toctou-fix.md) | Fix TOCTOU w setup lock | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0015](ADR-0015-pixel-9-default-device.md) | Pixel 9 jako domyślne urządzenie w module device/ | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0016](ADR-0016-cve-dependency-upgrades.md) | Upgrade zależności — CVE patch (cryptography, Pillow, certifi) | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0017](ADR-0017-rollback-sh-rewrite.md) | Przepisanie rollback.sh z atomową zamianą backupu | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0018](ADR-0018-fact-checker-model-id.md) | Fact-checker model ID — pin do stabilnej wersji | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0019](ADR-0019-install-script-fix.md) | Naprawa install.sh (missing requirements.txt, path fix) | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0020](ADR-0020-pydantic-migration.md) | Migracja walidacji danych do Pydantic v2 | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0021](ADR-0021-rodo-retention.md) | Polityka retencji danych osobowych (RODO Art. 5(1)(e)) | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0022](ADR-0022-pip-compile.md) | Lockfile zarządzany przez pip-compile (requirements-lock.txt) | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0023](ADR-0023-agent-id-reset.md) | Reset numeracji agent_id po migracji schematu | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0024](ADR-0024-sql-ollama-whitelist.md) | Whitelist zapytań SQL i modeli Ollama | v5.9.0 | Accepted | 2026-04-19 |
| [ADR-0025](ADR-0025-v591-final-verification-loop.md) | Końcowa pętla weryfikacyjna v5.9.1 | v5.9.1 | Accepted | 2026-04-19 |

---

## ADR proponowane (Proposed) — v5.9.2

| Nr | Tytuł | Wersja | Status | Data | Źródło mega_audit |
|----|-------|--------|--------|------|-------------------|
| [ADR-0026](ADR-0026-csrf-full-coverage.md) | CSRF pełne pokrycie wszystkich mutujących endpointów | v5.9.2 | PROPOSED | 2026-04-20 | csrf_71_endpoints |
| [ADR-0027](ADR-0027-wireguard-vpn-kill-switch-mudi.md) | WireGuard VPN z kill switch i DNS tunnel na Mudi | v5.9.2 | PROPOSED | 2026-04-20 | wireguard_impl |
| [ADR-0028](ADR-0028-run-codebase-audit-orchestrator.md) | run_codebase_audit() w orchestrator + POST /api/pipeline/run | v5.9.2 | PROPOSED | 2026-04-20 | upload_deep |
| [ADR-0029](ADR-0029-diagnostics-v2-syl-codes.md) | Diagnostyka v2 z 82 kodami SYL-* | v5.9.2 | PROPOSED | 2026-04-20 | diagnostyka_deep |
| [ADR-0030](ADR-0030-pixel9-detection-root-causes.md) | Pixel 9 detection root causes fix | v5.9.2 | PROPOSED | 2026-04-20 | pixel_deep |
| [ADR-0031](ADR-0031-db-init-race-condition-fresh-install.md) | DB init race condition fix dla fresh installs | v5.9.2 | PROPOSED | 2026-04-20 | db_init_bug |
| [ADR-0032](ADR-0032-rollback-wal-integrity-pidfile-guard.md) | Rollback.sh WAL integrity + pidfile guard merge | v5.9.2 | PROPOSED | 2026-04-20 | rollback_wal_integrity |
| [ADR-0033](ADR-0033-run-migrations-v3-to-v4.md) | run_migrations_v3_to_v4 (csrf_tokens + health_history) | v5.9.2 | PROPOSED | 2026-04-20 | migrations_deep |
| [ADR-0034](ADR-0034-ksef-e-rechnung.md) | KSeF 2.0 / JPK_V7M(3) / GoBD / E-Rechnung — Compliance Architecture | v5.9.2 / v5.10 | PROPOSED | 2026-04-20 | compliance_deep |

---

## Meta-ADR — Release (Accepted)

| Nr | Tytuł | Wersja | Status | Data |
|----|-------|--------|--------|------|
| [ADR-0035](ADR-0035-release-v5.9.2.md) | Release v5.9.2 — Stabilizacja i hardening (meta-ADR) | v5.9.2 | ACCEPTED | 2026-04-19 |

---

## Statystyki

| Kategoria | Liczba |
|-----------|--------|
| Accepted | 26 |
| PROPOSED | 9 |
| Deprecated | 0 |
| **Łącznie** | **35** |

## Domeny

- **Security**: ADR-0004, 0005, 0009, 0012, 0013, 0014, 0016, 0024, 0026
- **Database / Migrations**: ADR-0003, 0011, 0023, 0031, 0033
- **RODO / Compliance**: ADR-0021, 0034
- **DevOps / Infrastructure**: ADR-0006, 0007, 0017, 0019, 0022, 0027, 0032
- **Pipeline / Orchestration**: ADR-0028
- **Devices**: ADR-0015, 0030
- **Observability / Diagnostics**: ADR-0029
- **API / Quality**: ADR-0008, 0018, 0020, 0025
- **Release / Meta**: ADR-0035
- **E-Invoicing / Compliance**: ADR-0034

---

*Nowe ADR proponowane przez mega_audit v5.9.2 wymagają zatwierdzenia przez SYLION AI Council.*  
*Ścieżka plików ADR: `docs/adr/ADR-XXXX-*.md`*
