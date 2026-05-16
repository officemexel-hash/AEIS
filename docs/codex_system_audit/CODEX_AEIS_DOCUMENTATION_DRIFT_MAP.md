# CODEX AEIS DOCUMENTATION DRIFT MAP

**Status:** wersja robocza 0.1  
**Cel pliku:** pokazac, gdzie dokumentacja, prompty i audit Claude'a rozjezdzaja sie z kodem oraz runtime  
**Regula dowodowa:** kod > runtime > API > UI > testy > dokumentacja > audit innego modelu

## 1. Najwazniejsze drifty w jednym miejscu

| Obszar | Kanon / dokumentacja / audit Claude'a | Stan ustalony przez Codex | Typ driftu | Waga |
|---|---|---|---|---|
| Skala systemu | obraz systemu ~65 modulow i klarownych warstw | runtime zdrowia raportuje `119` modulow, repo ma `30` pakietow backendowych i `354` moduly `.py` | growth drift | CRITICAL |
| Distributed Build | osobne serwery i czyste warstwy rozproszone | jedna szeroka aplikacja FastAPI z federacja subsystemow | topology drift | HIGH |
| Human Gate | jeden nadrzedny plane zgody czlowieka | co najmniej trzy sciezki: `workspace humangate`, globalne `gates/human`, funding-local approvals | governance drift | CRITICAL |
| Council / rada modeli | jedna spojna rada modeli sterujaca planem | council istnieje, ale runtime potrafi zejsc do `active_size = 1` i `enabled = false` przy zachowaniu nazwy `planner_council` | semantics drift | HIGH |
| Memory | kanoniczna wspolna pamiec AEIS | globalne `/memory/*` istnieje, ale execution trzyma tez osobne `runtime.sqlite` per projekt, startup binding jest niepelny, a `/memory/evidence/stats` jest broken | plane drift | HIGH |
| Skills | dokumentacyjnie warstwa centralna | skills istnieja jako kod, API i UI, ale runtime execution plane startuje z `loaded_skills = 0` i nie wykonuje nawet seedowego skillu | integration drift | HIGH |
| Funding | w kanonie i starych opisach nie byl pierwszoplanowy | realny pion domenowy z backendem, store, UI i lokalnym approval plane | underdocumented implementation drift | HIGH |
| Mobile | prompt bardzo szczegolowo opisuje docelowy system | brak kodu backend/frontend mobile w `src/` | overdocumented / prompt-only drift | HIGH |
| Operator Console | pojedyncza warstwa operatora | nowy Next.js + osobny legacy dashboard Python | surface drift | HIGH |
| Lab extensions | slabo opisane lub nieobecne w kanonie | `cellular`, `sdr`, `vps`, `container`, `devices` sa realne i celowe | canon gap | MEDIUM |
| Runtime truth | dokumentacja operacyjna sugeruje proste start/stop truth | PID files sa rozjechane, frontend bind byl niestabilny miedzy probami | operational drift | MEDIUM |
| Observability | bywa czytane jako brakujace lub tylko planowane | metrics, traces i logs roundtrip sa zywe, ale backend jest lokalny i nietrwaly | maturity drift | MEDIUM |

## 2. Drift wzgledem Ksiegi v3.5 i Distributed Build

### 2.1. Z czystej architektury warstwowej do federacyjnego control-plane

Kanon i architektura rozproszona sugerowaly:

- osobne lub wyraznie oddzielone runtime planes
- jeden kanoniczny przeplyw planowania
- jeden Human Gate
- jedna warstwa operatorska

Kod i runtime pokazuja dzis:

- jedna szeroka aplikacje FastAPI montujaca bardzo duzo routerow
- silny spine `workspace`
- osobny engine wykonawczy `project_mode`
- osobny globalny governance plane
- osobne planes w fundingu
- rownolegly legacy dashboard

To nie jest brak systemu. To jest system, ktory rozrosl sie federacyjnie i przestal miescic w prostym opisie z dokumentacji.

### 2.2. `workspace` jest duzo wazniejszy niz wynika z wiekszosci starych opisow

Najmocniejszy obecnie dowod kanonicznego AEIS nie siedzi tylko w plikach governance, tylko w `workspace`:

- kickoff
- source-of-truth / canon book
- masterplan
- wybory councilu
- wybory autonomii
- Human Gate session tree
- launch do execution engine

W probe kontrolnej `project_a81b2c935d6c` flow doszedl do:

- dwoch zatwierdzonych approvals (`book`, `operating_model`)
- frozen masterplanu
- 4 modulow execution
- 6 workerow w puli
- 5 council members
- 29 warstw hierarchy

To oznacza, ze dokumentacja, ktora opisuje AEIS bez `workspace` jako glownego spinu, jest juz nieaktualna.

### 2.3. Funding jest zbyt slabo opisany przez stary kanon

Funding nie jest dodatkiem ani cienkim stubem. W kodzie i runtime potwierdzone sa:

- store
- sessions
- approval events
- submission flow
- frontend operatorski

Drift polega tu nie na braku implementacji, tylko na tym, ze kanon i starsze opisy nie nadazaja za rzeczywistym znaczeniem tego pionu.

