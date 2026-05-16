# AEIS v6.2.0 — SZCZEGÓŁOWY PLAN NAPRAWCZY

**Data:** 2026-05-12  
**Wersja systemu:** v6.2.0 "Breakthrough"  
**Cel:** Doprowadzenie AEIS do production readiness  
**Szacowany całkowity czas:** 6-8 tygodni (~240-320h)  
**Zespół:** 5 agentów równoległych (A/B/K/D/E)

---

## METRYKA POSTĘPU

| Faza | Zadań | Szacowany czas | Status |
|------|-------|----------------|--------|
| Faza 0: Przygotowanie | 8 | 16h | ⏳ |
| Faza 1: P0 Blockers | 12 | 72h | ⏳ |
| Faza 2: P1 Integracje | 10 | 56h | ⏳ |
| Faza 3: P2 Rozszerzenia | 8 | 48h | ⏳ |
| Faza 4: P3 Higiena | 6 | 32h | ⏳ |
| Faza 5: Staging & Prod | 8 | 64h | ⏳ |
| **RAZEM** | **52** | **288h (~7 tyg.)** | ⏳ |

---

## FAZA 0: PRZYGOTOWANIE (16h)

**Cel:** Ustawienie środowiska, backup, narzędzia, podział pracy

### ZAD-000: Backup pełnego stanu systemu
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-000 |
| **Priorytet** | P0 |
| **Agent** | D (Integrator) |
| **Czas** | 2h |
| **Zależności** | Brak |
| **Opis** | Wykonanie pełnego backupu: sylion_aeis.db, sylion_dashboard.db, advisor_*.db, .env.generated, src/, operator-mobile/, configs/ |
| **Kroki** | 1. `cp sylion_aeis.db sylion_aeis.db.backup-$(date)` 2. `cp -r src/ src.backup/` 3. ZIP całości z CHECKSUMS.sha256 |
| **Kryteria akceptacji** | Backup zweryfikowany (SHA256), możliwy rollback w <5 min |
| **Ryzyka** | Brak miejsca na dysku — sprawdzić przed |

### ZAD-001: Setup środowiska dev dla 5 agentów
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-001 |
| **Priorytet** | P0 |
| **Agent** | D |
| **Czas** | 2h |
| **Zależności** | ZAD-000 |
| **Opis** | Przygotowanie 5 niezależnych worktree/git branches: `agent-a-governance`, `agent-b-adaptive`, `agent-k-surface`, `agent-d-integration`, `agent-e-watchdog` |
| **Kroki** | 1. `git worktree add ../agent-a agent-a-governance` 2. Skopiować .env.generated do każdego worktree 3. Skrypt `switch-to-agent.sh` |
| **Kryteria akceptacji** | Każdy agent może uruchomić backend+frontend niezależnie, build PASS |
| **Ryzyka** | Konflikty portów — użyć portów 8001-8005, 3001-3005 |

### ZAD-002: Inventory scan — klasyfikacja 1432 mocków
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-002 |
| **Priorytet** | P0 |
| **Agent** | K (Surface) |
| **Czas** | 4h |
| **Zależności** | ZAD-001 |
| **Opis** | Przeanalizować `_inventory_scan.json` i sklasyfikować każde z 1432 wystąpień mock/TODO/placeholder do kategorii: CRITICAL (blokuje flow), WARNING (zakłamuje dane), INFO (kosmetyczne) |
| **Kroki** | 1. Parsowanie `_inventory_scan.json` 2. Ręczna weryfikacja top 100 plików 3. Generowanie `MOCK_PRIORITY_MAP.json` |
| **Kryteria akceptacji** | Mapa z priorytetami per plik, CRITICAL ≤50, WARNING ≤200, INFO ≤1200 |
| **Ryzyka** | Subiektywna klasyfikacja — wymaga review przez Agenta D |

### ZAD-003: Standup 5 agentów — podział ownership
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-003 |
| **Priorytet** | P0 |
| **Agent** | D + Wszyscy |
| **Czas** | 2h |
| **Zależności** | ZAD-001, ZAD-002 |
| **Opis** | Spotkanie synchronizacyjne (async via `REQUESTS.md` + `PROGRESS_LEDGER.md`). Ustalenie zasad: 1 plik = 1 owner, HANDOFF protocol, STOP conditions |
| **Kroki** | 1. Aktualizacja `COORDINATION.md` 2. Podpisanie (wirtualne) `INTEGRATION_CONTRACTS.md` 3. Start `WATCHDOG_LOG.md` |
| **Kryteria akceptacji** | Każdy agent wie które namespace'y może edytować, zna protokół HANDOFF |
| **Ryzyka** | Niejednoznaczne granice między A a B przy Human Gate + Memory |

### ZAD-004: Setup test harness — CI lokalny
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-004 |
| **Priorytet** | P0 |
| **Agent** | D |
| **Czas** | 2h |
| **Zależności** | ZAD-001 |
| **Opis** | Skonfigurowanie lokalnego CI: pre-commit hooks (ruff, mypy, pytest), smoke testy (S1-S8), regression suite |
| **Kroki** | 1. `.pre-commit-config.yaml` 2. Skrypt `run-local-ci.sh` 3. Baseline testów: 100% obecnych testów PASS |
| **Kryteria akceptacji** | `run-local-ci.sh` wykonuje się w <10 min, zero regresji |
| **Ryzyka** | Niektóre testy baseline FAIL (test_retention_cascade.py, test_secure_cookies.py) — oznaczyć jako known issues |

### ZAD-005: Dokumentacja obecnego stanu ("As-Is")
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-005 |
| **Priorytet** | P1 |
| **Agent** | E (Watchdog) |
| **Czas** | 2h |
| **Zależności** | ZAD-003 |
| **Opis** | PIERWSZY cykl Watchdog: zrzut pełnego stanu systemu przed zmianami. 9 checków per cykl |
| **Kroki** | 1. Ownership check 2. Greenfield/stale check 3. Test regression check 4. Duplicate planes check 5. Reserved-for-D check 6. TODO-for-D growth check 7. Plan adherence check |
| **Kryteria akceptacji** | Raport `WATCHDOG_CYCLE_01.md` z 9/9 checków, baseline dla porównania |
| **Ryzyka** | Brak — read-only audit |

