# Dla developera — szybki onboarding

> Praktyczny przewodnik dla osoby dołączającej do zespołu SYLION AEIS. Co znaleźć, jak
> zacząć, jakie konwencje przestrzegać.
> Wersja: 2026-04-26.

## Spis treści

- [1. Repo structure](#1-repo-structure)
- [2. Module pattern (singleton + EventBus + threading.Lock)](#2-module-pattern-singleton--eventbus--threadinglock)
- [3. Storage: PostgreSQL canonical + advisor PG-only divergence](#3-storage-postgresql-canonical--advisor-pg-only-divergence)
- [4. Event bus](#4-event-bus)
- [5. Module registry + auto-register](#5-module-registry--auto-register)
- [6. Testing](#6-testing)
- [7. Adding a new module — step by step](#7-adding-a-new-module--step-by-step)
- [8. Multi-agent workflow + masterplan](#8-multi-agent-workflow--masterplan)
- [9. Frontend conventions](#9-frontend-conventions)
- [10. Common gotchas](#10-common-gotchas)

---

## 1. Repo structure

```
pipeline_glm/
├── src/
│   ├── sylion-pipeline/                     # Backend Python (FastAPI + gRPC)
│   │   ├── sylion/
│   │   │   ├── api/                         # FastAPI routes (~50 plików _routes.py)
│   │   │   ├── core/                        # Module registry, event bus, auto_register
│   │   │   ├── governance/                  # Council, evidence spine, compliance
│   │   │   ├── cognitive/                   # Idea vault, code agent, model router
│   │   │   ├── aeis/                        # AEIS self-* modules + advisor (W13)
│   │   │   │   └── advisor/                 # 11 modułów (W13)
│   │   │   ├── contracts/manifests/         # JSON deployment manifests
│   │   │   ├── db/                          # pg_migration, alembic
│   │   │   ├── pipeline/                    # State machine
│   │   │   ├── security/                    # RBAC, PII redaction
│   │   │   └── proto/                       # gRPC proto definitions
│   │   ├── tests/
│   │   ├── alembic/                         # PG migrations
│   │   └── pyproject.toml
│   └── sylion-frontend/                     # Next.js 16 App Router
│       └── src/
│           ├── app/(app)/                   # Per-page routes (agents, audit, costs, ...)
│           ├── components/
│           └── lib/api/                     # client.ts + hooks.ts
├── docs/
│   ├── dokumentacja/                        # ← jesteś tutaj
│   ├── claude_parallel/                     # Multi-agent masterplans
│   ├── claude_system_audit/                 # Audyt prefix CLAUDE_AEIS_*
│   ├── system_audit/
│   ├── Ksiega_AEIS_v3_5_full.md
│   ├── Masterplan_AEIS_v3_5.md
│   └── PLAN_WDROZENIA.md
└── scripts/
    ├── start-server.bat                     # Windows launcher
    └── start-server.ps1
```

---

## 2. Module pattern (singleton + EventBus + threading.Lock)

### Reference modules (czytaj jako pierwsze)

| Plik | Co pokazuje |
|---|---|
| `sylion/governance/council_workflow.py` | Workflow z Council, EventBus, EvidenceSpine, threading.Lock |
| `sylion/cognitive/code_agent.py` | Service module z optional EventBus, SQLite, singleton factory |
| `sylion/cognitive/model_router.py` | Provider routing, dataclass models, JSON serialization |

### Wzorzec singleton factory

```python
# sylion/aeis/advisor/preferences/service.py
import threading
from typing import Optional

_INSTANCE: Optional["PreferencesService"] = None
_INSTANCE_LOCK = threading.Lock()


class PreferencesService:
    def __init__(self, db_pool, event_bus=None):
        self._db = db_pool
        self._event_bus = event_bus
        self._lock = threading.RLock()  # RLock not Lock — re-entrancy

    def get_effective(self, user_id, project_type, project_domain, key):
        with self._lock:
            # ... query DB ...
            return value


def get_preferences_service() -> PreferencesService:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                from sylion.aeis.advisor._db import get_pool
                from sylion.core.event_backbone import get_event_backbone
                _INSTANCE = PreferencesService(
                    db_pool=get_pool(),
                    event_bus=get_event_backbone(),
                )
    return _INSTANCE
```

### Konwencje

- **Sync-first** — `def`, NIE `async def`. FastAPI sync, gRPC sync, EventBus sync.
- **threading.RLock**, NIE Lock — wszystkie reads inside lock, RLock pozwala na re-entrancy.
- **EventBus optional injection** — service powinien działać bez EventBus (testy łatwiejsze).
- **Dataclass models** — używaj `@dataclass(frozen=True)` dla immutable types.
- **JSON serialization** — `dataclasses.asdict()` + custom encoder dla datetime/Decimal.

### Async — kiedy WOLNO

Tylko gdy heavy parallel external calls (np. ensemble LLM). Wrap w `concurrent.futures.ThreadPoolExecutor`:

```python
from concurrent.futures import ThreadPoolExecutor

def parallel_llm_judge(prompts, models):
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = [executor.submit(call_model, p, m) for p, m in zip(prompts, models)]
        return [f.result(timeout=30) for f in futures]
```

---

## 3. Storage: PostgreSQL canonical + advisor PG-only divergence

### Globalny pattern: PG canonical + SQLite mirror

Większość modułów SYLION:
- **Primary PG schema** — `sylion/db/pg_migration._PG_SCHEMA_SQL` + Alembic migrations.
- **SQLite for tests + dev fallback** — same schema, SQLite-compatible SQL.
- Migration runner: `pg_migration.run_migrations()`.

Pattern:
```python
# Detect backend
if os.environ.get("SYLION_DB_BACKEND") == "postgres":
    conn = psycopg.connect(...)
else:
    conn = sqlite3.connect(test_db_path)
```

### Advisor: PG-only (świadoma divergencja)

Advisor (W13) NIE ma SQLite fallback. Decyzja operatora: *"od razu robić docelowy duży system z bazą danych"*.

- Wszystkie advisor modules → PG only.
- Test database = real PG instance (nowy fixture `pg_test_db` w `tests/aeis/advisor/conftest.py`).
- Schema-per-module: `advisor_preferences`, `advisor_pricing`, `advisor_engine`, ...

### Migration

1. Append do `sylion/db/pg_migration._PG_SCHEMA_SQL`:
   ```python
   _PG_SCHEMA_SQL = """
   ... existing ...

   -- Advisor layer
   CREATE SCHEMA IF NOT EXISTS advisor_preferences;
   CREATE TABLE IF NOT EXISTS advisor_preferences.preferences (...);
   ...
   """
   ```

2. Stwórz Alembic revision:
   ```bash
   cd src/sylion-pipeline
   alembic revision -m "advisor layer schema"
   # → alembic/versions/20260425_0002_advisor_layer.py
   ```

3. W revision wstaw `op.execute(...)` z DDL z `02_postgresql_schema.sql`.

### Concurrency

- SQLite: ALL modules use `threading.RLock()` (NOT Lock), ALL reads inside lock.
- PG: connection pool (`psycopg[pool]`), each connection ma własną sesję.

---

## 4. Event bus

### API

```python
from sylion.core.event_bus import SylionEvent
from sylion.core.event_backbone import get_event_backbone
import time, uuid

# Publish
event = SylionEvent(
    event_id=str(uuid.uuid4()),
    topic="aeis.advisor.engine.recommendation_emitted",
    payload={"card_id": "...", "risk_level": "high"},
    source_module="sylion.aeis.advisor.engine",
    timestamp=time.time(),
    idempotency_key=f"card:{card_id}:emitted",
)
get_event_backbone().publish(event)

# Subscribe (pattern match z wildcards)
def handler(event: SylionEvent):
    if event.topic.startswith("aeis.advisor."):
        process(event)

get_event_backbone().subscribe("aeis.advisor.*", handler)
```

### 3 backendy

```bash
SYLION_EVENT_MODE=sqlite   # default — file lub :memory:, single-node
SYLION_EVENT_MODE=nats     # NATS JetStream — durable, distributed
SYLION_EVENT_MODE=redis    # Redis Pub/Sub — pattern subscriptions
```

Backend wybierany w `event_backbone.get_event_backbone()` na podstawie env var.

### Konwencja nazewnictwa eventów

```
aeis.<phase>.<entity>.<action>
```

- `<phase>`: `idea`, `council`, `production`, `system`, `testing`, `human_gate`, `final_approval`
- `<entity>`: `intake`, `formation`, `deploy`, `setup`, ...
- `<action>`: past-tense (`completed`, `requested`, `pending`, `crossed`, `dispatched`)

Advisor-emitted: prefix `aeis.advisor.*` (separate namespace).

### Schema validation

Każdy event walidowany przed publish przez `advisor_events.proto_registry`. Failures →
`aeis.advisor.events.validation_failed` (logged, NOT stored w main log).

---

## 5. Module registry + auto-register

### Manifest pattern

Każdy moduł ma JSON manifest w `sylion/contracts/manifests/{module_id}.json`:

```json
{
  "module_id": "sylion.aeis.advisor.preferences",
  "module_kind": "ADVISOR",
  "owner_plan": "advisor_layer_etap1",
  "implementation_strategy": "greenfield",
  "contract_version": "1.0.0",
  "depends_on": [],
  "lifecycle_stage": "DRAFT",
  "events_emit": [
    "aeis.advisor.preferences.created",
    "aeis.advisor.preferences.updated"
  ],
  "events_subscribe": [
    "aeis.advisor.history.learning_signal_emitted"
  ],
  "storage": {
    "postgres_schemas": ["advisor_preferences"]
  }
}
```

### ModuleKind enum

`sylion/core/module_registry.py`:
```python
class ModuleKind(Enum):
    CORE_KERNEL = "core_kernel"
    COGNITIVE = "cognitive"
    GOVERNANCE = "governance"
    # ... A-O ...
    CELLULAR = "cellular"
    ADVISOR = "advisor"     # ← new dla W13
```

### Auto-registration

App startup (`sylion/api/app.py` lifespan):
```python
from sylion.core.auto_register import auto_register_modules
from sylion.core.module_registry import get_registry
from sylion.core.event_backbone import get_event_backbone

@asynccontextmanager
async def lifespan(app):
    registry = get_registry()
    event_bus = get_event_backbone()
    auto_register_modules(
        registry=registry,
        manifest_dir=Path("sylion/contracts/manifests"),
        event_bus=event_bus,
    )
    # ... rest of startup ...
    yield
```

Nowy manifest dropped do `sylion/contracts/manifests/` → picked up automatycznie. Brak zmian
w `app.py`.

---

## 6. Testing

### pytest setup

```bash
cd src/sylion-pipeline
pytest                              # all tests
pytest tests/aeis/advisor/          # only advisor
pytest -k "preferences"             # filter by name
pytest -x --pdb                     # stop on first failure + drop to pdb
```

### conftest.py per moduł

```python
# tests/aeis/advisor/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def pg_test_db():
    """Real PG instance for advisor tests (PG-only, no SQLite mocks)."""
    # Create temp schema, run migrations, yield connection, drop schema
    ...

@pytest.fixture(autouse=True)
def disable_rbac(monkeypatch):
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    monkeypatch.setenv("SYLION_RATE_LIMIT_DISABLED", "1")
```

### Golden tests

Per moduł, w `tests/golden/aeis/advisor/{module}/`:
- JSON snapshots dla contract scenarios.
- Pytest cases dla logic.

Przykład:
```
tests/golden/aeis/advisor/preferences/
├── 4_level_cascade.json            # JSON scenario
├── audit_append_only.json
└── test_resolver.py                # Pytest logic
```

### Liczby testów (snapshot 2026-04-21)

- Python: **6298 passed**, 0 failed (29 skipped, 4 xfailed, 4 xpassed).
- Playwright: 113/113 e2e (26 dashboard + 87 integration).

### Backend restart (po zmianach)

```bash
cd src/sylion-pipeline
python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010
```

Frontend dev server osobno:
```bash
cd src/sylion-frontend
npm run dev
```

---

## 7. Adding a new module — step by step

### 1. Plan

Decide:
- `module_id` (e.g. `sylion.aeis.advisor.my_module`)
- `module_kind` (z enum)
- Storage schemas
- Events emit/subscribe
- gRPC service + methods
- Dependencies

### 2. Folder + module.py

```
sylion/aeis/advisor/my_module/
├── __init__.py
├── service.py
├── proto/
│   └── my_module.proto
└── (optional: adapters/, db.py, ...)
```

### 3. Manifest

`sylion/contracts/manifests/aeis.advisor.my_module.json` — patrz pattern w sekcji 5.

### 4. Schema

Append do `sylion/db/pg_migration._PG_SCHEMA_SQL`:
```sql
CREATE SCHEMA IF NOT EXISTS advisor_my_module;
CREATE TABLE IF NOT EXISTS advisor_my_module.records (...);
```

Stwórz Alembic revision:
```bash
alembic revision -m "advisor my_module schema"
```

### 5. Service implementation

```python
# service.py
class MyModuleService:
    def __init__(self, db_pool, event_bus=None):
        self._db = db_pool
        self._event_bus = event_bus
        self._lock = threading.RLock()

    def do_thing(self, ...):
        with self._lock:
            # logic
            if self._event_bus:
                self._event_bus.publish(SylionEvent(
                    topic="aeis.advisor.my_module.thing_done",
                    payload={...},
                    source_module="sylion.aeis.advisor.my_module",
                    ...
                ))
```

### 6. gRPC server (jeśli service)

`proto/my_module.proto` → `grpc_tools.protoc` → `_generated/`.
Server stub w `service.py` lub osobnym `grpc_server.py`.

### 7. FastAPI routes (jeśli REST surface)

`sylion/api/my_module_routes.py`:
```python
from fastapi import APIRouter
from sylion.aeis.advisor.my_module.service import get_my_module_service

router = APIRouter(prefix="/api/v1/advisor/my-module", tags=["advisor"])

@router.get("/things")
def list_things():  # sync, NOT async
    return get_my_module_service().list()
```

Register w `sylion/api/app.py`:
```python
from sylion.api.my_module_routes import router as my_module_router
app.include_router(my_module_router)
```

### 8. Tests

```
tests/aeis/advisor/my_module/
├── conftest.py              # fixtures
├── test_service.py          # unit
├── test_routes.py           # integration via TestClient
└── golden/
    └── ...
```

### 9. Frontend (optional)

```
src/sylion-frontend/src/app/(app)/my-module/
├── page.tsx                 # main page
├── _hooks.ts                # custom hooks
└── _types.ts                # local types
```

Hook pattern:
```typescript
import { useApi } from '@/lib/api/client';

export function useMyModule() {
    const { data, loading, error, refresh } = useApi('/api/v1/advisor/my-module/things');
    return { data, loading, error, refresh };
}
```

### 10. Manifest gates

Każdy moduł ma gates:
- `loc_max: 1000` — code-bloat-detector blokuje powyżej
- `test_coverage: 85` — minimum
- `security: rbac_enforced + audit_append_only_trigger_present`

---

## 8. Multi-agent workflow + masterplan

### Co to jest

Niektóre większe inicjatywy (np. AEIS Advisor Layer) są implementowane przez **wielu AI agentów
sekwencyjnie**. Każdy agent dostaje self-contained prompt z masterplanu.

### Folder masterplanu

```
docs/claude_parallel/{initiative_name}/
├── README.md                       # Master index
├── 00_architecture/                # Foundation specs
├── 01_prompts/                     # Per-agent execution prompts
├── 02_sequence/                    # Timeline + handoffs
├── 03_contracts/                   # API specifications
└── 04_validation/                  # Testing + audit
```

### Agent workflow (przykład Advisor Layer)

| Stage | Agent | Work Packages |
|---|---|---|
| 0 | Claude (planner) | All architecture + prompts |
| 1 | Codex | WP1 (preferences), WP2 (pricing), WP7 (actions) + WP-LCH |
| 2 | Kimi | WP3 (engine), WP4 (role_resolver/variants), WP5 (subscription/scaling/funding) |
| 3 | Codex | WP6 (history) |
| 4 | Claude (integrator) | WP8 (feed), WP9 (wizard), WP10/11 (dashboards) |
| 5 | z.ai | Audit (security + breaking + gates) |
| 6 | Claude (final) | Golden tests, Evidence Pack D3+, demo flow |

### File ownership rules

Każdy agent ma jawnie wypisane:
- **YOU OWN (write)** — konkretne ścieżki
- **READ-ONLY** — wszystko inne
- **DO NOT TOUCH** — explicit blocklist

### Rule podczas pracy w gałęzi multi-agent

- Branch naming: `[agent][stage][workpackage] description`
- Commit message: `[agent][workpackage] description`
- Przykład: `[advisor][kimi][b002-fix][scaling] migrate SQLite -> shared PG pool`

---

## 9. Frontend conventions

### Critical patterns

- **Mock fallback**: `backendLive ? realData : mockData` — **NO length check** (`&& data.length > 0` to BUG).
- **Optional chaining**: `(data?.items ?? []).map(...)` gdy `backendLive`.
- **useHealth shape**: `{data, loading, error, refresh}`.
  - 14 stron: `const { data: health }`
  - 4 strony: `const health = useHealth()`
- **FastAPI route ordering**: static paths BEFORE parameterized (`/active` przed `/{name}`).
- **Hydration-safe**: użyj `fmtDate`/`fmtNum` z `utils.ts`, NIGDY `toLocale*` (Windows ARP issue).

### File locations

```
src/sylion-frontend/src/
├── app/(app)/
│   ├── {feature}/
│   │   ├── page.tsx
│   │   ├── _hooks.ts        # local hooks
│   │   └── _components/
├── components/
│   ├── layout/AppSidebar.tsx
│   └── ui/                  # shadcn/ui
└── lib/
    ├── api/
    │   ├── client.ts        # base fetcher
    │   └── hooks.ts         # global hooks
    └── utils.ts             # fmtDate, fmtNum, cn
```

### Styling

- shadcn/ui + Tailwind.
- Modern, modernist, high-tech (Linear/Vercel/Arc class).
- Charts: Recharts (existing).

---

## 10. Common gotchas

### LLM provider env vars

```bash
SYLION_LLM_PROVIDER=anthropic        # stub | anthropic | openai | ollama
SYLION_LLM_API_KEY=sk-...
SYLION_LLM_MODEL=claude-sonnet-4-6
```

### Pipeline API endpoints

6 endpointów pod `/api/v1/pipeline/`:
- `ideas`, `runs`, `execute`, `cancel`, `steps`

### WebSocket bridge

Wired do FastAPI lifespan via `start_event_bridge`. Jeśli frontend nie pokazuje live data:
1. Sprawdź czy lifespan handler się uruchomił (logi backend).
2. Sprawdź czy WebSocket port nie jest zablokowany.
3. Sprawdź `backendLive` flag w hookach.

### Windows specific

- ARP regex: separate od Linux format (Windows wyświetla inaczej).
- Path separators: użyj `pathlib.Path`, nie raw string.
- Bash w session: `/dev/null`, NIE `NUL`. Forward slashes w paths.
- Shell encoding: ustawione w project rules.

### Decision Gate cascade

Gdy zmieniasz decyzję mid-pipeline:
1. `decision_snapshot.change_decision()` triggeruje cascade.
2. Strong deps → invalidated.
3. Weak deps → warning.
4. Pipeline state machine `handle_decision_change()` → rollback do `planning`.

NIE pomijaj cascade analysis.

### Audit append-only

Próba UPDATE/DELETE na audit table → DB exception. Jeśli "musisz" zmodyfikować — to znaczy
że projektujesz to źle.

### Testing concurrent code

- Wszystkie reads MUSZĄ być inside `threading.RLock()`.
- Concurrent test patterns: `decision_gate`, `quality_gate`, `skills_executor` mają
  reference patterns.

### "Switch to Technical Mode"

ZAWSZE widoczny w nav. Operator power-user może chcieć drill-down do raw endpointów.

### Memory awareness

Memory records mogą być stale (point-in-time). Przed cytowaniem `file:line` z memory:
1. Verify że plik nadal istnieje.
2. Verify że symbol/flag nadal istnieje (grep).
3. Jeśli stale → update lub usuń memory record.

---

## Powiązane dokumenty

- [00_architektura_systemu.md](./00_architektura_systemu.md) — architektura całości
- [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) — Advisor Layer deep-dive
- [02_operational_manual.md](./02_operational_manual.md) — codzienny workflow
- [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) — D-ladder + Evidence Pack
- `docs/claude_parallel/aeis_advisor/` — masterplan multi-agent
- `docs/Ksiega_AEIS_v3_5_full.md` — kanon AEIS pełny
- `docs/Masterplan_AEIS_v3_5.md` — masterplan AEIS
- `docs/PLAN_WDROZENIA.md` — plan wdrożenia
