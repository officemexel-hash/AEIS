# AEIS - podrecznik operatora

> Stan: 2026-04-28  
> Zakres: od pierwszego uruchomienia lokalnego do testowania gotowej aplikacji.  
> Sciezka domyslna: root API na `http://127.0.0.1:8000` + frontend Next.js na `http://localhost:3000`.

Ten dokument opisuje AEIS od strony uzytkownika-operatora. Nie jest to dokument
wewnetrznej implementacji modulu. Celem jest pokazanie, co operator robi w
praktyce, co w tym samym czasie robi system, jakie decyzje podejmuje Rada modeli,
kiedy zatrzymuje sie HumanGate, jak dzialaja guardy i jak sprawdzic gotowa
aplikacje przed uznaniem jej za zakonczona.

Dokument opiera sie na:

- `docs/v2/AEIS_LAYERS_AND_MODULES.md`
- `docs/v2/AEIS_HOW_IT_WORKS.md`
- `docs/v2/MODULES_INDEX.md`
- `docs/v2/operations/audit_chains_catalogue.md`
- `docs/CLAUDE_AEIS_W14_TESTING.md`
- `docs/w14_workplan/W14_OVERVIEW.md`
- `HOW_TO_RUN.md`
- `scripts/start-server.ps1`
- `start_frontend.ps1`

W starszych dokumentach wystepuje tez standalone dashboard na portach `8421` lub
`8422`. Dla aktualnej sciezki operatorskiej uzywaj portu `8000` dla API i portu
`3000` dla frontendu.

---

## 1. Czym jest AEIS z perspektywy operatora

AEIS, czyli Autonomous Engineering Intelligence System, to system ktory bierze
pomysl operatora i prowadzi go przez pelny cykl:

```text
pomysl
-> interpretacja wedlug kanonu
-> plan
-> dyskusja modeli
-> decyzja D0-D5
-> HumanGate, jezeli potrzebny
-> wykonanie przez workerow
-> testy i symulacje
-> weryfikacja czlowieka
-> final approval
-> deploy albo publikacja
-> snapshot, replay, drift audit, compact
```

Najwazniejsza roznica wzgledem zwyklego CI/CD jest taka, ze AEIS nie tylko
buduje. AEIS najpierw rozumie, dyskutuje, klasyfikuje ryzyko, zbiera dowody,
wymaga zgody czlowieka w miejscach krytycznych i zapisuje wszystko w audycie.

Operator nie powinien traktowac AEIS jak generatora kodu. Poprawny model
mentalny to: AEIS jest sterowanym przez czlowieka systemem inzynierskim, w ktorym
modele pelnia role dzialow, reviewerow, sentineli i wykonawcow.

---

## 2. Warstwy AEIS w prostym jezyku

| Warstwa | Nazwa | Co to znaczy dla operatora |
|---|---|---|
| L1 | Canon | System ma zrodlo prawdy: Ksiega, Masterplan, manifesty modulow. Zmiana musi byc zgodna z kanonem. |
| L2 | Model Council | Modele dyskutuja, glosuja, podpisuja decyzje i szukaja ryzyk zanim ruszy wykonanie. |
| L3 | Memory | Decyzje, glosy, klikniecia, testy i wyniki sa zapisywane do hash-chain audit logs. |
| L4 | Skills | Workery nie pracuja dowolnie. Dobieraja umiejetnosci opisane manifestami. |
| L5 | Planning | System zamienia pomysl na execution plan, worker plan i lane'y pracy. |
| L6 | Human Gate / Governance | Decyzje wysokiego ryzyka wymagaja ticketu, evidence packa i zgody czlowieka. |
| L7 | Coordination | System rozdziela prace, wykrywa konflikty i pilnuje zaleznosci. |
| L8 | Worker | Workery wykonuja kod, konfiguracje, testy, migracje i inne akcje. |
| L9 | Integration | Deployment, VPS, kontenery, urzadzenia, cellular, SDR i inne integracje. |
| L10 | Console | Web UI operatora: idea-vault, projekty, rada, test-center, governance, audit. |
| L11 | Mobile | Kolejka decyzji i approvale na urzadzeniu operatora. |
| L12 | Output | Raporty, evidence packi, eksporty GDPR, ksiazki, snapshoty i artefakty. |

Te warstwy nie sa tylko architektura na papierze. Operator widzi je jako kolejne
ekrany, tickety, statusy, logi, testy i decyzje.

---

## 3. Pierwszy start lokalny

### 3.1. Wymagania

Minimalnie potrzebujesz:

