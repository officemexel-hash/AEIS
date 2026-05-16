# FLOW-020 Project Start Lifecycle PASS12

Data: 2026-05-14

Zakres zamrożony: operator flow dla `/project-start`, `/projects`, `/projects/{project_id}` i `/projects/{project_id}/lifecycle`.

## Wynik

`PASS_2X`

- Evidence JSON: `evidence/json/project_start_lifecycle_pass12_2026-05-14T11-16-23-299Z.json`
- Runner: `tools/project_start_lifecycle_e2e.js`
- Screenshoty: 34 PNG w `evidence/screenshots/`
- Błędy konsoli: 0
- Page errors: 0
- Hard request failures: 0
- API `>=400`: 0

## PASS 1

Projekt: `proj_5f0706c51d42`

Scenariusz: ścieżka `idea`, szablon bazowy, projekt CRM/KSeF/RODO.

Kroki wykonane przez dashboard:

1. `/project-start`: wypełnienie nazwy, opisu, kontekstu klienta, terminu i budżetu.
2. `Pokaż analizę`: backend `/api/v1/project-start/projects/preview` zwrócił analizę.
3. `Utwórz projekt`: backend `/api/v1/project-start/projects/create` utworzył projekt.
4. Faza 16: acceptance `8/8`, hard blocks `0`.
5. `Zastosuj domyślne fazy 17`: cele zapisane, acceptance `7/7`, hard blocks `0`.
6. `Zastosuj domyślne fazy 18`: zakres zapisany, acceptance `8/8`, hard blocks `0`.
7. `Zastosuj domyślne fazy 19` + `Zatwierdź gotowość`: Rada przygotowana i zatwierdzona, acceptance `7/7`, hard blocks `0`.
8. `Diagnozuj przypadek problemowy`: edge diagnosis zwróciło case id.
9. `/projects`: projekt widoczny na liście i otwarty linkiem dashboardu.
10. `/projects/{id}`: szczegół projektu ma W18 terminal; komenda `/status` zwróciła output.
11. `/projects/{id}/lifecycle`: dashboard lifecycle, flow chart i quick actions widoczne.

## PASS 2

Projekt: `proj_4cd16bbad919`

Scenariusz: ścieżka `template`, inny wariant projektu - lokalny monitor kosztów AI.

Kroki wykonane przez dashboard: ten sam zestaw co PASS 1. Wszystkie fazy 16-19 zaliczone bez blokad:

- Faza 16: `8/8`
- Faza 17: `7/7`
- Faza 18: `8/8`
- Faza 19: `7/7`

## Ważna korekta harnessu

Pierwszy runner zgłosił fałszywe `project_detail_w18_missing`, bo sprawdzał detail page natychmiast po przejściu z `/projects`. Bezpośrednia reproba na tych samych projektach potwierdziła, że W18 istnieje i wszystkie API detail page zwracają `200`.

Korekta runnera:

- czeka na URL `/projects/{project_id}`;
- czeka na widoczny `[data-testid="project-w18-terminal"]`;
- klasyfikuje `net::ERR_ABORTED` przy szybkiej nawigacji jako telemetryczny abort, nie błąd produktu.

## Zasady freeze dla tego zakresu

Ten freeze obejmuje tylko:

- tworzenie projektu przez `/project-start`;
- fazy 16-19, ich defaults, approval i acceptance;
- widoczność projektu na `/projects`;
- otwarcie projektu z listy;
- W18 terminal na detail page i komendę `/status`;
- lifecycle dashboard i flow chart.

Nie obejmuje jeszcze:

- pełnego kreatora `/workspace-defaults` z każdą konfiguracją;
- uruchamiania pełnej Rady projektu do zamrożenia Księgi/Masterplanu;
- build authorization dla projektów startowych, bo to jest osobny zakres W18/Human Gate;
- produkcyjnego deployu albo zewnętrznych integracji.
