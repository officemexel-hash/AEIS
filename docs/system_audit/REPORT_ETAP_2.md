# RAPORT ETAP 2 — Mapa architektury + rozstrzygnięcia P1–P5

**Data:** 2026-04-24
**Zakres:** warstwy rzeczywiste vs kanon + 4 śledztwa decyzyjne (worktree Human Gate, proto generations, Dashboard V5/current, Plans 07/09/10)

---

## 1. Rezultat główny: mapa warstw rzeczywistych

Zapisana w [02_ARCHITECTURE_REALITY.md](docs/system_audit/02_ARCHITECTURE_REALITY.md). Kluczowe wnioski:

- System **de facto ma 7 warstw pionowych** + 4 poprzeczne (observability, monitoring, quality, efficiency) + 3 peryferyjne (LAB, Funding, Infra).
- **Księga miała 3 różne modele warstw** (6 AEIS / 7 Distributed Build / 13 klas A-L) — ujednolicenie wymagane w nowej Księdze.
- **Propozycja 2026**: 9 warstw pionowych (L0 Canon → L8 Operator Console + Mobile), z **Human Gate jako własną warstwą L7** (nie podrzędną Governance).

## 2. Framework Human Gate — uzupełnienie kanonu

Na podstawie uzupełnienia od użytkownika zapisano [02_HUMAN_GATE_FRAMEWORK.md](docs/system_audit/02_HUMAN_GATE_FRAMEWORK.md):
- **5 ról** (warstwa decyzyjna / orchestrator / budowanie źródła prawdy / polityki autonomii / interfejs operatorski)
- **12 osi konfiguracji** (ryzyko, typ, środowisko, moduł, operator, koszt, zasoby, tryb wykonania, etap, blocking, batch, timeout)
- **Checklist 12 pytań per moduł** — obowiązkowy w ETAP 3

## 3. Rozstrzygnięcia śledztw

### ✅ P1 — Worktree `serene-mccarthy-6bb664/` (Human Gate)
**Raport:** [02_WORKTREE_HUMAN_GATE_ASSESSMENT.md](docs/system_audit/02_WORKTREE_HUMAN_GATE_ASSESSMENT.md)

- **Inventory**: 18 plików / 1938 LoC Orchestrator, 13 plików / 1376 LoC Operator Mobile, bonus `operator_mobile_testing/` (4 / 359 LoC), ~500 LoC pytest
- **Pokrycie**: Orchestrator **85%** (11/13 IMPLEMENTED, Execution Continuity MISSING, Queue + Notifications PARTIAL). Mobile **75%** (8/12 IMPLEMENTED).
- **Jakość**: 100% type-hinted, pełne docstrings, biometria = HMAC-SHA256 constant-time compare, testy używają real SQLite + FastAPI TestClient (no mocks).
- **Router**: wired w `sylion/api/router.py`. Brak wpisu w `MANIFEST.json`.

**🟢 DECYZJA: MERGE** (Wave 26 po audycie). Uzasadnienie: kod dojrzały, zintegrowany, przetestowany, 0 stubów. Rebuild = 2-3× więcej pracy na identyczny wynik. Luki do uzupełnienia: Execution Continuity Engine, SMS/Email/Slack transports, typed preferences, mobile console UI.

### ✅ P2 — Proto: dwie generacje
**Raport:** [02_PROTO_GENERATIONS_ANALYSIS.md](docs/system_audit/02_PROTO_GENERATIONS_ANALYSIS.md)

- **Legacy** (`src/sylion-pipeline/proto/sylion_*.proto`): 6 plików / 12 services / 53 RPC / 1 pakiet
- **Kanon** (`src/sylion-pipeline/sylion/contracts/proto/`): 16 plików / **86 services / 483 RPC** / 15 pakietów per-domena
- **Runtime**: gRPC server rejestruje **WYŁĄCZNIE legacy stuby** (`grpc_stubs/sylion_*_pb2`). Kanon generowany (`buf.gen.yaml`) ale żaden runtime go nie importuje.
- **Jakość**: kanon wygrywa 11/14 kryteriów (organizacja, skalowalność, versioning, multi-language, buf managed mode). Legacy 3/14 (typowane enumy, Timestamp, docstringi `/** */`, streaming).
- **Drift**: services w obu generacjach (`GovernanceService` vs `DecisionLadderService`) są **wire-niekompatybilne**.
- **Ryzyko krytyczne**: Devices Addon (+16), Operator Mobile (+12), Human Gate Orchestrator (+13) wymagają kontraktów dostępnych **tylko w kanonie**.

