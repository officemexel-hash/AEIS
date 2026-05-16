# SYLION v5.9.0 — Documentation Consistency Analysis: CONSOLIDATED REPORT

**Wykonano:** 2026-04-18  
**Metoda:** 4-analityk council (Opus, Sonnet, GPT-5.4, Gemini) — równoległa analiza  
**Pliki źródłowe:** CHANGELOG_v5.8.8.md, CHANGELOG_v5.8.8.1.md, README.md, REPORT.md, PIPELINE_IMPLEMENTATION_STATUS.md, STREAMING_IMPLEMENTATION_STATUS.md  
**Status:** KOMPLETNA — gotowa do action items

---

## EXECUTIVE SUMMARY

| Kategoria | Liczba | Najpoważniejszy |
|---|---|---|
| **Niespójności CRITICAL** | 1 | Port 8420/8421/18422 w 3 różnych plikach |
| **Niespójności HIGH** | 9 | Etapy 12/13/14, Dashboard dual-arch, Race condition fix gap, v5.8.9 roadmap orphaned |
| **Niespójności MEDIUM** | 8 | Liczba agentów 47/48, test counts, safety layers, model versions |
| **Niespójności LOW** | 5 | Format dat, language mixing, LOC claims |
| **Luki dokumentacyjne (Tier 1 — CRITICAL)** | 4 | CHANGELOG v5.9.0, MIGRATION_GUIDE, STATUS date update, v5.8.9 resolution |
| **Luki dokumentacyjne (Tier 2 — HIGH)** | 5 | UPGRADE_GUIDE, agents.yaml schema, RUNBOOK, fixes README, Dashboard arch clarification |
| **Luki dokumentacyjne (Tier 3 — RECOMMENDED)** | 6 | GLOSSARY, RODO, ADR-003, ADR-INDEX, TEST_INVENTORY, COMPATIBILITY_MATRIX |
| **RAZEM niespójności** | **23** | |
| **RAZEM nowych dokumentów do stworzenia** | **15** | |

---

## CZĘŚĆ I: LISTA NIESPÓJNOŚCI DO NAPRAWIENIA

### CRITICAL (1)

#### INC-CRIT-01: Port discrepancy — 3 różne wartości w 3 plikach
**Zgłaszający:** Opus, Sonnet, GPT-5.4  
**Konsensus:** 3/4 analityków  
**Pliki:** README.md (linie 177-179 vs linia 290), CHANGELOG_v5.8.8.md (Bug 6), REPORT.md (linia 8)

| Lokalizacja | Port | Prawidłowość |
|---|---|---|
| README.md linia 179 (orchestrator example) | 8420 | ❌ STALE — pre-fix wartość |
| README.md linia 290 (dashboard section) | 8421 | ✅ Prawidłowy po Bug 6 fix |
| REPORT.md linia 8 | 18422 | ⚠️ Test override — nigdzie nie wyjaśniony |
| CHANGELOG_v5.8.8.md Bug 6 | 8420→8421 | ✅ Dokumentuje fix |

**Naprawa:** Ujednolicić README do 8421; dodać komentarz że 18422 to `--port` override z testowego uruchomienia.

---

### HIGH (9)

#### INC-HIGH-01: Stage count — 12 vs 13 vs 14
**Zgłaszający:** Gemini  
**Pliki:** README.md ("12 etapów"), PIPELINE_STATUS.md (13 wierszy), STREAMING_STATUS.md (14 etapów: dodaje 5.5 i 5.6)

- README: "Pipeline (12 etapów)" — ale diagram pokazuje Stage 0–9 + 6.5 + 7.5 + 8.5 = 13 distinct
- PIPELINE_STATUS: tabela ma 13 wierszy (0,1,2,3,4,5,6,6.5,7,7.5,8,8.5,9)
- STREAMING_STATUS: dodaje Stage 5.5 (RUNTIME health checks) i Stage 5.6 (LLM fact-check) = 15 w orchestratorze

