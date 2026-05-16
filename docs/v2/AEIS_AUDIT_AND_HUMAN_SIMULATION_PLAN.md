# AEIS - plan audytu i symulacji human-like

> Cel: przeprowadzic audyt aktualnego systemu AEIS od czystego startu,
> potem wykonac 6 symulacji realnych pomyslow jak operator-czlowiek,
> klikajac dashboard, bez omijania testow i bez bypassow.  
> Status: plan operacyjny do wykonania po doprecyzowaniu 6 pomyslow i limitow
> kosztowych.

---

## 1. Zasady niepodlegajace negocjacji

1. Audyt zaczyna sie od czystego stanu: pusta baza, pusta pamiec projektow,
   puste kolejki, brak seedowanych wynikow testowych udajacych realne dane.
2. Nie kasujemy przypadkowo istniejacych danych operatora. Tworzymy osobny
   profil audytowy, osobna baze i osobny katalog logow.
3. Nie uzywamy bypassow w testach operatorskich. Jezeli UI wymaga auth, RBAC,
   HumanGate albo rate-limit, test ma przejsc przez realny mechanizm.
4. Nie zaliczamy testu API jako substytutu testu UI, jezeli celem jest
   symulacja czlowieka. API moze byc uzyte do diagnostyki, nie do omijania
   dashboardu.
5. Nie przeskakujemy failing testow. Defekt jest naprawiany, a potem ten sam
   test jest powtarzany od miejsca, w ktorym ujawnil blad.
6. Pomysly, odpowiedzi operatora, decyzje HumanGate i zmiany konfiguracji sa
   wpisywane tak, jak robilby to czlowiek: klawiatura/mysz w dashboardzie.
   API nie sluzy do tworzenia pomyslow ani zatwierdzania decyzji.
7. Klucze API sa wpisywane przez dashboard albo oficjalny ekran konfiguracji.
   Nie zapisujemy ich w dokumentach, logach ani w promptach.
8. Kazdy kosztowy krok ma pre-flight cost estimate i Financial HumanGate.
9. Kazdy deploy zewnetrzny, w tym Hetzner VPS, ma Production/External Action
   HumanGate i rollback evidence.
10. Status `complete` bez artefaktow, evidence i testow jest traktowany jako
   blad systemu.
11. Kazdy stub, mock, fallback albo placeholder pokazany jako realna funkcja
    oznacza FAIL i wymaga poprawki. Mock moze istniec tylko wtedy, gdy UI jasno
    oznacza go jako mock i dany test nie wymaga realnej funkcji.
12. Po kazdej poprawce wracamy do punktu wejscia danego testu i powtarzamy
    sciezke od nowa jako czlowiek przez dashboard.
13. Dokumentacja nigdy nie wygrywa z runtime. Hierarchia prawdy:
    `kod -> runtime -> API -> UI -> testy -> dokumentacja`.

---

## 2. Wyniki koncowe audytu

Po zakonczeniu powstaja artefakty:

| Artefakt | Zawartosc |
|---|---|
| `AUDIT_RUNBOOK_RESULT.md` | Co wykonano, kiedy, na jakim commicie, z jakim wynikiem. |
| `RUNTIME_REALITY_MATRIX.md` | Co dziala w runtime, API, UI i testach. |
| `HUMAN_SIMULATION_REPORT.md` | 6 pomyslow, klikane sciezki, screenshoty, wyniki, blokery. |
| `BUG_FIX_LEDGER.md` | Defekty znalezione w trakcie, poprawki, retesty, status. |
| `COST_AND_MODEL_LEDGER.md` | Uzyte modele, koszt per sesja, latency, tokeny, decyzje cost sentinel. |
| `DEPLOYMENT_EVIDENCE.md` | Czy AEIS umial wygenerowac i wdrozyc aplikacje, np. na Hetzner VPS. |
| `W1_W19_COVERAGE_MATRIX.md` | Warstwa po warstwie: testy, evidence, defekty, retesty, status. |
| `AEIS_HUMAN_SIMULATION_AUDIT.pdf` | Finalny raport PDF ze screenshotami, opisem klikniec, skutkiem, wynikiem i evidence refs. |
| `EVIDENCE_PACKS/` | Zrzuty UI, logi, audit chain extracts, test outputs, deployment receipts. |

Minimalny werdykt koncowy:

```text
READY / PARTIAL / NOT_READY
```

Werdykt musi byc oparty o runtime i testy, nie o deklaracje w dokumentacji.

---

## 3. Role w audycie

| Rola | Odpowiedzialnosc |
|---|---|
| Operator | Dostarcza pomysly, zatwierdza HumanGate, wpisuje jednorazowe klucze API, akceptuje koszty. |
| Auditor | Prowadzi testy, klika UI, zapisuje evidence, klasyfikuje defekty. |
| Fixer | Naprawia kod na biezaco, ale nie zmienia kryteriow testu. |
| Council Observer | Sprawdza czy modele dyskutuja realnie, czy sa role, wagi, critic signature, sentinele. |
| DPO/Security Observer | Sprawdza PII, GDPR, secret handling, audit chains. |
| Release Observer | Sprawdza W14, release gate, deploy, rollback, evidence pack. |
| Funding Observer | Sprawdza funding profile, grant discovery, scoring, dokumenty, HumanGate i audit. |
| W18 Terminal Observer | Obserwuje live terminal, replay, komendy sprawdzajace, raporty modeli i podzial pracy. |
| Skills Observer | Sprawdza registry, manifesty, skill matching, binding do workerow i realne uzycie skillow. |
| W1-W19 Coverage Owner | Pilnuje, zeby kazda warstwa/fala miala test UI, W18 evidence, audit evidence i wynik PASS/FAIL. |

W praktyce jedna osoba moze pelnic kilka rol, ale w raporcie trzeba zapisac,
kto zatwierdzil kazdy HumanGate.

---

## 4. Przygotowanie czystego profilu audytowego

### 4.1. Zamrozenie punktu startowego

