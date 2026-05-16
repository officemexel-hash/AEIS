# CODEX AEIS Full Model Audit - 2026-05-02

Audyt sprawdza "Pelny Model Roboczy AEIS" wzgledem repo, runtime, API, UI, testow i dokumentacji.

Priorytet prawdy:

1. kod
2. runtime
3. API
4. UI
5. testy
6. dokumentacja

## Werdykt

AEIS nie jest juz tylko dokumentacja ani zbiorem statycznych paneli. Repo zawiera szeroki system z backendem FastAPI, duzym katalogiem endpointow, frontendem operatorskim, warstwami W1-W19, Human Gate, Council, Funding, Mobile, Memory, Skills, Worker/Runtime i rozszerzeniami laboratoryjnymi.

Jednoczesnie nie jest to jeszcze w pelni domkniety "system operacyjny projektow" w sensie kanonu. Najwieksza roznica miedzy kanonem a runtime jest taka, ze wiele warstw istnieje jako API i UI, ale nie wszystkie sa jeszcze wymuszane jako jeden globalny przeplyw: prawda -> rada -> Human Gate -> masterplan -> wykonanie -> testy -> closure -> memory.

Najkrotszy status: **duzy system kodowo-runtime'owy, czesciowo spiety end-to-end, ale governance i adaptacyjne planowanie nadal wymagaja domkniecia jako centralny przeplyw, nie tylko moduly.**

## Artefakty dowodowe

- `docs/codex_system_audit/aeis_full_model_inventory_2026_05_02.json`
- `docs/codex_system_audit/aeis_full_model_coverage_2026_05_02.json`
- `docs/codex_system_audit/AEIS_FULL_MODEL_API_UI_COVERAGE_2026_05_02.md`
- `docs/codex_system_audit/aeis_full_model_runtime_probe_2026_05_02.json`
- `docs/codex_system_audit/aeis_full_model_ui_probe_2026_05_02.json`
- `docs/codex_system_audit/aeis_full_model_governance_flow_probe_corrected_2026_05_02.json`

## Liczby z inwentaryzacji

| Obszar | Wynik |
|---|---:|
| Backend packages | 37 |
| Backend modules | 744 |
| API route files | 126 |
| Frontend routes | 125 |
| Client API refs | 788 |
| Runtime OpenAPI paths | 1599 |
| Repo skills | 29 |
| Test files | 573 |
| Proto files | 6 |
| `/health` modules | 138 |
| `/health` endpoints | 1946 |

## Naprawy wykonane podczas audytu

1. **Worker topology alias**

   Problem: `GET /api/v1/workers/topology` wpadal w dynamiczne `GET /api/v1/workers/{worker_id}` i zwracal `404 Worker not found`.

   Naprawa: dodany jawny alias `GET /api/v1/workers/topology`, ktory zwraca `{"topologies": [...]}`.

   Pliki:
   - `src/sylion-pipeline/sylion/api/worker_routes.py`
   - `src/sylion-pipeline/tests/test_worker_routes.py`

2. **Frontend Memory Search**

   Problem: klient frontendu wolal nieistniejace `/api/v1/memory/search?q=...`.

   Naprawa: klient uzywa teraz realnego endpointu backendu `/api/v1/memory/index/search?query=...`.

   Plik:
   - `src/sylion-frontend/src/lib/api/client.ts`

3. **Sonda runtime**

   Bledne probe `container/images` i `memory/search` zostaly zastapione realnymi endpointami `/api/v1/container/images` i `/api/v1/memory/index/search`.

## Runtime probe

Po poprawkach sprawdzone endpointy zwrocily `200`:

- system: `/health`, `/api/v1/architecture-layers`
- projekty: `/api/v1/projects`
- Human Gate: `/api/v1/gates/human/stats`, `/api/v1/gates/human/requests`
- governance: `/api/v1/governance/tickets`, `/api/v1/governance/gates`
- Council: `/api/v1/governance/council/sessions`, `/api/v1/workspace/council/roles`
- Memory: `/api/v1/memory/health`, `/api/v1/memory/index/stats`, `/api/v1/memory/evidence/stats`, `/api/v1/memory/index/search`
- Skills: `/api/v1/skills/health`, `/api/v1/skills/runtime/stats`, `/api/v1/skills/catalog-stats`
- Funding: `/api/v1/funding/health`, `/api/v1/funding/sources`, `/api/v1/funding/submission/sessions`
- Mobile: `/api/v1/mobile/devices?operator_id=...`, `/api/v1/mobile/queue?operator_id=...`
- W18: `/api/v1/terminal/health`
- Workers: `/api/v1/workers`, `/api/v1/workers/topology`, `/api/v1/workers/topology/all`
- Quality/Test: `/api/v1/test-center/catalog`, `/api/v1/quality/test-stats`
- Lab/runtime extensions: `/api/v1/devices/tests`, `/api/v1/sdr/devices`, `/api/v1/cellular/ran`, `/api/v1/container/images`, `/api/v1/vps/providers`

