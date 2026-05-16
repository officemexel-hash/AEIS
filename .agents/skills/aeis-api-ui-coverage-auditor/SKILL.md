---
name: "aeis-api-ui-coverage-auditor"
description: "Buduje mape pokrycia API i UI dla AEIS. Laczy frontend route pages, klienta API, probe runtime i wskazuje surface live, shell-only albo API-only."
---

# AEIS API/UI Coverage Auditor

Uzyj tego skillu przy tworzeniu:

- `docs/codex_system_audit/CODEX_AEIS_API_UI_COVERAGE_MAP.md`
- sekcji coverage w `CODEX_AEIS_FUNCTIONAL_AUDIT.md`
- sekcji surface drift w `CODEX_AEIS_CANON_VS_REALITY.md`

## Cel

Ustalic:

- ktore strony operatora istnieja w frontendzie
- ktore maja odpowiadajace endpointy API
- ktore sa potwierdzone runtime
- ktore sa tylko shellami lub skeletonami
- gdzie wystepuje drift miedzy klientem API a backendem

## Kroki

1. Uruchom skrypt `scripts/extract_api_ui_coverage.py`.
2. Zweryfikuj kluczowe powierzchnie probe runtime:
   - `workspace`
   - `funding`
   - `skills`
   - `governance`
   - wybrane lab surfaces
3. Zapisz wynik jako mape:
   - `LIVE_VERIFIED`
   - `PARTIAL`
   - `API_ONLY`
   - `UI_ONLY`
   - `DOC_DRIFT`

## Dane wejsciowe

- `src/sylion-frontend/src/app/(app)`
- `src/sylion-frontend/src/lib/api/client.ts`
- `src/sylion-pipeline/sylion/api/router.py`
- probe runtime HTTP

## Wynik

Mapa ma odpowiadac na pytania:

- czy dany ekran ma backend
- czy backend jest zywy
- czy klient API wskazuje na poprawne endpointy
- czy surface nalezy do glownego AEIS flow czy do subsystemu ubocznego