Przed czyszczeniem:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
git rev-parse --short HEAD
git status --short
```

Zapisujemy:

- commit,
- galez,
- lokalne zmiany,
- wersje Python/Node/npm,
- OS,
- data/czas startu,
- aktywne porty.

### 4.2. Izolacja danych

Nie usuwamy roboczych baz w repo. Tworzymy osobne sciezki:

```text
data/audit/<audit_id>/aeis_clean.db
logs/audit/<audit_id>/
evidence/audit/<audit_id>/
```

Jezeli system nie wspiera latwego przelaczenia DB path, to jest finding.
Nie wolno ukrywac problemu przez reczne przepinanie kodu bez wpisu w ledgerze.

### 4.2.1. Gate czystej dystrybucji

Ten gate symuluje osobe z zewnatrz, ktora dostaje paczke oprogramowania i
uruchamia ja pierwszy raz na swoim komputerze.

Przed pierwszym kliknieciem UI sprawdzamy:

- brak istniejacych projektow,
- brak istniejacych pomyslow,
- brak istniejacych users/sessions poza wymaganym bootstrap adminem,
- brak seedowanych wynikow W14,
- brak starych audit chain entries w katalogu audytu,
- brak starych kosztow,
- brak starych secretow/API keys,
- brak aktywnych kolejek HumanGate,
- brak starych deployment records,
- brak nieusunietych zasobow cloud z poprzednich testow,
- brak `.db`, `.sqlite`, `.jsonl` i logow, ktore sa uzywane przez runtime poza
  katalogiem `data/audit/<audit_id>` i `logs/audit/<audit_id>`.

PASS:

```text
System startuje jak nowa instalacja: 0 projektow, 0 pomyslow, 0 lessons,
0 starych decyzji, 0 starych kosztow, 0 starych sekretow.
```

FAIL:

```text
CLEAN_DISTRIBUTION_FAIL
```

Kazdy FAIL w tym gate jest P0/P1, bo falszuje caly audyt. Naprawiamy cleanup,
tworzymy nowy `audit_id` i zaczynamy od nowa.

### 4.3. Profil bez bypassow

Obecny `start_backend.ps1` ustawia lokalnie:

```text
SYLION_RBAC_DISABLED=1
SYLION_RATE_LIMIT_DISABLED=1
SYLION_AUTH_BYPASS=1
```

Dla audytu human-like te flagi musza byc wylaczone:

```powershell
$env:SYLION_RBAC_DISABLED="0"
$env:SYLION_RATE_LIMIT_DISABLED="0"
$env:SYLION_AUTH_BYPASS="0"
```

Jezeli bez tych bypassow system nie przechodzi pierwszego uruchomienia, wynik
brzmi: `BOOTSTRAP_BLOCKED_BY_AUTH_OR_RBAC`, a nastepnie naprawiamy przyczyne i
powtarzamy bootstrap.

---

## 5. Faza A - audyt aktualnego systemu przed symulacjami

### A1. Static inventory

Cel: ustalic co istnieje w kodzie.

Sprawdzamy:

- moduly backendu,
- routery API,
- strony frontendu,
- testy,
- W14 Test Center,
- HumanGate,
- Council,
- policy/guardy,
- deploy/VPS,
- audit chainy,
- konfiguracje modeli,
- konfiguracje secretow.

Evidence:

- lista routerow,
- lista stron UI,
- `openapi.json`,
- mapa API -> UI,
- mapa docs -> runtime.

### A2. Runtime boot audit

Cel: sprawdzic, czy czysty system wstaje.

Kroki:

1. Instalacja zaleznosci.
2. Start backendu w profilu audytowym bez bypassow.
3. Start frontendu.
4. Health API.
5. Health UI.
6. OpenAPI.
7. Test czy dashboard widzi backend.
8. Screenshot pierwszego ekranu.

PASS:

- backend startuje bez tracebackow,
- frontend startuje,
- UI nie pokazuje false-green,
- OpenAPI odpowiada,
- brak seedowanych projektow/pomyslow.

FAIL:

- crash,
- dashboard offline,
- dane nie sa puste,
- UI wymaga bypassu,
- API zwraca mock jako live.

### A2.1. Stub/mock/fallback audit

Cel: wykryc, czy system nie udaje dzialania.

Sprawdzamy:

- strony UI, ktore pokazuja dane mimo pustej bazy,
- endpointy zwracajace stale sample bez oznaczenia mock,
- `success=true` bez artefaktu,
- `production_ready` bez release gate evidence,
- model response fallback udajacy realny LLM,
- deploy status success bez zewnetrznego health check,
- Test Center PASS bez test run evidence,
- HumanGate approval bez review trace,
- Council consensus bez prawdziwych glosow.

Zasada:

```text
Stub/mock/fallback jako realna funkcja = FAIL.
Stub/mock jawnie oznaczony jako demo = moze pozostac, ale nie zalicza testu realnej funkcji.
```

P0-P2 zalezne od wplywu. Po naprawie powtarzamy test od bootstrapu danej sciezki.

### A3. Security and secret audit

Cel: sprawdzic, czy klucze mozna wpisac przez UI i czy nie wyciekaja.

Testy:

- wpisanie jednego klucza modelu przez dashboard,
- sprawdzenie czy pole maskuje sekret,
- test minimalnego requestu modelu,
- sprawdzenie logow pod katem wycieku sekretu,
- usuniecie/rotacja klucza,
- ponowny test z nowym kluczem.

Nie wpisujemy prawdziwych stale uzywanych kluczy. Operator generuje jednorazowe
testowe klucze w momencie, gdy test dojdzie do danego ekranu.

### A4. Council reality audit

Cel: sprawdzic, czy Rada faktycznie dyskutuje.

Testy:

- utworzenie sesji Council,
- analiza rol,
- dyskusja rundy drugiej,
- critic signature,
- sentinel evaluation,
- weighted consensus,
- gated consolidation.

PASS:

- widac role,
- odpowiedzi sa rozne i zwiazane z rola,
- critic moze zablokowac,
- sentinele moga blokowac,
- consensus liczy wagi,
- wynik trafia do audit chain.

FAIL:

- wszystkie role zwracaja ten sam tekst,
- brak critic signature,
- brak wag,
- `consolidate` przechodzi mimo blokady,
- UI pokazuje sesje, ktorej backend nie zna.

### A5. HumanGate reality audit

Cel: sprawdzic, czy HumanGate realnie blokuje.

Testy:

- D2 bez blokady,
- D3 z Council/evidence,
- D4 z wymaganym approvalem,
- `needs_info`,
- `rejected`,
- audit review,
- escalation po wielokrotnym `needs_info`.

PASS:

- D4 nie wykonuje sie bez approvalu,
- approval jest widoczny w audit,
- UI i API maja ten sam status,
- odrzucenie zatrzymuje pipeline.

### A6. W14 reality audit

Cel: sprawdzic, czy Test Center blokuje release bez dowodow.

Testy:

- `/test-center/dashboard`,
- `/test-center/catalog`,
- `/test-center/human-lab`,
- `/test-center/simulation`,
- `/test-center/auto-repair`,
- `/test-center/truth-alignment`,
- `/test-center/release-gate`,
- `/test-center/theater`.

PASS:

- release gate blokuje brak evidence,
- findings sa widoczne,
- guardian alerts sa widoczne,
- truth alignment wykrywa drift,
- human-like test ma trace.

### A7. W18 Terminal reality audit

Cel: sprawdzic, czy terminal operatorski W18 jest realnym narzedziem obserwacji,
kontroli i replayu, a nie tylko widokiem tekstu.

Sprawdzamy:

- czy `/terminal` pokazuje aktywne sesje,
- czy `/terminal/replay` potrafi odtworzyc sesje,
- czy terminal widzi eventy Council, workerow, HumanGate, W14 i deployu,
- czy mozna wpisywac bezpieczne komendy sprawdzajace,
- czy mozna poprosic system o raport w trakcie pracy modeli,
- czy raport pokrywa sie z tym, co widzi UI i audit chain,
- czy terminal pokazuje podzial pracy: lane, worker, task, owner, status,
- czy terminal rozroznia live run od replay/fork,
- czy terminal nie wycieka sekretow,
- czy terminal nie pozwala ominac HumanGate przez bezposrednia komende.

Minimalne komendy/operatorskie akcje W18 do przetestowania:

```text
status
report current-run
report council
report workers
report costs
report gates
report tests
report deploy
explain last-decision
show blockers
show audit-tail
request checkpoint
```

Jezeli komendy maja inna skladnie w UI, uzywamy skladni podanej przez dashboard,
ale testujemy te same intencje.

PASS:

- W18 pokazuje aktualny stan bez odswiezania strony,
- raporty w trakcie pracy modeli sa generowane i audytowane,
- podzial pracy zgadza sie z Project/Workers UI,
- komenda sprawdzajaca nie modyfikuje stanu bez jawnego action/HG,
- replay pokazuje ten sam przebieg co audit chain.

FAIL:

- terminal pokazuje stale sample,
- raporty sa mockami,
- W18 nie widzi aktywnego runu,
- terminal pozwala wykonac krok D4/D5 bez HumanGate,
- terminal ukrywa bledy workerow,
- terminal pokazuje status inny niz UI/API/audit bez wyjasnienia.

### A8. Skills layer reality audit

Cel: sprawdzic, czy L4 Skills dziala jako realna warstwa dopasowania
kompetencji, a nie jako lista nazw w UI.

Sprawdzamy:

- czy registry startuje czyste albo z jawnie seedowanymi kanonicznymi skillami,
- czy skill ma manifest, wersje, status, kontrakt, wejscia i wyjscia,
- czy skill moze byc `DRAFT`, `PUBLISHED`, `DEPRECATED`,
- czy system dobiera skille na podstawie rozwijanego pomyslu,
- czy po zmianie Ksiega/Masterplan dobiera inny zestaw skillow,
- czy operator widzi proponowane skille i moze je zatwierdzic/odrzucic,
- czy skill binding trafia do audit chain/evidence,
- czy worker rzeczywiscie uzywa przypietego skilla,
- czy brak wymaganego skilla blokuje build albo tworzy HumanGate,
- czy system odroznia skill lokalny, API skill, model skill i operator skill,
- czy skill nie jest mockiem udajacym gotowa kompetencje.

Minimalne ekrany/API do sprawdzenia:

```text
/skills
/role-catalog
/projects/{projectId}/skills
/projects/{projectId}/workers
/test-center/truth-alignment
/terminal -> report skills
```

Minimalne przypadki testowe:

| Przypadek | Oczekiwany wynik |
|---|---|
| Prosty pomysl bez integracji | Dobor kilku podstawowych skills: planning, UI, test. |
| Pomysl z uploadem zdjecia | Dobor upload/security/vision/OCR skills. |
| Pomysl z PII/GDPR | Dobor pii_redactor, gdpr_dsr, audit, security_review. |
| Pomysl z deployem Hetzner | Dobor deploy, vps, health_check, rollback, cleanup. |
| Operator odrzuca skill | Masterplan/workers aktualizuja sie albo build blokuje. |
| Skill oznaczony DEPRECATED | Nie moze byc wybrany bez jawnego override/HG. |

PASS:

- skill matching zmienia sie wraz z rozwojem pomyslu,
- wybrane skille sa widoczne w Masterplanie i worker planie,
- worker execution odnosi sie do skill binding,
- W18 i UI pokazuja ten sam zestaw skillow,
- brak skillow powoduje czytelny blocker.

FAIL:

- `loaded_skills=0` i system mimo tego buduje,
- UI pokazuje skille, ktorych backend nie zna,
- worker wykonuje task bez skill binding,
- skill mock jest traktowany jak PUBLISHED production skill,
- zmiana Ksiega/Masterplan nie zmienia rekomendacji skillow,
- odrzucenie skilla przez operatora jest ignorowane.

### A9. W1-W19 full coverage audit

Cel: sprawdzic wszystkie warstwy/fale W1-W19 po kolei, na zywych pomyslach,
przez dashboard. Sama obecnosc kodu, dokumentu albo endpointu nie zalicza
warstwy.

Kazda warstwa W1-W19 musi miec:

- zrodlo kanoniczne: dokument/charter/runbook albo jawny finding, ze go brakuje,
- powierzchnie operatorska w dashboardzie,
- minimum jeden test na zywej idei,
- minimum jeden test negatywny,
- evidence w W14 albo audit chain,
- obserwacje w W18,
- wpis PASS/FAIL w macierzy audytu,
- retest po kazdej poprawce.

Jezeli warstwa nie ma jasnej definicji w dokumentacji albo UI, wynik to:

```text
W##_CANON_OR_UI_GAP
```

To jest blad do naprawy, nie powod do pominiecia warstwy.

#### Macierz W1-W19

| Warstwa | Zakres do sprawdzenia | Test przez dashboard |
|---|---|---|
| W1 | Performance + DB: load profile, N+1, cache, migracje, backup/DR. | Na Idea 2/6 wygenerowac dane, obserwowac latency, cache, DB state, backup/restore evidence. |
| W2 | Security: auth, RBAC, rate limit, secrets, audit integrity, dependency safety. | Logowanie/role/rate limit/secret UI; proba dostepu bez roli; sprawdzenie braku bypassow. |
| W3 | Observability: metryki, alerty, tracing, logs, PII redaction, SLO. | Podczas kazdego pomyslu sprawdzic dashboard health, metryki, alert po bledzie, redakcje PII. |
| W4 | Real portals/external integrations. | Dla Idea 3/6 sprawdzic integracje zewnetrzna albo jawny blocker, bez mock success. |
| W5 | CI/CD i multi-env: build, blue/green, migration job, rollback. | Dla Idea 6 przejsc release/deploy flow, migration/rollback, statusy env. |
| W6 | Sign-off: final approval, DR drill, staging soak/report, release decision. | Dla Idea 5/6 wymusic final sign-off i sprawdzic, ze brak evidence blokuje approval. |
| W7 | Role Catalog: role modeli/operatorow, capabilities, 30+ kreatywnych rol. | Zmienic role w Radzie/workerach; sprawdzic czy routing i permissions sie zmieniaja. |
| W8 | Warstwa niezmapowana lub legacy w aktualnym kanonie. | Najpierw znalezc zrodlo prawdy; jezeli brak, otworzyc drift finding i nie oznaczac PASS. |
| W9 | Warstwa niezmapowana lub legacy w aktualnym kanonie. | Jak W8: discovery, UI surface, zywy test albo FAIL jako brak kanonu/UI. |
| W10 | Warstwa niezmapowana lub legacy w aktualnym kanonie. | Jak W8: wymagane mapowanie do modulu, UI i testu na idei. |
| W11 | Provider/model extensions: OpenRouter, Together, Replicate, Fireworks, LM Studio, vLLM, llama.cpp, capability tags. | Wpisac klucze przez UI, testowac routing, capability tags, zakaz uzycia OpenRouter dla modeli z dedykowanym kluczem. |
| W12 | Warstwa niezmapowana lub powiazana z bundle/testing legacy. | Zmapowac do aktualnego modulu; jesli to bundle/testing, sprawdzic bundle validation i blokady. |
| W13 | Task-to-Role / Task-to-Skill Suggester. | Dla kazdej idei sprawdzic rekomendacje rol/skilli i efekt odrzucenia/zmiany przez operatora. |
| W14 | Testing, Simulation, Repair & Release Governance. | Test Center, Human Lab, Auto Repair, Release Gate, Truth Alignment dla kazdego pomyslu. |
| W15 | Ontology Runtime: manifesty, schema compiler, OSDK, branches, lineage. | Dla Idea 2/4/6 dodac obiekty, sprawdzic schema/lineage/branch i UI zgodne z runtime. |
| W16 | Apps Builder: app manifest, widgets, forms, dashboards, workflows, automations. | Dla Idea 1-4 wygenerowac aplikacje, sprawdzic formularze, widgety, workflow i brak mockow. |
| W17 | Deployment Plane: federation, cost ledger, nodes, canary, rollback. | Dla Idea 6 realny Hetzner deploy, health check, cost ledger, rollback/cleanup. |
| W18 | Operator Terminal: live stream, command palette, sessions, replay. | Dla kazdej idei W18 reports: council/workers/skills/tests/cost/deploy/audit-tail. |
| W19 | Policy Plane: guardy, sandbox Jinja, staged rollout, routing gate, policy registry. | Zmienic policies przez UI, wymusic deny/allow/error, sprawdzic audit i blokady. |

W8-W10 i W12 sa celowo oznaczone jako wymagajace discovery, bo w aktualnych
materialach v2 mocno opisane sa W7, W11, W13-W19 oraz historyczne W1-W6.
Audyt ma wykryc, czy W8-W10/W12 maja realny odpowiednik w kodzie i dashboardzie.
Brak odpowiednika to finding, nie PASS.

#### Test zywego pokrycia warstw

Kazda z 6 idei musi miec macierz:

```yaml
idea_layer_coverage:
  idea_id: string
  layers:
    W1: pass|fail|not_applicable_with_reason
    W2: pass|fail|not_applicable_with_reason
    ...
    W19: pass|fail|not_applicable_with_reason
  evidence:
    dashboard_screenshot: path
    w18_report: path
    audit_chain_refs: []
    test_catalog_refs: []
    deployment_catalog_refs: []