### ZAD-006: Definicja Definition of Done (DoD)
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-006 |
| **Priorytet** | P1 |
| **Agent** | D |
| **Czas** | 1h |
| **Zależności** | ZAD-003 |
| **Opis** | Spisanie wspólnych kryteriów ukończenia: testy, dokumentacja, evidence, review |
| **Kroki** | Aktualizacja `docs/CLAUDE_MASTERPLANS/MASTERPLAN.md` sekcja DoD |
| **Kryteria akceptacji** | Każdy zadanie w planie ma przypisane kryteria akceptacji |
| **Ryzyka** | Brak |

### ZAD-007: Przygotowanie test data / fixtures
| Pole | Wartość |
|------|---------|
| **ID** | ZAD-007 |
| **Priorytet** | P1 |
| **Agent** | B (Adaptive) |
| **Czas** | 1h |
| **Zależności** | ZAD-001 |
| **Opis** | Przygotowanie zestawu danych testowych: admin user, 3 projekty testowe, sample skills, council config |
| **Kroki** | 1. `scripts/seed_test_data.py` 2. Idempotent seed 3. Cleanup po testach |
| **Kryteria akceptacji** | `scripts/seed_test_data.py` tworzy pełny stan testowy w <30s |
| **Ryzyka** | Konflikt z B-002 build guard (pre-seeded DB) — użyć --force |

---

## FAZA 1: P0 BLOCKERS (72h)

**Cel:** Naprawa krytycznych roszczepień architektonicznych. Bez tego system nie może osiągnąć staging.

### P0-001: Konsolidacja Human Gate — canonical endpoint
| Pole | Wartość |
|------|---------|
| **ID** | P0-001 |
| **Priorytet** | P0 |
| **Agent** | A (Governance) |
| **Czas** | 8h |
| **Zależności** | ZAD-000, ZAD-001, ZAD-003 |
| **Opis** | Wybranie JEDNEGO canonical endpointu Human Gate. `workspace/humangate/sessions` jako master, pozostałe jako proxy/redirect |
| **Kroki** | 1. Analiza 3 ścieżek: `workspace/humangate/*`, `gates/human/*`, funding-local approval events 2. Refactor `sylion/governance/human_gate.py` 3. Global `gates/human/*` → redirect 301 do `workspace/humangate/*` 4. Funding-local → emit event do canonical 5. Aktualizacja frontendu (3 strony) 6. Testy: 15 scenariuszy Human Gate |
| **Kryteria akceptacji** | `POST /api/v1/workspace/humangate/sessions` tworzy sesję widoczną we WSZYSTKICH 3 ścieżkach. GET `gates/human/requests` zwraca te same dane co `workspace/humangate/sessions`. 0 duplikatów. |
| **Ryzyka** | Breaking change dla istniejących projektów — wymaga migration script |

### P0-002: Konsolidacja Human Gate — UI routing
| Pole | Wartość |
|------|---------|
| **ID** | P0-002 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 4h |
| **Zależności** | P0-001 |
| **Opis** | Aktualizacja frontendu: strony `/human-gate`, `/governance`, `/funding` używają TEGO SAMEGO komponentu Human Gate |
| **Kroki** | 1. Ekstrakcja wspólnego komponentu `<HumanGatePanel>` 2. Refactor `/human-gate/page.tsx` 3. Refactor `/governance/human-gate` (jeśli istnieje) 4. Refactor `/funding/approvals` 5. Uniform event handling |
| **Kryteria akceptacji** | 1 komponent UI, 3 strony, identyczne zachowanie, brak duplikacji kodu |
| **Ryzyka** | Różne formaty danych per ścieżka — wymaga normalizacji |

### P0-003: Unifikacja Memory Plane — globalny memory store
| Pole | Wartość |
|------|---------|
| **ID** | P0-003 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 8h |
| **Zależności** | ZAD-000, ZAD-001 |
| **Opis** | Uczyinienie memory subsystem startup-bound (lifecycle entrypoint), nie per-project. Globalny `memory_plane` zamiast per-project `runtime.sqlite` |
| **Kroki** | 1. Analiza `sylion/memory/` (indexer, retrieval, evidence_store, self_model_store) 2. Dodanie `memory_bootstrap()` do `lifespan()` w `app.py` 3. Refactor `memory_routes.py` — dodanie global scope 4. Migracja istniejących per-project memory do global 5. Aktualizacja `workspace` — memory binding 6. Testy: 10 scenariuszy memory |
| **Kryteria akceptacji** | `POST /api/v1/memory/index/sections` zapisuje do GLOBALNEJ bazy. `GET /api/v1/memory/index/search` przeszukuje wszystkie projekty. `/api/v1/memory/evidence/stats` działa bez konfliktu tras. |
| **Ryzyka** | Per-project isolation może być pożądana — rozwiązanie: namespace per project w global store |

### P0-004: Memory — frontend integration
| Pole | Wartość |
|------|---------|
| **ID** | P0-004 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 4h |
| **Zależności** | P0-003 |
| **Opis** | Podłączenie strony `/memory` do globalnego memory API. Aktualnie używa mock/bridge only |
| **Kroki** | 1. Refactor `src/app/(app)/memory/page.tsx` 2. Hook `useGlobalMemory()` 3. Integracja z `/api/v1/memory/index/search` 4. Evidence timeline z real data |
| **Kryteria akceptacji** | `/memory` wyświetla REALNE dane z globalnego memory. 0 mocków. |
| **Ryzyka** | Duża ilość danych — potrzebna paginacja i search |

### P0-005: Skills runtime — bootstrap i registry sync
| Pole | Wartość |
|------|---------|
| **ID** | P0-005 |
| **Priorytet** | P0 |
| **Agent** | B (Adaptive) |
| **Czas** | 10h |
| **Zależności** | ZAD-000, ZAD-001, ZAD-007 |
| **Opis** | Dopięcie skills executor do registry i filesystem. Obecnie `loaded_skills = 0` |
| **Kroki** | 1. Analiza `sylion/skills/registry.py` vs `sylion/skills/runtime.py` vs `sylion/skills/executor.py` 2. Implementacja `runtime.bootstrap()` w `lifespan()` 3. Scan katalogu `.agents/skills/` i `manifests/skills/` 4. Ładowanie skilli do pamięci (LRU cache) 5. Implementacja `execute_skill(name, payload)` 6. Test seed skills: `seed.echo`, `seed.summarize`, `seed.tokenize` 7. Testy: 20 scenariuszy |
| **Kryteria akceptacji** | `GET /api/v1/skills/runtime/stats` zwraca `loaded_skills >= 3` (seed). `POST /api/v1/skills/execute` z seed skill działa. Registry stats = Runtime stats. |
| **Ryzyka** | Skills mogą wymagać różnych środowisk (Python, JS, bash) — zacząć od Python-only |

