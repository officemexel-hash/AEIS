# SYLION v5.9.0 — RODO/DSGVO Compliance Council
## SKONSOLIDOWANY RAPORT AUDYTOWY

**Data:** 2025-07-10  
**Wersja:** SYLION v5.9.0  
**Audytorzy:**
- **Opus** (Claude Opus 4.7) — Architektura Compliance
- **Sonnet** (Claude Sonnet 4.6) — Implementacja
- **GPT-5.4** — Legal Check PL+DE
- **Gemini** (Gemini 3.1 Pro) — Cross-Border EU

**Zakres:** `/dashboard/db.py`, `/dashboard/app.py`, `/dashboard/bridge.py`, `/dashboard/seed_agents.py`  
**Regulacje:** RODO art.5, 17, 30, 32; DSGVO/BDSG §26, §35; GoBD; HGB; AI Act EU 2024/1689; KSeF/JPK (PL)

---

## 1. EXECUTIVE SUMMARY

System SYLION v5.9.0 posiada solidną architekturę compliance: migracje SQLite z wersjonowaniem, WAL-safe backup (M-08), skonfigurowalną retencję (M-03), RBAC, audit_log, mechanizm human-gate. Mechanizmy techniczne retencji (`prune_audit_log`, `prune_sessions`, `_get_retention_days`) są zaimplementowane prawidłowo.

**Krytyczne problemy wymagające natychmiastowej akcji:**
1. **API Keys Hardcoded** — klucze API wklejone literalnie w kod źródłowy `db.py` (wszystkie 4 audytory: CRITICAL).
2. **Brak RoPA** — brak `docs/RODO_COMPLIANCE.md` lub Rejestru Czynności Przetwarzania (RODO art.30) (wszystkie 4 audytory: CRITICAL).
3. **Brak SCCs/DPA** — brak udokumentowanych umów z dostawcami API US (Gemini: CRITICAL, GPT-5.4: MEDIUM→HIGH).

---

## 2. SKONSOLIDOWANA LISTA FINDINGS

### 🔴 CRITICAL (wymagają natychmiastowej akcji)

| ID | Finding | Audytorzy | Artykuł | Lokalizacja |
|----|---------|-----------|---------|-------------|
| **CRIT-01** | **API Keys Hardcoded w kodzie źródłowym** | Opus C-01, Sonnet C-01, GPT C-PL-02/C-DE-01 | RODO art.32; BDSG §64 | `db.py:_DEFAULT_API_KEYS` (linie ~43-47) |
| **CRIT-02** | **Brak Rejestru Czynności Przetwarzania (RoPA)** | Opus C-02, GPT C-PL-01, Sonnet (implicite) | RODO art.30; kara do 10M EUR | Cały projekt — brak `docs/RODO_COMPLIANCE.md` |
| **CRIT-03** | **Brak SCCs/DPA z dostawcami API (US transfers)** | Gemini C-EU-01, GPT M-DE-02 | RODO art.44-46; DSGVO art.44 | Wywołania OpenAI/Anthropic/Google/Perplexity API |

**Szczegóły CRIT-01:**  
`_DEFAULT_API_KEYS = {"OPENAI_API_KEY": "sk-proj-JwEw64A9...", "ANTHROPIC_API_KEY": "sk-ant-api03-...", ...}` — literalne klucze API w pliku Python. Choć `secret=1` w DB chroni UI-display, klucze są eksponowane w: git history, backupach SQLite (plaintext), `os.environ` procesu (`/proc/PID/environ`). Fix: wczytywać wyłącznie z `os.environ.get()` lub Vault.

**Szczegóły CRIT-03:**  
OpenAI, Anthropic, Google, Perplexity = podmioty przetwarzające (processors) z USA. Wymagane: DPA (art.28) + SCC Module 2 (2021) lub weryfikacja DPF-certification. OpenAI i Google potencjalnie certyfikowani DPF (do weryfikacji). Anthropic i Perplexity — SCC wymagane.

---

### 🟠 HIGH (pilna akcja, przed produkcją)

