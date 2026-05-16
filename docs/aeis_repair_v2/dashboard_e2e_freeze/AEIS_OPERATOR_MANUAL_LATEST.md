# AEIS Operator Manual Latest - dashboard E2E freeze

**Wersja robocza:** 2026-05-13
**Cel:** zywa instrukcja operatorska AEIS pod kampanie dashboard E2E freeze.
**Zakres:** operator console Next.js, unified backend, workspace/project lifecycle, governance, execution, memory, skills, funding, audit/evidence, mobile/operator, konfiguracja i rollback.
**Zasada nadrzedna:** ten dokument nie potwierdza dzialania funkcji bez runtime evidence z freeze. Kazda funkcja ma status jawnie przypisany do jednego z czterech stanow: `ZWERYFIKOWANE`, `CZESCIOWE`, `BROKEN`, `NIEPRZETESTOWANE`.

## 1. Jak uzywac tej instrukcji

Ta instrukcja jest szkieletem, ktory ma byc uzupelniany podczas dwoch przebiegow E2E dashboard freeze. Operator lub audytor powinien dopisywac tylko to, co zostalo realnie zobaczone w uruchomionym systemie: adres ekranu, akcje klikniecia, wynik UI, wynik API, log lub plik evidence.

Nie wolno zmieniac statusu na `ZWERYFIKOWANE` tylko dlatego, ze ekran istnieje w kodzie, endpoint jest w kliencie API albo starsza dokumentacja opisuje taka funkcje. Status `ZWERYFIKOWANE` wymaga obserwacji runtime w aktualnej kampanii freeze.

Kazdy scenariusz, funkcja i flow ma byc opisany w tym formacie. Jezeli w tabeli ponizej jest tylko krotki wiersz z trasa albo akcja, ten wiersz jest indeksem do pelnej karty funkcji/flow, ktora glowny agent uzupelni w trakcie testow.

| Pole | Co wpisac |
|---|---|
| Status | `ZWERYFIKOWANE`, `CZESCIOWE`, `BROKEN` albo `NIEPRZETESTOWANE` |
| PASS | `PASS 1`, `PASS 2`, `2x PASS`, `FAIL`, `BLOCKED` |
| Trasa UI | np. `/workspace`, `/funding`, `/human-gate` |
| Nazwa funkcji/flow | np. `Workspace kickoff`, `Funding PDF export`, `Human Gate approve` |
| Screenshot desktop | Relatywna sciezka do PNG/JPG w evidence albo `TBD` |
| Screenshot mobile | Relatywna sciezka do PNG/JPG w evidence albo `N/D`, jezeli flow nie ma sensownego wariantu mobile |
| Opis ekranu | Co to jest za ekran, do czego sluzy i jakie dane powinien pokazywac |
| Co operator widzi | Konkretne naglowki, liczniki, panele, tabele, formularze, empty states, loading/error states |
| Wejscie operatora | dokladny przycisk, zakladka, formularz, filtr lub link |
| Kazdy klik/akcja | Sekwencja klikniec, wpisow formularza i nawigacji, krok po kroku |
| Oczekiwany widok po kliknieciu | tekst, panel, tabela, modal, toast, zmiana URL, stan loading/error |
| Co dzieje sie po kliknieciu | Skutek UI, request API, zapis, audit/evidence, zmiana stanu projektu albo brak skutku |
| Scenariusz pozytywny | Co musi sie stac, zeby uznac flow za PASS |
| Scenariusz bledny | Jak wyglada blad, timeout, brak danych, sprzeczny stan albo brak uprawnien |
| Bug IDs | Powiazane ID bugow/taskow, np. `FIX-...`, `R3...`, `BUG-...`, albo `TBD` |
| Evidence path | Sciezka do katalogu/pliku evidence uzupelniana przez glownego agenta |
| Dowod runtime | screenshot, JSON, log, test id, komenda, timestamp |
| Ryzyko | co moze popsuc projekt, decyzje, koszty, sekrety lub evidence |
| Rollback/przerwanie | jak bezpiecznie wyjsc, anulowac albo zatrzymac operacje |

## 1.1. Karta funkcji/flow - szablon do kopiowania

Ponizszy blok jest obowiazkowy dla kazdej istotnej funkcji i kazdego flow freeze. Screenshotow nie generuje ten dokument; glowne testy uzupelniaja tylko sciezki do evidence.

```text
### [Nazwa funkcji lub flow]

Status freeze: NIEPRZETESTOWANE
PASS: TBD
Trasa UI:
Powiazane API:
Powiazane bug IDs:
Evidence path:
Screenshot desktop:
Screenshot mobile: N/D

Opis ekranu:
- TBD

Co operator widzi:
- TBD

Kliki/akcje operatora:
| Krok | Klik/akcja | Dane wejsciowe | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|---|
| 1 | TBD | TBD | TBD | TBD | TBD |

Scenariusz pozytywny:
- TBD

Scenariusze bledne:
| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |

Rollback / bezpieczne przerwanie:
- TBD

Uwagi freeze:
- TBD
```

## 2. Slownik statusow freeze

| Status | Znaczenie | Minimalny dowod |
|---|---|---|
| `ZWERYFIKOWANE` | Funkcja przeszla aktualny scenariusz E2E i wynik jest zgodny z instrukcja. | Screenshot lub zapis testu + odpowiedz API/log/evidence, najlepiej w dwoch przebiegach. |
| `CZESCIOWE` | Ekran lub API istnieje, ale flow nie jest domkniety, brakuje jednego kroku, integracji albo potwierdzenia skutku. | Dowod na dzialajacy fragment oraz jawny opis luki. |
| `BROKEN` | Klikniecie, endpoint, zapis, odswiezenie albo widok konczy sie bledem lub sprzecznym stanem. | Blad UI/API/log, screenshot i krok reprodukcji. |
| `NIEPRZETESTOWANE` | Brak aktualnego runtime evidence w kampanii freeze. | Nie wymagany; to status domyslny. |

## 3. Freeze 2x PASS - rejestr roboczy

Status globalny tej instrukcji: `CZESCIOWE`. Obecne dowody daja `2x PASS` dla startu runtime, renderowania tras dashboardu, Skills, flow W18 project terminal freeze/build (`DASH-E2E-005`), execution-start Phase 32/33 W18 router (`DASH-E2E-006`), execution-start live worker smoke start/stop (`DASH-E2E-008`), execution-start phases 34-41 (`DASH-E2E-009`) oraz execution-start dispatch control (`DASH-E2E-010`). Nie daja jeszcze `FROZEN` dla calego systemu, bo rejestr wymaga pelnego 2x PASS akcji, skutku API i instrukcji operatora dla kazdego glownego flow.

| Obszar | PASS 1 | PASS 2 | Status freeze | Screenshot desktop | Screenshot mobile | Evidence path | Bug IDs |
|---|---|---|---|---|---|---|---|
| Start backendu i health | PASS_1 | PASS_2 | 2X_PASS | evidence/screenshots/health_desktop.png | N/D | evidence/runtime_baseline/backend_health_8010.json; evidence/runtime_baseline/backend_restart_retest_d004.json | - |
| Start frontend operator console | PASS_1 | PASS_2 | 2X_PASS | evidence/screenshots/root_launch_after_pass1.png | evidence/screenshots/root_mobile.png | evidence/runtime_baseline/frontend_root_3001.status.txt; evidence/runtime_baseline/frontend_start_retest2_clean.json | DASH-E2E-001 2X_PASS |
| Offline guard / backend unavailable | NIEPRZETESTOWANE | NIEPRZETESTOWANE | NIEPRZETESTOWANE | TBD | TBD | TBD | TBD |
| Workspace kickoff | PASS_1 tabs only | PASS_2 tabs only | PARTIAL_2X_PASS | evidence/screenshots/workspace_pass2_tab_wynik.png | evidence/screenshots/workspace_mobile.png | evidence/runtime_baseline/workspace_tabs_pass2.json | Kickoff/project lifecycle pending |
| Project lifecycle | PASS_1 route only | NIEPRZETESTOWANE | CZESCIOWE | evidence/screenshots/projects_desktop.png | TBD | evidence/runtime_baseline/dashboard_route_probe_pass1.md | TBD |
| Human Gate / approvals | PASS_1 | PASS_2 | PARTIAL_2X_PASS | evidence/screenshots/human_gate_pass2_approve_after.png | evidence/screenshots/human-gate_mobile.png | evidence/runtime_baseline/human_gate_pass2_approve_reject.json | Model Council action flow pending |
| W18 project terminal freeze/build | PASS_1 | PASS_2 | 2X_PASS | ../w18_router_repair/evidence/screenshots/pass2_authorize_build_project_f3e237d2a95b_2026-05-13T22-03-46-999Z.png | N/D | ../w18_router_repair/evidence/json/w18_router_dashboard_pass12_reconstructed_2026-05-13.json | DASH-E2E-005 2X_PASS |
| Model Council | NIEPRZETESTOWANE | NIEPRZETESTOWANE | NIEPRZETESTOWANE | TBD | TBD | TBD | TBD |
| Execution start/stop | PASS_1 Phase 32/33 + live worker start/stop + dispatch control | PASS_2 Phase 32/33 + live worker start/stop + dispatch control | PARTIAL_2X_PASS | ../execution_dispatch_control/evidence/screenshots/2026-05-14T09-58-40-542Z_pass2_cancel.png | ../execution_dispatch_control/evidence/screenshots/2026-05-14T09-58-40-542Z_mobile_final_dashboard.png | ../execution_start_router_repair/evidence/json/execution_start_dashboard_pass12_2026-05-13T22-23-31-684Z.json; ../execution_live_workers/evidence/json/live_workers_dashboard_pass12_2026-05-13T22-40-42-350Z.json; ../execution_dispatch_control/evidence/json/execution_dispatch_control_pass12_2026-05-14T09-58-40-542Z.json | DASH-E2E-006 2X_PASS; DASH-E2E-008 2X_PASS; DASH-E2E-010 2X_PASS |
| Memory | PASS_1 route only | PASS_2 route only | PARTIAL_ROUTE_2X | evidence/screenshots/memory_desktop_pass2_after_d004.png | TBD | evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.json | Search/evidence write pending |
| Skills | PASS_1 full interaction + 2x execution retest | PASS_2 full create/execute/signal | 2X_PASS | evidence/screenshots/skills_full_pass2_signal_after.png | evidence/screenshots/skills_mobile.png | evidence/runtime_baseline/skills_full_pass2_create_execute_signal.json | DASH-E2E-003 2X_PASS |
| Funding | PASS_1 tabs + 2x reports chart retest | PASS_2 tabs/reports | PARTIAL_2X_PASS | evidence/screenshots/funding_full_pass2_tab_raporty.png | evidence/screenshots/funding_mobile.png | evidence/runtime_baseline/funding_tabs_reports_pass2.json | DASH-E2E-002 2X_PASS; writes/exports pending |
| Audit/replay/evidence | PASS_1 route only | PASS_2 route only | PARTIAL_ROUTE_2X | evidence/screenshots/audit_desktop_pass2_after_d004.png | TBD | evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.json | Event lookup/replay verification pending |
| Mobile/operator | PASS_1 queue nav | PASS_2 queue nav mobile viewport | PARTIAL_2X_PASS | evidence/screenshots/operator_mobile_queue_after_click_pass1.png | evidence/screenshots/operator_mobile_pass2_queue_mobile.png | evidence/runtime_baseline/operator_mobile_queue_pass2.json | Mobile approve/reject/device binding pending |
| Settings/keys/secrets | PASS_1 tabs only | PASS_2 readonly tabs/secrets | PARTIAL_2X_PASS | evidence/screenshots/settings_pass2_tab_czlonkowie.png | evidence/screenshots/settings_mobile.png | evidence/runtime_baseline/settings_tabs_secrets_pass2.json | Dummy secret add/validate/rotate pending |
| Observability/readiness | PASS_1 route only | PASS_2 route only | PARTIAL_ROUTE_2X | evidence/screenshots/observability_desktop_pass2_after_d004.png | evidence/screenshots/observability_mobile_pass2_after_d004.png | evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.json | Metrics drilldown/readiness actions pending |
| Rollback / bezpieczne przerwanie | NIEPRZETESTOWANE | NIEPRZETESTOWANE | NIEPRZETESTOWANE | TBD | TBD | TBD | TBD |

## 4. Warstwy systemu - mapa operatorska

Wstepna mapa na podstawie dokumentacji i tras frontendowych. To nie jest potwierdzenie runtime.

| Warstwa | Glowne trasy UI | Glowne API z klienta | Status freeze |
|---|---|---|---|
| API aggregation / health | `/health`, `/runtime`, `/observability` | `/health`, `/api/v1/runtime/truth` | NIEPRZETESTOWANE |
| Workspace / planning | `/workspace`, `/workspace-defaults`, `/planning` | `/api/v1/workspace/*`, `/api/v1/workspace-defaults/*` | NIEPRZETESTOWANE |
| Project registry / lifecycle | `/projects`, `/projects/[projectId]`, `/projects/[projectId]/lifecycle`, `/lifecycle` | project/workspace routes, lifecycle routes | NIEPRZETESTOWANE |
| Governance / Human Gate | `/governance`, `/gates`, `/human-gate`, `/model-council`, `/decisions` | `/api/v1/governance/*`, `/api/v1/workspace/council/*` | NIEPRZETESTOWANE |
| Execution | `/execution-start`, `/pipeline`, `/orchestration`, `/workers`, `/terminal` | `/api/v1/execution-*`, `/api/v1/pipeline/*` | NIEPRZETESTOWANE |
| Memory | `/memory`, `/source-of-truth`, `/ontology` | `/api/v1/memory/*` | NIEPRZETESTOWANE |
| Skills | `/skills` | `/api/v1/skills/*` | NIEPRZETESTOWANE |
| Funding | `/funding`, `/costs`, `/budget`, `/cost-guard` | `/api/v1/funding/*`, `/api/v1/efficiency/cost/*` | NIEPRZETESTOWANE |
| Audit / replay / evidence | `/audit`, `/audit-trail`, `/evidence`, `/evidence-spine`, `/terminal/replay` | `/api/v1/core/evidence`, audit and replay routes | NIEPRZETESTOWANE |
| Mobile/operator | `/operator-mobile`, `/operator-mobile/queue`, `/operator-mobile/devices`, `/mobile` | `/mobile/v1` gateway wg dokumentacji | NIEPRZETESTOWANE |
| Settings / secrets | `/settings`, `/settings/profile`, `/settings/advisor`, `/secrets`, `/ai-models` | provider catalog, key/secrets/settings routes | NIEPRZETESTOWANE |

## 5. Konfiguracja startowa freeze

Status: `NIEPRZETESTOWANE`.

| Element | Wartosc kanoniczna do sprawdzenia | Co operator powinien zobaczyc |
|---|---|---|
| Backend | `uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010` | `/health` zwraca status OK; UI nie pokazuje offline guard. |
| Frontend | Next.js operator console, kanonicznie `127.0.0.1:3001` | Shell z sidebar, top command bar, FirstRunBanner jezeli onboarding nie jest domkniety. |
| API base | `NEXT_PUBLIC_API_URL` albo proxy Next.js | Wywolania z UI trafiaja w ten sam backend. |
| Runtime DB | `SYLION_DB_PATH`, domyslnie `sylion_aeis.db` | Operacje zapisu pozostaja w aktywnej bazie runtime. |
| Legacy dashboard | Nie uruchamiac jako aktywnego runtime. | Brak instrukcji `python dashboard/start.py` w aktywnym flow. |

Procedura do uzupelnienia:

1. Uruchom backend.
2. Otworz health endpoint.
3. Uruchom frontend.
4. Otworz operator console.
5. Zapisz screenshot startowy, health JSON i logi startowe.
6. Oznacz PASS 1 lub FAIL.
7. Powtorz jako PASS 2 po restarcie albo po zmianie testowanej przez glownego agenta.

## 6. Dashboard / operator console

Status: `NIEPRZETESTOWANE`.

Ekrany do sprawdzenia:

| Trasa | Co kliknac | Co operator powinien zobaczyc po kliknieciu | Status |
|---|---|---|---|
| `/dashboard/operator-monitor` | Wejscie z sidebar/linku operator monitor | Naglowek operator monitor, headline stats, runtime topology/config, link do lifecycle dashboard. | NIEPRZETESTOWANE |
| `/overview` | Wejscie z nawigacji | Podsumowanie systemu bez czerwonych bledow renderowania. | NIEPRZETESTOWANE |
| `/runtime` | Wejscie z nawigacji | Stan runtime/truth plane albo jawny blad backendu. | NIEPRZETESTOWANE |
| `/health` | Wejscie z nawigacji | Status ogolny, moduly, endpointy, tryb DB. | NIEPRZETESTOWANE |
| `/observability` | Wejscie z nawigacji | Widok observability/readiness. | NIEPRZETESTOWANE |

Checklist klikniec:

| Klikniecie | Oczekiwany skutek | Dowod | Status |
|---|---|---|---|
| Zwin/rozwin sidebar | Layout zmienia szerokosc bez zakrywania tresci. | TBD | NIEPRZETESTOWANE |
| Top command bar | Polecenia lub wyszukiwarka otwieraja oczekiwany panel. | TBD | NIEPRZETESTOWANE |
| Advisor bubble | Otwiera panel/advisor state albo pokazuje kontrolowany empty/error state. | TBD | NIEPRZETESTOWANE |
| Runtime config save | Zapis pokazuje toast/sukces albo kontrolowany blad. | TBD | NIEPRZETESTOWANE |
| Live spawn start/stop | Operator widzi efekt, stan i mozliwosc stop. | TBD | NIEPRZETESTOWANE |

## 7. Workspace i project lifecycle

Status: `NIEPRZETESTOWANE`.

Ekrany:

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/workspace` | Workspace spine, pipeline/code/output panels | Widok workspace z sekcjami pracy, bez stuck loading. | NIEPRZETESTOWANE |
| `/workspace-defaults` | Domyslne ustawienia workspace | Formularze/sekcje smart defaults, budzet, autonomia, mobile, cleanup. | NIEPRZETESTOWANE |
| `/projects` | Rejestr projektow | Lista/karty projektow, filtry lub empty state, szczegoly po wyborze. | NIEPRZETESTOWANE |
| `/projects/[projectId]` | Szczegol projektu | Dane projektu zgodne z wybranym ID. | NIEPRZETESTOWANE |
| `/projects/[projectId]/lifecycle` | Lifecycle projektu | Fazy, karty statusu, quick actions, modal szczegolow. | NIEPRZETESTOWANE |
| `/project-start` | Start projektu | Formularz/intake startowy lub kontrolowany stan braku danych. | NIEPRZETESTOWANE |

Scenariusz: utworzenie lub otwarcie projektu.

| Krok | Akcja operatora | Oczekiwany rezultat | Status |
|---|---|---|---|
| 1 | Otworz `/workspace` | Widac aktywny workspace albo empty state z instrukcja startu. | NIEPRZETESTOWANE |
| 2 | Uruchom kickoff/intake, jezeli dostepny | Powstaje sesja/projekt albo pojawia sie Human Gate. | NIEPRZETESTOWANE |
| 3 | Otworz `/projects` | Projekt jest widoczny na liscie, bez fikcyjnego PASS. | NIEPRZETESTOWANE |
| 4 | Kliknij projekt | Szczegoly odpowiadaja temu projektowi. | NIEPRZETESTOWANE |
| 5 | Otworz lifecycle | Fazy i next steps odpowiadaja stanowi backendu. | NIEPRZETESTOWANE |
| 6 | Cofnij lub przerwij | Operator wraca do listy bez utraty stanu. | NIEPRZETESTOWANE |

## 8. Governance, Human Gate i Model Council

Status: `NIEPRZETESTOWANE`.

Ekrany:

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/governance` | Governance overview, compliance, policies | Dashboard governance bez sprzecznych statusow. | NIEPRZETESTOWANE |
| `/gates` | Bramy decyzyjne | Lista/evaluacje gate albo empty state. | NIEPRZETESTOWANE |
| `/human-gate` | Kolejka decyzji Human Gate | Tickety, priorytety, origin, stan, przyciski przejscia do projektu/lifecycle/orchestration. | NIEPRZETESTOWANE |
| `/model-council` | Rada modeli | Sesje, role, uczestnicy, analiza, dyskusja, critic, sentinel, konsolidacja. | NIEPRZETESTOWANE |
| `/decisions` | Decyzje/snapshots | Timeline/chain/cascade albo kontrolowany empty state. | NIEPRZETESTOWANE |