### P0-006: Skills — frontend integration
| Pole | Wartość |
|------|---------|
| **ID** | P0-006 |
| **Priorytet** | P0 |
| **Agent** | B |
| **Czas** | 4h |
| **Zależności** | P0-005 |
| **Opis** | Strona `/skills` obecnie read-only. Włączenie wykonywania skilli z UI |
| **Kroki** | 1. Refactor `/skills/page.tsx` 2. Dodanie przycisku "Execute" per skill 3. Modal wykonania z payload 4. Polling wyniku 5. Evidence pack z wykonania |
| **Kryteria akceptacji** | Operator może wybrać skill, wpisać payload, wykonać, zobaczyć wynik i evidence. |
| **Ryzyka** | Długotrwałe skills mogą timeoutować — dodać async job + progress bar |

### P0-007: Reconciliation worker pool
| Pole | Wartość |
|------|---------|
| **ID** | P0-007 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 6h |
| **Zależności** | ZAD-000, ZAD-001 |
| **Opis** | Naprawa driftu między execution plan a worker pool w `project_mode`. Obecnie worker pool reconciliation ma bugi |
| **Kroki** | 1. Analiza `sylion/project_mode/engine.py` i `sylion/worker/registry.py` 2. Debug `worker_pool_count` vs `assignment_count` 3. Naprawa sync loop: `reconcile_assignments()` 4. Dodanie health check worker assignments 5. Testy: 10 scenariuszy |
| **Kryteria akceptacji** | `GET /api/v1/workers/assignments` zwraca spójne dane z `GET /api/v1/projects/{id}/orchestration`. Brak orphan assignments. |
| **Ryzyka** | Race condition przy concurrent updates — dodać RLock |

### P0-008: Unifikacja model registry vs council members
| Pole | Wartość |
|------|---------|
| **ID** | P0-008 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 8h |
| **Zależności** | ZAD-000, ZAD-001 |
| **Opis** | Workspace council members muszą brać skład z model registry truth plane, nie z hardcoded config |
| **Kroki** | 1. Analiza `sylion/aeis_v2/council/` vs `sylion/cognitive/model_registry.py` 2. Refactor `council_routes.py` — members z `model_registry` 3. Dodanie `council_mode` i `council_scale` z model registry 4. Walidacja: czy wybrany model jest w registry 5. Frontend: `/model-council` czyta z registry 6. Testy: 8 scenariuszy |
| **Kryteria akceptacji** | `GET /api/v1/council/sessions/{id}/members` zwraca modele z `model_registry`. Zmiana w registry propaguje się do council. |
| **Ryzyka** | Backward compatibility — stare sesje council mogą mieć usunięte modele |

### P0-009: Attach autonomy controller do spine
| Pole | Wartość |
|------|---------|
| **ID** | P0-009 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 6h |
| **Zależności** | P0-003, P0-005, P0-007, P0-008 |
| **Opis** | Autonomy controller obecnie siedzi na `observe`. Trzeba go podpiąć do realnego `workspace → project_mode` flow |
| **Kroki** | 1. Analiza `sylion/autonomy/` (stage machine A5) 2. Implementacja `autonomy_loop()` w tle 3. Decision points: D0-D5 per DIM-1..DIM-10 4. Integration z workspace launch 5. Auto-escalation do Human Gate gdy DIM > threshold 6. Testy: 10 scenariuszy |
| **Kryteria akceptacji** | Autonomy controller reaguje na workspace events. Dla DIM-8 (Deploy Auth) = L0 → zawsze Human Gate. Dla DIM-3 (Cost) = L2 → auto-approve <$1. |
| **Ryzyka** | Zbyt agresywna autonomia może spowodować niechciane akcje — default: Conservative preset |

### P0-010: Unified governance ticket (A1)
| Pole | Wartość |
|------|---------|
| **ID** | P0-010 |
| **Priorytet** | P0 |
| **Agent** | A |
| **Czas** | 4h |
| **Zależności** | P0-001, P0-003, P0-008 |
| **Opis** | Stworzenie jednolitego formatu governance ticketu używanego przez Human Gate, Council, Funding approvals, Security findings |
| **Kroki** | 1. Definicja `GovernanceTicket` schema (Pydantic) 2. Refactor `human_gate`, `council_sessions`, `funding_approvals`, `security_findings` 3. Central ticket store 4. Unified audit trail per ticket 5. Frontend: `/governance` pokazuje wszystkie tickety |
| **Kryteria akceptacji** | Jeden format ticketu, jeden store, jeden audit trail. Tickety z funding, security, human gate widoczne w `/governance`. |
| **Ryzyka** | Różne pola wymagane per typ — użyć polimorficznego schema |

### P0-011: Fix CORS na /budget i /costs
| Pole | Wartość |
|------|---------|
| **ID** | P0-011 |
| **Priorytet** | P0 |
| **Agent** | K (Surface) |
| **Czas** | 2h |
| **Zależności** | ZAD-000, ZAD-001 |
| **Opis** | Naprawa CORS policy block na `/api/v1/monitoring/budget/*` i `/api/v1/monitoring/costs/*` |
| **Kroki** | 1. Analiza `sylion/api/metrics_v2_routes.py` i CORS config 2. Dodanie `budget` i `costs` do `allow_origin_regex` lub explicit whitelist 3. Weryfikacja `SYLION_METRICS_BEARER` 4. Testy Playwright: 4 scenariusze |
| **Kryteria akceptacji** | Playwright PASS na `/budget` i `/costs`. Brak błędów CORS w konsoli. |
| **Ryzyka** | Może otworzyć metrics dla nieautoryzowanych — wymaga weryfikacji auth |

### P0-012: WebSocket `/ws/workspace` fix
| Pole | Wartość |
|------|---------|
| **ID** | P0-012 |
| **Priorytet** | P0 |
| **Agent** | K |
| **Czas** | 2h |
| **Zależności** | ZAD-000, ZAD-001 |
| **Opis** | Naprawa warningu WebSocket na stronie `/workspace` |
| **Kroki** | 1. Analiza `sylion/api/ws_routes.py` 2. Fix reconnect logic 3. Graceful degradation gdy backend offline 4. Test smoke: `/workspace` WebSocket connect |
| **Kryteria akceptacji** | Smoke test `/workspace` WebSocket: CONNECTED, 0 warnings. `BackendOfflineGuard` działa poprawnie. |
| **Ryzyka** | Może wymagać zmiany timeoutów — niektóre sieci mają długi RTT |

---

## FAZA 2: P1 INTEGRACJE (56h)

