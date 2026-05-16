# 01 — INVENTORY: Human Gate Orchestrator + Operator Mobile

Audit date: 2026-04-24
Auditor: Human Gate systems audit
Branch: `claude/gifted-wozniak-abf3ee`
Scope: compare `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt` specification vs. reality in `src/sylion-pipeline/sylion/` and `src/sylion-frontend/src/`.

---

## 0. Kluczowy wniosek na początek

Specyfikacja Human Gate Orchestrator + Operator Mobile **nie została zaimplementowana** na aktualnej gałęzi pracy. W kodzie żywego repo NIE istnieje żaden z następujących katalogów:

- `sylion/decision_orchestrator/` — **MISSING**
- `sylion/operator_mobile/` — **MISSING**
- `sylion/operator_mobile_testing/` — **MISSING**

Jedyna istniejąca implementacja to `sylion/governance/human_gate.py` — minimalny moduł SQLite o 367 liniach, który realizuje wyłącznie `create_request` / `submit_review` / `escalate_request` / `get_stats` (bez typów decyzji, ryzyka, priorytetu, kosztów, delegacji, batchy, SLA, urządzeń mobilnych, biometrii itp.).

Istnieje też artefakt po starszej, równoległej próbie implementacji w worktree `.claude/worktrees/serene-mccarthy-6bb664/` — który nie jest częścią głównej gałęzi.

Pokrycie spec: ~8/25 submodułów ma jakąś cząstkową analogię (PARTIAL), ~17/25 jest MISSING. Pixel Live Test Mode, Secure Approval Layer (biometria, device binding, approval tokens), Follow Me Mode, 6 poziomów autonomii (Level 0-5 wg spec), priorytety P0-P4 — **MISSING w całości**.

---

## 1. Specyfikacja kanoniczna

### MODUŁ 1 — AEIS Human Gate Orchestrator (13 submodułów)

1. **Decision Intake** — zbieranie decyzji od agentów, Dockerów, VPS, pipeline'ów, portali, modułów bezpieczeństwa/finansowych/prawnych; normalizacja, deduplikacja, nadawanie ID.
2. **Decision Classifier** — klasyfikacja ryzyka, finansowa, prawna, techniczna, produkcyjna, bezpieczeństwa, reputacyjna, komunikacyjna, danych wrażliwych, wpływu, pilności, priorytetu P0-P4.
3. **Autonomy Policy Engine** — reguły autozatwierdzania, eskalacji, limitów kosztów/Dockerów/VPS/API/deployment/dostępu, polityki per moduł/operator/środowisko.
4. **Decision Queue** — kolejki P0/P1/P2/P3/P4, finansowe, prawne, techniczne, produkcyjne, bezpieczeństwa, blocking, non-blocking, zbiorcze, przeterminowane.
5. **Batch Approval Engine** — grupowanie podobnych/technicznych/infra/dokumentowych/build-test, zatwierdzanie/odrzucanie pakietowe, analiza ryzyka pakietu, podpis.
6. **Delegation Engine** — przypisywanie do właścicieli (CTO/CFO/prawnik/admin/PM/zastępca), fallback owner, approval hierarchy, zastępstwa.
7. **Execution Continuity Engine** — kontynuacja niezależnych zadań, zamrażanie zależnych, work stealing, wykrywanie deadlocków, timeouty, fallback plans.
8. **Decision Dependency Graph** — graf zależności decyzji/tasków/agentów/workerów, blocking vs non-blocking, wąskie gardła, alternatywne ścieżki.
9. **Risk-Based Auto Approval** — autozatwierdzanie niskiego ryzyka, w limitach budżetu, testów/build/analiz/draftów/staging; blokada prawne/finansowe/produkcyjne.
10. **Notification Routing** — routing decyzji do dashboard/mobile/email/SMS/Slack/zastępcy, priorytety, tryb ciszy, eskalacja przy braku reakcji.
11. **Decision SLA** — czas reakcji per P0–P4, timeouty, fallbacki, eskalacje.
12. **Audit Trail** — kto/kiedy/z jakiego urządzenia/co/rekomendacja/alternatywy/ryzyka/wersje/koszt/wpływ/pełna historia.
13. **Decision Learning** — uczenie preferencji operatora, sugerowanie domyślnych, wykrywanie powtarzalnych decyzji, tworzenie reguł z historii, rekomendacje automatyzacji.

