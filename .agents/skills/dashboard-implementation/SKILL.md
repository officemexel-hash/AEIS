---
name: dashboard-implementation
description: Implementacja klasy J (Surface) i 5 rozszerzeń Dashboardu. Użyj przy pracy nad którymkolwiek z modułów `sylion.surface.*`, panelami Console UI, Command Bus, Artifact Control, Process Canvas, Readiness lub replay audytu.
---

# Dashboard Implementation Skill — V5

## Zawsze przeczytaj najpierw
1. `.Codex/docs/DASHBOARD_FUNCTIONAL_SPEC.md`
2. `.Codex/docs/DASHBOARD_TECHNICAL_SPEC.md`
3. `.Codex/docs/DASHBOARD_V5_MERGE_NOTES.md`

Nie improwizuj. V5 zamraża kluczowe decyzje.

## Moduły klasy J+ (8 total)

| Moduł | Port | Główne funkcje |
|---|---|---|
| console_api | 5801 | agregacja read-side, stan instancji, history snapshots |
| console_ui | — | static-first Next.js application |
| ws_gateway | 5802 | WS fan-out, subscriptions, presence |
| command_bus | 5803 | intent lifecycle, two-phase routing, apply orchestration |
| event_sourcing_store | 5804 | append-only stream, snapshots, replay, projection repair |
| artifact_control | 5805 | upload/version/publish/deprecate |
| process_canvas | 5806 | Yjs sync, DAG projection, validation |
| readiness_engine | 5807 | deterministic readiness + ML advisory |

## Zamrożone decyzje (nie podważaj)

1. **TWO_PHASE default**, NIE immediate default
2. **Yjs + tldraw**, NIE React Flow, NIE locking-based editor
3. **Yjs is source of truth** dla Canvas; SQL = projection only
4. **Browser uploads przez signed HTTP / resumable multipart**, NIE gRPC-Web client streaming
5. **Deterministic primary + ML advisory secondary**
6. **Pełny event sourcing**, NIE tylko audit log
7. **Static-first UI in prod**, NIE SSR-dependent control plane
8. **Hybrid deployment**
9. **Bootstrap bez tokena, localhost-bound**
10. **Secrets never enter event store / Yjs / replay / evidence payload**

Zmiana którejkolwiek z tych decyzji to minimum **D3 + Council 4/4**.

## Zasady szczególne

### 1. Event store jest append-only
Nigdy nie używaj `UPDATE` / `DELETE` na historii eventów. Korekta = nowy event lub redaction event + projection logic.

### 2. Source of truth
- `event_sourcing_store` = source of truth dla historii działań operatorskich
- `Yjs document` = source of truth dla collaborative canvas state
- projections są odtwarzalne i disposable

### 3. Dwa światy współbieżności
- Canvas/freeform collaboration = CRDT/Yjs
- Domenowe zmiany chronione governance = Command Bus + `expected_version`

### 4. Frontend RBAC to tylko UX
Ukryty button nie daje bezpieczeństwa. Każdy endpoint musi mieć backend enforcement.

### 5. Policy rules
Nowy intent type:
- domyślnie `TWO_PHASE`
- `IMMEDIATE` tylko gdy jawnie dopuszcza to policy rule i decyzja jest D0–D1

### 6. Secrets hygiene
Nie serializuj:
- raw API keys
- raw secret payloads
- decrypted secrets
- full credential diffs

Do UI/eventów trafia tylko referencja lub masked preview.

### 7. Replay correctness
Nowe feature’y muszą działać z replay:
- event payload musi być wystarczający do odbudowy stanu
- projection rebuild musi być przewidziany
- history snapshot w UI ma być read-only

## Task template: Scaffold module

```text
Jesteś sub-agentem scaffoldującym moduł `sylion.surface.<module_name>`.

Wejście:
- Port: <5801-5807>
- Owner plan: P17
- Dependencies: <lista depends_on>
- Docs:
  - `.Codex/docs/DASHBOARD_FUNCTIONAL_SPEC.md`
  - `.Codex/docs/DASHBOARD_TECHNICAL_SPEC.md`

Zadania:
1. Utwórz katalog `modules/sylion_surface_<module>/`
2. Wypełnij `manifest.yaml`
3. Utwórz `.proto` szkielet zgodnie ze specem V5
4. Wygeneruj stub service/server
5. Dodaj migration `001_init.sql`
6. Dodaj 3 golden tests minimum
7. Dodaj README modułu
8. Opisz depends_on i event subjects
```

## Task template: Implement panel

```text
Jesteś sub-agentem implementującym panel `<PanelName>` w `console_ui`.

Zadania:
1. Utwórz route/page dla panelu
2. Pobierz dane przez klienta gRPC-Web / REST shim
3. Dodaj live refresh przez WS subscriptions
4. Wszystkie akcje opakuj przez IntentSubmitter / Command Bus
5. Dodaj RbacGate
6. Dodaj mode-aware rendering
7. Dodaj test E2E
```

## Task template: Implement upload flow

```text
Nigdy nie implementuj browser uploadu jako gRPC-Web client stream.
Flow:
1. `InitiateUpload`
2. upload bytes by signed HTTP or resumable multipart
3. `FinalizeUpload`
4. schema/virus/checksum validation
5. DRAFT/PENDING artifact state
6. publish przez Command Bus
```

## Common pitfalls

- bezpośredni `UPDATE` na event store
- traktowanie projection store jak source of truth
- mieszanie freeform canvas fields z governance-protected fields
- SSR-dependent panel logic w prod
- gRPC-Web upload streaming z browsera
- brak idempotency handling
- brak dead-letter/rebuild path dla projections
- frontend RBAC bez backend enforcement
- tokenless setup bez localhost bind
- zapisanie surowego sekretu do event payload lub Yjs update

## Integracje z resztą bundle

- `decision-ladder` — klasyfikacja D0–D5
- `council-voting` — review/quorum dla D3+
- `evidence-pack` — evidence przy applied intents D2+
- `security-profile` — embedded vs separated deployment
- `module-scaffold` — standardowy scaffold
- `proto-contract` — finalizacja kontraktów
- `golden-test` — minimalny zestaw testów
- `sylion-canon` — canon as active immutable artifact