**Cel:** Połączenie istniejących warstw w jeden spine. Zależy od Fazy 1.

### P1-001: Memory bootstrap + route shadow fix (RB-003, RB-016)
| Pole | Wartość |
|------|---------|
| **ID** | P1-001 |
| **Priorytet** | P1 |
| **Agent** | B (Adaptive) |
| **Czas** | 6h |
| **Zależności** | P0-003, P0-004 |
| **Opis** | Startup memory binding + naprawa shadow routes (konflikt tras) |
| **Kroki** | 1. `memory_bootstrap()` w `lifespan()` 2. Fix `/api/v1/memory/evidence/stats` (konflikt z inną trasą) 3. Memory health check w `/health` 4. Testy: 8 scenariuszy |
| **Kryteria akceptacji** | `/health` zwraca `memory_status: ok`. Brak warningów o konflikcie tras w startup. |
| **Ryzyka** | Memory może być wolny przy dużych datasetach — dodać lazy loading |

### P1-002: Mobile bridge — backend
| Pole | Wartość |
|------|---------|
| **ID** | P1-002 |
| **Priorytet** | P1 |
| **Agent** | B |
| **Czas** | 8h |
| **Zależności** | P0-001, P0-003, ZAD-007 |
| **Opis** | Implementacja mobile gateway w głównym backendzie. Obecnie 11 endpointów `/mobile/v1/*` ale JWT stub (Etap 1) |
| **Kroki** | 1. Analiza `sylion/operator_mobile/` (5 plików) 2. Implementacja prawdziwego JWT verify (zamiast `decode_token_unverified`) 3. Biometric step-up D3+ 4. Push notifications (FCM) 5. Queue sync z desktop 6. Testy: 12 scenariuszy |
| **Kryteria akceptacji** | `POST /api/v1/mobile/v1/auth/login` weryfikuje JWT. `GET /api/v1/mobile/v1/queue` zwraca realną kolejkę. Biometric wymagane dla D3+. |
| **Ryzyka** | Mobile gateway wymaga mTLS/VPN — dodać wymaganie w docs |

### P1-003: Mobile bridge — frontend
| Pole | Wartość |
|------|---------|
| **ID** | P1-003 |
| **Priorytet** | P1 |
| **Agent** | B |
| **Czas** | 6h |
| **Zależności** | P1-002 |
| **Opis** | Podłączenie stron `/operator-mobile` do realnego mobile API |
| **Kroki** | 1. Refactor `/operator-mobile/page.tsx` 2. Hooki `_mobile.ts`: `useOperatorId`, `useOperatorMobileQueue`, `useOperatorMobileDevices` 3. Realne API calls zamiast mock 4. QR pairing 5. Testy: 8 scenariuszy |
| **Kryteria akceptacji** | `/operator-mobile/queue` wyświetla REALNE tickety. `/operator-mobile/devices` pokazuje zbindowane urządzenia. QR pairing działa. |
| **Ryzyka** | Wymaga uruchomionej aplikacji mobilnej — użyć emulatora w testach |

### P1-004: Operator Mobile surface
| Pole | Wartość |
|------|---------|
| **ID** | P1-004 |
| **Priorytet** | P1 |
| **Agent** | B |
| **Czas** | 6h |
| **Zależności** | P1-002, P1-003 |
| **Opis** | Dokończenie UI mobilnego: notyfikacje push, offline mode, sync z desktop |
| **Kroki** | 1. Push notification handler 2. Offline queue (dane zapisywane lokalnie, sync przy reconnect) 3. Biometric prompt 4. Deep linking (ticket → app) 5. Testy: 6 scenariuszy |
| **Kryteria akceptacji** | Push notification o Human Gate otwiera app na odpowiednim tickiecie. Offline: dane zapisane, sync po reconnect. |
| **Ryzyka** | iOS push wymaga certyfikatów Apple — przygotować dummy cert dla dev |

### P1-005: LLM quality fixes (FIX-016/17/23)
| Pole | Wartość |
|------|---------|
| **ID** | P1-005 |
| **Priorytet** | P1 |
| **Agent** | A |
| **Czas** | 6h |
| **Zależności** | P0-005, P0-008 |
| **Opis** | Naprawa jakości odpowiedzi LLM: prompt templates, temperature tuning, context window optimization |
| **Kroki** | 1. Analiza `sylion/cognitive/llm_adapter.py` i `sylion/aeis/advisor/engine/llm_judge/` 2. Update prompt templates per model capability 3. Temperature tuning: reasoning=0.2, creative=0.7 4. Context window trimming (token counting) 5. Anti-hallucination guards 6. Benchmark: 20 test prompts |
| **Kryteria akceptacji** | Benchmark: ≥80% responses rated "good" przez Critic. Anti-hallucination log: <5% false claims. |
| **Ryzyka** | Różne modele mają różne formaty promptów — wymaga per-model templates |

### P1-006: Prometheus metrics dedup (FIX-220)
| Pole | Wartość |
|------|---------|
| **ID** | P1-006 |
| **Priorytet** | P1 |
| **Agent** | K |
| **Czas** | 4h |
| **Zależności** | ZAD-000 |
| **Opis** | Usunięcie duplikacji metryk Prometheus. Obecnie 4 źródła emityją te same metryki |
| **Kroki** | 1. Analiza `sylion/monitoring/metrics_*.py` 2. Centralny `MetricsEmitter` singleton 3. Deduplikacja labeli 4. Refactor istniejących emitterów 5. Testy: 6 scenariuszy |
| **Kryteria akceptacji** | `GET /api/metrics/prom` zwraca unikalne metryki. Brak duplikatów. Grafana dashboardy poprawne. |
| **Ryzyka** | Może zepsuć istniejące dashboardy Grafana — wymaga aktualizacji queries |

### P1-007: Decomposition Engine
| Pole | Wartość |
|------|---------|
| **ID** | P1-007 |
| **Priorytet** | P1 |
| **Agent** | A |
| **Czas** | 12h |
| **Zależności** | P0-005, P0-008, P0-009, P1-005 |
| **Opis** | Implementacja `POST /api/v1/aeis/decompose` — LLM-based decomposition Księgi na warstwy/moduły |
| **Kroki** | 1. Analiza istniejącego rule-based fallback 2. Implementacja LLM-based decomposition (Claude/GPT) 3. Input: canonical_book (markdown) 4. Output: layer/module decomposition JSON 5. Walidacja: brak cykli, pokrycie 100% 6. Cache (memoization per book hash) 7. Testy: 10 scenariuszy |
| **Kryteria akceptacji** | `POST /api/v1/aeis/decompose` zwraca valid JSON z warstwami i modułami. Test z Customer Y CRM: pokrycie 100% wymagań. Cache hit: <100ms. |
| **Ryzyka** | Koszt LLM per decomposition (~$0.50-$2.00) — wymaga budget check |