### MODUŁ 2 — AEIS Operator Mobile (12 submodułów drzewa aplikacji)

1. **Global Critical Inbox** — decyzje P0/P1, blokujące projekt, prawne, finansowe, produkcyjne, bezpieczeństwa, czasowe.
2. **Module Channels** — Funding, Infrastructure, Deployment, Security, Finance, Legal, Code Build, Browser Agents, Documents, External Communication, Research, System Health.
3. **Push Notification Engine** — push P0/P1, krytyczne powtarzane, eskalacje, SMS/email fallback, tryb ciszy, reguły per moduł.
4. **Mobile Human Gate** — zatwierdź/odrzuć/odłóż/deleguj/poproś o szczegóły/wariant alternatywny/limit/podobne automatycznie.
5. **Secure Approval Layer** — Face ID/Touch ID/biometria, PIN, 2FA, device binding, approval token, podpis kluczem urządzenia, session timeout, device revoke.
6. **Operator Modes** — Full Control / Critical Only / Build Watch / Deployment Watch / Security Watch / Funding Watch / Night Build / Do Not Disturb / Delegated.
7. **System Status** — status AEIS Core, agentów, workerów, Dockerów, VPS, kolejek, kosztów, deploymentów, bezpieczeństwa.
8. **Batch Approval** (mobile view) — pakiety tech/infra/docs/code/tests, zatwierdzanie zbiorcze.
9. **Escalation System** — operator główny/zastępca/CTO/CFO/prawnik/admin/PM/fallback owner.
10. **Voice / Chat Operator** — zapytaj AEIS, streszczenie, ryzyko, logi, dyktowanie, zatwierdzenie po biometrii.
11. **Audit & Compliance** — fingerprint urządzenia, moduł, koszt, ryzyko, wersja, alternatywy, pełna historia.
12. **Operator Preferences** — reguły powiadomień, limity kosztów/infra, poziom autonomii, priorytety modułów, godziny ciszy, whitelist, delegacje.

### Dodatkowo wymagane

- **Pixel Live Test Mode** — 15 testów ADB (Device Detection, App Install, App Launch, Device Registration, Push, Deep Link, Approval/Rejection/Defer Flow, Token Expiry, Offline, Audit Trail, Logcat, Crash Report, Mobile QA Report).
- **Autonomy Levels** — 6 poziomów (0 Manual, 1 Assisted, 2 Bounded, 3 Supervised default, 4 High, 5 Full).
- **Decision Priorities** — P0 Emergency / P1 Critical / P2 High / P3 Medium / P4 Low.
- **Decision Types** — Strategic / Financial / Legal / Technical / Security / Data / External Action / Production / Low-Risk Operational.
- **Decision model** — 30+ pól (decision_id, priority, risk_level, is_blocking, cost_estimate, legal_impact, financial_impact, production_impact, security_impact, external_action, sensitive_data_usage, recommended_action, alternatives, consequences_*, dependencies, deadline, sla, assigned_to, delegation_allowed, mobile_allowed, requires_biometric, requires_fresh_auth, requires_signature, ...).
- **Backend packages** — `sylion/decision_orchestrator/` (17 plików), `sylion/operator_mobile/` (18 plików), `sylion/operator_mobile_testing/` (13 plików), 33 tabele DB, ~45 endpointów REST (Human Gate + Operator Mobile + Pixel Live Test).

---

## 2. Mapa rzeczywistości

### 2.1 Orchestrator — 13 submodułów