**🟢 DECYZJA: KANON** z planem 3-fazowym:
1. **Hardening kanonu** — enumy zamiast stringów, `google.protobuf.Timestamp`, `reserved` tags, docstringi
2. **Dual-run** — legacy port 50051 + v1 port 50052 (SYLION cutover pattern)
3. **Deprecation legacy** — po 2 releasach

### ✅ P3 — Security +10 modułów
**Rozstrzygnięcie (decyzja użytkownika + weryfikacja z P5):**

Security +10 modułów to **NIE bloat** — to częściowo wbudowane w P09 roadmap:
- **Profile management** (`security_profiles`, `profile_swap`, `profiles`) = zaplanowane w **R0.7 #3**
- **Ed25519 evidence signer** (`evidence_signer`) = docelowe **M5** z Masterplanu
- **Audit** (`audit_query`, `audit_trail_aggregator`, `hardened_audit`, `security_audit`) = ekspansja funkcji audytorskich
- **Bootstrap flow, key_vault** = infrastruktura security

**🟢 DECYZJA: zachować wszystkie 18 modułów.** W ETAP 5 zweryfikować **tylko** czy nie ma funkcjonalnych duplikatów między `audit_*` modułami. Security jest **ostatnim elementem przed wdrożeniem** — nie ruszamy teraz (spowolniłoby testy).

### ✅ P4 — Dashboard V5 vs Current
**Raport:** [02_DASHBOARD_V5_VS_CURRENT.md](docs/system_audit/02_DASHBOARD_V5_VS_CURRENT.md)

- **V5 paczka**: ~1092 LoC specu (0 kodu). Zamraża 8 modułów klasy J+ (porty 5801-5807): TWO_PHASE Command Bus, Yjs+tldraw Canvas, event sourcing, resumable upload, deterministic readiness, secrets hygiene.
- **Current**: 56 stron / 164 hooki / ~400 REST calls. Słabości: polling-first, brak `[id]` routes, single-phase governance, 0% mobile, brak trybów instancji.
- **V5 pokrywa 7/12 osi Human Gate** (ryzyko/typ/środowisko/moduł/operator/etap/execution). **Brakuje:** progi kosztowe, liczba zasobów, blocking, grouping (batch), escalation. V5 jest zbyt inżynieryjny (brak wireframe/persona/A11y).

**🟢 DECYZJA: Hybryda A+B** (nie C — rebuild)

**Ścieżka:**
1. **Sprint 1-2**: zachować 100% obecnego frontu jako bazę PRO. Dobudować **SIMPLE** jako `(simple)/` route group — **8 ekranów**: Home, Inbox, Pipeline, Costs, Skills, Evidence, Settings, Search.
2. **Sprint 3-16** (6-8 miesięcy): progresywnie wprowadzać moduły V5:
   - Command Bus TWO_PHASE
   - Event Store
   - Artifact Control
   - Process Canvas (Yjs+tldraw)
   - Readiness Module
   - Event Replay UI
   - 12 osi Human Gate (pełny framework)
3. **Przełącznik 3-warstwowy**: default per rola RBAC (12 ról) → user override w `/settings` → INCIDENT mode auto-lock na PRO. Toggle `Cmd+Shift+P` w TopBar.

**Screenshoty do Księgi (ETAP 7)**: `/workspace` (HumanGatePanel), `/decisions` (CascadeTree), `/overview`, `/governance`, `/evidence-spine`, `/audit`, `/rebuild`, `/cellular`, `/sdr`, `/autonomy` + przyszłe SIMPLE/home, Canvas, Replay.

