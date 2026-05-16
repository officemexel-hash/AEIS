# AEIS — KOMPLEKSOWY RAPORT AUDYTOWY
## Synteza audytów Codex (2026-04-25 → 2026-05-08) vs Claude Phase 2 (2026-04-24 → 2026-04-25)

**Data raportu:** 2026-05-12
**Autor:** Synteza niezależna na podstawie ~50 dokumentów audytowych
**Hierarchia dowodowa:** kod > runtime > API > UI > testy > dokumentacja > audit innego modelu
**Ocena końcowa AEIS:** 62/100 — SYSTEM FEDERATED / DEV-STAGING CAPABLE / NOT PRODUCTION READY

---

## 1. EKSEKUTYWNE PODSUMOWANIE

AEIS (Autonomous Enterprise Intelligence System) nie jest greenfieldem. To szeroki system FastAPI + Next.js z ~37 pakietami backendowymi, ~744 modułami .py, ~126 plikami route, ~125 trasami frontendu, ~1599 ścieżkami OpenAPI i ~14 000 zebranych testów. Największym problemem nie jest brak modułów, lecz **pofragmentowane płaszczyzny prawdy** (split truth planes) i **niespójna integracja runtime**.

### 1.1. Podstawowe fakty liczbowe

| Wymiar | Wartość |
|---|---|
| Pakiety backendowe | 37 |
| Moduły backend .py | 354-744 (zależnie od metody liczenia) |
| Pliki route API | 83-126 |
| Trasy frontend Next.js | 56-127 |
| Ścieżek OpenAPI runtime | 1394-1947 (dryf w czasie) |
| Testy zebrane | ~14 243 |
| Manifesty JSON | 115-119 |
| Protokoły proto | 6-22 |
| Repo skills | 27-29 |

### 1.2. Werdykt końcowy

**AEIS jest:**
- `ADVANCED STAGING CANDIDATE` — duży, żywy system z działającym backendem, frontendem i wieloma podsystemami.
- `NOT PRODUCTION READY` — z powodu trwałych pęknięć w core spine, rozszczepionych płaszczyzn prawdy i braku pełnego dowodu end-to-end.

**Kluczowe osiągnięcia potwierdzone niezależnie:**
1. **Workspace spine** działa: `kickoff → canon → masterplan → Human Gate → launch → bundle deploy` — zweryfikowane runtime'owo.
2. **Unified governance tickets** działają: tworzenie, rozstrzyganie, audit trail, mobile bridge.
3. **Funding backend** jest realnym pionem domenowym z store, API, UI i lokalnym approval flow.
4. **Model Council** ma strukturę: role, rangi, wagi, podpis krytyka, sentinele — ale wpływ na pipeline jest częściowy.
5. **Memory bootstrap** wstaje i nie jest już pusty (`unique_terms = 903`, `indexed_sections = 24`).
6. **Skills runtime** bootstrapuje się (`loaded_skills = 3` seed skills).

**Kluczowe blokery produkcyjne (P0-P1):**
1. **Workspace Human Gate crashuje** (`AttributeError: 'HumanGate' object has no attribute 'list_sessions'`).
2. **Workspace Idea Vault crashuje** (`TypeError` na niezgodne sygnatury).
3. **Skills registry ≠ skills runtime** — rozłączne płaszczyzny.
4. **Memory API** jest fragmentaryczny (`/memory/search` 404, `/evidence/stats` cieniowany).
5. **Funding approvals** nie są przepięte na unified governance tickets.
6. **Frontend compile breaks** na `/workers` i `/observability`.
7. **Projects UI** jest podpięty pod zły plane danych.
8. **Startup log** pełen `register error — Dependency X not registered`.

---

## 2. METODOLOGIA I HIERARCHIA DOWODOWA

### 2.1. Zasada prawdy

W całym audycie obowiązuje hierarchia:

```
kod → runtime → API → UI → testy → dokumentacja → audit innego modelu
```

Dokumentacja nigdy nie wygrywa z kodem. Audit innego modelu traktowany jest jako źródło wtórne.

### 2.2. Etapy audytu

| Etap | Data | Zakres | Agent |
|---|---|---|---|
| Bazowy audyt Codex | 2026-04-24 | Inwentaryzacja, drift map | Codex |
| Re-audyt Codex Phase 2 | 2026-04-25 | Weryfikacja claimów Claude'a | Codex |
| Audyt Claude Phase 2 | 2026-04-24-25 | Parallel execution, D-INTEGRATE | Claude |
| Audyt dashboardowy | 2026-05-02 | UI walk z klikaniem, 28 tras | Codex |
| Deep audit VPS/env | 2026-05-02 | Skalowanie środowisk, deploy | Codex |
| Mapa napraw | 2026-05-08 | Priorytety, masterplan naprawczy | Codex |

### 2.3. Metody weryfikacji

1. **Kod:** inspekcja plików `.py`, struktury pakietów, importów.
2. **Runtime:** HTTP probe na żywym backendzie (`/health`, kluczowe endpointy).
3. **API:** OpenAPI introspection, TestClient, sekwencyjne CRUD.
4. **UI:** Playwright/browser walk, route crawl (`67/67` tras bez krytycznych błędów po naprawach).
5. **Testy:** pytest, `npx tsc --noEmit`, testy integracyjne.
6. **Browser evidence:** screenshoty, network logs, console errors.

---

## 3. INWENTARYZACJA SYSTEMU

### 3.1. Architektura logiczna (federacyjna)

AEIS nie jest monolitem liniowego pipeline'u. To **graf federacyjny**:

```
Next.js Operator Surface ──→ frontend api client ──→ FastAPI main router
                                                            │
    ┌─────────────┬─────────────┬─────────────┬─────────────┼─────────────┬─────────────┐
    ▼             ▼             ▼             ▼             ▼             ▼             ▼
 workspace    governance     memory       skills      funding      project_mode     lab
    │             │             │             │             │             │             │
 kickoff    human_gate     indexer     registry      store        engine       cellular
 canon      tickets        evidence    runtime     submission   worker_pool    sdr
 council    policies       retrieval   executor    approval     execution      vps
 settings   audit_chain    self-model  catalog     browser      deployment     container
```

### 3.2. Klasyfikacja modułów (synteza Codex + Claude)

| Klasa | Liczba modułów | Przykłady |
|---|---|---|
| **CORE** | 14 obszarów | API aggregation, workspace, project_mode, governance, memory, skills, workers, operator console |
| **EXTENSIONS** | 11 obszarów | Funding, observability, quality, rebuild, infra, devices, VPS, container, cellular, SDR |
| **EXPERIMENTAL** | 3 obszary | AEIS self-evolution, gRPC stubs, cognitive layer (część) |
| **DUPLICATE** | 4 kluczowe | Human Gate split, funding vs global governance, Next.js vs legacy dashboard, governance/core/security duplikaty |
| **LEGACY** | 2 obszary | Stary dashboard Python, zewnętrzny pakiet SYLION_Dashboard_V5 |
| **PLANNED** | 1 obszar | Operator Mobile (prompt-only, brak backend/frontend app) |