| # | Nazwa spec | Status | Dowody (pliki / linie) | Luki |
|---|------------|--------|------------------------|------|
| 01 | Decision Intake | **MISSING** | Brak modułu intake. `governance/human_gate.py:130` `create_request()` przyjmuje tytuł/opis + opaque `context_json` od pojedynczego wywołującego. Brak integracji ze źródłami: Dockers, VPS, pipeline, portale, moduły finansowe/prawne/security. | Brak normalizacji, deduplikacji, adapterów źródeł, routingu od agentów. |
| 02 | Decision Classifier | **PARTIAL** | Istnieje `governance/decision_ladder.py` (D0-D5) oraz `core/decision_gate_engine.py`. Klasy D0-D5 to klasyfikacja "siły" decyzji pod Council, nie ma związku z klasami spec (Financial/Legal/Technical/Security/Data/External/Production/Strategic). Brak priorytetu P0-P4. Risk scorer `governance/risk_scorer.py` liczy score 0-1 dla modułów, nie dla decyzji Human Gate. | Brak klasyfikatora finansowego/prawnego/technicznego/produkcyjnego per decyzja. Brak pilności, priorytetu P0-P4, wpływu reputacyjnego, komunikacyjnego, danych wrażliwych. |
| 03 | Autonomy Policy Engine | **PARTIAL** | `governance/policy_engine.py` (rule-based, operatory eq/ne/gt/in/regex, scope-based). `aeis/autonomy_controller.py` — 5 etapów (observe/propose/sandbox/limited/full). Brak polityk dla: limitów kosztów, limitów Dockerów/VPS/API, polityk per moduł/operator/środowisko w formacie spec (`autonomy_policy.level`, `auto_approve: [...]`, `require_human_approval: [...]`, `budget_limits`). | Brak budżetów, limitów infrastruktury (`max_auto_local_docker_containers`, `max_auto_vps_workers`), definicji per-action (`production_deployment`, `signing_document`, `rotating_production_secrets`). |
| 04 | Decision Queue | **MISSING** | Tylko `human_gate.list_requests(status=?)` — płaska lista filtrowana. Brak kolejek priorytetowych, brak P0-P4, brak rozróżnienia blocking/non-blocking/zbiorcze/przeterminowane. | Brak PriorityQueue, brak osobnych kolejek finansowych/prawnych/technicznych, brak timeout queue. |
| 05 | Batch Approval Engine | **MISSING** | Brak kodu batchowania decyzji. `context_json` w `human_gate_requests` nie daje grupowania. | Brak grouping/bulk approve endpointów, brak analizy ryzyka pakietu, brak podpisu zbiorczego. |
| 06 | Delegation Engine | **MISSING** | Brak delegowania w `human_gate.py`. Nie ma pól `assigned_to`, `delegation_allowed`, fallback owner, hierarchii approval. | Brak CTO/CFO/prawnik/admin role-based routing. |
| 07 | Execution Continuity Engine | **PARTIAL** | `aeis/autonomy_stages.py::LimitedProdExecutor` ma `escalate_to_human`, `resolve_escalation`, rate limits, scope limits. To jednak sandbox AEIS-u, nie globalne continuity dla wszystkich agentów. Brak work-stealing, deadlock detection dla workerów. | Brak kontynuacji zadań niezależnych przy blokadzie Human Gate, brak work stealing, brak timeouts decyzji na poziomie orchestratora. |
| 08 | Decision Dependency Graph | **MISSING** | Istnieje `contracts/dependency_graph.py` i `core/dependency_mapper.py` — dla kontraktów/modułów, nie dla decyzji. | Brak grafu zależności między decyzjami, brak blocking/non-blocking markerów, brak wykrywania wąskich gardeł. |
| 09 | Risk-Based Auto Approval | **MISSING** | `risk_scorer.py` liczy ryzyko modułu, ale nie ma logiki auto-approve decyzji pod progiem ryzyka. | Brak polityki `auto_approve` z listą white-list akcji z spec (local_tests, code_generation_draft, staging_deployment, ...). |
| 10 | Notification Routing | **PARTIAL** | `monitoring/notification_engine.py` ma kanały (email/webhook/in_app/slack), severities (info/warning/urgent/critical) i rules engine. Jest też `api/notification_routes.py`. Nie ma routingu do mobile, SMS, do zastępcy. Brak powiązania z decision_id — notifications są generyczne. | Brak mobile channel, SMS, eskalacji przy braku reakcji, trybu ciszy globalnego, reguł per moduł mobilny. |
| 11 | Decision SLA | **MISSING** | Brak SLA per priorytet P0-P4, brak timeoutów decyzji, fallbacków. `human_gate_requests.priority` istnieje jako string pole, ale nie wpływa na żadne zachowanie. | Brak timerów, enforcement SLA, eskalacji po przekroczeniu. |
| 12 | Audit Trail | **PARTIAL** | `governance/decision_audit.py`, `governance/evidence_spine.py`, `governance/evidence_timeline.py`, `governance/decision_snapshot.py`. Zbiera snapshoty, cascades, conflicts, compliance checks. Brak pól: koszt, wpływ, device fingerprint, wersja kodu/dokumentu per decyzja Human Gate. `human_gate_reviews` zapisuje tylko reviewer/decision/rationale/timestamp. | Brak IP/urządzenia/fingerprintu, brak wpływu finansowego/prawnego/produkcyjnego, brak wersji dokumentu. |
| 13 | Decision Learning | **MISSING** | Brak modułu uczenia preferencji operatora, brak sugerowania domyślnych decyzji, brak ekstrakcji reguł z historii. | Całkowity brak. |

