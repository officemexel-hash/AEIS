# CODEX AEIS PRODUCTION READINESS MAP

## Re-Audyt 2026-04-25

Aktualny, wiążący werdykt po pełnym re-audycie jest opisany w:

- [CODEX_AEIS_FULL_REAUDIT_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_FULL_REAUDIT_2026_04_25.md)

Najważniejsza korekta:

`production ready` nie może zostać zaakceptowane.

Nowy stan globalny:

`ADVANCED STAGING CANDIDATE / REQUIRES FIXES / NOT ACCEPTED AS PRODUCTION READY`

Największe blokery z re-audytu:

- `workspace Human Gate` crashuje przez brakujące metody,
- `workspace ideas` crashują przez drift route API vs `IdeaVault`,
- `skills runtime` i `skills registry` nadal są rozdzielone,
- `funding approvals` nadal żyją w lokalnym plane, a nie w unified governance ticket plane,
- `workers` i `observability` fronty mają realne `500`,
- startup backendu nadal zgłasza dependency/register errors.

**Status:** wersja robocza 0.1  
**Cel pliku:** uczciwie ocenic, ktore obszary AEIS sa blisko staging / produkcji, a ktore nadal sa rozszczepione albo tylko planowane

## 1. Skala oceny

- `NOT_READY` - brak, split albo krytyczny bug
- `DEV_READY` - da sie uruchomic i badac wewnetrznie, ale nie jest to bezpieczna warstwa produkcyjna
- `STAGING_CANDIDATE` - warstwa ma zywy runtime i sensowna funkcje, ale wymaga domkniecia integracji i testow
- `PROMPT_ONLY` - zalozenie kanoniczne bez implementacji

## 2. Mapa gotowosci

| Obszar | Readiness | Uzasadnienie |
|---|---|---|
| Backend bootstrap | STAGING_CANDIDATE | `health=200`, `modules=119`, `endpoints=1433` |
| Main API aggregation | STAGING_CANDIDATE | router montuje 87 rodzin, backend zyje |
| Workspace kickoff -> canon -> masterplan -> launch | STAGING_CANDIDATE | probe runtime przeszedl end-to-end do bundle deploy |
| Projects registry and lifecycle | STAGING_CANDIDATE | `GET /api/v1/projects` zwraca 10 projektow, a `/projects` jest data-backed |
| Worker fleet surface | DEV_READY | CRUD i heartbeat sa zywe, ale flota startuje pusta, a topologie nie sa jeszcze wypelnione |
| Observability hub | DEV_READY | logs/metrics/traces dzialaja, ale backend to `LocalLogBackend` bez trwalej produkcyjnej telemetrii |
| AI provider plane | DEV_READY | lista providerow i realny test `openai` dzialaja |
| Model registry | DEV_READY | CRUD, capabilities i performance snapshots dzialaja, ale plane jest osobny od workspace council config |
| Council session runtime | NOT_READY | sesje zyja, ale brak dowodu na realne glosowanie i egzekucje deliberacji |
| Autonomy controller | DEV_READY | 5 etapow istnieje, lecz runtime pozostaje na `observe` i nie steruje jeszcze glownym spine |
| Global Human Gate | DEV_READY | istnieje, ale nie jest glownym plane projektowym |
| Workspace Human Gate | STAGING_CANDIDATE | realne sesje, tree, history, choices |
| Unified Human Gate AEIS | NOT_READY | split miedzy workspace, global gates i funding |
| Council / model settings plane | DEV_READY | runtime settings zyja, ale semantics drift nadal istnieje |
| Skills subsystem | DEV_READY | registry + UI zyja, ale runtime executor nie jest bootstrappowany i `loaded_skills = 0` |
| Memory subsystem | NOT_READY | API zyje i manualne index/search dziala, ale startup binding jest niepelny, plane pofragmentowany i `evidence/stats` jest broken |
| Project runtime / worker orchestration | DEV_READY | engine istnieje, ale ma bug worker topology reconciliation |
| Funding domain | STAGING_CANDIDATE | rozbudowany backend, UI i lokalny gate submit |
| Funding as unified AEIS governance citizen | NOT_READY | lokalny approval plane nie jest jeszcze globalnym Human Gate |
| Operator Console Next.js | STAGING_CANDIDATE | workspace, funding, governance, projects, workers i observability maja zywe surface'y |
| Legacy dashboard | LEGACY | rownolegly stack, nie powinien zostac produkcyjnym truth plane |
| Mobile operator | PROMPT_ONLY | brak codebase aplikacyjnej |
| Lab modules (`cellular`, `sdr`, `devices`, `vps`, `container`) | DEV_READY | sa realne i zamierzone, ale poza core production spine |

## 3. Blokery production ready

### 3.1. Jeden Human Gate plane nie istnieje

Produkcja AEIS w sensie kanonicznym wymaga jednej warstwy prawdy dla:

- approvals
- audit trail
- escalation
- operator queue

Dzis mamy co najmniej trzy sciezki:

- workspace session gate
- global gates human requests
- funding local approval events

### 3.2. Worker topology potrafi rozjechac sie z planem

To jest blocker produkcyjny, bo zatwierdzony plan i realna topologia runtime moga byc inne.

### 3.3. Memory nie jest wspolnym plane

System uczacy sie i produkcyjnie sterowalny nie moze miec:

- globalnego retrieval plane pustego
- per-project runtime plane bez synchronizacji
- lazy singletonow memory bez wspolnego startup binding
- broken trasy diagnostycznej `/memory/evidence/stats`

### 3.5. Skills runtime nie jest gotowy do produkcyjnego reuse

System opisywany jako skill-driven nie moze miec sytuacji, w ktorej:

- registry przechowuje skille
- UI pokazuje skille
- ale runtime executor startuje z `loaded_skills = 0`
- probe execute nie zna nawet seedowego skillu z registry

### 3.6. Global memory bootstrap nie istnieje jako startup plane

`app.py` bootstrappuje:

- worker registry
- skills registry
- human gate

ale nie bootstrappuje:

- memory indexer
- evidence store
- retrieval

To oznacza, ze produkcyjny shared-memory plane nie ma jeszcze jednego lifecycle entrypoint.

### 3.4. Operator truth plane nie jest jednoznaczny

Mamy:

- nowy Next.js surface
- legacy dashboard
- niespojny runtime bind / pid truth

To jest zbyt slabe na production ready.

## 4. Obszary z najlepszym potencjalem do szybkiego domkniecia

### 4.1. Workspace spine

To jest obecnie najlepszy kandydat na glowny spine AEIS, bo ma juz:

- kickoff
- canon
- masterplan
- Human Gate
- council
- settings
- launch

### 4.2. Funding

Funding jest dojrzaly technicznie i moze byc jednym z pierwszych pionow do dopiecia pod wspolne governance.

### 4.3. Governance data surfaces

`governance/gates`, `governance/policies`, `decision-snapshots`, `spine`, `audit` wygladaja jak mocny material do konsolidacji, nie do przepisywania od zera.

## 5. Wniosek

AEIS nie jest dzis production ready.

AEIS jest natomiast:

- duzo bardziej zywy, niz wynikaloby z najostrzejszych ocen dokumentacyjnych
- wystarczajaco dojrzaly, by budowac bardzo szczegolowy masterplan naprawczy
- wystarczajaco pofragmentowany, by bez audytu i bez podzialu prac na dobrze rozdzielone strumienie latwo bylo popsuc integracje

Najuczciwszy status zbiorczy na teraz:

`SYSTEM FEDERATED / DEV-STAGING CAPABLE / NOT PRODUCTION READY`