- Windows PowerShell.
- Python 3.11+ w `PATH`.
- Node.js i npm dla frontendu.
- Wolny port `8000` dla API.
- Wolny port `3000` dla frontendu.
- Opcjonalnie Ollama lub skonfigurowane klucze modeli, jezeli chcesz realne odpowiedzi LLM zamiast fallbackow/testowych adapterow.

### 3.2. Instalacja backendu

W katalogu repo:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
.\scripts\install.ps1
```

Instalator:

- sprawdza Python 3.11+,
- tworzy `.venv`,
- instaluje zaleznosci z `src/sylion-pipeline/requirements.txt`,
- generuje `.env.generated`,
- ustawia podstawowy sekret JWT i internal API key.

Jezeli PowerShell blokuje skrypt polityka uruchamiania:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

### 3.3. Start backendu

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
.\start_backend.ps1
```

Ten helper uruchamia `scripts/start-server.ps1`, ktory:

- laduje `.env.generated`,
- ustawia `PYTHONPATH=src\sylion-pipeline`,
- wlacza tryb dev,
- wylacza lokalnie RBAC/rate-limit/auth-bypass dla wygody developerskiej,
- startuje `uvicorn sylion.api.app:app` na `127.0.0.1:8000`.

Adres backendu:

```text
http://127.0.0.1:8000
```

Podstawowa kontrola:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/openapi.json
```

Uwaga: `scripts/verify.ps1` w starszej wersji domyslnie sprawdza port `8422`.
Dla aktualnego API ustaw baze recznie:

```powershell
$env:SYLION_BASE="http://127.0.0.1:8000"
.\scripts\verify.ps1
```

### 3.4. Start frontendu

W drugim oknie PowerShell:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
.\start_frontend.ps1
```

Adres frontendu:

```text
http://localhost:3000
```

Frontend korzysta z:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Jezeli port `3000` jest zajety, Next.js moze zaproponowac inny port. Wtedy
wejdz na adres podany w terminalu.

---

## 4. Pierwsza orientacja w UI

Po starcie wejdz na:

```text
http://localhost:3000
```

Najwazniejsze ekrany operatora:

| Ekran | Adres | Do czego sluzy |
|---|---|---|
| Idea Vault | `/idea-vault` | Tworzenie i prowadzenie pomyslow. |
| Projekty | `/projects` | Projekty po promocji z idei. |
| Model Council | `/model-council` lub `/orchestration/council-rules` | Konfiguracja i obserwacja pracy Rady. |
| Human Gate | `/human-gate` | Kolejka decyzji wymagajacych czlowieka. |
| Operator Mobile | `/operator-mobile` | Mobilna kolejka decyzji i follow-me. |
| Test Center | `/test-center` | W14: testy, release gate, symulacje, guardians, truth alignment. |
| Agent Theater | `/test-center/theater` | Widok zespolow, Rady, guardianow i auto-repair. |
| V2 Admin | `/v2/admin` | Dashboard W19: policy, canary, audit, violations, circuits, renders. |
| Audit | `/audit` lub `/evidence` | Dowody, logi i historia decyzji. |
| Terminal Replay | `/terminal/replay` | Replay/fork sesji i porownanie divergence. |

Pierwszy smoke test UI:

- wejdz na `/health` lub `/v2/admin`,
- sprawdz, czy backend nie jest oznaczony jako offline,
- wejdz na `/idea-vault`,
- sprawdz, czy lista idei laduje sie bez bledu.

---

## 5. Klasy decyzji D0-D5

AEIS nie traktuje wszystkich akcji tak samo. Kazda istotna decyzja powinna
zostac sklasyfikowana.

| Klasa | Znaczenie | Typowy przyklad | Wymagania |
|---|---|---|---|
| D0 | Informacyjne | odczyt, lista, zwykly log | auto |
| D1 | Rutynowe | wewnetrzna zmiana bez skutku zewnetrznego | zwykle auto |
| D2 | Standardowe | zmiana katalogu, konfiguracji, workflow | moze wymagac gate |
| D3 | Znaczace | nowy projekt, refactor, zmiana kontraktu | Council + evidence |
| D4 | Krytyczne | produkcja, PII, duzy koszt, security boundary | Council + HumanGate |
| D5 | Systemowe/awaryjne | kill-switch, rollback prod, duzy rebuild | Council + HumanGate + external review |

Dla operatora najwazniejsze jest to:

- D0-D2 moga przechodzic szybko.
- D3 wymaga realnych dowodow i czesto blokuje wykonanie do decyzji.
- D4 bez czlowieka nie powinno isc dalej.
- D5 jest traktowane jak decyzja najwyzszego ryzyka.

---

## 6. Model Council: jak modele dyskutuja

### 6.1. Role Rady