### 2.2 Operator Mobile — 12 submodułów

Kategoryczny status dla wszystkich: **MISSING** (brak `sylion/operator_mobile/` i frontendu mobilnego).
Dla pełnej rzetelności rozpisane pojedynczo:

| # | Nazwa spec | Status | Dowody | Luki |
|---|------------|--------|--------|------|
| 01 | Global Critical Inbox | **MISSING** | Brak aplikacji mobilnej. Web: `frontend/src/app/(app)/decisions/page.tsx` — dashboard decyzji D0-D5 (cascades, compliance), nie inbox krytyczny P0/P1. | Brak P0/P1 filtra, blokujących, czasowych, mobilnej nawigacji. |
| 02 | Module Channels | **MISSING** | Brak mobilnych kanałów per moduł. Web ma osobne strony `funding`, `deploy`, `security-scan`, `secrets`, `workers`, itd., ale to nie kanały decyzyjne a dashboardy techniczne. | Brak routingu decyzji per moduł do mobilnego kanału. |
| 03 | Push Notification Engine | **MISSING** | `monitoring/notification_engine.py` nie ma push tokenów, FCM/APNs, biometric repeat-until-ack, SMS/email fallback dla decyzji Human Gate. | Brak push gateway, brak push tokenów. |
| 04 | Mobile Human Gate (approve/reject/defer/delegate) | **PARTIAL (tylko web, nieobsługuje defer/delegate)** | `api/gates_routes.py:208,232,260` — POST `/human/reviews` (approve/reject/needs_info), GET `list_requests`, `escalate_request`. `frontend/components/workspace/HumanGatePanel.tsx` (802 linie) — UI dla session-based decision tree z choices, undo, rollback — to faktycznie jest "Decision Tree" dla workflow Canon Book, nie `approve/reject/defer/delegate` z spec Mobile. | Brak `defer` (odłóż), brak `delegate` (deleguj), brak `zatwierdź do limitu`, brak `zatwierdź podobne automatycznie`, brak `więcej informacji`. |
| 05 | Secure Approval Layer (biometria, device binding, token, signature) | **MISSING** | Brak biometrii, brak device binding dla decyzji, brak approval tokens, brak podpisu kluczem urządzenia. `pixel_provision.py:12` wzmiankuje FIDO2 dla provisionowania urządzeń SDR, nie dla Human Gate mobile. | Całkowity brak. |
| 06 | Operator Modes (Full/Critical/Build Watch/...) | **MISSING** | Brak jakiegokolwiek state machine operator mode. | Brak. |
| 07 | System Status | **PARTIAL (web)** | `frontend/src/app/(app)/overview/page.tsx` oraz `health`, `workers`, `deploy`, `costs` strony dają dashboardy. Nie mobile. | Brak mobilnej konsolidacji. |
| 08 | Batch Approval (mobile view) | **MISSING** | Brak batch view. | Brak. |
| 09 | Escalation System (role-based) | **PARTIAL** | `governance/human_gate.py::escalate_request` ustawia `status='escalated'` + `escalation_reason`. Brak mapping do CTO/CFO/prawnika/admin/zastępcy. | Brak role-based routing. |
| 10 | Voice / Chat Operator | **MISSING** | AI Workspace chat istnieje (`ai_workspace_routes.py`) dla ogólnych rozmów, ale nie dla dyktowania decyzji + biometria. | Brak. |
| 11 | Audit & Compliance (device fingerprint, versions) | **MISSING** | `human_gate_reviews` nie rejestruje device ID, IP, fingerprintu, wersji kodu/dokumentu. | Brak. |
| 12 | Operator Preferences | **MISSING** | Brak tabeli `operator_notification_preferences` i UI ustawień mobilnych. | Brak. |

