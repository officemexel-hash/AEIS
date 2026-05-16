# Workers Registry Dashboard PASS12

Data: 2026-05-14

Status: `PASS_2X`

Zakres zamrozenia: `/workers` dla rejestracji workera, heartbeatu, rebalansu, widoku per projekt, wyswietlania topologii i usuniecia workera.

## Dowody

- Repro topologii przed poprawka: `evidence/json/workers_topology_repro_2026-05-14T10-20-56-040Z.json`
- PASS12 po poprawkach: `evidence/json/workers_registry_pass12_2026-05-14T10-27-39-815Z.json`
- Screenshoty PASS: `evidence/screenshots/workers_pass*_2026-05-14T10-27-39-815Z.png`

## Naprawione bledy

| ID | Objaw | Przyczyna | Poprawka | Retest |
|---|---|---|---|---|
| `DASH-E2E-011` | API zwracalo topologie, UI pokazywal pusta sekcje. | Komponent czytal znieksztalcony lokalny klucz topologii zamiast `topologiesData.topologies`. | Ujednolicono nazwy i mapowanie na `topologies`. | PASS1 i PASS2 widza seeded topology. |
| `DASH-E2E-012` | `DELETE /workers/{id}` usuwal workera w API, ale UI pokazywal blad JSON i stalego workera. | Shared request helper zawsze parsowal body przez `res.json()`, mimo `204 No Content`. | Wszystkie lokalne request helpery znalezione w tym audycie zwracaja `undefined` dla pustego 2xx body. | PASS1 i PASS2 usuwaja workera z API i UI bez error banneru. |

## PASS 1

- `FreezeTopologyWorkers-2026-05-14T10-27-39-815Z` widoczna w `/workers`.
- `Freeze-Worker-1-2026-05-14T10-27-39-815Z` zarejestrowany przez formularz UI.
- Heartbeat zapisany w API.
- `Rebalansuj` klikniety bez error banneru.
- Worker widoczny w zakladce `Per projekt` dla `project_97bfd7670d3d`.
- Worker usuniety z API i z dashboardu.

## PASS 2

- Ten sam scenariusz powtorzony dla `Freeze-Worker-2-2026-05-14T10-27-39-815Z`.
- `console_errors=0`
- `hard_request_failures=0`
- `api_failures=0`

## Screenshoty

![PASS2 topology visible](evidence/screenshots/workers_pass2_topology_visible_2026-05-14T10-27-39-815Z.png)

![PASS2 registered](evidence/screenshots/workers_pass2_registered_2026-05-14T10-27-39-815Z.png)

![PASS2 per project](evidence/screenshots/workers_pass2_per_project_2026-05-14T10-27-39-815Z.png)

![PASS2 deleted](evidence/screenshots/workers_pass2_deleted_2026-05-14T10-27-39-815Z.png)

## Granice freeze

- Zamrozony jest lifecycle workera w dashboardzie `/workers`.
- Zamrozony jest odczyt topologii z `/api/v1/workers/topology/all`.
- Nie zamrozono tworzenia/edycji topologii z UI, bo dashboard nie ma osobnej kontrolki create/update topology.
- Nie zamrozono `/orchestration` drilldown; to zostaje kolejnym flow.