**Naprawa:** Zaktualizować README na "13 etapów (+ 2 sub-etapy pipeline wewnętrzne: 5.5 i 5.6)". Dodać Stage 5.5 i 5.6 do PIPELINE_STATUS.

#### INC-HIGH-02: Stage 5.5 i 5.6 nieudokumentowane w README i PIPELINE_STATUS
**Zgłaszający:** Gemini  
**Pliki:** STREAMING_STATUS.md (jedyne źródło), README.md (brak), PIPELINE_STATUS.md (brak)

Stage 5.5 (8 runtime health checks) i Stage 5.6 (fact_checker pre-deploy) są zaimplementowane i zrefencjonowane w STREAMING_STATUS, ale nieobecne w diagramie pipeline i tabeli PIPELINE_STATUS.

**Naprawa:** Dodać wiersze 5.5 i 5.6 do PIPELINE_STATUS; zaktualizować diagram README.

#### INC-HIGH-03: Race condition fix w v5.8.8 był niekompletny — brak przyzania w CHANGELOG_v5.8.8
**Zgłaszający:** GPT-5.4  
**Pliki:** CHANGELOG_v5.8.8.md (Bug 4 — "race fixed"), CHANGELOG_v5.8.8.1.md (H-02 — nowy lock w bridge.py)

CHANGELOG_v5.8.8 Bug 4 stwierdza fix race condition. v5.8.8.1 H-02 naprawia DRUGI race condition (bridge.py `_db_init_lock`). Czytelnik CHANGELOG_v5.8.8 w izolacji uwierzy, że race conditions są w pełni naprawione — to nieprawda.

**Naprawa:** Dodać w CHANGELOG_v5.8.8.md (lub nowym MIGRATION_GUIDE) notatkę: "Bug 4 fix incomplete — see v5.8.8.1 H-02 for bridge.py race".

#### INC-HIGH-04: v5.8.9 roadmap items — brak resolution (5 security items)
**Zgłaszający:** GPT-5.4  
**Pliki:** CHANGELOG_v5.8.8.1.md (PLANNED v5.8.9)

5 items zaplanowanych na v5.8.9 (key rotation, rate-limit, CSRF, SQLCipher, git filter-repo) nie mają statusu w żadnym innym dokumencie. v5.8.9 zdaje się nie istnieć (skok bezpośrednio do v5.9.0).

**Naprawa:** ADR-003 lub CHANGELOG_v5.9.0 musi jawnie adresować każdy z 5 items: DONE/DEFERRED/DROPPED.

#### INC-HIGH-05: 8 Known Issues (M-01..M-08) z v5.8.8.1 — zero traceability
**Zgłaszający:** GPT-5.4  
**Pliki:** CHANGELOG_v5.8.8.1.md (jedyne źródło)

M-01 (Pydantic), M-02 (PRAGMA migration), M-03 (prune logs), M-04 (poetry.lock), M-05 (sylion_deps.py), M-06 (SELECT optimization), M-07 (batch dep-check), M-08 (app.py refactor 6437 linii) — żaden nie pojawia się w README, PIPELINE_STATUS, REPORT ani STREAMING_STATUS.

**Naprawa:** W v5.9.0 — jawnie zaadresować każdy z M-01..M-08 w CHANGELOG_v5.9.0 (done/deferred/unchanged).

#### INC-HIGH-06: Dual dashboard architecture — nigdy niewyjaśniona
**Zgłaszający:** Gemini  
**Pliki:** README.md (linie 172-196 vs linie 281-311)

README opisuje DWA systemy dashboardu:
1. `dashboard_server.py` — "stdlib, zero external deps, startuje z pipeline" (linia 172)
2. `dashboard/` — FastAPI+SQLite, port 8421 (linia 281)

Changelogi naprawiają tylko `dashboard/`. `dashboard_server.py` może być legacy/zastąpiony. Nigdy nie wyjaśniono relacji między nimi.

**Naprawa:** README musi wyjaśnić, że `dashboard_server.py` jest starszą/uproszczoną wersją (lub usunąć odniesienie). Tylko jeden system dashboard powinien być dokumentowany.