Kanoniczny Council Hybrid sklada sie z rol:

| Rola | Co sprawdza |
|---|---|
| `planner` | Czy plan jest wykonalny i atomowy. |
| `critic` | Czy sa dziury, niespojnosci, brak warunkow brzegowych. |
| `security` | Auth, sekrety, PII, powierzchnia ataku, izolacja. |
| `legal` | GDPR, licencje, umowy, dane osobowe, ryzyka formalne. |
| `finance` | Koszt modeli, infrastruktury, workerow, rollout. |
| `governance` | Zgodnosc z D-ladder, HumanGate, evidence pack, kanon. |
| `qa` | Testy, regresja, release gate, coverage. |
| `red_team` | Ataki, naduzycia, bypassy, abuse cases. |
| `council_chair` | Porzadkuje wynik, liczy konsensus i finalny werdykt. |

### 6.2. Protokol sesji

Typowy przebieg:

```text
POST /api/v1/workspace/council/sessions
-> POST /sessions/{sid}/analyze
-> POST /sessions/{sid}/discuss
-> POST /sessions/{sid}/critic/sign
-> POST /sessions/{sid}/sentinels/evaluate
-> GET  /sessions/{sid}/consensus
-> POST /sessions/{sid}/consolidate-gated
```

W kodzie czesc tych endpointow jest wystawiona przez workspace council API:

```text
/api/v1/workspace/council/sessions
/api/v1/workspace/council/sessions/{session_id}/analyze
/api/v1/workspace/council/sessions/{session_id}/discuss
/api/v1/workspace/council/sessions/{session_id}/critic/sign
/api/v1/workspace/council/sessions/{session_id}/sentinels/evaluate
/api/v1/workspace/council/sessions/{session_id}/consensus
/api/v1/workspace/council/sessions/{session_id}/consolidate-gated
```

### 6.3. Format odpowiedzi modelu

Kazda rola powinna oddac strukturalna odpowiedz, a nie swobodny esej:

```json
{
  "role": "security",
  "verdict": "conditional",
  "reasoning": [
    "Pomysl dotyka PII i autoryzacji.",
    "Brakuje session timeout i rate limitu.",
    "Wymagany DPIA przed final approval."
  ],
  "dissents": [
    "Nie promowac do execution bez definicji SSO."
  ],
  "sentinel_blocks": [
    {
      "type": "security_high",
      "reason": "PII + auth + production deployment"
    }
  ]
}
```

### 6.4. Wazone glosowanie

Werdykt Rady nie jest zwyklym `5 za, 4 przeciw`. Glosy maja wagi. Rola
compliance albo chief architect moze miec wyzsza wage w decyzjach D3+.

Przyklad:

```text
approve:     1.25
conditional: 3.25
reject:      0.00
verdict: conditional
```

Jezeli `reject` przekracza ustalony prog, system powinien automatycznie
eskalowac do `conditional` lub blokady. Jezeli critic nie podpisze decyzji D3+,
pipeline nie powinien przejsc dalej.

---

## 7. HumanGate: jak dziala zatrzymanie dla czlowieka

HumanGate to formalny ticket decyzyjny. Nie jest to tylko przycisk OK.

### 7.1. Kiedy HumanGate sie pojawia

HumanGate pojawia sie, gdy:

- decyzja jest D4 albo D5,
- D3 zostanie eskalowane przez Rade albo sentinela,
- akcja dotyka produkcji,
- akcja dotyka PII/GDPR,
- koszt przekracza prog,
- planuje sie external action: submit, publish, deploy, upload,
- guard zablokuje akcje,
- operator recznie zatrzyma pipeline.

### 7.2. Typy HumanGate

W dokumentach wystepuja dwa spojne zestawy nazw. Dla operatora wazna jest
funkcja gate'a, nie sama nazwa enum.

| Typ funkcjonalny | Znaczenie |
|---|---|
| `idea_intake` / `non_blocking` | Pomysl zarejestrowany, mozna isc dalej. |
| `council_d3` | Decyzja znaczaca, wymaga Rady i evidence. |
| `council_d4` | Decyzja krytyczna, wymaga czlowieka. |
| `council_d5` | Decyzja systemowa, wymaga czlowieka i external review. |
| `dpia_required` / `legal` | Dane osobowe, GDPR, DPO. |
| `cost_threshold` / `financial` | Przekroczony prog kosztowy. |
| `security_high` / `security` | Auth, sekrety, trust boundary, PII high. |
| `production_deploy` / `production` | Dotyka produkcji. |
| `external_action` / `final` | Publikacja, submit, deploy, dzialanie poza systemem. |
| `mid_flight_pause` / `emergency` | Operator albo incident zatrzymuje bieg. |