```

`not_applicable` wymaga uzasadnienia i approvalu operatora. Nie moze byc uzyte
dla W14, W18, W19, Skills, HumanGate, Council, cleanup ani audit chain.

#### Zasada pelnego pokrycia funkcji

W trakcie 6 pomyslow musimy dotknac wszystkich glownych funkcji, mozliwosci,
zmian, warstw i modulow, ktore system deklaruje jako produkcyjne. Jezeli funkcja
jest widoczna w dashboardzie, musi miec co najmniej:

- klikany happy path,
- klikany negative path,
- sprawdzenie backend/API,
- sprawdzenie W18 albo audit chain,
- test po poprawce, jesli cokolwiek failuje.

Nie wolno powiedziec, ze modul jest sprawdzony, jezeli zostal tylko wymieniony w
inventory albo przeszedl unit test bez operatorskiej symulacji.

### A10. Funding section reality audit

Cel: sprawdzic, czy Funding jest realnym pionem AEIS, a nie statycznym panelem
albo recznie wypelnionym CRM-em grantow.

Funding testujemy osobno oraz jako cross-cutting test dla wybranych produktow
z 6 pomyslow. Minimum: Idea 3 i Idea 6 musza miec probe wyszukania grantow albo
programow finansowania dopasowanych do produktu.

#### Zakres Funding

Sprawdzamy:

- profil firmy/operatora,
- opis projektu do finansowania,
- discovery programow grantowych,
- porownanie zrodel discovery,
- scoring dopasowania,
- eligibility,
- wymagane dokumenty,
- ryzyka formalne,
- HumanGate przed external action,
- audit trail,
- eksport paczki aplikacyjnej,
- monitoring statusu.

#### Discovery provider test

Hipoteza operatora: do wyszukiwania grantow najlepsze beda Perplexity i Google.
Audyt nie zaklada tego jako prawdy. Test ma porownac wyniki.

| Provider | Co testujemy |
|---|---|
| Perplexity | Aktualne web discovery, cytowania, streszczenie warunkow, deduplikacja. |
| Google | Szerokie wyszukiwanie, oficjalne strony programow, aktualnosc wynikow. |
| Manual URL input | Operator wklepuje znany link do programu przez dashboard. |
| LLM scoring | Modele oceniaja dopasowanie, ale nie sa zrodlem prawdy bez URL/cytowania. |

PASS:

- provider discovery jest uruchamiany z dashboardu,
- operator wpisuje query przez pole UI,
- wyniki maja URL, tytul, date albo sygnal aktualnosci, zrodlo i snippet,
- system deduplikuje programy znalezione przez Perplexity i Google,
- scoring pokazuje kryteria i powody odrzucenia,
- finalna rekomendacja odroznia "eligible", "maybe", "not eligible",
- brak cytowania albo nieaktualny wynik obniza confidence,
- external submit wymaga HumanGate.

FAIL:

- funding panel pokazuje seedowane programy jako live search,
- wynik nie ma URL/cytowania,
- system miesza wyniki Perplexity/Google bez wskazania zrodla,
- scoring nie pokazuje powodow,
- aplikacja grantowa moze zostac wyslana bez HumanGate,
- token/search query/sekret wycieka do logow,
- "found grants" pojawia sie przy braku realnego zapytania.

#### Human-like funding flow

Wszystko klikane przez dashboard:

```text
/funding
-> create/update company profile
-> type project description
-> choose providers: Perplexity + Google
-> type grant search query
-> run discovery
-> compare results
-> open result details
-> run eligibility scoring
-> reject one bad result
-> mark one as candidate
-> generate document checklist
-> request HumanGate for external submit
-> export application pack
```

API wolno uzyc tylko do kontroli, czy UI zapisalo dane poprawnie.

#### Funding evidence

Kazdy funding test zapisuje:

```yaml
funding_evidence:
  idea_id: string
  product_ref: string
  query: string
  providers:
    - perplexity
    - google
  results_count: number
  deduped_count: number
  selected_programs: []
  rejected_programs: []
  scoring_refs: []
  human_gate_ref: string
  export_ref: string
  screenshots: []
  audit_refs: []
