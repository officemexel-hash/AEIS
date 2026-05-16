# W14 Agent Team Theater — dashboard zespołu agentów
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Moduł: `sylion.aeis.testing.agent_theater` + `sylion.api.agent_theater_routes`
> Frontend: `src/sylion-frontend/src/app/(app)/test-center/theater/`
> Commits: `ec2205a9` (E12-BE) + `50773c5a` (E12-FE)

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [AgentTheaterAggregator — metody](#4-agenttheateraggregator--metody)
5. [REST endpoints (6)](#5-rest-endpoints-6)
6. [Frontend — strona Theater](#6-frontend--strona-theater)
7. [Przykład użycia](#7-przykład-użycia)
8. [Weryfikacja](#8-weryfikacja)
9. [Rozwiązywanie problemów](#9-rozwiązywanie-problemów)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Agent Team Theater to widok read-only stanu zespołu modeli AI i infrastruktury testowej
W14 w czasie rzeczywistym. Agregator zbiera dane z różnych modułów W14 (OntologyStore,
GuardianRegistry) i eksponuje je przez 6 REST endpointów + stronę dashboard.

Operator widzi: kto (model/task) nad czym pracuje, stan 13 guardianów, obciążenie
modeli lokalnych oraz aktualny stan sesji Rady i przebiegu naprawy findingu.

`AgentTheaterAggregator` jest **czysto read-only** — nigdy nie mutuje stanu.

---

## 2. Architektura

```
testing/agent_theater.py           AgentTheaterAggregator
  get_topology()                   3 modele + otwarte findingi + edges
  get_council_session_view(sid)    sesja Rady (stub w E12)
  get_repair_theater(fid)          R-status + Loop Governor budget
  get_guardian_status()            13 guardianów health snapshot
  get_local_models_status()        qwen/gpt-oss workload

api/agent_theater_routes.py        FastAPI router
  GET /api/v1/agent-theater/topology
  GET /api/v1/agent-theater/council/{session_id}
  GET /api/v1/agent-theater/repair/{finding_id}
  GET /api/v1/agent-theater/guardians
  GET /api/v1/agent-theater/locals
  GET /api/v1/agent-theater/health

test-center/theater/page.tsx       Dashboard (E12-FE)
  Topology card, Guardians card, Local Models card, 5s auto-refresh

tests/aeis/testing/test_agent_theater.py   9 testów
```

Router zarejestrowany w `app.py` z prefixem `/api/v1/agent-theater`, tag `agent-theater`.
Po E12: łączna liczba tras: 1541 (1535 bazowych + 6 nowych).

---

## 3. Konfiguracja

| Zmienna | Default | Opis |
|---------|---------|------|
| `SYLION_W14_DB` | `sylion_aeis.db` | Ścieżka do SQLite — lazy-construct per request |

Aggregator tworzony lazy per request przez `_aggregator()` helper w routes:

```python
def _aggregator():
    db_path = os.environ.get("SYLION_W14_DB", "sylion_aeis.db")
    store = OntologyStore(db_path=db_path)
    return AgentTheaterAggregator(ontology=store)
```

`guardian_registry` opcjonalny: gdy `None`, `register_all_guardians(ontology)` wywoływane
automatycznie w konstruktorze.

---

## 4. AgentTheaterAggregator — metody

### `get_topology() -> dict`

Snapshot aktywnych aktorów i krawędzi (edges) w czasie rzeczywistym.

E12 MVP: 3 modele bazowe + otwarte findingi jako task-actors.

```python
result = agg.get_topology()
# {
#   "as_of": 1745667842.3,
#   "actors": [
#     {"id": "claude-opus-4-7", "name": "Claude Opus 4.7",
#      "role": "test_architect", "status": "working", "kind": "model"},
#     {"id": "gpt-5-codex", "name": "GPT-5 Codex",
#      "role": "repair_controller", "status": "idle", "kind": "model"},
#     {"id": "kimi-k2", "name": "Kimi K2",
#      "role": "ui_human_tester", "status": "idle", "kind": "model"},
#     # + otwarte findingi jako kind="task"
#   ],
#   "edges": [
#     {"source": "gpt-5-codex", "target": "finding_<id>", "kind": "works_on"}
#   ]
# }
```

Modele bazowe i ich role:

| Model | ID | Rola |
|-------|----|------|
| Claude Opus 4.7 | `claude-opus-4-7` | `test_architect` |
| GPT-5 Codex | `gpt-5-codex` | `repair_controller` |
| Kimi K2 | `kimi-k2` | `ui_human_tester` |

### `get_council_session_view(session_id: str) -> dict`

Widok sesji Rady: głosy, podpisy, sentinel status.
E12 MVP: zwraca stub jeśli sesja nie znaleziona.

```python
result = agg.get_council_session_view("cs-42")
# {
#   "session_id": "cs-42",
#   "participants": [...],
#   "votes": {...},
#   "sentinels": {"cost": "pass", "security": "pass"}
# }
```

### `get_repair_theater(finding_id: str) -> dict`

Status naprawy findingu + budżet Loop Governor:

```python
result = agg.get_repair_theater("f-001")
# {
#   "finding_id": "f-001",
#   "r_status": "REPAIRING",
#   "attempts_used": 3,
#   "attempts_max": 9,        # limit Loop Governor
#   "files_changed": 2,
#   "diff_lines": 45,
#   "time_in_loop_s": 180.0,
#   "loop_status": "ACTIVE"   # ACTIVE | BLOCKED | CLOSED
# }
```

Gdy finding nie znaleziony: `{"error": "finding not found: <id>"}` → HTTP 404.

### `get_guardian_status() -> list[dict]`

13 guardianów z health snapshot:

```python
guardians = agg.get_guardian_status()
# [
#   {"guardian_id": "GeoFenceGuard", "status": "GREEN",
#    "alerts_24h": 0, "last_check": 1745667842.3},
#   {"guardian_id": "CostSentinel", "status": "YELLOW",
#    "alerts_24h": 2, ...},
#   ...
# ]
```

Status: `GREEN | YELLOW | RED` per guardian.

### `get_local_models_status() -> list[dict]`

Workload modeli lokalnych (E12 MVP: config-derived data):

```python
locals_status = agg.get_local_models_status()
# [
#   {"model_id": "qwen2.5-coder", "status": "idle", "queue_depth": 0},
#   {"model_id": "qwen3.5-instruct", "status": "idle", "queue_depth": 0},
#   {"model_id": "gpt-oss", "status": "idle", "queue_depth": 0}
# ]
```

---

## 5. REST endpoints (6)

Wszystkie endpointy GET, prefix `/api/v1/agent-theater`:

| Endpoint | URL | Opis | HTTP error |
|----------|-----|------|-----------|
| topology | `GET /topology` | Snapshot aktorów + krawędzi | 500 |
| council view | `GET /council/{session_id}` | Widok sesji Rady | 500 |
| repair theater | `GET /repair/{finding_id}` | R-status + LG budget | 404 jeśli nie znaleziony |
| guardian status | `GET /guardians` | 13 guardianów health | 500 |
| local models | `GET /locals` | qwen/gpt-oss workload | 500 |
| health | `GET /health` | Liveness aggregatora | — (zawsze 200, ok=false przy błędzie) |

### Health endpoint

```json
{
  "ok": true,
  "actors": 5,
  "guardians": 13,
  "as_of": 1745667842.3
}
```

Przy błędzie: `{"ok": false, "error": "..."}` — HTTP 200 (liveness, nie readiness).

---

## 6. Frontend — strona Theater

**URL**: `/test-center/theater`

Dodana jako 8. karta w hub `/test-center` (commit `50773c5a`):

```typescript
{
  title: "Agent Team Theater",
  url: "/test-center/theater",
  icon: Network,
  description: "Real-time view of agent topology, guardian status, local models"
}
```

### Zawartość strony

**Karta Topology** — siatka aktorów (Claude/Codex/Kimi + otwarte findingi):

- Per aktor: nazwa, rola, status (chip), kind (model/task)
- Dla task (finding): severity chip + D-level chip + R-status

**Karta Guardians** — 13 guardianów w tabeli:

- Guardian ID
- Chip: GREEN (zielony) / YELLOW (bursztynowy) / RED (czerwony)
- `alerts_24h` — liczba alertów ostatnich 24h

**Karta Local Models** — lista modeli lokalnych:

- Model ID
- Status chip (idle/busy)
- Queue depth

Auto-refresh co 5 sekund (wszystkie 3 karty). Wzorzec `useHealth()` — `backendLive` guard.

---

## 7. Przykład użycia

### Pobierz topologię przez REST

```bash
# Po restarcie backendu (wymagany dla nowych routerów)
curl http://127.0.0.1:8010/api/v1/agent-theater/topology | python -m json.tool
```

### Sprawdź stan naprawy konkretnego findingu

```bash
curl http://127.0.0.1:8010/api/v1/agent-theater/repair/f-001
# {
#   "finding_id": "f-001",
#   "r_status": "REPAIRING",
#   "attempts_used": 3,
#   "attempts_max": 9,
#   "loop_status": "ACTIVE"
# }
```

### Użyj aggregatora bezpośrednio w Pythonie

```python
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.agent_theater import AgentTheaterAggregator

store = OntologyStore(db_path="sylion_aeis.db")
agg = AgentTheaterAggregator(ontology=store)

# Sprawdź ile guardianów w RED
guardians = agg.get_guardian_status()
red = [g for g in guardians if g["status"] == "RED"]
if red:
    print(f"UWAGA: {len(red)} guardianów w stanie RED:")
    for g in red:
        print(f"  {g['guardian_id']}: {g['alerts_24h']} alertów/24h")
```

---

## 8. Weryfikacja

```bash
cd src/sylion-pipeline

# Testy Agent Theater (9 testów)
python -m pytest tests/aeis/testing/test_agent_theater.py -v

# Sprawdź health endpoint (po restarcie backendu)
curl http://127.0.0.1:8010/api/v1/agent-theater/health
# Oczekiwane: {"ok": true, "actors": 3, "guardians": 13, ...}

# Sprawdź stronę theater w frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/test-center/theater
# Oczekiwane: 200

# Sprawdź registrację routera w app.py
grep "agent_theater" src/sylion-pipeline/sylion/api/app.py
# Oczekiwane: import + include_router
```

---

## 9. Rozwiązywanie problemów

### `GET /api/v1/agent-theater/health` → 404 (Not Found)

Backend nie zarejestrował routera. Wymagany restart serwera po dodaniu `agent_theater_routes`
do `app.py`. Sprawdź `grep "agent_theater" app.py`.

### Topology pokazuje tylko 3 aktorów (brak findingów)

Baza danych nie zawiera otwartych findingów. Jest to poprawne w środowisku bez aktywnych
testów. Po uruchomieniu `execute_demo()` lub ręcznym `FindingStore.create()` topology
pokaże task-actors.

### Health: `"ok": false, "error": "..."`

Aggregator nie może otworzyć bazy danych (`SYLION_W14_DB`). Sprawdź ścieżkę pliku
i uprawnienia. Endpoint zawsze zwraca HTTP 200 — sprawdź pole `ok` w body.

### Strona `/test-center/theater` nie auto-odświeża

Auto-refresh co 5s oparty na `setInterval` w React. Sprawdź czy DevTools Console nie
pokazuje błędów CORS lub sieciowych. Upewnij się, że backend jest uruchomiony i
`backendLive = true` (sprawdź endpoint `/health` serwera głównego).

---

## 10. Cross-references

- [`49_w14_test_center.md`](./49_w14_test_center.md) — Theater to jedna z 8 stron
  Test Center hub; sekcja 4 opisuje hub i nawigację
- [`46_w14_ontology.md`](./46_w14_ontology.md) — `Finding`, `GuardianAlert`, `LoopReport`,
  `RepairAttempt` czytane przez AgentTheaterAggregator
- [`47_w14_charter_finding.md`](./47_w14_charter_finding.md) — FindingStore tworzy finding
  obiekty widoczne w topology jako task-actors
- [`modules/33_council_hybrid.md`](./33_council_hybrid.md) — `get_council_session_view`
  planowane wire-up do `council_hybrid` w E12.1 (E12 MVP: stub)
- [`modules/46_w14_ontology.md` §14](./46_w14_ontology.md) — 13 guardianów
  rejestrowanych przez `register_all_guardians()` używane w `get_guardian_status()`