### 7.3. Cykl zycia ticketu

```text
created
-> pending
-> reviewed
-> approved | rejected | needs_info
```

Interpretacja:

- `approved`: pipeline moze isc dalej.
- `rejected`: pipeline zatrzymany, potrzeba nowego planu albo zamkniecia.
- `needs_info`: operator wymaga uzupelnienia. Kilka takich odpowiedzi moze
  eskalowac decyzje do wyzszej klasy.

### 7.4. Co operator powinien sprawdzic w HumanGate

Przed zatwierdzeniem:

- Czy decision class jest sensowna.
- Czy Rada miala komplet rol dla danego ryzyka.
- Czy critic podpisal decyzje.
- Czy sentinele nie zostawily blokad.
- Czy evidence pack zawiera testy, rollback, diff i artefakty.
- Czy PII/GDPR ma DPIA albo uzasadnienie braku DPIA.
- Czy koszt i canary plan sa akceptowalne.
- Czy rollback jest praktycznie wykonalny.

---

## 8. Guardy i W19 policy

Guardy sa policy-as-code. Dzialaja jako automatyczne bezpieczniki przed
wykonaniem kroku.

Przyklady:

```yaml
no_prod_deploy_friday:
  when: "deploy.environment == 'prod' and date.weekday() == 4"
  block: true

pii_high_requires_dpia:
  when: "tags includes 'pii_high' and dpia.signed != true"
  block: true

cost_cap_per_idea:
  when: "session.total_cost_usd > 50"
  block: true
```

Co robi guard:

- czyta kontekst decyzji,
- renderuje warunek w sandboxie,
- zwraca `allow`, `deny`, `skipped` albo `error`,
- zapisuje wynik do audit chain,
- moze wymusic HumanGate albo eskalacje D-level.

W19 uzywa sandboxed Jinja2 i testow chaos, zeby guardy nie byly droga do RCE.
Operator powinien traktowac blad guardu jako sygnal ostroznosci. Jezeli guard
zwraca `error`, pipeline nie powinien udawac, ze wszystko jest bezpieczne.

---

## 9. Szczegolowa symulacja: portal HR z SSO, dokumentami i produkcja

Ten scenariusz pokazuje pelen cykl AEIS.

### 9.1. Pomysl operatora

Operator chce stworzyc:

```text
Portal pracowniczy dla firmy:
- logowanie przez Google OAuth + LDAP SSO,
- role: employee, manager, HR admin, DPO,
- dokumenty pracownicze i workflow akceptacji,
- dane osobowe pracownikow,
- eksport i usuwanie danych GDPR,
- wdrozenie produkcyjne z canary rollout.
```

Ten pomysl jest skomplikowany, bo dotyka:

- auth,
- PII,
- GDPR,
- workflow dokumentow,
- RBAC,
- produkcji,
- testow UI,
- kosztow infrastruktury,
- potencjalnego external action.

### 9.2. Faza 1 - Intake

Co robi operator:

- Wchodzi na `/idea-vault`.
- Tworzy nowy pomysl.
- Wpisuje tytul, opis, domene `operations` albo `engineering`.
- Dodaje tagi: `portal`, `auth`, `workflow`, `pii_high`, `gdpr`, `prod`.

Co robi AEIS:

- Wysyla `POST /api/v1/ideas`.
- Tworzy rekord idei.
- Nadaje status `draft` albo `created`.
- Dopisuje wpis do `idea_lifecycle.jsonl`.

Przykladowy wpis:

```json
{
  "prev_hash": "abc123",
  "content": {
    "kind": "idea_lifecycle.transition",
    "idea_id": "idea_hr_portal_001",
    "from_state": null,
    "to_state": "draft",
    "actor": "operator",
    "success": true
  },
  "content_hash": "def456"
}
```

### 9.3. Faza 2 - Source of Truth

Co robi AEIS:

- Czyta kanon i manifesty.
- Rozpoznaje moduly dotkniete przez pomysl.
- Buduje `canonical_book_input`.

Przyklad:

```yaml
idea_id: idea_hr_portal_001
affected_modules:
  - auth_users
  - role_assignment
  - document_workflow
  - gdpr_dsr
  - deployment
  - audit_chain
potential_object_types:
  - employee
  - document
  - approval_request
  - user_session
policy_implications:
  rbac_roles_required: true
  gdpr_dsr_pii_scope: high
  audit_trail_required: true
  production_gate_required: true
```

Co widzi operator:

- Idea ma wiecej kontekstu.
- System moze oznaczyc ja jako wymagajaca Rady albo approvalu.

### 9.4. Faza 3 - Masterplan draft

