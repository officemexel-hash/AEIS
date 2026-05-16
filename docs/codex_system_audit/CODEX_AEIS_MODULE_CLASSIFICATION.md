# CODEX AEIS MODULE CLASSIFICATION

**Status:** wersja robocza 0.1  
**Cel pliku:** podzielic realne obszary AEIS na `CORE`, `EXTENSIONS`, `EXPERIMENTAL`, `DUPLICATE`, `LEGACY` oraz osobno oznaczyc rzeczy `PLANNED`  
**Uwaga:** to jest klasyfikacja logicznych modulow i grup modulow, a nie jeszcze finalny werdykt dla kazdego pojedynczego pliku `.py`

## 1. Zasada klasyfikacji

Klasyfikuje tu nie wszystko wedlug "czy istnieje kod", tylko wedlug pytania:

- czy ten obszar jest dzis konieczny, zeby obecny AEIS w ogole dzialal
- czy jest sensownym rozszerzeniem
- czy jest dopiero eksperymentem albo warstwa niedowiedziona
- czy dubluje inne planes
- czy jest juz legacy

## 2. CORE

To sa obszary, bez ktorych dzisiejszy AEIS traci swoj glowny spine.

| Modul / grupa | Klasyfikacja | Dowod / uzasadnienie |
|---|---|---|
| API aggregation (`sylion.api.router`, `app.py`) | CORE | glowny runtime backend montujacy wszystkie rodziny API |
| Workspace / Project Kickoff (`ai_workspace_routes.py`) | CORE | najmocniej potwierdzony flow: kickoff -> canon -> masterplan -> Human Gate -> launch |
| Project registry (`projects_routes.py`, `/api/v1/projects`) | CORE | projekty sa realnym bytem operatorskim, nie tylko skutkiem ubocznym kickoff |
| Project execution (`project_mode.engine`, `project_mode.store`) | CORE | realny execution engine uruchamiany przez `workspace launch` |
| Governance (`governance/*`, `governance_routes.py`) | CORE | globalne gates, policies, proposals, council workflows |
| Workspace Human Gate | CORE | to przez niego realnie przeszedl probe operatorski |
| Memory (`memory/*`, `memory_routes.py`) | CORE | subsystem istnieje i jest jednym z glownych filarow kanonu, mimo fragmentacji |
| Skills (`skills/*`, `skills_routes.py`) | CORE | subsystem kodowy, API i UI jest zywy, nawet jesli integracja z glownym loop jest nierowna |
| Worker fleet (`worker/*`, `worker_routes.py`) | CORE | registry, assignmenty i heartbeat sa realne |
| Operator Console Next.js (`src/sylion-frontend/src/app/(app)`) | CORE | to jest glowna nowa warstwa operatorska |
| Contracts / core control modules (`core/*`, `contracts/*`) | CORE | to nadal glowny kernel kontraktowy i kontrolny systemu |
| Security backbone (`security/*`) | CORE | warstwa przekrojowa, bez ktorej governance i runtime nie sa bezpieczne |

## 3. EXTENSIONS

To sa obszary sensowne, realne i wartosciowe, ale nie wszystkie naleza do minimalnego spinu AEIS.

| Modul / grupa | Klasyfikacja | Uwagi |
|---|---|---|
| Funding Autopilot (`funding_autopilot/*`) | EXTENSIONS | strategiczny pion domenowy; dojrzaly, ale nie jest minimalnym spine calego AEIS |
| Observability (`observability/*`) | EXTENSIONS | realny subsystem, dzis lokalny/dev-plane |
| Monitoring (`monitoring/*`) | EXTENSIONS | sensowne rozszerzenie operacyjne |
| Quality (`quality/*`) | EXTENSIONS | wspiera gotowosc i walidacje |
| Rebuild (`rebuild/*`) | EXTENSIONS | wzmacnia rebuildability i cutover |
| Execution helpers (`execution/*`) | EXTENSIONS | realne, ale nie wszystkie sciezki sa glownym runtime spine |
| Integration (`integration/*`) | EXTENSIONS | potrzebne dla styku ze swiatem, ale nierowno dojrzale |
| Infra (`infra/*`) | EXTENSIONS | wspiera runtime i topologie |
| Devices (`devices/*`) | EXTENSIONS + LABORATORY | swiadome rozszerzenie integracyjne |
| VPS (`vps/*`) | EXTENSIONS + LABORATORY | swiadome rozszerzenie runtime |
| Container (`container/*`) | EXTENSIONS + LABORATORY | swiadome rozszerzenie runtime |
| Cellular (`cellular/*`) | EXTENSIONS + LABORATORY | intencjonalny modul laboratoryjny, nie przypadkowy balast |
| SDR (`sdr/*`) | EXTENSIONS + LABORATORY | intencjonalny modul laboratoryjny, nie przypadkowy balast |