### P1-008: Frontend — eliminacja CRITICAL mocków
| Pole | Wartość |
|------|---------|
| **ID** | P1-008 |
| **Priorytet** | P1 |
| **Agent** | K |
| **Czas** | 6h |
| **Zależności** | ZAD-002, P0-001, P0-003, P0-005, P0-007 |
| **Opis** | Podłączenie TOP 20 stron frontendu do realnego API (zamiast mock). Fokus na: `/advisor`, `/projects`, `/funding`, `/governance`, `/skills`, `/memory`, `/test-center` |
| **Kroki** | 1. Z `MOCK_PRIORITY_MAP.json` wybrać CRITICAL (≤50) 2. Per strona: refactor z mock → real API hooks 3. Loading states, error handling 4. Empty states 5. Smoke test per strona |
| **Kryteria akceptacji** | 20 stron wyświetla REALNE dane. 0 CRITICAL mocków. Playwright smoke: 20/20 PASS. |
| **Ryzyka** | Backend może nie mieć danych (pusta baza) — wymaga seed data |

### P1-009: Security deduplication
| Pole | Wartość |
|------|---------|
| **ID** | P1-009 |
| **Priorytet** | P1 |
| **Agent** | K |
| **Czas** | 4h |
| **Zależności** | ZAD-000 |
| **Opis** | Połączenie 4 auditów w 1 i 2 key vaultów w 1 |
| **Kroki** | 1. Analiza `sylion/security/audit*.py` — 4 pliki 2. Ekstrakcja wspólnego `SecurityAuditor` 3. Merge `sylion_key_vault.db` + `advisor_preferences.db` (tylko security keys) 4. Refactor routes 5. Testy: 8 scenariuszy |
| **Kryteria akceptacji** | Jeden plik `security_audit.py`. Jeden vault. 0 regresji w testach bezpieczeństwa. |
| **Ryzyka** | Merge vaultów może uszkodzić istniejące klucze — wymaga backupu |

### P1-010: Council — frontend integration
| Pole | Wartość |
|------|---------|
| **ID** | P1-010 |
| **Priorytet** | P1 |
| **Agent** | A |
| **Czas** | 4h |
| **Zależności** | P0-008, P0-010 |
| **Opis** | Strona `/governance` generuje syntetyczne voteHistory. Trzeba podpiąć do realnego backendu |
| **Kroki** | 1. Refactor `/governance/page.tsx` 2. Realne `GET /api/v1/governance/proposals/{id}/votes` 3. CircularScore z real data 4. Live voting updates (WebSocket) 5. Testy: 6 scenariuszy |
| **Kryteria akceptacji** | `/governance` pokazuje REALNE proposals, votes, policies. WebSocket push na nowy vote. |
| **Ryzyka** | Duża ilość danych przy dużej Radzie — paginacja |

---

## FAZA 3: P2 ROZSZERZENIA (48h)

**Cel:** Funkcjonalności dodające wartość. Zależy od Faz 1+2.

### P2-001: Funding program scanner (FIX-100)
| Pole | Wartość |
|------|---------|
| **ID** | P2-001 |
| **Priorytet** | P2 |
| **Agent** | K |
| **Czas** | 8h |
| **Zależności** | P1-008 |
| **Opis** | Automatyczne skanowanie portali grantowych (EU, PL) i aktualizacja calls/programmes w systemie |
| **Kroki** | 1. Crawler/Selenium dla portalu grantowego 2. Parser HTML → structured data 3. Dedup z istniejącymi calls 4. Auto-create `Idea` z match score 5. Notification do operatora 6. Scheduler (cron: daily) |
| **Kryteria akceptacji** | Dziennie ≥1 nowy call dodany (w sezonie). Match score ≥70%. 0 duplikatów. |
| **Ryzyka** | Portale zmieniają strukturę HTML — wymaga maintenance |

### P2-002: Browser automation grant portals (FIX-103)
| Pole | Wartość |
|------|---------|
| **ID** | P2-002 |
| **Priorytet** | P2 |
| **Agent** | K |
| **Czas** | 8h |
| **Zależności** | P2-001 |
| **Opis** | Auto-wypełnianie formularzy grantowych na portalach zewnętrznych |
| **Kroki** | 1. Selenium/Playwright browser automation 2. Template per portal (NCBR, Horizon, FSTR) 3. Auto-fill z danych firmy (z `company_profiles`) 4. Operator review przed submit 5. Evidence pack z auto-fill 6. Testy: 6 scenariuszy |
| **Kryteria akceptacji** | Formularz grantowy wypełniony w <5 min. Operator tylko review i klik submit. Evidence pack zawiera screenshoty. |
| **Ryzyka** | Loginy do portali — wymaga credentials w vault |

### P2-003: Grant reporting (FIX-106)
| Pole | Wartość |
|------|---------|
| **ID** | P2-003 |
| **Priorytet** | P2 |
| **Agent** | K |
| **Czas** | 6h |
| **Zależności** | P2-001 |
| **Opis** | Generowanie raportów post-execution dla grantodawców |
| **Kroki** | 1. Template raportu per grantodawca 2. Auto-ekstrakcja metryk z systemu (koszt, czas, wyniki) 3. PDF generation 4. Polish language 5. Email dispatch 6. Testy: 4 scenariusze |
| **Kryteria akceptacji** | Raport PDF generowany w <2 min. Zawiera wszystkie wymagane sekcje. Po polsku. |
| **Ryzyka** | Różni grantodawcy mają różne wymagania — zacząć od TOP 3 |

### P2-004: Mobile app runtime integration
| Pole | Wartość |
|------|---------|
| **ID** | P2-004 |
| **Priorytet** | P2 |
| **Agent** | B |
| **Czas** | 8h |
| **Zależności** | P1-002, P1-003, P1-004 |
| **Opis** | Integracja aplikacji mobilnej KMM z głównym runtime AEIS |
| **Kroki** | 1. Shared module: `AuthRepository` → real API 2. `CardRepository` → advisor cards 3. `ProjectRepository` → projects list 4. `PushRepository` → FCM + backend push 5. Android: `HomeScreen` z real data 6. iOS: `ContentView` z real data 7. Testy: 10 scenariuszy |
| **Kryteria akceptacji** | Aplikacja mobilna wyświetla realne projekty, karty, kolejkę. Push działa. Biometric działa. |
| **Ryzyka** | KMM może mieć problemy z serialization — testować na real devices |

