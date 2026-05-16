# ADR-0025: Końcowa pętla weryfikacyjna v5.9.1 — grep-assert po każdym fixie

**Status:** Accepted
**Data:** 2026-04-19
**Wersja:** 5.9.1
**Autor:** SYLION AI Council (debug-loop-breaker monitor uzbrojony)

## Kontekst

Po zakończeniu Fazy 3 re-audytu v5.9.0 → v5.9.1 (22 klastry fixów A–V, ~200+ subagentów) wstępny UAT (Cluster V) zgłosił 3 P0 blocker-y:

1. **BUG-V-01** — `install.sh` miał wywoływać `python -m app.db.init_db` (moduł nieistniejący), raport Cluster C twierdził że naprawiony.
2. **BUG-V-08** — seed w `db.py:1349` nadal miał `("pixel8", "Pixel 8", ...)`, raport Cluster A twierdził PIX-1 zaaplikowany.
3. **BUG-V-09** — 5 z 6 nowych endpointów (Q/R/T) miało zwracać 404.

Powierzchowna weryfikacja grepem ujawniła jednak, że:

- Raport Cluster V używał **snapshotu sprzed merge'a Cluster U** — poprawki realnie były w plikach.
- Jedyne faktycznie pozostałe artefakty sprzed v5.9.1 to banner w `install.sh` (`v5.9.0`), komentarz `DEVICE_PIXEL_SERIAL` w `db.py:1185`, pole `"version": "5.9.0"` w `MANIFEST.json`, brak walidatora modelu `Pixel 9` (zdefiniowane tylko enumy `WRONG_MODEL`/`UNKNOWN_MODEL`, brak metody `validate_pixel_model`) oraz desynchronizacja `release_root/sylion-pipeline/` (stary snapshot).

Wzorzec typu **same-bug-re-report** (subagent raportuje fix bez weryfikacji rezultatu) został zarejestrowany przez debug-loop-breaker jako ryzyko Regression-Bounce iteracji #2.

## Decyzja

Wprowadzamy **regułę grep-assert-po-każdym-fixie** jako obowiązkowy krok POST-TASK dla wszystkich klastrów fixów generowanych przez rady 4-modelowe:

1. Każdy klaster fixów musi kończyć się listą asercji grep postaci:
   ```bash
   grep -c "<expected_new_string>" <file>   # must be > 0
   grep -c "<removed_old_string>" <file>    # must be 0
   ```
2. Weryfikacja wykonywana jest przez agent nadrzędny (sylion-orchestrator), nie przez samego subagenta-wykonawcę.
3. Asercje zapisywane są w `task_state.json` pod kluczem `postfix_assertions`.
4. Jeśli asercja zwraca nieoczekiwaną wartość → automatyczny re-fix + HumanGate po 2. iteracji.
5. Dla zmian wielokrotnych (np. banner v5.9.0 → v5.9.1 w wielu miejscach) asercja musi pokryć **wszystkie** wystąpienia, nie tylko pierwsze.

## Konsekwencje

### Pozytywne
- Zero zaufania do raportów subagentów — każde "done" wymaga weryfikowalnego dowodu.
- Detekcja desynchronizacji tree (`sylion-pipeline/` vs `release_root/sylion-pipeline/`) przed buildem zip.
- Debug-loop-breaker ma konkretne sygnały do wejścia — nie tylko liczba iteracji, ale też diff realnego stanu vs raportów.

### Negatywne
- Dodaje ~5-10% narzutu czasu na każdy klaster (grep-asserty).
- Wymaga dyscypliny w formułowaniu asercji — niewyspecjalizowany grep może fałszywie uspokoić.

### Neutralne
- Wprowadza obowiązek `cp -a sylion-pipeline release_root/sylion-pipeline` jako ostatni krok przed buildem zip.
- Wydziela `__pycache__`, `*.pyc`, `*.db*`, `SETUP_TOKEN.txt` z release tree.

## Weryfikacja końcowa v5.9.1

Uruchomiona dokładnie 2026-04-19, 150/150 testów pytest PASS (4 skip), uvicorn start OK na port 8821 z `HOME=/tmp/uat_runtime2`:

| Endpoint | HTTP | Oczekiwane |
|---|---|---|
| `GET /api/health` | 200, `version:5.9.1`, `db_ok:true` | ✅ |
| `GET /api/metrics` | 200 (Prometheus) | ✅ |
| `GET /api/observability/costs` | 401 (auth required) | ✅ |
| `GET /api/auth/me/export` | 401 | ✅ |
| `POST /api/auth/logout-all` → GET | 405 | ✅ (tylko POST) |
| `DELETE /api/auth/me/data` | 422 (wymaga password) | ✅ |
| `GET /api/settings/api-keys` | 401 | ✅ |

Grep-asercje:
- `grep -c "SYLION v5.9.1" sylion-pipeline/install.sh` → `2` ✅
- `grep -c "SYLION v5.9.0" sylion-pipeline/install.sh` → `0` ✅
- `grep -c '("pixel9", "Pixel 9"' sylion-pipeline/dashboard/db.py` → `1` ✅
- `grep -c '("pixel8", "Pixel 8"' sylion-pipeline/dashboard/db.py` → `0` ✅
- `grep -c "PIXEL_9_FAMILY" sylion-pipeline/device_harness.py` → `4` ✅
- `grep -c "def validate_pixel_model" sylion-pipeline/device_harness.py` → `1` ✅
- `grep -c '"version": "5.9.1"' release_root/MANIFEST.json` → `1` ✅

## Powiązane

- ADR-0015 Pixel 9 default device (rozszerzone o PIXEL_9_FAMILY tuple)
- ADR-0019 install script fix (banner update w tym ADR)
- Skill: `debug-loop-breaker` — Regression-Bounce pattern detection
- Skill: `skill-checklist-enforcer` — POST-TASK grep-assert rule
