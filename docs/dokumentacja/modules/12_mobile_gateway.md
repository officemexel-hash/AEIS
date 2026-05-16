# Moduł `sylion.aeis.advisor.mobile_gateway` — REST gateway dla aplikacji mobilnej
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> **Status**: Etap 1, lifecycle `draft`, contract `1.0.0`
> **Owner plan**: `advisor_layer_etap1`
> **Lokalizacja kodu**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/`
> **Manifest**: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.mobile_gateway.json`

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje REST → gRPC](#4-funkcje-rest--grpc)
5. [Eventy emitowane](#5-eventy-emitowane)
6. [Database tables](#6-database-tables)
7. [Przykład użycia](#7-przykład-użycia)
8. [Verification — checklist akceptacyjny](#8-verification--checklist-akceptacyjny)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

Załącznik: pełen `openapi.yaml` (sekcja [4.x](#48-pełen-openapi-spec)).

---

## 1. Cel modułu

`sylion.aeis.advisor.mobile_gateway` to **stateless REST gateway** dla aplikacji mobilnej AEIS Advisor (Etap 2 — Kotlin Multiplatform). Eksponuje powierzchnię HTTP `/mobile/v1/*`, która tłumaczy zapytania klienta mobilnego na **wewnętrzne wywołania gRPC / Python** do innych modułów Advisora (engine, actions, preferences, funding).

### 1.1. Problem biznesowy

Operator SYLION chce zaakceptować rekomendacje AEIS „w locie" — z telefonu, podczas spotkania, z wagonu pociągu. Aplikacja mobilna potrzebuje:

- **Niskiego latency** — REST zamiast gRPC (mobile/HTTP-1.1 lepiej tunneluje przez proxy/firewalle).
- **Offline-first** — `/sync/snapshot` zwraca cache 50 ostatnich kart, projektów, deadline'ów funding, preferencji.
- **Step-up auth** — działania z D-level >= D3 wymagają biometric prompt na urządzeniu (Face ID / Touch ID).
- **Device pairing** — JWT bearer tokens wiązane z konkretnym `device_id`, wystawione przez `sylion.security.auth` (Etap 2).
- **Stabilnego kontraktu** — OpenAPI 3.0.3 spec gwarantuje, że Kotlin generator KMP nie złamie się przy zmianach backendu.

Mobile gateway agreguje te wymagania w **jeden moduł** — zamiast każdy backend Advisora wystawiał własny REST adapter, gateway robi to centralnie.

### 1.2. Rola w architekturze Advisor

Mobile gateway jest **modułem facade'owym** — nie zawiera logiki biznesowej, tłumaczy tylko zapytania REST na wywołania innych modułów:

| REST endpoint | Backend module | Operacja |
|---|---|---|
| `GET /cards` | `engine.service.list_recommendations` | listowanie kart |
| `GET /cards/{id}` | `engine.service.get_recommendation` | pobranie pojedynczej karty |
| `POST /cards/{id}/actions` | `actions` (Etap 2) | submit akcji operatora |
| `GET /projects/{id}/lifecycle` | `mobile_gateway.translator` (skeleton lokalny) | 16-fazowy szkielet |
| `GET /human_gate/pending` | `human_gate` (Etap 2) | tickety do decyzji |
| `POST /human_gate/{id}/decide` | `human_gate.decide` (Etap 2) | decyzja H-G |
| `GET /funding/deadlines` | `funding` (Etap 2) | nadchodzące terminy |
| `GET /preferences[/{key}]` | `preferences` (Etap 2) | snapshot / pojedyncza wartość |
| `PUT /preferences/{key}` | `preferences.mutate` (Etap 2) | mutacja preferencji |
| `GET /sync/snapshot` | wszystkie powyższe | offline cache |

> **Etap 1 vs Etap 2**: W Etapie 1 część endpointów zwraca puste dane (`/projects` → `[]`, `/funding/deadlines` → `[]`, `/human_gate/pending` → `[]`) lub HTTP 501 (`/preferences/{key} PUT`, `/human_gate/{id}/decide POST`). To celowe — kontrakt OpenAPI jest kompletny, implementacja dochodzi modułami w Etapie 2.

### 1.3. Granice odpowiedzialności (czego moduł NIE robi)

- **Nie utrzymuje stanu** — zero tabel PG, brak cache w pamięci, brak sesji. Każde wywołanie jest niezależne.
- **Nie weryfikuje sygnatur JWT** w Etapie 1 — `decode_token_unverified` to stub. W Etapie 2 wskoczy `sylion.security.auth` z pełną walidacją RS256.
- **Nie zarządza pairingiem** w Etapie 1 — eventy `device_paired` / `device_unpaired` są zadeklarowane w manifeście, ale nie ma jeszcze flow rejestracji urządzenia.
- **Nie zna szczegółów modeli** — pole `card.body` jest `additionalProperties: true` (czyli `dict`), nie strukturalnym proto. Etap 2 zastąpi to canonical proto.
- **Nie buforuje** — każde `/sync/snapshot` to świeże call do `engine.list_recommendations`.

### 1.4. Kontrakt z aplikacją mobilną

OpenAPI 3.0.3 spec (`openapi.yaml`) jest **single source of truth**. Klient KMP generuje stuby z tego pliku. Moduł Pythona w `_models.py` jest tylko ręcznie utrzymywaną repliką — w Etapie 2 zostanie zastąpiony auto-genem z proto.

### 1.5. Bezpieczeństwo — model autentykacji

| Warstwa | Etap 1 | Etap 2 |
|---|---|---|
| **JWT verify** | `decode_token_unverified` (decode bez signature check) | `sylion.security.auth.verify_token` (RS256) |
| **Device binding** | `device_id` w claims (sub-claim `did`) | wymagany `device_pubkey_fingerprint` |
| **Biometric step-up** | header `X-Biometric-Verified: true/false` | header + signed nonce z urządzenia |
| **Rate limiting** | brak | per-`operator_id` + per-`device_id` |
| **TLS** | wymagane przez deployment (proxy) | wymagane + cert pinning |

Etap 1 jest **dev-only** — żaden token nie jest weryfikowany kryptograficznie. Wymaga to osłony za odwrotnym proxy z mTLS lub VPN-em do czasu Etapu 2.

---

## 2. Architektura

### 2.1. Pliki w module

```
sylion/aeis/advisor/mobile_gateway/
├── __init__.py
├── api.py            # FastAPI APIRouter — 11 endpointów
├── auth.py           # JWT decode stub + biometric step-up logic
├── _models.py        # Pydantic request/response models
├── openapi.yaml      # OpenAPI 3.0.3 spec (single source of truth)
└── translator.py     # REST → in-process call layer
```

### 2.2. Diagram zależności wewnętrznych

```
                    ┌──────────────────────────────┐
                    │  build_mobile_router()       │
                    │   (api.py:52, singleton)     │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────────┐
              ▼                    ▼                        ▼
       ┌─────────────┐      ┌─────────────┐         ┌──────────────┐
       │  authenticate│     │  translator │         │  EventBus    │
       │  (auth.py)   │     │ (translator │         │  (best-effort│
       │  - JWT decode│     │   .py)      │         │   try/except)│
       │  - biometric │     │  - call     │         └──────────────┘
       │    parser    │     │    engine   │
       └──────┬───────┘     │  - 16 hooks │
              │             │  - snapshot │
              ▼             └──────┬──────┘
       ┌──────────────┐            │
       │MobilePrincipal│           ▼
       │  - operator_id│    ┌────────────────────┐
       │  - device_id  │    │ engine.service     │
       │  - biometric_ │    │  (in-process Etap1)│
       │    verified   │    │  → gRPC (Etap 2)   │
       └───────────────┘    └────────────────────┘
```

### 2.3. Singleton router pattern

```python
_router_lock = threading.Lock()
_router_singleton: Optional[APIRouter] = None

def build_mobile_router() -> APIRouter:
    global _router_singleton
    if _router_singleton is not None:
        return _router_singleton
    with _router_lock:
        if _router_singleton is not None:
            return _router_singleton
        _router_singleton = _build()
    return _router_singleton

def reset_mobile_router() -> None:
    """For tests: drop the cached router so the next build_mobile_router() runs fresh."""
    global _router_singleton
    with _router_lock:
        _router_singleton = None
```

**Double-checked locking** — bezpieczny w Pythonie dzięki GIL przy primitives, lock chroni przed wielokrotnym `_build()` w teście współbieżnym.

### 2.4. Endpoints — pełna lista

11 endpointów pod prefiksem `/mobile/v1`:

| HTTP | Path | Auth | Biometric (D3+) | Status Etap 1 |
|---|---|---|---|---|
| GET | `/cards` | bearer | nie wymagane | implemented |
| GET | `/cards/{card_id}` | bearer | nie wymagane | implemented |
| POST | `/cards/{card_id}/actions` | bearer | wymagane gdy `d_level >= D3` | implemented (intent only) |
| GET | `/projects` | bearer | nie wymagane | stub (zwraca `[]`) |
| GET | `/projects/{project_id}/lifecycle` | bearer | nie wymagane | implemented (16-phase skeleton) |
| GET | `/human_gate/pending` | bearer | nie wymagane | stub (zwraca `[]`) |
| POST | `/human_gate/{ticket_id}/decide` | bearer | wymagane | 501 Not Implemented |
| GET | `/funding/deadlines` | bearer | nie wymagane | stub (zwraca `[]`) |
| GET | `/preferences` | bearer | nie wymagane | stub (zwraca `{}`) |
| GET | `/preferences/{key}` | bearer | nie wymagane | stub (zwraca `null`) |
| PUT | `/preferences/{key}` | bearer | nie wymagane | 501 Not Implemented |
| GET | `/sync/snapshot` | bearer | nie wymagane | implemented |

Razem: **12 ścieżek HTTP** (11 unikalnych + dodatkowe `PUT` na `/preferences/{key}`). W kodzie `api.py` to 12 dekoratorów `@router.<method>`.

### 2.5. JWT decode stub (`auth.py`)

#### 2.5.1. Format tokenu

Bearer token JWT z claims:

```json
{
  "sub": "op_alice",            // operator_id
  "device_id": "dev_iphone_15",  // alternative: "did"
  "iat": 1714123456,
  "exp": 1714209856
}
```

`sub` MUSI być wypełnione (lub `operator_id`), `device_id` (lub `did`) MUSI być wypełnione.

#### 2.5.2. Implementacja `decode_token_unverified`

```python
def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)

def decode_token_unverified(token: str) -> dict:
    if not token:
        raise AuthError("missing bearer token")
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    try:
        body = _b64url_decode(parts[1])
        claims = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise AuthError(f"invalid token payload: {exc}") from exc
    if not isinstance(claims, dict):
        raise AuthError("token payload must be an object")
    return claims
```

**Brak sprawdzenia signature** — tylko split na 3 części, base64-decode payload, parse JSON. To jest **stub Etapu 1**.

#### 2.5.3. Implementacja `extract_bearer`

```python
def extract_bearer(authorization_header: Optional[str]) -> str:
    if not authorization_header:
        raise AuthError("missing Authorization header")
    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("expected 'Bearer <token>' Authorization header")
    return parts[1]
```

Akceptuje: `Bearer <token>`, `bearer <token>`, `BEARER <token>` (case-insensitive na schema, token-as-is).

#### 2.5.4. `MobilePrincipal` dataclass

```python
@dataclass(frozen=True)
class MobilePrincipal:
    operator_id: str
    device_id: str
    biometric_verified: bool = False
    raw_token: str = ""
```

Frozen — niemodyfikowalny po utworzeniu. Przekazywany dalej do handlerów endpointów.

#### 2.5.5. Pełne `authenticate`

```python
def authenticate(
    authorization_header: Optional[str],
    biometric_header: Optional[str] = None,
) -> MobilePrincipal:
    token = extract_bearer(authorization_header)
    claims = decode_token_unverified(token)
    operator_id = str(claims.get("sub") or claims.get("operator_id") or "").strip()
    if not operator_id:
        raise AuthError("token missing operator subject")
    device_id = str(claims.get("device_id") or claims.get("did") or "").strip()
    if not device_id:
        raise AuthError("token missing device_id")
    return MobilePrincipal(
        operator_id=operator_id,
        device_id=device_id,
        biometric_verified=_parse_truthy(biometric_header),
        raw_token=token,
    )
```

Walidacje:
1. `Authorization` header obecny.
2. Tokeny w formacie `Bearer <jwt>`.
3. JWT ma 3 części (header.payload.signature).
4. Payload to base64url-encoded JSON object.
5. Object zawiera `sub` lub `operator_id` (non-empty po `strip()`).
6. Object zawiera `device_id` lub `did` (non-empty po `strip()`).

Brak walidacji: `exp`, `iat`, `aud`, `iss`. To stub.

### 2.6. Biometric step-up (`auth.biometric_required_for_d_level`)

```python
def biometric_required_for_d_level(d_level: str) -> bool:
    if not d_level:
        return False
    normalized = d_level.strip().upper()
    if not normalized.startswith("D"):
        return False
    try:
        ordinal = int(normalized[1:])
    except ValueError:
        return False
    return ordinal >= 3
```

Reguła: **D3 lub wyżej → wymagane**.

Tabela:

| `d_level` (input) | `biometric_required_for_d_level` |
|---|---|
| `"D0"` | `False` |
| `"D1"` | `False` |
| `"D2"` | `False` |
| `"D3"` | `True` |
| `"D4"` | `True` |
| `"D5"` | `True` |
| `""` (puste) | `False` (defensive) |
| `"d3"` (lowercase) | `True` (po `.upper()`) |
| `"X3"` (zły prefix) | `False` |
| `"DX"` (zły ordinal) | `False` |
| `None` | `False` (defensive — uwaga: niektóre wywołania nie obsłużą `None`, sprawdź wyżej) |

### 2.7. Header parsing — `_parse_truthy`

```python
def _parse_truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}
```

Akceptowane jako truthy: `1`, `true`, `yes`, `on` (case-insensitive). Wszystko inne (włącznie z `"0"`, `"false"`, pustym stringiem, `None`) jest false.

### 2.8. Translator — REST do wewnętrznego wywołania (`translator.py`)

#### 2.8.1. 16 lifecycle hooks (kanoniczne)

```python
_LIFECYCLE_HOOKS = (
    "aeis.system.model_setup_requested",
    "aeis.system.api_provider_setup_requested",
    "aeis.system.budget_config_requested",
    "aeis.idea.intake.completed",
    "aeis.idea.sot_model_selection_requested",
    "aeis.council.formation_requested",
    "aeis.system.autonomy_policy_change_requested",
    "aeis.idea.sot_drafted",
    "aeis.masterplan.created",
    "aeis.system.runtime_topology_change_requested",
    "aeis.system.vps_scaling_requested",
    "aeis.system.skill_selection_requested",
    "aeis.production.deploy_requested",
    "aeis.testing.started",
    "aeis.human_gate.ticket_pending",
    "aeis.final_approval.requested",
)
```

Tabela referencyjna z opisami:

| # | Hook | Faza |
|---|---|---|
| 1 | `aeis.system.model_setup_requested` | Setup modeli LLM (provider keys, fallbacki). |
| 2 | `aeis.system.api_provider_setup_requested` | Setup providerów API (Anthropic, OpenAI, Google). |
| 3 | `aeis.system.budget_config_requested` | Konfiguracja budżetu (limit dziennie/miesięcznie). |
| 4 | `aeis.idea.intake.completed` | Idea zakończona w `idea_intake`. |
| 5 | `aeis.idea.sot_model_selection_requested` | Wybór modelu SOT (single source of truth). |
| 6 | `aeis.council.formation_requested` | Formowanie rady modeli (council_hybrid). |
| 7 | `aeis.system.autonomy_policy_change_requested` | Zmiana polityki autonomii (manual / supervised / autopilot). |
| 8 | `aeis.idea.sot_drafted` | SOT wstępnie zarysowany. |
| 9 | `aeis.masterplan.created` | Masterplan utworzony. |
| 10 | `aeis.system.runtime_topology_change_requested` | Zmiana topologii (scaling). |
| 11 | `aeis.system.vps_scaling_requested` | Skalowanie VPS-ów. |
| 12 | `aeis.system.skill_selection_requested` | Wybór skillów. |
| 13 | `aeis.production.deploy_requested` | Wdrożenie produkcyjne. |
| 14 | `aeis.testing.started` | Start testów. |
| 15 | `aeis.human_gate.ticket_pending` | Oczekujący ticket Human Gate. |
| 16 | `aeis.final_approval.requested` | Finalna aprobata. |

#### 2.8.2. Funkcje translatora

```python
def list_recent_cards(operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
    svc = get_engine_service()
    return svc.list_recommendations(operator_id=operator_id, limit=limit)

def get_card(card_id: str) -> Optional[dict[str, Any]]:
    svc = get_engine_service()
    return svc.get_recommendation(card_id=card_id)

def project_lifecycle_skeleton(project_id: str) -> dict[str, Any]:
    phases = [
        {"hook": hook, "phase_index": idx, "status": "pending"}
        for idx, hook in enumerate(_LIFECYCLE_HOOKS, start=1)
    ]
    return {"project_id": project_id, "phases": phases}

def build_offline_snapshot(operator_id: str) -> dict[str, Any]:
    cards = list_recent_cards(operator_id=operator_id, limit=50)
    return {
        "operator_id": operator_id,
        "cards": cards,
        "projects": [],
        "human_gate_pending": [],
        "funding_deadlines": [],
        "settings": {},
        "snapshot_taken_at": time.time(),
    }

def card_d_level(card: dict[str, Any]) -> str:
    header = card.get("header") or {}
    return str(header.get("d_level") or "D0")
```

`card_d_level` defensive — jeśli `card.header` jest `None` lub brak — zwraca `"D0"` (czyli najniższy → biometric NIE wymagany — fail-open w testach, ale w produkcji `engine` zawsze wypełnia D-level).

### 2.9. Event emission helpers

```python
def _publish(topic: str, payload: dict[str, Any]) -> None:
    """Best-effort emit on the shared event backbone; never raise."""
    try:
        from sylion.core.event_backbone import get_event_backbone

        event = SylionEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            source_module=_SOURCE_MODULE,
            timestamp=time.time(),
        )
        get_event_backbone().publish(event)
    except Exception:
        log.warning("mobile_gateway: event emission failed for %s", topic, exc_info=True)
```

**Try/except — bus failure NIE łamie request path**. To celowe: gateway musi działać nawet jeśli event backbone jest zdrowy lokalnie, ale ma chwilowy outage.

### 2.10. Auth wrapper (`_authenticate`)

```python
def _authenticate(
    request: Request,
    authorization: Optional[str],
    biometric_header: Optional[str],
) -> MobilePrincipal:
    try:
        return authenticate(authorization, biometric_header)
    except AuthError as exc:
        _emit_auth_failure(request.url.path, str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc
```

Każda failure emit-uje event `auth_failure` zanim podniesie 401. To kluczowe dla audytu (security ops widzi próby brute-force).

### 2.11. Manifest contract

```json
{
  "module_id": "sylion.aeis.advisor.mobile_gateway",
  "module_kind": "ADVISOR",
  "owner_plan": "advisor_layer_etap1",
  "implementation_strategy": "greenfield",
  "contract_version": "1.0.0",
  "depends_on": [
    "sylion.aeis.advisor.engine",
    "sylion.aeis.advisor.actions",
    "sylion.aeis.advisor.preferences",
    "sylion.aeis.advisor.funding"
  ],
  "lifecycle_stage": "draft",
  "events_emit": [
    "aeis.advisor.mobile_gateway.request_handled",
    "aeis.advisor.mobile_gateway.auth_failure",
    "aeis.advisor.mobile_gateway.biometric_step_up_triggered",
    "aeis.advisor.mobile_gateway.device_paired",
    "aeis.advisor.mobile_gateway.device_unpaired",
    "aeis.advisor.mobile_gateway.offline_snapshot_served"
  ],
  "events_subscribe": [],
  "storage": {
    "postgres_schemas": [],
    "note": "stateless gateway — no own DB"
  }
}
```

Kluczowe konsekwencje:

- `depends_on`: 4 moduły — gateway nie może wystartować bez `engine`, `actions`, `preferences`, `funding`. W Etapie 1 niektóre z nich są stubami, ale interfejs musi istnieć.
- `events_subscribe: []` — nie reaguje na żadne eventy.
- `storage.postgres_schemas: []` — **stateless**.
- `events_emit`: 6 eventów (3 implementowane Etap 1, 3 zaplanowane Etap 2).

---

## 3. Konfiguracja

### 3.1. Variables środowiskowe

Moduł nie czyta bezpośrednio żadnych env vars. Konfiguracja przez:

- **FastAPI app** (parent app, w której router jest mountowany) — host, port, TLS, CORS.
- **Reverse proxy** (Nginx / Traefik / Cloud LB) — rate limiting, mTLS, header injection.
- **`event_backbone`** — DSN dziedziczone z `sylion.core.event_backbone`.

| ENV (dziedziczone) | Pochodzenie | Użycie |
|---|---|---|
| `SYLION_EVENT_BACKBONE_DSN` | core | Topic publishing |
| `SYLION_AUTH_PUBKEY` | (Etap 2) | RS256 verify dla JWT |
| `SYLION_MOBILE_RATE_LIMIT` | (Etap 2) | per-operator RPS |

### 3.2. Mount routera w aplikacji FastAPI

```python
from fastapi import FastAPI
from sylion.aeis.advisor.mobile_gateway.api import build_mobile_router

app = FastAPI()
app.include_router(build_mobile_router())

# Endpoint będzie dostępny pod: /mobile/v1/cards
```

### 3.3. Konfiguracja autentykacji

Etap 1: tylko `Authorization` header (`Bearer <jwt>`) bez verify. Etap 2: RS256 z public key wystawionym przez `sylion.security.auth`.

Headers wymagane przez wszystkie endpointy:

| Header | Wymagane | Przykład |
|---|---|---|
| `Authorization` | tak | `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvcF9hbGljZSIsImRldmljZV9pZCI6ImRldl9pcGhvbmUifQ.signature` |
| `X-Biometric-Verified` | warunkowo (D3+) | `true` lub `false` |
| `Content-Type` | dla POST/PUT | `application/json` |

### 3.4. Query parameters

| Endpoint | Parametr | Typ | Default | Min | Max |
|---|---|---|---|---|---|
| `GET /cards` | `limit` | int | 50 | 1 | 200 |

### 3.5. Konfiguracja CORS (deployment)

W aplikacji parent (poza modułem):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mobile.sylion.io"],  # tylko mobile app
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Biometric-Verified"],
)
```

### 3.6. Konfiguracja rate limiting (deployment)

W reverse proxy (Nginx example):

```nginx
limit_req_zone $http_authorization zone=mobile:10m rate=10r/s;

location /mobile/v1/ {
    limit_req zone=mobile burst=20 nodelay;
    proxy_pass http://advisor-backend;
}
```

Cel: 10 RPS per JWT token, burst 20.

### 3.7. Konfiguracja TLS

Mobile gateway **wymaga TLS** w produkcji. Stub Etapu 1 może działać po HTTP w dev-mode, ale to celowe security trade-off do czasu Etapu 2.

---

## 4. Funkcje REST → gRPC

### 4.1. `GET /mobile/v1/cards`

**Cel**: lista ostatnich kart rekomendacji dla zalogowanego operatora.

**Headers**:
- `Authorization: Bearer <jwt>` (wymagane)
- `X-Biometric-Verified: <true|false>` (opcjonalne)

**Query params**:
- `limit` (int, 1-200, default 50)

**Implementacja**:

```python
@router.get("/cards", response_model=CardListResponse)
def list_cards(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_biometric_verified: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> CardListResponse:
    principal = _authenticate(request, authorization, x_biometric_verified)
    cards = translator.list_recent_cards(operator_id=principal.operator_id, limit=limit)
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return CardListResponse(cards=cards, total=len(cards))
```

**Response (200)**:

```json
{
  "cards": [
    {
      "envelope_version": "1.0",
      "header": {
        "card_id": "card_001",
        "d_level": "D2",
        "type": "topology_recommendation"
      },
      "body": {
        "recommended": "local_only",
        "alternatives": ["local_plus_vps"]
      }
    }
  ],
  "next_cursor": null,
  "total": 1
}
```

**Errors**:
- `401` — brak/zły token
- `403` — RBAC (Etap 2)

### 4.2. `GET /mobile/v1/cards/{card_id}`

**Cel**: pobranie pojedynczej karty po `card_id`.

**Implementacja**:

```python
@router.get("/cards/{card_id}")
def get_card(
    card_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_biometric_verified: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    principal = _authenticate(request, authorization, x_biometric_verified)
    envelope = translator.get_card(card_id)
    if envelope is None:
        _emit_request_handled(request.url.path, 404, principal.operator_id)
        raise HTTPException(status_code=404, detail="card not found")
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return envelope
```

**Response (200)**: pełen envelope karty z `engine.get_recommendation(card_id)`.

**Errors**:
- `401` — brak/zły token
- `404` — karta nie istnieje

### 4.3. `POST /mobile/v1/cards/{card_id}/actions`

**Cel**: submit akcji operatora (accept/reject/modify/...) dla karty.

**Body**:

```json
{
  "action": "accept",
  "operator_note": "approved during meeting",
  "modified_recommendation": null
}
```

`action` enum: `accept`, `reject`, `modify`, `remind`, `not_useful`, `convert_human_gate`, `convert_masterplan`.

**Step-up logic**:

1. Auth → `MobilePrincipal`.
2. Pobierz envelope karty.
3. Jeśli `card.d_level >= D3` i `principal.biometric_verified == False` → emit `biometric_step_up_triggered`, raise 401.
4. W przeciwnym razie — log intent (Etap 1) lub przesłać do `actions` service (Etap 2).

**Implementacja**:

```python
@router.post("/cards/{card_id}/actions", response_model=CardActionResponse)
def submit_card_action(
    card_id: str,
    body: CardActionRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_biometric_verified: Optional[str] = Header(default=None),
) -> CardActionResponse:
    principal = _authenticate(request, authorization, x_biometric_verified)
    envelope = translator.get_card(card_id)
    if envelope is None:
        _emit_request_handled(request.url.path, 404, principal.operator_id)
        raise HTTPException(status_code=404, detail="card not found")

    d_level = translator.card_d_level(envelope)
    if biometric_required_for_d_level(d_level) and not principal.biometric_verified:
        _emit_biometric_step_up(card_id, principal.operator_id, d_level)
        _emit_request_handled(request.url.path, 401, principal.operator_id)
        raise HTTPException(
            status_code=401,
            detail="biometric step-up required (X-Biometric-Verified header)",
        )

    log.info(
        "mobile_gateway: action=%s card=%s operator=%s",
        body.action, card_id, principal.operator_id,
    )
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return CardActionResponse(
        card_id=card_id,
        action=body.action,
        accepted=True,
        biometric_required=biometric_required_for_d_level(d_level),
    )
```

**Response (200)**:

```json
{
  "card_id": "card_001",
  "action": "accept",
  "accepted": true,
  "biometric_required": false
}
```

**Errors**:
- `401` — brak token / biometric step-up wymagany
- `404` — karta nie istnieje

### 4.4. `GET /mobile/v1/projects`

**Cel**: lista aktywnych projektów operatora.

**Etap 1**: stub — zwraca `{"projects": []}`.

**Implementacja**:

```python
@router.get("/projects", response_model=ProjectListResponse)
def list_projects(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_biometric_verified: Optional[str] = Header(default=None),
) -> ProjectListResponse:
    principal = _authenticate(request, authorization, x_biometric_verified)
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return ProjectListResponse(projects=[])
```

### 4.5. `GET /mobile/v1/projects/{project_id}/lifecycle`

**Cel**: 16-fazowy szkielet lifecycle dla projektu.

**Implementacja**: zwraca skeleton z 16 hooks (sekcja 2.8.1) — wszystkie w stanie `pending`.

```python
@router.get("/projects/{project_id}/lifecycle", response_model=ProjectLifecycleResponse)
def project_lifecycle(
    project_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_biometric_verified: Optional[str] = Header(default=None),
) -> ProjectLifecycleResponse:
    principal = _authenticate(request, authorization, x_biometric_verified)
    skeleton = translator.project_lifecycle_skeleton(project_id)
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return ProjectLifecycleResponse(**skeleton)
```

**Response (200)**:

```json
{
  "project_id": "proj_42",
  "phases": [
    {"hook": "aeis.system.model_setup_requested", "phase_index": 1, "status": "pending"},
    {"hook": "aeis.system.api_provider_setup_requested", "phase_index": 2, "status": "pending"},
    ...
    {"hook": "aeis.final_approval.requested", "phase_index": 16, "status": "pending"}
  ]
}
```

W Etapie 2 status będzie czytany z idea-vault / human-gate state machine.

### 4.6. `GET /mobile/v1/human_gate/pending`

**Cel**: lista ticketów Human Gate oczekujących decyzji.

**Etap 1**: stub — zwraca `{"tickets": []}`.

```python
@router.get("/human_gate/pending", response_model=HumanGateListResponse)
def human_gate_pending(...) -> HumanGateListResponse:
    principal = _authenticate(...)
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return HumanGateListResponse(tickets=[])
```

### 4.7. `POST /mobile/v1/human_gate/{ticket_id}/decide`

**Cel**: decyzja Human Gate (approve/reject/defer).

**Body**:

```json
{
  "decision": "approve",
  "reviewer": "op_alice",
  "reason": "ROI confirmed"
}
```

**Etap 1**: zawsze 501 Not Implemented.

```python
@router.post("/human_gate/{ticket_id}/decide")
def human_gate_decide(...) -> dict[str, Any]:
    principal = _authenticate(...)
    _emit_request_handled(request.url.path, 501, principal.operator_id)
    raise HTTPException(
        status_code=501,
        detail="human_gate decision flow lands in Etap 2 (mobile actions service)",
    )
```

### 4.8. `GET /mobile/v1/funding/deadlines`

**Etap 1**: stub — `{"deadlines": []}`.

### 4.9. `GET /mobile/v1/preferences`

**Etap 1**: stub — `{"operator_id": "...", "preferences": {}}`.

### 4.10. `GET /mobile/v1/preferences/{key}`

**Etap 1**: stub — `{"key": "<key>", "value": null, "source": "default"}`.

### 4.11. `PUT /mobile/v1/preferences/{key}`

**Etap 1**: zawsze 501 Not Implemented.

### 4.12. `GET /mobile/v1/sync/snapshot`

**Cel**: kompletny offline snapshot dla mobile cache (50 ostatnich kart, projekty, HG, funding, settings).

**Implementacja**:

```python
@router.get("/sync/snapshot", response_model=SyncSnapshotResponse)
def sync_snapshot(...) -> SyncSnapshotResponse:
    principal = _authenticate(...)
    snapshot = translator.build_offline_snapshot(operator_id=principal.operator_id)
    _emit_request_handled(request.url.path, 200, principal.operator_id)
    return SyncSnapshotResponse(**snapshot)
```

**Response (200)**:

```json
{
  "operator_id": "op_alice",
  "cards": [...50 cards...],
  "projects": [],
  "human_gate_pending": [],
  "funding_deadlines": [],
  "settings": {},
  "snapshot_taken_at": 1714234567.123
}
```

### 4.13. Pełen openapi spec

Pełna definicja OpenAPI 3.0.3 (`openapi.yaml`):

```yaml
openapi: 3.0.3
info:
  title: SYLION AEIS Advisor — Mobile Gateway
  description: |
    REST gateway exposed by `sylion.aeis.advisor.mobile_gateway` (Etap 1).
    All endpoints require a device-bound JWT bearer token. Endpoints that
    operate on D3+ cards additionally require a fresh biometric step-up
    indicated by the `X-Biometric-Verified` header.

    Etap 1 implementation calls the advisor engine in-process. Etap 2 will
    swap this for a real gRPC client and add the Kotlin Multiplatform
    mobile application that consumes this surface.
  version: 0.1.0
servers:
  - url: /mobile/v1
    description: Mobile gateway base path
security:
  - bearerAuth: []
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  parameters:
    BiometricVerifiedHeader:
      name: X-Biometric-Verified
      in: header
      required: false
      description: |
        Set to `true` after the operator passes a fresh biometric prompt.
        Required for any action whose underlying card has `d_level >= D3`.
      schema:
        type: string
        enum: ["true", "false"]
  schemas:
    AdvisorCardEnvelope:
      type: object
      additionalProperties: true
      required: [envelope_version, header]
      properties:
        envelope_version:
          type: string
        header:
          type: object
          additionalProperties: true
        body:
          type: object
          additionalProperties: true
    CardListResponse:
      type: object
      properties:
        cards:
          type: array
          items:
            $ref: "#/components/schemas/AdvisorCardEnvelope"
        next_cursor:
          type: string
          nullable: true
        total:
          type: integer
    CardActionRequest:
      type: object
      required: [action]
      properties:
        action:
          type: string
          enum: [accept, reject, modify, remind, not_useful, convert_human_gate, convert_masterplan]
        operator_note:
          type: string
          nullable: true
        modified_recommendation:
          type: string
          nullable: true
    CardActionResponse:
      type: object
      properties:
        card_id:
          type: string
        action:
          type: string
        accepted:
          type: boolean
        biometric_required:
          type: boolean
    ProjectListResponse:
      type: object
      properties:
        projects:
          type: array
          items:
            type: object
            additionalProperties: true
    LifecyclePhase:
      type: object
      properties:
        hook:
          type: string
        phase_index:
          type: integer
        status:
          type: string
          enum: [pending, in_progress, approved, blocked]
    ProjectLifecycleResponse:
      type: object
      properties:
        project_id:
          type: string
        phases:
          type: array
          items:
            $ref: "#/components/schemas/LifecyclePhase"
    HumanGateTicketSummary:
      type: object
      properties:
        ticket_id:
          type: string
        title:
          type: string
        pending_since:
          type: number
        d_level:
          type: string
    HumanGateListResponse:
      type: object
      properties:
        tickets:
          type: array
          items:
            $ref: "#/components/schemas/HumanGateTicketSummary"
    HumanGateDecisionRequest:
      type: object
      required: [decision, reviewer]
      properties:
        decision:
          type: string
          enum: [approve, reject, defer]
        reviewer:
          type: string
        reason:
          type: string
          nullable: true
    FundingDeadlinesResponse:
      type: object
      properties:
        deadlines:
          type: array
          items:
            type: object
            additionalProperties: true
    PreferenceListResponse:
      type: object
      properties:
        operator_id:
          type: string
        preferences:
          type: object
          additionalProperties: true
    PreferenceValueResponse:
      type: object
      properties:
        key:
          type: string
        value: {}
        source:
          type: string
          enum: [default, operator, project, system]
    PreferencePutRequest:
      type: object
      required: [value]
      properties:
        value: {}
    SyncSnapshotResponse:
      type: object
      properties:
        operator_id:
          type: string
        cards:
          type: array
          items:
            $ref: "#/components/schemas/AdvisorCardEnvelope"
        projects:
          type: array
          items:
            type: object
            additionalProperties: true
        human_gate_pending:
          type: array
          items:
            $ref: "#/components/schemas/HumanGateTicketSummary"
        funding_deadlines:
          type: array
          items:
            type: object
            additionalProperties: true
        settings:
          type: object
          additionalProperties: true
        snapshot_taken_at:
          type: number
    ErrorResponse:
      type: object
      properties:
        error:
          type: string
        detail:
          type: string
          nullable: true
  responses:
    Unauthorized:
      description: JWT missing / invalid / biometric step-up required
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    Forbidden:
      description: Operator lacks RBAC permissions for this resource
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    NotFound:
      description: Requested resource does not exist
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    NotImplemented:
      description: Endpoint is reserved for Etap 2 — not yet implemented
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
paths:
  /cards:
    get:
      summary: List recent advisor cards for the authenticated operator
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            minimum: 1
            maximum: 200
            default: 50
      responses:
        "200":
          description: Paginated list of cards
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/CardListResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "403":
          $ref: "#/components/responses/Forbidden"
  /cards/{card_id}:
    get:
      summary: Fetch a single advisor card envelope by id
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: card_id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Card envelope
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/AdvisorCardEnvelope"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "404":
          $ref: "#/components/responses/NotFound"
  /cards/{card_id}/actions:
    post:
      summary: Submit an operator action against a card
      description: |
        Cards with `d_level >= D3` require a fresh biometric step-up indicated
        by `X-Biometric-Verified: true`. Without it, the gateway responds 401
        and emits `aeis.advisor.mobile_gateway.biometric_step_up_triggered`.
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: card_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CardActionRequest"
      responses:
        "200":
          description: Action accepted
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/CardActionResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "403":
          $ref: "#/components/responses/Forbidden"
        "404":
          $ref: "#/components/responses/NotFound"
  /projects:
    get:
      summary: List active projects (Etap 1 stub returns empty list)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
      responses:
        "200":
          description: Project list
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ProjectListResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
  /projects/{project_id}/lifecycle:
    get:
      summary: 16-phase lifecycle skeleton for a project
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: project_id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Lifecycle skeleton
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ProjectLifecycleResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
  /human_gate/pending:
    get:
      summary: List Human Gate tickets awaiting operator decision
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
      responses:
        "200":
          description: Pending tickets (Etap 1 stub returns empty list)
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HumanGateListResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
  /human_gate/{ticket_id}/decide:
    post:
      summary: Decide a Human Gate ticket (Etap 2)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: ticket_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/HumanGateDecisionRequest"
      responses:
        "401":
          $ref: "#/components/responses/Unauthorized"
        "501":
          $ref: "#/components/responses/NotImplemented"
  /funding/deadlines:
    get:
      summary: List funding deadlines (Etap 1 stub returns empty list)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
      responses:
        "200":
          description: Funding deadlines
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/FundingDeadlinesResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
  /preferences:
    get:
      summary: Effective preference snapshot (Etap 1 stub returns empty dict)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
      responses:
        "200":
          description: Operator preferences
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PreferenceListResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
  /preferences/{key}:
    get:
      summary: Get a single effective preference value
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: key
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Preference value
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PreferenceValueResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
        "404":
          $ref: "#/components/responses/NotFound"
    put:
      summary: Mutate a preference value (Etap 2 — preferences gRPC owns mutation)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
        - name: key
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/PreferencePutRequest"
      responses:
        "401":
          $ref: "#/components/responses/Unauthorized"
        "501":
          $ref: "#/components/responses/NotImplemented"
  /sync/snapshot:
    get:
      summary: Offline cache snapshot (last 50 cards + 10 projects + HG + funding + settings)
      parameters:
        - $ref: "#/components/parameters/BiometricVerifiedHeader"
      responses:
        "200":
          description: Snapshot
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SyncSnapshotResponse"
        "401":
          $ref: "#/components/responses/Unauthorized"
```

---

## 5. Eventy emitowane

Manifest deklaruje **6 eventów emitowanych**, z których 3 są aktywne w Etapie 1 i 3 zaplanowane w Etapie 2.

### 5.1. Eventy aktywne (Etap 1)

#### 5.1.1. `aeis.advisor.mobile_gateway.request_handled`

**Trigger**: każde zakończone wywołanie endpointu (success lub error).

**Payload**:

```json
{
  "path": "/mobile/v1/cards",
  "status_code": 200,
  "operator_id": "op_alice"
}
```

**Subskrybenci**: monitoring (count requests/op/path), audit_trail (per-operator log).

#### 5.1.2. `aeis.advisor.mobile_gateway.auth_failure`

**Trigger**: każde 401 z auth (brak token, malformed, missing claims).

**Payload**:

```json
{
  "path": "/mobile/v1/cards",
  "reason": "missing Authorization header"
}
```

Możliwe wartości `reason`:
- `"missing Authorization header"`
- `"missing bearer token"`
- `"expected 'Bearer <token>' Authorization header"`
- `"malformed token"`
- `"invalid token payload: <details>"`
- `"token payload must be an object"`
- `"token missing operator subject"`
- `"token missing device_id"`

**Subskrybenci**: security ops (alerty na > N failures w okno czasowym), audit_trail.

#### 5.1.3. `aeis.advisor.mobile_gateway.biometric_step_up_triggered`

**Trigger**: próba akcji na karcie D3+ bez `X-Biometric-Verified: true`.

**Payload**:

```json
{
  "card_id": "card_001",
  "operator_id": "op_alice",
  "d_level": "D3"
}
```

**Subskrybenci**: mobile push notification service (informuje aplikację o konieczności biometric prompt), audit_trail.

### 5.2. Eventy zaplanowane (Etap 2)

#### 5.2.1. `aeis.advisor.mobile_gateway.device_paired`

**Planowany trigger**: rejestracja nowego urządzenia (POST `/devices/pair` — endpoint Etapu 2).

**Planowany payload**:

```json
{
  "device_id": "dev_iphone_15_alice",
  "operator_id": "op_alice",
  "device_pubkey_fingerprint": "sha256:...",
  "paired_at": 1714234567
}
```

#### 5.2.2. `aeis.advisor.mobile_gateway.device_unpaired`

**Planowany trigger**: revoke urządzenia (DELETE `/devices/{id}` — endpoint Etapu 2).

**Planowany payload**:

```json
{
  "device_id": "dev_iphone_15_alice",
  "operator_id": "op_alice",
  "reason": "lost",
  "unpaired_at": 1714298100
}
```

#### 5.2.3. `aeis.advisor.mobile_gateway.offline_snapshot_served`

**Planowany trigger**: `GET /sync/snapshot` z metryką cache hit/miss.

**Planowany payload**:

```json
{
  "operator_id": "op_alice",
  "cards_count": 50,
  "snapshot_size_bytes": 124567,
  "served_at": 1714234567
}
```

W Etapie 1 to po prostu request_handled na ścieżce `/sync/snapshot`. Etap 2 doda dedykowany event z metrykami do telemetry.

### 5.3. Eventy subskrybowane

```json
"events_subscribe": []
```

Mobile gateway **nie subskrybuje** żadnych eventów.

### 5.4. Best-effort emit (try/except)

```python
def _publish(topic: str, payload: dict[str, Any]) -> None:
    try:
        from sylion.core.event_backbone import get_event_backbone
        event = SylionEvent(...)
        get_event_backbone().publish(event)
    except Exception:
        log.warning("mobile_gateway: event emission failed for %s", topic, exc_info=True)
```

Wyjątki są **łykane** — failure na bus-ie NIE łamie request path. To celowe: gateway musi działać nawet przy lokalnym outagu telemetry.

---

## 6. Database tables

```json
"storage": {
  "postgres_schemas": [],
  "note": "stateless gateway — no own DB"
}
```

Mobile gateway jest **stateless** — nie ma własnych tabel PG, nie zapisuje sesji, nie cachuje danych w pamięci między requestami.

### 6.1. Co konsumuje moduł (cudze tabele, przez translator)

| Backend module | Tabela (Etap 1+) | Operacja |
|---|---|---|
| `engine` | `engine_recommendations` | SELECT (read) |
| `actions` (Etap 2) | `actions_intents` | INSERT |
| `human_gate` (Etap 2) | `human_gate_tickets` | SELECT, UPDATE |
| `funding` | `funding_deadlines` | SELECT |
| `preferences` (Etap 2) | `operator_preferences` | SELECT, UPSERT |

Ale gateway nie wykonuje SQL bezpośrednio — całość przez service warstwy backendowych.

### 6.2. Stan w Etapie 2 — device pairing

W Etapie 2 zostanie dodana tabela `mobile_devices` (zarządzana przez `sylion.security.auth`, NIE przez mobile_gateway):

| Kolumna | Typ | Opis |
|---|---|---|
| `device_id` | TEXT PK | Identyfikator urządzenia |
| `operator_id` | TEXT NOT NULL | Właściciel |
| `device_pubkey_fingerprint` | TEXT NOT NULL | SHA256 klucza publicznego |
| `paired_at` | TIMESTAMP NOT NULL | Czas pairingu |
| `last_seen_at` | TIMESTAMP | Ostatnia aktywność |
| `unpaired_at` | TIMESTAMP NULL | Soft-delete |

Ale to **nie należy** do `mobile_gateway` — to zadanie `security` layer.

---

## 7. Przykład użycia

### 7.1. Pełny flow z curl-em

```bash
# Krok 1: zaloguj się przez sylion.security.auth (Etap 2 — w Etapie 1 token wystawiony ręcznie)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvcF9hbGljZSIsImRldmljZV9pZCI6ImRldl9pcGhvbmVfMTUifQ.dummy"

# Krok 2: pobierz snapshot offline
curl -s "https://advisor.sylion.io/mobile/v1/sync/snapshot" \
  -H "Authorization: Bearer $TOKEN"
# {
#   "operator_id": "op_alice",
#   "cards": [...50 cards...],
#   "projects": [],
#   "human_gate_pending": [],
#   "funding_deadlines": [],
#   "settings": {},
#   "snapshot_taken_at": 1714234567.123
# }

# Krok 3: pobierz konkretną kartę
curl -s "https://advisor.sylion.io/mobile/v1/cards/card_001" \
  -H "Authorization: Bearer $TOKEN"
# {
#   "envelope_version": "1.0",
#   "header": {
#     "card_id": "card_001",
#     "d_level": "D3",
#     "type": "vps_recommendation"
#   },
#   "body": {...}
# }

# Krok 4: spróbuj zaakceptować bez biometric (D3 → wymagane)
curl -s -X POST "https://advisor.sylion.io/mobile/v1/cards/card_001/actions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "accept", "operator_note": "approved"}'
# HTTP 401
# {"detail": "biometric step-up required (X-Biometric-Verified header)"}

# Krok 5: prompt biometric na urządzeniu, spróbuj ponownie z headerem
curl -s -X POST "https://advisor.sylion.io/mobile/v1/cards/card_001/actions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Biometric-Verified: true" \
  -H "Content-Type: application/json" \
  -d '{"action": "accept", "operator_note": "approved"}'
# HTTP 200
# {
#   "card_id": "card_001",
#   "action": "accept",
#   "accepted": true,
#   "biometric_required": true
# }
```

### 7.2. Klient TypeScript (test/dev)

```typescript
const BASE = "https://advisor.sylion.io/mobile/v1";

async function listCards(token: string, limit = 50) {
  const res = await fetch(`${BASE}/cards?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function submitCardAction(
  token: string,
  cardId: string,
  action: string,
  biometricVerified = false,
  note?: string,
) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  if (biometricVerified) headers["X-Biometric-Verified"] = "true";

  const res = await fetch(`${BASE}/cards/${cardId}/actions`, {
    method: "POST",
    headers,
    body: JSON.stringify({ action, operator_note: note }),
  });

  if (res.status === 401) {
    const body = await res.json();
    if (body.detail.includes("biometric step-up required")) {
      throw new BiometricRequiredError(cardId);
    }
    throw new AuthError(body.detail);
  }
  return res.json();
}
```

### 7.3. Klient Python (testowy)

```python
import requests

BASE = "http://127.0.0.1:8010/mobile/v1"

def make_token(operator_id: str, device_id: str) -> str:
    """Stub: build a JWT-like token without signature (Etap 1 only)."""
    import base64
    import json
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": operator_id, "device_id": device_id}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.dummy"

token = make_token("op_alice", "dev_iphone_15")

# List cards
r = requests.get(
    f"{BASE}/cards",
    headers={"Authorization": f"Bearer {token}"},
)
print(r.status_code, r.json())

# Submit action with biometric step-up
r = requests.post(
    f"{BASE}/cards/card_001/actions",
    headers={
        "Authorization": f"Bearer {token}",
        "X-Biometric-Verified": "true",
    },
    json={"action": "accept", "operator_note": "ok"},
)
print(r.status_code, r.json())
```

### 7.4. Test integracyjny (pytest)

```python
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sylion.aeis.advisor.mobile_gateway.api import (
    build_mobile_router,
    reset_mobile_router,
)

@pytest.fixture
def client():
    reset_mobile_router()
    app = FastAPI()
    app.include_router(build_mobile_router())
    yield TestClient(app)
    reset_mobile_router()

@pytest.fixture
def valid_token():
    # JWT-like token (Etap 1 — bez signature verify)
    import base64, json
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "op_alice", "device_id": "dev_test"}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.dummy"

def test_cards_endpoint_requires_auth(client):
    r = client.get("/mobile/v1/cards")
    assert r.status_code == 401

def test_cards_endpoint_with_valid_token(client, valid_token):
    r = client.get(
        "/mobile/v1/cards",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "total" in body

def test_card_action_requires_biometric_for_d3(client, valid_token):
    # Setup: zamockuj engine.get_recommendation aby zwrócił kartę D3
    # ... (mock setup omitted)

    r = client.post(
        "/mobile/v1/cards/card_d3/actions",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"action": "accept"},
    )
    assert r.status_code == 401
    assert "biometric step-up required" in r.json()["detail"]

def test_card_action_succeeds_with_biometric(client, valid_token):
    r = client.post(
        "/mobile/v1/cards/card_d3/actions",
        headers={
            "Authorization": f"Bearer {valid_token}",
            "X-Biometric-Verified": "true",
        },
        json={"action": "accept"},
    )
    assert r.status_code == 200
    assert r.json()["accepted"] is True

def test_unimplemented_endpoint_returns_501(client, valid_token):
    r = client.put(
        "/mobile/v1/preferences/key",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"value": "x"},
    )
    assert r.status_code == 501
```

---

## 8. Verification — checklist akceptacyjny

Lista odpowiada `golden_tests.minimum_required` z manifestu plus dodatkowe scenariusze.

### 8.1. Auth — JWT decode

| # | Test | Oczekiwane |
|---|---|---|
| A1 | Brak headera `Authorization` | 401 + event `auth_failure` z `reason="missing Authorization header"` |
| A2 | `Authorization: foo bar baz` | 401 + `reason="expected 'Bearer <token>' Authorization header"` |
| A3 | `Authorization: Bearer abc` (1-część) | 401 + `reason="malformed token"` |
| A4 | `Authorization: Bearer aaa.bbb.ccc` z pustym payloadem | 401 + `reason` zaczynające się od `"invalid token payload"` |
| A5 | Payload to JSON array zamiast object | 401 + `reason="token payload must be an object"` |
| A6 | Payload bez `sub`/`operator_id` | 401 + `reason="token missing operator subject"` |
| A7 | Payload z `sub`, ale bez `device_id`/`did` | 401 + `reason="token missing device_id"` |
| A8 | Pełen poprawny payload | 200, `MobilePrincipal` poprawnie wypełniony |
| A9 | `Authorization: BEARER <token>` (uppercase) | 200 — case-insensitive na schema |

### 8.2. Biometric — step-up logic

| # | Wejście | `biometric_required_for_d_level` |
|---|---|---|
| B1 | `"D0"` | False |
| B2 | `"D1"` | False |
| B3 | `"D2"` | False |
| B4 | `"D3"` | True |
| B5 | `"D4"` | True |
| B6 | `"D5"` | True |
| B7 | `""` (puste) | False |
| B8 | `"d3"` | True (po `.upper()`) |
| B9 | `"X3"` | False (zły prefix) |
| B10 | `"DX"` | False (zły ordinal) |
| B11 | `"D3 "` (trailing space) | True (po `.strip()`) |

### 8.3. Header `X-Biometric-Verified` — parsing

| # | Wartość | `_parse_truthy` |
|---|---|---|
| H1 | `"true"` | True |
| H2 | `"True"` | True |
| H3 | `"TRUE"` | True |
| H4 | `"1"` | True |
| H5 | `"yes"` | True |
| H6 | `"on"` | True |
| H7 | `"false"` | False |
| H8 | `"0"` | False |
| H9 | `""` (puste) | False |
| H10 | `None` | False |
| H11 | `"random"` | False |

### 8.4. Endpoints — golden tests (z manifestu)

| # | Test (z manifestu) | Status |
|---|---|---|
| G1 | `cards_endpoint_returns_paginated_list` | 200 + `{cards, total, next_cursor}` |
| G2 | `card_detail_returns_envelope_when_card_exists` | 200 + envelope |
| G3 | `card_detail_returns_404_when_missing` | 404 + ErrorResponse |
| G4 | `card_action_accepts_when_low_risk` | 200 + `accepted=true, biometric_required=false` (dla D2) |
| G5 | `card_action_requires_biometric_when_d3_or_higher` | 401 + emit `biometric_step_up_triggered` |
| G6 | `auth_failure_returns_401` | 401 + emit `auth_failure` |
| G7 | `sync_snapshot_returns_expected_shape` | 200 + 6 wymaganych pól |
| G8 | `unimplemented_endpoints_return_501` | 501 dla 2 ścieżek (`PUT /preferences/{key}`, `POST /human_gate/{id}/decide`) |
| G9 | `request_handled_event_emitted_after_successful_call` | event z poprawnym `path`, `status_code`, `operator_id` |

### 8.5. Eventy — emit verification

| # | Akcja | Spodziewany event |
|---|---|---|
| E1 | Pomyślny `GET /cards` | `request_handled` z `status_code=200` |
| E2 | 404 dla `GET /cards/{id}` | `request_handled` z `status_code=404` |
| E3 | 401 z brakiem token | `auth_failure` z `reason="missing Authorization header"` + `request_handled`? **Uwaga**: w kodzie `auth_failure` jest emit, potem raise HTTPException — `request_handled` NIE jest emitowane przy auth fail (tylko `auth_failure`). Trzeba zweryfikować. |
| E4 | D3+ action bez biometric | `biometric_step_up_triggered` + `request_handled(status=401)` |
| E5 | Bus-failure podczas emit | warning log, brak crashu — request leci dalej |

### 8.6. Stateless verification

| # | Test | Oczekiwane |
|---|---|---|
| SS1 | Gateway nie ma tabel PG własnych | manifest `postgres_schemas: []` |
| SS2 | Brak in-memory cache między requestami | (pamięć router-level wyłącznie cache singletona, ale bez per-user state) |
| SS3 | Restart serwera nie tracimy żadnych danych gateway-specific | brak danych do utracenia |

### 8.7. Lifecycle — 16 hooks

| # | Test | Oczekiwane |
|---|---|---|
| L1 | `GET /projects/{id}/lifecycle` zwraca dokładnie 16 faz | `len(phases) == 16` |
| L2 | Każda faza ma `hook`, `phase_index`, `status="pending"` | wszystkie 16 |
| L3 | `phase_index` startuje od 1 i jest sekwencyjne | 1..16 |
| L4 | Hooks zgodne z `_LIFECYCLE_HOOKS` | dokładny match |

### 8.8. Sync snapshot — shape

| # | Pole | Typ | Default |
|---|---|---|---|
| SY1 | `operator_id` | str | `principal.operator_id` |
| SY2 | `cards` | list[dict] | last 50 z engine |
| SY3 | `projects` | list[dict] | `[]` (Etap 1) |
| SY4 | `human_gate_pending` | list[HumanGateTicketSummary] | `[]` (Etap 1) |
| SY5 | `funding_deadlines` | list[dict] | `[]` (Etap 1) |
| SY6 | `settings` | dict | `{}` (Etap 1) |
| SY7 | `snapshot_taken_at` | float | `time.time()` |

### 8.9. Singleton

| # | Test | Oczekiwane |
|---|---|---|
| SI1 | Drugie wywołanie `build_mobile_router()` zwraca ten sam obiekt | identical reference |
| SI2 | `reset_mobile_router()` powoduje, że kolejny call buduje świeży | new reference |
| SI3 | Wielowątkowy contention na `build_mobile_router()` | tylko 1 build (lock) |

### 8.10. Pełna macierz dostępności endpointów (Etap 1)

| Endpoint | Auth | Bio (D3+) | Etap 1 status |
|---|---|---|---|
| `GET /cards` | wymagane | nie wymagane | implemented |
| `GET /cards/{id}` | wymagane | nie wymagane | implemented |
| `POST /cards/{id}/actions` | wymagane | wymagane (D3+) | implemented (intent only) |
| `GET /projects` | wymagane | nie | stub `[]` |
| `GET /projects/{id}/lifecycle` | wymagane | nie | implemented |
| `GET /human_gate/pending` | wymagane | nie | stub `[]` |
| `POST /human_gate/{id}/decide` | wymagane | wymagane | **501** |
| `GET /funding/deadlines` | wymagane | nie | stub `[]` |
| `GET /preferences` | wymagane | nie | stub `{}` |
| `GET /preferences/{key}` | wymagane | nie | stub `null` |
| `PUT /preferences/{key}` | wymagane | nie | **501** |
| `GET /sync/snapshot` | wymagane | nie | implemented |

---

## 9. Troubleshooting

### 9.1. 401 mimo poprawnego JWT

**Symptom**: Klient wysyła token, dostaje 401 z `"missing Authorization header"`.

**Przyczyna**:
- Header nie dociera do FastAPI (proxy go zjada).
- Format `Authorization` wartości jest niezgodny z `Bearer <token>`.

**Diagnoza**:

```bash
# Sprawdź, co dochodzi do gateway
curl -v "https://advisor.sylion.io/mobile/v1/cards" \
  -H "Authorization: Bearer eyJ..."
# Look at Sent: lines

# Sprawdź log
grep "auth_failure" /var/log/sylion/event_bus.log | tail -5
# Payload zawiera dokładny `reason`
```

**Rozwiązanie**:

1. Zweryfikuj, że proxy/LB nie strip-uje headera (Nginx: `proxy_pass_header Authorization;`).
2. Upewnij się, że format to dokładnie `Bearer <jwt>` z pojedynczą spacją.
3. Sprawdź, czy `<jwt>` ma 3 części rozdzielone kropkami.
4. Dekoduj payload (środkowa część) base64url i potwierdź obecność `sub` lub `operator_id` ORAZ `device_id` lub `did`.

### 9.2. Niespodziewane 401 dla D3+ działania

**Symptom**: `POST /cards/{id}/actions` na karcie D3 zwraca 401 mimo `X-Biometric-Verified: true`.

**Przyczyna**:
- Header `X-Biometric-Verified` ma inną wartość niż `"true"` / `"1"` / `"yes"` / `"on"` (case-insensitive).
- Header został strip-owany przez proxy.
- Engine zwraca kartę z `header.d_level = "D3"`, mimo że klient myślał, że to D2.

**Diagnoza**:

```bash
# 1. Wyświetl event biometric_step_up_triggered
grep "biometric_step_up" /var/log/sylion/event_bus.log

# 2. Pobierz kartę i sprawdź d_level
curl "/mobile/v1/cards/card_001" -H "Authorization: Bearer $T" | jq '.header.d_level'
# "D3"

# 3. Sprawdź dokładnie wysyłaną wartość headera
curl -v -X POST ".../cards/card_001/actions" \
  -H "Authorization: Bearer $T" \
  -H "X-Biometric-Verified: TRUE" \
  -H "Content-Type: application/json" \
  -d '{"action":"accept"}' 2>&1 | grep "X-Biometric"
```

**Rozwiązanie**:

1. Wyślij dokładnie `X-Biometric-Verified: true` (lub `1`, `yes`, `on`).
2. Sprawdź, czy proxy nie strip-uje custom headerów (Nginx: `proxy_set_header X-Biometric-Verified $http_x_biometric_verified;`).
3. Jeśli karta jest D2, ale UI pokazuje step-up — sprawdź flow w mobile (mobile może mieć stale d_level cache).

### 9.3. `request_handled` event nie pojawia się

**Symptom**: Subskrybent nie odbiera eventu po pomyślnym requeście.

**Przyczyna**:
- `event_backbone` nie jest dostępny (try/except łyka błąd).
- Subskrybent zarejestrowany za późno (po request).
- Topic mismatch (literówka).

**Diagnoza**:

```bash
# Sprawdź log warningów
grep "mobile_gateway: event emission failed" /var/log/sylion/app.log

# Sprawdź, czy event backbone w ogóle działa
grep "event_backbone" /var/log/sylion/app.log | tail -10
```

**Rozwiązanie**:

1. Restart procesu Advisor — czasami event_backbone wymaga reinicjalizacji.
2. Zarejestruj subskrybenta przed pierwszym requestem do gateway.
3. Sprawdź dokładny topic: `aeis.advisor.mobile_gateway.request_handled` (cztery kropki, trzy człony).

### 9.4. 501 dla wszystkich endpointów

**Symptom**: Każdy endpoint zwraca 501 Not Implemented.

**Przyczyna**: Etap 1 ma 2 endpointy z hard-coded 501:
- `PUT /preferences/{key}`
- `POST /human_gate/{id}/decide`

Pozostałe są implementowane lub stubowane.

**Diagnoza**:

```bash
# Lista endpointów z 501
grep -n "501" src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/api.py
```

**Rozwiązanie**: Te endpointy są zaplanowane na Etap 2. Nie używaj ich w Etapie 1.

### 9.5. Pusty list dla `/projects` lub `/funding/deadlines`

**Symptom**: API zwraca puste listy dla ressourców, gdzie spodziewasz się danych.

**Przyczyna**: To **stub Etapu 1**:
- `GET /projects` → zawsze `[]`
- `GET /funding/deadlines` → zawsze `[]`
- `GET /human_gate/pending` → zawsze `[]`
- `GET /preferences` → zawsze `{}`
- `GET /preferences/{key}` → zawsze `{value: null, source: "default"}`

**Rozwiązanie**: To zaplanowane na Etap 2. W Etapie 1 użyj `engine` direct call lub stwórz custom endpoint.

### 9.6. Build router fails on import

**Symptom**: `from sylion.aeis.advisor.mobile_gateway.api import build_mobile_router` rzuca `ImportError`.

**Przyczyna**:
- Brakująca zależność (`fastapi`, `pydantic`).
- Cykliczny import (rzadkie).
- Backend module nie zainstalowany (`engine.service.get_engine_service`).

**Diagnoza**:

```bash
python -c "from sylion.aeis.advisor.engine.service import get_engine_service; print(get_engine_service())"
```

**Rozwiązanie**:

1. `pip install fastapi pydantic`.
2. Sprawdź, czy `engine` module jest zainstalowany — manifest `depends_on` wymaga.
3. Zrestartuj proces, jeśli singleton trzyma stale referencje.

### 9.7. Gateway zwraca 422 zamiast 401 dla zmienionego body

**Symptom**: `POST /cards/{id}/actions` z body bez `action` zwraca 422 (Pydantic validation), nie 401.

**Przyczyna**: FastAPI najpierw waliduje request (przed handler), więc body validation idzie pierwsza.

**Rozwiązanie**: To poprawne zachowanie. Jeśli klient wysyła puste/błędne body, dostaje 422. Auth check odbywa się dopiero po deserialization.

### 9.8. Singleton nie respektuje `reset_mobile_router` w testach

**Symptom**: Mimo `reset_mobile_router()` w fixture, kolejny test używa starego routera.

**Przyczyna**:
- `reset_mobile_router()` wywołane PO `build_mobile_router()` w teście — następny test buduje świeżo.
- Ale `app.include_router(<old>)` w fixture trzyma stary obiekt.

**Rozwiązanie**:

```python
@pytest.fixture
def client():
    reset_mobile_router()  # NAJPIERW reset
    app = FastAPI()
    app.include_router(build_mobile_router())  # potem build
    yield TestClient(app)
    reset_mobile_router()  # cleanup po teście
```

Klucz: reset PRZED build, każdy test ma świeży app + router.

### 9.9. Klient mobilny dostaje CORS error

**Symptom**: Aplikacja mobilna (KMP / web) widzi `CORS policy: No 'Access-Control-Allow-Origin' header`.

**Przyczyna**: Brak `CORSMiddleware` w aplikacji parent.

**Rozwiązanie**: dodaj CORS middleware (sekcja 3.5 wyżej).

---

## 10. Cross-references

### 10.1. Moduły zależne (depends_on)

| Moduł | Cel zależności | Plik |
|---|---|---|
| `sylion.aeis.advisor.engine` | Source dla `/cards`, `/cards/{id}`, `/sync/snapshot` | (Etap 1+) |
| `sylion.aeis.advisor.actions` | Submit akcji operatora — `/cards/{id}/actions` (Etap 2 — Etap 1 to log only) | (Etap 2) |
| `sylion.aeis.advisor.preferences` | Effective preferences snapshot + mutation | (Etap 2) |
| `sylion.aeis.advisor.funding` | Lista deadline'ów dla `/funding/deadlines` (Etap 2) | [`07_funding.md`](./07_funding.md) |

### 10.2. Moduły downstream (consumers eventów)

| Subskrybent | Topiki | Cel |
|---|---|---|
| `audit_trail` | wszystkie 6 | append-only log |
| `monitoring` | `request_handled`, `auth_failure` | metryki HTTP, alerty |
| `security_ops` | `auth_failure`, `biometric_step_up_triggered` | brute-force detection |
| `mobile_push` (Etap 2) | `biometric_step_up_triggered` | natywny prompt na urządzeniu |

### 10.3. Dokumenty architektoniczne

- [`docs/claude_parallel/aeis_advisor/00_architecture/03_card_envelope.md`](../../claude_parallel/aeis_advisor/00_architecture/03_card_envelope.md) — kanoniczny format envelope kart (`AdvisorCardEnvelope`).
- [`docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md`](../../claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md) — lista 16 hooków lifecycle (`_LIFECYCLE_HOOKS`).
- [`docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md`](../../claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md) — Decision Ladder D0-D5; reguła biometric step-up dla D3+.
- [`docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md`](../../claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md) — taksonomia eventów (`mobile_gateway.*`).
- [`docs/claude_parallel/aeis_advisor/08_audit_revisions.md`](../../claude_parallel/aeis_advisor/08_audit_revisions.md) — Revision 3 (sync-first endpoints).

### 10.4. Code references

- **Router**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/api.py:52-69` — `build_mobile_router` + `reset_mobile_router`.
- **Endpoints builder**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/api.py:136-306` — `_build()` z 12 dekoratorami.
- **Auth**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/auth.py:67-85` — `authenticate`.
- **Step-up**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/auth.py:88-99` — `biometric_required_for_d_level`.
- **Translator**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/translator.py:39-75` — 5 funkcji.
- **Models**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/_models.py:10-93` — Pydantic models.
- **OpenAPI**: `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/openapi.yaml` — single source of truth.
- **Manifest**: `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.mobile_gateway.json`.

### 10.5. Testy złote (Etap 1 → Etap 2)

Lokalizacja: `tests/aeis/advisor/mobile_gateway/`.

Wymagane minimum (z manifestu):
- `cards_endpoint_returns_paginated_list`
- `card_detail_returns_envelope_when_card_exists`
- `card_detail_returns_404_when_missing`
- `card_action_accepts_when_low_risk`
- `card_action_requires_biometric_when_d3_or_higher`
- `auth_failure_returns_401`
- `sync_snapshot_returns_expected_shape`
- `unimplemented_endpoints_return_501`
- `request_handled_event_emitted_after_successful_call`

### 10.6. Granica z core layer

Mobile gateway konsumuje z core wyłącznie:
- `sylion.core.event_bus.SylionEvent` — typy eventów.
- `sylion.core.event_backbone.get_event_backbone` — publishing (lazy import w `_publish`).

Brak innych zależności — to celowe minimum dla powierzchni mobile.

### 10.7. Granica z security layer

Etap 1: `sylion.security.auth` NIE jest używany. Etap 2: pełna integracja:
- Token verification (RS256).
- Device pubkey storage.
- Biometric nonce signing.
- Rate limiting per principal.

Komentarz w kodzie:

```python
# TODO(Etap 2): swap stub decode for sylion.security.auth signature verification.
```

### 10.8. Mapping endpointów do tools/operators

| Endpoint | Operator persona | Tool/Use case |
|---|---|---|
| `GET /cards` | Operator decyzyjny (właściciel) | Lista zgromadzonych rekomendacji do zaakceptowania |
| `GET /cards/{id}` | Operator decyzyjny | Pełen detal jednej karty |
| `POST /cards/{id}/actions` | Operator decyzyjny | Akcja: accept/reject/modify |
| `GET /projects` | Operator wieloprojektowy | Przegląd portfolio |
| `GET /projects/{id}/lifecycle` | Operator | Stan postępu projektu |
| `GET /human_gate/pending` | Operator-zatwierdzający | Tickety do decyzji |
| `POST /human_gate/{id}/decide` | Operator-zatwierdzający (Etap 2) | Aprobata Human Gate |
| `GET /funding/deadlines` | Operator + funding manager | Najbliższe terminy grantów |
| `GET /preferences` | Operator | Snapshot ustawień |
| `GET /preferences/{key}` | Operator | Pojedyncza preferencja |
| `PUT /preferences/{key}` | Operator (Etap 2) | Mutacja preferencji |
| `GET /sync/snapshot` | Operator offline-first | Pełen cache na czas braku zasięgu |

### 10.9. Operator-facing dokumentacja

- W aplikacji KMP (Etap 2) — onboarding tutorial pokrywający: pairing, biometric setup, offline mode.
- Backend README (placeholder — istnieje sam manifest, brak pełnego README dla `mobile_gateway`).

### 10.10. Migracja z REST do gRPC (Etap 2)

W Etapie 2 `translator.py` zostanie przepisany — zamiast `get_engine_service()` (in-process) użyje gRPC client:

```python
# Etap 2 (planowane)
from sylion.aeis.advisor.engine.grpc_client import get_engine_grpc_client

def list_recent_cards(operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
    client = get_engine_grpc_client()
    request = ListRecommendationsRequest(operator_id=operator_id, limit=limit)
    response = client.ListRecommendations(request)
    return [proto_to_dict(card) for card in response.cards]
```

REST contract (`openapi.yaml`) pozostaje stabilny — to gateway, klient KMP nie zauważy zmiany.

### 10.11. Migracja JWT (Etap 2)

```python
# Etap 1 (stub)
def authenticate(authorization_header, biometric_header):
    token = extract_bearer(authorization_header)
    claims = decode_token_unverified(token)  # NO signature check
    ...

# Etap 2 (planowane)
from sylion.security.auth import verify_token

def authenticate(authorization_header, biometric_header):
    token = extract_bearer(authorization_header)
    claims = verify_token(token, algorithms=["RS256"], audience="advisor.mobile")
    ...
```

Migration będzie backward-compatible na poziomie API — klient nie zauważy. Tylko zmieni się cryptographic properties.

### 10.12. Pełna lista 6 zadeklarowanych eventów

| # | Event | Etap 1 | Etap 2 |
|---|---|---|---|
| 1 | `aeis.advisor.mobile_gateway.request_handled` | aktywne | aktywne (rozszerzone payload) |
| 2 | `aeis.advisor.mobile_gateway.auth_failure` | aktywne | aktywne (więcej szczegółów) |
| 3 | `aeis.advisor.mobile_gateway.biometric_step_up_triggered` | aktywne | aktywne |
| 4 | `aeis.advisor.mobile_gateway.device_paired` | brak (TODO) | aktywne |
| 5 | `aeis.advisor.mobile_gateway.device_unpaired` | brak (TODO) | aktywne |
| 6 | `aeis.advisor.mobile_gateway.offline_snapshot_served` | brak (TODO) | aktywne |