## UI probe

Playwright odwiedzil:

- `/execution-start`
- `/architecture-layers`
- `/memory`
- `/model-council`
- `/human-gate`
- `/governance`
- `/workers`
- `/operator-mobile`
- `/funding`
- `/test-center`

Wynik: kazda strona `200`, brak `console.error`, brak `pageerror`, brak `requestfailed`.

## Governance flow probe

Wykonany kontrolowany flow:

- utworzenie Council session
- dodanie planner i critic
- podpis krytyka
- oceny `cost_sentinel` i `security_sentinel`
- uruchomienie analizy Council
- weighted consensus
- gated consolidation
- utworzenie i rozstrzygniecie unified governance ticket `D4`
- utworzenie HumanGate session, prezentacja decyzji i wybor operatora

Wynik koncowy: flow dziala runtime'owo.

Wazny drift: `council_analyze` uzyl realnego fallbacku do providera API (`anthropic`, model `claude-haiku-4-5-20251001`) i oszacowal koszt ok. `0.011226 USD`. To jest ponizej progow kosztowych, ale w kanonie local-first/API-governance powinno byc jawnie widoczne w W18/Human Gate albo przynajmniej w polityce runtime. To nie jest crash, ale jest istotna luka governance.

## Status warstw W1-W19

| Warstwa | Status | Dowod / luka |
|---|---|---|
| W1 Canon | PARTIAL | `/api/v1/architecture-layers` eksponuje kanon W1-W19, ale reguly nie sa jeszcze jednolitym silnikiem wymuszania. |
| W2 Workspace | PARTIAL/LIVE | backend, SQLite, lokalny runtime i workspace dzialaja; repo ma duzo lokalnych baz i artefaktow. |
| W3 Operator Identity | PARTIAL | istnieja profile, mobile operator_id i governance reviewer, ale pelna tozsamosc wlasciciela/operatora nie jest centralnie wymuszana w kazdym flow. |
| W4 Provider & Model Catalog | LIVE/PARTIAL | endpointy provider/model istnieja; Council potrafi uzyc realnego fallbacku API. Brakuje twardego local-first gate dla takich wywolan. |
| W5 Runtime / Environment | LIVE/PARTIAL | local backend, workers, VPS/container/device endpoints istnieja; topologie puste. |
| W6 Defaults / Autonomy | PARTIAL | endpointy i panele istnieja; audyt nie potwierdzil, ze medium autonomy steruje kazda decyzja runtime. |
| W7 Guards / Human Gate | LIVE/PARTIAL | HumanGate tree i governance tickets dzialaja; globalne wymuszanie dla kazdego strategicznego flow wymaga dalszych testow i dopiecia. |
| W8 Memory | PARTIAL | health/search/stats dzialaja, ale indeks i evidence sa puste; brak dowodu, ze memory realnie zmienia nowe planowanie. |
| W9 Skills | PARTIAL | runtime stats pokazuja zaladowane skills, ale catalog stats = 0; reuzycie skills w planowaniu nie jest jeszcze dowiedzione. |
| W10 Intake | PARTIAL/LIVE | projekty i intake-like surfaces istnieja; pelne pytania startowe i klasyfikacja wymagaja E2E. |
| W11 Model Council | LIVE/PARTIAL | role, rangi, wagi, sentinele, podpis krytyka, consensus i consolidation dzialaja; polityka koszt/API nie jest wystarczajaco widoczna. |
| W12 Source of Truth / Ksiega | PARTIAL | ksiegi i project canon endpoints istnieja, ale pusty stan nie dowodzi pelnego SoT lifecycle. |
| W13 Masterplan | PARTIAL | planning/masterplan endpoints istnieja; freeze/Human Gate wymaga dalszego E2E od projektu do wykonania. |
| W14 Quality Gates | PARTIAL | test-center i quality stats dzialaja, ale stats puste; human-like test suite wymaga utrzymania jako realny gate. |
| W15 Ontology | PARTIAL | warstwa opisana i endpointy/route istnieja; potrzebny twardszy kontrakt domenowy dla Project/CouncilSession/HumanGateTicket/SoTEntry. |
| W16 Worker Execution | LIVE/PARTIAL | workers API dziala, poprawiono topology alias; brak dowodu pelnego rozproszonego builda z modulami masterplanu. |
| W17 Integrations / External Actions | PARTIAL/LIVE | funding/mobile/VPS/container/device/lab endpoints istnieja; external submit/production gate wymaga E2E. |
| W18 Operator Console | PARTIAL | `/api/v1/terminal/health` dziala i UI nie crashuje; `broadcaster_wired=false`, a zasada "klik generuje komende W18" nie jest jeszcze dowiedziona globalnie. |
| W19 Audit / Closure / Learning | PARTIAL | audit/governance evidence istnieje; memory snapshot i lessons learned nie sa jeszcze dowiedzione jako automatyczne zamkniecie projektu. |