#### INC-HIGH-07: API keys flow — 3 sprzeczne opisy
**Zgłaszający:** GPT-5.4  
**Pliki:** CHANGELOG_v5.8.8.md (hardcoded in _DEFAULT_API_KEYS), PIPELINE_STATUS.md (loaded via .env), README.md (from .env file)

CHANGELOG: klucze są hardcoded w `_DEFAULT_API_KEYS` jako fallback.  
PIPELINE_STATUS Limitations: "API keys loaded via .env/environment. No vault integration."  
README Requirements: "Klucze API: Anthropic, OpenAI, Google AI (...) (.env)"  

Żaden dokument nie opisuje pełnego łańcucha priorytetów: DB > _DEFAULT_API_KEYS > .env.

**Naprawa:** SECURITY_BASELINE.md lub README musi dokumentować pełny precedence chain.

#### INC-HIGH-08: Benchmark Reconnect timing — logiczna sprzeczność
**Zgłaszający:** GPT-5.4  
**Plik:** STREAMING_STATUS.md

- `STREAM_RECONNECT_TIMEOUT_S = 3s` (= 3000ms limit z config)
- Benchmark Reconnect target P95 = **4000ms**
- Benchmark zakończy się sukcesem przy 4000ms, podczas gdy config timeout = 3000ms

**Naprawa:** Ujednolicić — albo timeout = 4s, albo benchmark target = 3s. Dodać komentarz wyjaśniający relację.

#### INC-HIGH-09: README anti-hallucination opisuje tylko L1 (z 5 warstw)
**Zgłaszający:** Gemini  
**Pliki:** README.md (sekcja 6 — tylko file verification), PIPELINE_STATUS.md (5 layers L1-L5)

README sekcja 6 opisuje wyłącznie SHA-256 file verification (L1). Warstwy L2 (build_verification), L3 (claim_provenance), L4 (semantic_dedup), L5 (fact_checker) nie są udokumentowane w README — co jest głównym dokumentem projektowym.

**Naprawa:** Rozszerzyć sekcję README o opis wszystkich 5 warstw anti-hallucination.

---

### MEDIUM (8)

#### INC-MED-01: Liczba agentów 47 vs 48
**Zgłaszający:** Sonnet  
Canonical agents.yaml = 47. Ale CHANGELOG_v5.8.8.md Bug 3 i Finding C mówią "48-agent fallback" i "agents.yaml defaultuje enabled=true dla wszystkich 48". Źródło: prawdopodobnie jeden agent usunięty/scalony po napisaniu fallback listy, docs nie zaktualizowane.  
**Naprawa:** Zweryfikować agents.yaml (47 lub 48?) i ujednolicić WSZYSTKIE referencje.

#### INC-MED-02: Test counts — 4 różne liczby bez cross-reference
**Zgłaszający:** Sonnet, GPT-5.4  
9 (v5.8.8 regression) / 15+73 (v5.8.8.1) / 193 (STREAMING_STATUS) / 262 (README full suite)  
**Naprawa:** Dodać TEST_INVENTORY.md lub sekcję w README wyjaśniającą hierarchię: regression ⊂ streaming ⊂ full suite.

#### INC-MED-03: Safety layer taxonomy niespójna
**Zgłaszający:** Sonnet  
README: 8 sekcji ochronnych. PIPELINE_STATUS: "5 safety + 5 anti-hallucination". Loop Guard i Context Persistence są w README ale nie w tabeli PIPELINE_STATUS.  
**Naprawa:** Ujednolicić taksonomię — albo scalić tabele, albo dodać wyraźne mapowanie.

#### INC-MED-04: Model version identifiers — specific vs generic
**Zgłaszający:** Sonnet  
CHANGELOG: "Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro" (konkretne). Agents.yaml ref w docs: "claude-opus, gpt-5, gemini-pro" (generic).  
**Naprawa:** MODEL_VERSIONS.md lub sekcja w agents.yaml locking exact versions używanych w council.