### P2-005: Demo projects — real execution (E11)
| Pole | Wartość |
|------|---------|
| **ID** | P2-005 |
| **Priorytet** | P2 |
| **Agent** | B |
| **Czas** | 6h |
| **Zależności** | P1-007, P2-004 |
| **Opis** | Uruchomienie 6 projektów demo z REALNĄ deliberacją i buildem (nie stub) |
| **Kroki** | 1. `DemoProjectOrchestrator` — refactor z stub → real 2. Per demo: CRM, factory, funding, marketplace, mobile_inspector, skills_marketplace 3. Real council deliberation 4. Real build (min. 1 phase) 5. Evidence packs 6. Testy: 6 scenariuszy |
| **Kryteria akceptacji** | Każdy demo ma realny council session, realną Księgę, realny build artifact. |
| **Ryzyka** | Koszt LLM per demo (~$5-20) — limitować liczbę rund deliberacji |

### P2-006: Agent Theater Dashboard (E12)
| Pole | Wartość |
|------|---------|
| **ID** | P2-006 |
| **Priorytet** | P2 |
| **Agent** | K |
| **Czas** | 4h |
| **Zależności** | P0-005, P0-008, P0-009 |
| **Opis** | Dashboard zespołu agentów — live status, topology, guardians |
| **Kroki** | 1. `AgentTheaterAggregator` — read-only 2. 6 REST endpointów (`/api/v1/agent-theater/*`) 3. Topology viz 4. Guardian status (13) 5. Local models status 6. Auto-refresh 5s 7. Frontend: `/orchestration/teams` |
| **Kryteria akceptacji** | `/orchestration/teams` pokazuje live status wszystkich agentów. Auto-refresh. |
| **Ryzyka** | Duża liczba agentów może spowolnić UI — paginacja/filtering |

### P2-007: Long-horizon memory (Obsidian-backed)
| Pole | Wartość |
|------|---------|
| **ID** | P2-007 |
| **Priorytet** | P2 |
| **Agent** | B |
| **Czas** | 4h |
| **Zależności** | P1-001 |
| **Opis** | Integracja z Obsidian dla długoterminowej pamięci i learning workflow |
| **Kroki** | 1. Obsidian API connector 2. Sync: project notes → Obsidian vault 3. Backlinks: related projects 4. Graph view 5. Auto-tagging 6. Testy: 4 scenariusze |
| **Kryteria akceptacji** | Projekt zamknięty automatycznie syncuje się do Obsidian. Graph pokazuje powiązania. |
| **Ryzyka** | Obsidian vault może być duży — wymaga selektywnego sync |

### P2-008: Polish localization sweep
| Pole | Wartość |
|------|---------|
| **ID** | P2-008 |
| **Priorytet** | P2 |
| **Agent** | K |
| **Czas** | 4h |
| **Zależności** | P1-008 |
| **Opis** | Pełna lokalizacja UI na polski (labels, komunikaty, emaile) |
| **Kroki** | 1. Ekstrakcja wszystkich stringów UI 2. Tłumaczenie (manualne + LLM-assisted) 3. i18n keys 4. Fallback en 5. Testy: visual regression |
| **Kryteria akceptacji** | 100% polskich labels. Emaile po polsku. Brak mixed language. |
| **Ryzyka** | Niektóre terminy techniczne nie mają dobrego polskiego odpowiednika — zostawić angielskie |

---

## FAZA 4: P3 HIGIENA (32h)

**Cel:** Czyszczenie kodu, dokumentacja, finalne poprawki.

### P3-001: Dead code cleanup
| Pole | Wartość |
|------|---------|
| **ID** | P3-001 |
| **Priorytet** | P3 |
| **Agent** | K |
| **Czas** | 8h |
| **Zależności** | P1-008, P2-008 |
| **Opis** | Usunięcie martwego kodu: nieużywane funkcje, importy, pliki, zmienne |
| **Kroki** | 1. `vulture` / `pylint --disable-all --enable=unused-import` 2. Manual review top 50 plików 3. Usunięcie legacy dashboard routes (jeśli confirmed deprecated) 4. Usunięcie mock files 5. Refactor duplikatów 6. Testy: regression suite |
| **Kryteria akceptacji** | ≥20% redukcja linii kodu martwego. 0 regresji. Coverage nie spada. |
| **Ryzyka** | Można usunąć kod używany pośrednio (via reflection) — wymaga careful review |

### P3-002: Usunięcie legacy dashboard
| Pole | Wartość |
|------|---------|
| **ID** | P3-002 |
| **Priorytet** | P3 |
| **Agent** | K |
| **Czas** | 4h |
| **Zależności** | P1-008, P3-001 |
| **Opis** | Ostateczne usunięcie `src/sylion-pipeline/dashboard/` (DEPRECATED od 2026-04-24) |
| **Kroki** | 1. Backup `dashboard/` 2. Usunięcie katalogu 3. Usunięcie importów w `app.py` 4. Usunięcie `sylion_dashboard.db` references 5. Aktualizacja `docker-compose.yml` 6. Testy: smoke |
| **Kryteria akceptacji** | Brak katalogu `dashboard/`. Brak referencji w kodzie. Smoke test PASS. |
| **Ryzyka** | Niektóre testy mogą testować legacy dashboard — sprawdzić przed usunięciem |

### P3-003: FIX-100/103/106 reporting polish
| Pole | Wartość |
|------|---------|
| **ID** | P3-003 |
| **Priorytet** | P3 |
| **Agent** | K |
| **Czas** | 6h |
| **Zależności** | P2-001, P2-002, P2-003 |
| **Opis** | Dopracowanie UI raportowania funding: wykresy, eksporty, notyfikacje |
| **Kroki** | 1. Refactor `/funding` strona 2. Charts (Recharts): funding pipeline, success rate, ROI 3. Export: PDF, CSV, XLSX 4. Email notifications 5. Mobile responsive 6. Testy: visual regression |
| **Kryteria akceptacji** | `/funding` ma wykresy, eksporty, jest mobile-friendly. |
| **Ryzyka** | Brak |