## Status 12 warstw roboczych

| Warstwa robocza | Status |
|---|---|
| Canon Layer | PARTIAL |
| Model Council Layer | LIVE/PARTIAL |
| Memory Layer | PARTIAL |
| Skills Layer | PARTIAL |
| Planning Layer | PARTIAL |
| Human Gate / Governance Core | LIVE/PARTIAL |
| Coordination Layer | PARTIAL |
| Worker Layer | LIVE/PARTIAL |
| Integration Layer | PARTIAL/LIVE |
| Operator Layer | PARTIAL |
| Operator Mobile Layer | PARTIAL/LIVE |
| Output Layer | PARTIAL |

## Najwazniejsze ustalenia

1. **Mobile nie jest juz tylko planem.**

   Istnieje backend `operator_mobile`, endpointy `/api/v1/mobile/*` i frontend `/operator-mobile`. Status: PARTIAL/LIVE, nie `planned-only`.

2. **Funding jest realnym pionem kodowym.**

   `/api/v1/funding/*` ma health, sources, company profile, calls, ideas, matching, scoring, application/submission surfaces. Finalny submit nadal wymaga osobnego E2E governance proof.

3. **Council jest rzeczywisty runtime'owo.**

   Nie jest tylko tekstem. Sa role, rangi, wagi, podpisy krytyka, sentinele i consensus. Luka: widocznosc kosztu/model-provider gate.

4. **Human Gate dziala jako mechanizm, ale globalnosc wymuszenia jest nieudowodniona.**

   Drzewo decyzji i unified governance tickets dzialaja. Trzeba jeszcze przejsc caly projektowy flow i sprawdzic, czy kazda strategiczna zmiana rzeczywiscie wpada do Human Gate.

5. **Memory i Skills sa najbardziej puste operacyjnie.**

   Endpointy istnieja, ale runtime pokazywal puste indeksy/katalogi. To jest glowna roznica miedzy "system ma pamiec/skills" a "system uczy sie i dobiera skills".

6. **UI coverage script jest konserwatywny.**

   Oznacza wiele tras jako `UI_ONLY_OR_STATIC`, bo nie zawsze wykrywa API wywolane przez komponenty/hooki. Tego nie wolno czytac jako pewny brak integracji, tylko jako liste do recznego sprawdzenia.

7. **Repo jest bardzo duze i zabrudzone stanem lokalnym.**

   Wczesniejszy cleanup ograniczyl smieci, ale worktree nadal ma duzo zmian i usuniec niezaleznych od tego audytu. Nie wykonywac masowego `git clean` ani resetu bez osobnej decyzji.

8. **OpenAPI ma duplikaty `operation_id` w orchestration routes.**

   Backend dziala, ale log runtime pokazuje ostrzezenia FastAPI o zduplikowanych `operation_id` dla wielu endpointow `sylion.api.orchestration_routes`. To moze psuc generatory klientow API i powinno byc uporzadkowane osobnym patchem.

## Drift wzgledem modelu roboczego