### ✅ P5 — Plans 01-20 (zwłaszcza 07/09/10)
**Raport:** [02_PLANS_01_20_FULL_SPEC.md](docs/system_audit/02_PLANS_01_20_FULL_SPEC.md)

**ODWRÓCENIE ustalenia z ETAP 1**: Plans 07, 09, 10 **NIE są lukami**. Wcześniej inwentaryzator szukał artefaktów w `evidence/` i `docs/artifacts/` (puste), a faktyczne moduły są w `src/sylion-pipeline/sylion/<domena>/`.

- **P07 Execution**: 6/6 modułów spec + 4 dodatkowe (workflow_engine, tool_runner, connector_framework, job_runner, adapter_bus, retry_orchestrator)
- **P09 Security**: 8/8 spec + silnie rozszerzone (~20 plików) — wyjaśnia "+10" z ETAP 1
- **P10 Efficiency**: 4/4 spec + 4 dodatkowe (circuit_breaker, config_drift, cost_monitor, performance_budget)

**Critical path z Masterplanu:**
```
Contract Freeze → P01 → {P06, P04, P05} → {P02, P07, P08}
→ {P10, P11} → {P12, P13} → P14 → {P16, P17} → P18 → P19 → P20
```

**Human Gate najsilniej w planach:**
- **P05** — Council 4/4 = silnik Human Gate
- **P17** — UI operatora (= Dashboard PRO z P4)
- **P19** — framework autonomii + 5 etapów Autonomy Rollout (R7)

---

## 4. Zsumowany backlog naprawczy (po ETAP 2)

> To jest wstępna lista — ostateczny `AEIS_REPAIR_BACKLOG.md` powstanie w ETAP 6.

### 🔴 Priorytet P0 — bezpośrednio blokujące Księgę
1. **Merge worktree `serene-mccarthy-6bb664/`** → zintegrowanie Human Gate Orchestrator + Operator Mobile core
2. **Dodać wpis `governance.human_gate_orchestrator` do MANIFEST.json** po mergu
3. **Proto migration faza 1** — hardening kanonu (enumy, Timestamp, reserved)
4. **Human Gate — Execution Continuity Engine** (krytyczna luka po mergu)

### 🟠 Priorytet P1 — kluczowe funkcjonalności
5. **Proto migration faza 2** — dual-run legacy 50051 + kanon 50052
6. **Dashboard SIMPLE** — 8 ekranów w `(simple)/` route group
7. **Human Gate 12 osi polityk** — risk-based policy engine z UI (etap P17 Masterplanu)
8. **Notification transports** — SMS/Email/Slack dla Operator Mobile
9. **Typed preferences** w Operator Mobile
10. **Route'y dynamiczne `[id]`** we frontendzie — głębokie widoki detali

### 🟡 Priorytet P2 — rozwój
11. **Mobile AEIS natywna** — Android (Pixel Live Test Mode, 15 testów ADB), biometria, device binding, push, deep link, offline (pracuje sam AEIS według spec)
12. **Dashboard PRO V5** — Command Bus TWO_PHASE → Event Store → Canvas → Replay
13. **Observability/Monitoring** — konsolidacja domen (obecnie nakładające się)
14. **Proto migration faza 3** — deprecation legacy
15. **Security audit dedup** — weryfikacja czy `audit_*` moduły się nie duplikują (JAKO OSTATNIE PRZED WDROŻENIEM)

### ⚪ Dokumentacja i architektura
16. **Ujednolicenie taksonomii** — 9 warstw L0-L8 (propozycja) zamiast 3 równoległych modeli
17. **Plans → pliki `PLAN_XX.md`** w `docs/plans/` (brak kanonicznych MD)
18. **Skills → pliki `skill.yaml`** (obecnie SQLite-only)
19. **Dashboard V5 Package** — zdecydować czy zachować jako referencja / zarchiwizować

---

## 5. Co wiemy pewnie po ETAP 2