## 4. EXPERIMENTAL

To sa obszary, ktore maja znaczenie koncepcyjne, ale ich dzisiejsza rola runtime jest niepelna albo niejednoznaczna.

| Modul / grupa | Klasyfikacja | Dlaczego |
|---|---|---|
| AEIS self-evolution / autonomy package (`aeis/*`) | EXPERIMENTAL | zgodne z wizja kanonu, ale niepotwierdzone jako glowny runtime spine calego systemu |
| Szeroka warstwa cognitive (`cognitive/*`) | EXPERIMENTAL | realny kod istnieje, ale czesc tej warstwy jest szerzej deklarowana niz dowiedziona end-to-end |
| gRPC / `grpc_stubs/*` | EXPERIMENTAL | istnieje transport i stubs, ale realna dominujaca komunikacja jest REST-owa |

## 5. DUPLICATE

Tu trafia nie tyle pojedynczy plik, ile funkcjonalne dublowanie planes.

| Duplikat / klaster | Klasyfikacja | Dowod |
|---|---|---|
| Human Gate: `workspace humangate` vs globalne `gates/human` | DUPLICATE | dwa zywe planes approval zamiast jednego wspolnego truth plane |
| Funding approvals vs globalny Human Gate | DUPLICATE | funding ma lokalny approval plane obok globalnego governance |
| Operator Console Next.js vs legacy dashboard | DUPLICATE | dwa rownolegle stacki operatorskie |
| Governance/core/security duplicate concepts | DUPLICATE | decyzje, evidence, policy i rollback maja slady powtorzen miedzy rodzinami modulow |

## 6. LEGACY

To sa obszary, ktore nadal istnieja, ale nie powinny byc dalej traktowane jako glowny truth plane.

| Modul / grupa | Klasyfikacja | Uwagi |
|---|---|---|
| `src/sylion-pipeline/dashboard/*` | LEGACY | stary dashboard Python zyje obok nowego operator console |
| `SYLION_Dashboard_V5_ClaudeCode_Package` addon | LEGACY / ARCHIWALNE | zewnetrzny pakiet pomocniczy, nie glowny runtime spine |

## 7. PLANNED / NIEZAIMPLEMENTOWANE

To nie jest osobna kategoria z listy glownych pieciu, ale musi byc odnotowana.

| Modul / grupa | Status | Dowod |
|---|---|---|
| Operator Mobile / `operator_mobile` | PLANNED / NIEZAIMPLEMENTOWANY | brak trafien backend/frontend w `src/`, istnieje tylko prompt `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt` |

## 8. Najwazniejsze roznice wobec klasyfikacji Claude'a

Najwazniejsze korekty Codexa na ten moment:

1. `project_mode` nie powinien byc traktowany jak cienki eksperyment.
   To realny execution spine uruchamiany przez `workspace launch`.

2. `funding_autopilot` nie powinien byc spychany do lekkiej kategorii "do dopisania".
   To juz dzis mocny pion domenowy.

3. `cellular`, `sdr`, `vps`, `container`, `devices.artifact_deployer` nie sa "pomylka kanonu".
   To swiadome rozszerzenia laboratoryjne, ktore trzeba opisac, a nie kasowac.

4. Glowny problem dzis nie brzmi "brak modulow", tylko:
   - za duzo planes prawdy
   - za duzo rozszczepien
   - za duzo dublowania operator/governance/memory truth

## 9. Wniosek

Najuczciwszy obraz klasyfikacyjny na teraz jest taki:

- AEIS ma juz mocny `CORE`, zbudowany wokol `workspace`, `project_mode`, `governance`, `memory`, `skills`, `workers` i operator console
- ma duzy zestaw wartosciowych `EXTENSIONS`, z fundingiem i labami na czele
- ma kilka `EXPERIMENTAL` warstw, glownie tam, gdzie kanon wyprzedza runtime
- ma realne `DUPLICATE` planes, zwlaszcza w governance i operatorce
- ma wyrazny `LEGACY` w postaci starego dashboardu
- ma `PLANNED` mobile, ktore jest juz dobrze opisane w promptach, ale nie istnieje jeszcze jako kod
