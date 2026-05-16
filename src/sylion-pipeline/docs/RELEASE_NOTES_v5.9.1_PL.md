# SYLION v5.9.1 — Hardening Patch (Informacje o wydaniu, PL)

**Data wydania:** 2026-04-19
**Nazwa kodowa:** *Hardening Patch*
**Typ wydania:** PATCH (SemVer 5.9.0 → 5.9.1)
**Poprzednia wersja:** v5.9.0 (*Breakthrough — 18 Skills Audit*, 2026-04-18)
**Charakter wydania:** wyłącznie bugfix + wzmocnienie bezpieczeństwa.
**Brak zmian API. Brak breaking changes.**

Źródłowe Release Notes dla v5.9.1 zostały zarchiwizowane w snapshot_0052 i przeniesione
do LATEST docs zgodnie z luka nr 5 zidentyfikowaną w audit_LATEST/18_user_manual.md.

---

## Streszczenie

v5.9.1 to paczka naprawcza po audycie rady 4 modeli (Opus 4.7 / Sonnet 4.6 / GPT-5.4 /
Gemini 3.1 Pro) oraz 14 skilli domenowych (18 raportów łącznie). Znaleziono 33 findings
w v5.9.0 — v5.9.1 zamyka **13 z nich**, włącznie ze wszystkimi w stanie BLOCKER poza
jednym świadomie odroczonym (F-001).

**Jeśli jesteś na v5.9.0 — upgrade do v5.9.1 jest natychmiastowo zalecany.**

---

## Poprawki bezpieczeństwa

### F-002 (HIGH) — Rate limiter login ominięty za reverse-proxy

W v5.9.0 uvicorn startował bez `--proxy-headers`. Za Caddy rate limiter widział jako
źródło wszystkich żądań tylko `127.0.0.1`. Efekt: jeden zablokowany atakujący blokował
wszystkich legalnych użytkowników.

**Naprawa:** uvicorn zawsze startuje z `proxy_headers=True, forwarded_allow_ips="127.0.0.1"`.
Nowa zmienna `SYLION_FORWARDED_ALLOW_IPS` pozwala rozszerzyć listę zaufanych proxy.
Pełny przykładowy Caddyfile w `docs/RUNBOOK_DEPLOY.md §3.5`.

### F-010 (HIGH) — Cichy fallback Argon2id → SHA-256

Gdy `argon2-cffi` nie był zainstalowany, backend hashowania cicho przełączał się na
SHA-256. Operator nie wiedział o podatności.

**Naprawa:** `RuntimeError("Argon2id backend required")` — zero fallbacku.
`argon2-cffi>=23.1.0` jest teraz TWARDĄ zależnością.

### F-015 (MEDIUM) — `SESSION_COOKIE_SECURE` domyślnie wyłączone

Fail-open domyślnie — cookie sesyjne wysyłane przez HTTP. Wektor session hijackingu
w połączeniu z F-002.

**Naprawa:** Domyślna wartość `SESSION_COOKIE_SECURE = "1"`. Opt-out tylko przez
`SESSION_COOKIE_SECURE=0` (np. dla testów lokalnych).

### F-009 (MEDIUM) — `assert` w ścieżkach SQL Ollama

`assert column in ALLOWED_COLUMNS` był usuwany przez `python -O` → SQL injection możliwa.

**Naprawa:** Zastąpione przez `if column not in ALLOWED_COLUMNS: raise ValueError(...)`.

### F-019 (MEDIUM) — Brak indeksu `idx_sessions_expires_at`

Scheduled job `cleanup_expired_sessions()` robił pełny skan tabeli co 60 sekund.

**Naprawa:** Nowa migracja 1→2, indeks dodawany automatycznie przy starcie.
`_DB_TARGET_VERSION = 2`.

### F-026 (LOW) — Ciche połykanie wyjątków w `config.py`

4 bloki `except Exception: pass` ukrywały błędy inicjalizacji.

**Naprawa:** Zawężone do `except (sqlite3.Error, OSError)` + log ostrzeżenia.

---

## Poprawki operacyjne (SRE / Deploy)

### F-004, F-005, F-006 (HIGH) — Przepisanie rollback.sh

Stary skrypt: korupcja bazy przez WAL, zła ścieżka do backupów, brak weryfikacji.

**Naprawa (327 linii, poprzednio 261):**
- Staged restore — `PRAGMA integrity_check` PRZED podmianą produkcyjnej bazy.
- Obsługa plików WAL/SHM.
- Szuka backupów w: `$HOME/sylion/backups/`, `./backups/`, `/var/backups/sylion/`.
- Nowy tryb `--dry-run`.
- Kody wyjścia: 0=sukces, 1=brak backupu, 2=integrity failed, 3=brak uprawnień.