| Fakt | Dowód |
|---|---|
| System jest rzeczywiście 119-modułowy, 98% pokrycia Księgi | `01_INVENTORY_BACKEND.md` |
| Human Gate Orchestrator ma cząstkową dojrzałą impl. w worktree | `02_WORKTREE_HUMAN_GATE_ASSESSMENT.md` (85%/75%/100% type-hinted) |
| Proto ma 2 generacje, kanon wygrywa jakościowo | `02_PROTO_GENERATIONS_ANALYSIS.md` (11/14) |
| Frontend 56 stron ma solidną bazę, brak Canvas/Replay/Mobile | `02_DASHBOARD_V5_VS_CURRENT.md` |
| Plans 07/09/10 są IMPLEMENTED (nie luki) | `02_PLANS_01_20_FULL_SPEC.md` |
| Mobile = 0% implementacji | `01_INVENTORY_FRONTEND.md` |
| Security +10 modułów jest zaplanowane w P09 roadmap | `02_PLANS_01_20_FULL_SPEC.md` |
| LAB (cellular/sdr/vps/container) to świadome rozszerzenia | decyzja użytkownika + manifesty |
| Funding Autopilot jest nową produkcyjną warstwą | `01_INVENTORY_BACKEND.md` |

---

## 6. Co wymaga jeszcze pytania przed ETAP 3

### ❓ Q1 — 6 scenariuszy testowych: czy zatwierdzasz jak były?

Przypomnienie propozycji (z korektą S5 o dyskusję modeli → source of truth → masterplan):

| # | Scenariusz | Skala |
|---|---|---|
| S1 | "Hello World" REST endpoint | trywialna |
| S2 | CRUD TODO app (FastAPI + SQLite + 4 endpointy + testy) | prosta |
| S3 | Integracja z OpenAI + rate limiter + cache | średnia |
| S4 | Data pipeline: RSS scraper → normalizer → PostgreSQL → dashboard | średnia/duża |
| S5 | **Funding autopilot full flow** — pomysł → dyskusja modeli → propozycje wariantów → human gate → source of truth → masterplan → wybór topologii (1-model vs multi, local vs VPS) → realizacja → testy → human gate → submit wniosek dotacji | **kanoniczny** |
| S6 | Lokalny Ollama cluster — 5× Docker × 5× Ollama, router per-zadanie, kod bez cloud | ciężka |

Czy dodajesz coś? Zmieniasz kolejność? Priorytet do zrobienia najpierw?

### ❓ Q2 — Pre-check przed ETAP 3: czy uruchamiamy stack teraz?

Żeby robić audyt funkcjonalny per moduł + screenshoty, potrzebuję:
1. Uruchomić backend (`.\scripts\start-server.ps1`)
2. Uruchomić frontend (`.\start_frontend.ps1`)
3. Zweryfikować `/health`, zalogować się (admin password w `.env`), wykonać sanity check ścieżek
4. Zacząć systematyczny audyt modułów (L0 → L8) z dokumentem per warstwa

Jeśli coś się posypie przy starcie — **naprawiam na miejscu** zgodnie z Twoją regułą "fix_all_inline"? Czy zgłaszam i czekam na decyzję?

### ❓ Q3 — Ścieżka scenariuszy — TERAZ czy po audycie statycznym?

Opcje:
- **A)** Najpierw pełny audyt statyczny (moduł po moduł, Human Gate checklist 12 pytań, screenshoty każdej strony) = obraz stanu **bez** uruchamiania scenariuszy, potem scenariusze na koniec ETAP 3
- **B)** Najpierw S1 (trywialny) żeby zweryfikować czy system w ogóle działa end-to-end, potem audyt statyczny, potem pozostałe scenariusze
- **C)** Równolegle — ja audytuję, subagent pilotuje S1 w tle

Rekomenduję **(B)** — S1 jako sanity check, pokaże czy cokolwiek dalej ma sens.

---

**ETAP 2 gotowy. Czekam na odpowiedzi Q1-Q3 żeby uruchomić ETAP 3.**