| ID | Finding | Audytorzy | Artykuł | Lokalizacja |
|----|---------|-----------|---------|-------------|
| **HIGH-01** | **DSR art.17 niekompletny — brak procedury erasure dla zewnętrznych podmiotów** | Opus H-01, Sonnet H-02, GPT H-PL-01, GPT H-DE-02 | RODO art.17; BDSG §35 | `app.py:delete_user()` — tylko owner-only |
| **HIGH-02** | **Retencja 365 dni bez dokumentacji uzasadnienia** | Opus H-02, GPT H-PL-02 | RODO art.5.1.e | `db.py:_AUDIT_LOG_RETENTION_DEFAULT = 365` |
| **HIGH-03** | **Scheduler prune — działa tylko gdy app jest uruchomiona** | Sonnet H-01 | RODO art.5.1.e | `app.py:_periodic_prune`, `_PRUNE_INTERVAL_S = 86400` |
| **HIGH-04** | **Brak Transfer Impact Assessment (TIA) dla US API** | Gemini H-EU-01 | EDPB Guidelines 05/2021; Schrems II | Wywołania zewnętrznych API |
| **HIGH-05** | **Dane pracownicze (BDSG §26) — brak dokumentacji** | GPT H-DE-01 | BDSG §26; BetrVG §87 | audit_log z `actor=username` |
| **HIGH-06** | **Brak szyfrowania danych w spoczynku (at-rest)** | Opus H-03 | RODO art.32 | SQLite DB plaintext |

**Szczegóły HIGH-01:**  
`DELETE /api/users/{user_id}` usuwa `sessions` + `users` — podstawa OK. Braki: (a) audit_log zawiera `actor=username` po kasowaniu konta (anonimizacja lub dokumentacja wyjątku art.17.3e wymagana), (b) brak publicznego punktu DSR dla podmiotów zewnętrznych, (c) brak SLA 30-dniowego.

**Szczegóły HIGH-03:**  
`_periodic_prune` uruchamia się co 24h tylko podczas działania uvicorn. Jeśli aplikacja jest zatrzymana przez >30 dni, sesje wygasłe nie są kasowane. Rekomendacja: systemd timer lub cron job niezależny od aplikacji.

---

### 🟡 MEDIUM (adresować w ciągu 3 miesięcy)

| ID | Finding | Audytorzy | Artykuł | Lokalizacja |
|----|---------|-----------|---------|-------------|
| **MED-01** | **Brak indeksu na `audit_log.created_at`** | Sonnet M-02 | Wydajność | `db.py` — pełne skanowanie przy prune |
| **MED-02** | **`_get_retention_days` — brak górnego limitu** | Sonnet M-01 | RODO art.5.1.e | `db.py:944-967` |
| **MED-03** | **`_get_retention_days` — brak dolnego limitu** | Opus L-03 | RODO art.5.1.e (bezpieczeństwo) | `db.py:_get_retention_days` |
| **MED-04** | **AI Act art.14 — human-gate SPEŁNIA, brak dokumentacji technicznej** | Opus M-03, GPT M-AI-01, Gemini M-EU-02 | AI Act art.11, 14 | `db.py:human_gate` schema |
| **MED-05** | **Backup M-08 — brak szyfrowania i weryfikacji checksum** | Opus M-02, Sonnet M-04 | RODO art.32 | `db.py:_backup_db_before_migration()` |
| **MED-06** | **Brak obowiązku informacyjnego art.13 dla operatorów** | Sonnet L-03→MED, GPT M-PL-02 | RODO art.13 | Dashboard login UI |
| **MED-07** | **Retencja danych po stronie dostawców API (OpenAI 30 dni, etc.)** | Gemini M-EU-05 | RODO art.28.3g | Wywołania API |
| **MED-08** | **`prune_sessions` — weryfikacja pola daty (expires_at vs created_at)** | Sonnet M-03 | RODO art.5.1.e | `db.py:prune_sessions()` |

---

### 🟢 LOW (dobre praktyki, planować)

| ID | Finding | Audytorzy | Opis |
|----|---------|-----------|------|
| **LOW-01** | `SETUP_TOKEN.txt` — potencjalny sekret w repo | Sonnet L-01 | Sprawdzić `.gitignore` |
| **LOW-02** | `test_sylion.db` w repozytorium | Sonnet L-02 | Dane testowe w repo |
| **LOW-03** | Brak rate limiting na `/api/auth/login` | Sonnet L-03 | Brute force protection |
| **LOW-04** | DPO/DSB designation — niewymagany dla dev | GPT M-DE-03 | Rozważyć przy skalowaniu |
| **LOW-05** | DPF status dostawców — weryfikacja wymagana | Gemini L-EU-01 | OpenAI, Google — prawdopodobnie OK |
| **LOW-06** | Brak Privacy Notice dla operatorów dashboardu | Opus L-02 | Footer/modal z info art.13 |