### 2.4. Mobile ma odwrotny drift niz funding

W przypadku mobile drift jest odwrotny:

- prompt opisuje bardzo dokladnie docelowy produkt
- w `src/` brak realnego backendu i UI mobile

Czyli dokumentacja wyprzedza implementacje, zamiast za nia nadazac.

### 2.5. Memory i skills maja dzis drift typu "implemented but not joined"

To nie sa subsystemy `missing`.

To sa subsystemy, w ktorych:

- kod istnieje
- API istnieje
- czesc funkcji dziala

ale brakuje kluczowego zszycia runtime:

- memory nie ma jednego, jawnego startup binding
- evidence stats route jest broken
- skills registry zyje, ale skills runtime nie laduje niczego

To jest inny typ driftu niz "brak funkcji": to drift integracyjny i bootstrapowy.

## 3. Drift wzgledem audytu Claude'a

## 3.1. Gdzie Claude mial racje

Claude trafnie wychwycil:

- system nie jest production ready
- governance jest rozszczepione
- memory nie jest jedna wspolna warstwa
- legacy dashboard jest problemem truth plane
- dokumentacja odstaje od kodu

To sa trafne osie problemu.

### 3.2. Gdzie Claude byl zbyt ostry albo zbyt wczesny

Z dzisiejszego audytu Codexa wynika, ze Claude niedoszacowal dojrzalosc:

- `workspace`
- `funding`
- `skills`
- `projects`
- `workers`
- `observability`

Najwieksza roznica interpretacyjna nie brzmi:

- "Claude wymyslil system, ktorego nie ma"

tylko:

- "Claude zbyt czesto klasyfikowal cos jako missing lub experimental, podczas gdy to juz jest implemented but fragmented"

### 3.3. Gdzie Claude moze wprowadzac pozniejszy masterplan w blad

Dwa szczegolnie wazne przypadki:

1. `project_mode`
   - nie wyglada jak cienki eksperyment
   - stoi za realnym `launch` i generowaniem bundle/execution

2. `funding`
   - nie jest lekkim stubem do dopisania
   - ma juz wlasna lokalna logike governance i submit

Jesli przyszly masterplan bedzie budowany tak, jakby te obszary dopiero powstawaly, to latwo bedzie nadpisac dzialajacy runtime zamiast go skonsolidowac.

Drugi blad planistyczny moze dotyczyc `skills` i `memory`:

- nie wolno traktowac ich jako pustych greenfieldow
- trzeba je traktowac jako istniejace warstwy z uszkodzonym bootstrapem i niepelna integracja

### 3.4. Gdzie Claude parallel ownership i prompt execution sa technicznie ryzykowne

W `docs/claude_system_audit/parallel` sa zalozenia, ktore trzeba skorygowac przed uzyciem:

- `PROMPT_02_CODEX_AGENT_B.md` traktuje `skills/` i `memory/*` jako nowe greenfieldowe katalogi
- ten sam prompt planuje nowe `api/skills_routes.py`, mimo ze `src/sylion-pipeline/sylion/api/skills_routes.py` juz istnieje
- `PROMPT_03_KIMI_AGENT_K.md` planuje fundingowe dopelnienia jako osobne nowe pliki poza juz istniejacym `funding_autopilot`
- szkic integracji przez nowy `core/*` moze ominac realny spine `workspace -> project_mode`

To nie przekresla struktury parallel planu, ale oznacza, ze:

- jego szkic organizacyjny jest uzyteczny
- jego tresc techniczna wymaga przepisania na podstawie realnego repo

## 4. Najwazniejsze typy driftu do naprawy

### 4.1. Drift dokumentacja <-> runtime

To sa miejsca, gdzie system dziala inaczej niz sugeruja opisy:

- port i proces truth
- realny spine `workspace`
- rozdzielone approval planes
- federacyjna topologia backendu

### 4.2. Drift dokumentacja <-> kod

To sa miejsca, gdzie implementacja istnieje, ale nie jest uczciwie opisana:

- funding
- projects
- workers
- observability
- lab extensions

### 4.3. Drift prompt <-> implementacja

To sa miejsca, gdzie kanon/prompt wyprzedza rzeczywistosc:

- operator mobile
- pelna unifikacja Human Gate
- pelna unifikacja memory
- pelna rada modeli z wagami i rangami jako twardy runtime

## 5. Wnioski do dalszego audytu

Z tej mapy wynikaja trzy twarde reguly na dalszy audyt i pozniejszy masterplan:

1. Nie wolno planowac napraw tak, jakby system byl pusty.
   Trzeba zakladac, ze duza czesc warstw juz istnieje, tylko jest rozdzielona i nierowno dojrzala.

2. Nie wolno planowac z samej dokumentacji.
   `workspace`, `project_mode`, `funding`, `projects`, `workers`, `observability` musza byc traktowane wedlug runtime, nie wedlug starszych opisow.

3. Mobile i pelna unifikacja governance nie sa "brakujacymi detalami".
   To sa duze luki kanoniczne, ktore trzeba traktowac jako osobne strumienie naprawcze.