Scenariusze Human Gate:

| Scenariusz | Klikniecie | Co operator powinien zobaczyc po kliknieciu | Status |
|---|---|---|---|
| Otwarcie ticketa | Kliknij ticket w `/human-gate` | Panel szczegolow, payload, ryzyko, origin i dostepne akcje. | NIEPRZETESTOWANE |
| Przejscie do lifecycle | Kliknij akcje lifecycle | Nawigacja do lifecycle wlasciwego projektu. | NIEPRZETESTOWANE |
| Przejscie do directions | Kliknij akcje project directions | Nawigacja do odpowiedniego widoku projektu. | NIEPRZETESTOWANE |
| Przejscie do orchestration | Kliknij akcje orchestration | Widok orchestration z kontekstem projektu. | NIEPRZETESTOWANE |
| Zgoda/odrzucenie | Kliknij approve/reject, jezeli dostepne | Zmiana stanu ticketa i audit/evidence wpis. | NIEPRZETESTOWANE |

Scenariusze Model Council:

| Scenariusz | Klikniecie | Co operator powinien zobaczyc po kliknieciu | Status |
|---|---|---|---|
| Nowa sesja | `model-council-new-session` i submit | Sesja pojawia sie na liscie. | NIEPRZETESTOWANE |
| Analiza | `run-council-analysis` | Analizy lub kontrolowany blad modeli. | NIEPRZETESTOWANE |
| Dyskusja | `run-council-discussion` | Rundy dyskusji albo jasny brak dostepnych modeli. | NIEPRZETESTOWANE |
| Uczestnik | Add participant | Uczestnik z rola/ranga pojawia sie w sesji. | NIEPRZETESTOWANE |
| Critic | Critic sign | Podpis critic zapisany i widoczny. | NIEPRZETESTOWANE |
| Sentinel | Sentinel evaluate | Verdict sentinela aktualizuje consensus. | NIEPRZETESTOWANE |
| Konsolidacja | Consolidate gated | Wynik respektuje wymogi critic/sentinel. | NIEPRZETESTOWANE |

## 9. Execution

Status: `NIEPRZETESTOWANE`.

Ekrany:

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/execution-start` | Start execution | Runtime capabilities, active project, live workers lub gate required. | NIEPRZETESTOWANE |
| `/pipeline` | Pipeline runs | Runs, steps, execute/cancel albo empty state. | NIEPRZETESTOWANE |
| `/orchestration` | Orchestration overview | Teams, dispatch, event map, council rules, fixer links. | NIEPRZETESTOWANE |
| `/workers` | Worker pool | Worker status, pool/topology, brak sprzecznych licznikow. | NIEPRZETESTOWANE |
| `/terminal` | Terminal/operator actions | Terminal state lub kontrolowany brak uprawnien. | NIEPRZETESTOWANE |

Bezpieczne zasady:

| Operacja | Wymagany warunek przed kliknieciem | Bezpieczne przerwanie | Status |
|---|---|---|---|
| Execute run | Projekt ma jasny ID i gate nie blokuje execution. | Cancel run/stop workers i zapis audit. | NIEPRZETESTOWANE |
| Live spawn workers | Operator rozumie koszt i topologie. | Stop live workers, potwierdz stan zero/idle. | NIEPRZETESTOWANE |
| Dispatch/orchestration | Human Gate/council nie blokuje decyzji. | Cofnij dispatch lub oznacz jako blocked. | NIEPRZETESTOWANE |

## 10. Memory

Status: `NIEPRZETESTOWANE`.

Ekrany i API:

| Trasa/API | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/memory` | Memory dashboard | Sekcje/recent/stats/search/evidence bez stuck loading. | NIEPRZETESTOWANE |
| `/source-of-truth` | Source of truth | Kanon/truth plane albo kontrolowany status czesciowy. | NIEPRZETESTOWANE |
| `/ontology` | Ontology | Graf/relacje albo empty state. | NIEPRZETESTOWANE |
| `/api/v1/memory/index/search` | Search | Wynik zgodny z zapytaniem testowym. | NIEPRZETESTOWANE |
| `/api/v1/memory/evidence` | Evidence write | Rekord zapisany i odczytywalny. | NIEPRZETESTOWANE |

Scenariusz:

| Krok | Akcja | Oczekiwany rezultat | Status |
|---|---|---|---|
| 1 | Otworz `/memory` | Widoczne statystyki lub kontrolowany empty state. | NIEPRZETESTOWANE |
| 2 | Wyszukaj znana fraze | Wynik zawiera pasujacy rekord albo jawnie brak wynikow. | NIEPRZETESTOWANE |
| 3 | Dodaj testowe evidence, jezeli scenariusz pozwala | Rekord pojawia sie w recent/evidence. | NIEPRZETESTOWANE |
| 4 | Odswiez strone | Rekord/stats nie znikaja bez wyjasnienia. | NIEPRZETESTOWANE |

## 11. Skills

Status: `NIEPRZETESTOWANE`.

| Trasa/API | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/skills` | Registry/runtime/executions/demand | Zakladki skills, executions, demand signals, lifecycle. | NIEPRZETESTOWANE |
| `/api/v1/skills/skills` | Lista skills | Lista albo empty state z liczba 0 bez falszywego sukcesu. | NIEPRZETESTOWANE |
| `/api/v1/skills/executions` | Executions | Historia wykonania albo empty state. | NIEPRZETESTOWANE |
| `/api/v1/skills/demand/analyze` | Demand analysis | Wynik analizy albo kontrolowany blad. | NIEPRZETESTOWANE |

Scenariusze:

| Scenariusz | Klikniecie | Oczekiwany rezultat | Status |
|---|---|---|---|
| Rejestracja skill | Formularz/register, jezeli dostepny | Skill pojawia sie w registry z poprawnym statusem lifecycle. | NIEPRZETESTOWANE |
| Wykonanie skill | Execute skill | Execution ma ID, status, czas i wynik/blokade. | NIEPRZETESTOWANE |
| Demand signal | Record/analyze demand | Demand signal pojawia sie i jest analizowany. | NIEPRZETESTOWANE |
| Long-run lifecycle | Long-run test | Cykl nie udaje PASS bez wykonania. | NIEPRZETESTOWANE |

## 12. Funding

Status: `NIEPRZETESTOWANE`.

W dokumentacji R3.14 opisano `/funding` z raportami, wykresami, eksportami CSV/PDF/XLSX i operator-reviewed e-mail. W tej instrukcji to pozostaje `NIEPRZETESTOWANE` do czasu aktualnego freeze evidence.

| Element | Co kliknac | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/funding` overview | Otworz trase | Programy/calls/ideas/company profile albo kontrolowany empty state. | NIEPRZETESTOWANE |
| Zakladka `Raporty` | Kliknij raporty | Wykresy pipeline, status/skutecznosc, ROI/budzet, presja terminow. | NIEPRZETESTOWANE |
| CSV pipeline | Kliknij export CSV | Plik CSV lub widoczny download event. | NIEPRZETESTOWANE |
| PDF export | Kliknij PDF dla aplikacji | Pobranie z `/api/v1/funding/application/{application_id}/export/pdf`. | NIEPRZETESTOWANE |
| XLSX export | Kliknij XLSX dla aplikacji | Pobranie z `/api/v1/funding/application/{application_id}/export/xlsx`. | NIEPRZETESTOWANE |
| E-mail draft | Kliknij szkic e-mail | Otwiera operator-reviewed draft, nie automatyczna wysylka bez gate. | NIEPRZETESTOWANE |
| Funding approval | Wywolaj akcje wymagajaca zgody | Ticket w Human Gate lub jasny status approval. | NIEPRZETESTOWANE |

## 13. Audit, replay i evidence

Status: `NIEPRZETESTOWANE`.

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/audit` | Audit viewer | Liczba zdarzen, integralnosc lancucha, tabela/log. | NIEPRZETESTOWANE |
| `/audit-trail` | Audit trail | Historia operacji albo kontrolowany empty state. | NIEPRZETESTOWANE |
| `/evidence` | Evidence viewer | Evidence packs/entries, filtry, szczegoly. | NIEPRZETESTOWANE |
| `/evidence-spine` | Evidence spine | Relacje evidence i decyzji. | NIEPRZETESTOWANE |
| `/terminal/replay` | Replay | Timeline, kontrolki czasu, lista eventow, playback. | NIEPRZETESTOWANE |

Scenariusz dowodowy:

| Krok | Akcja | Oczekiwany rezultat | Status |
|---|---|---|---|
| 1 | Wykonaj akcje testowa w UI | Powstaje widoczny skutek. | NIEPRZETESTOWANE |
| 2 | Otworz `/audit` | Akcja ma wpis audit albo jawny brak wpisu jest oznaczony jako luka. | NIEPRZETESTOWANE |
| 3 | Otworz `/evidence` | Evidence pack/entry istnieje, jezeli flow powinien go tworzyc. | NIEPRZETESTOWANE |
| 4 | Otworz `/terminal/replay` | Event mozna odnalezc w timeline albo replay wskazuje brak danych. | NIEPRZETESTOWANE |

## 14. Mobile/operator

Status: `NIEPRZETESTOWANE`.

Wstepna mapa wskazuje web surfaces `/operator-mobile`, `/operator-mobile/queue`, `/operator-mobile/devices` oraz `/mobile`. Starsza dokumentacja opisuje mobile gateway jako czesciowy i natywna aplikacje jako planowana/czesciowa. Freeze musi to zweryfikowac runtime.

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/operator-mobile` | Mobile landing | Liczniki: oczekujace decyzje, zbindowane urzadzenia, pilne zgody. | NIEPRZETESTOWANE |
| `/operator-mobile/queue` | Kolejka mobile | Lista ticketow/decyzji lub empty state. | NIEPRZETESTOWANE |
| `/operator-mobile/queue/[ticketId]` | Szczegol ticketa | Szczegoly i akcje decyzji. | NIEPRZETESTOWANE |
| `/operator-mobile/devices` | Urzadzenia | Lista/binding devices. | NIEPRZETESTOWANE |
| `/mobile` | Mobile preview/gateway surface | Stan gateway albo mobile overview. | NIEPRZETESTOWANE |

## 15. Settings, keys i secrets

Status: `NIEPRZETESTOWANE`.