---

## 3. Pixel Live Test Mode

Ślady w kodzie:

- `src/sylion-pipeline/pixel_provision.py` — skrypt provisionowania Pixel 9 z GrapheneOS, USB passthrough (usbipd), ADB unlock, Magisk, FIDO2. **Przeznaczenie: urządzenie SDR / fizyczny klucz bezpieczeństwa dla operatora SYLION**, nie testbed dla aplikacji mobilnej.
- `src/sylion-pipeline/templates/51-android.rules` — udev rules dla Pixela (ADB/fastboot).
- `src/sylion-pipeline/tests/test_pixel_detect_endpoint.py` — testy endpointu `/api/health/pixel-detect` (stary stack `dashboard/app.py`, nie aktywny `sylion/api`). Mockuje `adb devices` dla wykrycia Pixel 9.
- `src/sylion-pipeline/docs/security/PIXEL_HARDENING_CHECKLIST.md`, `PIXEL_THREAT_MODEL.md` — hardening urządzenia operatora (nie app testy).
- `sylion/devices/device_discovery.py` — generyczny scanner urządzeń (nie app Android).

Nie istnieją: `sylion/operator_mobile_testing/adb_device_manager.py`, `pixel_device_detector.py`, `apk_installer.py`, `app_launcher.py`, `push_test_service.py`, `approval_flow_test.py`, `biometric_test_plan.py`, `logcat_collector.py`, `crash_report_collector.py`, `network_test_runner.py`, `mobile_qa_report.py`, `device_trust_test.py`, `reconnect_test.py`.

Nie istnieje: 15 testów z spec (Test 1 Device Detection ... Test 15 Mobile QA Report).
Brak: budowania APK, `adb install`, deep link testów, push notification testów, approval flow E2E, biometric test plan.

**Status całościowy Pixel Live Test Mode: MISSING** w kontekście Operator Mobile. Istnieje odrębny strumień Pixel dla SDR/hardware provisioning, niezwiązany ze spec.

---

## 4. Secure Approval Layer (biometria, device binding)

Ślady:

- `sylion/security/execution_guard.py` — execution guard dla operacji ryzykownych (biometrii nie obsługuje).
- `sylion/security/profile_swap.py` — security profile swapping.
- `sylion/auth/` (nie sprawdzony głęboko, ale brak odwołań do biometrii, FIDO2, approval tokens w grep).
- `pixel_provision.py:12` — pojedyncza wzmianka FIDO2 w komentarzu: "FIDO2 key enrollment (HumanGate — operator physically swaps USB cable for FIDO2 key)". To prostokątna koncepcja fizycznego klucza dla zatwierdzeń, ale nie ma implementacji weryfikacji FIDO2 w Human Gate flow, nie ma generacji approval tokens, nie ma device binding per decyzja.
- Brak plików: `operator_mobile/approval_tokens.py`, `biometric_challenge.py`, `device_registry.py`, `mobile_auth.py`, `operator_devices` table.
- Brak wymagań `requires_biometric`, `requires_fresh_auth`, `requires_signature` w `human_gate_requests`.

**Status: MISSING.** Jedynie koncepcyjna wzmianka FIDO2 bez kodu enforcement.

---

## 5. Autonomy Levels — 6 poziomów