Planner proponuje plan:

```yaml
masterplan:
  - register_employee_object_type
  - configure_auth_google_oauth
  - configure_ldap_sso
  - define_rbac_roles
  - create_document_workflow_template
  - enable_gdpr_dsr
  - add_session_timeout_and_rate_limit
  - run_security_tests
  - deploy_to_blue_environment
  - human_smoke_test
  - canary_rollout
  - monitor_30d
```

AEIS od razu powinien wykryc, ze to nie jest D1. To minimum D3, a przez
PII + produkcje prawdopodobnie D4.

### 9.5. Faza 4 - Idea Debate

Rada zaczyna dyskusje.

`planner` mowi:

```json
{
  "verdict": "conditional",
  "reasoning": ["Plan wykonalny, ale wymaga doprecyzowania SSO i security."],
  "dissents": [],
  "sentinel_blocks": []
}
```

`critic` mowi:

```json
{
  "verdict": "conditional",
  "reasoning": [
    "Brakuje session timeout.",
    "Brakuje password/session policy.",
    "Nie opisano rate limitu.",
    "Nie ma rollback planu dla migracji uzytkownikow."
  ],
  "dissents": ["Nie podpisuje decyzji bez uzupelnienia auth policy."],
  "sentinel_blocks": []
}
```

`security` mowi:

```json
{
  "verdict": "conditional",
  "reasoning": [
    "Ryzyko brute force.",
    "Ryzyko session hijacking.",
    "Wymagany audit log logowania i zmian rol."
  ],
  "sentinel_blocks": [
    {"type": "security_high", "reason": "auth + PII + production"}
  ]
}
```

`legal` albo `compliance` mowi:

```json
{
  "verdict": "conditional",
  "reasoning": [
    "DPIA wymagana.",
    "Trzeba opisac podstawe prawna GDPR Art. 6.",
    "Trzeba zapewnic prawa Art. 15, 16, 17, 20."
  ],
  "sentinel_blocks": [
    {"type": "dpia_required", "reason": "employee PII scope high"}
  ]
}
```

`red_team` mowi:

```json
{
  "verdict": "conditional",
  "reasoning": [
    "Ataki: brute-force, session fixation, privilege escalation, SQL injection.",
    "Nalezy przetestowac role manager/employee/HR admin."
  ],
  "dissents": ["Brak testow naduzyc roli HR admin."]
}
```

Wynik pierwszej rundy:

```text
approve:     1.25
conditional: 4.25
reject:      0.00
verdict: conditional
critic_signature: missing
pipeline: blocked
```

Co robi operator:

- Czyta braki.
- Uzupelnia pomysl:
  `OAuth Google + LDAP SSO, session timeout 30 minut, rate limit 5 prob / 15 min, MFA dla HR admin, DPIA wymagane, rollback przez blue/green.`

### 9.6. Faza 5 - Druga deliberacja i HumanGate

Rada uruchamia druga runde. Tym razem:

- critic podpisuje,
- security sentinel nie blokuje, ale eskaluje do D4,
- legal wymaga DPO approval,
- governance wymaga evidence packa i rollback planu.

Wynik:

```text
verdict: approve
decision_class: D4
critic_signature: present
human_gate_required: true
required_reviewers:
  - operator
  - DPO
```

AEIS tworzy HumanGate:

```json
{
  "gate_type": "dpia_required",
  "decision_class": "D4",
  "status": "pending",
  "required_reviewers": ["dpo", "operator"],
  "reason": "PII high + auth + production deployment"
}
```

Co robi operator:

- Wchodzi na `/human-gate` albo `/operator-mobile/queue`.
- Otwiera ticket.
- Sprawdza decyzje Rady, podpis critic, sentinele, DPIA.
- Zatwierdza albo zwraca `needs_info`.

### 9.7. Faza 6 - Team Scaling

Po approval AEIS tworzy execution plan:

```yaml
lanes:
  backend:
    workers:
      - auth_worker
      - gdpr_worker
  frontend:
    workers:
      - ui_worker
  qa_security:
    workers:
      - test_worker
      - red_team_worker
tasks:
  - implement_oauth
  - implement_ldap_sso
  - implement_rbac
  - implement_document_workflow
  - implement_gdpr_dsr
  - build_ui
  - run_contract_tests
  - run_human_like_tests
  - prepare_canary
```

Co robi AEIS:

- sprawdza zaleznosci,
- przypisuje lane'y,
- wykrywa konflikty,
- wybiera workerow i umiejetnosci.

### 9.8. Faza 7 - Skill Binding

System dobiera skille:

```yaml
skill_bindings:
  auth_worker:
    - auth_provider
    - session_broker
    - policy_engine
  gdpr_worker:
    - gdpr_dsr
    - hard_purge
    - audit_chain
  test_worker:
    - contract_test_runner
    - human_lab
    - release_gate
```

Co to znaczy praktycznie:

- worker nie ma sam wymyslac, jak obsluzyc GDPR,
- ma uzyc istniejacego kontraktu i evidence,
- kazde wykonanie jest przypisane do manifestu lub modulu.

### 9.9. Faza 8 - Execution

Workery wykonuja zadania. Kazdy krok emituje dowod:

```json
{
  "kind": "worker.task.completed",
  "task": "implement_session_timeout",
  "worker_id": "auth_worker",
  "artifact": "commit_or_patch_ref",
  "tests": ["test_session_timeout", "test_rate_limit"],
  "success": true
}
```

Mozliwe stany:

- task konczy sie sukcesem,
- task blokuje sie na braku danych,
- task wykrywa konflikt,
- task wymaga nowej decyzji D2+,
- task odpala auto-repair,
- task eskaluje do HumanGate.

### 9.10. Faza 9 - Mid-flight Steering

Przyklad konfliktu:

```text
backend worker tworzy employee.email
auth worker tworzy users.email
workflow worker oczekuje actor.email
```

ConflictResolver moze zaproponowac:

```yaml
recommendation: "Uzyc users.email jako identity source, employee.email jako profile mirror."
confidence: 0.93
decision_class: D2
auto_approve: true
```

Jezeli confidence jest niskie albo blast radius wysoki:

```yaml
decision_class: D3
human_gate_required: true
```

### 9.11. Faza 10 - W14 Verification

W14 traktuje testy jako osobny organ, nie jako koncowy checkbox.

Operator wchodzi na:

```text
/test-center
```

Najwazniejsze widoki:

| Widok | Co sprawdza |
|---|---|
| `/test-center/dashboard` | Stan testow, findings, release blockers. |
| `/test-center/catalog` | Test cases, suites, wymagania. |
| `/test-center/human-lab` | Symulacje uzytkownikow i bledow ludzkich. |
| `/test-center/simulation` | Simulation branches i testruny. |
| `/test-center/auto-repair` | Findings, proby naprawy, loop guard. |
| `/test-center/truth-alignment` | Czy runtime/API/UI/testy zgadzaja sie z SoT i Masterplanem. |
| `/test-center/release-gate` | Czy projekt moze byc release candidate. |
| `/test-center/theater` | Podglad agentow, Rady, guardianow i napraw. |

W14 powinno wymagac:

- Test Charter,
- wymaganych testow,
- evidence dla PASS,
- human-like verification,
- release gate,
- rollback planu dla D3+,
- Council/HumanGate dla D4/D5.

### 9.12. Faza 11 - Manualne testowanie gotowej aplikacji

Operator testuje aplikacje na blue/staging env.

Checklist dla portalu HR:

| Obszar | Co sprawdzic |
|---|---|
| Login | Google OAuth, LDAP SSO, bledne haslo, brak konta, wygasla sesja. |
| Sesja | Timeout 30 minut, logout, odswiezenie tokenu, brak session fixation. |
| Role | Employee nie widzi panelu HR, manager widzi swoje workflow, DPO widzi GDPR. |
| Dokumenty | Upload, lista, status, zatwierdzenie, odrzucenie, historia. |
| Workflow | Manager approval, HR approval, cofniecie, komentarz, powiadomienie. |
| GDPR | Access, rectification, erasure, portability. |
| Audit | Kazda zmiana roli, dokumentu i decyzji widoczna w logu. |
| Security | Rate limit, proby brute force, brak SQL injection na polach. |
| UI | Bledy walidacji, puste stany, mobile width, loading/error states. |
| Failure | Backend offline, timeout API, blad uploadu, rollback blue/green. |

Kazdy istotny klik powinien trafic do verification/audit trail. Jezeli UI pokazuje
PASS, ale nie ma dowodu, operator nie powinien uznawac testu za zakonczony.

### 9.13. Faza 12 - Final Approval

AEIS sklada evidence pack:

```yaml
evidence_pack:
  decision:
    class: D4
    verdict: approve
  council:
    votes: present
    critic_signature: present
    sentinel_evaluations: present
  human_gate:
    operator_approval: present
    dpo_approval: present
  tests:
    contract_tests: passed
    human_like_tests: passed
    release_gate: passed
  artifacts:
    canonical_diff: present
    dpia: present
    rollback_plan: present
    deployment_plan: present
  verification:
    manual_click_trace: present
```

Dla D4 final approval moze wymagac:

- operatora,
- drugiego operatora,
- DPO,
- Council sign-off.

Dla D5 dochodzi external reviewer.

### 9.14. Faza 13 - External Action

Przy produkcji AEIS powinien uzyc canary:

```text
0% -> 1% -> 5% -> 25% -> 50% -> 100%
```

Kazdy etap ma guardy:

- error rate,
- latency,
- koszt,
- security alerts,
- audit chain health,
- rollback readiness.

Jezeli `error_rate > 1%`, guard moze zatrzymac rollout i uruchomic rollback.

### 9.15. Faza 14 - Memory Snapshot

Po zakonczeniu:

- evidence pack zostaje zapieczetowany,
- snapshot sesji trafia do memory,
- replay-fork moze odtworzyc decyzje z innymi parametrami,
- divergence score pokazuje, jak bardzo zmienilby sie wynik.

### 9.16. Faza 15 - Drift Audit i Compact

System porownuje wynik z kanonem:

- czy zbudowano to, co bylo w Source of Truth,
- czy Masterplan nie rozjechal sie z runtime,
- czy UI nie pokazuje mockow jako live,
- czy dokumentacja nie klamie wzgledem kodu,
- czy nowe decyzje D3+ powinny wejsc do compactu.

Memory compact robi z dlugiego sladu operacyjnego krotszy kontekst dla przyszlych
modeli i operatora. Dla decyzji D4+ compact powinien przejsc CFT, czyli Compact
Fidelity Test.

---

## 10. Co moze pojsc inaczej

AEIS nie zawsze idzie linia prosta.

| Sytuacja | Co robi AEIS | Co robi operator |
|---|---|---|
| Rada daje `conditional` | Pipeline blokuje wykonanie. | Uzupelnia braki i uruchamia druga runde. |
| Critic nie podpisuje | Decyzja D3+ nie przechodzi. | Czyta dissent i poprawia plan. |
| Security sentinel blokuje | Eskalacja do D4/D5 albo stop. | Sprawdza ryzyko i wymagane mitigacje. |
| Guard zwraca `deny` | Krok nie jest wykonywany. | Poprawia kontekst, policy albo plan. |
| HumanGate `needs_info` | Ticket wraca do uzupelnienia. | Dopisuje brakujace dane. |
| Worker wykrywa konflikt | ConflictResolver proponuje naprawe. | Akceptuje auto-D2 albo otwiera D3. |
| Testy W14 failuja | Finding trafia do auto-repair. | Sprawdza, czy naprawa ma evidence. |
| UI dziala, ale brak audit | Release gate powinien blokowac. | Nie zatwierdza final approval. |
| Canary pogarsza metryki | StagedRolloutGate zatrzymuje lub rollbackuje. | Potwierdza incident i decyzje rollback. |

---

## 11. Audit chains, ktore operator powinien znac

| Chain | Po co |
|---|---|
| `idea_lifecycle.jsonl` | Historia pomyslu i statusow. |
| `council_wedge.jsonl` | Decyzje Rady i werdykty. |
| `adr_signoff.jsonl` | Proby sign-off ADR/Council. |
| `w19_evaluator.jsonl` | Wyniki guardow/policy render. |
| `federation_policy.jsonl` | Decyzje routing gate i rollout. |
| `workflow_engine.jsonl` | Odpalenie reguly workflow. |
| `replay_fork.jsonl` | Replay i divergence score. |
| `gdpr_dsr.jsonl` | Dzialania GDPR DSR. |
| `rbac_v2.jsonl` | Sprawdzenia capability i role. |
| `cost_ledger.jsonl` | Koszty modeli/infrastruktury. |

Manualna weryfikacja chainow:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
python scripts/v2/verify_audit_chains.py
```

Oczekiwany wynik: wszystkie chainy clean. Jezeli jest violation, patrz
`docs/v2/operations/dpo_recovery_runbook.md`.

---

## 12. Testowanie gotowej aplikacji

### 12.1. Techniczne testy backendu

Dla aktualnej warstwy v2:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline
pytest tests/aeis_v2/ -q
```