### P3-004: Documentation update
| Pole | Wartość |
|------|---------|
| **ID** | P3-004 |
| **Priorytet** | P3 |
| **Agent** | D |
| **Czas** | 6h |
| **Zależności** | Wszystkie powyższe |
| **Opis** | Aktualizacja dokumentacji: 51 plików modułowych, instrukcja obsługi, API reference |
| **Kroki** | 1. Przegląd 51 plików `docs/dokumentacja/` 2. Aktualizacja statusów (Draft→Sprint3→Done) 3. Aktualizacja zależności 4. Nowe API endpoints 5. Frontend surfaces update 6. `AEIS_SYSTEM_BOOK_2026.md` — final version |
| **Kryteria akceptacji** | Dokumentacja zgodna z kodem. Brak rozjazdów >5%. |
| **Ryzyka** | Dokumentacja szybko się dezaktualizuje — wymaga CI check |

### P3-005: Test coverage ≥80%
| Pole | Wartość |
|------|---------|
| **ID** | P3-005 |
| **Priorytet** | P3 |
| **Agent** | D |
| **Czas** | 4h |
| **Zależności** | Wszystkie powyższe |
| **Opis** | Podniesienie test coverage z 75% do 80% |
| **Kroki** | 1. `pytest --cov` 2. Identyfikacja brakujących testów 3. Dodanie testów dla nowych funkcji 4. Dodanie testów dla edge cases 5. CI update: threshold 80% |
| **Kryteria akceptacji** | `pytest --cov` ≥80%. CI green. |
| **Ryzyka** | Niektóre ścieżki trudne do testowania (LLM calls) — użyć mock |

### P3-006: Final security scan
| Pole | Wartość |
|------|---------|
| **ID** | P3-006 |
| **Priorytet** | P3 |
| **Agent** | D + E |
| **Czas** | 4h |
| **Zależności** | Wszystkie powyższe |
| **Opis** | Finalny skan bezpieczeństwa przed staging |
| **Kroki** | 1. `bandit -r src/sylion-pipeline/sylion/` 2. `pip-audit` 3. `trivy fs .` 4. `gitleaks detect` 5. OWASP ZAP quick scan 6. Raport: 0 critical, 0 high |
| **Kryteria akceptacji** | 0 critical, 0 high vulnerabilities. Raport w `evidence/security_final_scan.md`. |
| **Ryzyka** | Może wykryć nowe CVE w dependencies — wymaga patch |

---

## FAZA 5: STAGING & PRODUCTION (64h)

**Cel:** Wdrożenie na staging, testy, production hardening.