#### INC-MED-05: PIPELINE_STATUS i STREAMING_STATUS dated 2026-04-11 — 7 dni przed release
**Zgłaszający:** Opus  
Oba pliki status mają "Last updated: 2026-04-11" — czyli PRZED v5.8.8 (2026-04-18) i v5.8.8.1 (2026-04-18).  
**Naprawa:** Zaktualizować datę; zweryfikować czy zawartość jest aktualna po v5.8.8.1.

#### INC-MED-06: REPORT.md nie zawiera v5.8.8.1 zmian
**Zgłaszający:** Opus  
REPORT.md tytułuje się "SYLION v5.8.8 — REPORT" i nie wspomina H-01, H-02, H-03 z v5.8.8.1 (mimo że obie wersje miały tę samą datę wydania).  
**Naprawa:** Albo dodać sekcję v5.8.8.1 do REPORT.md, albo stworzyć osobny REPORT_v5.8.8.1.md.

#### INC-MED-07: ADR-001 i ADR-002 referencjonowane ale nie w distribution
**Zgłaszający:** Opus  
CHANGELOG_v5.8.8.1.md: "Added docs/adr/ADR-001-seed-agents-guard.md" i "ADR-002-doc-scope-mismatch.md". Te pliki NIE są w zestawie 6 analizowanych dokumentów.  
**Naprawa:** Zweryfikować że ADR-001 i ADR-002 są w distribution ZIP v5.9.0; stworzyć ADR-INDEX.md.

#### INC-MED-08: `sylion_deps.py` — ghost architecture bez formalnej decyzji
**Zgłaszający:** Gemini  
ADR-002 dokumentuje mismatch z PDF (sylion_deps.py nie istnieje). M-05: "sylion_deps.py jeśli zdecydujemy się wdrożyć architekturę z PDF". Nigdzie nie ma formalnej decyzji GO/NO-GO.  
**Naprawa:** ADR-003 lub explict zapis w CHANGELOG_v5.9.0: "sylion_deps.py — DROPPED/DEFERRED".

---

### LOW (5)

#### INC-LOW-01: Format daty niespójny
CHANGELOG_v5.8.8: `**Data:**` (bold PL label) vs CHANGELOG_v5.8.8.1: `Data wydania:` vs STATUS files: `Last updated:`.  
**Naprawa:** Standard: `## Metadata\n- **Release date:** YYYY-MM-DD` we wszystkich CHANGELOG.

#### INC-LOW-02: Language mixing — polskie narracje + angielskie statusy
Changelogi i README — po polsku. PIPELINE_STATUS i STREAMING_STATUS — po angielsku. Brak policy.  
**Naprawa:** Ustalić: statusy tech = angielski, narracja = polski. Udokumentować w CONTRIBUTING.md.

#### INC-LOW-03: Absolute paths w REPORT.md i CHANGELOG
`/home/user/workspace/audit/security_v588.md`, `/home/user/workspace/council/round-prerelease-*.md` — złamane na każdej innej maszynie.  
**Naprawa:** Użyć relative paths lub repository-relative refs.

#### INC-LOW-04: "Pion D" — niezdefiniowany termin
Używany w README, STREAMING_STATUS, changelogs bez definicji.  
**Naprawa:** GLOSSARY.md + krótka definicja przy pierwszym użyciu w README.

#### INC-LOW-05: app.py LOC (6437) — tylko jedno źródło
Wspomniane tylko w M-08 CHANGELOG_v5.8.8.1 — nigdy w README ani PIPELINE_STATUS.  
**Naprawa:** Jeśli M-08 (app.py refactor) jest celem v5.9.0, powinno pojawić się w tech scope.

---

## CZĘŚĆ II: DOKUMENTY DO STWORZENIA W v5.9.0

### TIER 1 — CRITICAL (muszą istnieć przed wydaniem v5.9.0 ZIP)