```

Jezeli Funding nie ma dashboardu lub nie ma realnego discovery, wynik to FAIL,
nie "not applicable".

---

## 6. Faza B - 10 krokow pierwszego uruchomienia

Te kroki wykonujemy klikajac UI tam, gdzie istnieje UI. Terminal jest tylko do
startu procesu i diagnostyki.

| # | Krok | Co testujemy | PASS |
|---|---|---|---|
| 1 | Install/clone | Repo, dependencies, venv, node_modules. | Instalacja bez recznych patchy. |
| 2 | Bootstrap wizard | OS, GPU, RAM, porty, internet, filesystem. | UI pokazuje realny stan hosta. |
| 3 | Tryb modelu | Local/API/Hybrid. | Operator moze wybrac tryb. |
| 4 | Minimum 1 model | Ollama pull albo API key. | Model jest zapisany i testowalny. |
| 5 | Smoke test modelu | `reply with OK`, latency, koszt. | Odpowiedz i koszt widoczne. |
| 6 | Polityki domyslne | Production=HG, cost caps, autonomy, follow-me. | Operator moze zaakceptowac/zmienic. |
| 7 | Bootstrap Council | Minimalny sklad Rady. | System pokazuje role i braki. |
| 8 | Inicjalizacja pamieci | Puste tabele, 0 projektow, 0 lessons. | UI potwierdza cold-start. |
| 9 | Seed Skill Registry | Podstawowe skills. | Skills widoczne i audytowalne. |
| 10 | Health + first HumanGate | Final setup approval. | Bez approvalu system nie przechodzi do pracy. |

Jezeli ktorykolwiek krok nie istnieje w UI, zapisujemy finding:

```text
BOOTSTRAP_UI_GAP: krok X nie ma operatorskiej powierzchni.
```

Potem decydujemy, czy naprawiamy UI od razu, czy testujemy najblizsza istniejaca
powierzchnie. Nie wolno uznac kroku za PASS przez sam fakt istnienia endpointu.

---

## 7. Faza C - konfiguracja modeli i kluczy API

### C1. Minimalna konfiguracja

Do startu potrzebny jest minimum jeden dzialajacy model:

- lokalny Ollama, np. `qwen2.5:7b`, `qwen3.5`, `mistral`,
- albo jeden klucz API: OpenAI, Anthropic, Google, Mistral,
- dla testow specjalnych: DeepL, Hetzner, marketplace sandbox.

### C2. Moment pytania operatora o klucze

Nie pytamy o wszystkie klucze na starcie. Pytamy wtedy, gdy test dochodzi do
konkretnej funkcji.

| Moment | Klucz |
|---|---|
| Smoke test modelu API | OpenAI/Anthropic/Gemini/Mistral, jeden wybrany. |
| Tlumaczenia | DeepL albo inny provider, jezeli pomysl tego wymaga. |
| Funding discovery | Perplexity i Google, wpisane przez dashboard dopiero przy Funding test. |
| Deploy VPS | Hetzner API token, SSH key albo testowy projekt cloud. |
| DNS/domena | Provider DNS, tylko jesli test obejmuje publiczny adres. |
| Marketplace publish | Sandbox/token testowy, nigdy produkcyjny bez osobnego HG. |

Kazdy klucz:

- jednorazowy,
- testowy,
- z minimalnym zakresem uprawnien,
- wpisany przez dashboard,
- rotowany/usuwany po tescie.

### C3. Test sekretnosci

Po wpisaniu klucza:

1. wykonujemy smoke request,
2. sprawdzamy UI maskowania,
3. sprawdzamy logi backendu,
4. sprawdzamy audit chain,
5. sprawdzamy czy export/report nie zawiera sekretu.

Wyciek sekretu = P0/P1, zalezne od zakresu.

---

## 8. Faza D - 6 realnych pomyslow

Pomysly doprecyzuje operator. Plan zaklada rosnaca zlozonosc.

| Pomysl | Zlozonosc | Typ |
|---|---|---|
| Idea 1 | Prosta | Mala aplikacja lub narzedzie bez auth i bez deploy prod. |
| Idea 2 | Niska/srednia | CRUD albo dashboard z prostym modelem danych. |
| Idea 3 | Srednia | Aplikacja z integracja zewnetrzna albo generacja tresci. |
| Idea 4 | Srednia/wysoka | Workflow wieloetapowy, role, testy human-like. |
| Idea 5 | Wysoka | PII/GDPR/security/cost, wymaga D4 i DPO-like approval. |
| Idea 6 | Bardzo wysoka | Rozbudowany system projektowy z workerami, deployem, monitoringiem i rollbackiem. |

### 8.1. Zalozenia operatora do budzetu i providerow

Operator deklaruje:

- po ok. 50 USD na kontach: OpenAI/ChatGPT, Claude/Anthropic, z.ai, Kimi,
  Perplexity,
- dodatkowy klucz OpenRouter do modeli bez dedykowanego dostepu,
- lokalne modele Ollama sa juz na komputerze,
- realny test Hetzner jest dozwolony,
- P0, P1 i P2 blokuja caly audyt do naprawy i retestu.

Zasada routingu:

- OpenAI models tylko przez dedykowany klucz OpenAI.
- Claude models tylko przez dedykowany klucz Anthropic.
- z.ai/GLM tylko przez dedykowany klucz z.ai.
- Kimi tylko przez dedykowany klucz Kimi, gdy zostanie podany przez dashboard.
- Perplexity tylko do research/search i tylko przez dedykowany klucz Perplexity.
- OpenRouter tylko dla modeli, do ktorych nie ma dedykowanego klucza.
- Lokalne Ollama jako domyslny low-cost verifier, sanity checker i drugi glos
  w prostych rundach.

Sekrety wklejone w czat traktujemy jako ujawnione i nie zapisujemy ich w plikach.
Przed realnym audytem operator powinien wygenerowac nowe jednorazowe tokeny i
wpisac je przez dashboard.

### 8.2. Proponowany budzet calego przebiegu

Celem nie jest wydanie calego limitu, tylko sprawdzenie systemu. Proponowany
hard cap modelowy:

| Provider | Limit roboczy | Zastosowanie |
|---|---:|---|
| OpenAI | 35 USD | coding critic, test reasoning, final verifier, trudne naprawy. |
| Anthropic | 35 USD | architect, critic, long-context Ksiega/Masterplan. |
| z.ai | 20 USD | red team, QA, alternate reasoning, cost-aware council. |
| Kimi | 20 USD | frontend/UI, implementation review, long-context code reading. |
| Perplexity | 10 USD | research tylko wtedy, gdy pomysl wymaga aktualnych informacji. |
| Google | 15 USD | dodatkowy multimodal/reasoning slot, jezeli dashboard obsluzy klucz. |
| OpenRouter | 10 USD | tylko brakujace modele, zadne duplikaty providerow dedykowanych. |
| Ollama | 0 USD | baseline, verifier, local-only fallback, tanie rundy. |

Proponowany laczny model cap: ok. 145 USD, z buforem ok. 100 USD na retesty po
naprawach. Cost Sentinel powinien zatrzymac sesje przy 80% limitu danego
pomyslu i auto-stop przy 100%.

### 8.3. Proponowane 6 pomyslow

#### Idea 1 - Generator checklisty odbioru mieszkania

Cel: mala aplikacja bez logowania, ktora generuje liste kontrolna odbioru
mieszkania/domu na podstawie typu lokalu, metrazu i standardu.

Zakres:

- formularz: typ lokalu, metraz, ryzyka, standard,
- wygenerowana checklista pomieszczen i usterek,
- reczna edycja punktow,
- eksport Markdown/PDF albo przynajmniej tekstowy raport,
- brak danych osobowych,
- brak deployu zewnetrznego.

Co testuje w AEIS:

- czysty cold-start pomyslu,
- minimalny Council,
- pierwsza Ksiega,
- pierwszy Masterplan,
- prosta budowa UI,
- W14 release gate dla malej aplikacji.

Budzet: 3-5 USD.  
Modele: Ollama + jeden tani API architect/critic.  
D-level oczekiwany: D1/D2.  
Human-like test: operator tworzy checklisty dla 3 typow lokali, edytuje punkt,
eksportuje wynik, sprawdza pusty formularz i bledne dane.

#### Idea 2 - Mini CRM serwisanta

Cel: prosta aplikacja CRUD dla jednoosobowego serwisu: klienci, zgloszenia,
statusy, notatki i eksport CSV.

Zakres:

- lista klientow,
- zgloszenia serwisowe,
- statusy: new, scheduled, done, invoiced,
- wyszukiwarka,
- filtr po statusie,
- eksport CSV,
- brak prawdziwego logowania, ale przygotowane miejsce na role.

Co testuje w AEIS:

- generowanie modelu danych,
- formularze i walidacje,
- podstawowa persystencja,
- testy CRUD,
- pierwszy maly deploy smoke na Hetzner opcjonalnie.

Budzet: 6-8 USD.  
Modele: Ollama + Claude/OpenAI do architektury i test review.  
D-level oczekiwany: D2, D3 jesli robimy deploy.  
Human-like test: operator tworzy klienta, zgloszenie, zmienia status,
wyszukuje rekord, eksportuje CSV, odswieza UI i sprawdza czy dane zostaly.

#### Idea 3 - Generator opisow e-commerce ze zdjecia

Cel: aplikacja, ktora przyjmuje zdjecie produktu i generuje opis PL/EN/DE,
tagi, atrybuty i CSV do importu marketplace.

Zakres:

- upload zdjecia,
- opis produktu po polsku,
- tlumaczenia EN/DE,
- pole human review przed eksportem,
- CSV export,
- brak automatycznego publikowania do marketplace w v1,
- ochrona przed zdjeciami z osobami lub PII.

Co testuje w AEIS:

- multimodal/model routing,
- Cost Sentinel,
- security sentinel dla uploadu,
- propozycje dodatkowych modeli,
- batch HumanGate dla wyboru modeli,
- test mock-as-live, bo latwo udawac upload/vision,
- Funding discovery dla produktu e-commerce: Perplexity vs Google, URL/cytowania,
  deduplikacja i scoring programu.

Budzet: 12-18 USD.  
Modele: Claude/OpenAI/Kimi lub Google do multimodal, Ollama jako verifier,
Perplexity tylko jesli system chce sprawdzac aktualne wymogi marketplace.  
D-level oczekiwany: D3.  
Human-like test: operator wgrywa 3 zdjecia testowe, poprawia opis, odrzuca jeden
wynik, eksportuje CSV i sprawdza, czy aplikacja nie publikuje nic automatycznie.
Potem operator przechodzi do `/funding`, wpisuje query grantowe dla produktu
e-commerce, uruchamia Perplexity i Google, odrzuca jeden zly wynik i wybiera
jednego kandydata do dokument checklist.

#### Idea 4 - System rezerwacji wizyt z workflow akceptacji

Cel: aplikacja dla malej firmy uslugowej: klient sklada prosbe o termin,
pracownik proponuje termin, manager zatwierdza, system generuje potwierdzenie.

Zakres:

- role: klient, pracownik, manager,
- formularz rezerwacji,
- kolejka prosb,
- workflow approve/reject/reschedule,
- historia decyzji,
- powiadomienie jako mock albo lokalny log,
- testy human-like dla roznych rol.

Co testuje w AEIS:

- workflow wieloetapowy,
- role i uprawnienia,
- HumanGate-like approval wewnatrz aplikacji,
- W14 Human Lab,
- truth alignment UI/API/runtime.

Budzet: 18-25 USD.  
Modele: Claude jako architect, OpenAI jako critic/tester, z.ai albo Kimi jako
red/QA, Ollama jako cheap verifier.  
D-level oczekiwany: D3.  
Human-like test: operator jako klient sklada prosbe, jako pracownik proponuje
termin, jako manager zatwierdza, potem sprawdza odrzucenie i reschedule.

#### Idea 5 - Portal pracowniczy HR z PII/GDPR

Cel: portal pracowniczy z rolami, dokumentami, workflow wnioskow i obsluga GDPR
DSR. To jest pomysl wysokiego ryzyka, ale jeszcze bez pelnego publicznego deployu.

Zakres:

- role: employee, manager, HR admin, DPO,
- logowanie albo jego audytowalny mock, jesli brak IdP,
- dokumenty pracownicze,
- wnioski i workflow akceptacji,
- DSR: access, rectification, erasure, portability,
- audit zmian rol i dokumentow,
- session timeout/rate limit jako wymaganie.

Co testuje w AEIS:

- D4 classification,
- DPIA/DPO-like HumanGate,
- security sentinel,
- GDPR guard,
- PII redaction,
- evidence pack,
- reject/needs_info flow.

Budzet: 30-40 USD.  
Modele: Claude/OpenAI jako primary architect+critic, z.ai red team, Kimi UI,
Ollama sanity, Perplexity bez uzycia chyba ze potrzeba aktualnego compliance
researchu.  
D-level oczekiwany: D4.  
Human-like test: operator sprawdza role, dokumenty, DSR export, soft delete,
brak dostepu employee do panelu HR, audit trail i final approval.

#### Idea 6 - Rozbudowany system projektowy z deployem Hetzner

Cel: mini system zarzadzania projektami i wykonaniem: projekty, backlog,
zadania, budzet, worker lanes, decyzje, audit, release gate, deploy na VPS i
rollback.

Zakres:

- projekty i milestone'y,
- zadania i lane'y,
- role: owner, operator, reviewer, auditor,
- budzet per projekt,
- decision log,
- evidence timeline,
- release gate,
- monitoring health,
- deploy testowy na Hetzner,
- cleanup/rollback po tescie.

Co testuje w AEIS:

- pelna meta-orchestracja 3 rund,
- Rada wielomodelowa,
- worker plan,
- W14 release governance,
- Cost Sentinel,
- Funding discovery dla rozbudowanego systemu projektowego,
- Production/External Action HumanGate,
- Hetzner provisioning,
- deploy, health check, rollback/cleanup,
- final evidence pack.

Budzet modelowy: 55-70 USD.  
Budzet Hetzner: osobny hard cap operatora, rekomendacja 5-15 EUR dla krotkiego
testu malej instancji i natychmiastowego cleanupu.  
Modele: Claude/OpenAI primary, Kimi implementation/UI, z.ai red/QA, Ollama local
verifier, OpenRouter tylko jesli AEIS zasugeruje model bez dedykowanego klucza.  
D-level oczekiwany: D4/D5 dla deployu.  
Human-like test: operator tworzy projekt, dodaje zadania, zmienia statusy,
zatwierdza release gate, akceptuje Hetzner HG, sprawdza URL aplikacji, wymusza
rollback albo cleanup i weryfikuje, ze zasoby zniknely.
Nastepnie operator uruchamia Funding dla gotowego produktu, wpisuje query przez
dashboard, porownuje Perplexity/Google, generuje dokument checklist i blokuje
external submit bez HumanGate.

Kazdy pomysl przechodzi ten sam protokol:

```text
Idea
-> Cost pre-flight
-> Round 1 meta-orchestration: Idea -> Ksiega
-> Council clarification
-> Source of Truth freeze
-> Round 2 meta-orchestration: Ksiega -> Masterplan
-> Masterplan freeze
-> Skill matching and binding
-> Round 3 meta-orchestration: Masterplan -> Build
-> Build authorization
-> Execution
-> W14 Test Center
-> W1-W19 coverage update
-> Funding test, jezeli pomysl moze miec finansowanie albo grant
-> Human-like UI test
-> Deploy, jezeli zakres wymaga
-> Final approval
-> Snapshot, replay, drift audit
```

---

## 9. Trzy rundy meta-orchestracji

### Round 1 - Idea -> Ksiega

Cel:

- zrozumiec pomysl,
- zadac pytania,
- wybrac modele do interpretacji,
- ustalic limit kosztu,
- ustalic sentinele,
- zamrozic Source of Truth.

Operator widzi:

- pytania modeli,
- deduplikowana ankiete doprecyzowujaca,
- propozycje dodatkowych modeli,
- koszt pelnego Council vs bootstrap mode,
- ekran zatwierdzenia orchestracji.

Blokujace HumanGate:

```text
"Czy akceptujesz sklad modeli, limit kosztu i reguly Rady dla stworzenia Ksiega?"
```

PASS:

- Ksiega ma scope, constraints, risks, evidence requirements,
- critic podpisal,
- sentinele nie blokuja albo maja obsluzony blocker,
- operator zatwierdzil freeze.

Test zmiany zdania i suwakow:

- operator najpierw wybiera tani/local-first sklad,
- potem zmienia max koszt,
- potem zwieksza liczbe rund clarification,
- potem wlacza/wylacza legal/security/cost sentinel,
- potem zmienia wage critica albo architecta,
- potem zapisuje orchestracje.

Sprawdzamy, czy AEIS faktycznie uzywa tych ustawien w kolejnej rundzie. Jezeli
UI pozwala zmienic suwak, ale backend/council ignoruje wartosc, wynik to FAIL.

### 9.1. Obowiazkowe panele Meta-Orkiestracji

Kazdy pomysl musi przejsc przez te panele lub ich aktualne odpowiedniki w UI.
Nie wystarczy, ze ekran istnieje. Trzeba zmienic konfiguracje i zobaczyc efekt w
runtime, W18, audit chain i wynikach testow.

| Panel | Co konfigurujemy | Efekt, ktory musi byc widoczny |
|---|---|---|
| Routing LLM Judge | Jakie modele oceniaja decyzje, progi confidence, local/API/hybrid. | Kolejne decyzje uzywaja wybranych modeli, a koszt/latency trafia do ledger. |
| Reguly Rady | Role, wagi, quorum, critic signature, sentinels, dissent policy. | Consensus zmienia sie po zmianie wag/rol; brak podpisu critica blokuje D3+. |
| Rytm Audytora | Jak czesto auditor robi checkpointy, raporty, drift scan, cost scan. | W18 i audit chain pokazuja checkpointy w ustawionym rytmie. |
| Protokol Fixera | Co robi system po findingu: auto-repair, pause, ask operator, max attempts. | P0-P2 zatrzymuja flow, fixer nie robi petli i wymaga retestu. |
| Dispatch Agentow | Jak zadania ida do agentow, lane'y, priorytety, concurrency. | Worker plan i W18 `report workers` pokazuja realny podzial pracy. |
| Katalog Testow | Jakie testy sa wymagane dla projektu i release gate. | W14 ma test charter, test cases i release blockers dla danego pomyslu. |
| Formowanie Zespolow | Dobor zespolow/modeli/workerow do typu pomyslu. | Zespol dla Idea 1 jest mniejszy niz dla Idea 6; zmiany widac w planie. |
| Mapa Zdarzen | Event flow: idea, council, skill, worker, test, deploy, audit. | Event map pokazuje faktyczne zdarzenia, nie statyczny diagram. |
| Rozmowy Modeli | Widok dyskusji modeli, pytan, dissentow, zmian zdania. | Modele odpowiadaja na siebie, a nie tylko generuja niezalezne teksty. |

Minimalna negatywna proba dla kazdego panelu:

- ustawic niska granice kosztu i sprawdzic, czy guard blokuje,
- zmienic wage critica i sprawdzic, czy consensus sie zmienia,
- wylaczyc albo oslabic sentinel i sprawdzic, czy UI wymaga HG przy ryzyku,
- ustawic max fixer attempts = 1 i wywolac blad,
- zmienic concurrency dispatchu i sprawdzic worker lanes,
- dodac wymagany test do katalogu i sprawdzic release gate,
- odrzucic proponowany zespol i sprawdzic re-formowanie,
- sprawdzic event map po realnej akcji,
- poprosic modele o ponowna dyskusje po odpowiedzi operatora.

FAIL:

- panel zapisuje wartosc, ale runtime jej nie uzywa,
- W18 raportuje inny stan niz UI,
- guard nie reaguje na przekroczenie konfiguracji,
- release gate nie widzi wymaganego testu z katalogu,
- event map pokazuje zdarzenia, ktorych nie ma w audit chain,
- rozmowy modeli nie sa powiazane z decyzjami.

### Round 2 - Ksiega -> Masterplan

Cel:

- sprawdzic, czy po doprecyzowaniu pomyslu nadal mamy dobry sklad modeli,
- ustalic topologie zespolow,
- dobrac role Rady do masterplanu,
- zmienic cost policy, jezeli zakres urosl,
- wygenerowac masterplan.

Blokujace HumanGate:

```text
"Czy akceptujesz sklad Rady i zasady planowania dla tej Ksiega?"
```

PASS:

- masterplan ma kroki,
- kazdy krok ma ownera, success criteria i test,
- koszt jest oszacowany,
- ryzyka maja mitigacje,
- D-level jest uzasadniony.

Test zmiany zdania:

- operator odrzuca pierwsza propozycje masterplanu,
- zmienia topology z malej na srednia albo odwrotnie,
- zmienia role Council,
- obniza albo podnosi cost cap,
- wymusza dodatkowego critic/security reviewer,
- zatwierdza dopiero druga wersje.

AEIS musi pokazac, ze druga wersja masterplanu rozni sie zgodnie z ustawieniami.
Brak reakcji na konfiguracje = P1/P2.

Skills checkpoint po Round 2:

- system pokazuje proponowane skille dla Masterplanu,
- operator zmienia co najmniej jeden skill: zatwierdza, odrzuca albo wymaga
  alternatywy,
- AEIS przelicza worker plan,
- W18 `report skills` pokazuje ten sam zestaw,
- audit/evidence zapisuje decyzje skill binding.

Brak reakcji worker planu na zmiane skilla = FAIL.

Meta-Orkiestracja po Round 2:

- ponownie testujemy Routing LLM Judge, bo po Ksiedze mogly zmienic sie
  wymagane modele,
- ponownie testujemy Reguly Rady, bo Masterplan moze miec inna klase D-level,
- tworzymy albo aktualizujemy Katalog Testow dla tego Masterplanu,
- aktualizujemy Formowanie Zespolow,
- sprawdzamy Mape Zdarzen od idea intake do masterplan freeze,
- prosimy W18 o raport: `report council`, `report skills`, `report workers`,
  `report tests`, `show audit-tail`.

### Round 3 - Masterplan -> Build

Cel:

- zablokowac koszt,
- zablokowac modele do wykonania,
- ustawic external action policy,
- ustawic rollback policy,
- zatwierdzic rozpoczecie budowy.

Blokujace HumanGate:

```text
"Czy zaczac budowe w ramach tego kosztu, tych modeli i tych guardow?"
```

PASS:

- build ma cost cap,
- 80% kosztu wysyla HG,
- 100% kosztu auto-stop,
- deploy wymaga HG,
- rollback jest opisany,
- W14 ma Test Charter.

Test posluszenstwa konfiguracji:

- operator ustawia niski cost cap i sprawdza, czy Cost Sentinel blokuje,
- operator zwieksza cap przez Financial HG i powtarza,
- operator zmienia autonomy z medium na low,
- operator wymusza production deploy HG,
- operator wlacza rollback mandatory.

Jezeli build rusza mimo blokujacego capa, braku HG albo ignoruje autonomy level,
wynik to FAIL.

Build nie moze ruszyc, jezeli:

- wymagany skill nie istnieje,
- skill jest `DRAFT` albo `DEPRECATED` bez HumanGate override,
- worker nie ma skill binding,
- skill contract nie ma testu albo output schema,
- skill jest mockiem, a test wymaga realnej funkcji.

Meta-Orkiestracja przed buildem:

- Routing LLM Judge ma miec finalny lock modeli do build/test/fixer.
- Rytm Audytora ma miec ustawione checkpointy na czas wykonania.
- Protokol Fixera ma miec progi P0-P4, max attempts i retest policy.
- Dispatch Agentow ma miec finalny worker plan i concurrency.
- Katalog Testow ma miec testy blokujace release.
- Mapa Zdarzen ma miec oczekiwany event flow.
- Rozmowy Modeli maja miec finalna decyzje i podpis critica, jesli D3+.

Kazda zmiana na tym etapie musi byc widoczna w build authorization summary.

---

## 10. Human-like simulation protocol

Kazdy test operatorski wykonujemy przez UI.

### 10.1. Narzedzia

- Browser / Playwright do klikania.
- Screenshot po kazdym krytycznym ekranie.
- Network/console error capture.
- Log backendu.
- Audit chain verification.
- Test Center evidence.
- W18 Terminal live view i replay do obserwacji pracy modeli oraz workerow.

### 10.2. Zasada testu

Jeden test human-like sklada sie z:

1. otwarcia UI jak operator,
2. klikniecia wymaganej sciezki,
3. wpisania danych do pol dashboardu tak, jak robi to czlowiek,
4. odczytania statusu,
5. sprawdzenia backendu tylko jako potwierdzenia,
6. zapisania screenshotu,
7. sprawdzenia audit/evidence.

Nie wolno:

- tworzyc pomyslu przez `curl`, jezeli testujemy Idea Vault,
- zatwierdzic HumanGate przez API, jezeli testujemy dashboard,
- wkleic gotowego rekordu do bazy zamiast wpisac go w UI,
- wygenerowac funding query/API request poza dashboardem, jezeli testujemy Funding,
- seedowac wynikow testu,
- recznie zmieniac bazy, zeby odblokowac flow,
- zmieniac acceptance criteria po fakcie.

Rola AI w tym protokole:

- AI klika dashboard jak operator,
- AI wpisuje tekst w pola UI sekwencyjnie, najlepiej z human-like typing delay,
- AI obserwuje frontend, network, console i backend,
- AI uzywa API tylko do sprawdzenia poprawnosci dzialania, diagnostyki i
  potwierdzenia, ze UI nie klamie,
- AI nie wykonuje akcji przez API, jezeli dana akcja ma byc wykonana przez
  czlowieka w dashboardzie.

### 10.3. Klikane sciezki minimalne

Dla kazdego z 6 pomyslow:

```text
/idea-vault
-> create idea
-> idea detail
-> discuss/council
-> answer clarification
-> approve Round 1 meta-orchestration
-> freeze Source of Truth
-> approve Round 2 meta-orchestration
-> freeze Masterplan
-> approve Round 3 build authorization
-> projects
-> project detail
-> workers/orchestration
-> test-center
-> terminal live/replay
-> human-gate
-> release-gate
-> final approval
```

Jezeli ktoregos ekranu nie ma albo nie dziala, to jest finding.

### 10.4. Obowiazkowe uzycie W18 podczas kazdego pomyslu

Dla kazdego z 6 pomyslow operator musi uzyc terminala W18 co najmniej w tych
momentach:

| Moment | Co robimy w W18 |
|---|---|
| Po utworzeniu idei | `status` i `report current-run`, sprawdzenie czy terminal widzi nowa idee. |
| Podczas Council Round 1 | `report council`, sprawdzenie rol, modeli, wag i dissentow. |
| Po zmianie meta-orchestracji | `explain last-decision`, sprawdzenie czy suwaki/role/koszty zostaly uwzglednione. |
| Podczas masterplanu | `report workers` albo odpowiednik, sprawdzenie lane/task/owner. |
| Po skill matchingu | `report skills`, sprawdzenie skill -> worker -> task. |
| Przed build authorization | `report costs` i `show blockers`. |
| Podczas execution | obserwacja live eventow workerow i checkpoint. |
| Podczas W14 | `report tests`, porownanie z Test Center. |
| Przed deployem | `report deploy`, `report gates`, potwierdzenie HG. |
| Po final approval | `show audit-tail` i replay/fork jezeli dostepny. |

Kazdy raport terminalowy porownujemy z UI i backendem. Rozjazd jest findingiem.

W18 nie moze byc bocznym kanalem do wykonania akcji. Jezeli terminal przyjmuje
komende, ktora zmienia stan projektu, musi utworzyc action, audit entry i jezeli
trzeba HumanGate.

### 10.5. Katalog testow i katalog wdrozen produktow AEIS

Dla kazdego pomyslu AEIS musi utworzyc lub zaktualizowac dwa katalogi.

#### Katalog testow

Minimalne pola:

```yaml
test_catalog_entry:
  project_id: string
  idea_id: string
  source_of_truth_ref: string
  masterplan_ref: string
  required_tests:
    - id: string
      type: unit | api | ui | human_like | security | gdpr | deploy | rollback
      blocker_level: P0 | P1 | P2 | P3 | P4
      evidence_required: true
  release_gate_required: true
  human_gate_required_for_release: bool