| Teza kanonu | Stan runtime |
|---|---|
| AEIS sam dobiera modele i zespoly | Czesc mechanizmow istnieje, ale pelny auto-scaling zespolow od intake do masterplanu nie jest dowiedziony. |
| Local-first jako domyslna topologia | Backend dziala lokalnie, ale Council moze uzyc fallbacku API. Wymaga mocniejszej polityki lub widocznego gate. |
| Human Gate dla kosztow/produkcji/external | Ticketing dziala; globalne wymuszenie na kazdym module wymaga E2E i testow regresji. |
| Memory szuka podobnych projektow i wplywa na plan | Search API dziala, ale indeks pusty i brak dowodu wplywu na planning. |
| Skills sa kompetencjami wykonawczymi | Runtime pokazuje skills, ale catalog pusty; trzeba udowodnic binding do projektow/modulow. |
| W18 determinuje wszystko | Terminal health dziala, ale broadcaster nie jest spiety i klik -> komenda nie jest jeszcze globalnym kontraktem UI. |
| Closure zapisuje learning | Audyt i ticket evidence istnieja, lecz automatyczny memory snapshot/lessons learned po final approval wymaga implementacyjnego dowodu. |

## Backlog naprawczy

### P0

- Wprowadzic twardy `model_api_usage_gate` dla Council/Planning, ktory respektuje local-first, koszt, data sensitivity i provider policy przed wywolaniem zewnetrznego modelu.
- Spiac unified governance tickets z kazdym strategicznym przejsciem: direction, SoT freeze, masterplan freeze, runtime expansion, cost over threshold, production, external submit, final closure.
- Zrobic E2E projektu: intake -> Council variants -> Human Gate direction -> SoT -> Human Gate SoT -> Masterplan -> Human Gate Masterplan -> worker execution -> Quality Gate -> final approval -> Memory snapshot.
- W18: ustawic kontrakt, ze glowne akcje UI emituja komende/event W18; doprowadzic `broadcaster_wired` do true albo jawnie opisac tryb bez broadcastu.

### P1

- Zasilic Memory realnymi snapshotami i podobienstwem projektow; dodac test, ze memory zmienia rekomendacje planning.
- Zasilic Skills catalog i dodac binding skills -> project/module/team; sprawdzic skutecznosc w planning.
- Dodac testy final submit dla Funding z blokada Human Gate przed submission.
- Rozbudowac coverage extractor o sledzenie komponentow i hookow, nie tylko page.tsx.
- Przejsc trasy oznaczone `NEEDS_REVIEW`: `/autonomy`, `/coherence-guard`, `/onboarding`, `/test-center/*`, `/workspace-defaults`.

### P2

- Dodac health/readiness endpoints dla lab/runtime extensions tam, gdzie obecnie istnieja tylko zasoby listujace.
- Ujednolic polskie nazewnictwo UI i przywrocic help-tip `?` dla operatora.
- Ograniczyc puste/demo dane na stronach operatorskich albo oznaczyc je jawnie jako brak runtime data.
- Dodac test regresji dla `memorySearchSimilar`, zeby frontend nie wrocil do starego `/api/v1/memory/search`.
- Uporzadkowac zduplikowane `operation_id` w `sylion.api.orchestration_routes`, zeby OpenAPI bylo stabilne dla klientow i narzedzi audytu.

## Testy wykonane

- `python -m pytest tests\test_worker_routes.py -q` - 2 passed
- `python -m pytest tests\test_architecture_layers_routes.py -q` - 6 passed
- `npx tsc --noEmit` - passed
- runtime HTTP probe - 33/33 checked endpoints returned `200`
- Playwright UI probe - 10/10 pages returned `200`, 0 console/page/request failures
- corrected governance flow probe - Council, HumanGate and unified governance ticket passed

## Konkluzja

Kanon W1-W19 jest juz reprezentowany w kodzie i runtime, ale nadal trzeba odroznic "modul istnieje" od "modul rzadzi przeplywem". Najmocniejsze obszary runtime to API surface, Council mechanics, Human Gate tree/tickets, Funding API, Mobile API i worker/runtime endpoints. Najslabsze obszary wzgledem modelu roboczego to globalne wymuszenie governance, realna adaptacyjna Memory, realne Skills binding, W18 jako centralny command bus oraz pelny projektowy E2E od intake do closure.