| # | Dokument | Powód | Owner suggestion |
|---|---|---|---|
| D-01 | `CHANGELOG_v5.9.0.md` | Oczywisty brak | reporter agent (Stage 9) |
| D-02 | `MIGRATION_v5.8.x_to_v5.9.0.md` | 2 breaking changes v5.8.8 + potencjalnie więcej w v5.9.0; obowiązkowe dla operatorów | arch lead |
| D-03 | `docs/adr/ADR-003-v5.9.0-scope.md` | Formalne zamknięcie v5.8.9 roadmap (5 security items); resolve M-01..M-08 status; sylion_deps.py decision | arch lead |
| D-04 | Status files date refresh (PIPELINE_STATUS + STREAMING_STATUS) | Datowane 7 dni przed ostatnim release — dezinformacja | CI/automated |

### TIER 2 — HIGH (silnie zalecane przed wydaniem)

| # | Dokument | Powód | Priority |
|---|---|---|---|
| D-05 | `UPGRADE_GUIDE.md` | Krok po kroku: backup SQLite, migracja DB, zmiana config, weryfikacja portów | HIGH |
| D-06 | `docs/agents_schema.md` lub sekcja w agents.yaml | agents.yaml format nie jest nigdzie udokumentowany | HIGH |
| D-07 | `RUNBOOK.md` | Start/stop, health check, rollback "3-warstwowy" (opisany słownie, nieudokumentowany), dodanie agenta | HIGH |
| D-08 | `SECURITY_BASELINE.md` | Skonsolidowany dokument: API key precedence chain, CVE acceptance rationale, accepted risks rejestr | HIGH |
| D-09 | README port fix + dashboard architecture clarification | Naprawa INC-CRIT-01 i INC-HIGH-06 — jedna sekcja w README | HIGH |

### TIER 3 — RECOMMENDED (w pierwszym możliwym release po v5.9.0)

| # | Dokument | Powód |
|---|---|---|
| D-10 | `GLOSSARY.md` | Pion D, Strażnik Księgi, Rada, Ksiega, Human Gate — niezdefiniowane dla nowych czytelników |
| D-11 | `compliance/RODO_GDPR_NOTES.md` | Audit log data retention (M-03), key storage, operator actions — nawet dla local-only |
| D-12 | `docs/adr/ADR-INDEX.md` | Indeks ADR-001..ADR-003+ z jednozdaniowym opisem każdego |
| D-13 | `TEST_INVENTORY.md` | Mapowanie: test files → count → scope → covered bugs; resolve INC-MED-02 |
| D-14 | `COMPATIBILITY_MATRIX.md` | Python 3.12+, litellm 1.67.4.post1, FastAPI version, OS — testowane kombinacje |
| D-15 | `CONTRIBUTING.md` | Jak dodać agenta, jak pisać ADR, language policy (PL/EN), changelog format |

---

## CZĘŚĆ III: REKOMENDOWANA STRUKTURA docs/ W ZIPIE v5.9.0

```
docs/
├── CHANGELOG_v5.9.0.md                          ← D-01 [CRITICAL]
├── CHANGELOG_v5.8.8.md                          ← existing
├── CHANGELOG_v5.8.8.1.md                        ← existing
├── MIGRATION_v5.8.x_to_v5.9.0.md               ← D-02 [CRITICAL]
├── UPGRADE_GUIDE.md                             ← D-05 [HIGH]
├── RUNBOOK.md                                   ← D-07 [HIGH]
├── SECURITY_BASELINE.md                         ← D-08 [HIGH]
├── GLOSSARY.md                                  ← D-10 [RECOMMENDED]
│
├── status/
│   ├── PIPELINE_IMPLEMENTATION_STATUS.md        ← existing, date refreshed [CRITICAL]
│   └── STREAMING_IMPLEMENTATION_STATUS.md       ← existing, date refreshed [CRITICAL]
│
├── adr/
│   ├── ADR-INDEX.md                             ← D-12 [RECOMMENDED]
│   ├── ADR-001-seed-agents-guard.md             ← existing (verify in ZIP)
│   ├── ADR-002-doc-scope-mismatch.md            ← existing (verify in ZIP)
│   └── ADR-003-v5.9.0-scope.md                 ← D-03 [CRITICAL]
│
├── compliance/
│   └── RODO_GDPR_NOTES.md                      ← D-11 [RECOMMENDED]
│
├── reference/
│   ├── agents_schema.md                         ← D-06 [HIGH]
│   ├── TEST_INVENTORY.md                        ← D-13 [RECOMMENDED]
│   └── COMPATIBILITY_MATRIX.md                 ← D-14 [RECOMMENDED]
│
└── dev/
    └── CONTRIBUTING.md                          ← D-15 [RECOMMENDED]
```