Spec wymaga 6 poziomów (Level 0 Manual → Level 5 Full Autonomy), domyślnie **Level 3 Supervised**.

Rzeczywistość:

- `sylion/aeis/autonomy_controller.py` — ma **5 etapów** (observe / propose / sandbox / limited / full) pod nazwą `AutonomyStage`. To **nie są** spec levels 0-5; to etapy "rollout" per Masterplan R7 (gates G-AUTONOMY-1..5).
- Mapping etap vs spec level jest tylko luźny: `observe` ≈ Level 0, `full` ≈ Level 5. Brak semantyki "Assisted", "Bounded", "Supervised" z spec.
- Domyślny etap: `OBSERVE` (najniższy). Spec wymaga: Level 3 Supervised jako domyślny.
- `sylion/aeis/autonomy_stages.py` — implementuje SandboxExecutor (Stage 3) i LimitedProdExecutor (Stage 4) z rate limits, scope limits, escalation — to jest wartościowa część.
- Brak: `autonomy_policy.level`, `auto_approve` list, `require_human_approval` list, `budget_limits`, `infrastructure_limits`, `deployment`, `documents`, `portals` sections z spec YAML.
- Brak endpointu `/api/v1/decisions/autonomy-level` z spec.

**Status: PARTIAL.** Istnieje kompletny controller 5-stage rollout (≠ spec 6-level), ale semantycznie niezgodny. Domyślny poziom błędny wg spec.

---

## 6. Decision Queue + priorytety P0-P4

- `human_gate_requests.priority TEXT DEFAULT 'normal'` — kolumna istnieje, ale nie ma enum P0/P1/P2/P3/P4 ani żadnej logiki sortowania/routingu wg priorytetu.
- Brak klasy `DecisionPriority` gdziekolwiek w `sylion/`.
- Brak osobnych kolejek: emergency, critical, high, medium, low, finansowych, prawnych, technicznych, produkcyjnych, bezpieczeństwa, blocking, non-blocking, zbiorczych, przeterminowanych.
- Brak endpointu `/api/v1/decisions/critical`, `/api/v1/decisions/pending`, `/api/v1/decisions/batches`.
- `risk_scorer.py::VALID_LEVELS = ('low','medium','high','critical')` — to risk levels modułu, nie priorytet decyzji.
- `notification_engine.py::VALID_SEVERITIES = ('info','warning','urgent','critical')` — severity kanałów powiadomień, nie priorytet decyzji.

**Status: MISSING.** Kolumna `priority` istnieje jako martwe pole.

---

## 7. Wnioski

### 7.1 Pokrycie spec (ilościowe)

| Obszar | IMPLEMENTED | PARTIAL | API_ONLY | MISSING |
|--------|-------------|---------|----------|---------|
| Human Gate Orchestrator (13 submodułów) | 0 | 5 (02, 03, 07, 10, 12) | 0 | 8 (01, 04, 05, 06, 08, 09, 11, 13) |
| Operator Mobile (12 submodułów) | 0 | 3 (04, 07, 09) | 0 | 9 |
| Pixel Live Test Mode (15 testów) | 0 | 0 | 0 | 15 |
| Autonomy Levels (6 poziomów) | 0 | 1 (PARTIAL — 5 innych poziomów) | 0 | 0 |
| Decision Priorities (P0-P4) | 0 | 0 | 0 | 1 |
| Backend packages (decision_orchestrator, operator_mobile, operator_mobile_testing) | 0 | 0 | 0 | 3 |

**Łącznie spec submodułów (25 orchestrator+mobile):** 0 IMPLEMENTED, 8 PARTIAL, 17 MISSING → **pokrycie ~8/25 ≈ 32% cząstkowo, 0% w pełni**.

Jeśli dodać Pixel Test, Priorities, Levels, Secure Approval, Follow Me Mode, Operator Modes, Decision Types jako osobne wymiary — pełny stopień zgodności jest znacząco niższy (szacunkowo ~10–15% gdy uwzględnimy wagi).

### 7.2 Największe luki