| Trasa | Funkcja | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/settings` | Ustawienia glowne | Zakladki API keys, hierarchy, council lub odpowiedniki. | NIEPRZETESTOWANE |
| `/settings/profile` | Profil operatora | Formularz profilu lub kontrolowany empty state. | NIEPRZETESTOWANE |
| `/settings/advisor` | Settings advisor | Konfiguracja doradcy. | NIEPRZETESTOWANE |
| `/secrets` | Sekrety | Lista zamaskowanych sekretow, formularz dodania, sukces/blad bez ujawniania wartosci. | NIEPRZETESTOWANE |
| `/ai-models` | Modele AI | Providers/catalog/budgets albo kontrolowany blad konfiguracji. | NIEPRZETESTOWANE |

Zasady freeze:

| Operacja | Zakaz | Oczekiwane zabezpieczenie | Status |
|---|---|---|---|
| Dodanie sekretu | Nie wklejac prawdziwych produkcyjnych sekretow do testu. | Uzyc testowego placeholdera i sprawdzic maskowanie. | NIEPRZETESTOWANE |
| Walidacja providera | Nie traktowac bledu provider API jako bledu UI bez sprawdzenia konfiguracji. | UI pokazuje jasny blad i nie zapisuje jawnej wartosci. | NIEPRZETESTOWANE |
| Rotacja | Nie rotowac prawdziwych kluczy bez zgody operatora. | Rotacja wymaga jawnej akcji i audit. | NIEPRZETESTOWANE |

## 16. Observability i readiness

Status: `NIEPRZETESTOWANE`.

| Trasa/API | Co sprawdzic | Co operator powinien zobaczyc | Status |
|---|---|---|---|
| `/health` | Health score, moduly, endpointy, DB mode | Stan spójny z backend health. | NIEPRZETESTOWANE |
| `/observability` | Readiness/metrics | Widok metryk lub kontrolowany brak backendu. | NIEPRZETESTOWANE |
| `/runtime` | Runtime truth | Runtime truth bez sprzecznosci z health. | NIEPRZETESTOWANE |
| `/performance` | Performance | Budzety/performance state. | NIEPRZETESTOWANE |
| `/quality` | Quality | Golden sets/regression alerts lub empty state. | NIEPRZETESTOWANE |
| `/security-scan` | Security scan | Wyniki lub brak uprawnien w kontrolowanej formie. | NIEPRZETESTOWANE |

## 17. Scenariusze bledow

| Blad | Jak rozpoznac | Co operator robi | Status |
|---|---|---|---|
| Backend niedostepny | Offline guard, fetch error, brak health OK | Nie klika akcji zapisu; zapisuje screenshot i log. | NIEPRZETESTOWANE |
| 401/403 | Unauthorized/forbidden w UI albo API | Sprawdza auth/session/profile; nie obchodzi RBAC. | NIEPRZETESTOWANE |
| 404 route | Next.js 404 albo brak endpointu | Oznacza route/API jako `BROKEN` lub drift dokumentacji. | NIEPRZETESTOWANE |
| 500 API | Error toast lub stack/backend log | Zapisuje request, response, timestamp i krok reprodukcji. | NIEPRZETESTOWANE |
| Stuck loading | Spinner bez konca po ustalonym czasie | Screenshot, network/log, odswiezenie tylko jako osobny krok. | NIEPRZETESTOWANE |
| Rozjazd licznikow | UI pokazuje inne liczby niz API/evidence | Oznacza jako `CZESCIOWE` lub `BROKEN` z porownaniem. | NIEPRZETESTOWANE |
| Falszywy PASS | UI pokazuje sukces bez skutku w API/audit | Nie akceptuje jako `ZWERYFIKOWANE`; wymaga dowodu skutku. | NIEPRZETESTOWANE |
| Ujawnienie sekretu | Wartosc sekretu widoczna po zapisie | Natychmiast `BROKEN`, przerwanie testu i rotacja testowego sekretu. | NIEPRZETESTOWANE |
| Nieodwracalna akcja | Deploy, funding submission, worker spawn, secret rotation | Wymaga Human Gate/operator approval i rollback planu. | NIEPRZETESTOWANE |

## 18. Co operator powinien zobaczyc po kliknieciu - wzorzec zapisu

Uzywaj tego szablonu przy kazdej funkcji:

```text
Ekran:
Status:
PASS:
Klikniecie:
Selektor/test id:
Dane wejsciowe:
Oczekiwany widok:
Rzeczywisty widok:
Skutek API:
Skutek audit/evidence:
Screenshot/log:
Werdykt:
Rollback/przerwanie:
Uwagi:
```

Minimalny opis pozytywnego wyniku:

```text
Po kliknieciu [nazwa przycisku] operator widzi [konkretny panel/modal/tabele/toast].
URL zmienia sie na [trasa] albo pozostaje na [trasa].
Backend zwraca [status/kod/ID].
Audit/evidence zawiera [ID/typ wpisu].
Stan utrzymuje sie po odswiezeniu strony.
```

Minimalny opis negatywnego wyniku:

```text
Po kliknieciu [nazwa przycisku] operator widzi [blad/brak reakcji/stuck loading].
Backend zwraca [kod/blad] albo brak requestu.
Nie powstaje wymagany audit/evidence.
Status scenariusza: BROKEN.
Bezpieczne przerwanie: [kroki].
```

## 19. Rollback i bezpieczne przerwanie

Status: `NIEPRZETESTOWANE`.

| Obszar | Przerwanie | Rollback | Status |
|---|---|---|---|
| Workspace/project intake | Zamknij modal, wróć do `/workspace` lub `/projects`; nie uruchamiaj launch. | Usun/oznacz testowy projekt tylko wedlug zatwierdzonego flow. | NIEPRZETESTOWANE |
| Human Gate | Nie klikaj approve/reject bez potwierdzenia scenariusza. | Cofniecie decyzji tylko przez decyzje/cascade/audit, jezeli system to wspiera. | NIEPRZETESTOWANE |
| Model Council | Nie konsoliduj gated decision bez critic/sentinel wymaganego przez scenariusz. | Nowa sesja albo snapshot decyzji; nie edytowac evidence recznie. | NIEPRZETESTOWANE |
| Execution | Uzyj cancel/stop workers; potwierdz idle/zero active. | Odtworz poprzedni config runtime z evidence, jezeli byl zapisany. | NIEPRZETESTOWANE |
| Funding | Nie wysylaj realnych aplikacji ani maili bez Human Gate. | Cofnij do draft/review; zachowaj eksporty jako artefakty testowe. | NIEPRZETESTOWANE |
| Secrets | Nie testuj prawdziwymi sekretami; uzyj placeholderow. | Usun/rotuj testowy sekret, sprawdz audit. | NIEPRZETESTOWANE |
| Mobile | Nie paruj prawdziwego urzadzenia bez zgody. | Unpair test device, jezeli flow istnieje. | NIEPRZETESTOWANE |

## 20. Lista ekranow do pelnego freeze walkthrough

Status domyslny kazdego wpisu: `NIEPRZETESTOWANE`.

| Grupa | Trasy |
|---|---|
| Entry/system | `/overview`, `/dashboard/operator-monitor`, `/health`, `/runtime`, `/observability`, `/modules` |
| Workspace/project | `/workspace`, `/workspace-defaults`, `/project-start`, `/projects`, `/projects/[projectId]`, `/projects/[projectId]/lifecycle`, `/lifecycle` |
| Governance | `/governance`, `/gates`, `/human-gate`, `/model-council`, `/decisions`, `/policy`, `/guards` |
| Execution/orchestration | `/execution-start`, `/pipeline`, `/orchestration`, `/orchestration/dispatch`, `/orchestration/event-map`, `/orchestration/teams`, `/workers`, `/terminal` |
| Memory/truth | `/memory`, `/source-of-truth`, `/ontology`, `/book`, `/masterplan` |
| Skills/quality | `/skills`, `/quality`, `/golden-tests`, `/test-center`, `/test-center/dashboard`, `/test-center/catalog` |
| Funding/cost | `/funding`, `/costs`, `/budget`, `/cost-guard`, `/performance`, `/autoscaler`, `/capacity` |
| Audit/evidence/replay | `/audit`, `/audit-trail`, `/evidence`, `/evidence-spine`, `/terminal/replay` |
| Mobile/operator | `/operator-mobile`, `/operator-mobile/queue`, `/operator-mobile/devices`, `/mobile` |
| Settings/security | `/settings`, `/settings/profile`, `/settings/advisor`, `/secrets`, `/ai-models`, `/auth`, `/security-guard`, `/security-scan` |
| Lab/demo | `/test-center/theater`, `/test-center/simulation`, `/test-center/release-gate`, `/demo/portal`, `/demo/funding`, `/demo/mobile-inspector` |

## 21. Rejestr kart funkcji i flow do uzupelnienia screenshotami

Ten rejestr jest miejscem, w ktorym glowny agent dopisuje sciezki do screenshotow i evidence. Wiersz moze pozostac `NIEPRZETESTOWANE`, ale nie moze zostac usuniety tylko dlatego, ze flow nie przeszlo testu.

| Flow ID | Funkcja/flow | Trasa UI | Screenshot desktop | Screenshot mobile | Opis ekranu | Co operator widzi | Kliki/akcje | Po kliknieciu | Scenariusz pozytywny | Scenariusz bledny | Bug IDs | Evidence path | Status freeze |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SYS-001 | Backend health | `/health` | evidence/screenshots/health_desktop.png | N/D | Health unified backendu `8010`. | Status OK, wersja `3.5.0`, `modules=138`, `endpoints=1953`, `db_mode=sqlite`. | Otworz `/health` po starcie backendu. | Backend zwraca JSON health. | PASS_1: health JSON istnieje. PASS_2 pending. | Brak health albo inny port blokuje freeze. | DASH-E2E-001 | evidence/runtime_baseline/backend_health_8010.json | CZESCIOWE |
| SYS-002 | Frontend shell | dowolna trasa app | evidence/screenshots/root_launch_after_pass1.png | evidence/screenshots/root_mobile.png | Shell operator console po starcie frontendu. | Sidebar, top command bar, banner onboarding, overview po launch. | Otworz `/`, kliknij launch/entry do overview. | URL konczy na `/overview`. | PASS_1: root launch przeszedl. PASS_2 pending przez DASH-E2E-001. | Frontend startuje na zlym porcie albo root nie nawiguje. | DASH-E2E-001 | evidence/runtime_baseline/frontend_root_3001.status.txt | CZESCIOWE |
| SYS-003 | Offline guard | dowolna trasa app przy braku backendu | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| DASH-001 | Operator monitor overview | `/dashboard/operator-monitor` | evidence/screenshots/dashboard__operator-monitor_desktop.png | TBD | Dashboard operatora i runtime topology. | Route renderuje HTTP 200 bez console errors w probe. | Otworz trase z sidebar albo URL. | Widok renderuje operator monitor. | PASS_1 route probe. | Brak renderu, console/network error, stuck loading. | TBD | evidence/runtime_baseline/dashboard_route_probe_pass1.md | CZESCIOWE |
| DASH-002 | Runtime config save | `/dashboard/operator-monitor` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| DASH-003 | Live spawn start/stop | `/dashboard/operator-monitor` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| WORK-001 | Workspace tabs | `/workspace` | evidence/screenshots/workspace_tab_wynik_pass1.png | evidence/screenshots/workspace_mobile.png | Dwupanelowa przestrzen Thinking/Working. | Zakladki: Czat, Rada, Ksiegi, Bramka, Pipeline, Kod, Wynik. | Kliknij kazda zakladke. | Widok przelacza aktywny panel i zostaje na `/workspace`. | PASS_1 tabs. PASS_2 pending. | Tab nie przelacza, znika layout, console error. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| WORK-002 | Workspace kickoff/intake | `/workspace` | evidence/screenshots/workspace_desktop.png | evidence/screenshots/workspace_mobile.png | Start projektu z workspace. | Obecnie potwierdzono tylko ekran i zakladki, nie pelny kickoff. | TBD | TBD | Nie potwierdzono pelnego create/open project flow. | Brak projektu po kickoff lub brak Human Gate. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | NIEPRZETESTOWANE |
| WORK-003 | Workspace defaults | `/workspace-defaults` | evidence/screenshots/workspace-defaults_desktop.png | TBD | Domyslne ustawienia workspace. | Route renderuje HTTP 200. | Otworz trase. | Widok ustawien renderuje sie bez bledow probe. | PASS_1 route. | Zapis ustawien nie byl testowany. | TBD | evidence/runtime_baseline/dashboard_route_probe_pass1.md | CZESCIOWE |
| PROJ-001 | Projects list | `/projects` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| PROJ-002 | Project detail | `/projects/[projectId]` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| PROJ-003 | Project lifecycle | `/projects/[projectId]/lifecycle` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| GOV-001 | Governance overview | `/governance` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| GOV-002 | Human Gate queue | `/human-gate` | evidence/screenshots/human-gate_desktop.png | evidence/screenshots/human-gate_mobile.png | Kolejka decyzji operatora. | Liczniki widocznych, oczekujacych, wysokiego ryzyka i blokujacych biletow. | Otworz trase i przelacz oczekujace/wszystkie. | Lista biletow pozostaje widoczna. | PASS_1 route i controlled action context. | Brak biletow mimo backend tickets albo zly status. | TBD | evidence/runtime_baseline/dashboard_route_probe_pass1.md | CZESCIOWE |
| GOV-003 | Human Gate approve/reject | `/human-gate` | evidence/screenshots/human_gate_controlled_approve_after_pass1.png | evidence/screenshots/human-gate_mobile.png | Kontrolowane zatwierdzanie i odrzucanie biletow freeze. | Ticket P4 D3 non-blocking, payload `dashboard_e2e_freeze`, przyciski Zatwierdz/Odrzuc. | Otworz kontrolowany ticket, kliknij Zatwierdz albo Odrzuc. | Backend zmienia `state` na `approved` albo `rejected`, `resolved_by=operator-console`. | PASS_1 approve i reject. PASS_2 pending. | UI pokazuje sukces bez zmiany backend state. | TBD | evidence/runtime_baseline/human_gate_approve_after_ui_ticket_get.json; evidence/runtime_baseline/human_gate_reject_after_ui_ticket_get.json | CZESCIOWE |
| GOV-004 | Model Council session create | `/model-council` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| GOV-005 | Model Council analysis/discussion | `/model-council` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| GOV-006 | Critic/sentinel/consolidation | `/model-council` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| EXEC-001 | Execution runtime capabilities | `/execution-start` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| EXEC-002 | Pipeline execute/cancel | `/pipeline` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| EXEC-003 | Orchestration dispatch | `/orchestration/dispatch` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| MEM-001 | Memory dashboard | `/memory` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| MEM-002 | Memory search | `/memory` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| MEM-003 | Memory evidence write/read | `/memory` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| SKILL-001 | Skills create | `/skills` | evidence/screenshots/skills_controlled_create_after_pass1.png | evidence/screenshots/skills_mobile.png | Rejestr skills z formularzem/kontrolowanym create. | Liczniki skills, lifecycle, lista skills, status po utworzeniu. | Otworz `/skills`, wypelnij kontrolowany skill, zapisz. | Skill pojawia sie w registry. | PASS_1 create. Pelny PASS_2 pending. | Brak rekordu po zapisie albo brak bledu walidacji. | DASH-E2E-003 context | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| SKILL-002 | Skill execution `seed.echo` | `/skills` | evidence/screenshots/skills_execute_retest2_after_fix.png | evidence/screenshots/skills_mobile.png | Manualne wykonanie skill z domyslnym payloadem po naprawie. | UI status `Wykonano skill seed.echo: completed`; execution ma `status=completed`. | Wybierz `seed.echo`, kliknij `Wykonaj wybrana`. | Backend execution zapisuje `input_data.text`, output zwraca echo text. | Naprawa DASH-E2E-003 ma 2x PASS retest; caly Skills flow nadal nie FROZEN. | UI sukces przy backend `failed` byl bledem DASH-E2E-003. | DASH-E2E-003 | evidence/runtime_baseline/skills_execute_retest1_after_fix.json; evidence/runtime_baseline/skills_execute_retest2_after_fix.json | CZESCIOWE |
| SKILL-003 | Demand signal | `/skills` | evidence/screenshots/skills_controlled_signal_after_pass1.png | evidence/screenshots/skills_mobile.png | Sygnal popytu dla skills. | Panel demand/signals po kontrolowanej akcji. | Wykonaj kontrolowany signal scenario. | Signal jest widoczny albo licznik/sekcja sie aktualizuje. | PASS_1 signal. PASS_2 pending. | Signal nie zapisuje sie albo brak widocznej informacji. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| FUND-001 | Funding tabs readonly | `/funding` | evidence/screenshots/funding_tab_wnioski_pass1.png | evidence/screenshots/funding_mobile.png | Funding cockpit z zakladkami Firma, Nabory, Pomysly, Dopasowanie, Wnioski, Zlozenie i CRM, Raporty. | Karty gotowosci, naborow, wnioskow, alertow oraz tresc aktywnej zakladki. | Kliknij kazda zakladke. | Widok przelacza zakladki bez 4xx/5xx. | PASS_1 tab navigation. | Save/profile/conversion/submission nie byly pelnie testowane. | DASH-E2E-002 context | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| FUND-002 | Funding reports charts | `/funding` | evidence/screenshots/funding_reports_retest5_second_pass.png | evidence/screenshots/funding_mobile.png | Zakladka Raporty po naprawie chart sizing. | Widoczne 4 wykresy raportowe i brak Recharts width/height warnings. | Kliknij `Raporty`. | ChartFrame mierzy dodatni rozmiar i renderuje wykresy. | DASH-E2E-002 ma 2x PASS chart-render; caly Funding flow nie FROZEN. | Recharts warning width/height `-1` byl bledem DASH-E2E-002. | DASH-E2E-002 | evidence/runtime_baseline/funding_reports_chart_warning_retest4.json; evidence/runtime_baseline/funding_reports_chart_warning_retest5_second_pass.json | CZESCIOWE |
| FUND-003 | Funding CSV/PDF/XLSX exports | `/funding` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| FUND-004 | Funding Human Gate approval | `/funding`, `/human-gate` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| AUD-001 | Audit viewer | `/audit` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| AUD-002 | Evidence viewer | `/evidence` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| AUD-003 | Terminal replay | `/terminal/replay` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| MOB-001 | Operator mobile landing | `/operator-mobile` | evidence/screenshots/operator_mobile_home_pass1.png | evidence/screenshots/operator-mobile_mobile.png | Mobile/operator entry. | Liczniki i link/karta do kolejki operatora. | Otworz `/operator-mobile`. | Home renderuje sie i pozwala przejsc do queue. | PASS_1. PASS_2 pending. | Brak nawigacji do kolejki albo route error. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| MOB-002 | Operator mobile queue | `/operator-mobile/queue` | evidence/screenshots/operator_mobile_queue_after_click_pass1.png | evidence/screenshots/operator-mobile_mobile.png | Mobilna kolejka pending approvals. | Lista P0/P2 pending tickets z `Open Detail`, `Approve`, `Reject`. | Kliknij przejscie do queue z home. | URL `/operator-mobile/queue`, lista ticketow widoczna. | PASS_1 queue nav. PASS_2 pending. | Brak ticketow, zly URL albo akcje bez potwierdzenia. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| MOB-003 | Operator mobile devices | `/operator-mobile/devices` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| SET-001 | Settings tabs | `/settings` | evidence/screenshots/settings_tab_czlonkowie_pass1.png | evidence/screenshots/settings_mobile.png | Centrum konfiguracji: Klucze API, Hierarchia modeli, Czlonkowie rady. | Zakladki ustawien i opis uprawnien D3+. | Kliknij `Klucze API`, `Hierarchia modeli`, `Czlonkowie rady`. | Aktywna zakladka zmienia tresc. | PASS_1 tab navigation. | Dodanie/walidacja klucza celowo pending. | TBD | evidence/runtime_baseline/dashboard_human_interactions_pass1.md | CZESCIOWE |
| SET-002 | Secrets add/mask/rotate | `/secrets` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| SET-003 | AI models/providers | `/ai-models` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| OBS-001 | Observability | `/observability` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| OBS-002 | Runtime truth | `/runtime` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |
| SAFE-001 | Rollback / safe stop | zalezne od flow | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | NIEPRZETESTOWANE |

## 22. Aktualne walkthrough operatorskie z evidence

Ta sekcja opisuje tylko to, co obecnie wynika z `evidence/`, `BUG_LEDGER.md`, `FREEZE_REGISTER.md` i `RUN_LOG.md`. Zadne z ponizszych pelnych flow nie jest oznaczone jako `FROZEN`, bo rejestr nadal wymaga pelnego 2x PASS flow. Wyjatkiem sa lokalne naprawy `DASH-E2E-002` i `DASH-E2E-003`, ktore maja 2x PASS retest na waskim zakresie bledu.

### 22.1. Start, backend health i frontend shell

Status freeze: `2X_PASS` dla startu runtime; `CZESCIOWE` dla pelnych flow operator console  
Flow: `FLOW-001`, `FLOW-002`  
Bug IDs: `DASH-E2E-001`  
Evidence: `evidence/runtime_baseline/backend_health_8010.json`, `evidence/runtime_baseline/backend_restart_retest_d004.json`, `evidence/runtime_baseline/frontend_root_3001.status.txt`, `evidence/runtime_baseline/frontend_start_retest2_clean.json`, `evidence/runtime_baseline/openapi_summary.txt`, `evidence/runtime_baseline/dashboard_route_probe_pass1.md`, `evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.md`, `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`

![Health desktop](evidence/screenshots/health_desktop.png)

![Root launch after PASS 1](evidence/screenshots/root_launch_after_pass1.png)

Co operator widzi:

- Backend health zwraca `status=ok`, `version=3.5.0`, `modules=138`, `endpoints=1953`, `db_mode=sqlite`, `event_mode=sqlite`.
- Frontend root po uruchomieniu przechodzi do `http://127.0.0.1:3001/overview`.
- Shell pokazuje sidebar, top command bar, tryb operator/techniczny, banner pierwszej konfiguracji oraz overview z licznikami systemu.
- OpenAPI summary pokazuje `openapi_paths=1642`.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po akcji | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Uruchom backend na `127.0.0.1:8010`. | Backend wystawia `/health` i `/openapi.json`. | `/health` zwraca JSON z `status=ok`. | PASS_1 |
| 2 | Sprawdz `/health`. | UI i probe maja punkt odniesienia dla backendu. | `modules=138`, `endpoints=1953`. | PASS_1 |
| 3 | Uruchom frontend na `127.0.0.1:3001`. | Next powinien sluchac na kanonicznym porcie. | `frontend_root_3001.status.txt` zawiera `200`. | PASS_1 |
| 4 | Otworz `/`. | Root launch przechodzi do overview. | Final URL: `/overview`. | PASS_1 |
| 5 | Wykonaj drugi restart frontendu. | Stary listener `32036` zostaje zatrzymany, nowy listener `32204` startuje z `127.0.0.1:3001`. | `frontend_start_retest2_clean.json` ma root `HTTP 200`. | PASS_2 |
| 6 | Wykonaj restart backendu po poprawce D004. | Stary listener `9828` zostaje zatrzymany, nowy listener `29740` startuje na `8010`. | `/health` zwraca `HTTP 200`. | PASS_2 |

Scenariusz pozytywny:

- Backend `/health` odpowiada na `8010`.
- Frontend root i overview odpowiadaja na `3001`.
- Nie ma HTTP 4xx/5xx ani browser console errors w route probe.

Scenariusze bledne:

| Blad | Objaw | Operator robi |
|---|---|---|
| Zly port frontendu | Next pokazuje inny URL niz `127.0.0.1:3001`. | Oznacza `DASH-E2E-001` jako nadal blokujacy PASS_2. |
| Backend offline | Offline guard albo health nie zwraca `status=ok`. | Nie testuje zapisow; zbiera log backendu i screenshot UI. |
| Root nie przechodzi do overview | URL zostaje na `/` albo pokazuje blad. | Zapisuje screenshot przed/po i route probe JSON. |

### 22.2. Route probe dashboardu

Status freeze: `2X_PASS` dla renderowania tras; `CZESCIOWE` dla akcji w pelnych flow  
Flow: `FLOW-002` plus route proof dla `FLOW-003`, `FLOW-004`, `FLOW-007`, `FLOW-008`, `FLOW-010`, `FLOW-011`  
Evidence: `evidence/runtime_baseline/dashboard_route_probe_pass1.md`, `evidence/runtime_baseline/dashboard_route_probe_pass1.json`, `evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.md`, `evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.json`

![Operator monitor desktop](evidence/screenshots/dashboard__operator-monitor_desktop.png)

![Runtime desktop](evidence/screenshots/runtime_desktop.png)

Probe PASS 1 objal 27 tras desktop i 8 widokow mobile. Wszystkie wpisane trasy w `dashboard_route_probe_pass1.md` mialy HTTP `200`, `Error=NO`, `Console warnings/errors=0` i `HTTP >=400=0`.

Probe PASS 2 po restarcie i poprawce `DASH-E2E-004` objal ten sam zestaw 35 widokow. `dashboard_route_probe_pass2_after_d004.json` ma wynik `35/35 OK`, `0` browser console errors/warnings i `0` HTTP >=400.

Trasy desktop z PASS_1:

| Grupa | Trasy |
|---|---|
| Shell/system | `/`, `/overview`, `/dashboard/operator-monitor`, `/runtime`, `/health`, `/observability` |
| Workspace/project | `/workspace`, `/workspace-defaults`, `/projects` |
| Governance | `/governance`, `/human-gate`, `/gates`, `/model-council` |
| Execution/orchestration | `/execution-start`, `/workers`, `/orchestration` |
| Memory/skills/funding | `/memory`, `/skills`, `/funding` |
| Audit/evidence/replay | `/audit`, `/evidence`, `/terminal/replay` |
| Mobile/settings | `/operator-mobile`, `/operator-mobile/queue`, `/settings`, `/settings/profile`, `/secrets` |

Trasy mobile z PASS_1:

| Trasa | Screenshot |
|---|---|
| `/` | `evidence/screenshots/root_mobile.png` |
| `/workspace` | `evidence/screenshots/workspace_mobile.png` |
| `/human-gate` | `evidence/screenshots/human-gate_mobile.png` |
| `/skills` | `evidence/screenshots/skills_mobile.png` |
| `/funding` | `evidence/screenshots/funding_mobile.png` |
| `/operator-mobile` | `evidence/screenshots/operator-mobile_mobile.png` |
| `/settings` | `evidence/screenshots/settings_mobile.png` |
| `/observability` | `evidence/screenshots/observability_mobile.png` |

Operator nie powinien traktowac route probe jako dowodu pelnego flow. Route probe potwierdza render i brak bledow sieci/konsoli w momencie wejscia na ekran, ale nie potwierdza zapisow, akcji, audit trail ani rollback.

Uwagi do `DASH-E2E-004`:

- Pierwszy PASS 2 wykryl HTTP `500` na `/api/v1/governance/compliance/council` podczas wejscia na `/governance`.
- Backend log pokazal `sqlite3.InterfaceError` w `policy_registry.list_policies`.
- Po poprawce lockowania odczytow `PolicyRegistry` wykonano 2x retest punktowy i pelny route probe PASS 2 after D004.
- Operator moze traktowac render tras jako 2x PASS, ale nie moze oznaczyc governance/Human Gate jako `FROZEN`, dopoki approve/reject i pozostale decyzje nie przejda pelnego drugiego przebiegu.

### 22.3. Workspace tabs

Status freeze: `PARTIAL_2X_PASS` dla tab switching  
Flow: `FLOW-003`  
Evidence: `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`, `evidence/runtime_baseline/dashboard_human_interactions_pass1.json`, `evidence/runtime_baseline/workspace_tabs_pass2.json`

![Workspace desktop](evidence/screenshots/workspace_desktop.png)