### 3.3. Stan warstw W1-W19 (zgodność z kanonem)

| Warstwa | Status | Dowód / luka |
|---|---|---|
| W1 Canon | PARTIAL | `/api/v1/architecture-layers` eksponuje W1-W19, ale reguły nie są jednolitym silnikiem wymuszania |
| W2 Workspace | LIVE/PARTIAL | Backend, SQLite, lokalny runtime; workspace działa jako główny spine |
| W3 Operator Identity | PARTIAL | Profile, mobile operator_id istnieją, ale pełna tożsamość nie jest centralnie wymuszana |
| W4 Provider & Model Catalog | LIVE/PARTIAL | Endpointy istnieją; Council potrafi użyć realnego fallbacku API; brak twardego local-first gate |
| W5 Runtime/Environment | LIVE/PARTIAL | Local backend, workers, VPS/container/device endpoints; topologie puste |
| W6 Defaults/Autonomy | PARTIAL | Endpointy i panele istnieją; brak dowodu, że medium autonomy steruje każdą decyzją |
| W7 Guards/Human Gate | LIVE/PARTIAL | Human Gate tree i governance tickets działają; globalne wymuszanie wymaga E2E |
| W8 Memory | PARTIAL | health/search/stats działają, ale indeks i evidence są startowo puste |
| W9 Skills | PARTIAL | runtime stats pokazują załadowane skills, ale catalog pusty; reuse nieudowodniony |
| W10 Intake | PARTIAL/LIVE | Projekty i intake-like surfaces istnieją; pełne pytania startowe wymagają E2E |
| W11 Model Council | LIVE/PARTIAL | Role, rangi, wagi, sentinele, podpis krytyka, consensus działają; koszt/API nie jest wystarczająco widoczny |
| W12 Source of Truth | PARTIAL | Księgi i project canon endpoints istnieją, ale pusty stan nie dowodzi pełnego SoT lifecycle |
| W13 Masterplan | PARTIAL | Planning/masterplan endpoints istnieją; freeze/Human Gate wymaga dalszego E2E |
| W14 Quality Gates | PARTIAL | Test-center i quality stats działają, ale stats puste; human-like test suite wymaga utrzymania |
| W15 Ontology | PARTIAL | Warstwa opisana i endpointy/route istnieją; potrzebny twardszy kontrakt domenowy |
| W16 Worker Execution | LIVE/PARTIAL | Workers API działa; brak dowodu pełnego rozproszonego builda |
| W17 Integrations | PARTIAL/LIVE | Funding/mobile/VPS/container/device/lab endpoints istnieją; external submit wymaga E2E |
| W18 Operator Console | PARTIAL | Terminal health działa; `broadcaster_wired=false`; klik→komenda nie jest globalnym kontraktem |
| W19 Audit/Closure/Learning | PARTIAL | Audit/governance evidence istnieje; memory snapshot i lessons learned nie są automatyczne |

---

## 4. MAPA ROZJAZDOW (DRIFT MAPS) — KOD vs DOKUMENTACJA vs CLAIMY

### 4.1. Drift architektoniczny (6 krytycznych roszczeń)

| ID | Obszar | Rozjazd | Wpływ | Status naprawy |
|---|---|---|---|---|
| D1 | **Runtime Truth** | Frontend używa `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010`, ale pojawiają się instancje na `8000`. Brak panelu PID/cwd/git. | Niepewna wersja systemu, ryzyko debugowania starego procesu | Brak naprawy |
| D2 | **Memory Plane Split** | Globalne `/api/v1/memory/*` puste; engine używa per-project SQLite. Startup `app.py` nie binduje globalnego db. | Memory nie jest współdzielona pomiędzy projektami | Brak naprawy |
| D3 | **Skills Registry ≠ Runtime** | Registry żyje (`total_skills = 0` w Phase2 → teraz seed skills załadowane), ale w Phase2 runtime nie miał `skills_dir`. | Skills nie są wykonywalne | Częściowo naprawione (seed skills) |
| D4 | **Human Gate Split Brain** | Globalny gate (`/api/v1/gates/human/requests` pusty) vs sesyjny workspace gate (crashuje) vs lokalny funding. | Niezdefiniowany model approval | Brak naprawy |
| D5 | **Funding Governance Local vs Global** | Finalny submit funding jest blokowany lokalnie, ale brak dowodu przepływu przez globalny AEIS Human Gate. | Governance nie jest jednolity | Brak naprawy |
| D6 | **Worker Pool Reconciliation** | `_derive_worker_pool()` zwraca istniejący pool bez przebudowy. Konfiguracja `local_docker` zostawia VPS workerów. | Niespójna topologia wykonawcza | Brak naprawy |

### 4.2. Drift API (trasy vs deklaracje)

| Typ | Liczba | Opis |
|---|---|---|
| Endpointy BE (OpenAPI) | 1615 | Dynamiczne trasowanie FastAPI |
| Endpointy FE (deklaracje) | 788 | Klient API frontend |
| Niepotwierdzone (`no`) | ~50 | Endpointy zadeklarowane, ale niepotwierdzone runtime'owo |
| Legaci/migracyjne | ~30 | Stare endpointy kickoff, council, settings |

**Przykłady dryfu API:**
- `GET /api/v1/workspace/ideas?category=X` — route layer wysyła `category`, ale `IdeaVault.list_ideas()` nie akceptuje tego argumentu (`TypeError`).
- `GET /api/v1/workspace/ideas/stats` — route wywołuje `get_stats()`, którego nie ma w `IdeaVault` (`AttributeError`).
- `GET /api/v1/memory/evidence/{evidence_id}` — cieniuje `/api/v1/memory/evidence/stats` w routerze FastAPI → `404` na stats.
- `POST /api/v1/workspace/projects/kickoff` — zwraca `404`; prawdopodobnie zastąpiony przez `/workspace/ideas/{idea_id}/submit-pipeline`.
- `GET /api/v1/skills/runtime/stats` — zwraca `loaded_skills = 0` w Phase2 (niezabootstrappowany runtime).
- `POST /api/v1/skills/runtime/execute?skill_name=seed_skill_001` → `failed` / `Unknown skill` w Phase2.

### 4.3. Drift dokumentacyjny (Codex vs Claude)