1. **Brak pakietu `sylion/decision_orchestrator/`** — 17 plików spec (models, schemas, routes, policy_engine, decision_classifier, decision_queue, batch_compiler, dependency_graph, approval_service, delegation_service, notification_router, audit_log, timeout_handler, fallback_engine, autonomy_profiles, decision_learning).
2. **Brak pakietu `sylion/operator_mobile/`** — 18 plików spec (mobile_auth, device_registry, push_gateway, notification_policy, priority_classifier, mobile_decision_view, approval_tokens, biometric_challenge, escalation_service, operator_status, notification_preferences, module_channels, audit_service, emergency_alerts, pixel_live_test).
3. **Brak pakietu `sylion/operator_mobile_testing/`** — 13 plików spec (adb_device_manager, pixel_device_detector, apk_installer, app_launcher, push_test_service, approval_flow_test, biometric_test_plan, logcat_collector, crash_report_collector, network_test_runner, mobile_qa_report, device_trust_test, reconnect_test).
4. **Brak aplikacji mobilnej Android/iOS w całości** — nie ma żadnego katalogu z projektem React Native / Flutter / natywnym Android. Nie można instalować na Pixel przez ADB.
5. **Brak priorytetów P0-P4 jako first-class concept** — istnieje tylko `priority TEXT 'normal'` jako nieużywane pole.
6. **Brak batch approval** — cała logika grupowania decyzji nie istnieje.
7. **Brak delegation** — Human Gate nie ma role-based assignment, fallback owner.
8. **Brak SLA, timeoutów, fallbacków** dla decyzji Human Gate.
9. **Brak Secure Approval Layer**: biometria, FIDO2 w flow Human Gate, approval tokens, device binding, signature decyzji.
10. **Brak Follow Me Mode, Operator Modes, Notification Preferences.**
11. **Brak integracji Human Gate z agentami AEIS** (Funding, Code, Infra, Deploy, Security, Finance, Legal, External Comm, Browser, Data, Research) jako globalny bus decyzji. `human_gate.py::create_request` wymaga, żeby ktoś ręcznie ją zawołał; nie ma hookow z agentów.
12. **Drift nazewnictwa**: 5-stage autonomy rollout (R7) vs 6-level autonomy (spec) — istnieją obok siebie i konfundują.
13. **Przemieszany artefakt w worktree** `.claude/worktrees/serene-mccarthy-6bb664/` zawiera częściowe implementacje `decision_orchestrator/` i `operator_mobile/` (routes, services, schemas, emergency_alerts, biometric_challenge, pixel_live_test, batch_compiler, delegation_service, timeout_handler, decision_learning, dependency_graph, notification_router, aeis_adapter, operator_digest). **Ten kod NIE jest w głównej gałęzi `main` ani w `claude/gifted-wozniak-abf3ee`.** Trzeba zadecydować: merge, rebuild, czy porzucenie.

### 7.3 Co jest dobrze zaimplementowane

- **`sylion/governance/human_gate.py`** (367 linii) — solidny, thread-safe SQLite moduł z EventBus, ale z bardzo wąskim zakresem (create/submit/escalate/list/stats). Dobra baza do rozszerzenia, ale nie może sama zrealizować spec.
- **`sylion/governance/decision_ladder.py`** (D0-D5) + **`core/decision_gate_engine.py`** — solidny governance flow z evidence spine, cascades, snapshots; obsługuje D4/D5 z Human Gate jako etapem. Warto połączyć z brakującym `decision_classifier` z spec (klasy Financial/Legal/Technical/...).
- **`sylion/governance/decision_audit.py`** + **`evidence_spine.py`** + **`decision_snapshot.py`** — dojrzały audit trail dla governance decyzji, cascade events, conflicts. Dobra podstawa pod wymaganie "Audit Trail" z spec, po dodaniu pól device/cost/impact.
- **`sylion/aeis/autonomy_controller.py`** + **`autonomy_stages.py`** (SandboxExecutor, LimitedProdExecutor) — dobra infrastruktura pod execution continuity, rate limits, scope limits, escalations. Można ją refaktoryzować tak, by mapowała się na spec Levels 0-5.
- **`sylion/governance/policy_engine.py`** — generyczny rule engine (operatory, scope) — dobry fundament pod Autonomy Policy Engine z spec (budget_limits, infrastructure_limits, auto_approve lists).
- **`sylion/monitoring/notification_engine.py`** + **`api/notification_routes.py`** — pełny notification system z kanałami (email/webhook/in_app/slack), rules, log. Brakuje tylko mobile/SMS kanału i integracji z decision_id.
- **`frontend/src/components/workspace/HumanGatePanel.tsx`** (802 linie) — dobra bazowa UI dla decision tree, ale dotyczy innego flow (Canon Book kickoff z choices + rollback), nie `approve/reject/defer/delegate` krytycznych decyzji. Do dużej przebudowy.
- **`frontend/src/app/(app)/decisions/page.tsx`** oraz `gates/page.tsx`, `governance/page.tsx`, `autonomy/page.tsx`, `evidence/page.tsx`, `evidence-spine/page.tsx` — bogata warstwa UI po stronie web (nie mobile).

