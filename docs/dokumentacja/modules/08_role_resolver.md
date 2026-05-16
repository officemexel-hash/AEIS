# Moduł: sylion.aeis.advisor.role_resolver
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (gRPC RPCs / REST endpoints)](#4-funkcje-grpc-rpcs--rest-endpoints)
5. [Eventy](#5-eventy)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przykład-użycia)
8. [Verification](#8-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Moduł `sylion.aeis.advisor.role_resolver` jest **routerem modeli LLM**: dla każdej roli AEIS (planner / worker / critic / governance / local_verifier) lub każdego *judge purpose* (rationale_generation, alternatives_ranking, risk_assessment, funding_scoring, consortium_matching), w połączeniu z poziomem ryzyka (`low / medium / high / critical`), wybiera konkretny model i providera, którym zostanie obsłużone zadanie. Resolver realizuje pięcioetapową hierarchię decyzyjną: **operator override → blocked providers → cost ceiling → default routing matrix → local fallback**. Zanim AEIS wyśle jakikolwiek prompt do zewnętrznego API, resolver odpowiada na pytanie *"który model, u którego providera, za ile"*.

Moduł jest **stateless i bezdyskowy** — nie posiada własnych tabel ani plików. Czyta preferencje przez `aeis.advisor.preferences` i wycenę modeli przez `aeis.advisor.pricing.catalog`. Z tego powodu jest też najmniejszym modułem warstwy advisor (manifest deklaruje brak schematów PG, brak subskrypcji eventów). Emituje trzy eventy diagnostyczne: każda decyzja routingu, każde zastosowanie operator override oraz każdy fallback do modelu lokalnego (Qwen). Te eventy są używane przez panel **Operator → Audit Trail** do debug i przez billing/subscription do śledzenia rzeczywistego użycia modeli.

## 2. Architektura modułu

### Pliki w module

| Plik | Rola |
|---|---|
| `__init__.py` | Eksport publicznego API (singleton `get_role_resolver_service`). |
| `service.py` | Klasa `RoleResolverService` — fasada nad funkcjami `resolver.py`. Emituje eventy. |
| `resolver.py` | Pure-function logika resolwera. 5-stopniowa hierarchia decyzyjna. |
| `routing_table.py` | Statyczne tabele `DEFAULT_ROUTING_BY_ROLE` i `DEFAULT_ROUTING_BY_PURPOSE` + listy `RISK_LEVELS, ROLES, PURPOSES`. |
| `role_routing_defaults.yaml` | Operator-editable wersja YAML domyślnych tabel (referencja, runtime używa stałych z `routing_table.py`). |
| `_models.py` | Dataclassy: `ModelChoice`, `Role`, `RoutingEntry`, `RoutingPreview`. |
| `grpc_server.py` | Stub gRPC servicer (czeka na proto codegen). Metody: `ResolveRole`, `ResolveJudgeModel`, `ListAvailableRoles`, `GetRoutingMatrix`, `PreviewRouting`. |
| `README.md` | Operator guide po polsku — interakcja, troubleshooting, eventy. |

### Dependencies

**Wewnętrzne:**

- `sylion.aeis.advisor.preferences` — pobranie `blocked_providers`, `cost_ceilings`, `llm_judge_routing_override`.
- `sylion.aeis.advisor.pricing.catalog` — sprawdzenie istnienia modelu i `list_models()`.
- `sylion.aeis.advisor.pricing.estimator` — `estimate_cost(model, input_tokens, output_tokens)` dla cost ceiling check.
- `sylion.core.event_bus` — emisja eventów.

**Zewnętrzne:**

- Standard library: `logging`, `time`, `uuid`, `pathlib.Path`.
- (planowane) `pyyaml` dla load `role_routing_defaults.yaml`.

### Storage

Brak. Manifest deklaruje `"postgres_schemas": []`. Resolver jest stateless i opiera się wyłącznie na (a) statycznej tabeli routingu, (b) preferencjach operatora (te są w `aeis.advisor.preferences` schema), (c) katalogu cenowym (w `aeis.advisor.pricing` schema).

### Workers / threads / async loops

Brak. Resolver to czyste funkcje — każde wywołanie kończy się w O(1) (lookup w słowniku) plus zapytania do preferences/pricing.

## 3. Konfiguracja

### Environment variables

Resolver nie czyta żadnych zmiennych środowiskowych bezpośrednio. Wszystkie ustawienia pochodzą z preferencji operatora.

### Preferencje operatora (przez `aeis.advisor.preferences`)

| Klucz | Typ | Domyślna | Znaczenie |
|---|---|---|---|
| `blocked_providers` | list[str] | `[]` | Lista zablokowanych providerów (`anthropic`, `openai`, `google`, `local`). Modele danego providera są pomijane. |
| `cost_ceilings` | dict[str, float] | `{low: 25, medium: 25, high: 150, critical: 200}` (przykładowe) | Limit kosztu USD per zapytanie 2k+1k tokens, per poziom ryzyka. Modele droższe są odrzucane. Internal default w kodzie: `6.0` USD jeśli klucz nie istnieje. |
| `llm_judge_routing_override` | dict[str, str] | `{}` | Operator wymusza model. Klucze: `"<purpose>:<risk>"` (np. `"funding_scoring:critical"`) lub samo `"<purpose>"`. Wartość: `model_id`. Override ma najwyższy priorytet. |

### Plik `role_routing_defaults.yaml`

```yaml
# Default role routing configuration.
# Operator-editable defaults. Loaded by routing_table.py as reference.
# For runtime resolution, use routing_table.DEFAULT_ROUTING_BY_ROLE and
# routing_table.DEFAULT_ROUTING_BY_PURPOSE.

roles:
  planner:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  worker:
    low: qwen2.5:72b-instruct
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7
  critic:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  governance:
    low: claude-sonnet-4-6
    medium: claude-opus-4-7
    high: claude-opus-4-7
    critical: claude-opus-4-7
  local_verifier:
    low: qwen2.5:7b-instruct
    medium: qwen2.5:72b-instruct
    high: qwen2.5:72b-instruct
    critical: qwen2.5:72b-instruct

purposes:
  rationale_generation:
    low: qwen2.5:7b-instruct
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7
  alternatives_ranking:
    low: qwen2.5:72b-instruct
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  risk_assessment:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  funding_scoring:
    low: gemini-2.5-pro
    medium: gemini-2.5-pro
    high:
      - claude-opus-4-7
      - gemini-2.5-pro
    critical:
      - claude-opus-4-7
      - gpt-5
  consortium_matching:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
```

### Defaults — domyślna tabela routingu (per role)

| Rola | low | medium | high | critical |
|---|---|---|---|---|
| `planner` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `worker` | qwen2.5:72b-instruct | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `critic` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `governance` | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 | claude-opus-4-7 |
| `local_verifier` | qwen2.5:7b-instruct | qwen2.5:72b-instruct | qwen2.5:72b-instruct | qwen2.5:72b-instruct |

### Defaults — domyślna tabela routingu (per purpose)

| Purpose | low | medium | high | critical |
|---|---|---|---|---|
| `rationale_generation` | qwen2.5:7b-instruct | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 |
| `alternatives_ranking` | qwen2.5:72b-instruct | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `risk_assessment` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |
| `funding_scoring` | gemini-2.5-pro | gemini-2.5-pro | [claude-opus-4-7, gemini-2.5-pro] | [claude-opus-4-7, gpt-5] |
| `consortium_matching` | claude-sonnet-4-6 | claude-sonnet-4-6 | claude-opus-4-7 | claude-opus-4-7 |

> Ensemble (lista zamiast pojedynczego modelu) działa w trybie *first-available-wins*: resolver iteruje po kandydatach, bierze pierwszego, który jest dostępny i mieści się w cost ceiling. Jeśli wszystkie odrzucone — schodzi do generic fallback i lokalnego.

### Provider mapping

Resolver mapuje prefix model_id na provider:

| Prefix | Provider |
|---|---|
| `claude*` | `anthropic` |
| `gpt*` | `openai` |
| `gemini*` | `google` |
| `qwen*` | `local` |
| (inne) | `unknown` |

## 4. Funkcje (gRPC RPCs / REST endpoints)

W Etap 1 moduł wystawia `RoleResolverService` z poniższymi metodami. Stub gRPC w `grpc_server.py` ma placeholder *Servicer* gotowy do podpięcia po wygenerowaniu proto.

### 4.1 `resolve_role(operator_id, role, risk_level, project_domain="", project_type="") -> ModelChoice`

- **Sygnatura proto-style:** `rpc ResolveRole(ResolveRoleRequest) returns (ModelChoice)`.
- **Input:**
  - `operator_id` (str) — ID operatora.
  - `role` (str) — jedna z `ROLES = [planner, worker, critic, governance, local_verifier]`.
  - `risk_level` (str) — `low | medium | high | critical`.
  - `project_domain, project_type` (str, opt) — kontekst preferencji project-scoped.
- **Output:** `ModelChoice` (`model_id`, `reason`, `is_local_fallback`, `confidence`, `estimated_cost_usd`).
- **Side effects:** emituje jeden z eventów (zob. §5) zależnie od `reason`.
- **Errors:**
  - `RuntimeError("No available model for role {role}/{risk_level}")` — gdy wszystkie modele odrzucone (zewn. zablokowani + lokalni offline).

### 4.2 `resolve_judge(operator_id, judge_purpose, risk_level) -> ModelChoice`

- **Sygnatura:** `rpc ResolveJudgeModel(ResolveJudgeRequest) returns (ModelChoice)`.
- **Input:**
  - `judge_purpose` (str) — jedna z `PURPOSES = [rationale_generation, alternatives_ranking, risk_assessment, funding_scoring, consortium_matching]`.
  - `risk_level` (str).
- **Output / Errors / Side effects** — analogicznie do `resolve_role`.

### 4.3 `list_available_roles() -> list[Role]`

- **Sygnatura:** `rpc ListAvailableRoles(Empty) returns (RolesResponse)`.
- Zwraca listę 5 ról z `display_name = role.replace("_", " ").title()`.

### 4.4 `get_routing_matrix() -> list[RoutingEntry]`

- **Sygnatura:** `rpc GetRoutingMatrix(Empty) returns (RoutingMatrixResponse)`.
- Zwraca pełen flat dump tabel: 5 ról × 4 risk + 5 purposes × 4 risk = 40 entries.
- `RoutingEntry`: `{purpose_or_role, risk_level, model_id, description}`.

### 4.5 `preview_routing(operator_id, scenario) -> RoutingPreview`

- **Sygnatura:** `rpc PreviewRouting(PreviewRequest) returns (RoutingPreview)`.
- **Input:** `scenario` (str) — wolny tekst, np. "planner critical task" lub "funding_scoring high".
- **Logika:** heurystyczny parse scenariusza (lookup ról i risk levels w stringu).
- **Output:** `{operator_id, scenario, resolved: ModelChoice, alternatives: list[ModelChoice]}`. Alternatives zawierają do 3 innych modeli z katalogu cenowego.

### Hierarchia decyzyjna (resolver.py)

Dla `resolve_judge_model`:

1. **Operator override:** sprawdź `preferences.llm_judge_routing_override["{purpose}:{risk}"]` lub `["{purpose}"]`. Jeśli model dostępny → zwróć z `reason="operator_override"`.
2. **Default routing:** wybierz `DEFAULT_ROUTING_BY_PURPOSE[purpose][risk]`.
   - Jeśli to lista (ensemble): iteruj, weź pierwszego dostępnego ORAZ mieszczącego się w ceiling. `reason="default_ensemble_pick"`.
   - Jeśli string: sprawdź dostępność i ceiling. `reason="default_routing"`.
3. **Generic fallback:** iteruj po `pricing.catalog.list_models()`, weź pierwszy dostępny w ceiling. `reason="generic_fallback"`.
4. **Local fallback:** iteruj po `["qwen2.5:72b-instruct", "qwen2.5:7b-instruct"]`. `reason="local_fallback"`, `is_local_fallback=True`.
5. **Wyjątek:** `RuntimeError("No available model for ...")`.

Dla `resolve_role_model`: analogicznie, ale tylko kroki 2 (default), 4 (local), 5 (raise). Brak operator override per role w obecnej wersji.

### Cost ceiling check

```python
ceilings = preferences.get_effective("cost_ceilings").value or {}
ceiling = float(ceilings.get(risk_level, 6.0))   # 6.0 USD = internal default
est = estimate_cost(model_id, input_tokens=2000, output_tokens=1000)
return est.total_cost_usd <= ceiling
```

### 4.6. gRPC Servicer — `RoleResolverServicer` (sprint3)

Plik: `sylion/aeis/advisor/role_resolver/grpc_server.py`. Bezpośredni wrapper na `RoleResolverService` — bezstanowy, bezdyskowy.

| RPC | Opis |
|-----|------|
| `ResolveRole(ResolveRoleRequest{operator_id, role, risk_level, project_domain, project_type})` | Zwraca `ModelChoice` z wybranym modelem i powodem. |
| `ResolveJudgeModel(ResolveJudgeRequest{operator_id, judge_purpose, risk_level})` | Zwraca `ModelChoice` dla judge. |
| `ListAvailableRoles(Empty)` | Zwraca `ListAvailableRolesResponse{roles[]}`. |
| `GetRoutingMatrix(Empty)` | Zwraca `GetRoutingMatrixResponse{entries[]}`. |

Rejestracja: `register_role_resolver_service(server, service=None) -> bool`.

### 4.7 Walidacja dostepnosci modelu — `_validators.py` [sprint4, commit 782b58c9]

Plik: `sylion/aeis/advisor/role_resolver/_validators.py`. Dodany w sprint4 jako warstwa weryfikacji, wywolywana przez `service.py` przed faktycznym routingiem.

**Wyjątek:**

```python
class ModelNotAvailableError(Exception):
    def __init__(self, model_id: str, reason: str): ...
    # model_id: str
    # reason: str  (komunikat po polsku)
```

**Funkcja glowna:**

```python
def check_model_available(operator_id: str, model_id: str) -> tuple[bool, str | None]:
    """Zwraca (True, None) jezeli model dostepny lub (False, reason_po_polsku)."""
```

**Logika walidacji (kolejnosc):**

1. Pusty `model_id` → `(False, "Brak wybranego modelu")`
2. Lokalny model Ollama (`_is_local_ollama_model`) → sprawdza `ollama list` przez `subprocess`. Jesli nie zainstalowany → `(False, "Model lokalny '{name}' nie jest zainstalowany (uruchom: ollama pull {name})")`.
3. Zewnetrzny model nieznany (nie w `PROVIDER_OF_MODEL`) → `(False, "Nieznany model '{name}' - brak w katalogu")`.
4. Pokryty subskrypcja (`_subscription_covers_model`) → `(True, None)`.
5. Klucz API providera dostepny w env (`_resolve_provider_key`) → `(True, None)`.
6. Brak klucza → `(False, "Brak klucza API dla providera {provider}. Ustaw zmienną środowiskową {ENV_KEY} lub dodaj klucz w kroku 2 wizarda.")`.

Mapa dostawcow i zmiennych srodowiskowych (`ENV_KEY_BY_PROVIDER`):

| Provider | Zmienna |
|----------|---------|
| anthropic | `ANTHROPIC_API_KEY` |
| openai | `OPENAI_API_KEY` |
| google | `GOOGLE_API_KEY` |
| perplexity | `PERPLEXITY_API_KEY` |
| zai | `ZAI_API_KEY` |
| xai | `XAI_API_KEY` |
| moonshot | `MOONSHOT_API_KEY` |

Lokalne modele Ollama (prefix-based detection w `LOCAL_MODEL_PREFIXES`):
`qwen2.5`, `qwen3`, `qwen3.5`, `llama3`, `llama3.1`, `llama3.2`, `llama3.3`, `mistral`, `gemma2`, `phi3`, `codellama`, `deepseek-coder`.

**Integracja z `service.py`:** `ensure_model_available(operator_id, model_id)` jest wywolywane przed zwroceniem `ModelChoice`. Jesli walidacja nie przejdzie — serwis rzuca `ModelNotAvailableError` z polskojezycznym komunikatem zamiast cicho zwracac niedostepny model.

---

### 4.8 Priority Routing: Subscription → PAYG → Budget Cap [sprint4, commit d6eb4d15]

Sprint4 przebudowal hierarchie decyzyjna resolwera o krok "subscription pool" jako priorytet numer 3 (po override i blocked-check, przed PAYG ceiling check).

#### Pelna hierarchia (6 krokow)

| Krok | Nazwa | Opis |
|------|-------|------|
| 1 | Operator override | `llm_judge_routing_override[purpose:risk]` — najwyzszy priorytet |
| 2 | Blocked providers | Kandydaci z zablokowanych providerow pomijani |
| 3 | **Subscription pool** | Modele pokryte aktywna subskrypcja z `has_quota=True` → koszt $0, `used_subscription=True` |
| 4 | PAYG ceiling check | `pricing.effective_cost_estimate()` → porownanie z `cost_ceilings[risk_level]` |
| 5 | Default routing matrix | Tabele `DEFAULT_ROUTING_BY_ROLE` / `DEFAULT_ROUTING_BY_PURPOSE` |
| 6 | Local fallback | `qwen2.5:72b-instruct` → `qwen2.5:7b-instruct` |

#### Subscription pool — logika (resolver.py)

```python
from sylion.aeis.advisor.subscription.quota_tracker import get_quota_status

# Krok 3: z listy kandydatow wybierz tych z aktywna kwota
subscription_pool: list[tuple[str, int]] = []
for model_id in available_candidates:
    quota = get_quota_status(operator_id, model_id)
    if quota and quota.has_quota:
        subscription_pool.append((model_id, quota.remaining_tokens))

if subscription_pool:
    subscription_pool.sort(key=lambda item: item[1], reverse=True)  # max remaining first
    chosen = subscription_pool[0][0]
    return ModelChoice(
        model_id=chosen,
        reason=f"{preferred_reason}_subscription",
        estimated_cost_usd=0.0,
        used_subscription=True,
        suggested_alternative=subscription_pool[1][0] if len(subscription_pool) > 1 else None,
    )
```

Jesli `subscription_pool` jest pusty (brak aktywnych subskrypcji lub wszystkie kwoty wyczerpane) → routing kontynuuje do kroku 4 (PAYG).

#### Rozszerzone pole `ModelChoice.used_subscription`

`ModelChoice` (z `role_resolver/_models.py`) uzyskal w sprint4 trzy nowe pola:

| Pole | Typ | Opis |
|------|-----|------|
| `used_subscription` | `bool = False` | True jesli model wybrany z subscription pool |
| `budget_exceeded` | `bool = False` | True jesli PAYG koszt > ceiling (model odrzucony) |
| `suggested_alternative` | `str | None = None` | Alternatywny model z tego samego subscription pool lub None |

Pole `suggested_alternative` jest uzyteczne gdy operator dostaje `budget_exceeded=True` — pozwala UI pokazac "Sprobuj {alternative}, ktory jest objety Twoja subskrypcja".

#### Identyfikacja powodu routingu (pole `reason`)

| `reason` (przyrostek) | Znaczenie |
|----------------------|-----------|
| `_subscription` | Model wybrany z subscription pool (krok 3) |
| `_payg` | Model wybrany przez PAYG ceiling check (krok 4) |
| `operator_override` | Override operatora (krok 1) |
| `local_fallback` | Lokalny Qwen jako fallback (krok 6) |

#### Testowanie

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/subscription/test_quota_tracker.py -v
# 5 testow: get_quota_status_no_subscription, get_quota_status_with_quota,
#           consume_quota_increments_usage, billing_period_reset_day,
#           billing_period_end_of_month
```

---

## 5. Eventy

### Emitted

| Topic | Kiedy | Payload |
|---|---|---|
| `aeis.advisor.role_resolver.routing_decision` | Każda decyzja oprócz override i fallback (czyli `default_routing`, `default_ensemble_pick`, `generic_fallback`, `default_role_routing`, `default_role_ensemble`) | `operator_id, role/judge_purpose, risk_level, project_domain, project_type, resolved_model, reason, is_local_fallback` |
| `aeis.advisor.role_resolver.override_applied` | Gdy `reason == "operator_override"` | analogicznie + `override_key` |
| `aeis.advisor.role_resolver.fallback_to_local` | Gdy `is_local_fallback == True` | analogicznie |

### Subscribed

Brak. Manifest deklaruje `"events_subscribe": []`.

## 6. Database tables

Brak. Resolver jest stateless. Wszystkie dane konfiguracyjne pochodzą z preferencji operatora (`aeis.advisor.preferences` schema) lub z katalogu cenowego (`aeis.advisor.pricing` schema).

## 7. Przykład użycia

### 7.1 Resolve role w kodzie Python

```python
from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service

svc = get_role_resolver_service()

# Planner dla zadania krytycznego
choice = svc.resolve_role(
    operator_id="op-1",
    role="planner",
    risk_level="critical",
    project_domain="fintech",
    project_type="masterplan",
)
print(choice.model_id, choice.reason)
# -> "claude-opus-4-7", "default_role_routing"
```

### 7.2 Resolve judge purpose

```python
choice = svc.resolve_judge(
    operator_id="op-1",
    judge_purpose="funding_scoring",
    risk_level="critical",
)
# Critical funding_scoring jest ensemble [claude-opus-4-7, gpt-5].
# Resolver iteruje, bierze pierwszy dostępny + w ceiling.
print(choice.model_id, choice.reason)
# -> "claude-opus-4-7", "default_ensemble_pick"
```

### 7.3 Operator override (wymuszenie modelu)

```python
from sylion.aeis.advisor.preferences import get_preferences

# Operator wymusza GPT-5 dla funding_scoring/critical
get_preferences().set_preference(
    user_id="op-1",
    project_type=None,
    project_domain=None,
    preference_key="llm_judge_routing_override",
    value={"funding_scoring:critical": "gpt-5"},
    source="operator",
)

choice = svc.resolve_judge("op-1", "funding_scoring", "critical")
print(choice.model_id, choice.reason)
# -> "gpt-5", "operator_override"
```

### 7.4 Cost ceiling block + fallback

```python
# Operator ustawia limit $1 dla critical
get_preferences().set_preference(
    user_id="op-1",
    project_type=None,
    project_domain=None,
    preference_key="cost_ceilings",
    value={"critical": 1.0},
    source="operator",
)

choice = svc.resolve_judge("op-1", "funding_scoring", "critical")
# Wszystkie zewnętrzne odrzucone → fallback do Qwen 72B.
print(choice.model_id, choice.is_local_fallback, choice.reason)
# -> "qwen2.5:72b-instruct", True, "local_fallback"
```

### 7.5 Routing matrix + preview

```python
matrix = svc.get_routing_matrix()
print(f"Total entries: {len(matrix)}")  # 40
for entry in matrix[:5]:
    print(entry.to_dict())

preview = svc.preview_routing(
    operator_id="op-1",
    scenario="planner critical task for fintech masterplan",
)
print("Resolved:", preview.resolved.model_id)
print("Alternatives:", [a.model_id for a in preview.alternatives])
```

### 7.6 curl / TypeScript REST (Etap 2 — przyszłość)

```bash
curl -X POST http://127.0.0.1:8010/advisor/role_resolver/resolve_role \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "operator_id": "op-1",
    "role": "planner",
    "risk_level": "critical"
  }'
```

```typescript
const choice = await fetch("/api/advisor/role_resolver/resolve_role", {
  method: "POST",
  headers: { Authorization: `Bearer ${jwt}`, "Content-Type": "application/json" },
  body: JSON.stringify({ operator_id: "op-1", role: "planner", risk_level: "high" }),
}).then(r => r.json());
console.log(choice.model_id, choice.reason);
```

## 8. Verification

### 8.1 Pytest

```bash
cd src/sylion-pipeline
pytest tests/aeis/advisor/role_resolver/ -v
```

Kluczowe scenariusze testowe:

- `test_resolve_role_default_routing` — zwraca model z tabeli.
- `test_blocked_provider_skipped` — anthropic w blocked → claude pomijany.
- `test_cost_ceiling_blocks_expensive` — opus odrzucony przy niskim limicie.
- `test_override_wins` — `llm_judge_routing_override` ma najwyższy priorytet.
- `test_local_fallback_when_all_external_blocked` — qwen jako ostateczność.
- `test_ensemble_picks_first_available` — lista [claude-opus, gpt-5] → pierwszy dostępny.

### 8.2 Smoke test

```python
python -c "
from sylion.aeis.advisor.role_resolver.service import get_role_resolver_service
svc = get_role_resolver_service()
print(svc.list_available_roles())
print(len(svc.get_routing_matrix()))
"
```

Output: 5 ról + `40` entries.

### 8.3 Event subscription test

```python
from sylion.core.event_bus import get_event_bus

events = []
get_event_bus().subscribe("aeis.advisor.role_resolver.*", lambda e: events.append(e))

svc.resolve_role("op-1", "planner", "high")
assert any(e.topic == "aeis.advisor.role_resolver.routing_decision" for e in events)
```

### 8.4 Manualna inspekcja routing matrix

```python
from sylion.aeis.advisor.role_resolver.routing_table import (
    DEFAULT_ROUTING_BY_ROLE, DEFAULT_ROUTING_BY_PURPOSE,
)
import json
print(json.dumps(DEFAULT_ROUTING_BY_ROLE, indent=2))
print(json.dumps(DEFAULT_ROUTING_BY_PURPOSE, indent=2))
```

## 9. Troubleshooting

| Problem | Diagnoza | Fix |
|---|---|---|
| AEIS ciągle wybiera lokalny Qwen zamiast zewnętrznego | Wszyscy zewnętrzni providerzy zablokowani lub cost ceiling za niski. | Wejdź w **Preferencje → Bezpieczeństwo → Blokowani providerzy**, usuń `anthropic/openai/google`. Sprawdź `cost_ceilings` w **Preferencje → Budżet** — podnieś dla `high/critical`. |
| Override nie działa, model się nie zmienia | Wybrany model jest zablokowany lub nie istnieje w pricing.catalog. | (a) Sprawdź `blocked_providers`. (b) Sprawdź czy `pricing.catalog.get_model(model_id) is not None`. (c) Klucz override musi być dokładny: `"planner:critical"` lub `"planner"`. |
| `RuntimeError: No available model for X/Y` | Wszystkie modele (włącznie z lokalnymi) wykluczone. | Sprawdź event `fallback_to_local`. Tymczasowo usuń wszystkich blocked_providers lub ustaw ceiling=0 (brak limitu). Upewnij się że Ollama/Qwen jest uruchomiony. |
| Drogi opus na każdym critical task | Brak `cost_ceilings` lub za wysoki. | Ustaw realistyczne wartości w **Preferencje → Budżet**: `critical=$100` zamiast $200. |
| Ensemble [opus, gpt-5] zawsze wybiera opus | First-available-wins logic. opus dostępny → koniec. | To jest by design. Aby wymusić gpt-5 — ustaw `llm_judge_routing_override["funding_scoring:critical"] = "gpt-5"`. |
| Reason = `"generic_fallback"` zamiast `"default_routing"` | Default model dla danej (purpose, risk) niedostępny → resolver szuka dowolnego. | Sprawdź czy default model nie jest blocked albo nie ma w pricing catalog. |
| Estimated_cost_usd zawsze 0 | `ModelChoice.estimated_cost_usd` w obecnej implementacji nie jest wypełniany w resolverze. | To znany limit MVP — wycenę robi się oddzielnym `pricing.estimator.estimate_cost(...)`. |
| Lokalny Qwen wybierany dla low risk planner mimo `claude-sonnet-4-6` w tabeli | Provider `anthropic` zablokowany. | Sprawdź `blocked_providers`; usuń jeśli błędne. |
| Routing matrix puste / `list_available_roles()` zwraca `[]` | Singleton resolvera nie został utworzony lub `routing_table.py` nie zaimportowane. | Wywołaj `get_role_resolver_service()` przed użyciem. Sprawdź importy. |
| Eventy nie pojawiają się w audit trail | EventBus singleton nie jest podpięty. | Wywołaj `get_event_bus()` najpierw lub przekaż explicit `event_bus=` przy konstruowaniu serwisu. |

## 10. Cross-references

### Powiązane moduły

- **`sylion.aeis.advisor.preferences`** — źródło `blocked_providers`, `cost_ceilings`, `llm_judge_routing_override`. Każda zmiana preferencji wpływa na resolver natychmiast (brak cache).
- **`sylion.aeis.advisor.pricing`** — `pricing.catalog.get_model(model_id)` weryfikuje czy model jest znany; `pricing.estimator.estimate_cost(model, input, output)` używany w cost ceiling check.
- **`sylion.aeis.advisor.subscription`** — trackuje rzeczywiste koszty z modeli, które resolver wybierze. Jeśli resolver wybiera tańsze modele, subscription pokazuje niższy ROI dla planu Pro.
- **`sylion.aeis.advisor.variants`** — wariant `aggressive` używa critic_model `claude-opus-4-7`. Resolver może go zablokować, jeśli operator zablokował anthropic.
- **`sylion.aeis.advisor.engine`** — engine wywołuje resolver przy każdej generacji rekomendacji aby wybrać model dla planner/critic.
- **`sylion.aeis.advisor.scaling`** — decyzja o VPS wpływa na dostępność lokalnych modeli (qwen). Jeśli VPS odpada, resolver może mieć problem z fallback.
- **`sylion.aeis.advisor.funding`** — `purpose=funding_scoring` używa specjalnego ensemble (gemini/claude/gpt-5).

### Architecture refs

- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — D-ladder i mapping risk_level ↔ D-level.
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — pełna taksonomia eventów.
- `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/README.md` — operator-friendly guide po polsku.
- `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/role_routing_defaults.yaml` — kanoniczna referencja YAML.

### Wewnątrz dokumentacji

- [`docs/dokumentacja/01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — wysokopoziomowa rola resolwera w warstwie advisor.
- [`docs/dokumentacja/modules/04_preferences.md`](./04_preferences.md) — preferencje, które zasilają resolver.
- [`docs/dokumentacja/modules/06_pricing.md`](./06_pricing.md) — pricing catalog i estimator.
- [`docs/dokumentacja/modules/09_variants.md`](./09_variants.md) — wariantowanie projektów oparte na decyzjach resolwera.
- [`docs/dokumentacja/modules/10_subscription.md`](./10_subscription.md) — subscription śledzi koszty modeli wybranych przez resolwer.
