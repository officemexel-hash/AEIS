# Funding, mobile i HelpTipy

## Spis tresci

1. [Funding Autopilot](#funding-autopilot)
2. [Zakladki funding](#zakladki-funding)
3. [Funding API](#funding-api)
4. [Bezpieczny external submit](#bezpieczny-external-submit)
5. [Operator mobile](#operator-mobile)
6. [HelpTip - mechanizm](#helptip---mechanizm)
7. [Katalog HelpTipow kluczowych ekranow](#katalog-helptipow-kluczowych-ekranow)
8. [Legenda ikon i kontrolek](#legenda-ikon-i-kontrolek)

## Funding Autopilot

Funding jest realnym pionem domenowym, a nie tylko promptem. Ma:

- backend `sylion/funding_autopilot/routes.py`;
- service/store/schema/permissions;
- UI `/funding`;
- profile firmy;
- zrodla i nabory;
- pomysly projektow;
- matching i scoring;
- aplikacje grantowe;
- submission session;
- CRM tracking;
- raporty i alerty.

Screenshot:

![Funding](screenshots/05_funding.png)

## Zakladki funding

| Zakladka | Cel | Typowe akcje |
| --- | --- | --- |
| Firma | Profil firmy, dokumenty, KRS, readiness. | Zapis profilu, registry sync, dokumenty, state aid. |
| Nabory | Programy i call'e. | Lista sources, create programme, create call, scan/search. |
| Pomysly | Idee projektow grantowych. | Generate ideas, convert idea to project. |
| Dopasowanie | Matching/scoring/consortium. | Run matching, eligibility, scoring, partner search, outreach. |
| Wnioski | Aplikacje. | Create application, review, export, document checklist. |
| Submission | Bramka zlozenia. | Prepare, fill mapping, save draft, request approval, submit receipt. |
| Raporty | Executive reporting. | Deadlines, alerts, executive report, exports. |

## Funding API

Najwazniejsze endpointy:

| Obszar | Endpointy |
| --- | --- |
| Health | `GET /api/v1/funding/health` |
| Company | `GET/PUT /company-profile`, `/company-profile/readiness`, `/documents`, `/state-aid`, `/registry-sync` |
| Sources/programmes | `GET /sources`, `GET/POST /programmes`, `GET/POST /calls`, `POST /calls/search`, `GET /calls/scored` |
| Ideas | `GET /ideas`, `POST /ideas/generate`, `POST /ideas/{id}/convert-to-project` |
| Projects/matching | `GET/POST /projects`, `POST /matching/run`, `GET /matching/results/{project_id}` |
| Eligibility/scoring | `POST /eligibility/check`, `POST /scoring/run`, `GET /scoring/{project_id}` |
| Consortium | `POST /consortium/analyze`, `/partners/search`, `/partners/shortlist`, `/outreach/generate` |
| Application | `POST /application/create`, `GET /application/{id}`, `/documents`, `/review`, `/export` |
| Submission | `POST /submission/prepare`, `/fill`, `/save-draft`, `/request-approval`, `/submit`, `GET /submission/receipt`, `/sessions`, `/approvals` |
| CRM/reporting | `GET /crm/applications`, `/deadlines`, `/alerts`, `/reports/executive` |
| Scan | `POST /scan/trigger`, `GET /scan/status/{job_id}` |

## Bezpieczny external submit

W testach P3 funding pozostal local rehearsal. Regola:

```text
External submit = D4.
Realny submit wymaga Human Gate.
Preview musi pokazac dokladny payload/PDF.
Submit zapisuje payload_hash, operator_id, timestamp i receipt.
Po realnym submit nie ma rollbacku, jest tylko korekta/wycofanie zgodnie z portalem zewnetrznym.
```

Wymagane pre-submit checks:

- deadline OK;
- source OK;
- legal OK;
- budget OK;
- documents OK;
- review readiness OK;
- operator approval present;
- portal/reference captured;
- CRM entry created.

## Operator mobile

Powierzchnie:

- `/operator-mobile`;
- `/operator-mobile/queue`;
- `/operator-mobile/queue/{ticketId}`;
- `/operator-mobile/devices`.

API:

- `POST /api/v1/mobile/devices/bind`;
- `GET /api/v1/mobile/devices`;
- `DELETE /api/v1/mobile/devices/{device_id}`;
- `GET /api/v1/mobile/queue`;
- `GET /api/v1/mobile/queue/{ticket_id}`;
- `POST /api/v1/mobile/queue/{ticket_id}/decision`;
- `POST /api/v1/mobile/queue/{ticket_id}/approve`;
- `POST /api/v1/mobile/queue/{ticket_id}/reject`.

Screenshot:

![Operator mobile](screenshots/09_operator_mobile.png)

Status:

- queue view istnieje;
- approve/reject API istnieje;
- docelowo wymagane sa device binding, push, biometric/PIN, non-repudiation i offline queue.

## HelpTip - mechanizm

Komponent: `src/sylion-frontend/src/components/common/HelpTip.tsx`.

Zachowanie:

- renderuje okragly znak pomocy;
- otwiera tooltip po hover/focus/click;
- ma `aria-label`;
- przelicza pozycje przy scroll/resize;
- uzywa portalu do `document.body`;
- maksymalna szerokosc tooltipa to `min(420px, viewport - 32px)`;
- automatycznie zmienia strone, gdy brakuje miejsca;
- zamyka tooltip po outside pointer albo `Escape`.

Regola pisania HelpTipow:

- tekst prosty, po polsku;
- 1-3 zdania;
- opisuje ryzyko albo sens funkcji, nie marketing;
- nie powinien zawierac sekretow ani danych wrazliwych;
- przy akcjach D3+ powinien tlumaczyc, co zostanie zapisane w audycie.

## Katalog HelpTipow kluczowych ekranow

### Execution Start

| Element | Tresc/znaczenie |
| --- | --- |
| Header | Ekran prowadzi przez fazy 32-41: budowa, testy, predeploy, deploy/proba, zamkniecie. |
| Active project | Aktywny projekt jest kontekstem wykonania; wszystkie akcje zapisuja artefakty i audit dla niego. |
| Actions | Przyciski uruchamiaja kolejne fazy i po kazdej akcji odswiezaja projekt, acceptance i edge cases. |
| Operator notes | Notatka trafia do requestu jako kontekst zatwierdzenia; nie wpisywac sekretow. |
| Phase 32 | Tworzy workspace, galezie, workerow, srodowiska i monitoring. |
| Phase 33 | Uruchamia petle budowy i raportowanie kosztu/postepu/guardow. |
| Phase 34 | Zwoluje rade w trakcie budowy przy zmianie zakresu lub ryzyku. |
| Phase 35 | Wlacza koordynacje workerow, kolejki, blokady i recovery. |
| Phase 36 | Waliduje artefakty, koszt, spojnosci i wygasza workerow. |
| Phase 37 | Uruchamia L1-L5, coverage, performance i quality verdict. |
| Phase 38 | Wystawia acceptance/staging i zbiera feedback klienta. |
| Phase 39 | Sprawdza rollback, monitoring, support i hard authorization. |
| Phase 40 | Wykonuje deploy albo lokalny release rehearsal; external wymaga Human Gate. |
| Phase 41 | Tworzy raporty, archiwum, invoice, handoff i warranty. |

### Funding

| Element | Tresc/znaczenie |
| --- | --- |
| Header funding | Granty, dotacje, auto-matching i generowanie wnioskow z masterplanu. |
| Zakladki | Firma, Nabory, Pomysly, Dopasowanie, Wnioski, Submission, Raporty. |
| Gotowosc | Procent uzupelnienia profilu; >80% rekomendowane przed wnioskami. |
| Nabory metric | Liczba aktywnych call'i zindeksowanych w systemie. |
| Wnioski metric | Liczba pakietow aplikacyjnych w przygotowaniu lub zlozonych. |
| Alerty metric | Aktywne alerty: terminy, brakujace dokumenty, walidacja. |
| KRS sync | Pobranie odpisu z API KRS i powiazanie ze sprawozdaniami. |
| Profil firmy | Dane prawne, finansowe i kompetencyjne wymagane przed matchingiem. |
| Nabory | Ewidencja programow, deadline'ow, budzetow i dokumentow. |
| Rekomendowane granty | Auto-generowane rekomendacje z engine dopasowania. |
| Pomysly | AI-generated ideas na podstawie kompetencji i naborow. |
| Projekty grantowe | Projekty z konsorcjum i dopasowaniami. |
| Scoring | Ocena szansy sukcesu na podstawie tematu, gotowosci, konsorcjum i historii. |
| Dopasowanie | Wyniki matchingu projektu do programow, score i uzasadnienie. |
| Wniosek | Generowanie pakietu z masterplanu, profilu i dokumentacji. |
| Bramka zlozenia | Walidacja dokumentow, review readiness i approval przed zlozeniem. |
| Sesja zlozenia | Walidacja, status zatwierdzenia i numer referencyjny. |
| Terminy | Alerty 30/14/7 dni przed deadlinem. |
| Alerty i zatwierdzenia | Brakujace dokumenty, bledy walidacji, historia decyzji. |
| Raport wykonawczy | Status pipeline, gotowosc, ryzyka, prognozowane przychody. |

### Project Start / Council / Planning

| Ekran | Typ HelpTipow |
| --- | --- |
| `/project-start` | Wyjasnia faze aktywna, stan backendu, acceptance, edge cases, tworzenie projektu. |
| `/council-to-ksiega` | Wyjasnia role rady, pytania, consensus, generowanie ksiegi, finalizacje. |
| `/planning` | Wyjasnia model selection, skill synthesis, masterplan, test plan, cost preview i dry-run. |

### Globalne HelpTipy

| Element | Znaczenie |
| --- | --- |
| HelpTip przy labelu | Opisuje pole albo metryke. |
| HelpTip przy sekcji | Tlumaczy caly panel. |
| HelpTip przy akcji | Tlumaczy skutki klikniecia. |
| HelpTip przy ryzyku | Tlumaczy, co blokuje lub wymaga Human Gate. |

## Legenda ikon i kontrolek

| Kontrolka | Znaczenie |
| --- | --- |
| `RefreshCw` / OdĹ›wieĹĽ | Pobierz aktualny stan z backendu. |
| `Rocket` | Start fazy, deploy, uruchomienie. |
| `ShieldCheck` | Approval, guard, quality pass. |
| `AlertTriangle` | Blokada, alert, ryzyko. |
| `Loader2` | Akcja w toku. |
| `Users` | Rada, zespol, council. |
| `GitBranch` | Routing, decyzja, workflow. |
| `TestTube` | Testy i symulacje. |
| `DollarSign` | Koszt/funding/budzet. |
| `Smartphone` | Mobile/operator device. |
| `Database` | Memory, ontology, source of truth. |
| Badge zielony | Pass/gotowe/zaakceptowane. |
| Badge amber | W toku/oczekuje/ostrzezenie. |
| Badge czerwony | Blad/blokada/niedostepne. |
| Tabs | Rozdzielaja workflow na kroki albo domeny. |
| Switch/checkbox | Wlaczanie polityki binarnej. |
| Select | Wybor projektu, aplikacji, sesji, modelu. |
| Text area | Notatka operatora, opis, uzasadnienie. |
