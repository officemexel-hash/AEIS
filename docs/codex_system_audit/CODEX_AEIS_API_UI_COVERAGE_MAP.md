# CODEX AEIS API UI COVERAGE MAP

## Re-Audyt 2026-04-25

Aktualny, wiążący stan po pełnym re-audycie Phase 2 jest opisany w:

- [CODEX_AEIS_FULL_REAUDIT_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_REAUDIT_2026_04_25.md)

Najważniejsze korekty względem starej mapy:

- `Workspace` nie jest już `LIVE_VERIFIED`, bo `workspace/humangate/*` i `workspace/ideas/*` mają realne `500`.
- `Projects` UI nie jest uczciwie live względem `/api/v1/projects`; ekran jest podpięty pod `plans/workflows/jobs`, nie pod prawdziwy `projects plane`.
- `Workers` i `Observability` nie są `LIVE_VERIFIED`; w browser re-audycie oba surface'y zwracają `500` przez brakujące exporty hooków.
- `Operator Mobile` nie jest już `PROMPT_ONLY`; backend bridge i UI istnieją, ale status to `PARTIAL`, bo queue routing per operator nie działa, a UI potrafi maskować błędy fallbackiem.
- `Skills` jest lepsze niż w starej mapie: runtime ładuje `3` skills, ale registry/runtime nadal są rozdzielone.
- `Memory` jest lepsze niż w starej mapie: index runtime żyje, ale publiczny surface nadal ma `404` i split API.

**Status:** wersja robocza 0.1  
**Cel pliku:** pokazac, ktore surface'y operatora sa realnie podlaczone do API i runtime, a ktore pozostaja tylko shellami albo powierzchniami niezweryfikowanymi  
**Zrodla:** frontend `app/(app)`, `src/lib/api/client.ts`, `api/router.py`, probe runtime 2026-04-24

## 1. Snapshot strukturalny

Na ten moment potwierdzone:

- `55` route pages w `src/sylion-frontend/src/app/(app)`
- `368` sciezek API uzywanych lub deklarowanych w `src/sylion-frontend/src/lib/api/client.ts`
- `87` router mounts w backendowym `src/sylion-pipeline/sylion/api/router.py`

Wniosek:

- nowy operator surface jest szeroki
- klient API jest wiekszy niz aktualnie runtime-verified coverage
- coverage audit musi odroznic `istnieje w kliencie` od `potwierdzone w runtime`

## 2. Mapa glownych surface'ow

| Surface | UI route | API family | Runtime | Status | Uwagi |
|---|---|---|---|---|---|
| Workspace | `/workspace` | `/api/v1/workspace/*`, `/api/v1/projects/*` | `200` UI + zywe kickoff/approve/launch + frozen plan dla `project_a81b2c935d6c` | LIVE_VERIFIED | najmocniej potwierdzony flow AEIS |
| Projects | `/projects` | `/api/v1/projects/*` | `200` UI + `GET /projects` = 10 rekordow + detail runtime dla `project_a81b2c935d6c` | LIVE_VERIFIED | rejestr projektow i etapow jest realny |
| Workers | `/workers` | `/api/v1/workers/*`, `/api/v1/workers/topology/*` | `200` UI + sekwencyjny CRUD/heartbeat verified | LIVE_VERIFIED | domyslnie pusta flota; topologie puste |
| Observability | `/observability` | `/api/v1/observability/*` | `200` UI + roundtrip metrics/logs/traces | LIVE_VERIFIED | LocalLogBackend, czyli dev-plane bez trwalego backendu |
| Council | `/workspace` -> `CouncilPanel` | `/api/v1/workspace/council/*` | `GET /workspace/council/sessions` = `200` | PARTIAL | surface zyje, sesje puste dopoki operator ich nie utworzy |
| Human Gate projektowy | `/workspace` -> `HumanGatePanel` | `/api/v1/workspace/humangate/*` | `200`, realne sesje i drzewo | LIVE_VERIFIED | osobny plane od globalnych requestow |
| Funding | `/funding` | `/api/v1/funding/*` | `200` UI + zywe dane submission/approval | LIVE_VERIFIED | bogata powierzchnia operatorska, nie stub |
| Skills | `/skills` | `/api/v1/skills/*` | `200` UI + registry live + runtime execute broken | PARTIAL | UI i registry zyja, ale runtime ma `loaded_skills=0` |
| Governance | `/governance` | `/api/v1/governance/*`, `/api/v1/gates/*` | `200` UI + proposals/gates/policies = `200` | LIVE_VERIFIED | zywa warstwa, ale nie jeden wspolny plane z workspace |
| Memory | brak jednej dedykowanej glownej strony pamieci | `/api/v1/memory/*` | `index/stats`, `self-model`, `evidence-store` = `200`, manualne index/search dziala, `evidence/stats` = `404` | API_ONLY / PARTIAL | globalne API zyje, ale brak dominujacego UI i trwałego startup binding |
| Cellular | `/cellular` | `/api/v1/cellular/*` | `200` UI + `GET /cellular/ran` = `0` stackow | PARTIAL | zywy lab surface, aktualnie pusty runtime |
| SDR | `/sdr` | `/api/v1/sdr/*` | `200` UI + `GET /sdr/devices` = `0` urzadzen | PARTIAL | zywy lab surface, aktualnie pusty runtime |
| Devices | `/devices` | `/api/v1/devices/*` | `200` UI + discovery/registry = `0` | PARTIAL | zywy lab/device surface, aktualnie bez aktywnych urzadzen |
| VPS | brak dedykowanej glownej strony | `/api/v1/vps/*` | `GET /vps/providers` = `0` | API_ONLY / PARTIAL | runtime provider plane istnieje, ale jest pusty |
| Container | brak dedykowanej glownej strony | `/api/v1/container/*` | `GET /container/stats` = zera | API_ONLY / PARTIAL | runtime container plane istnieje, ale jest pusty |
| Operator Mobile | brak | brak trafien w `src/` dla `operator_mobile` lub `/operator-mobile` | brak | PLANOWANY / NIEZAIMPLEMENTOWANY | obecny tylko jako prompt i kanon docelowy |
| Legacy dashboard | oddzielny Python stack | nie przez nowy Next.js | nieaudytowany browserowo w tej turze | LEGACY | drugi operator stack rownolegly do Next.js |

