# CODEX Deep Audit - VPS, Environments, Runtime

Data: 2026-05-02
Zakres: audyt runtime, API, dashboardu oraz ścieżek związanych z VPS, środowiskami, Human Gate, Council, Memory/Skills i modułami projektu AEIS.

## Wniosek główny

W audycie potwierdziłem realną lukę operatorską: dashboard i backend nie dawały operatorowi praktycznej kontroli nad liczbą środowisk i liczbą VPS na środowisko w flow Hetzner/deploy. W UI widoczne były wartości stałe, a backendowy request Hetznera nie miał pól skalowania.

Luka została naprawiona. Operator może teraz ustawić:

- `Liczba środowisk` w panelu `Deploy`;
- `VPS na środowisko` w panelu `Deploy`;
- `Liczba środowisk` przy dodawaniu środowisk w panelu `Environments`;
- limit bezpieczeństwa: maksymalnie 10 VPS w jednym żądaniu provisioningowym.

## Stan runtime

Backend po restarcie działa:

- URL: `http://127.0.0.1:8010`
- status: `ok`
- version: `3.5.0`
- modules: `138`
- endpoints: `1947`
- db_mode: `sqlite`
- event_mode: `sqlite`

OpenAPI potwierdza nowe pola requestu `HetznerProvisionRequest`:

- `environment_count`, integer, min 1, max 10, default 1
- `vps_per_environment`, integer, min 1, max 10, default 1

Backend blokuje zbyt dużą skalę przed kontaktem z providerem:

- request testowy: `environment_count=4`, `vps_per_environment=3`
- total: 12 VPS
- status: `409`
- komunikat: `Hetzner scale is capped at 10 VPS per provisioning request...`

Nie utworzyłem nowego VPS i nie wygenerowałem kosztu w tym audycie.

## Poprawki wdrożone

### Backend deploy

Plik: `src/sylion-pipeline/sylion/api/deploy_routes.py`

Dodano:

- pola `environment_count` i `vps_per_environment`;
- walidację `_validate_hetzner_scale`;
- blokadę powyżej 10 VPS na jedno żądanie;
- generowanie grupy wdrożenia;
- osobne `deployment_id` dla pary środowisko/VPS;
- metadane `deployment_group`, `environment_index`, `server_index`, `total_servers`;
- cleanup utworzonych serwerów przy błędzie w trakcie provisioning loop.

### Dashboard Deploy

Plik: `src/sylion-frontend/src/app/(app)/deploy/page.tsx`

Dodano:

- input `Liczba środowisk`;
- input `VPS na środowisko`;
- przelicznik `Planowana skala: X środowisk x Y VPS = Z VPS`;
- ostrzeżenie przy przekroczeniu limitu;
- blokadę przycisku `Utwórz VPS i wdróż artefakt` przy `Z > 10`;
- prezentację metadanych grupy wdrożenia na kartach wdrożeń.

### Dashboard Environments

Plik: `src/sylion-frontend/src/app/(app)/environments/page.tsx`

Dodano:

- pole `Liczba środowisk`;
- tworzenie środowisk batchowo;
- nazwy `base-01`, `base-02`, ... przy liczbie większej niż 1;
- metadane `batch_size` i `batch_index`.

### Dodatkowe naprawy wykryte w trakcie audytu

Naprawione zostały też błędy, które blokowały pełniejszą kolekcję testów i runtime:

- kompatybilność `LifecycleGateEnforcer`;
- polityka runtime modeli przy głosowaniu Council;
- synchroniczne karty advisor kickoff dla projektów;
- eksporty legacy w `sylion.core`;
- bezpieczne metryki Prometheus bez duplikacji rejestracji;
- fallback kosztowy dla nieznanych/nowszych modeli;
- kompatybilność `hot_swap`, `profile_swap`, `model_registry`, `decision_boundaries`;
- obsługa HTML/CSS/JS artifactów w `decomposition_engine`.

## Test dashboardu jak operator

Test wykonany przez in-app browser, na realnym dashboardzie.

### `/deploy`

Przebieg:

1. Otworzono `http://127.0.0.1:3000/deploy`.
2. Wpisano `3` w `Liczba środowisk`.
3. Wpisano `2` w `VPS na środowisko`.
4. Dashboard pokazał `Planowana skala: 3 środowisk x 2 VPS = 6 VPS`.
5. Wpisano `4` i `3`.
6. Dashboard pokazał `Planowana skala: 4 środowisk x 3 VPS = 12 VPS`.
7. Dashboard pokazał ostrzeżenie limitu.
8. Przycisk `Utwórz VPS i wdróż artefakt` był zablokowany.

Dowód:

- `docs/codex_system_audit/screenshots/deploy_scale_limit_20260502.png`

### `/environments`

Przebieg:

1. Otworzono `http://127.0.0.1:3000/environments`.
2. Odnaleziono formularz `Dodaj środowisko`.
3. Wpisano `3` w `Liczba środowisk`.
4. Przycisk `Zapisz środowisko` pozostał aktywny.
5. Nie kliknięto zapisu, żeby nie zaśmiecać lokalnego stanu testowego.

Dowód:

- `docs/codex_system_audit/screenshots/environments_scale_20260502.png`

## Testy automatyczne

Wykonane po poprawkach:

- `python -m pytest src\sylion-pipeline\tests\test_environment_catalog_routes.py src\sylion-pipeline\tests\test_deploy_routes.py src\sylion-pipeline\tests\test_deployment_orchestrator.py src\sylion-pipeline\tests\test_projects_routes.py -q`
- wynik: `143 passed`, `6 warnings`

Wykonane wcześniej w tej iteracji:

- krytyczny zestaw runtime/governance/deploy/workers: `357 passed`
- zestaw napraw import/kompatybilności: `174 passed`
- frontend: `npx tsc --noEmit` przeszedł
- backend compile: `python -m compileall` przeszedł

Pełna kolekcja testów:

- `python -m pytest src\sylion-pipeline\tests --collect-only -q`
- wynik: `14243 tests collected`
- brak błędów kolekcji

Pełne wykonanie całej suite nie zostało doprowadzone do końca w tej iteracji, bo przekracza czas praktycznego testu interaktywnego. Wcześniejsza próba pełnego runu przekroczyła 10 minut. To nie jest błąd kolekcji, tylko rozmiar suite.

## Audyt API/UI

Ostatni snapshot inventory/API/UI:

- backend packages: `37`
- backend modules: `744`
- API routes: `126`
- runtime OpenAPI paths: `1599`
- OpenAPI schemas: `422`
- frontend routes: `127`
- repo skills: `29`
- entrypoints: `8`

Wyniki zapisane:

- `docs/codex_system_audit/_inventory_snapshot.json`
- `docs/codex_system_audit/_api_ui_coverage_snapshot.json`

## Status względem kanonu AEIS

### Zgodne / poprawione

- W5 Runtime/Environment: operator ma realną regulację skali środowisk i VPS.
- W7 Human Gate/Governance: operacje finansowe i zewnętrzne nadal są blokowane checkboxem oraz limitem backendowym.
- W13/W16 Plan/Execution: wdrożenie może tworzyć grupę kilku instancji i śledzić je jako oddzielne deploymenty.
- W18 Operator Console: dashboard pokazuje decyzję skali wprost, a nie jako stałą wartość.

### Nadal do obserwacji

- W repo jest bardzo duży dirty working tree z wieloma zmianami wcześniejszymi i wygenerowanymi plikami. Nie odwracałem ich, żeby nie skasować cudzej pracy.
- Backend emituje ostrzeżenia o zduplikowanych Operation ID w OpenAPI.
- Security package nadal importuje kilka modułów oznaczonych jako deprecated (`hardened_audit`, `secret_provider`, `profile_swap`, `security_audit`, `audit_sink`, `key_vault`).
- Pełna suite 14k testów wymaga dłuższego runu batchowego poza krótką sesją interaktywną.

## Sekrety i koszty

W raporcie nie zapisuję żadnych przekazanych sekretów.

W tej iteracji:

- nie utworzono nowego VPS;
- nie wykonano deploymentu na Hetzner;
- nie wysłano kluczy API do zewnętrznych serwisów;
- nie wykonano akcji kosztowej.

## Ocena końcowa

Problem wskazany przez operatora był realny. Panel deploy miał stałą skalę, a backend nie miał kontraktu skali. Po poprawkach operator ma regulację liczby VPS i środowisk, UI pokazuje planowaną skalę, backend przyjmuje pola skali, a limit 10 VPS jest egzekwowany zarówno w dashboardzie, jak i na API.