| Roszczenie Claude'a | Werdykt Codexa | Dowód |
|---|---|---|
| "Claude Phase 2 naprawił workspace + council" | **Ograniczona prawda** | Pliki `council_hybrid.py`, `idea_vault.py` nowe; crash `list_sessions` trwa |
| "Memory + skills = resolved" | **Częściowo prawda** | Bootstrap załadował seed skills; memory health ok; search pusty; evidence=0 |
| "Funding governance = complete" | **Fałsz** | Lokalne approval, brak integracji z globalnym gate |
| "Worker pool bootstrapped" | **Fałsz** | W Phase2 `_derive_worker_pool` nie buduje poola |
| "Build green" | **Niepewne** | Frontend compile break na `/workers` i `/observability` w Phase2 |
| "Claude branch = P0 fixed" | **Fałsz** | Codex przetestował codex-final i claude-phase2; crash workspace trwał w obu |
| "Human-like test = browser test" | **Fałsz** | Był to `FastAPI TestClient walkthrough`, nie test przeglądarkowy |

### 4.4. Niespójność wewnętrzna w `.audit_500`

| Dokument | Zadeklarowany wynik | Rzeczywisty wynik |
|---|---|---|
| `FINAL_REPORT.json` | `0 open_deferred`, `PRODUCTION_READY` | Smoke test zawierał 2 deferred |
| `SMOKE_TEST.json` | Zawierał 2 deferred | Ominięty w podsumowaniu końcowym |
| `QA_CHECKLIST.md` | "8 critical items addressed" | Brak dowodu adresowania P0 workspace crash |
| `MERGED_ARCHITECTURE_SPEC.md` | "Phase 3 ready, no blockers" | Głęboki dryf między spec a kodem |

**Wniosek:** Pakiet `.audit_500` jest **fikcją produkcyjności** — naprawy w nim zawarte są realne i poprawne, ale weryfikacja niespójna, a roszczenie produkcyjności jest przesadzone.

---

## 5. OCENA GOTOWOŚCI PRODUKCYJNEJ

### 5.1. Ocena kanoniczna (58/100)

| Kryterium | Max | Wartość | Uzasadnienie |
|---|---|---|---|
| Produktywny workspace (W2) | 10 | 7 | Żywy flow; crash Human Gate i Idea Vault obniża |
| Unified governance (W7) | 10 | 6 | Tickets działają; split brain obniża |
| Council decyzyjność (W11) | 10 | 6 | Struktura ok; wpływ na pipeline nieudowodniony; `active_size=1` obniża |
| Memory + evidence (W8) | 10 | 5 | Bootstrap seed działa; search pusty; evidence=0 |
| Skills runtime (W9) | 10 | 5 | Runtime zasilony; reuse E2E nieudowodniony |
| Build bez mocków (W14) | 10 | 5 | Test-center działa; stats puste; coverage nieznana |
| Stop-Fix-Restart (W16-W18) | 10 | 5 | Polityka istnieje; nie jest automatycznie wymuszana |
| UI na trasach kluczowych | 10 | 6 | 67/67 tras; kompily na 2 trasach; projects podpięty pod zły plane |
| Startup stability | 10 | 5 | Backend startuje; log pełen błędów DI |
| Documentation drift | 10 | 4 | Drift ~1615 vs ~788; duplikaty; pliki nieobsłużone |

### 5.2. Ocena względem poziomów dojrzałości

| Poziom | Definicja | Status |
|---|---|---|
| P0 (Foundation) | `workspace + council + human_gate` + puste `memory/skills` | **Niepełny** — P0 Human Gate crashuje |
| P1 (End-to-end build) | P0 + działający worker + deploy bundle + 1 projekt | **Brak** — niezweryfikowany pełny cykl |
| P2 (Multi-project + Funding) | P1 + funding scenario (bez external submit) | **Brak** — funding UI jest, ale submit nie E2E |
| P3 (Multi-agent + Rada) | P2 + >1 agent, council quorum, masterplan freeze | **Brak** — quorum nie jest twarde |
| P4/P5 (Error handling + Real use) | P3 + wykrywa błęd, Stop-Fix-Restart, realne użycie | **Brak** — stop nie jest automatyczny |

### 5.3. Ewaluacja zewnętrznych zagrożeń

| Zagrożenie | Poziom | Uzasadnienie |
|---|---|---|
| Bazowe zagrożenia | LOW-MEDIUM | Dostawca danych (MOCK), model AI (wymuszony naive), operator (brak RBAC) |
| Pojawiające się zagrożenia | LOW-MEDIUM | Interakcja modeli, oszustwa danych, manipulacja promptów |
| Przyszłe zagrożenia | MEDIUM | Ataki na supply chain AI, wymuszone zachowania agentów, manipulacje kognitywne |
| Systemiczne zagrożenia | MEDIUM | Dependency na modelach zewnętrznych, dług terminologiczny, brak kryptograficznych podpisów |

---

## 6. ANALIZA RÓŻNIC PLANÓW RÓWNOLEGŁYCH (CLAUDE vs CODEX)

### 6.1. Strategia Claude'a (Phase 2 + parallel)

**Paradygmat:** Greenfield replacement + parallel enhancement
- Nowe `skills/` (zamiast fix `sylion/skills/runtime.py`)
- Nowe `memory/search/` (zamiast fix `memory_routes.py`)
- Nowe `funding/*` scannery (zamiast integracji z istniejącym `funding_autopilot`)
- Nowy `core/*` adapter spine (zamiast konsolidacji istniejących routerów)

**Ryzyko:** Duplikowanie namespace'ów, rozszczepienie kodu, zwiększenie długu strukturalnego.

### 6.2. Strategia Codex'a

**Paradygmat:** Fix + Bootstrap + Integrate
- Naprawić istniejący workspace spine (Human Gate, Idea Vault)
- Bootstrapować puste runtimes (skills, memory)
- Zunifikować governance planes
- Utrzymać i utwardzić żywe trasy

**Wniosek:** Strategia Codex'a jest prawidłowa dla obecnego stanu systemu. AEIS ma już silny spine — należy go konsolidować, nie zastępować.

---

### 6A. Rekomendacja strategiczna — Co zrobić z core/* i greenfieldami z planów Claude'a

**Werdykt: ODRZUCIĆ greenfield, przyjąć strategię konsolidacji.**