## 3. Potwierdzone API settings plane dla modeli i operatora

W `workspace` potwierdzone zostaly zywe endpointy:

- `GET /api/v1/workspace/settings/keys`
- `GET /api/v1/workspace/settings/runtime/llm`
- `GET /api/v1/workspace/settings/hierarchies`
- `GET /api/v1/workspace/settings/council-members`
- `GET /api/v1/workspace/books`
- `GET /api/v1/workspace/council/sessions`

Wniosek:

- frontend nie trafia w martwe nazwy; settings plane jest realny
- listy council members i hierarchies sa puste, ale sam plane istnieje

## 4. Najwazniejsze luki coverage

### 4.1. UI zyje, ale nie wszystko jest runtime-zweryfikowane

To, ze route page zwraca `200`, nie oznacza jeszcze:

- poprawnego data loading
- poprawnego mutation flow
- poprawnego Human Gate
- poprawnego audit trail

Najbardziej dojrzale surface'y na teraz:

- `workspace`
- `funding`
- `governance`
- `projects`

Najmniej potwierdzone:

- bezposrednie UI dla globalnego memory plane
- UI dla globalnych human gate requests
- UI dla operator mobile
- pelny runtime execution flow skilli

### 4.2. Globalny Human Gate nie dominuje operator surface

Probe runtime pokazuja:

- `GET /api/v1/workspace/humangate/sessions` = realne sesje
- `GET /api/v1/gates/human/requests` = pusty zbior

Wniosek:

- operator surface dla projektu przechodzi przez `workspace/humangate`
- globalny human request plane nie jest obecnie glownym miejscem pracy operatora

### 4.3. Funding ma osobny approval plane

Funding page i funding client korzystaja z:

- `submission/prepare`
- `submission/fill`
- `submission/save-draft`
- `submission/request-approval`
- `submission/submit`
- `submission/sessions`
- `submission/approvals`

Wniosek:

- to nie jest cienki UI-only ekran
- ale approval idzie przez funding-local event plane, nie przez globalne `gates/human/requests`

### 4.4. Mobile nie ma jeszcze nawet cienkiego bridge backend/frontend

Przeszukanie `src/sylion-pipeline` i `src/sylion-frontend/src` nie wykazalo:

- katalogu `operator_mobile`
- route'ow `/api/v1/operator-mobile/*`
- route page pod mobile approvals
- kodu `follow-me`, `device binding`, `approval token`

Wniosek:

- mobile nie jest dzis powierzchnia operatorska
- pozostaje celem kanonicznym, ale nie elementem zywej coverage map

## 5. Wnioski praktyczne

Najuczciwszy opis coverage na teraz brzmi:

- frontend Next.js jest szeroki i realnie spiety z wieloma rodzinami API
- `workspace`, `funding`, `governance` i `skills` maja zywe surface'y operatorskie
- coverage jest nierowne: czesc ekranow jest juz produktem, czesc tylko szeroka deklaracja klienta API
- najwiekszy problem nie lezy dzis w samym braku ekranow, tylko w tym, ze kilka ekranow pracuje nad rozdzielonymi planes:
  - workspace Human Gate
  - global gates
  - funding-local approvals
  - global memory
  - per-project runtime DB

## 6. Dowody wizualne z tej tury

Zapisane screenshoty operatorskie:

- `output/playwright/workspace-overview.png`
- `output/playwright/funding-overview.png`
- `output/playwright/governance-overview.png`
- `output/playwright/projects-overview.png`
- `output/playwright/project-workspace-flow-detail.png`
- `output/playwright/skills-overview-live.png`
- `output/playwright/workers-overview-live.png`
- `output/playwright/observability-overview-live.png`

Uwagi:

- screenshoty zostaly wykonane na zywych ekranach Next.js podczas probe runtime
- trafia pozniej do nowej ksiegi systemowej jako material pomocniczy, nie jako jedyne zrodlo prawdy