```

W14 musi widziec ten katalog. Jezeli operator dodaje test w UI, release gate musi
go uwzglednic. Jezeli test jest wymagany i nie wykonany, final approval ma byc
zablokowany.

#### Katalog wdrozen produktow

Minimalne pola:

```yaml
deployment_catalog_entry:
  project_id: string
  product_name: string
  environment: local | staging | vps | production
  provider: local | hetzner | other
  artifact_ref: string
  deploy_plan_ref: string
  rollback_plan_ref: string
  healthcheck_url: string
  last_deploy_status: pending | running | success | failed | rolled_back
  cleanup_required: bool
  cleanup_status: not_started | done | failed
```

Katalog wdrozen musi pokazac, co AEIS faktycznie wyprodukowal. `success` bez
artefaktu, URL, health checku i cleanup evidence jest FAIL.

---

## 11. Deploy test, w tym Hetzner VPS

Deploy test robimy dopiero dla pomyslow, ktore tego wymagaja, najpewniej Idea 4-6.

### 11.1. Pre-flight

Operator dostarcza:

- testowy Hetzner API token,
- limit kosztu,
- region,
- typ instancji,
- SSH key albo testowy sposob dostepu,
- zgode na utworzenie i usuniecie zasobow,
- ewentualnie testowa domena/DNS.

HumanGate:

```text
Financial + Production + External Action
```

### 11.2. Test deployu

AEIS powinien:

1. zaproponowac plan infrastruktury,
2. pokazac koszt,
3. wymagac approval,
4. utworzyc VPS,
5. wdrozyc aplikacje,
6. wykonac health check,
7. wykonac smoke test UI,
8. zapisac deployment evidence,
9. wykonac rollback albo cleanup testowy.

PASS:

- zasob powstaje tylko po HG,
- aplikacja odpowiada z VPS,
- logi deployu sa w evidence,
- koszt jest zapisany,
- cleanup usuwa zasob,
- rollback jest przetestowany albo jawnie udokumentowany jako nieuruchomiony.

FAIL:

- system tworzy VPS bez approvalu,
- klucz wycieka do logu,
- brak cleanup,
- brak health check,
- deploy status `success`, ale aplikacja nie odpowiada.

---

## 12. Bug loop: znajdz, napraw, powtorz

Kazdy blad przechodzi jedna petle:

```text
Finding
-> severity P0-P4
-> reproduction steps
-> screenshot/log/evidence
-> root cause
-> code fix
-> unit/API test, jezeli sensowne
-> ten sam human-like retest
-> regression check
-> close finding
```

Nie zamykamy findingu po samej poprawce kodu. Zamyka go dopiero powtorka
sciezki operatorskiej.

Po kazdej poprawce:

1. zatrzymujemy biezacy test,
2. zapisujemy root cause i pliki zmienione,
3. uruchamiamy test jednostkowy/API tylko jako szybka weryfikacje techniczna,
4. resetujemy dane tej sciezki do czystego punktu wejscia,
5. wracamy do dashboardu,
6. powtarzamy klikana sciezke od poczatku danego flow,
7. dopiero wtedy zamykamy finding albo eskalujemy.

Punkt wejscia zalezy od miejsca bledu:

| Gdzie wykryto blad | Punkt powrotu po poprawce |
|---|---|
| Bootstrap/cleanup | Nowy `audit_id`, start od pierwszego uruchomienia. |
| Model key setup | Ekran konfiguracji modeli, ponowne wpisanie testowego klucza. |
| Idea intake | `/idea-vault`, utworzenie idei od nowa. |
| Round 1 | Ekran meta-orchestracji Round 1. |
| Ksiega freeze | Ponowna deliberacja i freeze Ksiega. |
| Round 2 | Ekran meta-orchestracji Round 2. |
| Round 3/build | Build authorization od nowa. |
| Worker execution | Ponowny start execution z tym samym planem. |
| W14 | `/test-center`, ponowny release/test flow. |
| W18 terminal | `/terminal` i `/terminal/replay`, ponowny raport live/replay. |
| Skills | `/skills` i project skills, ponowny match/binding/reject flow. |
| Deploy | Production HG + deploy od nowa na czystym zasobie. |
| Cleanup | Weryfikacja zasobow zewnetrznych od zera. |

### 12.1. Severity

| Severity | Znaczenie |
|---|---|
| P0 | Blokuje audyt albo grozi utrata danych/sekretow/kosztow. |
| P1 | Blokuje kluczowy flow: bootstrap, idea, council, HG, deploy, test. |
| P2 | Wazna funkcja dziala zle, ale jest obejscie operatorskie bez bypassu. |
| P3 | UI/UX, brak komunikatu, niespojnosc mniej krytyczna. |
| P4 | Kosmetyka lub dokumentacja. |

P0/P1 naprawiamy przed przejsciem dalej.

---

## 13. Kryteria PASS/FAIL dla calego audytu

### PASS

System moze dostac PASS, jezeli:

- czysty bootstrap przechodzi,
- minimum jeden model dziala,
- klucze sa wpisywane przez UI i nie wyciekaja,
- Council prowadzi realna dyskusje,
- HumanGate blokuje D4/D5,
- guardy potrafia blokowac,
- warstwa Skills dobiera, zapisuje i egzekwuje skill binding,
- 6 pomyslow przechodzi przez pelny protokol albo ma jasno naprawione findingi,
- W14 blokuje release bez evidence,
- W18 terminal pokazuje live stan, raporty i replay zgodne z UI/API/audit,
- przynajmniej jeden deploy zewnetrzny przechodzi z cleanupem,
- audit chains sa clean,
- final report ma dowody.

### PARTIAL

PARTIAL, jezeli:

- system buduje aplikacje, ale nie ma pelnego HG/evidence,
- deploy dziala tylko lokalnie,
- Council dziala czesciowo,
- W14 nie pokrywa wszystkich flow,
- W18 dziala tylko jako obserwacja czesciowa bez pelnego replayu,
- Skills dziala czesciowo, ale wymaga dopiecia czesci manifestow/worker binding,
- czesc pomyslow wymaga dalszych napraw.

### NOT_READY

NOT_READY, jezeli:

- bootstrap wymaga bypassu,
- UI nie potrafi przejsc podstawowego flow,
- D4/D5 przechodzi bez HumanGate,
- build startuje bez wymaganych skills albo ignoruje odrzucony skill,
- klucze wyciekaja,
- deploy tworzy zasoby bez zgody,
- statusy `complete` pojawiaja sie bez artefaktow,
- terminal W18 pozwala ominac HumanGate albo pokazuje mock/live false-green,
- testy sa omijane zamiast naprawiane.

---

## 14. Pytania do operatora przed wykonaniem

Te odpowiedzi sa potrzebne zanim zaczniemy rzeczywisty audyt.

### 14.1. Pomysly 1-6

Dla kazdego pomyslu podaj:

```text
Nazwa:
Cel:
Dla kogo:
Must-have:
Nice-to-have:
Czego nie robimy:
Czy wymaga logowania:
Czy wymaga PII/GDPR:
Czy wymaga platnych modeli/API:
Czy wymaga deployu:
Docelowy efekt koncowy:
Kryteria akceptacji:
Maksymalny koszt testu:
```

Proponowana skala:

1. Pomysl prosty, np. mala aplikacja bez auth.
2. Pomysl CRUD/dashboard.
3. Pomysl z integracja lub generacja tresci.
4. Pomysl workflow z rolami.
5. Pomysl z PII/security/compliance.
6. Rozbudowany system projektowy z deployem, monitoringiem i rollbackiem.

### 14.2. Modele i klucze

Odpowiedz:

```text
Czy mozemy pobierac lokalne modele przez Ollama?
Jaki model lokalny preferujesz na start?
Jaki pierwszy testowy klucz API dasz: OpenAI / Anthropic / Google / Mistral?
Jaki dzienny limit kosztu ustawiamy?
Jaki limit kosztu na jeden pomysl?
Czy pozwalasz systemowi proponowac pobranie dodatkowych modeli?
```

### 14.3. Deploy

Odpowiedz:

```text
Czy testujemy Hetzner realnie?
Jaki maksymalny koszt VPS?
Jaki region?
Czy token ma prawo tworzyc i usuwac serwery?
Czy testujemy DNS/domene?
Czy po tescie zawsze usuwamy zasoby?
```

### 14.4. Poziom rygoru

Odpowiedz:

```text
Czy P0/P1 blokuje caly audyt do naprawy? (rekomendacja: tak)
Czy P2 naprawiamy od razu czy zapisujemy i idziemy dalej?
Czy kazdy pomysl ma miec finalny deploy, czy tylko Idea 6?
Czy koszt modelu ma byc hard-stop, czy moze pytac o podniesienie limitu?
```

---

## 15. Kolejnosc realnego wykonania

1. Operator odpowiada na pytania z sekcji 14.
2. Tworzymy `audit_id`.
3. Tworzymy czysty profil DB/log/evidence.
4. Startujemy backend bez bypassow.
5. Startujemy frontend.
6. Robimy audyt A1-A6.
7. Naprawiamy blokery bootstrapu.
8. Wykonujemy 10 krokow pierwszego uruchomienia.
9. Wpisujemy pierwszy model/API key przez dashboard.
10. Uruchamiamy Idea 1.
11. Po kazdym pomysle robimy mini-retro: koszty, bledy, co AEIS wyprodukowal.
12. Idea 6 konczy sie testem deployu, najlepiej Hetzner.
13. Uruchamiamy finalne testy W14, W18 replay i audit chain verification.
14. Spisujemy finalny werdykt.

---

## 16. Najwazniejsze ryzyka

| Ryzyko | Kontrola |
|---|---|
| Nieczysty start przez stare DB/logi | Osobny audit profile i sprawdzenie 0 danych. |
| Bypass auth/RBAC | Profil audytowy z `*_BYPASS=0`. |
| Koszty modeli | Pre-flight estimate, cap, cost sentinel, HG at 80%. |
| Wyciek API keys | UI secret handling test + log scan. |
| False-green UI | Porownanie UI z API, audit chain i runtime. |
| Deploy bez cleanup | HumanGate + cleanup evidence mandatory. |
| Omijanie failing tests | Bug loop wymusza retest tej samej sciezki. |
| Mock jako live | W14 mock sentinel i truth alignment. |
| Terminal jako slepy podglad | Obowiazkowe W18 raporty live + replay + porownanie z UI/API/audit. |
| Skills jako martwa lista | Obowiazkowy skill matching, operator reject flow i worker binding evidence. |

---

## 17. Finalny raport PDF i screenshot evidence

Finalny audyt ma byc czytelny dla osoby z zewnatrz, ktora nie siedziala przy
terminalu. Dlatego kazdy istotny krok operatorski musi miec screenshot i opis.

Zakladany wolumen: 700-1000 screenshotow. Przy takim rozmiarze raport dzielimy
na tomy, z jednym indeksem glownym:

```text
evidence/audit/<audit_id>/pdf/
  00_INDEX.pdf
  01_BOOTSTRAP_AND_CLEAN_STATE.pdf
  02_SYSTEM_REALITY_AUDIT.pdf
  03_IDEA_1_SIMPLE_APP.pdf
  04_IDEA_2_CRM.pdf
  05_IDEA_3_ECOM_IMAGE.pdf
  06_IDEA_4_WORKFLOW.pdf
  07_IDEA_5_HR_GDPR.pdf
  08_IDEA_6_PROJECT_SYSTEM_DEPLOY.pdf
  09_W1_W19_COVERAGE.pdf
  10_BUG_FIX_RETEST_LEDGER.pdf