---

## 3. STATUS POPRAWNOŚCI MECHANIZMÓW RETENCJI

### ✅ DZIAŁA PRAWIDŁOWO

| Mechanizm | Status | Szczegóły |
|-----------|--------|-----------|
| `_get_retention_days()` | ✅ POPRAWNY | Fallback do default, walidacja ≤0, non-numeric |
| `prune_audit_log()` | ✅ POPRAWNY | Batch 1000/tx, WAL-safe, zwraca count |
| `prune_sessions()` | ✅ POPRAWNY | Analogiczna implementacja |
| `_PRUNE_TASKS` scheduler | ✅ AKTYWNY | Co 24h gdy app działa |
| Backup M-08 WAL-safe | ✅ POPRAWNY | Guard F-04 path traversal |
| API Keys `secret=1` w DB | ✅ POPRAWNY (UI) | Chroni wyświetlanie w UI |
| `human_gate` mechanizm | ✅ AI Act art.14 | Mode, deferred, escalation |
| AUDIT_LOG_RETENTION=365 | ✅ ADEKWATNY | 1 rok — uzasadniony celem bezpieczeństwa |
| SESSIONS_RETENTION=30 | ✅ ADEKWATNY | 30 dni — OK dla RBAC sessions |
| GoBD/HGB retencja | ✅ N/A | audit_log ≠ dokument księgowy |
| KSeF/JPK | ✅ N/A | Dev pipeline, nie produkt komercyjny |

### ⚠ WYMAGA UWAGI

| Mechanizm | Problem | Priorytet |
|-----------|---------|-----------|
| API Keys w kodzie | CRIT-01: hardcoded plaintex | Natychmiastowy |
| Prune bez indeksu | MED-01: pełne skanowanie | 3 miesiące |
| Prune gdy app off | HIGH-03: scheduler zależny od uptime | Pilny |
| At-rest encryption | HIGH-06: SQLite plaintext | Przed produkcją |

---

## 4. OCENA ZGODNOŚCI — DASHBOARD

### RODO art.5.1.e (Data Minimization / Retention)
**Ocena:** ⚠ CZĘŚCIOWO ZGODNY  
- Mechanizmy retencji DZIAŁAJĄ prawidłowo.  
- Brak dokumentacji uzasadnienia 365 dni (HIGH-02).  
- Prune zależny od uptime aplikacji (HIGH-03).

### RODO art.17 (Prawo do Usunięcia)
**Ocena:** ⚠ CZĘŚCIOWO ZGODNY  
- Endpoint `delete_user` usuwa konto i sesje.  
- Audit_log z danymi usuniętego użytkownika NIE jest anonimizowany (wymaga decyzji: anonimizacja lub dokumentacja wyjątku).  
- Brak formalnej procedury DSR dla zewnętrznych podmiotów.

### RODO art.30 (RoPA)
**Ocena:** ❌ NIEZGODNY  
- Brak rejestru czynności przetwarzania.  
- Generowany `docs/RODO_COMPLIANCE.md` adresuje ten brak.

### RODO art.32 (Security Measures)
**Ocena:** ⚠ CZĘŚCIOWO ZGODNY  
- Backup M-08: ✅  
- Audit_log retention: ✅  
- API Keys `secret=1`: ✅ (UI level)  
- API Keys hardcoded: ❌ CRITICAL  
- At-rest encryption: ❌ brak

### DSGVO/BDSG §26, §35
**Ocena:** ⚠ WYMAGA DOKUMENTACJI  
- §26: Brak dokumentacji przetwarzania danych pracowniczych (audit_log zawiera akcje operatorów).  
- §35: Brak procedury DSR zgodnej z §35 BDSG (pisemne potwierdzenie, uzasadnienie odmowy).

### GoBD / HGB (Niemcy)
**Ocena:** ✅ ZGODNY  
- audit_log = dziennik techniczny, NIE dokument księgowy.  
- Retencja 365 dni nie narusza GoBD (10 lat dotyczy dokumentów handlowych).

### KSeF / JPK (Polska)
**Ocena:** ✅ N/A  
- Lokalny dev pipeline, brak przetwarzania faktur VAT.

### AI Act EU 2024/1689 art.14 (Human Oversight)
**Ocena:** ✅ ZGODNY (architektura)  
- `human_gate` z mode/deferred_until/escalated_to spełnia wymogi art.14.  
- Brak dokumentacji technicznej systemu AI (art.11) — MEDIUM.