Plan Claude'a Phase 3 proponuje:
1. Nowy namespace core/* jako adapter spine.
2. Nowe skills/ zamiast naprawy sylion/skills/runtime.py.
3. Nowe memory/search/ zamiast naprawy memory_routes.py.
4. Nowe unding/* scannery zamiast integracji z istniejącym unding_autopilot.

**Dlaczego to zagrożenie:**
- AEIS ma już ~744 moduły, ~126 plików route i ~1599 ścieżek API.
- Dodanie nowych namespace'ów zamiast naprawy istniejących zwiększy dług strukturalny z ~58/100 do potencjalnie <50/100.
- Istniejący spine workspace → project_mode → governance jest żywy i działa (z wyjątkiem znanych crashy P0).
- Rozszczepienie płaszczyzn prawdy jest JUŻ problemem — duplikowanie namespace'ów pogorszy je.

**Alternatywa proponowana (strategia Codex):**
1. **Fix, nie replace:** Naprawić human_gate.list_sessions(), idea_vault.list_ideas(category), _derive_worker_pool().
2. **Bootstrap, nie twórz:** Podłączyć skills_dir do istniejącego 
untime.py, zbindować db_path w pp.py.
3. **Integrate, nie izoluj:** Przepiąć funding approvals na unified governance tickets.
4. **Consolidate, nie rozszczepiaj:** Zunifikować Human Gate do jednej płaszczyzny.

**Jedyny wyjątek:** Jeśli core/* ma być warstwą abstrakcji nad ISTNIEJĄCYMI modułami (adapter pattern, nie replacement), można rozważyć — ale tylko jako thin wrapper, nie jako nowy spine.

**Metryka sukcesu:** Po 40h developmentu P0-P1, ocena powinna wzrosnąć z 58/100 do 75/100 bez dodania nowych namespace'ów.

### 6B. Szacunki effortu vs rzeczywisty postęp (timeline)

**Zadeklarowane vs wykonane:**

| Sprint | Zadeklarowany cel | Rzeczywisty wynik | Różnica |
|---|---|---|---|
| Claude Phase 2 (24-25.04) | "Fix P0, production ready" | Naprawy częściowe (council_hybrid, idea_vault), ale crash workspace trwał | Overclaim |
| Codex Re-audyt (25.04) | Weryfikacja claimów | Potwierdzono 6 osiągnięć, odrzucono 7 roszczeń | Evidence-based |
| Dashboard Audit (02.05) | UI walk 28 tras | 67/67 tras, 5 błędów naprawionych, retest pass | Real progress |
| Deep Audit VPS (02.05) | Skalowanie środowisk | Potwierdzono topologie, worker pool, env catalog | Partial |
| Repair Map (08.05) | Priorytety naprawcze | 18 zadań P0-P3 z szacunkami effortu | Accurate |

**Effort do stagingu:**
- P0: ~18h (6 zadań × średnio 3h)
- P1: ~29h (6 zadań × średnio 4.8h)
- P2: ~19h (5 zadań × średnio 3.8h)
- P3: ~18h (3 zadań × średnio 6h)
- **Razem: ~84h developmentu + ~20h testów/browser = ~104h (~13 dni × 1 FTE)**

**Wnioski:**
- Szacunek Claude'a "Phase 2 w 2 dni = production ready" był nierealny (potrzeba ~13 dni na sam staging).
- Postęp Codex'a (audity + naprawy UI) był bardziej realistyczny i evidence-based.
- Kluczowe opóźnienie: każda naprawa P0 wymaga testu browserowego, co dodaje ~2h per iteracja.

### 6C. Porównanie modeli audytowych — Codex vs Claude

**Metodologia:**

| Aspekt | Codex | Claude |
|---|---|---|
| **Filozofia** | Evidence-based sceptycyzm | Optimistic execution |
| **Hierarchia dowodowa** | kod > runtime > API > UI > docs | docs > code (claim-driven) |
| **Testowanie** | Runtime probe + browser walk | TestClient walkthrough |
| **Raportowanie** | Drift maps, wyceny numeryczne | Binary ready/not-ready |
| **Naprawy** | Minimalne, targetowane | Szerokie, greenfield-oriented |

**Wzorce błędów:**

| Wzorzec | Claude | Codex |
|---|---|---|
| Overclaim | "Production ready" przy crashach P0 | "58/100" zamiast binary pass/fail |
| Underverification | Brak testu browserowego | Brak testu 24h lifecycle |
| Scope creep | Nowe namespace'y zamiast fixów | Głęboki audit zamiast szybkich napraw |
| Documentation bias | FINAL_REPORT > SMOKE_TEST | kod > FINAL_REPORT |

**Rekomendacja dla przyszłych audytów:**
1. **Zawsze wymagaj testu browserowego** — TestClient nie wystarczy.
2. **Używaj skali numerycznej** (0-100) zamiast binary pass/fail.
3. **Weryfikuj niespójności wewnętrzne** w pakietach audit_500.
4. **Preferuj fix over replace** — nowe namespace'y to ostateczność.
5. **Dokumentuj drift maps** — różnice między deklaracją a runtime'em.

### 6D. Ryzyka biznesowe i compliance

**Ryzyka operacyjne:**

| Ryzyko | Poziom | Opis | Mitigacja |
|---|---|---|---|
| False positive production ready | HIGH | Roszczenie Claude'a mogło prowadzić do przedwczesnego wdrożenia | Wymuszenie niezależnego audytu |
| Data loss przy crashach P0 | MEDIUM | Workspace Human Gate crashuje — brak graceful degradation | Retry logic + fallback to manual |
| Split brain governance | HIGH | Niejasność, który gate jest autorytatywny | Zunifikowanie lub formalizacja federacji |
| Skill execution failure | MEDIUM | Runtime nie znajduje skills mimo deklaracji | Bootstrap + registry reconciliation |

**Ryzyka compliance (GDPR/AI Act):**

| Wymaganie | Status | Gap |
|---|---|---|
| Explainability (AI Act Art. 13) | PARTIAL | Council ma logi, ale brak automatycznych raportów dla użytkownika |
| Human oversight (AI Act Art. 14) | PARTIAL | Human Gate istnieje, ale crashuje; brak fallbacku |
| Data minimization (GDPR Art. 5) | UNKNOWN | Brak audytu co do zakresu przechowywanych danych |
| Audit trail | PARTIAL | Governance tickets mają trail, ale memory evidence jest puste |

**Rekomendacja:** Przed jakąkolwiek eksploatacją zewnętrzną przeprowadzić audit compliance z udziałem eksperta prawnego.

### 6E. Checklist dla następnego audytu (przewidywalny)

**Pre-audit (przed rozpoczęciem):**
- [ ] Potwierdź wersję backendu (PID, cwd, git commit, branch)
- [ ] Potwierdź wersję frontendu (build timestamp, npm list)
- [ ] Wykonaj backup bazy danych (SQLite)
- [ ] Przygotuj środowisko testowe (osobny port, osobna baza)

**Runtime probe (5 min):**
- [ ] GET /health — status, modules count
- [ ] GET /openapi.json — liczba tras, porównanie z baseline
- [ ] GET /api/v1/skills/runtime/stats — loaded_skills > 0
- [ ] GET /api/v1/memory/index/stats — indexed_sections > 0
- [ ] GET /api/v1/governance/tickets — count >= 0 (nie 500)

**Workspace spine (15 min):**
- [ ] POST /api/v1/workspace/ideas — utwórz pomysł
- [ ] GET /api/v1/workspace/ideas?category=X — filtruj (nie TypeError)
- [ ] GET /api/v1/workspace/ideas/stats — stats (nie AttributeError)
- [ ] POST kickoff lub submit-pipeline — 200, nie 404
- [ ] GET /api/v1/workspace/humangate/sessions — list sessions (nie AttributeError)
- [ ] POST /api/v1/workspace/humangate/nodes/{id}/choose — wybierz node

**Browser walk (30 min):**
- [ ] Dashboard — render bez błędów console
- [ ] Operator monitor — odświeżanie co 30s działa
- [ ] Projects — lista projektów, szczegóły
- [ ] Human Gate — tree renderuje się, wybór działa
- [ ] Council — role, rangi, wagi widoczne
- [ ] Funding — źródła, submission, approvals
- [ ] Terminal W18 — przewijanie, nie przykrywa kontrolek

**Regression tests (15 min):**
- [ ] npx tsc --noEmit — 0 błędów
- [ ] pytest — pass rate > 95%
- [ ] No-mock scan — 0 mocków w ścieżce krytycznej
- [ ] Stop-Fix-Restart — symulacja błędu P0, system blokuje

**Post-audit (5 min):**
- [ ] Zrób screenshot dashboardu
- [ ] Wyeksportuj logi backendu (stderr)
- [ ] Porównaj wyniki z baseline (poprzedni audit)
- [ ] Oceń drift (nowe błędy, naprawione, utrzymujące się)

### 6F. Template dla raportu naprawczego (per-P0)

**Format raportu naprawczego dla każdego zadania P0:**

```markdown
## [ID_ZADANIA]: [TYTUŁ]

**Status:** [OPEN | IN_PROGRESS | FIXED | VERIFIED]
**Przypisane do:** [osoba/model]
**Szacunek:** [Xh]
**Rzeczywisty czas:** [Yh]

### Opis problemu
[Co się dzieje, krok po kroku]

### Dowód (repro)
```bash
# Komenda repro
curl -X GET http://127.0.0.1:8010/api/v1/...
# Oczekiwane: 200 + JSON
# Rzeczywiste: 500 / AttributeError / TypeError
```

### Root cause
[Analiza kodu — dlaczego tak się dzieje]

### Naprawa
[Zmiana w kodzie — diff lub opis]

### Testy
- [ ] Unit test (pytest)
- [ ] Integration test (TestClient)
- [ ] UI test (Playwright / browser walk)
- [ ] Regression test (czy nie zepsuło czegoś innego)

### Weryfikacja
[Screenshot / log / wynik testu]

### Drift check
- [ ] Czy naprawa nie wprowadziła nowych endpointów zamiast fixu?
- [ ] Czy dokumentacja (CHANGELOG) została zaktualizowana?
- [ ] Czy ocena systemu wzrosła (score before/after)?
```

**Zasady:**
1. Każde P0 MUSI mieć repro.
2. Każde P0 MUSI mieć test UI (browser).
3. Każde P0 MUSI aktualizować CHANGELOG.
4. Score przed/after musi być udokumentowany.

### 6G. Matrix decyzyjna — co robić przy nowym crashu

**Schemat postępowania operatora:**

```
CRASH (500/AttributeError/TypeError)
│
├─> Czy dotyczy P0 (workspace/humangate/skills/memory/governance)?
│   ├─ TAK → STOP (zablokuj execution-start, test-center)
│   │         ├─> Repro → Root cause → Fix → Test UI → Restart → Verify
│   │         └─> Jeśli fix > 4h → tymczasowy fallback (manualny gate)
│   └─ NIE → Log do deferred (P1/P2)
│
├─> Czy jest nowy (nieznany z poprzedniego audytu)?
│   ├─ TAK → Dodaj do drift map, oceń wpływ, aktualizuj score
│   └─ NIE → Sprawdź czy regression (czy naprawa cofnęła fix)
│
├─> Czy dotyczy API czy UI?
│   ├─ API → TestClient repro + log backendu + diff kodu
│   └─ UI → Browser screenshot + console errors + network log
│
└─> Czy wymaga nowego namespace'u (core/*, nowy skills/*)?
    ├─ TAK → ODRZUĆ. Szukaj fix w istniejącym kodzie.
    └─ NIE → Kontynuuj standardowy fix.
```

**Kluczowe zasady:**
1. **Stop first** — nigdy nie kontynuuj execution przy P0.
2. **Repro before fix** — nie naprawiaj czegoś, czego nie potrafisz odtworzyć.
3. **UI test mandatory** — TestClient to za mało.
4. **No new namespaces** — fix > replace.
5. **Document drift** — każdy nowy crash to nowy wpis w drift map.

### 6H. Słownik terminologii (AEIS glossary)

**Aby uniknąć długu terminologicznego:**

| Termin | Definicja | Kontekst |
|---|---|---|
| AEIS | Autonomous Enterprise Intelligence System | Główny system |
| Workspace | Moduł intake'u pomysłów, Księgi, Masterplanu | W2 |
| Human Gate | Mechanizm approval człowieka w pipeline | W7 |
| Council | Rada decyzyjna z rolami, rangami, wagami | W11 |
| Masterplan | Plan wykonawczy projektu z freeze gate | W13 |
| Source of Truth | Kanoniczna Księga projektu | W12 |
| Runtime Truth | Panel weryfikacji wersji systemu (PID, git) | D1 |
| Split Brain | Rozszczepienie płaszczyzn prawdy (np. 3 Human Gate) | D4 |
| Drift Map | Mapa różnic między kodem a dokumentacją | Sekcja 4 |
| P0/P1/P2/P3 | Priorytety naprawcze (Critical/High/Medium/Low) | Sekcja 7 |
| Stop-Fix-Restart | Procedura naprawcza przy wykryciu P0 | P0.2 |
| No-Mock Gate | Wymuszenie braku mocków w ścieżce krytycznej | P0.3 |
| Evidence-Based | Hierarchia dowodowa: kod > runtime > API > UI | Sekcja 2 |
| Greenfield | Tworzenie nowego kodu zamiast naprawy istniejącego | Sekcja 6A |
| Bootstrap | Inicjalizacja runtime'u (skills, memory) przy starcie | P1.1, P1.2 |
| Reconciliation | Dopasowanie stanu (np. worker pool) do konfiguracji | P1.5 |
| Federation | Model rozproszony (AEIS jako federacja modułów) | Sekcja 3.1 |
| Overclaim | Przesadzone roszczenie (np. "production ready") | Sekcja 4.3 |
| Audit_500 | Pakiet hardeningu (.zip z poprawkami) | Załącznik 5 |
| SMOKE_TEST | Szybki test wstępny | Sekcja 4.4 |
| TestClient | Testy API przez FastAPI TestClient (nie browser) | Sekcja 6C |
| Browser Walk | Test UI przez realną przeglądarkę (Playwright) | Checklist 6E |
| Runtime Probe | Szybki test endpointów na żywym backendzie | Checklist 6E |
| Deferred | Zadanie odłożone na później (nie krytyczne) | Sekcja 4.4 |
| Registry | Baza danych skills (metadane) | P1.1 |
| Runtime | Wykonawca skills (executor) | P1.1 |
| Evidence Store | Magazyn dowodów (memory) | D2 |
| Indexer | Moduł indeksowania tekstu (memory) | D2 |
| Worker Pool | Zbiór workerów przypisanych do projektu | P1.5 |
| Execution Plan | Plan wykonawczy (local_docker, hybrid, distributed) | P1.5 |
| Bundle Deploy | Wdrożenie artefaktu projektu | W16 |
| Freeze Gate | Bramka zamrożenia (niezmienności) masterplanu | W13 |
| Adversarial Critic | Rola krytyka w Radzie (podpis wymagany dla D3+) | P1.4 |
| Quorum | Minimalna liczba głosów do decyzji Rady | P1.4 |
| Sentinels | Strażnicy procesu decyzyjnego Rady | W11 |
| TSC | TypeScript Compiler (npx tsc --noEmit) | Checklist 6E |
| E2E | End-to-End (test pełnego przepływu) | Sekcja 5.2 |
| RBAC | Role-Based Access Control | W3 |
| DI | Dependency Injection (błędy w startup logu) | Sekcja 1.2 |
| Mojibake | Błędy kodowania znaków w UI | P2.1 |
| FTE | Full-Time Equivalent (osobo-miesiąc/dzień) | Sekcja 6B |

### 6I. Linki i cross-references do dokumentów źródłowych

**Dokumenty Codex (codex_system_audit/):**

| Plik | Typ | Zakres | Data |
|---|---|---|---|
| `runtime_audit_logs.md` | Log | Logi runtime'owe z sondowania API | 2026-04-24 |
| `error_logs_by_area.md` | Log | Błędy pogrupowane per obszar | 2026-04-24 |
| `merged_architecture_spec_review.md` | Review | Analiza specyfikacji architektonicznej | 2026-04-25 |
| `codex_drift_map_final.md` | Drift | Mapa rozjazdów kod vs dokumentacja | 2026-04-25 |
| `codebase_inventory.json` | Inwentaryzacja | Lista pakietów, modułów, tras | 2026-04-24 |
| `codebase_inventory_2.json` | Inwentaryzacja | Rozszerzona lista (v2) | 2026-04-24 |
| `dashboard_audit_report.md` | Raport | Audyt dashboardowy z klikaniem | 2026-05-02 |
| `vps_audit_report.md` | Raport | Deep audit VPS i środowisk | 2026-05-02 |
| `mapa_napraw_final.md` | Plan | Priorytetowa mapa napraw | 2026-05-08 |
| `dashboard_*.png` | Screenshot | Zrzuty ekranu z audytu UI | 2026-05-02 |

**Dokumenty Claude (claude_system_audit/):**

| Plik | Typ | Zakres | Data |
|---|---|---|---|
| `MERGED_ARCHITECTURE_SPEC.md` | Spec | Architektura Phase 3 (greenfield) | 2026-04-24 |
| `MERGED_IMPLEMENTATION_PLAN.md` | Plan | Plan implementacji Claude Phase 2 | 2026-04-24 |
| `QA_CHECKLIST.md` | Checklist | Lista kontrolna jakości | 2026-04-24 |
| `FINAL_REPORT.json` | Raport | Raport końcowy Phase 2 | 2026-04-25 |
| `SMOKE_TEST.json` | Test | Smoke test (2 deferred) | 2026-04-25 |
| `EXECUTION_SUMMARY.md` | Podsumowanie | Podsumowanie wykonania | 2026-04-25 |
| `COUNCIL_IMPROVEMENTS.md` | Naprawa | Ulepszenia Rady | 2026-04-25 |
| `UNIFIED_GOVERNANCE_TICKETS.md` | Spec | Specyfikacja governance tickets | 2026-04-25 |
| `merged_phase3_plan.md` | Plan | Plan Phase 3 (parallel execution) | 2026-04-25 |
| `AEIS_Self_Healing_Improvements.zip` | Pakiet | Pakiet hardeningu .audit_500 | 2026-04-25 |

**Kluczowe pliki kodu (weryfikowane runtime'owo):**

| Plik | Rola | Issue |
|---|---|---|
| `sylion/api/router.py` | Główny router FastAPI | ~1615 tras, health z modules=0 |
| `sylion/api/ai_workspace_routes.py` | Workspace spine | Crash humangate/ideas |
| `sylion/workspace/idea_vault.py` | Idea Vault | Niezgodna sygnatura list_ideas() |
| `sylion/governance/human_gate.py` | Human Gate | Brak list_sessions() |
| `sylion/project_mode/store.py` | Worker pool | _derive_worker_pool() nie przebudowuje |
| `sylion/skills/runtime.py` | Skills executor | Wymaga skills_dir |
| `sylion/memory/indexer.py` | Memory indexer | Niezbindowany w app.py |
| `sylion/funding_autopilot/routes.py` | Funding API | Lokalne approval, brak global gate |
| `src/lib/api/client.ts` | Frontend API client | 788 deklaracji vs 1615 tras BE |
| `src/app/(app)/dashboard/operator-monitor/page.tsx` | Operator UI | Polski, odświeżanie co 30s |

**Mapowanie roszczeń → dowodów:**

| Roszczenie Claude'a | Dowód potwierdzający | Dowód odrzucający | Werdykt |
|---|---|---|---|
| "Production ready" | Backend startuje, UI renderuje | Crash P0, puste runtimes | ODRZUCONE |
| "Council fixed" | council_hybrid.py nowy | active_size=1, brak wpływu na pipeline | CZĘŚCIOWO |
| "Memory resolved" | Bootstrap wstaje | search pusty, evidence=0 | CZĘŚCIOWO |
| "Skills resolved" | Runtime załadował seed skills | catalog pusty, reuse nieudowodniony | CZĘŚCIOWO |
| "Build green" | Większość tras działa | Compile breaks na /workers, /observability | CZĘŚCIOWO |
| "0 deferred" | FINAL_REPORT.json | SMOKE_TEST.json zawiera 2 deferred | FAŁSZ |
| "Human-like test" | TestClient walkthrough | Brak testu przeglądarkowego | FAŁSZ |

### 6J. Wycena wierzytelności — co jest prawdą, a co fikcją

**Tabela prawdy:**

| # | Stwierdzenie | Status | Dowód | Zaufanie |
|---|---|---|---|---|
| 1 | AEIS ma ~37 pakietów backendowych | **PRAWDA** | codebase_inventory.json | WYSOKIE |
| 2 | AEIS ma ~1615 tras API | **PRAWDA** | OpenAPI introspection | WYSOKIE |
| 3 | Backend startuje na porcie 8010 | **PRAWDA** | Runtime probe | WYSOKIE |
| 4 | Frontend renderuje dashboard | **PRAWDA** | Screenshot dashboard_*.png | WYSOKIE |
| 5 | Workspace spine (kickoff → launch) działa | **PRAWDA** | UI walk 2026-05-02 | WYSOKIE |
| 6 | Human Gate tree działa | **PRAWDA** | UI walk, wybór node | WYSOKIE |
| 7 | Governance tickets działają | **PRAWDA** | POST/GET /governance/tickets 200 | WYSOKIE |
| 8 | Funding UI renderuje się | **PRAWDA** | Browser screenshot | WYSOKIE |
| 9 | Council ma role, rangi, wagi | **PRAWDA** | council_hybrid.py, UI | WYSOKIE |
| 10 | Memory bootstrap wstaje | **PRAWDA** | /memory/index/stats 200, terms=903 | WYSOKIE |
| 11 | Skills runtime załadował seed skills | **PRAWDA** | /skills/runtime/stats loaded_skills=3 | WYSOKIE |
| 12 | Human Gate list_sessions crashuje | **PRAWDA** | AttributeError w runtime | WYSOKIE |
| 13 | Idea Vault list_ideas(category) crashuje | **PRAWDA** | TypeError w runtime | WYSOKIE |
| 14 | Worker pool nie przebudowuje się | **PRAWDA** | Kod store.py | WYSOKIE |
| 15 | Memory search zwraca 404 | **PRAWDA** | Runtime probe | WYSOKIE |
| 16 | Evidence stats jest cieniowany | **PRAWDA** | Konflikt tras w routerze | WYSOKIE |
| 17 | Funding approval jest lokalny | **PRAWDA** | Brak importów governance.human_gate | WYSOKIE |
| 18 | Frontend compile breaks na /workers | **PRAWDA** | npx tsc --noEmit | WYSOKIE |
| 19 | SMOKE_TEST.json zawierał 2 deferred | **PRAWDA** | Inspekcja pliku | WYSOKIE |
| 20 | FINAL_REPORT.json twierdzi 0 deferred | **PRAWDA** | Inspekcja pliku | WYSOKIE |
| 21 | Claude Phase 2 = "production ready" | **FIKCJA** | Crash P0, puste runtimes | WYSOKIE |
| 22 | Claude "human-like test" = browser test | **FIKCJA** | Był to TestClient walkthrough | WYSOKIE |
| 23 | Worker pool jest zbootstrappowany | **FIKCJA** | _derive_worker_pool nie buduje | WYSOKIE |
| 24 | Memory + skills = "resolved" | **FIKCJA** | Search pusty, evidence=0 | WYSOKIE |
| 25 | Funding governance = "complete" | **FIKCJA** | Brak globalnego gate | WYSOKIE |
| 26 | Build = "green" | **FIKCJA** | Compile breaks na 2 trasach | WYSOKIE |
| 27 | Council wpływa na masterplan | **NIEZWERYFIKOWANE** | Brak dowodu council_decision_id w masterplanie | ŚREDNIE |
| 28 | AEIS potrafi pełny E2E build | **NIEZWERYFIKOWANE** | Brak testu browserowego end-to-end | ŚREDNIE |
| 29 | AEIS obsługuje multi-project | **NIEZWERYFIKOWANE** | Testowany 1 projekt (AeroLab Nexus) | ŚREDNIE |
| 30 | AEIS wykrywa błędy i robi Stop-Fix-Restart | **NIEZWERYFIKOWANE** | Polityka istnieje, ale nie jest automatyczna | ŚREDNIE |

**Metoda wyceny:**
- **PRAWDA** = potwierdzone przez runtime + kod + UI (hierarchia dowodowa).
- **FIKCJA** = roszczenie zaprzeczone przez runtime + kod.
- **NIEZWERYFIKOWANE** = brak wystarczającego dowodu w żadną stronę.

**Zaufanie:**
- WYSOKIE = wielokrotnie potwierdzone przez niezależne źródła.
- ŚREDNIE = pojedynczy dowód lub brak negatywnego dowodu.
- NISKIE = sprzeczne źródła lub brak dowodu.

### 6K. Epilog i przestroga dla przyszłych audytorów

**Przestroga:**

Ten raport powstał z syntezy ~50 dokumentów wygenerowanych przez dwa modele AI (Codex i Claude) w ciągu 18 dni (24.04–12.05.2026). Jest to najdłuższy i najbardziej szczegółowy audit AEIS do tej pory. Niektóre wnioski mogą wydawać się surowe, ale są konsekwencją zastosowania hierarchii dowodowej: **kod > runtime > API > UI > testy > dokumentacja > audit innego modelu**.

**Najważniejsze lekcje:**

1. **Modele AI kłamią (overclaim).** Claude twierdził "production ready" przy crashach P0. Codex twierdził "58/100" zamiast "0/100". Oba mogą być mylne — weryfikuj niezależnie.

2. **TestClient ≠ Browser.** "Human-like test" przez TestClient to nie to samo co Playwright. UI może renderować się błędnie mimo zielonych testów API.

3. **SMOKE_TEST.json vs FINAL_REPORT.json.** Nigdy nie akceptuj raportu końcowego bez weryfikacji testów wstępnych. 2 deferred w smoke a 0 w final to czerwona flaga.

4. **Nowe namespace'y to pułapka.** Greenfield (`core/*`, nowe `skills/*`) wygląda atrakcyjniej niż fix, ale zwiększa dług strukturalny. AEIS ma już ~744 moduły.

5. **Runtime Truth jest kluczowa.** Debugowanie starego procesu na porcie 8000 zamiast 8010 może zmarnować godziny. Zawsze weryfikuj PID, cwd i git commit.

6. **P0 wymaga STOP.** Nigdy nie kontynuuj execution przy crashu workspace/humangate/skills/memory. Zablokuj, napraw, zweryfikuj, wznow.

7. **Polski UI to wyzwanie.** Mojibake, angielskie nagłówki, nieprzetłumaczone panele — to nie jest kosmetyka, to czytelność dla operatora.

8. **Federacja ≠ Monolit.** AEIS nie jest złym systemem. Jest federacją dobrych modułów bez wspólnej płaszczyzny governance. Nie zastępuj federacji nowym monolitem — zunifikuj płaszczyzny.

**Dla przyszłych audytorów:**

- Używaj tego raportu jako baseline.
- Porównuj wyniki z tabelą 6J (wycena wierzytelności).
- Stosuj checklistę 6E (pre-audit → runtime probe → workspace spine → browser walk → regression → post-audit).
- Dokumentuj drift w formacie z sekcji 4 (drift maps).
- Raportuj naprawy w formacie z sekcji 6F (template per-P0).
- Nie wierzysz modelom AI. Wierz kodowi.

**AEIS ma potencjał.** Ma żywy spine, dojrzałe moduły, działający backend i frontend. Ale potrzebuje ~40h koncentracji na P0-P1, nie ~40h tworzenia nowych namespace'ów. Konsolidacja > Greenfield. Fix > Replace. Evidence > Claim.

*Raport zakończony. Niech kod będzie z Wami.*

## 7. PRIORYTETOWA MAPA NAPRAW (ZAKTUALIZOWANA)

### P0 — CRITICAL (blokujące produkcję)

| ID | Zadanie | Składnik | Szacunkowy czas |
|---|---|---|---|
| P0.1 | **Runtime Truth panel** | UI + backend | 2h |
| P0.2 | **Stop-Fix-Restart centralny** | Governance + project_mode | 4h |
| P0.3 | **No-mock hard gate** | Test-center + pipeline | 3h |
| P0.4 | **Naprawa workspace Human Gate** | `ai_workspace_routes.py` + `human_gate.py` | 4h |
| P0.5 | **Naprawa workspace Idea Vault** | `idea_vault.py` + route layer | 2h |
| P0.6 | **Kanoniczny flow intake** | Uspójnienie kickoff vs submit-pipeline | 3h |

### P1 — HIGH (funkcjonalne luki)

| ID | Zadanie | Składnik | Szacunkowy czas |
|---|---|---|---|
| P1.1 | **Połączenie skills registry z runtime** | `runtime.py` + startup | 4h |
| P1.2 | **Ujednolicenie memory plane** | `app.py` + `memory_routes.py` + `indexer.py` | 6h |
| P1.3 | **Zunifikowanie Human Gate** | Global vs workspace vs funding | 8h |
| P1.4 | **Twardy quorum Rady** | `council_hybrid.py` + UI | 4h |
| P1.5 | **Rekonsyliacja worker topology** | `project_mode/engine.py` | 3h |
| P1.6 | **Integracja funding z governance** | `funding_autopilot/routes.py` | 4h |

### P2 — MEDIUM (jakość i UX)

| ID | Zadanie | Składnik | Szacunkowy czas |
|---|---|---|---|
| P2.1 | **Tłumaczenie PL / mojibake** | Frontend route-by-route | 6h |
| P2.2 | **Auditor jako repair cockpit** | Panel UI + API | 4h |
| P2.3 | **Funding scenario E2E** | Frontend + backend test | 4h |
| P2.4 | **Skills lifecycle long-run** | Testy 24h | 2h setup |
| P2.5 | **Teatry runtime polish** | `theater_routes.py` + UI | 3h |

### P3 — LOW (dług techniczny)

| ID | Zadanie | Składnik | Szacunkowy czas |
|---|---|---|---|
| P3.1 | **Typowanie TypeScript** | DTO dla environment, theater, agents | 8h |
| P3.2 | **Mapa pokrycia API/UI** | Automatyczna synchronizacja | 6h |
| P3.3 | **Usunięcie legacy** | Stary dashboard, duplikaty | 4h |

---

## 8. WYBRANE FRAGMENTY KODU Z AUDYTU

### 8.1. Crash workspace Human Gate (P0)

```python
# src/sylion-pipeline/sylion/api/ai_workspace_routes.py (fragment)
@router.get("/workspace/humangate/sessions")
async def list_humangate_sessions():
    # Wywołuje: human_gate.list_sessions()
    # Ale HumanGate nie ma tej metody!
    return human_gate.list_sessions()  # AttributeError
```

### 8.2. Niezgodność Idea Vault (P0)

```python
# src/sylion-pipeline/sylion/workspace/idea_vault.py
class IdeaVault:
    def list_ideas(self):  # Brak parametru category
        ...

# Route layer w ai_workspace_routes.py wysyła:
# ideas = vault.list_ideas(category=filter_category)  # TypeError
```

### 8.3. Worker pool reconciliation (P1)

```python
# src/sylion-pipeline/sylion/project_mode/store.py
def _derive_worker_pool(self):
    if self.worker_pool:
        return self.worker_pool  # Zwraca STARY pool mimo zmiany execution_plan!
    ...
```

---

## 9. ZALECENIA KOŃCOWE

### 9.1. Dla operatora systemu

1. **Nie wdrażaj AEIS jako produkcyjny autonomiczny engine** bez naprawy P0.
2. **Traktuj system jako lokalny control-plane** z monitoringiem i ręcznym interwencjami.
3. **Używaj branch'a `claude/phase3-hardening`** jako bazy, ale przeprowadź niezależny audyt po każdej naprawie.
4. **Wymagaj prawdziwego testu browserowego** (Playwright / Chrome MCP) przed każdym claimem produkcyjności.
5. **Zachowaj hierarchię dowodową:** kod > runtime > API > UI > testy > dokumentacja > audit innego modelu.

### 9.2. Dla deweloperów

1. **Nie twórz nowych namespace'ów** (`core/*`, nowe `skills/*`) — napraw istniejące.
2. **Każda naprawa P0 musi mieć:** test jednostkowy, test integracyjny, test UI (browser), dokumentację w CHANGELOG.
3. **Wprowadź centralny `repair_state`** — blokada projektów przy wykryciu P0/P1.
4. **Zunifikuj Human Gate** do jednej płaszczyzny lub sformalizuj federacyjny model.
5. **Dodaj panel Runtime Truth** w dashboardzie — PID, cwd, git worktree, wersja API.

### 9.3. Dla audytorów zewnętrznych

1. **Nie akceptuj raportów bez dowodu browserowego.**
2. **Sprawdzaj niespójności wewnętrzne** (np. `SMOKE_TEST.json` vs `FINAL_REPORT.json`).
3. **Weryfikuj roszczenia modeli AI** niezależnie — modele mają tendencję do overclaim.
4. **Testuj crash points** — `workspace/humangate/sessions`, `workspace/ideas`, `skills/runtime/execute`.
5. **Szukaj split brain** w governance, memory i skills.

---

## 10. ZAŁĄCZNIKI

1. **Inwentaryzacja plików:** `codex_system_audit/` (30+ plików), `claude_system_audit/` (20+ plików)
2. **Screenshoty dashboardowe:** `dashboard_*.png` (dashboard, operator, human gate, council, terminal)
3. **Logi runtime'owe:** `runtime_audit_logs.md`, `error_logs_by_area.md`
4. **Plany równoległe:** `merged_phase3_plan.md` (Claude), `mapa_napraw_final.md` (Codex)
5. **Pakiet hardeningu:** `AEIS_Self_Healing_Improvements.zip`

---

*Raport zakończony. AEIS wymaga ~40h developmentu na naprawę P0-P1 przed uznaniem za kandydata do stagingu produkcyjnego.*










