# Execution Live Workers PASS1/PASS2

Data: 2026-05-13

## Zakres

Naprawiony i przetestowany zakres:

- `/execution-start` pokazuje panel `Live smoke workers`;
- operator moze kliknac `Start live`, `Stop live`, `Odswiez`;
- start uruchamia lokalne procesy `windows_process_group`;
- stop zatrzymuje uruchomione procesy;
- wpisy W18 maja centralny `command_route`:
  - `live_spawn_workers` jako `TWO_PHASE`, D3, Human Gate;
  - `stop_live_workers` jako `IMMEDIATE`, D1;
- flow nie uruchamia Dockera, VPS ani kosztow zewnetrznych.

## Evidence

- JSON: `evidence/json/live_workers_dashboard_pass12_2026-05-13T22-40-42-350Z.json`
- Screenshots: `evidence/screenshots/live_workers_2026-05-13T22-40-42-350Z_*.png`
- Router audit: `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`
- Projekt kontrolny: `project_97bfd7670d3d`

## Wynik

| PASS | Start | Stop | Console | Request failures | Route actions |
|---|---:|---:|---:|---:|---|
| PASS1 | 2 running | 0 running | 0 | 0 | `live_spawn_workers`, `stop_live_workers` |
| PASS2 | 2 running | 0 running | 0 | 0 | `live_spawn_workers`, `stop_live_workers` |

## Zamrozony zakres

Mozna zamrozic:

- UI controls dla live smoke worker start/stop na `/execution-start`;
- backend endpoints `/phase32/live-spawn-workers` i `/phase32/stop-live-workers` w trybie smoke/local;
- widoczny status PID/log lines/state w dashboardzie;
- W18 route evidence dla start/stop live workers.

Nie wolno jeszcze zamrazac:

- calego execution dashboardu;
- dispatch/cancel dla dlugich runow;
- faz 34-41 jako pelnego E2E;
- produkcyjnego deploy;
- Docker/VPS live spawn.

## Reguly utrzymania

- `Start live` nie moze byc aktywny, gdy istnieja uruchomione sesje.
- `Stop live` musi zostawic `running=0`.
- D3 live spawn wymaga governance ticket ID.
- D1 stop live moze byc `IMMEDIATE`, ale musi miec centralny audit route.
- Console errors albo request failures blokuja freeze.