---

## 5. PLAN NAPRAWCZY — PRIORYTETY

### Faza 1 — Natychmiastowa (< 1 tydzień)
1. **CRIT-01**: Usunąć `_DEFAULT_API_KEYS` z kodu. Wczytywać z `os.environ` lub `.env` w `.gitignore`. Zrotować wszystkie eksponowane klucze.
2. **CRIT-02**: Wygenerować `docs/RODO_COMPLIANCE.md` (RoPA) — ✅ ZROBIONE w tym audycie.
3. **CRIT-03**: Podpisać DPA z OpenAI (Enterprise) i Anthropic. Zweryfikować status DPF dla Google/OpenAI.

### Faza 2 — Pilna (< 1 miesiąc)
4. **HIGH-01**: Dodać endpoint DSR `/api/dsr/erasure` z procedurą weryfikacji i SLA 30 dni.
5. **HIGH-02**: Udokumentować uzasadnienie retencji 365 dni w RoPA (cel bezpieczeństwa, art.6.1f).
6. **HIGH-03**: Dodać cron job / systemd timer dla prune niezależnie od uptime.
7. **HIGH-04**: Przeprowadzić TIA dla dostawców US API.

### Faza 3 — Planowa (< 3 miesiące)
8. **MED-01**: `CREATE INDEX idx_audit_log_created_at ON audit_log(created_at)`.
9. **MED-02/03**: Dodać górny i dolny limit w `_get_retention_days`.
10. **MED-04**: Sporządzić dokumentację techniczną systemu AI (AI Act art.11).
11. **MED-05**: Szyfrowanie backupów + SHA-256 checksum.
12. **MED-06**: Dodać obowiązek informacyjny art.13 w UI.

---

## 6. WYNIKI GŁOSOWANIA COUNCIL

| Finding | Opus | Sonnet | GPT-5.4 | Gemini | Konsensus |
|---------|------|--------|---------|--------|-----------|
| API Keys CRITICAL | ✅ C | ✅ C | ✅ C | ✅ C | **CRITICAL (4/4)** |
| Brak RoPA CRITICAL | ✅ C | ✅ (impl.) | ✅ C | ✅ (impl.) | **CRITICAL (4/4)** |
| SCCs/DPA CRITICAL | ✅ H | ✅ M | ✅ M-H | ✅ C | **HIGH (3/4 → CRITICAL)** |
| DSR art.17 HIGH | ✅ H | ✅ H | ✅ H | ✅ H | **HIGH (4/4)** |
| Retencja 365 OK | ✅ (z uwagą) | ✅ | ✅ | ✅ | **ZGODNY — wymaga dokumentacji** |
| GoBD N/A | ✅ | ✅ | ✅ | ✅ | **N/A — bez naruszenia** |
| KSeF N/A | ✅ | ✅ | ✅ (N/A) | ✅ | **N/A** |
| AI Act art.14 OK | ✅ (med) | ✅ | ✅ (med) | ✅ | **ZGODNY — brak dokumentacji** |
| human_gate SPEŁNIA | ✅ | ✅ | ✅ | ✅ | **SPEŁNIA art.14 (4/4)** |
| `prune_*` POPRAWNE | ✅ | ✅ | ✅ | ✅ | **IMPLEMENTACJA POPRAWNA (4/4)** |

---

## 7. SYGNATURA AUDYTORÓW

```
Opus (Architektura):    [SIGNED] 2025-07-10 — 2 CRITICAL, 3 HIGH, 4 MEDIUM, 3 LOW
Sonnet (Implementacja): [SIGNED] 2025-07-10 — 1 CRITICAL, 2 HIGH, 5 MEDIUM, 3 LOW
GPT-5.4 (Legal PL+DE): [SIGNED] 2025-07-10 — 3 CRITICAL (PL+DE), 4 HIGH, 4 MEDIUM, 1 LOW
Gemini (EU Cross-Border):[SIGNED] 2025-07-10 — 1 CRITICAL, 2 HIGH, 5 MEDIUM, 1 LOW
```

**PODSUMOWANIE COUNCIL:** 3 CRITICAL / 6 HIGH / 8 MEDIUM / 6 LOW  
**Rekomendacja:** SYLION v5.9.0 **NIE jest gotowy do produkcji** bez rozwiązania CRIT-01 (API keys) i CRIT-02 (RoPA). Dev-only deployment: akceptowalny z pisemnym potwierdzeniem ryzyka.
