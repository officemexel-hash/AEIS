# ADR-0028: run_codebase_audit() w orchestrator + POST /api/pipeline/run

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/upload_deep  

---

## Kontekst

Audyt mega_audit/upload_deep wykazał, że funkcja analizy codebase (upload ZIP → ekstrakcja → analiza przez agentów) była dostępna wyłącznie przez ręczne wywołanie skryptów CLI (`scripts/run_pipeline.sh`). Brak:

1. **Programowalnego API**: żaden endpoint HTTP nie pozwalał na wyzwolenie pełnej analizy codebase — blokowało integrację CI/CD i dashboard.
2. **Centralnej funkcji orchestratora**: logika analizy była rozproszona między `agents/orchestrator.py`, `scripts/run_pipeline.sh` i `dashboard/app.py` bez spójnego punktu wejścia.
3. **Obsługi stanu pipeline**: brak mechanizmu śledzenia stanu uruchomionej analizy (running/completed/failed) — użytkownik nie wiedział czy analiza trwa czy zakończyła się błędem.

Audyt `mega_audit/orchestrator_run_codebase_audit/` i `mega_audit/pipeline_run_button/` wskazał na żądanie: przycisk "Run Audit" w dashboardzie powinien wyzwalać `POST /api/pipeline/run` → orchestrator → agenci → wyniki w UI.

Rozważane warianty:
- **O1** — Endpoint `POST /api/pipeline/run` wywołujący `subprocess` (`run_pipeline.sh`) — prosta integracja
- **O2** — Nowa metoda `run_codebase_audit()` w `agents/orchestrator.py` wywołana asynchronicznie przez endpoint (wybrana)
- **O3** — Kolejka zadań (Celery/RQ) z workerami — nadmierna złożoność dla lokalnej aplikacji
- **O4** — WebSocket push zamiast REST endpoint dla real-time status

## Decyzja

Wdrożenie **O2**: dedykowana metoda `run_codebase_audit(zip_path: str, config: AuditConfig) -> AuditRunID` w `agents/orchestrator.py`. Endpoint `POST /api/pipeline/run` (z CSRF — patrz ADR-0026) wywołuje tę metodę asynchronicznie (`asyncio.create_task`). Stan pipeline przechowywany w tabeli `pipeline_runs` (SQLite) z polami: `run_id`, `status`, `started_at`, `finished_at`, `artifact_path`. Polling statusu przez `GET /api/pipeline/status/{run_id}`.

Przycisk "Run Audit" w `dashboard/templates/pipeline.html` wywołuje `POST /api/pipeline/run` i przekierowuje do strony statusu z auto-refresh co 5s.

## Konsekwencje

### Pozytywne
- Integracja CI/CD: `curl -X POST /api/pipeline/run -F zip=@codebase.zip` uruchamia pełny audit
- Dashboard: widoczność stanu analizy w czasie rzeczywistym (polling SSE planowane w v5.10)
- Idempotentność: każde wywołanie generuje unikalne `run_id` (UUID4) — brak konfliktów równoległych uruchomień
- `run_codebase_audit()` testowalna jednostkowo bez stawiania serwera HTTP

### Negatywne
- Polling co 5s generuje N×5s opóźnienie reakcji UI — akceptowalne dla długich analiz (> 60s)
- Tabela `pipeline_runs` wymaga migracji schematu (ADR-0033: run_migrations_v3_to_v4)
- Brak limitowania równoległych uruchomień — wiele równoczesnych `POST /api/pipeline/run` może przeciążyć system

### Neutralne
- Artefakty (raporty) zapisywane do `workspace_uploads/` z unikalną nazwą `run_{run_id}/`
- Limit rozmiaru ZIP: 50 MB (konfigurowalny przez `config.yaml: pipeline.max_upload_mb`)

## Alternatywy odrzucone

- **subprocess (O1)**: brak obsługi błędów Pythona, niemożność anulowania, trudny test — odrzucone
- **Celery (O3)**: wymaga Redis/RabbitMQ — sprzeczne z filozofią zero-dependency-broker SYLION — odrzucone

## Referencje

- `mega_audit/upload_deep/` — głęboki audyt mechanizmu upload codebase
- `mega_audit/orchestrator_run_codebase_audit/` — analiza obecnej struktury orchestratora
- `mega_audit/pipeline_run_button/` — specyfikacja UX przycisku Run Audit
- `agents/orchestrator.py` — `run_codebase_audit()`
- `dashboard/app.py` — `POST /api/pipeline/run`, `GET /api/pipeline/status/{run_id}`
- ADR-0026 (CSRF) — wymagana walidacja tokenu dla `POST /api/pipeline/run`
- ADR-0033 (run_migrations_v3_to_v4) — migracja tabeli `pipeline_runs`