![Workspace tab Czat](evidence/screenshots/workspace_tab_czat_pass1.png)

![Workspace tab Rada](evidence/screenshots/workspace_tab_rada_pass1.png)

![Workspace tab Ksiegi](evidence/screenshots/workspace_tab_ksiegi_pass1.png)

![Workspace tab Bramka](evidence/screenshots/workspace_tab_bramka_pass1.png)

![Workspace tab Pipeline](evidence/screenshots/workspace_tab_pipeline_pass1.png)

![Workspace tab Kod](evidence/screenshots/workspace_tab_kod_pass1.png)

![Workspace tab Wynik](evidence/screenshots/workspace_tab_wynik_pass1.png)

![Workspace PASS 2 Wynik](evidence/screenshots/workspace_pass2_tab_wynik.png)

Co operator widzi:

- Naglowek `Przestrzen robocza AI`.
- Lewa warstwa Thinking z zakladkami `Czat`, `Rada`, `Ksiegi`, `Bramka`.
- Prawa warstwa Working z zakladkami `Pipeline`, `Kod`, `Wynik`.
- Log wykonania i wpisy pipeline w panelu `Wynik`.

Kroki operatora:

| Krok | Klik/akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Otworz `/workspace`. | Renderuje sie workspace. | Widac Thinking + Working. | PASS_1 |
| 2 | Kliknij `Czat`. | Lewy panel pokazuje czat albo wybor sesji. | Brak route error. | PASS_1 |
| 3 | Kliknij `Rada`. | Lewy panel przechodzi na narade rady. | Panel zmienia tresc. | PASS_1 |
| 4 | Kliknij `Ksiegi`. | Lewy panel pokazuje knowledge/book context. | Panel zmienia tresc. | PASS_1 |
| 5 | Kliknij `Bramka`. | Lewy panel pokazuje Human Gate context. | Panel zmienia tresc. | PASS_1 |
| 6 | Kliknij `Pipeline`, `Kod`, `Wynik`. | Prawy panel przelacza working layer. | Kazda zakladka ma screenshot PASS_1. | PASS_1 |
| 7 | Powtorz wszystkie zakladki w PASS 2. | Thinking/Working layer przelacza sie bez request errors. | `workspace_tabs_pass2.json`: 7 tabs, console 0, HTTP >=400 0. | PASS_2 |

Scenariusz pozytywny:

- Kazda zakladka przelacza widok bez zmiany na blad i bez utraty shell layout.

Scenariusze bledne:

- Klikniecie zakladki nie zmienia aktywnego panelu.
- Panel znika, zachodzi pod sidebar albo zostaje pusty bez empty state.
- Konsola lub network pokazuje blad podczas interakcji.

Zakres niepotwierdzony:

- Pelny `workspace kickoff`.
- Utworzenie projektu i przejscie do lifecycle.
- Persistencja nowej sesji/projektu po odswiezeniu.

### 22.4. Human Gate approve/reject

Status freeze: `PARTIAL_2X_PASS` dla approve/reject; `CZESCIOWE` dla calego governance/council flow  
Flow: `FLOW-004`  
Evidence: `evidence/runtime_baseline/human_gate_approve_ticket_create.json`, `evidence/runtime_baseline/human_gate_approve_after_ui_ticket_get.json`, `evidence/runtime_baseline/human_gate_reject_ticket_create.json`, `evidence/runtime_baseline/human_gate_reject_after_ui_ticket_get.json`, `evidence/runtime_baseline/human_gate_pass2_approve_reject.json`, `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`

![Human Gate approve before](evidence/screenshots/human_gate_controlled_approve_before_pass1.png)

![Human Gate approve after](evidence/screenshots/human_gate_controlled_approve_after_pass1.png)

![Human Gate reject before](evidence/screenshots/human_gate_controlled_reject_before_pass1.png)

![Human Gate reject after](evidence/screenshots/human_gate_controlled_reject_after_pass1.png)

![Human Gate PASS 2 approve after](evidence/screenshots/human_gate_pass2_approve_after.png)

![Human Gate PASS 2 reject after](evidence/screenshots/human_gate_pass2_reject_after.png)

Co operator widzi:

- Ekran `Bramka czlowieka`.
- Liczniki: widoczne bilety, oczekujace, wysokie ryzyko, blokujace/P1.
- Kontrolowane bilety `DASH FREEZE E2E approve ...` i `DASH FREEZE E2E reject ...`.
- Przyciski `Zatwierdz` i `Odrzuc`.

Kroki approve:

| Krok | Akcja | Co dzieje sie po kliknieciu | Dowod | Status |
|---|---|---|---|---|
| 1 | Utworz kontrolowany ticket approve. | Backend zapisuje ticket `66a4aaa6008c4bb49a6192a1258a7418` ze `state=pending`. | `human_gate_approve_ticket_create.json` | PASS_1 |
| 2 | Otworz `/human-gate` na tym tickecie. | Ticket jest widoczny w kolejce. | `human_gate_controlled_approve_before_pass1.png` | PASS_1 |
| 3 | Kliknij `Zatwierdz`. | UI pokazuje stan zatwierdzony. | `human_gate_controlled_approve_after_pass1.png` | PASS_1 |
| 4 | Odczytaj ticket z backendu. | `state=approved`, `resolved_by=operator-console`, `resolution_reason=operator-console approved`. | `human_gate_approve_after_ui_ticket_get.json` | PASS_1 |

Kroki reject:

| Krok | Akcja | Co dzieje sie po kliknieciu | Dowod | Status |
|---|---|---|---|---|
| 1 | Utworz kontrolowany ticket reject. | Backend zapisuje ticket `b1e004c53d6541d8979e946877ce7dc2` ze `state=pending`. | `human_gate_reject_ticket_create.json` | PASS_1 |
| 2 | Otworz `/human-gate` na tym tickecie. | Ticket jest widoczny w kolejce. | `human_gate_controlled_reject_before_pass1.png` | PASS_1 |
| 3 | Kliknij `Odrzuc`. | UI pokazuje stan odrzucony. | `human_gate_controlled_reject_after_pass1.png` | PASS_1 |
| 4 | Odczytaj ticket z backendu. | `state=rejected`, `resolved_by=operator-console`, `resolution_reason=operator-console rejected`. | `human_gate_reject_after_ui_ticket_get.json` | PASS_1 |

Drugi przebieg approve/reject:

| Scenariusz | Ticket | Co operator kliknal | Backend po kliknieciu | Console | HTTP errors | Status |
|---|---|---|---|---:|---:|---|
| Approve PASS 2 | `762ec6b42a2f4476bc24ab3b0d37c528` | `Zatwierdz` na kontrolowanym tickecie PASS2 | `state=approved` | 0 | 0 | PASS |
| Reject PASS 2 | `1d063560e4504f93aa89370ae0c97929` | `Odrzuc` na kontrolowanym tickecie PASS2 | `state=rejected` | 0 | 0 | PASS |

Scenariusz pozytywny:

- UI i backend maja ten sam finalny stan ticketu.
- Kontrolowany ticket nie dotyczy produkcji ani realnego finansowania.

Scenariusze bledne:

- UI pokazuje zatwierdzenie/odrzucenie, ale backend zostaje `pending`.
- Operator kliknie realny ticket zamiast kontrolowanego freeze ticket.
- Po kliknieciu nie ma statusu, toastu ani zmiany listy.

Governance compliance retest `DASH-E2E-004`:

![Governance compliance retest 1](evidence/screenshots/governance_compliance_retest1_d004.png)

![Governance compliance retest 2](evidence/screenshots/governance_compliance_retest2_d004.png)

| Retest | Akcja | Co dzieje sie po akcji | Wynik API | Status |
|---|---|---|---|---|
| 1 | Otworz `/governance`. | UI pobiera compliance scope `council`. | `/api/v1/governance/compliance/council` zwraca HTTP 200, `consoleCount=0`, `httpErrorCount=0`. | PASS |
| 2 | Powtorz wejscie na `/governance`. | Ten sam request compliance przechodzi po restarcie backendu. | HTTP 200 w UI i bezposrednio z backendu. | PASS |

Instrukcja operatora po naprawie:

- Jezeli `/governance` pokazuje dane, ale konsola przegladarki ma `Failed to load resource` dla `/api/v1/governance/compliance/council`, nie wolno oznaczac governance jako PASS.
- Jezeli endpoint compliance zwraca 500, zapisac screenshot `/governance`, request URL, backend traceback i oznaczyc flow jako `BROKEN`.
- Po poprawce D004 stan wymagany to: trasa `/governance` HTTP 200, endpoint compliance HTTP 200, zero browser console errors i zero HTTP >=400.

### 22.5. Skills create/execute/signal oraz DASH-E2E-003

Status freeze: `2X_PASS` dla create/execute/signal  
Flow: `FLOW-007`  
Bug IDs: `DASH-E2E-003`  
Evidence: `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`, `evidence/runtime_baseline/skills_executions_after_pass1.json`, `evidence/runtime_baseline/skills_execute_retest1_after_fix.json`, `evidence/runtime_baseline/skills_execute_retest2_after_fix.json`, `evidence/runtime_baseline/skills_full_pass2_create_execute_signal.json`

![Skills before controlled flow](evidence/screenshots/skills_controlled_before_pass1.png)

![Skills create after PASS 1](evidence/screenshots/skills_controlled_create_after_pass1.png)

![Skills execute after original PASS 1](evidence/screenshots/skills_controlled_execute_after_pass1.png)

![Skills signal after PASS 1](evidence/screenshots/skills_controlled_signal_after_pass1.png)

![Skills execute retest 1 after fix](evidence/screenshots/skills_execute_retest1_after_fix.png)

![Skills execute retest 2 after fix](evidence/screenshots/skills_execute_retest2_after_fix.png)

![Skills full PASS 2 create](evidence/screenshots/skills_full_pass2_create_after.png)

![Skills full PASS 2 execute](evidence/screenshots/skills_full_pass2_execute_after.png)

![Skills full PASS 2 signal](evidence/screenshots/skills_full_pass2_signal_after.png)

Co operator widzi:

- Ekran `Umiejetnosci`.
- Liczniki: zarejestrowane skills, laczne wykonania, wskaznik sukcesu, aktywne sygnaly popytu.
- Liste skills z `seed.echo`, `seed.tokenize`, `seed.summarize` i skills wygenerowanymi automatycznie.
- Kontrolowane akcje create, execute i signal.

Kroki create/execute/signal:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Otworz `/skills`. | Renderuje sie registry/runtime dashboard. | Widac liczniki i liste skills. | PASS_1 |
| 2 | Wykonaj kontrolowany create. | UI pokazuje nowy/zaktualizowany skill kontrolny. | Screenshot `skills_controlled_create_after_pass1.png`. | PASS_1 |
| 3 | Wybierz `seed.echo`. | Formularz/akcja execution uzywa payloadu dla wybranego skill. | Skill jest gotowy do manual execute. | PASS_1 |
| 4 | Kliknij `Wykonaj wybrana`. | Backend tworzy execution. | Po naprawie status backendu to `completed`. | 2x retest naprawy |
| 5 | Wykonaj kontrolowany signal. | Demand signal jest widoczny w panelu albo licznik/sekcja sie aktualizuje. | Screenshot `skills_controlled_signal_after_pass1.png`. | PASS_1 |

Opis naprawy `DASH-E2E-003`:

- Blad: UI po kliknieciu `Wykonaj wybrana` komunikowal sukces, ale backend execution dla `seed.echo` mial `status=failed` i `error=Missing required input: text`.
- Przyczyna: domyslny payload dashboardu nie zawieral wymaganego pola `text`, a UI traktowal HTTP 200 jako sukces bez sprawdzenia `execution.status`.
- Naprawa: payload zawiera `text`, a UI nie uznaje akcji za sukces, jezeli backend zwraca failed/error.

Retesty naprawy:

| Retest | Screenshot | Backend result | Console | HTTP errors | Status |
|---|---|---|---|---|---|
| 1 | `evidence/screenshots/skills_execute_retest1_after_fix.png` | `status=completed`, `runtime_output=Dashboard skills execution smoke test retest 1` | 0 | 0 | PASS |
| 2 | `evidence/screenshots/skills_execute_retest2_after_fix.png` | `status=completed`, `runtime_output=Dashboard skills execution smoke test retest 2` | 0 | 0 | PASS |

Pelny drugi przebieg create/execute/signal:

| Krok | Wynik runtime | Evidence | Status |
|---|---|---|---|
| Create | Utworzono `dashboard_freeze1778688239038_1778688241102`. | `skills_full_pass2_create_after.png` | PASS |
| Execute | `seed.echo` zakonczyl sie `status=completed`. | `skills_full_pass2_execute_after.png` | PASS |
| Demand signal | Zapisano `missing_freeze1778688239038_skill`. | `skills_full_pass2_signal_after.png` | PASS |
| Konsola/siec | `consoleCount=0`, `httpErrorCount=0`. | `skills_full_pass2_create_execute_signal.json` | PASS |

Scenariusz pozytywny:

- UI status brzmi `Wykonano skill seed.echo: completed`.
- Najnowszy backend execution ma `status=completed`, puste `error`, `skill_id=seed.echo` i `input_data.text`.

Scenariusze bledne:

- UI pokazuje sukces mimo `status=failed`.
- Brakuje `input_data.text`.
- `consoleCount` albo `httpErrorCount` jest wiekszy od 0.
- Create/signal przechodzi tylko w UI, ale nie ma potwierdzenia w runtime evidence.

Uwagi freeze:

- `DASH-E2E-003` ma 2x PASS retest dla wykonania `seed.echo`.
- Caly flow Skills create/execute/signal ma teraz 2x PASS w tej kampanii.

### 22.6. Funding tabs/reports oraz DASH-E2E-002

Status freeze: `PARTIAL_2X_PASS` dla zakladek i raportow  
Flow: `FLOW-008`  
Bug IDs: `DASH-E2E-002`  
Evidence: `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`, `evidence/runtime_baseline/funding_reports_chart_warning_retest4.json`, `evidence/runtime_baseline/funding_reports_chart_warning_retest5_second_pass.json`, `evidence/runtime_baseline/funding_tabs_reports_pass2.json`

![Funding desktop](evidence/screenshots/funding_desktop.png)

![Funding Firma](evidence/screenshots/funding_tab_firma_pass1.png)

![Funding Nabory](evidence/screenshots/funding_tab_nabory_pass1.png)

![Funding Pomysly](evidence/screenshots/funding_tab_pomys_pass1.png)

![Funding Dopasowanie](evidence/screenshots/funding_tab_dopasowanie_pass1.png)

![Funding Wnioski](evidence/screenshots/funding_tab_wnioski_pass1.png)

![Funding Raporty PASS 1](evidence/screenshots/funding_tab_raporty_pass1.png)

![Funding reports retest 2](evidence/screenshots/funding_reports_retest5_second_pass.png)

![Funding PASS 2 Raporty](evidence/screenshots/funding_full_pass2_tab_raporty.png)

Co operator widzi:

- Naglowek `Finansowanie`.
- Karty: gotowosc profilu, nabory, wnioski, alerty.
- Zakladki: `Firma`, `Nabory`, `Pomysly`, `Dopasowanie`, `Wnioski`, `Zlozenie i CRM`, `Raporty`.
- Zakladka `Raporty` pokazuje raportowanie funding z wykresami i eksportami/powiadomieniami jako obszarami do dalszego testu.

Kroki tabs/reports:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Otworz `/funding`. | Renderuje sie funding cockpit. | Widac karty i zakladki. | PASS_1 |
| 2 | Kliknij `Firma`. | Widok profilu firmy/dokumentow. | Screenshot `funding_tab_firma_pass1.png`. | PASS_1 |
| 3 | Kliknij `Nabory`. | Widok open calls. | Screenshot `funding_tab_nabory_pass1.png`. | PASS_1 |
| 4 | Kliknij `Pomysly`. | Widok idei funding. | Screenshot `funding_tab_pomys_pass1.png`. | PASS_1 |
| 5 | Kliknij `Dopasowanie`. | Widok matching/scoring. | Screenshot `funding_tab_dopasowanie_pass1.png`. | PASS_1 |
| 6 | Kliknij `Wnioski`. | Widok pakietow aplikacji. | Screenshot `funding_tab_wnioski_pass1.png`. | PASS_1 |
| 7 | Kliknij `Raporty`. | Renderuje sie panel raportow. | Po naprawie widoczne 4 wykresy, brak warnings. | 2x retest chart fix |

Opis naprawy `DASH-E2E-002`:

- Blad: po wejsciu w `Raporty` Recharts logowal ostrzezenia width/height `-1`.
- Przyczyna: `ResponsiveContainer` montowal sie, zanim aktywna zakladka miala dodatni zmierzony rozmiar.
- Naprawa: lokalny `ChartFrame` z `ResizeObserver`, render wykresu dopiero po dodatnim pomiarze kontenera.

Retesty naprawy:

| Retest | Screenshot | Wynik | Console | HTTP errors | Status |
|---|---|---|---|---|---|
| 1 | `evidence/screenshots/funding_reports_retest4_after_resize_observer.png` | `chartCount=4` | 0 | 0 | PASS |
| 2 | `evidence/screenshots/funding_reports_retest5_second_pass.png` | `chartCount=4` | 0 | 0 | PASS |

Drugi przebieg zakladek/raportow:

| Zakladka | Screenshot | Status |
|---|---|---|
| Firma | `evidence/screenshots/funding_full_pass2_tab_firma.png` | PASS |
| Nabory | `evidence/screenshots/funding_full_pass2_tab_nabory.png` | PASS |
| Pomysly | `evidence/screenshots/funding_full_pass2_tab_pomysly.png` | PASS |
| Dopasowanie | `evidence/screenshots/funding_full_pass2_tab_dopasowanie.png` | PASS |
| Wnioski | `evidence/screenshots/funding_full_pass2_tab_wnioski.png` | PASS |
| Raporty | `evidence/screenshots/funding_full_pass2_tab_raporty.png`; `chartCount=4` | PASS |

`funding_tabs_reports_pass2.json` potwierdza `consoleCount=0` i `httpErrorCount=0`.

Scenariusz pozytywny:

- Zakladka `Raporty` pokazuje 4 wykresy.
- Brak Recharts width/height warnings.
- Brak HTTP errors.

Scenariusze bledne:

- Wykresy nie renderuja sie albo `chartCount` jest mniejszy niz 4.
- Powracaja warningi Recharts width/height `-1`.
- Eksporty, profile save, idea conversion, application/submission i e-mail draft nie maja jeszcze pelnego PASS_2, wiec nie wolno oznaczac calego Funding jako `FROZEN`.

### 22.7. Settings tabs

Status freeze: `PARTIAL_2X_PASS` dla readonly tabs/secrets route  
Flow: `FLOW-011`  
Evidence: `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`, `evidence/runtime_baseline/dashboard_route_probe_pass1.md`, `evidence/runtime_baseline/settings_tabs_secrets_pass2.json`

![Settings desktop](evidence/screenshots/settings_desktop.png)

![Settings tab Klucze API](evidence/screenshots/settings_tab_keys_pass1.png)

![Settings tab Hierarchia](evidence/screenshots/settings_tab_hierarchia_pass1.png)

![Settings tab Czlonkowie rady](evidence/screenshots/settings_tab_czlonkowie_pass1.png)

![Secrets desktop](evidence/screenshots/secrets_desktop.png)

![Settings PASS 2 Czlonkowie rady](evidence/screenshots/settings_pass2_tab_czlonkowie.png)

![Secrets PASS 2 readonly](evidence/screenshots/secrets_pass2_readonly.png)

Co operator widzi:

- Ekran `Ustawienia`.
- Zakladki `Klucze API`, `Hierarchia modeli`, `Czlonkowie rady`.
- Informacje, ze zmiany hierarchii i rady sa traktowane jako D3+.
- Dla czlonkow rady widoczny stan `0 czlonkow rady` i przycisk `Dodaj czlonka`.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Otworz `/settings`. | Renderuje sie centrum konfiguracji. | Widac zakladki. | PASS_1 |
| 2 | Kliknij `Klucze API`. | Aktywna tresc przechodzi na konfiguracje kluczy. | Screenshot `settings_tab_keys_pass1.png`. | PASS_1 |
| 3 | Kliknij `Hierarchia modeli`. | Aktywna tresc przechodzi na routing/hierarchie. | Screenshot `settings_tab_hierarchia_pass1.png`. | PASS_1 |
| 4 | Kliknij `Czlonkowie rady`. | Aktywna tresc przechodzi na sklad rady. | Screenshot `settings_tab_czlonkowie_pass1.png`. | PASS_1 |
| 5 | Otworz `/secrets`. | Secrets route renderuje sie z maskowaniem/lista/formularzem. | Screenshot `secrets_desktop.png`. | PASS_1 route |
| 6 | Powtorz zakladki i `/secrets` w PASS 2. | UI uzywa rol `tab`; nie wykonuje zapisu sekretow. | `settings_tabs_secrets_pass2.json`: `consoleCount=0`, `httpErrorCount=0`. | PASS_2 readonly |

Scenariusz pozytywny:

- Zakladki przelaczaja widok.
- `/secrets` renderuje sie bez route error.

Scenariusze bledne:

- Zakladki nie zmieniaja panelu.
- Sekret jest pokazany jawnie po zapisie.
- Dodanie/walidacja klucza nie jest jeszcze freeze-pass; kontrolowany dummy secret scenario jest pending.

### 22.8. Operator Mobile queue

Status freeze: `PARTIAL_2X_PASS` dla queue navigation  
Flow: `FLOW-010`  
Evidence: `evidence/runtime_baseline/dashboard_human_interactions_pass1.md`, `evidence/runtime_baseline/dashboard_route_probe_pass1.md`, `evidence/runtime_baseline/operator_mobile_queue_pass2.json`

![Operator mobile home](evidence/screenshots/operator_mobile_home_pass1.png)

![Operator mobile queue after click](evidence/screenshots/operator_mobile_queue_after_click_pass1.png)

![Operator mobile mobile viewport](evidence/screenshots/operator-mobile_mobile.png)

![Operator mobile PASS 2 home](evidence/screenshots/operator_mobile_pass2_home_mobile.png)

![Operator mobile PASS 2 queue](evidence/screenshots/operator_mobile_pass2_queue_mobile.png)

Co operator widzi:

- Home operator-mobile prowadzi do kolejki decyzji.
- Po kliknieciu kolejki final URL to `http://127.0.0.1:3001/operator-mobile/queue`.
- Kolejka pokazuje pending approvals dla `operator-main`, m.in. wpisy P0/P2 z przyciskami `Open Detail`, `Approve`, `Reject`.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Status |
|---|---|---|---|---|
| 1 | Otworz `/operator-mobile`. | Renderuje sie landing mobile/operator. | Widoczne wejscie do kolejki. | PASS_1 |
| 2 | Kliknij przejscie do queue. | UI nawiguje do `/operator-mobile/queue`. | Final URL zgodny z evidence. | PASS_1 |
| 3 | Obejrzyj liste ticketow. | Widac pending approvals i akcje. | Lista nie jest pusta w PASS_1. | PASS_1 |
| 4 | Powtorz na mobilnym viewport PASS 2. | UI przechodzi do `/operator-mobile/queue`. | `operator_mobile_queue_pass2.json`: final URL `/operator-mobile/queue`, console 0, HTTP >=400 0. | PASS_2 |

Scenariusz pozytywny:

- Queue navigation dziala.
- Lista ticketow jest widoczna.

Scenariusze bledne:

- Home nie nawiguje do `/operator-mobile/queue`.
- Queue jest pusta mimo backend pending tickets.
- Przyciski `Approve`/`Reject` na realnych ticketach nie powinny byc klikane bez osobnego kontrolowanego scenariusza.

### 22.9. W18 project terminal freeze/build

Status freeze: `2X_PASS` dla projektu W18: `zamroz ksiege`, `zamroz masterplan`, `autoryzuj budowe`, kontrola przez `/human-gate`  
Flow: `FLOW-013`  
Evidence: `../w18_router_repair/evidence/json/w18_router_dashboard_pass12_reconstructed_2026-05-13.json`, `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`, `../w18_router_repair/evidence/screenshots/`

![W18 PASS 2 freeze canon](../w18_router_repair/evidence/screenshots/pass2_freeze_canon_project_f3e237d2a95b_2026-05-13T22-03-46-999Z.png)

![W18 PASS 2 Human Gate canon before](../w18_router_repair/evidence/screenshots/pass2_human_gate_canon_before_5b354f302389_2026-05-13T22-03-46-999Z.png)

![W18 PASS 2 Human Gate canon after](../w18_router_repair/evidence/screenshots/pass2_human_gate_canon_after_5b354f302389_2026-05-13T22-03-46-999Z.png)

![W18 PASS 2 authorize build](../w18_router_repair/evidence/screenshots/pass2_authorize_build_project_f3e237d2a95b_2026-05-13T22-03-46-999Z.png)

Co operator widzi:

- W szczegole projektu jest projektowy terminal W18.
- Po komendzie mutujacej terminal nie wykonuje lokalnej zmiany w UI. Wysyla komende do backendowego `/api/v1/terminal/exec`.
- Odpowiedz backendu zawiera route contract: `command_intent`, `command_route`, `command_execution`.
- Dla `zamroz ksiege` powstaje Human Gate ticket `project_freeze/canon`, `decision_class=D3`, `phase=TWO_PHASE`.
- Dla `zamroz masterplan` powstaje Human Gate ticket `project_freeze/masterplan`, `decision_class=D4`, `phase=TWO_PHASE`.
- Dla `autoryzuj budowe` powstaje Human Gate ticket `project_build_authorize/build`, `decision_class=D4`, `phase=TWO_PHASE`.
- Po zatwierdzeniu w `/human-gate` projekt ma odpowiednio `canon_frozen_at`, `masterplan_frozen_at`, `build_authorized_at`, a `pending_governance_count` wraca do 0.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu/wpisie | Oczekiwany wynik | Evidence |
|---|---|---|---|---|
| 1 | Otworz `/projects/[projectId]`. | Dashboard pobiera stan projektu i pokazuje terminal W18. | Projekt jest zgodny z ID testowym, nie z innym workspace. | PASS1 `project_ca111ec23cf2`, PASS2 `project_f3e237d2a95b` |
| 2 | Wpisz `zamroz ksiege` w terminal W18. | Frontend wysyla komende do `/api/v1/terminal/exec` z `source_surface=project_w18_terminal` i `project_id`. | Powstaje ticket Human Gate dla canon/source-of-truth; terminal pokazuje odpowiedz z ID ticketa. | `pass*_freeze_canon_*.png`; audit JSONL |
| 3 | Otworz `/human-gate` i zatwierdz ticket canon. | Human Gate wykonuje approval hook. | Ticket przechodzi na `approved`; projekt dostaje `canon_frozen_at`. | `pass*_human_gate_canon_before_*.png`, `pass*_human_gate_canon_after_*.png` |
| 4 | Wpisz `zamroz masterplan`. | Backend tworzy route `freeze_masterplan`, `decision_class=D4`, `requires_human_gate=true`. | Powstaje ticket masterplan i po approval projekt dostaje `masterplan_frozen_at`. | `pass*_freeze_masterplan_*.png`; `pass*_human_gate_masterplan_*` |
| 5 | Wpisz `autoryzuj budowe`. | Backend tworzy route `authorize_build`; build nie rusza bez approval. | Powstaje ticket build i po approval projekt dostaje `build_authorized_at`. | `pass*_authorize_build_*.png`; `pass*_human_gate_build_*` |
| 6 | Wpisz `bramka czlowieka`. | Backend odczytuje ticket state dla projektu. | Brak pending ticketow po approval, `pending_governance_count=0`. | `pass*_human_gate_status_*.png` |

Scenariusz pozytywny:

- Kazda komenda mutujaca ma jeden wlasciciel (`project_mode.round_meta`) i jawny target projektu.
- Kazda decyzja D3/D4 idzie przez `TWO_PHASE` i Human Gate.
- Approval zmienia stan projektu, a nie tylko status ticketa.
- `command_router_audit.jsonl` ma wpis z ownerem, route, decision class, ticket ID i command bus intent ID.
- Ten sam scenariusz przechodzi dwa razy na dwoch projektach kontrolnych.

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| Komenda trafia tylko do frontendu | Terminal pokazuje sukces bez ticket ID. | Brak wpisu `command_router_audit.jsonl`. | Oznacz `FULL-AUD-001` jako regresje i nie zamrazaj flow. | WATCH |
| Ticket nie pojawia sie w `/human-gate` | Terminal mowi o bramce, ale kolejka jest pusta. | `pending_governance_ticket_id` pusty albo ticket nie istnieje. | Oznacz `FULL-AUD-002` jako regresje. | WATCH |
| Approval nie zmienia projektu | Ticket ma `approved`, ale projekt nie ma timestampu. | Brak `canon_frozen_at`, `masterplan_frozen_at` albo `build_authorized_at`. | Nie uruchamiaj kolejnego kroku budowy. | WATCH |
| Execution-start wraca do osobnego kanalu komend | `/execution-start` pokazuje `w18_commands` bez `command_route`. | Brak wpisu w centralnym routerze dla tej akcji. | Oznacz `FULL-AUD-005` jako regresje i nie zamrazaj `FLOW-014`. | WATCH |

Rollback / bezpieczne przerwanie:

- Jezeli ticket jest pending i operator nie chce kontynuowac, nie klikac approve; ticket zostaje dowodem blokady.
- Jezeli approval byl bledny, nie usuwac eventow ani audit logow; dopisac correction/rollback event zgodnie z append-only policy.
- Nie oznaczac calego systemu jako `FROZEN`; zamrozony jest tylko zakres W18 project terminal freeze/build.

Uwagi freeze:

- PASS1: `project_ca111ec23cf2`, ticket canon `40382a65776546ac985dfe21022ee8f3`, masterplan `acef8fb4486b40da8d1030c3c32d141b`, build `6ade1fe12fe645169f9739403a241c35`.
- PASS2: `project_f3e237d2a95b`, ticket canon `5b354f30238942fc816f660204b42002`, masterplan `f31334978b9e4898b307cfe668158c92`, build `8b73aa796cd4454e9293af09a7dcc20b`.
- Execution-start Phase 32/33 jest wlaczony do tego samego routera w sekcji 22.11. Nadal nie oznacza to zamrozenia calego execution.

### 22.10. Route-only partial surfaces

Status freeze: `PARTIAL_ROUTE_2X`  
Flow: `FLOW-005`, `FLOW-006`, `FLOW-009`, `FLOW-012`  
Evidence: `evidence/runtime_baseline/dashboard_route_probe_pass1.md`, `evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.md`

Te powierzchnie maja 2x PASS tylko dla wejscia na trase, renderu ekranu, braku browser console errors/warnings i braku HTTP >=400. To nie jest dowod pelnych akcji takich jak start/stop execution, memory write, replay event search albo drilldown metryk.

Uwaga dla `FULL-AUD-006`: stare `net::ERR_ABORTED` z route smoke zostaly sprawdzone osobno. Dwa przebiegi direct endpoint + route reprobe (`full_aud_006_route_failure_probe_2026-05-13T22-28-10-448Z.json` i `full_aud_006_route_failure_probe_pass2_2026-05-13T22-29-13-370Z.json`) maja `directFailures=0` i `routeFailures=0`, wiec nie sa aktywnym blockerem freeze.

![Execution start PASS 2](evidence/screenshots/execution-start_desktop_pass2_after_d004.png)

![Workers PASS 2](evidence/screenshots/workers_desktop_pass2_after_d004.png)

![Orchestration PASS 2](evidence/screenshots/orchestration_desktop_pass2_after_d004.png)

![Memory PASS 2](evidence/screenshots/memory_desktop_pass2_after_d004.png)

![Audit PASS 2](evidence/screenshots/audit_desktop_pass2_after_d004.png)

![Evidence PASS 2](evidence/screenshots/evidence_desktop_pass2_after_d004.png)

![Replay PASS 2](evidence/screenshots/terminal__replay_desktop_pass2_after_d004.png)

![Observability PASS 2](evidence/screenshots/observability_desktop_pass2_after_d004.png)

| Flow | Trasy | Potwierdzone | Niepotwierdzone |
|---|---|---|---|
| Execution | `/execution-start`, `/workers`, `/orchestration` | 2x route render, Phase 32/33, live worker smoke start/stop, dispatch control, phases 34-41, workers registry lifecycle, screenshots, console 0, HTTP >=400 0 | `/orchestration` action drilldown; topology create/update UI is not available on `/workers` |
| Memory | `/memory` | 2x route render, screenshots, console 0, HTTP >=400 0 | Search, evidence write/read, refresh persistence |
| Audit/evidence/replay | `/audit`, `/evidence`, `/terminal/replay` | 2x route render, screenshots, console 0, HTTP >=400 0 | Odnalezienie konkretnego eventu, replay playback, evidence integrity drilldown |
| Observability/readiness | `/observability`, `/runtime`, `/health` | 2x route render, screenshots, console 0, HTTP >=400 0 | Metrics drilldown, readiness remediation actions, config save |

### 22.11. Execution-start W18 router Phase 32-33

Status freeze: `2X_PASS` dla zakresu: `Zapisz runtime`, `Zainicjuj budowe`, `Start wykonania`  
Flow: `FLOW-014`  
Evidence: `../execution_start_router_repair/evidence/json/execution_start_dashboard_pass12_2026-05-13T22-23-31-684Z.json`, `../execution_start_router_repair/evidence/screenshots/`, `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`

![Execution-start PASS 2 loaded](../execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_loaded.png)

![Execution-start PASS 2 runtime saved](../execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_runtime_saved.png)

![Execution-start PASS 2 phase 32](../execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_phase32_initialized.png)

![Execution-start PASS 2 phase 33](../execution_start_router_repair/evidence/screenshots/pass2_project_97bfd7670d3d_2026-05-13T22-23-31-684Z_phase33_started.png)

Co operator widzi:

- `/execution-start` pokazuje aktywny projekt z backendu.
- `Zapisz runtime` zapisuje topologie, liczbe lokalnych workerow, VPS=0 i limit rownoleglosci.
- `Zainicjuj budowe` tworzy Phase 32 build initialization: worker ownership, srodowiska, repo/worktree plan i governance ticket.
- `Start wykonania` tworzy Phase 33 sequential execution: lokalne worker evidence, logi, diffy, test-result JSON i governance ticket.
- Lokalna lista `execution.w18_commands` nadal istnieje dla UI, ale kazdy wpis ma tez `command_intent`, `command_route`, `command_execution`.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|
| 1 | Otworz `/execution-start`. | Dashboard pobiera aktywny projekt. | Na ekranie widac `project_id` kontrolnego projektu. | `*_loaded.png` |
| 2 | Ustaw `Topologia=local-only`, `Lokalni wykonawcy=2`, `VPS=0`, `Srodowiska=2`, `Rownoleglosc=2`. | UI przygotowuje payload runtime. | Brak ostrzezen i request failures. | JSON PASS1/PASS2 |
| 3 | Kliknij `Zapisz runtime`. | Backend zapisuje runtime config i dopisuje W18 route `runtime_configuration`. | W `w18_commands` jest `command_route.owner=execution_start.runtime_configuration`. | `*_runtime_saved.png` |
| 4 | Kliknij `Zainicjuj budowe`. | Backend uruchamia Phase 32 i dopisuje W18 route `initialize_build`. | Wpis ma `decision_class=D3`, `phase=TWO_PHASE`, governance ticket ID. | `*_phase32_initialized.png` |
| 5 | Kliknij `Start wykonania`. | Backend uruchamia Phase 33 i dopisuje W18 route `start_sequential_execution`. | `real_execution_evidence.status=live_verified_local`, `artifacts_written=10`, worker logs/diffs/tests sa zapisane. | `*_phase33_started.png` |

Scenariusz pozytywny:

- PASS1 i PASS2 maja 0 browser console warnings/errors oraz 0 request failures.
- `w18_commands` zawiera route actions: `runtime_configuration`, `initialize_build`, `start_sequential_execution`.
- Phase 33 ma `governance_ticket_id` i worker evidence `live_verified_local`.
- `command_router_audit.jsonl` zawiera te same route actions z ownerem i target project ID.

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| Runtime save nie ma centralnego route | UI pokazuje sukces, ale `w18_commands` nie ma `command_route`. | Brak wpisu `runtime_configuration` w `command_router_audit.jsonl`. | Nie zamrazac `FULL-AUD-005`. | WATCH |
| Phase 33 nie tworzy W18 entry | Start wykonania zmienia projekt, ale ledger milczy. | Brak `start_sequential_execution`. | Oznacz `FULL-AUD-007` jako regresje. | WATCH |
| Worker evidence puste | Postep budowy widoczny, ale brak worker artifacts. | `real_execution_evidence.status` inny niz `live_verified_local`. | Nie uznawac wykonania za PASS. | WATCH |
| Dispatch/cancel regresja | `Pauza`, `Wznow` albo `Anuluj` nie zmienia stanu dispatch. | Brak route `pause_dispatch`, `resume_dispatch` albo `cancel_dispatch`. | Nie zamrazac FLOW-017, otworzyc bug P1. | WATCH |

Uwagi freeze:

- PASS1: `project_941d83cdd5d9`, worker run `wr_1778711023104`, `workers_completed=2`, `artifacts_written=10`.
- PASS2: `project_97bfd7670d3d`, worker run `wr_1778711035018`, `workers_completed=2`, `artifacts_written=10`.
- Zamrozony jest routing W18, Phase 32/33 worker evidence, live smoke worker start/stop z sekcji 22.12, phases 34-41 z sekcji 22.13 oraz dispatch control z sekcji 22.14.

### 22.12. Execution-start live smoke workers

Flow: `FLOW-015`  
Evidence: `../execution_live_workers/evidence/json/live_workers_dashboard_pass12_2026-05-13T22-40-42-350Z.json`, `../execution_live_workers/evidence/screenshots/`, `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`

![Live workers PASS 2 started](../execution_live_workers/evidence/screenshots/live_workers_2026-05-13T22-40-42-350Z_pass2_started.png)

![Live workers PASS 2 stopped](../execution_live_workers/evidence/screenshots/live_workers_2026-05-13T22-40-42-350Z_pass2_stopped.png)

Co operator widzi:

- Sekcja `Live smoke workers` pokazuje backend, liczbe uruchomionych workerow, tryb/czas i status kosztow zewnetrznych.
- `Start live` uruchamia lokalne procesy smoke worker w `windows_process_group`.
- `Stop live` zatrzymuje procesy i zostawia `running=0`.
- `Odswiez` pobiera aktualny status PID/log lines/state.
- Flow nie uruchamia Dockera, VPS ani produkcyjnego deploy.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|
| 1 | Otworz `/execution-start`. | Dashboard pobiera aktywny projekt i status live workers. | Sekcja `Live smoke workers` jest widoczna. | `*_loaded.png` |
| 2 | Kliknij `Start live`. | Backend tworzy governance ticket D3, uruchamia 2 lokalne procesy smoke worker i dopisuje W18 route `live_spawn_workers`. | UI pokazuje `2/2`, API ma `running=2`, logi workerow maja heartbeat. | `*_pass1_started.png`, `*_pass2_started.png` |
| 3 | Kliknij `Stop live`. | Backend zatrzymuje procesy i dopisuje W18 route `stop_live_workers`. | UI/API pokazuja `running=0`; route ma `phase=IMMEDIATE`. | `*_pass1_stopped.png`, `*_pass2_stopped.png` |
| 4 | Sprawdz JSON evidence. | Proba porownuje W18 commands i status procesow. | `consoleErrors=0`, `requestFailures=0`, route actions obecne. | JSON PASS1/PASS2 |

Scenariusz pozytywny:

- PASS1 i PASS2 maja `Start live -> 2 running`, `Stop live -> 0 running`.
- Browser evidence ma `consoleErrors=0` i `requestFailures=0`.
- `w18_commands` zawiera `live_spawn_workers` i `stop_live_workers`.
- `command_router_audit.jsonl` ma te same target actions.

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| Start live bez route | UI pokazuje workerow, ale brak `command_route`. | Brak `live_spawn_workers` w audit logu. | Oznacz `DASH-E2E-008` jako regresje. | WATCH |
| Stop live nie zatrzymuje procesow | Po kliknieciu dalej widac running > 0. | `live_spawn.running` nie spada do 0. | Nie zamrazac flow, zatrzymac procesy awaryjnie i zapisac PID. | WATCH |
| Console error po otwarciu | Dashboard dziala, ale konsola ma React/runtime error. | Evidence `consoleErrors > 0`. | Nie zamrazac do czasu retestu z konsola 0. | WATCH |
| Docker/VPS live spawn | Operator oczekuje kontenerow albo VPS. | Ten flow ma `allow_docker_run=false`, `external_cost=false`. | Traktowac jako osobny flow, nie rozszerzac tego freeze. | OPEN |

Uwagi freeze:

- PASS1 i PASS2 wykonano na projekcie `project_97bfd7670d3d`, bo dashboard `/execution-start` ma jeden aktywny projekt. Dowod obejmuje dwa oddzielne cykle start/stop z nowymi PID.
- Zamrozony jest tylko local smoke start/stop. Nie jest to produkcyjny worker pool, Docker ani VPS.

### 22.13. Execution-start phases 34-41 closeout

Status freeze: `2X_PASS` dla zakresu: Phase 34-41 w dashboardzie `/execution-start`  
Flow: `FLOW-016`  
Evidence: `../execution_phases_34_41/evidence/json/execution_phases_34_41_pass12_2026-05-14T09-40-35-269Z.json`, `../execution_phases_34_41/evidence/screenshots/`, `../execution_phases_34_41/EXECUTION_PHASES_34_41_PASS12.md`, `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`

![Execution phases 34-41 PASS 2 phase 34](../execution_phases_34_41/evidence/screenshots/execution_34_41_2026-05-14T09-40-35-269Z_pass2_phase34.png)

![Execution phases 34-41 PASS 2 phase 41](../execution_phases_34_41/evidence/screenshots/execution_34_41_2026-05-14T09-40-35-269Z_pass2_phase41.png)

Co operator widzi:

- `Zwolaj rade` uruchamia Phase 34, zapisuje decyzje rady i W18 route `reconvene_mid_build_council`.
- `Uruchom orkiestracje` uruchamia Phase 35 i W18 route `activate_orchestration`.
- `Zamknij budowe` uruchamia Phase 36, generuje inventory/summary i W18 route `complete_build`.
- `Bramki jakosci` uruchamia Phase 37, zapisuje L1-L5 quality gates i W18 route `run_quality_gates`.
- `Akceptacja klienta` uruchamia Phase 38, zapisuje signoff i W18 route `complete_acceptance_testing`.
- `Zatwierdz kontrole` uruchamia Phase 39, tworzy governance ticket i W18 route `authorize_predeploy`.
- `Wdrozenie / proba` uruchamia Phase 40, tworzy governance ticket i W18 route `execute_production_deploy`.
- `Zamknij projekt` uruchamia Phase 41, zapisuje closure/archive/memory sync i W18 route `close_project`.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik |
|---|---|---|---|
| 1 | Otworz `/execution-start`. | Dashboard pobiera aktywny projekt po Phase 33. | Fazy 34-41 sa dostepne jako akcje operatora. |
| 2 | Klikaj kolejno Phase 34-41. | Kazda akcja wykonuje POST do backendu i odswieza akceptacje aktywnej fazy. | `accepted=true`, `hard_blocks=0`. |
| 3 | Sprawdz W18. | Kazda akcja dopisuje `command_intent`, `command_route`, `command_execution`. | Owner/action/decision class zgadzaja sie z tabela ponizej. |
| 4 | Powtorz caly zestaw drugi raz. | Drugi przebieg ponownie zapisuje artefakty i W18 route. | Projekt konczy w stanie `CLOSED`; brak bledow konsoli i API. |

Kontrakt W18:

| Phase | Owner | Target action | Decision class |
|---|---|---|---|
| 34 | `execution_start.phase34` | `reconvene_mid_build_council` | `D4` |
| 35 | `execution_start.phase35` | `activate_orchestration` | `D3` |
| 36 | `execution_start.phase36` | `complete_build` | `D3` |
| 37 | `execution_start.phase37` | `run_quality_gates` | `D3` |
| 38 | `execution_start.phase38` | `complete_acceptance_testing` | `D4` |
| 39 | `execution_start.phase39` | `authorize_predeploy` | `D4` |
| 40 | `execution_start.phase40` | `execute_production_deploy` | `D5` |
| 41 | `execution_start.phase41` | `close_project` | `D4` |

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| Brak W18 route dla fazy | Akcja konczy sie sukcesem, ale ostatni `w18_command` nie ma `command_route`. | Brak owner/action/decision class w `command_router_audit.jsonl`. | Nie zamrazac fazy, otworzyc bug P1. | WATCH |
| Impossible quorum | Phase 34 ma `accepted=false`, hard block `weighted_votes`. | `quorum.configured_required_roles` wieksze niz liczba rol. | System powinien uzyc efektywnego quorum ograniczonego do zaproszonych rol i zachowac configured value w evidence. | WATCH |
| Phase 39/40 bez governance ticket | UI przechodzi dalej bez ticket ID. | `command_execution.governance_ticket_id` puste dla 39/40. | Nie zamrazac, bo akcje D4/D5 musza miec governance trace. | WATCH |
| Reload abort | Po reloadzie test widzi `GET net::ERR_ABORTED`. | Brak HTTP >=400 i brak POST failure. | Klasyfikowac jako benign reload abort, nie jako blad akcji. | WATCH |

Uwagi freeze:

- PASS1 i PASS2 wykonano na projekcie `proj_3505bd6a1892`.
- Evidence ma `consoleErrors=0`, `requestFailures=0`, `apiFailures=0`; cztery `GET net::ERR_ABORTED` sa zapisane osobno jako benign reload aborts.
- Zamrozony jest closeout Phase 34-41. Dispatch/cancel jest zamrozony osobno w sekcji 22.14, a `/workers` registry w sekcji 22.15. `/orchestration` drilldown pozostaje poza tym freeze.

### 22.14. Execution-start dispatch control

Status freeze: `2X_PASS` dla zakresu: `Start wykonania`, `Pauza`, `Wznow`, `Anuluj` w Phase 33  
Flow: `FLOW-017`  
Evidence: `../execution_dispatch_control/evidence/json/execution_dispatch_control_pass12_2026-05-14T09-58-40-542Z.json`, `../execution_dispatch_control/evidence/screenshots/`, `../execution_dispatch_control/EXECUTION_DISPATCH_CONTROL_PASS12.md`, `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`

![Dispatch control PASS 2 cancel](../execution_dispatch_control/evidence/screenshots/2026-05-14T09-58-40-542Z_pass2_cancel.png)

![Dispatch control mobile final](../execution_dispatch_control/evidence/screenshots/2026-05-14T09-58-40-542Z_mobile_final_dashboard.png)

Co operator widzi:

- Sekcja `Dispatch control` pokazuje stan dispatchu, `run_id`, ownera, target resolution, worker pool i env pool.
- `Pauza` jest aktywna tylko gdy dispatch ma stan `running`.
- `Wznow` jest aktywne tylko gdy dispatch ma stan `paused`.
- `Anuluj` jest aktywne tylko gdy dispatch ma stan `running` albo `paused`.
- Po anulowaniu wszystkie kontrolki mutujace sa nieaktywne, a ostatni event pokazuje `/dispatch cancel`.

Reguly wlasciciela komend:

| Regula | Wartosc |
|---|---|
| Owner | `execution_start.dispatch_control` |
| Target resolution | `project_id -> phase33 dispatch -> worker_pool -> local_environment` |
| Worker/model/env rule | Komenda moze targetowac workera, model albo srodowisko tylko wewnatrz aktywnego projektu. |
| External runtime rule | VPS, Docker i production effects zostaja zablokowane bez osobnej Human Gate dla runtime. |
| Precedence | `cancel`, potem `pause`, potem `resume`, potem start phase33. |

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|
| 1 | Otworz `/execution-start`. | Dashboard pobiera aktywny projekt i GET `/phase33/dispatch-control`. | Sekcja `Dispatch control` jest widoczna. | `*_initial_dashboard.png` |
| 2 | Kliknij `Start wykonania`. | Backend tworzy/odswieza Phase 33 sequential execution i ustawia dispatch `running`. | UI pokazuje `Stan=running`, `run_id`, worker/env pool. | `*_pass1_start.png`, `*_pass2_start.png` |
| 3 | Kliknij `Pauza`. | POST `/phase33/pause-dispatch`; backend zapisuje event `dispatch_paused`, W18 `/dispatch pause`, decision `D3`. | UI/API maja `state=paused`; aktywne jest `Wznow`. | `*_pass1_pause.png`, `*_pass2_pause.png` |
| 4 | Kliknij `Wznow`. | POST `/phase33/resume-dispatch`; backend zapisuje event `dispatch_resumed`, W18 `/dispatch resume`, decision `D3`. | UI/API wracaja do `state=running`; aktywne sa `Pauza` i `Anuluj`. | `*_pass1_resume.png`, `*_pass2_resume.png` |
| 5 | Kliknij `Anuluj`. | POST `/phase33/cancel-dispatch`; backend zapisuje event `dispatch_cancelled`, W18 `/dispatch cancel`, decision `D4`. | UI/API maja `state=cancelled`; mutujace kontrolki sa nieaktywne. | `*_pass1_cancel.png`, `*_pass2_cancel.png` |
| 6 | Powtorz kroki 2-5. | Drugi przebieg sprawdza idempotentny reset przez start i ponowne pause/resume/cancel. | `PASS_2X`, console errors 0, hard request failures 0, API failures 0. | JSON PASS12 |

Kontrakt W18:

| Komenda | Owner | Target action | Decision class | Phase | Human Gate |
|---|---|---|---|---|---|
| `/dispatch pause` | `execution_start.dispatch_control` | `pause_dispatch` | `D3` | `TWO_PHASE` | wymagany |
| `/dispatch resume` | `execution_start.dispatch_control` | `resume_dispatch` | `D3` | `TWO_PHASE` | wymagany |
| `/dispatch cancel` | `execution_start.dispatch_control` | `cancel_dispatch` | `D4` | `TWO_PHASE` | wymagany |

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| Pauza bez startu | `Pauza` nieaktywna albo API 409. | `phase33 execution must be started first`. | Najpierw kliknij `Start wykonania`; nie obchodzic kolejki stanem recznym. | EXPECTED |
| Wznow bez pauzy | `Wznow` nieaktywne albo API 409. | `dispatch must be paused before resume`. | Sprawdz `state`; wznowienie tylko po `paused`. | EXPECTED |
| Anuluj po cancel | `Anuluj` nieaktywne albo API 409. | `dispatch can be cancelled only while running or paused`. | Aby testowac ponownie, kliknij `Start wykonania`, ktory tworzy nowy running run. | EXPECTED |
| Brak W18 route | Klik dziala, ale ledger nie pokazuje owner/action/decision. | Brak `pause_dispatch`, `resume_dispatch` albo `cancel_dispatch` w W18. | Nie zamrazac FLOW-017; otworzyc P1. | WATCH |

Uwagi freeze:

- PASS1 i PASS2 wykonano na projekcie `project_97bfd7670d3d`.
- Finalny stan po PASS2: `dispatch_control.state=cancelled`, `progress_status=cancelled`, `timeline_status=cancelled_by_operator`.
- Evidence ma `consoleErrors=0`, `hardRequestFailures=0`, `apiFailures=0`.
- Zamrozony jest tylko Phase 33 dispatch control. `/workers` registry jest zamrozony osobno w sekcji 22.15, a `/orchestration` drilldown pozostaje osobnym flow.

### 22.15. Workers registry i topologie

Status freeze: `2X_PASS` dla zakresu: topologie, rejestracja workera, heartbeat, rebalans, widok per projekt i usuniecie workera  
Flow: `FLOW-018`  
Evidence: `../workers_registry/evidence/json/workers_registry_pass12_2026-05-14T10-27-39-815Z.json`, `../workers_registry/evidence/json/workers_topology_repro_2026-05-14T10-20-56-040Z.json`, `../workers_registry/evidence/screenshots/`, `../workers_registry/WORKERS_REGISTRY_PASS12.md`

![Workers PASS 2 registered](../workers_registry/evidence/screenshots/workers_pass2_registered_2026-05-14T10-27-39-815Z.png)

![Workers PASS 2 per project](../workers_registry/evidence/screenshots/workers_pass2_per_project_2026-05-14T10-27-39-815Z.png)

![Workers PASS 2 deleted](../workers_registry/evidence/screenshots/workers_pass2_deleted_2026-05-14T10-27-39-815Z.png)

Co operator widzi:

- Naglowek `Flota wykonawcow` pokazuje status live backendu i glowne akcje: `Odswiez`, `Zarejestruj wykonawce`, `Rebalansuj`.
- Karty statystyk pokazuja liczbe workerow, aktywnych, offline, laczna pojemnosc i obciazenie.
- Zakladka `Wszyscy wykonawcy` pokazuje globalna pule workerow; klikniecie karty otwiera szczegoly.
- Zakladka `Per projekt` filtruje workerow po `project_id`, tagu `project:{id}` albo `assigned_projects`.
- Sekcja `Topologie buildow` pokazuje rekordy z `/api/v1/workers/topology/all`; nie wolno jej uznac za pusta, gdy API zwraca topologie.

Kroki operatora:

| Krok | Akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|
| 1 | Otworz `/workers`. | Dashboard pobiera `GET /api/v1/workers` i `GET /api/v1/workers/topology/all`. | Workerzy i topologie sa zgodne z API; brak error banneru. | `workers_pass*_topology_visible_*.png` |
| 2 | Kliknij `Zarejestruj wykonawce`. | Otwiera sie formularz: nazwa, host, pojemnosc, tagi. | Formularz nie mutuje backendu przed kliknieciem `Zarejestruj`. | `workers_pass*_registered_*.png` |
| 3 | Wpisz nazwe workera, host, pojemnosc i tagi, potem kliknij `Zarejestruj`. | `POST /api/v1/workers`; po sukcesie formularz sie zamyka i lista workerow odswieza. | Worker jest widoczny w UI i w API. | JSON PASS12 `registered_api=true`, `registered_dashboard=true` |
| 4 | Kliknij karte workera i potem `Heartbeat`. | `POST /api/v1/workers/{worker_id}/heartbeat`. | `last_heartbeat` rosnie lub jest rowny nowszej wartosci; UI nie pokazuje bledu. | `workers_pass*_heartbeat_*.png` |
| 5 | Kliknij `Rebalansuj`. | `POST /api/v1/workers/assignments/rebalance`; lista workerow i topologii jest odswiezana. | Brak error banneru `Operacja wykonawcy nieudana`. | JSON PASS12 `rebalance_clicked_without_error_banner=true` |
| 6 | Przejdz do `Per projekt`. | Dashboard pobiera projekty i filtruje workerow po tagu `project:{project_id}`. | Worker z tagiem projektu jest widoczny w tej zakladce. | `workers_pass*_per_project_*.png` |
| 7 | Wroc do `Wszyscy wykonawcy`, kliknij worker i `Usun`. | `DELETE /api/v1/workers/{worker_id}` zwraca `204 No Content`; frontend traktuje pusty body jako sukces. | Worker znika z API i dashboardu; brak error banneru. | `workers_pass*_deleted_*.png` |
| 8 | Powtorz kroki 1-7 drugi raz. | Drugi przebieg sprawdza powtarzalnosc i brak starych stanow. | `PASS_2X`, console errors 0, hard request failures 0, API failures 0. | JSON PASS12 |

Kontrakt API/UI:

| Obszar | Endpoint | Regula |
|---|---|---|
| Lista workerow | `GET /api/v1/workers` | UI nie moze syntetyzowac workerow; pusta lista musi byc rzeczywista. |
| Rejestracja | `POST /api/v1/workers` | Wymagana nazwa; host domyslnie `localhost`; tagi sa rozdzielane przecinkami. |
| Heartbeat | `POST /api/v1/workers/{worker_id}/heartbeat` | Sukces musi zwrocic worker i `heartbeat_recorded=true`. |
| Delete | `DELETE /api/v1/workers/{worker_id}` | `204 No Content` jest sukcesem, nie bledem JSON. |
| Topologie | `GET /api/v1/workers/topology/all` | UI czyta pole `topologies`; brak topologii w UI jest poprawny tylko przy pustej tablicy API. |
| Per projekt | tag `project:{project_id}` | Worker z tagiem projektu musi pojawic sie w zakladce per-projekt. |

Scenariusze bledne:

| Blad | Objaw w UI | Objaw API/log | Co operator robi | Status |
|---|---|---|---|---|
| API ma topologie, UI pokazuje pustke | `Brak wygenerowanych topologii` mimo seeded topology. | `/api/v1/workers/topology/all` zawiera rekord. | Nie zamrazac; to regresja `DASH-E2E-011`. | RESOLVED_2X_PASS |
| Delete zwraca blad JSON | Banner `Operacja wykonawcy nieudana`, tekst `Unexpected end of JSON input`. | `DELETE` ma status `204`, worker znika z API. | Nie klikac ponownie w ciemno; sprawdz API i request helper. | RESOLVED_2X_PASS |
| Worker nie znika po delete | Karta workera zostaje po odswiezeniu. | API nadal zawiera `worker_id` albo UI nie odswieza. | Jesli API zawiera worker, delete nie przeszedl; jesli API nie zawiera, to bug UI cache. | WATCH |
| Per projekt pusty | Zakladka nie pokazuje workera. | Worker nie ma `project_id`, `assigned_projects` ani tagu `project:{id}`. | Dodaj tag projektu albo przypisanie przez scheduler; nie uznawac za blad listy globalnej. | EXPECTED |

Uwagi freeze:

- PASS1 i PASS2 wykonano z projektem `project_97bfd7670d3d`.
- Evidence ma `consoleErrors=0`, `hardRequestFailures=0`, `apiFailures=0`.
- Zamrozony jest `/workers` registry lifecycle i odczyt topologii.
- Tworzenie/edycja topologii z UI nie jest zamrozone, bo dashboard nie ma osobnej kontrolki create/update topology.
- `/orchestration` drilldown J1-J9 jest zamrozony osobno w sekcji 22.16.

### 22.16. Orchestration J1-J9 drilldown

