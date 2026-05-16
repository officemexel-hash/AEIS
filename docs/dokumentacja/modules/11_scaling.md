# Moduł `sylion.aeis.advisor.scaling` — rekomendator topologii i planer staging
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> **Status**: Etap 1, lifecycle `DRAFT`, contract `1.0.0`
> **Owner plan**: `advisor_layer_etap1`
> **Lokalizacja kodu**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/`
> **Manifest**: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.scaling.json`

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje gRPC / Service API](#4-funkcje-grpc--service-api)
5. [Eventy emitowane](#5-eventy-emitowane)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przykład-użycia)
8. [Verification — checklist akceptacyjny](#8-verification--checklist-akceptacyjny)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.scaling` odpowiada za **rekomendowanie topologii infrastrukturalnej** dla projektów uruchamianych w warstwie AEIS Advisor oraz za **planowanie etapowych migracji** między topologiami. To bezpośredni doradca operatora w decyzji „uruchomić tylko lokalnie", „dodać VPS", „przejść w pełni na VPS", „rozproszyć na wiele VPS-ów".

### 1.1. Problem biznesowy

W modelu SYLION AEIS operator zaczyna od **lokalnego runtime'u** (laptop / stacja robocza, np. Ollama + lokalne modele Qwen) i może skalować się w górę zgodnie z potrzebami konkretnego projektu. Każda zmiana topologii niesie ze sobą:

- **Koszt finansowy** (subskrypcje VPS, opłaty hostingowe)
- **Ryzyko bezpieczeństwa** (dane wychodzą poza lokalny boundary)
- **Latencję** (RTT do VPS-a, transfer)
- **Kompleksowość operacyjną** (konfiguracja, monitoring, backup)

Bez modułu scaling operator musi sam zgadywać, czy 800 000 tokenów dziennie to „dużo" dla lokalnego setupu i czy potrzeba mu jednego VPS-a, czy klastra. Scaling formalizuje te decyzje:

- Mapuje **profil obciążenia** (`estimated_tokens_per_day`, `parallelism`, `latency_target_seconds`) na **rekomendowaną topologię**.
- Klasyfikuje rekomendację na **D-level** (D2 / D3 / D4) zgodnie z Decision Ladder.
- Wymusza **Human Gate + Evidence Pack** dla wszystkich rekomendacji powyżej `local_only` (D3+).
- Buduje **plan etapowy** (`StagingPlan`) dla migracji w górę (scale-up) lub w dół (scale-down).
- Utrzymuje **inventory zarejestrowanych środowisk** (lokalne, VPS, hybrid) w PostgreSQL.

### 1.2. Rola w architekturze Advisor

Scaling jest **modułem technicznym** w obrębie warstwy doradczej. Współpracuje z:

- **role_resolver** — wybór modeli (lokalnych vs zewnętrznych) determinuje minimalną wymaganą topologię.
- **subscription** — VPS-y kosztują, subskrypcja musi mieć wystarczający budżet/ROI.
- **variants** — wariant „aggressive" (council=7, więcej tokenów) może wymusić `multi_vps`.
- **engine** — engine generuje karty rekomendacji, ale nie zna profilu sprzętowego operatora; scaling odpowiada na pytanie „czy dasz radę to uruchomić".
- **mobile_gateway** — operator może akceptować kartę topologii z aplikacji mobilnej (D3+ wymaga biometric step-up).

### 1.3. Granice odpowiedzialności (czego moduł NIE robi)

- **Nie wdraża** infrastruktury — nie tworzy VPS-ów, nie konfiguruje SSH, nie startuje kontenerów. To rola Codex Phase 2 (provisioning).
- **Nie monitoruje** zdrowia środowisk — health check / SLO leży po stronie observability stack.
- **Nie kupuje** subskrypcji VPS — tylko rekomenduje; faktyczna decyzja zakupowa idzie przez `subscription.emit_purchase_recommendation`.
- **Nie negocjuje** SLA z dostawcami — używa tylko zarejestrowanych środowisk z inventory.
- **Nie szyfruje** danych w tranzycie — to warstwa security/transport.

### 1.4. Kontrakt typów topologii

Moduł rozpoznaje cztery topologie, w stałej kolejności (od najprostszej do najbardziej rozproszonej):

| Typ | Opis | Typowy use-case | D-level (default) |
|---|---|---|---|
| `local_only` | Wszystko działa na maszynie operatora (laptop/desktop). | Single-user, low traffic, small projects, eksperymenty. | D2 |
| `local_plus_vps` | Lokalny runtime + jeden zdalny VPS (tańszy hybrid). | Średnie projekty, brak wymagań co-location, scale-out logiki. | D3 |
| `vps_only` | Cała kalkulacja na zdalnym VPS-ie (bez lokalu). | Klient wymaga dedykowanego środowiska, zdalna praca, niska latencja od strony klienta. | D3 |
| `multi_vps` | Wiele VPS-ów w klastrze (LB, sharding). | Duże projekty, parallelism > 3, wysoka dostępność. | D4 |

Kolejność jest kanoniczna i wykorzystywana przez `staging_planner.TOPOLOGY_ORDER`:

```python
TOPOLOGY_ORDER = ["local_only", "local_plus_vps", "vps_only", "multi_vps"]
```

Oznacza to, że scale-up to ruch w prawo, scale-down — w lewo. `local_plus_vps` jest „pomiędzy" lokalem a `vps_only`, mimo że `vps_only` ma niższy operacyjny koszt (mniej koordynacji), ponieważ migracja przez `local_plus_vps` jest bezpieczniejszą ścieżką (operator może w każdej chwili wycofać się do lokalu).

### 1.5. Granica D-level (Decision Ladder mapping)

Heurystyka klasyfikuje rekomendacje:

- **`local_only` → D2** — niski wpływ, brak kosztu zewnętrznego, brak nowego vendor lock-in.
- **`local_plus_vps` → D3** — pojawia się koszt VPS i nowa infrastruktura.
- **`vps_only` → D3** — pełne przeniesienie, ale w obrębie jednego dostawcy.
- **`multi_vps` → D4** — klaster, multi-vendor, wyższe ryzyko operacyjne.

D3 i D4 wymagają Evidence Pack (`evp_scaling_<topology>`) i Human Gate. D2 nie wymaga.

---

## 2. Architektura

### 2.1. Pliki w module

```
sylion/aeis/advisor/scaling/
├── __init__.py
├── _db.py                    # PG-only no-op (schema w Alembic)
├── _models.py                # ScalingCard, Env, StagingPlan dataclasses
├── env_inventory.py          # rejestracja + listowanie środowisk
├── grpc_server.py            # gRPC entrypoint (Etap 2)
├── README.md                 # operator-facing
├── service.py                # ScalingService — fasada
├── staging_planner.py        # propose_staging_plan, TOPOLOGY_ORDER
└── topology_recommender.py   # recommend_topology — heurystyka
```

### 2.2. Diagram zależności wewnętrznych

```
                 ┌──────────────────────┐
                 │   ScalingService     │
                 │  (service.py:22)     │
                 │  singleton: _service │
                 └─────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────────┐
         ▼                 ▼                     ▼
  recommend_topology  propose_staging_plan  env_inventory
  (heurystyka 4-     (TOPOLOGY_ORDER walk)  (PG insert/list)
   warianty)
         │                 │                     │
         └─────────────────┴─────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │   EventBus     │
                  │ (3 eventy)     │
                  └────────────────┘
```

### 2.3. Modele danych (`_models.py`)

#### `ScalingCard` (rekomendacja topologii)

```python
@dataclass
class ScalingCard:
    card_id: str = ""                       # auto-uuid hex
    operator_id: str = ""
    project_id: str = ""
    recommended: str = ""                   # local_only | local_plus_vps | vps_only | multi_vps
    alternatives: list[str] = field(default_factory=list)
    d_level: str = "D2"
    evidence_pack_id: str | None = None     # evp_scaling_<topology> dla D3+
    human_gate_required: bool = False       # True dla D3+
    impacts: dict[str, Any] = field(default_factory=dict)
```

`impacts` zawiera trzy kanoniczne klucze:
- `monthly_cost_usd` — szacowany miesięczny koszt zewnętrzny (USD).
- `max_parallelism` — maksymalna liczba równoległych workerów wspieranych przez topologię.
- `latency_estimate_seconds` — szacowana latencja end-to-end po zastosowaniu topologii.

#### `Env` (zarejestrowane środowisko w inventory)

```python
@dataclass
class Env:
    env_id: str = ""                        # auto-uuid hex
    operator_id: str = ""
    name: str = ""                          # np. "vps-warsaw-prod"
    kind: str = ""                          # local | vps | hybrid
    capacity_tokens_per_day: int = 0
    registered_at: float = 0.0              # auto-time.time()
```

Pole `kind` przyjmuje trzy wartości i nie jest enforced na poziomie DB (string column). Konwencja:

| `kind` | Znaczenie |
|---|---|
| `local` | Maszyna operatora — laptop, desktop, on-premise. |
| `vps` | Pojedynczy VPS u dostawcy zewnętrznego. |
| `hybrid` | Setup mieszany — np. lokalna pamięć + VPS-owy compute. |

#### `StagingPlan` (plan migracji)

```python
@dataclass
class StagingPlan:
    plan_id: str = ""                       # auto-uuid hex
    current_topology: str = ""
    target_topology: str = ""
    phases: list[dict[str, Any]] = field(default_factory=list)
```

Każda faza w `phases` ma kształt:

```python
{
    "phase": <int>,                # 1, 2, 3, ...
    "action": <str>,               # "deploy_env" | "decommission_env" | "no_change"
    "topology": <str>,             # opcjonalne, dla deploy/decommission
    "description": <str>,          # human-readable
}
```

### 2.4. Heurystyka rekomendacji (`topology_recommender.recommend_topology`)

Procedura jest deterministyczna i bezstanowa — to czysta funkcja od profilu obciążenia do `ScalingCard`. Pełen branch:

```python
estimated_tokens_per_day = workload.get("estimated_tokens_per_day", 0)
parallelism = workload.get("parallelism", 1)
latency_target = workload.get("latency_target_seconds", 10.0)

# Defensive: coerce None / negatives to safe defaults
if estimated_tokens_per_day is None or estimated_tokens_per_day < 0:
    estimated_tokens_per_day = 0
if parallelism is None or parallelism < 1:
    parallelism = 1
if latency_target is None or latency_target <= 0:
    latency_target = 10.0

if estimated_tokens_per_day < 100_000 and parallelism == 1:
    recommended = "local_only"
    d_level = "D2"
    alternatives = ["local_plus_vps"]
    impacts = {
        "monthly_cost_usd": 0,
        "max_parallelism": 1,
        "latency_estimate_seconds": latency_target,
    }
elif estimated_tokens_per_day < 1_000_000:
    recommended = "local_plus_vps"
    d_level = "D3"
    alternatives = ["local_only", "multi_vps"]
    impacts = {
        "monthly_cost_usd": 20,
        "max_parallelism": 2,
        "latency_estimate_seconds": latency_target * 0.8,
    }
elif parallelism > 3:
    recommended = "multi_vps"
    d_level = "D4"
    alternatives = ["local_plus_vps", "vps_only"]
    impacts = {
        "monthly_cost_usd": 60,
        "max_parallelism": parallelism + 2,
        "latency_estimate_seconds": latency_target * 0.5,
    }
else:
    recommended = "vps_only"
    d_level = "D3"
    alternatives = ["local_plus_vps", "multi_vps"]
    impacts = {
        "monthly_cost_usd": 40,
        "max_parallelism": 3,
        "latency_estimate_seconds": latency_target * 0.7,
    }
```

Tabelarycznie:

| Warunek | Topologia | D-level | Koszt USD/m | Max parallelism | Latency multiplier |
|---|---|---|---|---|---|
| `tokens < 100k` AND `parallelism == 1` | `local_only` | D2 | 0 | 1 | 1.0× target |
| `tokens < 1M` | `local_plus_vps` | D3 | 20 | 2 | 0.8× target |
| `parallelism > 3` | `multi_vps` | D4 | 60 | parallelism + 2 | 0.5× target |
| pozostałe | `vps_only` | D3 | 40 | 3 | 0.7× target |

> **Uwaga**: Heurystyka ma kolejność branchy w `if/elif`. Jeśli operator poda `tokens=2_000_000, parallelism=1`, to NIE wpadnie w `multi_vps` (bo `parallelism > 3` dotyczy tylko gdy nie zaszło `tokens < 1M` ORAZ nie zaszedł próg `< 100k AND p==1`). Kaskada idzie: local→hybrid→multi→vps_only. Czytelnik kodu powinien myśleć w terminach „pierwsze pasujące" — co sprawia, że `multi_vps` wymaga zarówno wysokich tokenów (>=1M) JAK I parallelism > 3.

### 2.5. Heurystyka planowania staging (`staging_planner.propose_staging_plan`)

```python
TOPOLOGY_ORDER = ["local_only", "local_plus_vps", "vps_only", "multi_vps"]

def propose_staging_plan(current_topology, target_topology) -> StagingPlan:
    plan = StagingPlan(current_topology=current_topology, target_topology=target_topology)

    if current_topology == target_topology:
        plan.phases.append({
            "phase": 1,
            "action": "no_change",
            "description": "Current and target topology are the same",
        })
        return plan

    current_idx = TOPOLOGY_ORDER.index(current_topology) if current_topology in TOPOLOGY_ORDER else -1
    target_idx = TOPOLOGY_ORDER.index(target_topology) if target_topology in TOPOLOGY_ORDER else -1

    if current_idx < target_idx:
        # Scale up
        phase_num = 1
        for topo in TOPOLOGY_ORDER[current_idx + 1:target_idx + 1]:
            plan.phases.append({
                "phase": phase_num,
                "action": "deploy_env",
                "topology": topo,
                "description": f"Deploy {topo} environment",
            })
            phase_num += 1
    else:
        # Scale down
        phase_num = 1
        for topo in reversed(TOPOLOGY_ORDER[target_idx:current_idx]):
            plan.phases.append({
                "phase": phase_num,
                "action": "decommission_env",
                "topology": topo,
                "description": f"Decommission {topo} environment",
            })
            phase_num += 1

    return plan
```

Trzy ścieżki:

1. **No-op** (`current == target`) — jedna faza `no_change`.
2. **Scale-up** (`current_idx < target_idx`) — jedna faza `deploy_env` na każdą topologię na ścieżce między current i target.
3. **Scale-down** (`current_idx > target_idx`) — jedna faza `decommission_env` w odwrotnej kolejności (od najbardziej rozproszonej do najmniej).

#### Przykłady ścieżek

| Current | Target | Liczba faz | Akcje |
|---|---|---|---|
| `local_only` | `local_only` | 1 | `no_change` |
| `local_only` | `local_plus_vps` | 1 | deploy local_plus_vps |
| `local_only` | `multi_vps` | 3 | deploy local_plus_vps → deploy vps_only → deploy multi_vps |
| `multi_vps` | `local_only` | 3 | decommission multi_vps → decommission vps_only → decommission local_plus_vps |
| `vps_only` | `local_plus_vps` | 1 | decommission vps_only |
| `local_plus_vps` | `vps_only` | 1 | deploy vps_only |

### 2.6. Środowiska w inventory (`env_inventory.py`)

`register_env(env_data)` wykonuje **UPSERT** na PG (`ON CONFLICT (env_id) DO UPDATE SET ...`), więc ponowna rejestracja istniejącego `env_id` aktualizuje pola. `get_env_inventory(operator_id)` zwraca listę środowisk filtrowaną po `operator_id`, posortowaną po `registered_at` rosnąco (najstarsze pierwsze).

Pełny SQL z kodu:

```sql
INSERT INTO scaling_envs
  (env_id, operator_id, name, kind, capacity_tokens_per_day, registered_at)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (env_id) DO UPDATE SET
  operator_id = EXCLUDED.operator_id,
  name = EXCLUDED.name,
  kind = EXCLUDED.kind,
  capacity_tokens_per_day = EXCLUDED.capacity_tokens_per_day,
  registered_at = EXCLUDED.registered_at;
```

Listing:

```sql
SELECT * FROM scaling_envs
WHERE operator_id = %s
ORDER BY registered_at;
```

### 2.7. Pattern singletona

`get_scaling_service(event_bus=None)` zwraca jeden globalny `ScalingService`. Brak thread-locka — pierwszy call alokuje, kolejne reusują. Test cleanup używa `reset_scaling_service()`.

```python
_service: ScalingService | None = None

def get_scaling_service(event_bus: EventBus | None = None) -> ScalingService:
    global _service
    if _service is None:
        _service = ScalingService(event_bus=event_bus)
    return _service

def reset_scaling_service() -> None:
    global _service
    _service = None
```

### 2.8. PG-only mode

Plik `_db.py` jest celowo no-opem:

```python
def ensure_tables() -> None:
    """No-op in PG-only mode. Schema lives in Alembic migration."""
    return None
```

Schema `scaling_envs` jest tworzona przez migrację Alembica zarządzaną z poziomu `sylion.aeis.advisor._db`. Patrz: rozdział [6. Database tables](#6-database-tables).

### 2.9. Manifest contract

```json
{
  "module_id": "sylion.aeis.advisor.scaling",
  "module_kind": "ADVISOR",
  "owner_plan": "advisor_layer_etap1",
  "implementation_strategy": "greenfield",
  "contract_version": "1.0.0",
  "depends_on": [],
  "lifecycle_stage": "DRAFT",
  "events_emit": [
    "aeis.advisor.scaling.topology_recommended",
    "aeis.advisor.scaling.staging_proposed",
    "aeis.advisor.scaling.env_registered"
  ],
  "events_subscribe": [],
  "storage": {
    "postgres_schemas": ["scaling_envs"]
  }
}
```

Kluczowe konsekwencje:

- `depends_on: []` — moduł jest **zerową zależnością** — nie woła innych modułów Advisora. To pozwala odpalać go w pełnej izolacji w testach jednostkowych.
- `events_subscribe: []` — moduł **nie reaguje** na żadne eventy — działa imperatywnie, na żądanie service callera.
- `storage.postgres_schemas: ["scaling_envs"]` — jedna tabela.

---

## 3. Konfiguracja

### 3.1. Variables środowiskowe

Moduł nie czyta bezpośrednio żadnych `os.environ` — całość konfiguracji odbywa się przez `event_bus` injection oraz parametry profilu obciążenia przekazywane na wejściu.

| ENV | Pochodzenie | Użycie |
|---|---|---|
| `SYLION_DATABASE_URL` | dziedziczone z `sylion.aeis.advisor._db` | URL Postgres dla connection pool |
| `SYLION_EVENT_BUS_DSN` | dziedziczone z `sylion.core.event_bus` | DSN szyny eventów (jeśli zewnętrzna) |

### 3.2. Konfiguracja przez UI operatora (Etap 2 hookpointy)

Z perspektywy operatora moduł czyta przyszłe preferencje (na chwilę obecną nie są obsługiwane — heurystyka jest jednolita):

| Preferencja | Lokalizacja UI | Efekt | Status |
|---|---|---|---|
| `infrastructure.runtime_strategy` | Preferencje → Infrastruktura → Strategia | Wymusza topologię (`local_only`, `hybrid`, `vps_only`) | Codex Phase 2 |
| `autonomy.level` | Operator → Ustawienia → Poziom autonomii | `manual` wymusza D3+ na wszystkich kartach (U5) | Codex Phase 2 |
| `infrastructure.trusted_providers` | Preferencje → Bezpieczeństwo | Whitelist hostingu | Codex Phase 2 |

W chwili obecnej heurystyka działa na sztywno — przyszła rozszerzalność jest zaplanowana, ale nie ma jej w kodzie Etapu 1.

### 3.3. Konfiguracja workload profile

Wejście do `recommend_topology` to dictionary z kluczami:

| Klucz | Typ | Default | Walidacja |
|---|---|---|---|
| `estimated_tokens_per_day` | `int` | `0` | `None` lub negatywne → `0` |
| `parallelism` | `int` | `1` | `None` lub `< 1` → `1` |
| `latency_target_seconds` | `float` | `10.0` | `None` lub `<= 0` → `10.0` |
| `project_id` | `str` | `""` | przekazywane do `ScalingCard.project_id` |

Wszystkie pola defensywne — moduł nie podnosi wyjątków przy złym wejściu, tylko sanityzuje.

### 3.4. Konfiguracja środowiska (rejestracja Env)

| Klucz | Typ | Default | Notatki |
|---|---|---|---|
| `env_id` | `str` | auto-uuid | Jeśli puste, generowane w `__post_init__`. UPSERT po tym kluczu. |
| `operator_id` | `str` | `""` | Wymagane do filtrowania w `get_env_inventory`. |
| `name` | `str` | `""` | Friendly name (np. `vps-warsaw-prod`). |
| `kind` | `str` | `""` | `local` / `vps` / `hybrid` (konwencja, brak enforcement). |
| `capacity_tokens_per_day` | `int` | `0` | Górny limit przepustowości środowiska. |
| `registered_at` | `float` | auto-`time.time()` | Unix epoch. |

---

## 4. Funkcje gRPC / Service API

Moduł eksponuje **4 publiczne metody** w klasie `ScalingService`. Etap 1 nie ma jeszcze gRPC server stuba — `grpc_server.py` jest scaffoldem do podpięcia w Etapie 2. Wszystkie wywołania w Etapie 1 idą przez Python in-process call.

### 4.1. `recommend_topology(operator_id, project_id, workload_profile) -> ScalingCard`

**Sygnatura**:

```python
def recommend_topology(
    self,
    operator_id: str,
    project_id: str,
    workload_profile: dict[str, Any],
) -> ScalingCard
```

**Działanie**:

1. Kopiuje `workload_profile` (defensywnie), wstrzykuje `project_id`.
2. Woła pure-function `topology_recommender.recommend_topology(operator_id, workload)`.
3. Emituje event `aeis.advisor.scaling.topology_recommended` z payloadem zawierającym `card_id`, `operator_id`, `project_id`, `recommended`, `d_level`.
4. Loguje na poziomie INFO: `"recommended topology %s for %s (D%s)"`.
5. Zwraca pełny `ScalingCard`.

**Przykład wejścia**:

```python
profile = {
    "estimated_tokens_per_day": 750_000,
    "parallelism": 2,
    "latency_target_seconds": 8.0,
}
card = service.recommend_topology(
    operator_id="op_alice",
    project_id="proj_42",
    workload_profile=profile,
)
```

**Przykład wyjścia** (JSON):

```json
{
  "card_id": "f3a2c8e44b7e4f5e9bc6d12a87913456",
  "operator_id": "op_alice",
  "project_id": "proj_42",
  "recommended": "local_plus_vps",
  "alternatives": ["local_only", "multi_vps"],
  "d_level": "D3",
  "evidence_pack_id": "evp_scaling_local_plus_vps",
  "human_gate_required": true,
  "impacts": {
    "monthly_cost_usd": 20,
    "max_parallelism": 2,
    "latency_estimate_seconds": 6.4
  }
}
```

### 4.2. `propose_staging_plan(current_topology, target_topology) -> StagingPlan`

**Sygnatura**:

```python
def propose_staging_plan(
    self,
    current_topology: str,
    target_topology: str,
) -> StagingPlan
```

**Działanie**:

1. Woła `staging_planner.propose_staging_plan(current, target)`.
2. Emituje event `aeis.advisor.scaling.staging_proposed` z payloadem `plan_id`, `current`, `target`, `phases` (liczba faz, nie pełne).
3. Zwraca pełny `StagingPlan`.

**Przykład**:

```python
plan = service.propose_staging_plan("local_only", "vps_only")
# Wynik: 2 fazy
# 1. deploy_env local_plus_vps
# 2. deploy_env vps_only
```

JSON wynikowy:

```json
{
  "plan_id": "ab12cd34ef567890",
  "current_topology": "local_only",
  "target_topology": "vps_only",
  "phases": [
    {
      "phase": 1,
      "action": "deploy_env",
      "topology": "local_plus_vps",
      "description": "Deploy local_plus_vps environment"
    },
    {
      "phase": 2,
      "action": "deploy_env",
      "topology": "vps_only",
      "description": "Deploy vps_only environment"
    }
  ]
}
```

### 4.3. `get_env_inventory(operator_id) -> list[dict[str, Any]]`

**Sygnatura**:

```python
def get_env_inventory(self, operator_id: str) -> list[dict[str, Any]]
```

**Działanie**: Czyta z PG `scaling_envs WHERE operator_id = %s ORDER BY registered_at`, mapuje wiersze na `Env`, zwraca listę `to_dict()`. NIE emituje eventów — to read-only operacja.

**Przykład**:

```python
envs = service.get_env_inventory("op_alice")
# [
#   {"env_id": "...", "operator_id": "op_alice", "name": "laptop-main",
#    "kind": "local", "capacity_tokens_per_day": 500000, "registered_at": 1714123456.0},
#   {"env_id": "...", "operator_id": "op_alice", "name": "vps-warsaw",
#    "kind": "vps", "capacity_tokens_per_day": 2000000, "registered_at": 1714234567.0}
# ]
```

### 4.4. `register_env(env_data) -> dict[str, Any]`

**Sygnatura**:

```python
def register_env(self, env_data: dict[str, Any]) -> dict[str, Any]
```

**Działanie**:

1. Tworzy `Env` (auto-uuid jeśli `env_id` puste, auto-`time.time()` jeśli `registered_at == 0`).
2. UPSERT do `scaling_envs` po `env_id`.
3. Emituje event `aeis.advisor.scaling.env_registered` z payloadem `env_id`, `operator_id`, `kind`.
4. Zwraca `env.to_dict()`.

**Przykład**:

```python
result = service.register_env({
    "operator_id": "op_alice",
    "name": "vps-warsaw-prod",
    "kind": "vps",
    "capacity_tokens_per_day": 2_000_000,
})
# {"env_id": "auto-generated-uuid", ...}
```

Re-rejestracja istniejącego `env_id`:

```python
service.register_env({
    "env_id": "existing-uuid",
    "operator_id": "op_alice",
    "name": "vps-warsaw-prod-v2",   # zmiana nazwy
    "kind": "vps",
    "capacity_tokens_per_day": 3_000_000,  # bump capacity
})
# UPDATE w PG, ten sam env_id, nowa nazwa i capacity
```

### 4.5. Helpery modułowe

Spoza klasy:

- `get_scaling_service(event_bus=None) -> ScalingService` — singleton accessor, lazy-init.
- `reset_scaling_service() -> None` — reset singleton dla testów.

### 4.6. Wstępny scaffold gRPC (Etap 2)

`grpc_server.py` zawiera placeholder na cztery RPC:

| RPC | Sygnatura proto (planowana) | Mapowanie do `ScalingService` |
|---|---|---|
| `RecommendTopology` | `RecommendTopologyRequest → ScalingCard` | `recommend_topology` |
| `ProposeStagingPlan` | `ProposeStagingPlanRequest → StagingPlan` | `propose_staging_plan` |
| `GetEnvInventory` | `GetEnvInventoryRequest → EnvList` | `get_env_inventory` |
| `RegisterEnv` | `RegisterEnvRequest → Env` | `register_env` |

### 4.5. gRPC Servicer — `ScalingServicer` (sprint3, zaimplementowany)

Plik: `sylion/aeis/advisor/scaling/grpc_server.py`. Sprint3 wypełnił stub prawdziwymi implementacjami.

| RPC | Request pola | Opis |
|-----|-------------|------|
| `RecommendTopology` | `operator_id, project_id, workload_profile{estimated_tokens_per_day, parallelism, latency_target_seconds}` | Woła `recommend_topology(...)`. Zwraca `ScalingCard`. |
| `ProposeStagingPlan` | `current_topology, target_topology` | Woła `propose_staging_plan(...)`. Zwraca `StagingPlan{plan_id, phases[]}`. |
| `GetEnvInventory` | `operator_id` | Woła `get_env_inventory(operator_id)`. Zwraca `GetEnvInventoryResponse{envs[]}`. |
| `RegisterEnv` | `name, kind, capacity_tokens_per_day` | Woła `register_env(env_data)`. Zwraca `Env`. |

Pełen kontrakt proto trafi do `sylion.contracts.protos.advisor.scaling.v1` w Etapie 3. Rejestracja: `register_scaling_service(server, service=None) -> bool`.

---

## 5. Eventy emitowane

Moduł emituje **3 eventy** na szynie `EventBus` (przez `SylionEvent`). Wszystkie eventy mają:

- `event_id`: auto-`uuid.uuid4().hex`
- `source_module`: `"sylion.aeis.advisor.scaling"`
- `timestamp`: `time.time()` (Unix epoch float)

### 5.1. `aeis.advisor.scaling.topology_recommended`

**Trigger**: `ScalingService.recommend_topology()` po zbudowaniu `ScalingCard`.

**Payload**:

```json
{
  "card_id": "f3a2c8e44b7e4f5e9bc6d12a87913456",
  "operator_id": "op_alice",
  "project_id": "proj_42",
  "recommended": "local_plus_vps",
  "d_level": "D3"
}
```

**Subskrybenci (typowi)**:
- `audit_trail` — zapis decyzji topologii do append-only ledger.
- `engine` — może użyć rekomendacji do enrichmentu kart projektowych.
- `subscription` — sprawdza, czy operator ma budżet na rekomendowany VPS.
- `mobile_gateway` (Etap 2) — push-notify operatora o nowej karcie.

### 5.2. `aeis.advisor.scaling.staging_proposed`

**Trigger**: `ScalingService.propose_staging_plan()` po wygenerowaniu planu.

**Payload**:

```json
{
  "plan_id": "ab12cd34ef567890",
  "current": "local_only",
  "target": "vps_only",
  "phases": 2
}
```

> Uwaga: payload zawiera tylko **liczbę faz** (`phases: int`), nie pełną listę. Pełen plan dostępny jest tylko z return value `propose_staging_plan` (nie jest replikowany do eventu — minimalizuje payload size).

**Subskrybenci**:
- `audit_trail` — historia decyzji staging.
- `idea_vault` (Etap 2) — może wstrzymać projekt na czas migracji.

### 5.3. `aeis.advisor.scaling.env_registered`

**Trigger**: `ScalingService.register_env()` po commit do PG.

**Payload**:

```json
{
  "env_id": "vps_warsaw_2025",
  "operator_id": "op_alice",
  "kind": "vps"
}
```

**Subskrybenci**:
- `audit_trail` — kto kiedy dodał środowisko.
- `subscription` — przelicza budżet (nowy VPS = potencjalny nowy koszt).
- `monitoring` (Etap 2) — startuje health check na nowym Env.

### 5.4. Eventy subskrybowane

```json
"events_subscribe": []
```

Moduł **nie subskrybuje** żadnych eventów. Działa wyłącznie reaktywnie na bezpośrednie wywołania API.

### 5.5. Best-effort emit pattern

Implementacja w `service.py`:

```python
def _emit(self, topic: str, payload: dict[str, Any]) -> None:
    if self._event_bus:
        self._event_bus.publish(SylionEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            source_module="sylion.aeis.advisor.scaling",
            timestamp=time.time(),
        ))
```

Jeśli `event_bus` jest `None` (np. test bez injektu), emit jest no-opem. **Brak fallbacku** — w produkcji `event_bus` jest gwarantowany przez `get_event_bus()`.

> W odróżnieniu od `mobile_gateway`, który łyka wyjątki z bus.publish (try/except), `scaling.service._emit` przepuszcza wyjątki w górę. To celowy design: błąd publishera w core path scalingu (np. PG niedostępny dla audit trail) musi być widoczny.

---

## 6. Database tables

Moduł korzysta z **jednego schematu PG**: `scaling_envs`. Migration zarządzana przez Alembic w `sylion.aeis.advisor._db`.

### 6.1. Tabela `scaling_envs`

| Kolumna | Typ | Constraints | Opis |
|---|---|---|---|
| `env_id` | `TEXT` | PRIMARY KEY | UUID hex środowiska |
| `operator_id` | `TEXT` | NOT NULL | Właściciel środowiska (operator scope) |
| `name` | `TEXT` | NOT NULL | Friendly name (np. `vps-warsaw-prod`) |
| `kind` | `TEXT` | NOT NULL | `local` / `vps` / `hybrid` (konwencja) |
| `capacity_tokens_per_day` | `BIGINT` | DEFAULT 0 | Limit przepustowości |
| `registered_at` | `DOUBLE PRECISION` | NOT NULL | Unix epoch |

**Indeksy**:
- PK na `env_id` (auto)
- Index na `(operator_id, registered_at)` dla szybkiego listingu (rekomendowany dla Etapu 2; w Etapie 1 wystarczy seq scan).

**DDL (referencyjny — faktyczny w Alembic migration)**:

```sql
CREATE TABLE IF NOT EXISTS scaling_envs (
    env_id                  TEXT PRIMARY KEY,
    operator_id             TEXT NOT NULL,
    name                    TEXT NOT NULL,
    kind                    TEXT NOT NULL,
    capacity_tokens_per_day BIGINT NOT NULL DEFAULT 0,
    registered_at           DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scaling_envs_operator_registered
    ON scaling_envs (operator_id, registered_at);
```

### 6.2. Operacje CRUD

| Operacja | SQL | Wywołanie |
|---|---|---|
| Insert | `INSERT ... ON CONFLICT (env_id) DO UPDATE SET ...` | `register_env(env_data)` |
| List | `SELECT * FROM scaling_envs WHERE operator_id = %s ORDER BY registered_at` | `get_env_inventory(operator_id)` |
| Update | (UPSERT — przez Insert) | `register_env({"env_id": existing, ...})` |
| Delete | (brak w API Etapu 1) | brak |

> **Brak DELETE w API**: W Etapie 1 środowiska są **append-only**. Wycofanie środowiska wymaga ręcznego DELETE w PG lub dedykowanej operacji administracyjnej. W Etapie 2 zaplanowano `decommission_env(env_id)` z mechanizmem soft-delete (kolumna `decommissioned_at`).

### 6.3. Brak innych tabel

- `ScalingCard` jest **ulotna** — nie jest persistowana w bazie. Każde wywołanie `recommend_topology` produkuje nowy `card_id`.
- `StagingPlan` jest **ulotny** — nie jest persistowany. Karta planu wygenerowana per request.

Persystencja kart i planów jest planowana na Etap 2 jako część `engine.recommendations` (gdzie scaling cards będą jednym z typów envelope).

---

## 7. Przykład użycia

### 7.1. Pełny flow operatora — od zera do zarejestrowanego VPS

```python
from sylion.aeis.advisor.scaling.service import get_scaling_service
from sylion.core.event_bus import get_event_bus

# Krok 1: Operator zaczyna projekt
service = get_scaling_service(event_bus=get_event_bus())

# Krok 2: Engine pyta scaling o rekomendację dla nowego projektu
profile = {
    "estimated_tokens_per_day": 500_000,
    "parallelism": 2,
    "latency_target_seconds": 5.0,
}
card = service.recommend_topology(
    operator_id="op_alice",
    project_id="proj_research_ai",
    workload_profile=profile,
)

print(card.recommended)         # "local_plus_vps"
print(card.d_level)             # "D3"
print(card.human_gate_required) # True
print(card.evidence_pack_id)    # "evp_scaling_local_plus_vps"
print(card.impacts)
# {'monthly_cost_usd': 20, 'max_parallelism': 2, 'latency_estimate_seconds': 4.0}

# Krok 3: Operator akceptuje rekomendację (D3 → przez Human Gate i biometric step-up w mobile)
# (To dzieje się poza modułem scaling — engine + actions + human_gate)

# Krok 4: Operator zarejestrował fizycznie VPS (kupił u dostawcy)
env = service.register_env({
    "operator_id": "op_alice",
    "name": "vps-warsaw-prod-1",
    "kind": "vps",
    "capacity_tokens_per_day": 2_000_000,
})
print(env["env_id"])     # auto-uuid hex
print(env["registered_at"])  # 1714234567.123

# Krok 5: Operator listuje swoje środowiska
envs = service.get_env_inventory("op_alice")
for e in envs:
    print(f"{e['name']} ({e['kind']}) — cap={e['capacity_tokens_per_day']}")
# laptop-main (local) — cap=500000
# vps-warsaw-prod-1 (vps) — cap=2000000
```

### 7.2. Scale-up z planem etapowym

```python
# Operator decyduje skalować z local_only → multi_vps
plan = service.propose_staging_plan(
    current_topology="local_only",
    target_topology="multi_vps",
)

print(plan.plan_id)
# "f9e8d7c6b5a4321098765432109abcde"

print(plan.current_topology, "→", plan.target_topology)
# local_only → multi_vps

for phase in plan.phases:
    print(f"  Phase {phase['phase']}: {phase['action']} → {phase.get('topology', 'n/a')}")
    print(f"    {phase['description']}")
# Phase 1: deploy_env → local_plus_vps
#   Deploy local_plus_vps environment
# Phase 2: deploy_env → vps_only
#   Deploy vps_only environment
# Phase 3: deploy_env → multi_vps
#   Deploy multi_vps environment
```

### 7.3. Scale-down z multi_vps do local_only

```python
plan = service.propose_staging_plan("multi_vps", "local_only")
# Phase 1: decommission_env → multi_vps
# Phase 2: decommission_env → vps_only
# Phase 3: decommission_env → local_plus_vps

# Uwaga: kolejność dekomisji jest reverse — od najbardziej rozproszonej do najmniejszej
```

### 7.4. No-op staging plan (current == target)

```python
plan = service.propose_staging_plan("vps_only", "vps_only")
# Phase 1: no_change → "Current and target topology are the same"
```

### 7.5. Heurystyka — edge cases

```python
# Edge case 1: brak danych w workload — defaults
card = service.recommend_topology(
    operator_id="op_x",
    project_id="proj_x",
    workload_profile={},  # pusty
)
# → recommended="local_only" (tokens=0 < 100k, parallelism=1)
# → d_level="D2"
# → human_gate_required=False

# Edge case 2: ujemne tokens (defensive)
card = service.recommend_topology(
    operator_id="op_x",
    project_id="proj_x",
    workload_profile={"estimated_tokens_per_day": -1_000_000, "parallelism": 1},
)
# → recommended="local_only" (sanityzacja: tokens=-x → 0)

# Edge case 3: wysoki tokens, niski parallelism
card = service.recommend_topology(
    operator_id="op_x",
    project_id="proj_x",
    workload_profile={"estimated_tokens_per_day": 5_000_000, "parallelism": 1},
)
# → tokens >= 1M, parallelism (1) <= 3 → wpada w "else" → recommended="vps_only"
# → d_level="D3"

# Edge case 4: bardzo wysoki parallelism, średnie tokens
card = service.recommend_topology(
    operator_id="op_x",
    project_id="proj_x",
    workload_profile={"estimated_tokens_per_day": 500_000, "parallelism": 10},
)
# → tokens (500k) < 1M → wpada w branch "local_plus_vps" (NIE w multi_vps!)
# → recommended="local_plus_vps"
# → impacts.max_parallelism=2 (mimo że request był dla 10 — heurystyka konserwatywna)
```

### 7.6. Przykład odbioru eventów

```python
from sylion.core.event_bus import get_event_bus

bus = get_event_bus()

def on_topology(event):
    p = event.payload
    print(f"[topology] {p['recommended']} D{p['d_level']} for {p['project_id']}")

def on_staging(event):
    p = event.payload
    print(f"[staging] {p['current']}→{p['target']} ({p['phases']} faz)")

def on_env(event):
    p = event.payload
    print(f"[env_registered] {p['kind']} for {p['operator_id']}")

bus.subscribe("aeis.advisor.scaling.topology_recommended", on_topology)
bus.subscribe("aeis.advisor.scaling.staging_proposed", on_staging)
bus.subscribe("aeis.advisor.scaling.env_registered", on_env)
```

### 7.7. Test izolowany (pattern test fixture)

```python
import pytest
from sylion.aeis.advisor.scaling.service import (
    get_scaling_service,
    reset_scaling_service,
)

@pytest.fixture(autouse=True)
def reset_singleton():
    reset_scaling_service()
    yield
    reset_scaling_service()

def test_recommend_local_for_small_workload():
    service = get_scaling_service(event_bus=None)  # bez busa
    card = service.recommend_topology(
        operator_id="op_test",
        project_id="proj_test",
        workload_profile={
            "estimated_tokens_per_day": 50_000,
            "parallelism": 1,
        },
    )
    assert card.recommended == "local_only"
    assert card.d_level == "D2"
    assert card.human_gate_required is False
    assert card.evidence_pack_id is None
    assert card.impacts["monthly_cost_usd"] == 0
```

---

## 8. Verification — checklist akceptacyjny

### 8.1. Smoke test API

| # | Test | Oczekiwane |
|---|---|---|
| 1 | `service = get_scaling_service()` zwraca obiekt | non-None |
| 2 | Drugi call `get_scaling_service()` zwraca ten sam obiekt | identical reference |
| 3 | `recommend_topology(operator_id="x", project_id="p", workload_profile={})` | `ScalingCard(recommended="local_only", d_level="D2")` |
| 4 | `propose_staging_plan("local_only", "local_only")` | `phases=[{action: "no_change"}]` |
| 5 | `register_env({"operator_id": "x", "name": "n", "kind": "local"})` | dict z auto-`env_id`, `registered_at` > 0 |
| 6 | `get_env_inventory("x")` | lista zawierająca dopiero co zarejestrowany env |

### 8.2. Heurystyka — pełen branch coverage

| # | Tokens | Parallelism | Spodziewana topologia | D-level | monthly_cost_usd |
|---|---|---|---|---|---|
| H1 | 50 000 | 1 | `local_only` | D2 | 0 |
| H2 | 99 999 | 1 | `local_only` | D2 | 0 |
| H3 | 100 000 | 1 | `local_plus_vps` | D3 | 20 |
| H4 | 50 000 | 2 | `local_plus_vps` | D3 | 20 |
| H5 | 999 999 | 3 | `local_plus_vps` | D3 | 20 |
| H6 | 1 000 000 | 1 | `vps_only` | D3 | 40 |
| H7 | 1 000 000 | 4 | `multi_vps` | D4 | 60 |
| H8 | 5 000 000 | 10 | `multi_vps` | D4 | 60 |

### 8.3. Staging — pełna macierz przejść

| # | Current | Target | Phases | Akcje |
|---|---|---|---|---|
| S1 | `local_only` | `local_only` | 1 | no_change |
| S2 | `local_only` | `local_plus_vps` | 1 | deploy local_plus_vps |
| S3 | `local_only` | `vps_only` | 2 | deploy local_plus_vps, deploy vps_only |
| S4 | `local_only` | `multi_vps` | 3 | deploy local_plus_vps, deploy vps_only, deploy multi_vps |
| S5 | `local_plus_vps` | `local_only` | 1 | decommission local_plus_vps |
| S6 | `local_plus_vps` | `vps_only` | 1 | deploy vps_only |
| S7 | `vps_only` | `local_only` | 2 | decommission vps_only, decommission local_plus_vps |
| S8 | `multi_vps` | `local_only` | 3 | decommission multi_vps, vps_only, local_plus_vps |
| S9 | `multi_vps` | `vps_only` | 1 | decommission multi_vps |
| S10 | `vps_only` | `multi_vps` | 1 | deploy multi_vps |

### 8.4. Eventy

| # | Akcja | Spodziewany event | Subset payload |
|---|---|---|---|
| E1 | `recommend_topology(...)` | `aeis.advisor.scaling.topology_recommended` | `{card_id, operator_id, project_id, recommended, d_level}` |
| E2 | `propose_staging_plan(a, b)` z różnymi a, b | `aeis.advisor.scaling.staging_proposed` | `{plan_id, current, target, phases}` |
| E3 | `register_env({...})` | `aeis.advisor.scaling.env_registered` | `{env_id, operator_id, kind}` |
| E4 | `recommend_topology` z `event_bus=None` | brak emit (no-op) | n/a |

### 8.5. PG persistence

| # | Test | Oczekiwane |
|---|---|---|
| P1 | Po `register_env` w `scaling_envs` jest 1 wiersz z poprawnym `env_id` | row exists |
| P2 | Drugi `register_env` z tym samym `env_id` aktualizuje wiersz (UPSERT) | 1 wiersz, zaktualizowane pola |
| P3 | `register_env` różnych operatorów — `get_env_inventory` zwraca tylko ich własne | scope-isolated |
| P4 | Sortowanie w `get_env_inventory` po `registered_at ASC` | poprawna kolejność |
| P5 | Brak rekordu — `get_env_inventory("nieistniejacy")` zwraca `[]` | empty list |

### 8.6. Defensive coding — sanityzacja

| # | Wejście | Spodziewane |
|---|---|---|
| D1 | `workload_profile={"estimated_tokens_per_day": None}` | tokens → 0 |
| D2 | `workload_profile={"estimated_tokens_per_day": -1000}` | tokens → 0 |
| D3 | `workload_profile={"parallelism": None}` | parallelism → 1 |
| D4 | `workload_profile={"parallelism": 0}` | parallelism → 1 |
| D5 | `workload_profile={"latency_target_seconds": None}` | latency → 10.0 |
| D6 | `workload_profile={"latency_target_seconds": -5.0}` | latency → 10.0 |
| D7 | `workload_profile={}` (pusty) | wszystko → defaulty, recommended="local_only" |

### 8.7. Idempotentność

| # | Scenariusz | Oczekiwane |
|---|---|---|
| I1 | Dwa wywołania `recommend_topology` z tym samym profile | różne `card_id`, ale ten sam `recommended`, `d_level`, `impacts` |
| I2 | Dwa wywołania `propose_staging_plan(a, b)` | różne `plan_id`, ale identyczne `phases` |
| I3 | Dwa razy `register_env` z tym samym `env_id` | 1 wiersz w PG, drugi UPSERT |

### 8.8. Edge case — invalid topology

| # | Test | Oczekiwane |
|---|---|---|
| X1 | `propose_staging_plan("invalid", "local_only")` | `current_idx = -1`, `target_idx = 0` → scale-down? trzeba sprawdzić |
| X2 | `propose_staging_plan("local_only", "")` | `target_idx = -1` → trzeba sprawdzić |

> **Znana ograniczenia**: Funkcja `propose_staging_plan` przy nieprawidłowych nazwach topologii NIE rzuca wyjątku, ale generuje plan oparty o `index = -1`, co prowadzi do nieoczywistych slice'ów. **Konsument odpowiada za walidację**. W Etapie 2 plan dostanie eksplicytną walidację i zwróci błąd zamiast generować śmieci. Patrz: rozdział 9 troubleshooting.

---

## 9. Troubleshooting

### 9.1. AEIS zawsze rekomenduje `local_only`, choć projekt jest duży

**Symptom**: Nawet dla 10M tokenów/dzień rekomendacja to `local_only`, brak VPS.

**Przyczyna**: Pole `estimated_tokens_per_day` w profilu obciążenia jest `None`, ujemne lub nie zostało przekazane do modułu — sanityzacja na 0 powoduje wpadnięcie w pierwszy branch (`< 100k AND parallelism == 1`).

**Diagnoza**:

```python
profile = {"estimated_tokens_per_day": None}
# w recommend_topology defensive coerce: tokens = 0
# wynik: local_only (False positive)
```

**Rozwiązanie**:

1. W panelu **Projekt → Profil obciążenia** upewnij się, że pole *Szacowane tokeny/dzień* jest wypełnione liczbą dodatnią.
2. Sprawdź, czy `parallelism > 0` (jeśli `0` lub brak, moduł przyjmuje 1).
3. W kodzie wywołującym dodaj walidację przed `recommend_topology`:

```python
if not profile.get("estimated_tokens_per_day"):
    raise ValueError("workload_profile.estimated_tokens_per_day must be set")
```

4. Wyczyść pamięć podręczną UI i wygeneruj rekomendację na nowo.

### 9.2. Przy staging planie pojawia się `ValueError: ... is not in list`

**Symptom**: Czerwony błąd przy próbie wygenerowania planu zmiany topologii.

**Przyczyna**: Nazwa topologii nie jest w `TOPOLOGY_ORDER` (literówka, przestarzała nazwa, case mismatch).

**Diagnoza**: `current_topology` lub `target_topology` musi być dokładnie jednym z:
- `"local_only"`
- `"local_plus_vps"`
- `"vps_only"`
- `"multi_vps"`

**Rozwiązanie**:

1. Upewnij się, że używasz dokładnie jednej z tych nazw — case-sensitive.
2. Najczęstsze pomyłki: `local`, `vps`, `cloud`, `multi-vps` (z myślnikiem). Zawsze używaj snake_case.
3. Jeśli używasz API bezpośrednio — waliduj wcześniej:

```python
VALID = {"local_only", "local_plus_vps", "vps_only", "multi_vps"}
if current not in VALID or target not in VALID:
    raise ValueError(f"unknown topology: {current} / {target}")
```

### 9.3. Karta VPS ma D-level D2 zamiast D3

**Symptom**: AEIS pokazuje rekomendację `vps_only` lub `local_plus_vps`, ale `d_level = "D2"` i `human_gate_required = False`.

**Przyczyna**: Niezgodność z heurystyką — `recommend_topology` **zawsze** ustawia `d_level=D3` dla `local_plus_vps` i `vps_only`, oraz `D4` dla `multi_vps`. Jeśli widzisz D2 dla nie-local — to **bug** w pipeline'ie pomiędzy modułem a UI.

**Diagnoza**:

1. Sprawdź log eventu `aeis.advisor.scaling.topology_recommended`:

```bash
grep "scaling.topology_recommended" /var/log/sylion/event_bus.log | tail -5
```

Payload powinien zawierać `"d_level": "D3"` lub `"D4"`.

2. Jeśli payload zawiera `D3+`, ale UI pokazuje D2 — problem jest w `engine` lub renderingu UI, nie w scaling.
3. Jeśli payload zawiera `D2` dla `vps_only` — to bug w `recommend_topology`. Zgłoś z reproduktorem.

**Rozwiązanie**:

1. Tymczasowo wymuś `manual` autonomy w **Operator → Ustawienia → Poziom autonomii** (każda karta dostanie D3+ niezależnie od engine).
2. Patrz log eventu — porównaj wartość emitowaną z wyświetlaną.
3. Jeśli to bug w heurystyce — zgłoś do zespołu Claude territory (zmiana w `topology_recommender.py`).

### 9.4. Rejestracja środowiska nie pojawia się w inventory

**Symptom**: Dodano VPS w panelu, ale lista `get_env_inventory(operator_id)` jest pusta.

**Przyczyna**:
- `operator_id` w rejestracji nie zgadza się z aktualnym operatorem.
- Connection pool PG nie odświeżył się.
- Migracja Alembica nie została zaaplikowana (`scaling_envs` nie istnieje).

**Diagnoza**:

```bash
# 1. Sprawdź event
grep "scaling.env_registered" /var/log/sylion/event_bus.log

# 2. Sprawdź bezpośrednio w PG
psql -d sylion -c "SELECT env_id, operator_id, name FROM scaling_envs ORDER BY registered_at DESC LIMIT 10;"

# 3. Sprawdź migracje
alembic -c alembic.ini current
alembic -c alembic.ini history | grep scaling
```

**Rozwiązanie**:

1. Zweryfikuj `operator_id` przekazany w `register_env` — porównaj z `current_operator_id` w sesji UI.
2. Upewnij się, że migracja `*_create_scaling_envs.py` jest zaaplikowana (`alembic upgrade head`).
3. Restart procesu Advisor — czasami connection pool nie zauważa nowych tabel.
4. Sprawdź logi PG: `tail -100 /var/log/postgresql/postgresql-*.log | grep ERROR`.

### 9.5. Scale-up i scale-down dają ten sam plan (no_change)

**Symptom**: `propose_staging_plan(a, b)` zwraca tylko 1 fazę `no_change`.

**Przyczyna**: `current_topology == target_topology` — celowe zachowanie.

**Rozwiązanie**:

1. Sprawdź w karcie *Aktualna topologia* — być może już jesteś na celu.
2. Jeśli celowo nie zmieniasz — to prawidłowe zachowanie.
3. Jeśli chcesz inny target — wybierz inną topologię docelową.

### 9.6. Plan staging skip-uje topologię pośrednią

**Symptom**: Plan dla `local_only → multi_vps` MA fazę `local_plus_vps` i `vps_only`. Operator chciałby przeskoczyć (deploy bezpośrednio na multi_vps).

**Przyczyna**: Algorytm zawsze przechodzi przez wszystkie pośrednie topologie w `TOPOLOGY_ORDER` — to **konwencjonalne zachowanie** dla bezpieczeństwa.

**Rozwiązanie**:

W Etapie 1 — brak. W Etapie 2 zaplanowano flagę `skip_intermediate=True`, która zwróci 1-fazowy plan z bezpośrednim deployem. W chwili obecnej operator może ręcznie usunąć fazy lokalnie po wygenerowaniu planu (nie commit do PG, bo plan nie jest persistowany).

### 9.7. Event `topology_recommended` nie pojawia się na bus-ie

**Symptom**: Po `recommend_topology` event nie jest odbierany przez subskrybentów.

**Przyczyna**:
- `event_bus=None` przekazany do `ScalingService` (test-mode).
- `event_bus` upadł / connection lost.
- Subskrybent zapisał się PO emit (race).

**Diagnoza**:

```python
service = get_scaling_service()
print(service._event_bus)  # czy jest non-None?

# jeśli None — singleton został zainicjalizowany bez busa (np. w teście wcześniej):
from sylion.aeis.advisor.scaling.service import reset_scaling_service
reset_scaling_service()
service = get_scaling_service(event_bus=get_event_bus())  # ponowna init z busem
```

**Rozwiązanie**:

1. Restartuj proces Advisor — singleton dostanie świeży `event_bus`.
2. Upewnij się, że subskrybent registruje się PRZED pierwszym wywołaniem `recommend_topology`.
3. Sprawdź `EventBus.subscribers` — czy callback jest na liście dla danego topiku.

### 9.8. Wysoki koszt mimo `local_only`

**Symptom**: `card.impacts.monthly_cost_usd` > 0 dla `recommended == "local_only"`.

**Przyczyna**: To **nigdy** nie powinno się zdarzyć — heurystyka hard-coduje `monthly_cost_usd: 0` dla `local_only`. Jeśli widzisz inną wartość, to mutacja po fakcie.

**Diagnoza**:

```python
card = service.recommend_topology(...)
assert card.recommended == "local_only" and card.impacts["monthly_cost_usd"] == 0
```

**Rozwiązanie**: Zgłoś bug — to invariant ekosystemu. Sprawdź, czy żaden middleware nie modyfikuje `card.impacts` po returnie z service.

---

## 10. Cross-references

### 10.1. Moduły zależne (downstream consumers)

| Moduł | Zależność | Plik |
|---|---|---|
| `sylion.aeis.advisor.engine` | Zaczytuje rekomendację scaling do enrichmentu kart projektów. | [`docs/dokumentacja/modules/01_engine.md`](./01_engine.md) (w przyszłości) |
| `sylion.aeis.advisor.subscription` | Liczy ROI/koszt VPS — używa `card.impacts.monthly_cost_usd`. | [`10_subscription.md`](./10_subscription.md) |
| `sylion.aeis.advisor.variants` | Wariant `aggressive` (council=7) może wymagać `multi_vps`; sprawdza w scaling. | [`09_variants.md`](./09_variants.md) |
| `sylion.aeis.advisor.role_resolver` | Zwraca modele lokalne/zewnętrzne; scaling decyduje, czy infrastruktura im sprosta. | [`08_role_resolver.md`](./08_role_resolver.md) |
| `sylion.aeis.advisor.mobile_gateway` | Operator akceptuje karty topologii z mobile (D3+ → biometric step-up). | [`12_mobile_gateway.md`](./12_mobile_gateway.md) |
| `sylion.aeis.advisor.audit_trail` | Subskrybuje wszystkie 3 eventy scalingu — append-only audit. | (Etap 2) |

### 10.2. Moduły niezależne (depends_on: [])

Scaling nie ma zależności od innych modułów Advisora. Jest **liściem grafu zależności** — można go testować w pełnej izolacji bez stubowania niczego (poza event_bus, który jest opcjonalny).

### 10.3. Dokumenty architektoniczne

- [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — Decision Ladder D0-D5; D3+ wymaga Evidence Pack i Human Gate; mapowanie scaling → D-level.
- [`docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md`](../../claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md) — wymagana zawartość Evidence Pack przy scale-up; co rejestrować jako evidence dla zmiany topologii.
- [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — pełna taksonomia eventów Advisor; scaling owns 3 eventy w przestrzeni `aeis.advisor.scaling.*`.

### 10.4. Code references

- **Service**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/service.py:22-101` — klasa `ScalingService` + singleton.
- **Heurystyka**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/topology_recommender.py:10-77` — pure function `recommend_topology`.
- **Staging**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/staging_planner.py:10-58` — pure function `propose_staging_plan` + `TOPOLOGY_ORDER` constant.
- **Inventory**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/env_inventory.py:14-60` — PG persistence dla Env.
- **Models**: `src/sylion-pipeline/sylion/aeis/advisor/scaling/_models.py:11-90` — dataclasses ScalingCard / Env / StagingPlan.
- **Manifest**: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.scaling.json`.

### 10.5. Operator-facing README

Wewnętrzna dokumentacja operatorska (Polish, krótka): [`src/sylion-pipeline/sylion/aeis/advisor/scaling/README.md`](../../../src/sylion-pipeline/sylion/aeis/advisor/scaling/README.md).

### 10.6. Testy złote (planowane Etap 1 → Etap 2)

- `tests/aeis/advisor/scaling/test_recommend_topology.py` — pełna macierz heurystyki (8 wierszy w sekcji 8.2).
- `tests/aeis/advisor/scaling/test_staging_planner.py` — macierz przejść (10 wierszy w sekcji 8.3).
- `tests/aeis/advisor/scaling/test_env_inventory.py` — UPSERT, scope, sortowanie.
- `tests/aeis/advisor/scaling/test_events.py` — emit każdego z 3 eventów.

### 10.7. Rola w Decision Ladder

| D-level | Topologie | Wymagania |
|---|---|---|
| D0-D1 | (brak — scaling nie operuje na D1) | n/a |
| D2 | `local_only` | brak Evidence Pack, brak Human Gate, autonomous |
| D3 | `local_plus_vps`, `vps_only` | Evidence Pack `evp_scaling_<topology>`, Human Gate, biometric step-up dla mobile |
| D4 | `multi_vps` | Evidence Pack, Human Gate, biometric step-up, dodatkowo cost-sentinel review |
| D5 | (zarezerwowane Etap 2) | n/a |

### 10.8. Współzależność z subscription

Operator akceptujący kartę `vps_only` (D3, $40/m) musi mieć w `subscription` budżet conjuncta:
- ROI > 30% (próg downgrade jest w subscription),
- D3 → step-up Human Gate,
- nowy VPS pojawi się w `register_env` po fizycznym deploymencie (Etap 2 — automation).

Pełen flow:

1. `scaling.recommend_topology` → `topology_recommended` event.
2. `subscription` subskrybuje → liczy ROI dla nowego VPS-a.
3. Jeśli ROI < 30% — `subscription.emit_purchase_recommendation` z `decision: "downgrade_or_skip"`.
4. Jeśli ROI > 150% — `subscription` proponuje upgrade planu.
5. Operator akceptuje przez `mobile_gateway.POST /cards/{id}/actions` (D3+ → `X-Biometric-Verified: true`).
6. Po fizycznym setupcie VPS — `scaling.register_env` zarejestruje go w inventory.

### 10.9. Granica z core layer

Scaling konsumuje wyłącznie:
- `sylion.core.event_bus.{EventBus, SylionEvent, get_event_bus}` — event publishing.
- `sylion.aeis.advisor._db.get_pool` (przez `shared_db`) — connection pool PG.
- `psycopg.rows.dict_row` — dla typed row mapping w `env_inventory.py`.

Brak innych zależności na core / infrastructure. To minimalny moduł — łatwy do auditu, łatwy do mock'owania, łatwy do uruchomienia w izolacji.
