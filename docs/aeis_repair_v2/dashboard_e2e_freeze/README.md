# AEIS Dashboard E2E Freeze Campaign

Status: ACTIVE.

Cel: przetestowac AEIS przez dashboard/operator console w trybie czlowieka, zapisac kazdy blad, naprawic, wykonac dwa niezalezne retesty i zamrazac tylko flow z wynikiem `PASS_2`.

## Zasada 2x PASS => freeze

Flow moze dostac status `FROZEN` tylko gdy:

1. ma opis krokow operatora;
2. ma evidence z dashboardu: screenshot, log albo probe runtime;
3. nie ma otwartego bledu P0/P1/P2;
4. przechodzi `PASS_1`;
5. po odswiezeniu sesji albo restarcie relewantnego runtime przechodzi `PASS_2`;
6. instrukcja obslugi opisuje co operator widzi i co dzieje sie po kliknieciu.

## Statusy

- `UNTESTED`: nie bylo jeszcze runtime probe.
- `BROKEN`: flow pada albo dashboard pokazuje stan sprzeczny z backendem.
- `FIXING`: blad ma wlasciciela i patch w toku.
- `PASS_1`: pierwszy dashboard retest przeszedl.
- `FROZEN`: dwa przejscia z rzedu sa poprawne i manual jest zaktualizowany.
- `BLOCKED`: brakuje narzedzia, sekretu, procesu albo decyzji operatora.

## Artefakty kampanii

- `BUG_LEDGER.md`: rejestr bledow.
- `FREEZE_REGISTER.md`: rejestr flow i statusow freeze.
- `RUN_LOG.md`: chronologiczny dziennik przebiegu.
- `AEIS_OPERATOR_MANUAL_LATEST.md`: zywa instrukcja obslugi tworzona rownolegle przez subagenta dokumentacyjnego.
- `evidence/`: screenshoty, logi, OpenAPI dumps, probe JSON.

## Zasady testowania

1. Testy ida przez dashboard, o ile flow ma UI.
2. API-only probe jest dozwolone tylko do diagnozy albo dla surface bez UI.
3. Kazdy bug dostaje ID `DASH-E2E-###`.
4. Fix bez retestu nie zmienia statusu na PASS.
5. Freeze bez aktualizacji manuala jest niedozwolony.
6. Sekrety sa maskowane; evidence nie moze zawierac raw API keys ani credential payloads.
7. Zmiany w zamrozonym flow wymagaja nowego bug ID albo jawnego reopen.