```

### 17.1. Format pojedynczego kroku w raporcie

Kazdy krok ma miec:

```yaml
step:
  id: "IDEA3-R2-014"
  timestamp: "ISO-8601"
  screen: "/idea-vault/..."
  action: "Klikam 'Wyslij do Rady'"
  expected_effect: "Powstaje Council session z rolami i cost pre-flight"
  actual_effect: "Council session utworzona, 5 rol, cost estimate 1.20 USD"
  result: PASS | FAIL | BLOCKED | RETEST_PASS
  screenshot: "screens/IDEA3-R2-014.png"
  w18_ref: "terminal_report_IDEA3-R2-014.txt"
  audit_refs:
    - "council_wedge.jsonl:line..."
    - "idea_lifecycle.jsonl:line..."
  bug_ref: "BUG-023"
```

Na stronie PDF:

- screenshot jest glownym elementem,
- pod screenshotem krotki opis: co klikam i po co,
- obok albo pod spodem: oczekiwany skutek, faktyczny skutek, PASS/FAIL,
- jezeli jest blad: wskazanie findingu i numeru retestu,
- jezeli jest HumanGate: kto zatwierdzil, jaka decyzja, jaki audit ref,
- jezeli jest koszt: cost estimate i cost actual,
- jezeli jest W18: cytat/summary z raportu terminala.

Opis jednego kroku ma miescic sie zwykle na jednej stronie razem ze
screenshotem. Jezeli ekran jest zlozony, opis moze przejsc na druga strone.

### 17.2. Nazewnictwo screenshotow

```text
screens/
  BOOT-001-clean-workspace.png
  BOOT-002-install-start.png
  IDEA1-R1-001-create-idea.png
  IDEA1-R1-002-cost-preflight.png
  IDEA1-R1-003-council-questions.png
  IDEA1-R2-001-masterplan-meta.png
  IDEA1-W18-001-report-council.png
  IDEA1-W14-001-release-gate.png
  IDEA6-DEPLOY-001-hetzner-hg.png
  IDEA6-DEPLOY-002-vps-created.png
  IDEA6-DEPLOY-003-healthcheck.png
  IDEA6-DEPLOY-004-cleanup-done.png