Status freeze: `2X_PASS` dla huba `/orchestration` oraz podtras J1-J9  
Flow: `FLOW-019`  
Evidence: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\orchestration_drilldown\evidence\json\orchestration_drilldown_pass12_2026-05-14T10-54-40-012Z.json`  
Screenshots: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\orchestration_drilldown\evidence\screenshots\*2026-05-14T10-54-40-012Z.png`

![Orchestration PASS 1 hub](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_hub_2026-05-14T10-54-40-012Z.png)

![Orchestration PASS 2 hub](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_hub_2026-05-14T10-54-40-012Z.png)

Co operator widzi:

- Hub `/orchestration` pokazuje powierzchnie `Meta-Orkiestracja`, status live oraz kafle nawigacyjne J1-J9: routing LLM, reguly rady, rytm audytora, protokol fixera, dispatch agentow, katalog testow, formowanie zespolow, mape zdarzen i rozmowy modeli.
- Kazda podtrasa ma wlasny naglowek, HelpTip, akcje `Odswiez` oraz akcje mutujace wlasciwe dla danego modulu.
- FLOW-019 potwierdzil dwa pelne przebiegi: hub + J1-J9. Evidence ma `console_errors=[]`, `page_errors=[]`, `request_failures=[]`, `hard_request_failures=[]`, `api_failures=[]`.

Kroki operatora:

| Krok | Trasa | Klik/akcja | Co dzieje sie po kliknieciu | Oczekiwany wynik | Evidence |
|---|---|---|---|---|---|
| 1 | `/orchestration` | Otworz hub Meta-Orkiestracji. | UI laduje katalog J1-J9 i status powierzchni orchestration. | Widoczne sa wszystkie kafle J1-J9 bez stuck loading i bez bledu runtime. | `orchestration_p1_hub_*.png`, `orchestration_p2_hub_*.png` |
| 2 | `/orchestration/llm-routing` J1 | Wybierz preset `balanced` i zapisz zmiany. | UI wysyla zapis matrycy routingu LLM. | API zwraca `status=200`, `preset=balanced`, `cells=32`; operator widzi zapisany preset. | `orchestration_p1_j1_llm_routing_*.png`, `orchestration_p2_j1_llm_routing_*.png` |
| 3 | `/orchestration/council-rules` J2 | Zapisz reguly i uruchom symulacje glosowania. | UI zapisuje konfiguracje rady i liczy wynik symulacji. | Save ma `status=200`; symulacja moze byc `rejected`, jezeli `quorum_met=false`. W FLOW-019 quorum min wynioslo 5 przy 3 uczestnikach. | `orchestration_p1_j2_council_rules_*.png`, `orchestration_p2_j2_council_rules_*.png` |
| 4 | `/orchestration/auditor` J3 | Kliknij `Audytuj teraz`, potem uruchom `Stop-Fix-Restart Gate`. | System tworzy audit runtime i odpala gate blokujacy syntetyczne fallbacki/stuby na powierzchniach wykonywalnych. | Powstaje `audit_id`; gate zwraca `gate_decision=CONTINUE`, `blockers=0`. | `orchestration_p1_j3_auditor_gate_*.png`, `orchestration_p2_j3_auditor_gate_*.png` |
| 5 | `/orchestration/fixer` J4 | Zapisz protokol fixera. | UI zapisuje budzety retry, sciezki eskalacji i limit iteracji NO-GO. | API zwraca `status=200`, `retry_budgets=4`, `max_nogo_iterations=3`. | `orchestration_p1_j4_fixer_protocol_*.png`, `orchestration_p2_j4_fixer_protocol_*.png` |
| 6 | `/orchestration/dispatch` J5 | Zapisz konfiguracje dispatchu. | UI zapisuje tryb rownoleglosci i limit jednoczesnych zadan. | API zwraca `status=200`, `parallelism_mode=capped`, `max_simultaneous=8`. | `orchestration_p1_j5_dispatch_*.png`, `orchestration_p2_j5_dispatch_*.png` |
| 7 | `/orchestration/tests` J6 | Kliknij `Uruchom golden`. | UI uruchamia katalog golden testow on-demand. | Wynik `status=pass`, suite `golden`; output potwierdza 5 testow advisor jako PASS. | `orchestration_p1_j6_test_catalog_*.png`, `orchestration_p2_j6_test_catalog_*.png` |
| 8 | `/orchestration/teams` J7 | Kliknij test reguly formowania zespolu. | System dopasowuje aktywna regule i tworzy zespol runtime. | Response pokazuje `event_label=[r39-theater] dashboard runtime check`, `matched_rules=1`, `created_teams=1`. | `orchestration_p1_j7_team_formation_*.png`, `orchestration_p2_j7_team_formation_*.png` |
| 9 | `/orchestration/event-map` J8 | Uzyj filtra mapy zdarzen. | UI filtruje graf po topic/module i przelicza runtime edges. | Response pokazuje `edges=2`, `runtime_edges=2`; filtr nie tworzy fikcyjnej mapy. | `orchestration_p1_j8_event_map_*.png`, `orchestration_p2_j8_event_map_*.png` |
| 10 | `/orchestration/conversations` J9 | Kliknij `Uruchom rozmowe`. | System uruchamia rozmowe agent-to-agent z arbitrem i logiem tur. | Response ma `status=completed`, `turns=3`, oraz nowy `conversation_id`. | `orchestration_p1_j9_conversations_*.png`, `orchestration_p2_j9_conversations_*.png` |
| 11 | J1-J9 | Powtorz kroki 1-10 jako drugi przebieg. | Dashboard wykonuje te same akcje po raz drugi i zapisuje nowe odpowiedzi runtime. | `PASS_2X`; brak console/page/request/API failures. | JSON PASS12 |

Scenariusze wyniku:

| Scenariusz | Objaw w UI/API | Decyzja operatora |
|---|---|---|
| PASS | Trasa sie renderuje, akcja konczy sie statusem z JSON evidence, brak bledow konsoli i requestow. | Mozna uznac dany modul J za zamrozony w zakresie FLOW-019. |
| Odrzucona symulacja rady | J2 pokazuje `outcome=rejected`, `quorum_met=false`. | To nie jest blad techniczny, jezeli quorum i wagi sa zgodne z konfiguracja; operator nie traktuje tego jako approve. |
| Gate blokuje kontynuacje | J3 zwraca blockery albo decyzje inna niz `CONTINUE`. | Zatrzymac symulacje, naprawic wskazany plik/powierzchnie i uruchomic etap od poczatku zgodnie ze Stop-Fix-Restart. |
| Blad zapisu konfiguracji | Status HTTP inny niz 2xx, error banner albo brak odswiezenia wartosci po reloadzie. | Nie powtarzac zmian w ciemno; sprawdzic JSON/logi, nie zamrazac modulu J. |
| Brak realnego skutku runtime | UI pokazuje sukces, ale JSON/API nie potwierdza zmiany lub uruchomienia. | Klasyfikowac jako regresje dashboard/backend contract; nie wpisywac PASS bez dowodu runtime. |
| Kosztowna lub szeroka konfiguracja | J1 aggressive/Opus wszedzie, J5 wide/bez capu, J9 rozmowy wlaczone szeroko. | Wymagac jawnego uzasadnienia kosztu i zgodnosci z Human Gate/cost guard przed uzyciem w projekcie. |

Zasady wdrozenia i operowania:

- Operator zaczyna od huba `/orchestration` i przechodzi przez J1-J9 w kolejnosci. Taka kolejnosc utrzymuje zaleznosci: routing modeli, reguly decyzji, audit gate, fixer, dispatch, testy, teamy, event map, rozmowy.
- Nie wolno traktowac samego renderu trasy jako PASS. PASS wymaga klikniecia akcji, odpowiedzi runtime i screenshotu z aktualnego przebiegu.
- Zmiany J1, J2, J4, J5 i J9 sa konfiguracjami sterujacymi kosztem, autonomia albo jakoscia decyzji. Operator nie wdraza ich szerzej bez zgodnosci z aktualna polityka projektu i ewentualna bramka Human Gate.
- J3 jest bramka ochronna: blocker Stop-Fix-Restart przerywa dalszy drilldown i wymaga naprawy przed powtorzeniem.
- J6 sluzy jako szybki sygnal regresji katalogu testow. PASS golden nie zastepuje pelnych testow release, ale brak PASS blokuje zamrozenie orchestration.
- J7 tworzy zespoly tylko na podstawie aktywnych regul; wylaczenie reguly zatrzymuje nowe spawny, ale nie usuwa juz istniejacych teamow.
- J8 jest narzedziem diagnostycznym. Filtr ma pokazywac runtime edges zwrocone przez backend; operator nie dopisuje recznie brakujacych krawedzi do instrukcji.
- Po FLOW-019 stan J1 i J9 zostal odtworzony wedlug sekcji `restored` w JSON evidence; przy kolejnych testach operator ma porownac stan startowy z runtime, a nie zakladac wartosci z tego manuala.

Screenshoty FLOW-019:

![PASS 1 J1 LLM routing](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j1_llm_routing_2026-05-14T10-54-40-012Z.png)

![PASS 1 J2 council rules](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j2_council_rules_2026-05-14T10-54-40-012Z.png)

![PASS 1 J3 auditor gate](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j3_auditor_gate_2026-05-14T10-54-40-012Z.png)

![PASS 1 J4 fixer protocol](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j4_fixer_protocol_2026-05-14T10-54-40-012Z.png)

![PASS 1 J5 dispatch](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j5_dispatch_2026-05-14T10-54-40-012Z.png)

![PASS 1 J6 test catalog](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j6_test_catalog_2026-05-14T10-54-40-012Z.png)

![PASS 1 J7 team formation](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j7_team_formation_2026-05-14T10-54-40-012Z.png)

![PASS 1 J8 event map](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j8_event_map_2026-05-14T10-54-40-012Z.png)

![PASS 1 J9 conversations](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p1_j9_conversations_2026-05-14T10-54-40-012Z.png)

![PASS 2 J1 LLM routing](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j1_llm_routing_2026-05-14T10-54-40-012Z.png)

![PASS 2 J2 council rules](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j2_council_rules_2026-05-14T10-54-40-012Z.png)

![PASS 2 J3 auditor gate](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j3_auditor_gate_2026-05-14T10-54-40-012Z.png)

![PASS 2 J4 fixer protocol](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j4_fixer_protocol_2026-05-14T10-54-40-012Z.png)

![PASS 2 J5 dispatch](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j5_dispatch_2026-05-14T10-54-40-012Z.png)

![PASS 2 J6 test catalog](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j6_test_catalog_2026-05-14T10-54-40-012Z.png)

![PASS 2 J7 team formation](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j7_team_formation_2026-05-14T10-54-40-012Z.png)

![PASS 2 J8 event map](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j8_event_map_2026-05-14T10-54-40-012Z.png)

![PASS 2 J9 conversations](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/orchestration_drilldown/evidence/screenshots/orchestration_p2_j9_conversations_2026-05-14T10-54-40-012Z.png)

### 22.17. FLOW-003 Project Start + Project List + W18 + Lifecycle

Status freeze: `2X_PASS` dla utworzenia projektu, faz 16-19, listy projektow, szczegolow projektu, terminala W18 `/status` i lifecycle  
Evidence: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\project_start_lifecycle\evidence\json\project_start_lifecycle_pass12_2026-05-14T11-16-23-299Z.json`  
Screenshots: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\project_start_lifecycle\evidence\screenshots\*2026-05-14T11-16-23-299Z.png`

![FLOW-003 project start loaded](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/project_start_lifecycle/evidence/screenshots/pass2_01_project_start_loaded_2026-05-14T11-16-23-299Z.png)

![FLOW-003 project created](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/project_start_lifecycle/evidence/screenshots/pass2_04_created_2026-05-14T11-16-23-299Z.png)

![FLOW-003 projects list](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/project_start_lifecycle/evidence/screenshots/pass2_projects_list_2026-05-14T11-16-23-299Z.png)

![FLOW-003 W18 status](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/project_start_lifecycle/evidence/screenshots/pass2_w18_status_2026-05-14T11-16-23-299Z.png)

![FLOW-003 lifecycle](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/project_start_lifecycle/evidence/screenshots/pass2_lifecycle_2026-05-14T11-16-23-299Z.png)

Co operator klika:

| Krok | Ekran | Klik/akcja | Co ma sie stac po kliknieciu |
|---|---|---|---|
| 1 | `/project-start` | Wybierz sciezke startu: `pomysl` albo `szablon`. | Formularz pokazuje pola startowe i zachowuje wybrany tryb. PASS1 uzywa `idea`, PASS2 uzywa `template`. |
| 2 | `/project-start` | Wypelnij nazwe, opis/kontekst, deadline i budzet, potem uruchom podglad. | API `/api/v1/project-start/projects/preview` zwraca `200` i klasyfikacje projektu, m.in. D-level, ryzyko, szablony i estymacje. |
| 3 | `/project-start` | Kliknij utworzenie projektu. | API `/api/v1/project-start/projects/create` zwraca `200`, powstaje `project_id`, shell projektu i audit `project_inception`; faza 16 ma acceptance PASS. |
| 4 | Project Start | Uruchom acceptance fazy 16. | Faza 16 ma `accepted=true`, `hardBlocks=0`, `requiredPassed=8/8`. |
| 5 | Project Start | Utworz defaults dla fazy 17 i uruchom acceptance. | API goals defaults zwraca `200`; faza 17 ma `accepted=true`, `hardBlocks=0`, `requiredPassed=7/7`. |
| 6 | Project Start | Utworz defaults dla fazy 18 i uruchom acceptance. | API scope defaults zwraca `200`; faza 18 ma `accepted=true`, `hardBlocks=0`, `requiredPassed=8/8`. |
| 7 | Project Start | Utworz defaults rady dla fazy 19, zatwierdz readiness i uruchom acceptance. | Pierwszy defaults moze pokazac brak gotowosci; po `approve-readiness` faza 19 ma `accepted=true`, `hardBlocks=0`, `requiredPassed=7/7`. |
| 8 | Project Start | Uruchom diagnoze edge case. | API `edge-cases/diagnose` zwraca `200`, `caseId=EC-A1`, `requiresOperatorReview=true`; operator nie ignoruje tego sygnalu. |
| 9 | `/projects` | Otworz liste projektow. | Karta nowego projektu jest widoczna: `cardFound=true`, body zawiera nazwe projektu. |
| 10 | `/projects/{projectId}` | Kliknij projekt z listy. | Szczegoly otwieraja sie z linku dashboardu, zawieraja nazwe projektu i terminal W18. |
| 11 | Terminal W18 | Wpisz `/status`. | Terminal ma input, odpowiada statusem systemu; w evidence: `services: 6/6 up`, `audit_chain: 4/4 ok`, `status=ok`. |
| 12 | Lifecycle projektu | Otworz lifecycle/advisor dla projektu. | Dashboard lifecycle jest obecny, nie jest empty state, ma flow chart i szybkie akcje. |

Warstwy i fazy 16-19:

| Faza | Warstwa | Warunek PASS z FLOW-003 |
|---|---|---|
| 16 | Project inception / utworzenie shell + audit | `accepted=true`, `hardBlocks=0`, `requiredPassed=8/8`; projekt ma `state=READY_FOR_GOAL_DEFINITION`. |
| 17 | Goals defaults | `accepted=true`, `hardBlocks=0`, `requiredPassed=7/7`; defaults celow sa zapisane przez API. |
| 18 | Scope defaults | `accepted=true`, `hardBlocks=0`, `requiredPassed=8/8`; zakres jest gotowy do dalszej pracy. |
| 19 | Council readiness | Po zatwierdzeniu readiness `accepted=true`, `hardBlocks=0`, `requiredPassed=7/7`; sam stan defaults przed approve moze miec blockery i nie jest finalnym PASS. |

Scenariusze PASS/FAIL:

| Scenariusz | PASS | FAIL / co robi operator |
|---|---|---|
| Start projektu | Preview i create zwracaja `200`, projekt ma `project_id`, shell, klasyfikacje i audit chain. | Brak `project_id`, blad API, brak shell albo brak audit chain: nie przechodzic do faz 17-19, zapisac bug z JSON i screenshotem. |
| Fazy 16-19 | Kazda finalna acceptance ma `accepted=true`, `hardBlocks=0` i pelne `requiredPassed/requiredTotal`. | Kazdy hard block blokuje freeze; operator poprawia dane albo wraca do odpowiedniej fazy zamiast recznie oznaczac PASS. |
| Lista projektow | `/projects` pokazuje karte nowego projektu i nazwe z aktualnego przebiegu. | Projekt istnieje w API, ale nie ma go w UI: bug listy/cache. UI pokazuje projekt, ale API go nie zna: bug kontraktu. |
| Szczegoly projektu | Link z listy otwiera `/projects/{projectId}`, widac nazwe i W18. | Brak nazwy, zly `projectId` albo brak terminala W18 oznacza FAIL dla integracji listy ze szczegolami. |
| W18 `/status` | Input jest dostepny, `/status` zwraca status AEIS i wykonuje sie w kontekscie tego projektu. | Brak inputu, brak odpowiedzi albo odpowiedz poza kontekstem projektu blokuje PASS. |
| Lifecycle | Widok lifecycle ma dashboard, flow chart i quick actions; nie jest pusty. | Empty state po utworzeniu projektu albo brak osi lifecycle oznacza FAIL integracji lifecycle/advisor. |

Projekty z przebiegu:

| PASS | Project ID | Nazwa | Sciezka |
|---|---|---|---|
| PASS1 | `proj_5f0706c51d42` | `FLOW003 Project Start PASS1 1778757384015` | `idea` |
| PASS2 | `proj_4cd16bbad919` | `FLOW003 Project Start PASS2 1778757384015` | `template` |

Operator ma sie trzymac tych zasad:

- Nie uznawac Project Start za zakonczony po samym preview; wymagane sa create, acceptance fazy 16 i widoczny projekt na `/projects`.
- Faza 19 jest PASS dopiero po `approve-readiness` i finalnym acceptance. Stan przed approve z blockerami jest oczekiwanym etapem posrednim, nie finalnym sukcesem.
- Edge diagnosis z `requiresOperatorReview=true` jest sygnalem do przegladu operatorskiego; nie blokuje automatycznie PASS FLOW-003, ale musi byc widoczne w evidence.
- W18 `/status` musi byc sprawdzony z poziomu szczegolow konkretnego projektu, nie z neutralnego terminala bez kontekstu.
- Lifecycle musi pokazac os 16 faz i szybkie akcje; pusty lifecycle po utworzeniu projektu jest regresja.

### 22.18. FLOW-021 Workspace Defaults Full Wizard