### 7.4 Rekomendowane kolejne kroki audytu

1. Zdecydować losy worktree `serene-mccarthy-6bb664` — czy to był poprzedni spike do merge'a?
2. Po stronie backend: zaplanować wprowadzenie `sylion/decision_orchestrator/` jako orkiestratora ponad istniejącym `human_gate.py` + `decision_ladder.py` + `policy_engine.py` (nie rewrite — kompozycja).
3. Wprowadzić enum `DecisionPriority {P0..P4}` i `DecisionType {Strategic, Financial, Legal, Technical, Security, Data, ExternalAction, Production, LowRiskOperational}` jako first-class w modelu.
4. Dopisać pola do `human_gate_requests`: priority enum, risk_level, decision_type, is_blocking, cost_estimate, legal_impact, production_impact, mobile_allowed, requires_biometric, assigned_to, deadline, sla.
5. Autonomy Levels: udokumentować jawnie relację między 5-stage rollout a 6-level spec; albo skonsolidować, albo rozdzielić (rollout = dojrzałość AEIS; levels = polityka per-task).
6. Mobile: oddzielna decyzja strategiczna — zbudować natywną aplikację (React Native?), czy na starcie PWA oparte o istniejący `sylion-frontend`.

---

## Załącznik A — Odwołania do plików (absolutne ścieżki)

- `C:\Users\razor\Desktop\pipeline_glm\AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt` — spec, 1408 linii.
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\human_gate.py` — jedyna istniejąca implementacja Human Gate.
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\decision_ladder.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\decision_audit.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\decision_snapshot.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\evidence_spine.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\policy_engine.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\risk_scorer.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\governance\conflict_resolver.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\aeis\autonomy_controller.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\aeis\autonomy_stages.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\core\decision_gate_engine.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\monitoring\notification_engine.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\api\gates_routes.py` — `/api/v1/gates/human/*` endpointy.
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\api\governance_routes.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\api\notification_routes.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\api\aeis_routes.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\api\ai_workspace_routes.py` — `/workspace/human-gate/*` endpointy sesji decyzji.
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\security\execution_guard.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\devices\device_discovery.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\pixel_provision.py` — provisioning Pixel SDR (nie app mobilnej).
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\tests\test_pixel_detect_endpoint.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\tests\test_human_gate.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\tests\test_autonomy_controller.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\tests\test_autonomy_stages.py`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\components\workspace\HumanGatePanel.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\app\(app)\decisions\page.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\app\(app)\gates\page.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\app\(app)\governance\page.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\app\(app)\autonomy\page.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\app\(app)\evidence\page.tsx`
- `C:\Users\razor\Desktop\pipeline_glm\.claude\worktrees\serene-mccarthy-6bb664\src\sylion-pipeline\sylion\decision_orchestrator\*` — artefakt równoległej implementacji POZA gałęzią.
- `C:\Users\razor\Desktop\pipeline_glm\.claude\worktrees\serene-mccarthy-6bb664\src\sylion-pipeline\sylion\operator_mobile\*` — jw.