```

Screenshot bez wpisu w step ledger nie zalicza evidence. Wpis bez screenshotu
jest dopuszczalny tylko dla krokow czysto terminalowych i wymaga uzasadnienia.

### 17.3. Screenshoty obowiazkowe

Dla kazdego pomyslu minimum:

- idea creation,
- cost pre-flight,
- Round 1 meta-orchestration,
- pytania modeli,
- odpowiedzi operatora,
- Council discussion,
- critic signature,
- sentinels,
- Ksiega freeze,
- Round 2 meta-orchestration,
- Masterplan,
- skills matching,
- team formation,
- test catalog,
- Round 3 build authorization,
- HumanGate approval/reject/needs_info,
- W18 report council/workers/skills/cost/tests,
- worker execution,
- W14 dashboard,
- truth alignment,
- release gate,
- produced app UI,
- manual human-like test of produced app,
- final approval,
- audit chain verification,
- snapshot/replay,
- cleanup.

Dla Idea 6 dodatkowo:

- Hetzner key entry screen, bez widocznego sekretu,
- Production/External Action HumanGate,
- server creation status,
- deployment log,
- public/private healthcheck,
- rollback albo cleanup,
- potwierdzenie, ze zasob zniknal.

### 17.4. Retesty w PDF

Kazdy blad P0-P2 ma miec sekwencje:

```text
FAIL screenshot
-> finding page
-> fix summary
-> technical verification
-> same-flow retest screenshot
-> RETEST_PASS albo nadal FAIL
```

Nie wolno zamknac P0-P2 bez screenshotu retestu z dashboardu.

### 17.5. Generowanie PDF

Preferowany pipeline:

1. screenshoty zapisywane jako PNG,
2. step ledger zapisywany jako JSONL/YAML,
3. generator sklada Markdown/HTML,
4. render do PDF,
5. PDF ma spis tresci, numery stron i indeks screenshotow.

Minimalny output:

```text
AEIS_HUMAN_SIMULATION_AUDIT.pdf
AEIS_HUMAN_SIMULATION_AUDIT_INDEX.md
screens/
step_ledger.jsonl
```

Jezeli raport przekracza rozsadny rozmiar PDF, dzielimy go na tomy i generujemy
`00_INDEX.pdf` z linkami/nazwami tomow.