**Istniejące pliki root-level:** README.md, REPORT.md — pozostają w katalogu głównym projektu (nie w docs/).

---

## CZĘŚĆ IV: FACT-CHECK SUMMARY — CHANGELOG v5.8.8 vs rzeczywistość v5.8.8.1

| Claim v5.8.8 | Status w v5.8.8.1 | Weryfikacja |
|---|---|---|
| litellm==1.67.4.post1 | ✅ Potwierdzony | CHANGELOG_v5.8.8.1 Verified section |
| 9/9 regression tests PASS | ✅ Zgodne (v5.8.8.1 rozszerza do 15/15) | CHANGELOG_v5.8.8.1 Verified |
| sync_api_keys_to_env empty fix (A) | ✅ Testowany (test_finding_a PASS) | CHANGELOG_v5.8.8.1 Verified |
| UPSERT nie re-enables UI-disabled agent (C) | ✅ Testowany (test_finding_c PASS) | CHANGELOG_v5.8.8.1 Verified |
| Race condition fully fixed (Bug 4) | ⚠️ NIEKOMPLETNE — v5.8.8.1 H-02 naprawia drugi race w bridge.py | INC-HIGH-03 |
| health_check.py v5.8.8 | ✅ Zaktualizowane do v5.8.8.1 przez H-03 | CHANGELOG_v5.8.8.1 H-03 |
| 0 eval/exec/pickle/shell=True | ✅ Potwierdzone w REPORT.md | REPORT.md security scan |
| 4 hardcoded API keys accepted | ✅ Potwierdzono akceptację w v5.8.8.1 | CHANGELOG_v5.8.8.1 Security |
| Default port 8421 (Bug 6) | ⚠️ README orchestrator section nadal mówi 8420 | INC-CRIT-01 |
| _DEFAULT_API_KEYS as developer fallback | ⚠️ PIPELINE_STATUS mówi "loaded via .env" — sprzeczne | INC-HIGH-07 |
| compute_sha256 duplicate removed | ✅ H-01 (nie bylo w v5.8.8 scope — nowe odkrycie v5.8.8.1) | CHANGELOG_v5.8.8.1 H-01 |

**Wynik fact-check:** 8 claims zweryfikowanych ✅ / 3 claims częściowo niespójnych ⚠️ / 0 claims fałszywych ❌

---

## METRYKI COUNCIL

| Analityk | Plik | Niespójności | Luki |
|---|---|---|---|
| Claude Opus 4.7 | opus.md | 9 | 7 |
| Claude Sonnet 4.6 | sonnet.md | 9 (15 findings total) | 6 |
| GPT-5.4 | gpt54.md | 12 | 0 (embedded in findings) |
| Gemini 3.1 Pro | gemini.md | 8 | 15 new docs |
| **CONSOLIDATED (deduplicated)** | **CONSOLIDATED.md** | **23** | **15** |

**Duplikaty wyeliminowane przy konsolidacji:** 12 (port issue zgłoszone przez 3 analityków jako jedna pozycja; test count by 2 analityków = 1 pozycja; race condition by 1 analityk mapped to fact-check; etc.)

---

*Wygenerowano przez: doc-analiza-council orchestrator, SYLION v5.9.0 pre-release*  
*Pliki analityków: opus.md, sonnet.md, gpt54.md, gemini.md (ten sam katalog)*