### F-007 (MEDIUM) — Błędny entry point w runbookach

9 wystąpień `app.main:app` → poprawione na `dashboard.app:app` w `RUNBOOK_DEPLOY.md`.

### F-008 (MEDIUM) — `INCIDENT_RESPONSE.md` używał nginx zamiast Caddy

Pełny rewrite sekcji „Reverse proxy" — diagnostyka Caddy, port 8421, `/api/health`.

### F-016, F-023 (LOW) — Niespójne wersje Pythona w dokumentacji

Python 3.12 jest teraz wymagany (nie 3.11+) we WSZYSTKICH dokumentach.

---

## Poprawki dokumentacji

| ID | Naprawa |
|----|---------|
| F-003 | Poprzednie „halucynowane" Release Notes v5.9.0 zastąpione wiarygodnym dokumentem. |
| F-017 | `QUICKSTART_PL/DE.md` jawnie ostrzega o placeholderze `your-org/sylion.git`. |
| F-018 | Literówka w `FAQ_DE.md`: „Datenbanksperfehler" → „Datenbanksperrfehler". |
| F-025 | Błędne nazwy testów w `CHANGELOG_v5.9.0.md` poprawione na istniejące pliki. |
| F-022 | Usunięto `.github/workflows/validate-manifest.yml` (naruszenie constraint C-103). |

---

## Aktualizacje zależności (CVE patch)

| Pakiet | v5.9.0 | v5.9.1 | Uzasadnienie |
|--------|--------|--------|--------------|
| `starlette` | `0.46.2` | `0.47.2` | Path traversal w `StaticFiles` |
| `python-multipart` | `0.0.20` | `0.0.21` | DoS przez malformed multipart boundary |
| `pypdf` | `5.4.0` | `5.5.0` | Infinite loop w `EncodedStreamObject` |

Lockfile `requirements-lock.txt` zaktualizowany, checksums odświeżone.

---

## Co NIE jest naprawione (świadome odroczenia)

### F-001 — Hardcoded API keys w `dashboard/db.py:1081-1086` (CRITICAL)

Klucze nie zostały jeszcze zrotowane — odroczenie do v5.9.2.

**OBOWIĄZEK OPERATORA PRZED DEPLOYEM:**
1. Zrotuj wszystkie 4 klucze (OpenAI, Anthropic, Perplexity, Google).
2. Skonfiguruj je WYŁĄCZNIE przez `.env`.
3. Zweryfikuj: `grep -n "sk-" dashboard/db.py` — wynik musi być pusty.

### F-011, F-013 (LOW)

Drobne niespójności w `DISASTER_RECOVERY.md` — odłożone do v5.9.2.

---

## Upgrade z v5.9.0

```bash
# 1. Backup bazy PRZED upgrade
sqlite3 ~/sylion/sylion.db \
  ".backup '~/sylion/backups/sylion-pre-v591-$(date +%Y%m%d-%H%M%S).db.bak'"

# 2. Stop serwisu
sudo systemctl stop sylion

# 3. Wgraj v5.9.1
rsync -a --delete /tmp/sylion-v591/sylion-pipeline/ /opt/sylion/sylion-pipeline/

# 4. Zaktualizuj zależności (argon2-cffi obowiązkowe!)
pip install -r requirements-lock.txt --upgrade

# 5. Rotacja kluczy API — KRYTYCZNE (F-001)

# 6. Zaktualizuj Caddyfile (RUNBOOK_DEPLOY.md §3.5.2)
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy

# 7. Start serwisu
sudo systemctl start sylion

# 8. Weryfikacja
curl -sf https://sylion.example.com/api/health
```

### Rollback

```bash
sudo systemctl stop sylion
./rollback.sh --dry-run   # podgląd
./rollback.sh             # wykonanie
sudo systemctl start sylion
```

---

## Zgodność i compliance

- **RODO/DSGVO:** brak zmian w przetwarzaniu danych osobowych względem v5.9.0.
- **KSeF / JPK:** brak zmian w modułach fakturowych.
- **HGB / GoBD (DE):** brak zmian w retencji audit_log (10 lat).
- **Cross-border PL↔DE:** brak zmian w SCC / transfer pricing.

Pełny audit trail: `docs/council-reports/FIX_MAP_v5.9.1.md`

---

## Kontakt

Issues / bugs: `${SYLION_ONCALL_CONTACT}`
Dokumentacja: `docs/` w katalogu instalacji
Rotacja kluczy (F-001): wykonaj przed deployem — `docs/ROLLBACK_PLAN.md`