### S5-001: Staging deployment
| Pole | Wartość |
|------|---------|
| **ID** | S5-001 |
| **Priorytet** | P0 |
| **Agent** | D |
| **Czas** | 8h |
| **Zależności** | Wszystkie powyższe |
| **Opis** | Wdrożenie na środowisko staging (Hetzner Host B) |
| **Kroki** | 1. `scripts/hetzner_provision_host_b.py` 2. Deploy: `AEIS.exe` lub Docker 3. PostgreSQL setup 4. Redis setup 5. SSL/TLS (Caddy/Let's Encrypt) 6. Smoke test z zewnętrznego IP |
| **Kryteria akceptacji** | `https://staging.sylion.io/health` → ok. Wszystkie 52 testy PASS. |
| **Ryzyka** | Firewall, DNS propagation — rezerwa 24h |

### S5-002: Staging test suite (S1-S8)
| Pole | Wartość |
|------|---------|
| **ID** | S5-002 |
| **Priorytet** | P0 |
| **Agent** | D + E |
| **Czas** | 8h |
| **Zależności** | S5-001 |
| **Opis** | Pełna kampania testów integracyjnych na staging |
| **Kroki** | S1: Auth flow, S2: Project lifecycle, S3: Council deliberation, S4: Build execution, S5: Quality gates, S6: Funding flow, S7: Mobile sync, S8: Observability + alerts |
| **Kryteria akceptacji** | 8/8 scenarios PASS. Raport w `evidence/staging_s1_s8.md`. |
| **Ryzyka** | Timeouty przy wolnych połączeniach — zwiększyć timeouty |

### S5-003: Performance test (p95 <500ms)
| Pole | Wartość |
|------|---------|
| **ID** | S5-003 |
| **Priorytet** | P1 |
| **Agent** | D |
| **Czas** | 4h |
| **Zależności** | S5-001 |
| **Opis** | Locust performance test na staging |
| **Kroki** | 1. `tests/perf/locustfile.py` 2. 100 users → ≥250 RPS 3. 500 users → ≥1000 RPS 4. p95 <500ms 5. Memory <512MB 6. CPU <80% |
| **Kryteria akceptacji** | SLOs spełnione. Raport w `evidence/perf_baseline_staging.md`. |
| **Ryzyka** | SQLite może być wąskim gardłem — użyć PostgreSQL |

### S5-004: Load test (1000 users)
| Pole | Wartość |
|------|---------|
| **ID** | S5-004 |
| **Priorytet** | P1 |
| **Agent** | D |
| **Czas** | 4h |
| **Zależności** | S5-003 |
| **Opis** | Load test 1000 concurrent users |
| **Kroki** | 1. Locust 1000 users 2. Duration 1h 3. Monitor: CPU, memory, DB connections, Redis 4. Auto-scaling test 5. Raport |
| **Kryteria akceptacji** | 0 crashów. Error rate <0.1%. p99 <2000ms. |
| **Ryzyka** | Może wymagać vertical scaling — Hetzner cx23 może być za słaby |

### S5-005: DR test (disaster recovery)
| Pole | Wartość |
|------|---------|
| **ID** | S5-005 |
| **Priorytet** | P1 |
| **Agent** | D |
| **Czas** | 4h |
| **Zależności** | S5-001 |
| **Opis** | Symulacja awarii i przywracania z backupu |
| **Kroki** | 1. Symulacja crash DB 2. Restore z pg_dump 3. RTO test: <4h 4. RPO test: <1h data loss 5. Smoke test post-restore |
| **Kryteria akceptacji** | RTO ≤4h, RPO ≤1h. Smoke S1-S8 PASS po restore. |
| **Ryzyka** | Backup może być uszkodzony — wymaga regularnych testów restore |

### S5-006: Security hardening
| Pole | Wartość |
|------|---------|
| **ID** | S5-006 |
| **Priorytet** | P0 |
| **Agent** | D + E |
| **Czas** | 8h |
| **Zależności** | S5-001 |
| **Opis** | Production hardening: mTLS, strict auth, RBAC włączone, secrets rotation |
| **Kroki** | 1. `SYLION_AUTH_BYPASS=0` 2. `SYLION_RBAC_DISABLED=0` 3. `SYLION_ENV=production` 4. mTLS internal 5. External IdP / OIDC 6. Secrets rotation 7. Rate limiting strict 8. HSTS, CSP, X-Frame-Options 9. Audit log shipping |
| **Kryteria akceptacji** | `GET /health` zwraca `env: production`. Auth wymagany na wszystkich endpointach (poza public). RBAC enforced. |
| **Ryzyka** | Może zablokować operatora — wymaga emergency access procedure |

### S5-007: Production deploy
| Pole | Wartość |
|------|---------|
| **ID** | S5-007 |
| **Priorytet** | P0 |
| **Agent** | D |
| **Czas** | 8h |
| **Zależności** | S5-002, S5-003, S5-004, S5-005, S5-006 |
| **Opis** | Wdrożenie produkcyjne z canary deployment |
| **Kroki** | 1. Canary 5% → 25% → 50% → 100% 2. Rollback plan (hot standby) 3. Monitoring: error rate, latency, CPU, memory 4. Auto-rollback triggers 5. 24h observation 6. Final sign-off |
| **Kryteria akceptacji** | 24h stable. Error rate <0.1%. p95 <500ms. Operator sign-off. |
| **Ryzyka** | Produkcja to production — wymaga osoby na standby |

### S5-008: Post-deploy calibration
| Pole | Wartość |
|------|---------|
| **ID** | S5-008 |
| **Priorytet** | P1 |
| **Agent** | D + E |
| **Czas** | 4h |
| **Zależności** | S5-007 |
| **Opis** | Kalibracja: predicted vs actual (koszt, czas, productivity) |
| **Kroki** | 1. Ekstrakcja metryk z produkcji 2. Porównanie z pre-flight estimates 3. Update cost models 4. Update worker productivity baselines 5. Update council efficiency models 6. Raport kalibracyjny |
| **Kryteria akceptacji** | Kalibracyjny raport w `evidence/calibration_prod_001.md`. Deviation <20%. |
| **Ryzyka** | Brak |

---

## HARMONOGRAM GANTT (7 tygodni)

```
Tydzień 1: [ZZZZZZZZ] Faza 0 (Przygotowanie) — D + K
Tydzień 1-2: [RRRRRRRRRRRRRRRR] Faza 1 (P0 Blockers) — A + B
Tydzień 2-3: [IIIIIIIIIIII] Faza 2 (P1 Integracje) — A + B + K
Tydzień 3-4: [EEEEEEEEEEEE] Faza 3 (P2 Rozszerzenia) — K + B
Tydzień 4-5: [HHHHHHHH] Faza 4 (P3 Higiena) — K + D
Tydzień 5-6: [SSSSSSSSSSSS] Faza 5 (Staging) — D + E
Tydzień 6-7: [PPPPPPPP] Faza 5 (Production) — D + E
Tydzień 7: [CCCC] Post-deploy + Calibration — D + E

Legenda: Z=Faza0, R=Faza1, I=Faza2, E=Faza3, H=Faza4, S=Staging, P=Production, C=Calibration

Watchdog (E): WWWWWW WWWWWW WWWWWW WWWWWW WWWWWW WWWWWW WWWWWW (daily cycles)
```

---

## PROTOKÓŁ HANDOFF

### Handoff A → D (Governance → Integrator)
**Trigger:** P0-001..P0-012 PASS
**Deliverables:**
- Raport: `docs/claude_system_audit/AGENT_A_HANDOFF.md`
- Lista plików zmienionych (git diff)
- Testy: governance test suite PASS
- Evidence pack: D3 Light

### Handoff B → D (Adaptive → Integrator)
**Trigger:** P1-001..P1-004, P2-004..P2-007 PASS
**Deliverables:**
- Raport: `docs/claude_system_audit/AGENT_B_HANDOFF.md`
- Mobile app: build APK + IPA
- Testy: mobile integration suite PASS
- Evidence pack: D3 Light

### Handoff K → D (Surface → Integrator)
**Trigger:** P0-011..P0-012, P1-006..P1-010, P2-001..P2-003, P2-008, P3-001..P3-006 PASS
**Deliverables:**
- Raport: `docs/claude_system_audit/AGENT_K_HANDOFF.md`
- UI screenshots: all pages real data
- Testy: E2E Playwright PASS
- Evidence pack: D3 Light

### Final Integration (D)
**Trigger:** 3× HANDOFF received
**Tasks:**
- Merge wszystkich branchy
- Resolve conflicts
- S1-S8 integration test
- Module-by-module audit
- 5 final deliverables

---

## DEFINITION OF DONE (DoD) — Globalna

Każde zadanie w tym planie jest uznane za zakończone gdy:
1. ✅ Kod napisany i zacommitowany do worktree agenta
2. ✅ Testy jednostkowe PASS (≥75% coverage per moduł)
3. ✅ Testy integracyjne PASS (jeśli dotyczy)
4. ✅ Linter (ruff) PASS, type-check (mypy) PASS
5. ✅ Dokumentacja zaktualizowana (jeśli dotyczy)
6. ✅ Evidence pack (screenshot, log, JSON) w `evidence/<task_id>/`
7. ✅ Code review przez Agenta D (lub E dla read-only audit)
8. ✅ Brak nowych mocków/placeholderów w zmienionym kodzie
9. ✅ Security scan: 0 critical, 0 high per `scripts/security_scan.sh`
10. ✅ HANDOFF checklist complete (dla zadań wymagających)

---

## WATCHDOG CHECKLIST (E — per 4-6h)

| # | Check | FAIL Condition | Akcja |
|---|-------|----------------|-------|
| 1 | Ownership | Plik edytowany przez nie-owner | STOP + revert |
| 2 | Greenfield | Zmiany poza zielone pole agenta | WARN + flag |
| 3 | Stale | Brak commitów >24h (dla P0) | WARN + ping |
| 4 | Test regression | <75% coverage lub FAIL | STOP + fix |
| 5 | Requests backlog | >3 otwarte requesty cross-agent | WARN + escalate |
| 6 | Duplicate planes | Nowy split-brain wykryty | STOP + fix |
| 7 | Reserved-for-D | Zadanie oznaczone "for D" nieprzekazane | WARN |
| 8 | TODO-for-D growth | >5 nowych TODO-for-D per cykl | WARN |
| 9 | Plan adherence | Opóźnienie >2 dni (dla P0) | STOP + replan |

---

*Plan przygotowany na podstawie analizy 1200+ plików systemu AEIS v6.2.0, audytów Codex/Claude, instrukcji obsługi 41 faz, testów manualnych P1-P5 i artefaktów architektonicznych.*
