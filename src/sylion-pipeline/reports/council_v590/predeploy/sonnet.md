# CVE-Watcher (Sonnet) — Pre-Deploy Report v5.9.0

**Rola:** CVE analyst, bezpieczeństwo zależności, secrets scan  
**Data:** 2026-04-18  
**Scope:** SYLION v5.9.0 — requirements-lock.txt, dashboard/, diff patches

---

## Podsumowanie

Przeprowadzono skan CVE, bandit, secrets diff oraz analizę nowych zależności w v5.9.0. Zidentyfikowano **0 nowych krytycznych CVE** w diff (znane CVE z v5.8.8 pozostają), **1 warning** dotyczący nowych tabel/historii upload, i potwierdzam znane accepted-risk CVE z v5.8.8.

**Werdykt CVE-Watcher: GO-WITH-WARNINGS** (CVE scope niezmieniony, brak nowych sekretów w diff)

---

## Checkpoint 4 — ENV secrets diff

**STATUS: PASS ✓ (no new credentials)**

Analiza diff-db.patch, diff-app.patch, diff-start.patch pod kątem nowych hardcoded credentials:

```
grep "^\+" diff-*.patch | grep -E "(api_key|sk-|pplx-|AQ\.|password)" 
→ Wynik: tylko 2 referencje do DELETE FROM sessions (prawidłowe SQL queries)
```

**Nowe credentials w diff v5.9.0: BRAK**

Istniejące `_DEFAULT_API_KEYS` w db.py (OPENAI, ANTHROPIC, PERPLEXITY, GOOGLE) są **identyczne** z v5.8.8.1 — nie stanowią nowego ryzyka w kontekście tego release'u.

Nota: klucze API w `_DEFAULT_API_KEYS` są potencjalnie kompromitowane (ekspozycja przez wielokrotne analizy). Rekomendacja: rotacja przed produkcją.

---

## Checkpoint 11 — CVE Scan

**STATUS: WARNING ⚠️ (znane, accepted risk)**

### Bandit scan — wyniki

Uruchomiono: `/tmp/sylion_venv/bin/bandit -r dashboard -ll`

```
Run metrics:
  Total lines of code: 8895
  Total issues (by severity):
    Low:    29
    Medium: 17  
    High:    0
```

**High severity: 0** — brak krytycznych findings.

**Medium severity (17):**
- B608 `hardcoded_sql_expressions` — 6 wystąpień w app.py (linie 664, 997, 1397, 1440, 1884, +inne). Wszystkie to **FALSE POSITIVES** — wzorzec `', '.join(updates)` gdzie `updates` jest listą hardcoded string literałów (`"display_name=?"`, `"content=?"` etc.), wartości przez `?` binding. Zidentyfikowane i opisane w v5.8.8 security triage.
- B108 `hardcoded_tmp_directory` — db.py linia 1302: `"/tmp/sylion/"` w seed danych dla urządzenia GL.iNet. To statyczne dane seed (router device entry), nie runtime path — false positive.

**Nowe B608 w v5.9.0:**
Diff-app.patch nie wprowadza nowych dynamicznych `f"UPDATE {table}..."` form. Istniejące wzorce są niezmienione.

### CVE Status zależności

Poniższa analiza bazuje na `requirements-lock.txt` + poprzedni `pip-audit` z v5.8.8.1:

| Pakiet | Wersja | CVE | Status v5.9.0 |
|--------|--------|-----|---------------|
| litellm | 1.67.4.post1 | CVE-2026-35029, 35030 | **Accepted** — SYLION używa tylko `litellm.completion()` bibliotecznie, nie proxy |
| starlette | 0.46.2 | CVE-2025-54121, 62727 | **Accepted** — lokalny bind 127.0.0.1 |
| pypdf | 5.4.0 | 22× CVE (DoS via malicious PDF) | **Accepted** — user uploaduje własne PDFy |
| python-multipart | 0.0.20 | CVE-2026-24486, 40347 | **Accepted** — lokalny upload single-user |
| pytest | 8.3.4 | CVE-2025-71176 | **N/A** — dev only dependency |

**Zmiana w v5.9.0 vs v5.8.8.1:** `requirements-lock.txt` jest **identyczny** — brak bumpu żadnego pakietu. Zatem zbiór CVE pozostaje bez zmian: ~38 accepted-risk CVE, 0 nowych.

**Rekomendacja (nie blocker):** Rozważyć bumpy przed kolejnym release:
- `python-multipart` 0.0.20 → 0.0.26 (2 CVE, safe bump bez breaking changes)
- `pytest` 8.3.4 → 9.0.3 (1 CVE, dev-only, safe)

### Nowe zależności w v5.9.0

Diff-db.patch dodaje `import datetime` i `from pydantic import BaseModel, field_validator, ValidationError` (conditional import). Pydantic już w lockfile (`pydantic==2.11.1`), nie nowa zależność. Brak nowych pakietów niezarejestrowanych w lockfile.

---

## Analiza nowych tabel (bezpieczeństwo)

W `init_db()` v5.9.0 dodano dwie nowe tabele:

### `upload_history` (v5.9)
```sql
CREATE TABLE IF NOT EXISTS upload_history (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    uploaded_by TEXT NOT NULL DEFAULT 'system',
    ...
)
```
**Ocena:** Tabela przechowuje historię uploadów z SHA256 i `uploaded_by`. Brak PII/danych wrażliwych w schemacie (poza `uploaded_by` username). RODO compliance: retencja nie jest skonfigurowana dla tej tabeli — patrz checkpoint 15.

### `code_versions` (v5.9)
```sql
CREATE TABLE IF NOT EXISTS code_versions (
    version_tag TEXT NOT NULL,
    sha256_manifest TEXT NOT NULL DEFAULT '',
    ...
)
```
**Ocena:** Metadane wersji. Niska wrażliwość.

---

## Checkpoint 12 — Rollback Plan

**STATUS: MISSING ❌**

`docs/ROLLBACK_PLAN.md` — **plik nie istnieje** w repozytorium v5.9.0.

```
find /home/user/workspace/ -name "ROLLBACK_PLAN.md" → brak wyników
```

Dostępny jest `ROLLBACK.md` w starszych release'ach (v5.8.8_release, v5.8.8_unzipped), ale nie jest to plan data-migration-council dla v5.9.0.

**Wymagane:** Plik `docs/ROLLBACK_PLAN.md` dokumentujący kroki rollback dla migracji v5.9.0, w tym:
- Przywrócenie backupu DB (co się dzieje gdy `_backup_db_before_migration` nie tworzy pliku?)
- Rollback PRAGMA user_version
- Procedura downgrade kodu z v5.9.0 → v5.8.8.1

---

## Podsumowanie CVE-Watcher (Sonnet)

| # | Checkpoint | Status |
|---|---|---|
| 4 | ENV secrets diff — no new creds | ✅ PASS |
| 11 | CVE scan (bandit + deps) | ⚠️ WARN (known, accepted) |
| 12 | Rollback Plan | ❌ MISSING |

**Werdykt Sonnet: GO-WITH-WARNINGS** na sekcji CVE, ale **NO-GO** z powodu braku ROLLBACK_PLAN.md (checkpoint 12).
