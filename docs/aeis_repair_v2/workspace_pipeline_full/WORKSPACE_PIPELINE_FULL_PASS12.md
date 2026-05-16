# FLOW-022 Workspace Pipeline Full PASS_2X

Data: 2026-05-14  
Surface: `/workspace`  
Zakres: submit pomyslu do pipeline, wybor runu, wykonanie, weryfikacja krokow, zakladki `Pipeline`, `Kod`, `Wynik`.

## Wynik

Status: `PASS_2X`

Dowod JSON: `docs/aeis_repair_v2/workspace_pipeline_full/evidence/json/workspace_pipeline_full_pass12_2026-05-14T12-39-30-039Z.json`

| Pass | Run ID | Final status | Steps | Output chars | Screenshots |
|---|---|---:|---:|---:|---:|
| PASS1 | `8610fd01d3404434a709917c467f1fa6` | `complete` | 5 | 20533 | 7 |
| PASS2 | `37b4b93bf0924a1e97038f17aca005f1` | `complete` | 5 | 21767 | 7 |

Kontrola negatywna:

- `issueCount=0`
- `hardEventCount=0`
- `apiErrorCount=0`
- oba runy mialy `quality_gate=passed`
- oba runy mialy niepuste wyniki krokow
- zakladka `Kod` pokazala dane z `step.result`
- zakladka `Wynik` pokazala log wykonania ze statusem kroku

## Sciezka operatora

1. Otworzono `/workspace`.
2. Wpisano unikalny pomysl w polu `Wyslij pomysl do uruchomienia w pipeline...`.
3. Kliknieto `Wyslij`.
4. Zweryfikowano `POST /api/v1/pipeline/ideas`: run utworzony ze statusem `pending`.
5. Wybrano nowy run z listy.
6. Kliknieto `Wykonaj`.
7. Zweryfikowano `POST /api/v1/pipeline/runs/{run_id}/execute`.
8. Polling API potwierdzil `GET /api/v1/pipeline/runs/{run_id}` -> `complete`.
9. `GET /api/v1/pipeline/runs/{run_id}/steps` zwrocil 5 krokow i niepuste wyniki.
10. Zakladka `Pipeline` pokazala aktualny pomysl i finalny status.
11. Zakladka `Kod` pokazala rezultat kroku.
12. Zakladka `Wynik` pokazala log wykonania.

## Naprawione bledy

- `DASH-E2E-018`: zakladka `Kod` ignorowala `step.result`, wiec po udanym pipeline mogla pokazywac placeholder zamiast wyniku.
- `DASH-E2E-019`: zakladka `Wynik` opierala opis logu na `phase/step_type`, podczas gdy backend zwraca `name/step_id`; status byl widoczny tylko jako ikona.
- `DASH-E2E-020`: guard raportu jakosci ocenial finalny raport jak pelny artefakt implementacyjny i mogl fałszywie blokowac pipeline.
- `DASH-E2E-021`: guard URL traktowal lokalny `http://localhost:3000` jako zewnetrzny endpoint oraz email fixture `*@example.com` jak endpoint `example.com`.
- `DASH-E2E-022`: harness sprawdzal slowo `failed` globalnie na stronie `/workspace`, przez co historyczne nieudane runy mogly tworzyc falszywy fail aktualnego runu.

## Zasady zamrozenia

Ten zakres mozna uznac za zamrozony tylko dla `/workspace` pipeline submit/execute i zakladek `Pipeline`, `Kod`, `Wynik`.

Nie rozszerza to freeze na osobne tryby pracy workspace poza testowana sciezka, ani na jakosc merytoryczna losowego modelowego artefaktu poza egzekwowalnymi guardami.

Warunki utrzymania freeze:

- kazda zmiana w `/workspace` musi zachowac `POST /ideas`, `POST /execute`, `GET /run`, `GET /steps`;
- `complete` jest jedynym statusem dopuszczonym do zamrozenia;
- `failed`, `cancelled`, pusty output kroku albo `quality_gate != passed` natychmiast cofaja scope do naprawy;
- zakladki `Kod` i `Wynik` musza korzystac z rzeczywistego `step.result`, `step.output` albo `result.output`, nie z placeholderow;
- lokalne adresy runtime `localhost` i `127.0.0.1` sa dozwolone, ale prawdziwe endpointy placeholderowe `example.com` dalej blokuja artefakt.

## Screenshoty

- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_01_workspace_loaded_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_02_idea_filled_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_03_run_pending_selected_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_04_execute_clicked_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_05_run_complete_selected_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_06_code_tab_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_07_output_tab_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_01_workspace_loaded_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_02_idea_filled_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_03_run_pending_selected_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_04_execute_clicked_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_05_run_complete_selected_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_06_code_tab_2026-05-14T12-39-30-039Z.png`
- `docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass2_07_output_tab_2026-05-14T12-39-30-039Z.png`