Dla W14 Test Center:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline
pytest tests/aeis/testing/ -q
```

### 12.2. Testy frontendu

```powershell
cd C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend
npm run lint
npm run build
```

Jezeli pracujesz na UI, uruchom tez przegladarke i sprawdz ekrany:

```text
http://localhost:3000/idea-vault
http://localhost:3000/projects
http://localhost:3000/human-gate
http://localhost:3000/test-center
http://localhost:3000/test-center/release-gate
http://localhost:3000/test-center/theater
http://localhost:3000/v2/admin
```

### 12.3. Test release gate

W Test Center wejdz na:

```text
/test-center/release-gate
```

Release nie powinien przejsc, jezeli:

- brakuje Test Charter,
- sa otwarte P0/P1 findings,
- nie ma evidence dla PASS,
- truth alignment ma drift,
- HumanGate D4/D5 nie jest zatwierdzony,
- rollback plan nie istnieje,
- testy human-like nie zostaly wykonane.

### 12.4. Human-like verification

Operator powinien wykonac test tak, jak zrobi to realny uzytkownik:

- wejsc do aplikacji bez wiedzy developerskiej,
- przejsc glowne scenariusze,
- sprobowac blednych danych,
- sprawdzic puste stany,
- sprawdzic mobile width,
- sprawdzic role z mniejszymi uprawnieniami,
- sprawdzic czy system pokazuje prawdziwe dane, a nie mock.

W AEIS status `complete` bez evidence jest podejrzany. Status koncowy musi miec
slad w testach, audycie i approvalach.

---

## 13. Minimalny operator runbook

### Start dnia

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
.\start_backend.ps1
```

W drugim terminalu:

```powershell
cd C:\Users\razor\Desktop\pipeline_glm
.\start_frontend.ps1
```

Potem:

```text
http://localhost:3000/v2/admin
http://localhost:3000/idea-vault
```

### Nowy pomysl

1. Wejdz na `/idea-vault`.
2. Utworz idee z tytulem, opisem, domena i tagami.
3. Wyslij do `submitted` albo `council_review`.
4. Otworz dyskusje Rady.
5. Czytaj conditional/reject jako zadania do poprawy, nie jako blad systemu.

### Przed wykonaniem

1. Sprawdz D-level.
2. Sprawdz role Rady.
3. Sprawdz critic signature.
4. Sprawdz sentinele.
5. Sprawdz HumanGate.
6. Sprawdz czy plan ma rollback i testy.

### Podczas wykonania

1. Monitoruj projekty i workers.
2. Sprawdz konflikty.
3. Sprawdz findings.
4. Nie zatwierdzaj naprawy bez evidence.

### Przed final approval

1. Otworz `/test-center/release-gate`.
2. Otworz `/test-center/truth-alignment`.
3. Otworz `/human-gate`.
4. Sprawdz audit chain health.
5. Wykonaj manualny smoke test aplikacji.
6. Zatwierdz dopiero, gdy evidence pack jest kompletny.

---

## 14. Najczestsze problemy

| Problem | Przyczyna | Co zrobic |
|---|---|---|
| Frontend pokazuje backend offline | API nie dziala albo zly port. | Sprawdz `http://127.0.0.1:8000/health` i `NEXT_PUBLIC_API_URL`. |
| `verify.ps1` sprawdza port `8422` | Starszy default skryptu. | Ustaw `$env:SYLION_BASE="http://127.0.0.1:8000"`. |
| Council nie daje realnych odpowiedzi | Brak model provider albo fallback. | Sprawdz konfiguracje modeli/Ollama/API keys. |
| HumanGate nie pokazuje ticketu | Decyzja nie zostala sklasyfikowana jako wymagajaca HG. | Sprawdz D-level i policy/sentinel. |
| Test Center puste | Backend W14 nie ma seed danych albo endpoint nie dziala. | Sprawdz `/api/v1/testing/health`. |
| Release gate blokuje | To oczekiwane przy brakujacym evidence. | Otworz blockers i domknij findingi. |
| Audit chain violation | Hash-chain nie przechodzi weryfikacji. | Uzyj DPO recovery runbook. |

---

## 15. Definicja "gotowe" dla aplikacji stworzonej przez AEIS

Aplikacja jest gotowa dopiero wtedy, gdy wszystkie ponizsze warunki sa spelnione:

- Pomysl ma zamkniety lifecycle.
- Source of Truth i Masterplan sa zgodne z runtime.
- Council wydal werdykt.
- Critic podpisal decyzje D3+.
- Sentinele nie maja aktywnych blokad.
- HumanGate D4/D5 jest zatwierdzony przez wymagane osoby.
- Workery zakonczyly zadania i zapisaly evidence.
- Testy techniczne przeszly.
- Testy human-like przeszly.
- Operator recznie sprawdzil gotowy produkt.
- Release gate przepuszcza.
- Evidence pack jest sealed.
- Deploy/canary zakonczyl sie bez blokad.
- Snapshot i audit chain sa poprawne.
- Drift audit nie wykazuje krytycznej rozbieznosci.

Jezeli ktorykolwiek punkt nie jest spelniony, aplikacja moze byc "zbudowana",
ale nie jest jeszcze zakonczona w sensie AEIS.