Status freeze: `2X_PASS` dla pelnego kreatora `/workspace-defaults` na celach `apps_internal`, `public_products`, `cybersecurity`, `research`  
Evidence: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\workspace_defaults_full\evidence\json\workspace_defaults_full_pass12_2026-05-14T11-58-27-462Z.json`  
Screenshots: `C:\Users\razor\Desktop\pipeline_glm\docs\aeis_repair_v2\workspace_defaults_full\evidence\screenshots\*2026-05-14T11-58-27-462Z.png`

![FLOW-021 apps internal loaded](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_00_loaded_2026-05-14T11-58-27-462Z.png)

![FLOW-021 apps internal acceptance](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_apps_internal_10_acceptance_2026-05-14T11-58-27-462Z.png)

![FLOW-021 public products acceptance](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_public_products_10_acceptance_2026-05-14T11-58-27-462Z.png)

![FLOW-021 cybersecurity acceptance](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_cybersecurity_10_acceptance_2026-05-14T11-58-27-462Z.png)

![FLOW-021 research acceptance](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_defaults_full/evidence/screenshots/pass2_research_10_acceptance_2026-05-14T11-58-27-462Z.png)

Co operator klika w kreatorze:

| Krok | Warstwa/funkcja | Klik/akcja | Co ma sie stac po kliknieciu |
|---|---|---|---|
| 1 | Smart defaults / welcome | Otworz `/workspace-defaults?goal={goal}` i zapisz krok startowy po zastosowaniu smart defaults. | `POST /api/v1/workspace-defaults/smart-defaults/apply` i `POST /wizard/step` zwracaja `200`; kreator przechodzi na krok 2. |
| 2 | Budget estimate | Kliknij zapis estymacji budzetu. | `POST /budgets/estimate` zwraca `200`, `recommendedBudget` i rekomendacje kosztowa; krok 2 jest oznaczony jako ukonczony. |
| 3 | Autonomy mapping | Wybierz/zapisz mapowanie autonomii dla celu. | `POST /autonomy/mapping` zwraca `200`; preset celu jest zapisany i kreator przechodzi dalej. |
| 4 | Mobile pairing + notification matrix | Sparuj mobile i zapisz macierz powiadomien. | `POST /mobile/pair` ma `paired=true`, `verifiedPush=true`; `POST /notifications/matrix` zapisuje kanaly `email,in_app,mobile,slack,sms`. |
| 5 | Cleanup | Zapisz domyslne okresy cleanup. | Krok 5 zapisuje konfiguracje retencji/cleanup i przechodzi do UI. Acceptance ma pozniej check `cleanup_defaults_set`. |
| 6 | UI preset | Zapisz preset interfejsu. | `POST /workspace-defaults/ui` zwraca `200`, preset `power_user`; kreator przechodzi do shortcut. |
| 7 | Shortcut | Dodaj/zapisz skrot `open_today_project`. | `POST /workspace-defaults/shortcuts` zwraca `200`, `conflict=false`; liczba skrotow w final snapshot wynosi 1. |
| 8 | Approval escalation | Zapisz eskalacje akceptacji. | Panel eskalacji jest widoczny i krok 8 zapisuje sie bez skipow; kreator przechodzi do testow/edge/inheritance. |
| 9 | Test strategy + edge diagnosis + inheritance preview | Zapisz strategie testow, uruchom diagnoze edge i podglad dziedziczenia, potem acceptance. | Test strategy ma `balanced_human_like` i `humanLikeRequired=true`; edge diagnosis zwraca `EC-A2`, `requiresOperatorReview=true`; inheritance preview zwraca template budzetu i autonomie; acceptance zwraca `accepted=true`. |

Cele i wynik 2x PASS:

| Cel | Autonomia | Budget template | Budget estimate | Acceptance |
|---|---|---|---|---|
| `apps_internal` | `balanced` | `medium` | `226.68`, rekomendacja `increase_budget_or_upgrade_template` | PASS1/PASS2 `accepted=true`, `hardBlocks=0`, `checks=8` |
| `public_products` | `production` | `large` | `358.66`, rekomendacja `increase_budget_or_upgrade_template` | PASS1/PASS2 `accepted=true`, `hardBlocks=0`, `checks=12` |
| `cybersecurity` | `conservative` | `medium` | `226.68`, rekomendacja `increase_budget_or_upgrade_template` | PASS1/PASS2 `accepted=true`, `hardBlocks=0`, `checks=12` |
| `research` | `research` | `medium` | `226.68`, rekomendacja `increase_budget_or_upgrade_template` | PASS1/PASS2 `accepted=true`, `hardBlocks=0`, `checks=8` |

Kontrakt warstw/funkcji:

| Funkcja | Endpoint / dowod | Warunek PASS |
|---|---|---|
| Smart defaults | `/api/v1/workspace-defaults/smart-defaults/apply` | Status `200`, brak skipow, krok 1 zapisany. |
| Budget estimate | `/api/v1/workspace-defaults/budgets/estimate` | Status `200`, budzet rekomendowany widoczny; rekomendacja kosztowa nie jest ignorowana. |
| Autonomy mapping | `/api/v1/workspace-defaults/autonomy/mapping` | Preset zgodny z celem: balanced/production/conservative/research. |
| Mobile pairing | `/api/v1/workspace-defaults/mobile/pair` | `paired=true`, `verifiedPush=true`. |
| Notification matrix | `/api/v1/workspace-defaults/notifications/matrix` | Aktywne kanaly: `email`, `in_app`, `mobile`, `slack`, `sms`. |
| Cleanup | Acceptance `cleanup_defaults_set` | Domyslne okresy cleanup sa zapisane dla 10 typow srodowisk. |
| UI preset | `/api/v1/workspace-defaults/ui` | `preset=power_user`. |
| Shortcut | `/api/v1/workspace-defaults/shortcuts` | `id=open_today_project`, `conflict=false`. |
| Approval escalation | Widoczny panel eskalacji | Krok 8 zapisany, brak pominięcia. |
| Test strategy | `/api/v1/workspace-defaults/test-strategy` | `defaultStrategy=balanced_human_like`, `humanLikeRequired=true`. |
| Edge diagnosis | `/api/v1/workspace-defaults/edge-cases/diagnose` | `caseId=EC-A2`, `requiresOperatorReview=true`; operator zapisuje przeglad, nie udaje braku ryzyka. |
| Inheritance preview | `/api/v1/workspace-defaults/inheritance/preview` | Zwrocony budget template i autonomy preset zgadzaja sie z celem. |
| Acceptance | `/api/v1/workspace-defaults/acceptance-test?goal={goal}` | `accepted=true`, `hardBlocks=0`, audit `phase_4.complete` recorded. |

Scenariusze PASS/FAIL:

| Scenariusz | PASS | FAIL / reakcja operatora |
|---|---|---|
| Pelny kreator 1-9 | Kazdy krok zwraca `status=200`, `completedSteps=1..9`, `skippedSteps=[]`. | Brak zapisanego kroku albo skip bez jawnej decyzji blokuje freeze celu. |
| Cel workspace | Wszystkie 4 cele przechodza w PASS1 i PASS2. | Jeden cel z hard blockiem oznacza brak globalnego `2X_PASS`; poprawic cel i powtorzyc oba przebiegi. |
| Mobile i powiadomienia | Push zweryfikowany, mobile sparowany, macierz ma aktywne kanaly. | Brak push albo pusta macierz to FAIL konfiguracji operator/mobile. |
| Koszt i autonomia | Budzet, rekomendacja kosztowa i autonomy preset sa widoczne i zgodne z celem. | Operator nie nadpisuje kosztow/autonomii w ciemno; wymagany nowy screenshot i acceptance po zmianie. |
| Edge diagnosis | `EC-A2` jest zarejestrowane jako wymagajace przegladu operatora. | Brak diagnozy edge albo ukrycie review to FAIL dla bezpiecznego wdrozenia. |
| Acceptance | `accepted=true`, `hardBlocks=0`; public_products/cybersecurity maja 12 checks, apps_internal/research 8 checks. | Dowolny hard block zatrzymuje domkniecie Phase 4 defaults. |

Zasady operatorskie:

- Operator wykonuje kreator osobno dla `apps_internal`, `public_products`, `cybersecurity`, `research`; nie wolno przenosic PASS z jednego celu na drugi.
- Kolejnosc krokow 1-9 jest obowiazkowa, bo acceptance sprawdza komplet: budzet, autonomie, powiadomienia, cleanup, audit, mobile i uprawnienia.
- Rekomendacja `increase_budget_or_upgrade_template` nie jest bledem, ale musi pozostac widoczna dla decyzji kosztowej.
- Dla `public_products` i `cybersecurity` acceptance ma dodatkowe wymagania celu; 8-check PASS z innych celow nie wystarcza.
- `requiresOperatorReview=true` przy edge diagnosis oznacza, ze operator ma odnotowac ryzyko przed produkcyjnym uzyciem defaults.

### 22.19. FLOW-022 Workspace Pipeline Full

Status freeze: `PASS_2X` dla pelnego flow `/workspace`: zakladki `Pipeline`, `Kod`, `Wynik`  
Evidence JSON: `docs/aeis_repair_v2/workspace_pipeline_full/evidence/json/workspace_pipeline_full_pass12_2026-05-14T12-39-30-039Z.json`  
PASS1 run: `8610fd01d3404434a709917c467f1fa6`  
PASS2 run: `37b4b93bf0924a1e97038f17aca005f1`  
Evidence summary: `screenshotCount=14`, `issueCount=0`, `hardEventCount=0`, `apiErrorCount=0`

![FLOW-022 workspace loaded](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_01_workspace_loaded_2026-05-14T12-39-30-039Z.png)

![FLOW-022 run pending selected](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_03_run_pending_selected_2026-05-14T12-39-30-039Z.png)

![FLOW-022 run complete selected](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_05_run_complete_selected_2026-05-14T12-39-30-039Z.png)

![FLOW-022 code tab](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_06_code_tab_2026-05-14T12-39-30-039Z.png)

![FLOW-022 output tab](C:/Users/razor/Desktop/pipeline_glm/docs/aeis_repair_v2/workspace_pipeline_full/evidence/screenshots/pass1_07_output_tab_2026-05-14T12-39-30-039Z.png)

Co operator widzi:

- Route `/workspace` pokazuje zakladki `Pipeline`, `Kod`, `Wynik`.
- `Pipeline` sluzy do wyslania pomyslu, wyboru runu, wykonania pipeline i kontroli statusu oraz krokow.
- `Kod` pokazuje artefakty/kod z wynikow krokow pipeline; po poprawce czyta `step.result`.
- `Wynik` pokazuje nazwe i status kroku oraz wynik koncowy, a nie pusty shell.

Kroki operatora:

| Krok | Klik/akcja | Co dzieje sie po kliknieciu | API/stan do weryfikacji |
|---|---|---|---|
| 1 | Otworz `/workspace` i zostan na zakladce `Pipeline`. | UI laduje formularz pomyslu i liste runow. | Brak console/API errors; widoczne pole `Wyslij pomysl do uruchomienia w pipeline...`. |
| 2 | Wpisz pomysl w polu `Wyslij pomysl do uruchomienia w pipeline...`. | Tekst trafia do lokalnego stanu formularza; backend nie jest jeszcze mutowany. | Pole zawiera pelny pomysl operatora. |
| 3 | Kliknij `Wyslij`. | Frontend tworzy run pipeline z pomyslu. | `POST /api/v1/pipeline/ideas` zwraca run; nowy run pojawia sie na liscie jako `pending`. |
| 4 | Wybierz utworzony run. | UI ustawia aktywny `run_id` i pobiera jego szczegoly. | `GET /api/v1/pipeline/runs/{run_id}` zwraca wybrany run; widok pokazuje status `pending`. |
| 5 | Kliknij `Wykonaj`. | Backend uruchamia pipeline dla wybranego runu. | `POST /api/v1/pipeline/runs/{run_id}/execute` zwraca sukces; status przechodzi przez `running`. |
| 6 | Czekaj na status `complete`. | UI odpytuje stan runu do zakonczenia. | `GET /api/v1/pipeline/runs/{run_id}` zwraca finalStatus `complete`; `failed` albo `cancelled` blokuja freeze. |
| 7 | Skontroluj 5 krokow pipeline. | UI pobiera szczegoly krokow aktywnego runu. | `GET /api/v1/pipeline/runs/{run_id}/steps` zwraca 5 steps; `quality_gate=passed`. |
| 8 | Przejdz do zakladki `Kod`. | UI renderuje wyniki kodowe z krokow. | Zakladka `Kod` pokazuje dane z `step.result`, a nie puste pola. |
| 9 | Przejdz do zakladki `Wynik`. | UI renderuje podsumowanie i wynik krokow. | Zakladka `Wynik` pokazuje nazwe/status kroku oraz dane wynikowe. |

Scenariusze statusu runu:

| Status | Znaczenie operatorskie | Decyzja |
|---|---|---|
| `pending` | Run zostal utworzony po `Wyslij`, ale jeszcze nie wykonany. | Operator wybiera run i klika `Wykonaj`; sam `pending` nie jest PASS. |
| `running` | Pipeline wykonuje kroki po `Wykonaj`. | Operator czeka i odswieza/polluje stan; nie zamraza flow w trakcie pracy. |
| `complete` | Pipeline zakonczyl sie poprawnie. | Mozna przejsc do kontroli 5 krokow, `Kod` i `Wynik`. |
| `failed` / `cancelled` | Run nie zakonczyl sie poprawnym wynikiem. | Blokada freeze; zapisac run ID, screenshot i blad API/UI. |

Zasady zamrozenia FLOW-022:

- Wymagane sa 2 przebiegi: PASS1 i PASS2.
- Kazdy przebieg musi miec finalStatus `complete`.
- Kazdy przebieg musi miec dokladnie 5 steps z `quality_gate=passed`.
- Zakladki `Kod` i `Wynik` musza pokazac dane dla wybranego runu.
- `console errors = 0`, `API errors = 0`, `issueCount=0`, `hardEventCount=0`.
- PASS1 zostal potwierdzony dla runu `8610fd01d3404434a709917c467f1fa6`; PASS2 dla runu `37b4b93bf0924a1e97038f17aca005f1`.

Poprawki objete instrukcja:

| Poprawka | Co operator sprawdza |
|---|---|
| Zakladka `Kod` czyta `step.result`. | Po przejsciu do `Kod` widac dane wynikowe krokow, nie pusty fallback. |
| Zakladka `Wynik` pokazuje nazwe/status kroku. | Po przejsciu do `Wynik` widac nazwy i statusy krokow pipeline. |
| Guard jakosci rozroznia localhost i email fixture `example.com` od prawdziwego endpointu `example.com`. | `quality_gate=passed` nie moze byc falszywie blokowany przez dozwolone fixture, ale prawdziwy zewnetrzny endpoint `example.com` pozostaje ryzykiem. |

## 23. Zrodla uzyte do wstepnego ukladu

Pliki przeczytane podczas przygotowania szkieletu:

- `AEIS_SYSTEM_BOOK_2026.md`
- `docs/dokumentacja/00_INDEX.md`
- `docs/dokumentacja/02_operational_manual.md`
- `docs/dokumentacja/DOCS_RUNTIME_SYNC_2026_05_13.md`
- `docs/aeis_repair_v2/AEIS_REPAIR_V2_R0_BASELINE.md`
- `src/sylion-frontend/src/app/(app)/layout.tsx`
- `src/sylion-frontend/src/app/(app)/_canonical-surface.tsx`
- `src/sylion-frontend/src/app/(app)` - lista tras przez `rg --files`
- `src/sylion-frontend/src/app/(app)/workspace/page.tsx`
- `src/sylion-frontend/src/app/(app)/projects/page.tsx`
- `src/sylion-frontend/src/app/(app)/dashboard/operator-monitor/page.tsx`
- `src/sylion-frontend/src/app/(app)/governance/page.tsx`
- `src/sylion-frontend/src/app/(app)/human-gate/page.tsx`
- `src/sylion-frontend/src/app/(app)/model-council/page.tsx`
- `src/sylion-frontend/src/app/(app)/execution-start/page.tsx`
- `src/sylion-frontend/src/app/(app)/memory/page.tsx`
- `src/sylion-frontend/src/app/(app)/skills/page.tsx`
- `src/sylion-frontend/src/app/(app)/funding/page.tsx`
- `src/sylion-frontend/src/app/(app)/evidence/page.tsx`
- `src/sylion-frontend/src/app/(app)/audit/page.tsx`
- `src/sylion-frontend/src/app/(app)/terminal/replay/page.tsx`
- `src/sylion-frontend/src/app/(app)/operator-mobile/page.tsx`
- `src/sylion-frontend/src/app/(app)/settings/page.tsx`
- `src/sylion-frontend/src/app/(app)/secrets/page.tsx`
- `src/sylion-frontend/src/app/(app)/observability/page.tsx`
- `src/sylion-frontend/src/app/(app)/health/page.tsx`
- `src/sylion-frontend/src/lib/api/client.ts`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/BUG_LEDGER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/FREEZE_REGISTER.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/RUN_LOG.md`
- `docs/aeis_repair_v2/w18_router_repair/evidence/json/w18_router_dashboard_pass12_reconstructed_2026-05-13.json`
- `docs/aeis_repair_v2/w18_router_repair/evidence/screenshots/`
- `docs/aeis_repair_v2/execution_start_router_repair/evidence/json/execution_start_dashboard_pass12_2026-05-13T22-23-31-684Z.json`
- `docs/aeis_repair_v2/execution_start_router_repair/evidence/screenshots/`
- `docs/aeis_repair_v2/execution_live_workers/evidence/json/live_workers_dashboard_pass12_2026-05-13T22-40-42-350Z.json`
- `docs/aeis_repair_v2/execution_live_workers/evidence/screenshots/`
- `docs/aeis_repair_v2/execution_phases_34_41/EXECUTION_PHASES_34_41_PASS12.md`
- `docs/aeis_repair_v2/execution_phases_34_41/evidence/json/execution_phases_34_41_pass12_2026-05-14T09-40-35-269Z.json`
- `docs/aeis_repair_v2/execution_phases_34_41/evidence/screenshots/`
- `docs/aeis_repair_v2/execution_dispatch_control/EXECUTION_DISPATCH_CONTROL_PASS12.md`
- `docs/aeis_repair_v2/execution_dispatch_control/evidence/json/execution_dispatch_control_pass12_2026-05-14T09-58-40-542Z.json`
- `docs/aeis_repair_v2/execution_dispatch_control/evidence/screenshots/`
- `docs/aeis_repair_v2/full_human_dashboard_audit/evidence/json/full_aud_006_route_failure_probe_2026-05-13T22-28-10-448Z.json`
- `docs/aeis_repair_v2/full_human_dashboard_audit/evidence/json/full_aud_006_route_failure_probe_pass2_2026-05-13T22-29-13-370Z.json`
- `docs/aeis_repair_v2/full_human_dashboard_audit/evidence/screenshots/full_aud_006/`
- `src/sylion-pipeline/logs/v2/command_router_audit.jsonl`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/dashboard_route_probe_pass1.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/dashboard_route_probe_pass2_after_d004.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/dashboard_human_interactions_pass1.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/dashboard_human_interactions_pass1.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/workspace_tabs_pass2.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/workspace_tabs_pass2.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/backend_health_8010.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/backend_restart_retest_d004.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/frontend_root_3001.status.txt`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/frontend_start_retest2_clean.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/openapi_summary.txt`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_approve_ticket_create.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_approve_after_ui_ticket_get.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_reject_ticket_create.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_reject_after_ui_ticket_get.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_pass2_approve_reject.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/human_gate_pass2_approve_reject.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/skills_execute_retest1_after_fix.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/skills_execute_retest2_after_fix.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/skills_full_pass2_create_execute_signal.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/skills_full_pass2_create_execute_signal.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/funding_reports_chart_warning_retest4.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/funding_reports_chart_warning_retest5_second_pass.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/funding_tabs_reports_pass2.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/funding_tabs_reports_pass2.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/settings_tabs_secrets_pass2.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/settings_tabs_secrets_pass2.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/operator_mobile_queue_pass2.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/operator_mobile_queue_pass2.md`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/governance_compliance_retest1_d004.json`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/evidence/runtime_baseline/governance_compliance_retest2_d004.json`

Utworzone/zmienione:

- `docs/aeis_repair_v2/dashboard_e2e_freeze/`
- `docs/aeis_repair_v2/dashboard_e2e_freeze/AEIS_OPERATOR_MANUAL_LATEST.md`
