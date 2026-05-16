# SYLION AEIS — Jak to działa, krok po kroku

> **Stan na:** 2026-04-28
> **Companion:** ten dokument uzupełnia `AEIS_LAYERS_AND_MODULES.md`
> (referencja warstw) o **narrację działania** — od "operator wpisuje
> pomysł" do "produkt jest w produkcji + pamięć skompresowana".

---

## 1. Czym JEST AEIS

**AEIS = Autonomous Engineering Intelligence System.**

Najprościej: AEIS to **pipeline, który zamienia pomysł w produkt**, ale
nie jest to zwykły CI/CD. Różni się od standardowego pipeline'u w trzech
fundamentalnych aspektach:

### 1.1. AEIS rozmawia ze sobą zanim zacznie kodować

Zanim cokolwiek się zbuduje, **9-rolowa Rada modeli LLM** (Council
Hybrid) prowadzi **prawdziwą deliberację**: planner proponuje, krytyk
kwestionuje, security/legal/finance dorzucają obiekcje, sentinels
(Cost/Security) mogą zawetować. Krytyk **musi** podpisać każdą decyzję
≥D3, bez podpisu nic dalej nie idzie.

To nie jest "wywołaj LLM, dostaniesz odpowiedź" — to jest **strukturalna
debata** z głosowaniem ważonym, sygnaturami, dissents zapisanymi w
audit chain. Każdy może odtworzyć dlaczego rada zdecydowała tak a nie
inaczej (replay-as-fork z divergence scoring).

### 1.2. AEIS pamięta i się uczy

Każda decyzja, każdy głos rady, każda zmiana parametru, każde
zatwierdzenie/odrzucenie człowieka — wszystko trafia do
**hash-chained JSONL** (każdy wiersz ma `prev_hash` + `content` +
`content_hash`). Nawet drobna zmiana w środku = wykryta natychmiast
przez `verify_chain()`.

Te logi zasilają:
- **Replay-as-fork** — bierzesz snapshot z punktu N, podajesz inny
  override (np. "co by się stało gdybyśmy użyli claude-opus zamiast
  gpt-oss"), system odtwarza i daje **divergence_score** (0.0 = tak
  samo, 1.0 = całkowicie inaczej).
- **Drift audit** — jeśli rada zaczęła decydować inaczej niż mówi
  Księga (canonical_book), otwiera się ticket dryfu.
- **Memory compact** — co X dni stare logi są skompresowane w
  long-term layer + Księga regenerowana.

### 1.3. AEIS ma **HumanGate** w każdym krytycznym miejscu

Nie ma "AI sam zatwierdza produkcję". Klasy decyzji **D4 i D5
wymagają sygnatury człowieka** — bez niej rada nawet jeśli głosuje 4/4
nie może wypchnąć kodu na produkcję. Klasa D3 ma opcjonalne HG, D2
może być auto.

HG to nie tylko "kliknij OK" — to:
- **Ticket** w `/api/v1/gates/human/requests` z kontekstem (co rada
  zdecydowała, co krytyk podpisał, jakie są sentinel blocks)
- **Eskalacja** do wyższej klasy (D3 → D4) jeśli operator powie
  "needs_info" 3 razy lub odrzuci
- **Audit chain** — każda decyzja człowieka jest podpisana czasem,
  reviewer_id, decision (approved/rejected/needs_info), comment

---

## 2. Jak działa AEIS

### 2.1. Architektura wysokiego poziomu

```
                ┌──────────────────────────────┐
   OPERATOR ────│   L10 Operator Console       │
                │   (Web Next.js App Router)    │
                └────────────┬─────────────────┘
                             │ REST + SSE
                ┌────────────▼─────────────────┐
                │     L6 Human Gate / Gov      │
                │   (D0-D5 ladder, gates)      │
                └────────────┬─────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐          ┌────▼────┐         ┌─────▼────┐
   │ L1 Canon│  ←——→    │ L2      │  ←——→   │ L3       │
   │ Księga  │          │ Council │         │ Memory   │
   │Masterplan│         │  9 ról  │         │ chains   │
   └────┬────┘          └────┬────┘         └──────────┘
        │                    │                    │
        └──────────┬─────────┴───────┬───────────┘
                   │                 │
              ┌────▼─────┐      ┌────▼─────┐
              │ L4 Skills│      │ L5 Plan  │
              │ contracts│      │ engine   │
              └────┬─────┘      └────┬─────┘
                   │                 │
                   └────────┬────────┘
                            │
                       ┌────▼─────┐
                       │ L7 Coord │
                       │ + L8 Wkr │
                       └────┬─────┘
                            │
                       ┌────▼─────┐
                       │ L9 Integ.│
                       │ L11 Mob. │
                       │ L12 Out. │
                       └──────────┘
```

### 2.2. Trzy fundamentalne pętle

AEIS działa w **trzech zagnieżdżonych pętlach**:

**Pętla A — Decyzyjna (sekundy do minut):**
```
operator wpisuje → klasyfikator D0-D5 → rada głosuje →
critic podpisuje → human gate (jeśli ≥D3) → ticket zaakceptowany
```

**Pętla B — Wykonawcza (minuty do godzin):**
```
ticket → execution_plan → worker pool dispatch → workery wykonują
moduły → emitują evidence + audit events → reconciliation
```

**Pętla C — Pamięciowa (dni do tygodni):**
```
audit chains rosną → drift detector porównuje z Księgą → backlog
otwarty na rozbieżności → memory compact → Księga regeneruje się
```

Każda pętla ma własne metryki Prometheus, własny audit chain, własne
gate'y wejścia/wyjścia.

### 2.3. Główne komponenty komunikacji

| Komponent | Co robi | Przykład |
|---|---|---|
| `EventBus` | Domain events (publish/subscribe) | `idea.created` → `council.deliberate` |
| `AdapterBus` | Inter-module dispatch | `wedge` → `audit_chain` |
| `FederationRouter` | Routing modeli LLM | `claude-opus` (deep) vs `gpt-oss:20b` (cheap) |
| `WorkflowEngine` | Deklaratywne reguły YAML | `on_status_change → emit_event` |
| `DecisionGateEngine` | Egzekwuje gate D0-D5 | "D4 wymaga critic + HG" |

---

## 3. Anatomia warstw — krótkie podsumowanie

(Pełny opis: `AEIS_LAYERS_AND_MODULES.md`)

| Warstwa | Esencja | Główny moduł |
|---|---|---|
| **L1 Canon** | Źródło prawdy — Księga, Masterplan, manifesty | `contracts/manifests/` |
| **L2 Council** | Rada 9 ról + krytyk + sentinels | `governance/council_hybrid.py` |
| **L3 Memory** | Hash-chained JSONL, snapshots, replay | `aeis_v2/audit_chain/`, `aeis_v2/replay_v2/` |
| **L4 Skills** | Manifest-driven runtime | `core/contract_registry.py` |
| **L5 Planning** | Workflow engine, decision ladder | `aeis_v2/workflow_v2/`, `governance/decision_ladder.py` |
| **L6 HG/Gov** | D0-D5 + gates + policy | `governance/`, `aeis_v2/policy_v2/` |
| **L7 Coord** | Lane partitioning, conflict resolution | `governance/conflict_resolver.py` |
| **L8 Worker** | Wykonanie + evidence emission | `aeis_v2/deployment/agent.py` |
| **L9 Integration** | Cellular, devices, containers | `cellular/`, `containers/`, `devices/` |
| **L10 Console** | Web UI dla operatora | `src/sylion-frontend/src/app/(app)/` |
| **L11 Mobile** | Backlog | — |
| **L12 Output** | Books, evidence packs, GDPR exports | `governance/evidence_packs.py`, `aeis_v2/gdpr_v2/` |

---

## 4. SYMULACJA: "Portal pracowniczy z logowaniem"

Rozegrajmy pełny scenariusz. Operator chce stworzyć portal dla
pracowników firmy z logowaniem, autoryzacją, dokumentami i workflow
akceptacji wniosków. Idziemy fazami 1-15.

### **Faza 1 — Intake (Operator wpisuje pomysł)**

**Co robi operator:**
1. Wchodzi na `/idea-vault`
2. Klika "Nowy pomysł"
3. Modal otwiera się z polami:
   - Tytuł: "Portal pracowniczy z logowaniem"
   - Opis: "Portal dla pracowników firmy z autoryzacją użytkowników,
     rolami, dokumentami do zatwierdzania i workflow akceptacji wniosków."
   - Domena: HR
   - Tagi: `portal`, `auth`, `workflow`

**Co robi system:**
- POST `/api/v1/ideas` z body `{title, description, author, tags, attachments}`
- IdeaVault tworzy `idea_id = e7786bfe-...` ze statusem **`draft`**
- Wpis do `idea_lifecycle.jsonl`:
  ```json
  {
    "prev_hash": "...",
    "content": {
      "kind": "idea.created",
      "idea_id": "e7786bfe...",
      "title": "Portal pracowniczy...",
      "ts": 1777391330.42,
      "status": "draft"
    },
    "content_hash": "..."
  }
  ```
- Event Bus publikuje `idea.created` → handler w lifecycle_v2
  rozważa auto-przejście do `submitted` jeśli opis ma min. 50 znaków
  i tagi są w taksonomii

**Stan:** Idea w `draft`, w UI widać kartę z statusem badge'em.

---

### **Faza 2 — Source of Truth (Draft canonical_book)**

**Co robi system:**
- Book Interpreter (rola w Council) pobiera Księgę v3.5 + manifesty
  modułów, których pomysł dotyczy (auth, workflow, hr)
- Generuje **canonical_book_input** — strukturalny dokument:
  ```yaml
  idea_id: e7786bfe...
  affected_modules: [auth_users, document_workflow, role_assignment]
  potential_object_types: [employee, document, approval_request]
  potential_widgets: [login_form, document_list, approval_button]
  policy_implications:
    - rbac_roles_required: true
    - gdpr_dsr_pii_scope: high  # bo logowanie + dane pracowników
    - audit_trail_required: true
  ```
- Wpis do `apply_audit.jsonl` (informacyjny, nie blokujący)

**Stan:** System ma kontekst kanoniczny — wie że ten pomysł dotyczy
PII, więc każda kolejna faza wie że trzeba aktywować GDPR DSR module
i wymagać audytu.

---

### **Faza 3 — Masterplan draft (Planner proponuje)**

**Co robi system:**
- W tle: workspace council session jest tworzona via POST
  `/api/v1/workspace/council/sessions` z `topic = "masterplan-draft: portal"`
- **Planner role** (Claude Opus 4) dostaje prompt:
  ```
  System: Jesteś planner-em w Radzie SYLION AEIS. Operator chce zbudować
  portal pracowniczy. Twoja praca: zaproponować masterplan z 5-10 krokami.
  Każdy krok ma być atomowy, ma mieć kryterium sukcesu, i ma wskazać
  który moduł SYLION jest odpowiedzialny.

  Kontekst: {canonical_book_input}
  Idea: "Portal pracowniczy z logowaniem..."
  Tags: [portal, auth, workflow]
  ```
- Planner odpowiada np.:
  ```yaml
  masterplan:
    1: register_employee_object_type  (W15 ontology)
    2: configure_auth_users           (auth_users module)
    3: define_workflow_template       (W16 apps_v2)
    4: enable_gdpr_dsr_for_employees  (W7 gdpr_v2)
    5: deploy_to_blue_environment     (W17 deployment)
    6: human_smoke_test               (Operator)
    7: green_promote                  (Council D4)
    8: monitor_30d                    (Observability)
  ```

**Stan:** Masterplan w pamięci sesji rady, jeszcze nie zatwierdzony.

---

### **Faza 4 — Idea Debate (Rada głosuje, krytyk podpisuje)**

To jest **najważniejszy moment**. Tutaj się dzieje magia.

**Co robi system:**

1. **Klasyfikacja D0-D5:**
   - `decision_ladder.classify_decision()` analizuje:
     - blast_radius: high (logowanie = security-critical)
     - reversible: tak (można usunąć moduł)
     - affects_contracts: tak (nowy object_type employee)
     - affects_kernel: nie
   - **Wynik: D3 (Significant)** — wymaga Full Board Council 4/4

2. **Składanie Rady (4 z 7 departamentów):**
   - **Governance Lead** (Claude Opus 4, waga 1.00) — zawsze
   - **Compliance Officer** (Gemini 2.5 Pro, waga 1.25) — zawsze
   - **Architecture/Chief Architect** (Gemini 2.5 Pro, waga 1.25) — D3+ rebuild
   - **Red Team/Red Lead** (Grok-3, waga 1.00) — D3+ security

3. **Każda rola dostaje prompt-template dostosowany do swojej roli:**

   *Critic (zawsze obecny niezależnie od składu 4/4):*
   ```
   Ty jesteś krytyk. Twoja praca to znaleźć dziury w propozycji.
   Co MOŻE pójść źle? Jakie założenia są niepoprawne?

   Idea: Portal pracowniczy z logowaniem
   Masterplan: {planner_output}

   Wymagana odpowiedź: 3-5 obiekcji + 1 sentencja "approve/conditional/reject".
   ```

   *Security/Red Lead:*
   ```
   Ty jesteś red team lead. Wymyślasz scenariusze ataku.
   Co by zrobił atakujący żeby ten portal złamać?

   Idea: Portal pracowniczy z logowaniem...
   Affected modules: auth_users, document_workflow

   Wymagana odpowiedź: 3-5 wektorów ataku + ocena ryzyka (low/med/high) + verdict.
   ```

   *Compliance Officer:*
   ```
   Ty jesteś compliance officer. Sprawdzasz GDPR/RODO + ISO27001 + SOC2.
   Czy ta funkcjonalność wymaga DPIA? Czy są ślady audytu?

   Idea: Portal pracowniczy...
   PII scope: high (logowanie + dane pracowników)

   Wymagana odpowiedź: lista artykułów GDPR które stosują się + verdict.
   ```

4. **Wywołanie równoległe (ThreadPoolExecutor, 4 wątki):**
   - `OllamaRoleAdapter` lub `ClaudeOpusAdapter` strzela do każdego
     modelu jednocześnie z timeoutem 30s
   - Każda rola zwraca: `{verdict, reasoning, dissents, sentinel_blocks}`

5. **Przykładowe odpowiedzi:**

   *Critic:*
   ```
   Obiekcje:
   - "logowanie" jest niedoprecyzowane — OAuth/SAML/local password?
   - Brak specyfikacji session timeout
   - Brak password policy (długość, complexity, rotation)
   Verdict: conditional (potrzebne dodatkowe szczegóły)
   ```

   *Red Lead:*
   ```
   Wektory ataku:
   - Brute-force na logowanie (mitigation: rate limit?)
   - Session hijacking (mitigation: HttpOnly + Secure flag?)
   - SQL injection w document workflow (mitigation: parametryzowane query?)
   Risk: high → wymaga code review przed produkcją
   Verdict: conditional (wymagane: rate limit, secure session, prepared statements)
   ```

   *Compliance Officer:*
   ```
   GDPR Articles: 6 (lawful basis), 13 (info notice), 17 (erasure), 32 (security)
   DPIA: TAK (high-risk processing — pracownicze dane)
   Wymagane: audit trail każdego logowania, retention policy 90d hot/2y cold
   Verdict: conditional (wymagana DPIA + retention config)
   ```

   *Chief Architect:*
   ```
   Architektura ok ale:
   - employee object_type konfliktuje z istniejącym person?
   - workflow template powinien dziedziczyć z approval_workflow base
   Verdict: approve (z warunkiem konsolidacji z person)
   ```

6. **Ważone głosowanie:**
   ```
   approve     = chief_architect (1.25)              = 1.25
   conditional = critic (1.0) + red (1.0) + compl (1.25) = 3.25
   reject      = (nikt)                              = 0.00
   ──────────────────────────────────────────────────────
   Suma głosów ważona: 4.50, max = conditional (3.25)
   Verdict końcowy: conditional
   ```

7. **Sentinel blocks:**
   - Cost Sentinel: estimated_cost = $145 LLM tokens / decyzja → OK (< budget)
   - Security Sentinel: scan tagów → "auth", "logowanie" → flaga "high-PII"
     → wymaga ADR sign-off

8. **Critic signature gate:**
   - Critic verdict = `conditional` → **WYMAGA OPERATORA**
     żeby uzupełnić warunki PRZED dalszym przejściem
   - Bez sygnatury critic'a `pipeline.proceed = False`

9. **Audit:**
   ```jsonl
   {
     "prev_hash": "...",
     "content": {
       "kind": "council_wedge.decision",
       "session_id": "8c4f...",
       "topic": "match-idea-g1: portal pracowniczy z logowaniem...",
       "verdict": "conditional",
       "weights": {"approve": 1.25, "conditional": 3.25, "reject": 0.0},
       "dissents": [
         {"role": "critic", "reasons": ["unspecified auth method", "no session timeout"]},
         {"role": "red", "reasons": ["brute force vector", "session hijack vector"]},
         {"role": "compliance", "reasons": ["DPIA required"]}
       ],
       "sentinel_blocks": [
         {"sentinel": "security", "block": "high-PII flag"}
       ],
       "chosen_template_id": "approval_workflow",
       "ts": 1777391500
     },
     "content_hash": "..."
   }
   ```

**Stan:** verdict = conditional, czeka na operatora żeby uzupełnić
warunki. UI pokazuje kartę "wymaga doprecyzowania".

---

### **Faza 5 — Plan Approval (Ticket D3 + opcjonalny HG)**

**Co robi operator:**
- Widzi w `/idea-vault/{id}` listę dissents
- Edytuje pomysł, dodaje brakujące informacje:
  - "logowanie via OAuth Google + SSO LDAP"
  - "session timeout 30 min idle"
  - "rate limit 5 prób / 15 min"
- Klika "Re-deliberate"

**Co robi system:**
- Idea status: `draft` → `under_review`
- Nowa sesja rady z uaktualnionym kontekstem
- **Tym razem** wszystkie obiekcje są zaadresowane → nowy verdict:
  `approve` (waga 5.5/5.5 jednogłośnie)
- Critic podpisuje (w `governance.jsonl`):
  ```json
  {
    "kind": "critic.signature",
    "session_id": "8c4f...",
    "decision_class": "D3",
    "approved": true,
    "ts": 1777392000
  }
  ```
- Decision Ladder generuje **ticket D3**:
  ```json
  {
    "ticket_id": "tk-09bf...",
    "decision_class": "D3",
    "status": "classified",
    "requirements": {
      "human": false,    // D3: opcjonalny
      "council": true,
      "evidence": true,
      "retention_hot": "90d",
      "retention_cold": "2y"
    }
  }
  ```

**HG decision point:**
- D3 ma `human: false`, ale Compliance Officer dorzucił **DPIA wymóg**
- Policy registry W19 sprawdza: "high-PII scope + auth = wymagana
  HG eskalacja"
- Ticket eskaluje na **D4** automatycznie
- Tworzony jest request HG: `/api/v1/gates/human/requests`:
  ```json
  {
    "request_id": "hg-3f2c...",
    "gate_id": "deploy_pii_high",
    "title": "Portal pracowniczy: zatwierdzenie DPIA",
    "context_json": {
      "council_verdict": "approve",
      "dpia_required": true,
      "modules_affected": ["auth_users", "document_workflow"],
      "estimated_users": 500
    },
    "status": "pending"
  }
  ```
- Operator (lub DPO) widzi w UI alert "Wymagana decyzja człowieka"

**Co robi człowiek:**
- Otwiera request, czyta kontekst, ewentualnie dodaje komentarz
- Klika "Approve" → POST `/api/v1/gates/human/reviews`:
  ```json
  {
    "request_id": "hg-3f2c...",
    "reviewer": "operator-001",
    "decision": "approved",
    "comment": "DPIA podpisana, retention 90d/2y OK"
  }
  ```
- Audit:
  ```jsonl
  {
    "kind": "human_gate.review",
    "request_id": "hg-3f2c...",
    "reviewer": "operator-001",
    "decision": "approved",
    "ts": 1777392600
  }
  ```

**Stan:** Ticket D4 zatwierdzony, można przejść do execution.

---

### **Faza 6 — Team Scaling (execution_plan → worker_pool)**

**Co robi system:**
- Workflow_v2 fires `on_status_change` rule:
  - Trigger: `idea.status == "approved"`
  - Action: `dispatch_to_l5_planning`
- L5 generuje `execution_plan` z masterplan'a:
  ```yaml
  execution_plan:
    plan_id: ep-7a31...
    worker_pool_required:
      - kind: ontology_worker  # do registracji object types
        count: 1
      - kind: api_worker        # do generacji REST endpoints
        count: 1
      - kind: ui_worker         # do generacji React komponentów
        count: 2
      - kind: test_worker       # do generacji testów
        count: 1
    parallel_lanes:
      - lane_a: [register_employee, register_document]  # ontology
      - lane_b: [generate_login_endpoints]              # auth
      - lane_c: [generate_workflow_ui]                  # frontend
  ```
- L7 Coord sprawdza konflikty: `register_employee` i `register_document`
  używają tej samej tabeli `object_types` — **muszą być sekwencyjne** w
  lane_a.

**Stan:** Worker pool w stanie `ready_to_dispatch`.

---

### **Faza 7 — Skill Binding**

**Co robi system:**
- L4 Skills bierze `execution_plan` i mapuje kroki na **konkretne skille**
  z `contract_registry`:
  ```yaml
  skill_bindings:
    register_employee:
      contract: ontology.object_type.register
      version: "v2.1"
      executor: aeis_v2/ontology/applier.py:apply_manifest
    generate_login_endpoints:
      contract: auth.endpoints.generate
      version: "v1.4"
      executor: auth/codegen.py:generate_login_routes
    generate_workflow_ui:
      contract: frontend.workflow.scaffold
      version: "v3.0"
      executor: frontend/scaffolder.py:emit_workflow_pages
  ```
- Każdy skill bind jest **immutable** — gdyby manifest się zmienił
  w trakcie, plan musi być przewidziany na nowo (idempotent)

**Stan:** Skille zbindowane, plan jest fully-resolved.

---

### **Faza 8 — Execution (Workery wykonują)**

**Co robi system:**
- L8 Worker pool startuje (przez `DeployAgent`):
  - 5 workerów dispatch'owanych w 3 lane'y
  - Każdy worker dostaje:
    - `worker_id`
    - `task_spec` (skill_binding + parametry)
    - `audit_endpoint` (gdzie ma zgłaszać evidence)
- Workery wykonują:
  - **Lane A worker** → `apply_manifest('employee.yaml')` → DDL
    `CREATE TABLE employee` → applied → wpis do `apply_audit.jsonl`
  - **Lane B worker** → generuje `routes/auth.py` z 5 endpointami
    (login, logout, refresh, etc.) → wpis do `worker_audit.jsonl`
  - **Lane C workery** → emitują React `LoginPage.tsx`,
    `WorkflowList.tsx`, `ApprovalButton.tsx` → commit w gałąź
    `feature/portal-employee`
- Każdy emisyjny event przechodzi przez `RoutingGate` (W19):
  ```
  Filter: event_type in [worker.success, worker.error] → pass
  Route:  by lane → write to audit chain
  Audit:  hash-chained append
  ```

**Mid-flight monitoring:**
- Operator widzi w `/orchestration/dispatch` live stream:
  ```
  [10:23:15] ontology_worker_001 → DDL applied: employee table
  [10:23:18] api_worker_002      → 5 endpoints generated
  [10:23:21] ui_worker_003       → LoginPage.tsx committed
  [10:23:21] ui_worker_004       → WorkflowList.tsx committed
  [10:23:25] test_worker_005     → 24 tests pass, 0 fail
  ```

**Stan:** Wszystkie workery zakończone success, evidence pack
gotowy.

---

### **Faza 9 — Mid-flight Steering (jeśli trzeba)**

**Możliwy scenariusz:** w połowie execution, jeden z workerów wykrył
że proponowane employee table konfliktuje z istniejącą tabelą users
(pola się pokrywają).

**Co robi system:**
- Worker emituje `worker.conflict` event
- L7 ConflictResolver łapie event
- Otwiera **D2 ticket** (mid-flight steering):
  ```
  conflict: employee.email vs users.email — duplikacja
  proposed: rename employee.email → employee.work_email
  ```
- HG opcjonalny dla D2 — domyślnie auto-approve jeśli rezolwer
  rekomenduje rozwiązanie z `confidence > 0.9`
- Jeśli operator chce wstrzymać — klika "Pause" w UI, system
  zatrzymuje pool

**Stan:** Konflikt rozwiązany, execution wznowione.

---

### **Faza 10 — Verification (human-like)**

**Co robi operator:**
- Wchodzi na blue environment (np. `https://blue.portal.firma.local`)
- **Ręcznie klika** flow logowania:
  - Klikam "Zaloguj"
  - Wpisuje email + hasło
  - Klikam "Submit"
  - Sprawdza czy przekierowuje
- W każdym kroku UI emituje `verification.event`:
  ```jsonl
  {
    "kind": "verification.click",
    "operator": "op-001",
    "target": "login_button",
    "result": "success",
    "ts": 1777393500
  }
  ```
- Po pełnej weryfikacji operator klika "Mark verified" — emituje
  `verification.complete`

**Stan:** Verification chain ma N wpisów (po jednym per kliknięcie),
operator zatwierdził wizualnie.

---

### **Faza 11 — Final Approval (D4/D5 — Council + 2 Operators)**

**Co robi system:**
- Generuje **evidence_pack**:
  ```
  evidence_packs/portal-employee-v1.0.zip
  ├── council_decisions/        # wszystkie verdicts z faz 4-5
  ├── critic_signatures/        # 2 sygnatury krytyka
  ├── execution_audit/          # wszystkie worker_audit wpisy
  ├── verification_clicks/      # 47 click events od operatora
  ├── tests/                    # 24 testy + coverage
  ├── dpia.pdf                  # DPIA podpisana
  └── canonical_diff.md         # diff vs Księga
  ```
- Wymaga **drugiego operatora** (lub DPO) do co-sign:
  - HG request `final_approval_d4` z `min_reviewers: 2`
  - First operator (op-001) approve
  - Second operator/DPO (dpo-001) approve
- Dopiero po obu sygnaturach: ticket → `status: approved_for_external`

**Stan:** 2 sygnatury, evidence pack zapieczętowany.

---

### **Faza 12 — External Action (Deploy do prod)**

**Co robi system:**
- DeployAgent uruchamia blue→green promotion przez `StagedRolloutGate`:
  ```
  step 1: 0% traffic → green   (verify config)
  step 2: 1% traffic → green   (smoke test)
  step 3: 5% traffic → green   (canary)
  step 4: 25% traffic → green  (early adopters)
  step 5: 50% traffic → green  (half rollout)
  step 6: 100% traffic → green (full)
  ```
- Każdy step ma **gate**: jeśli error_rate > 1% → automatyczny rollback
  na poprzedni step
- Audit każdego step'u w `deploy_audit.jsonl`

**Stan:** Portal działa na 100% prod traffic.

---

### **Faza 13 — Memory Snapshot**

**Co robi system:**
- Evidence pack frozen — content_hash zapisany w `evidence_chain.jsonl`
- Snapshot stanu rady, masterplan'u, decyzji w `decision_snapshot.py`
- Jeśli operator później zechce "co byłoby gdyby" — może użyć
  `replay-as-fork`:
  ```
  POST /api/v1/terminal/sessions/{sid}/snapshot
  → snapshot_id: snap-7d2f...

  POST /api/v1/replay/run
  body: {
    snapshot_id: snap-7d2f,
    model_override: "claude-opus-4.7",  // co by było z Opus zamiast Gemini?
    replay_decisions: ["approve", ...],
    replay_final: [1.0, ...]
  }
  → divergence_score: 0.34  # 34% różnica vs oryginał
  ```

**Stan:** Wszystko hash-chained, replay'owalne.

---

### **Faza 14 — Drift Audit**

**Co robi system (cron co 24h):**
- Porównuje:
  - Decyzje rady z ostatnich 7 dni
  - vs canonical_book (Księga)
- Jeśli widzi rozjazd (np. "rada zaczęła odrzucać MCP integration ale
  Księga mówi że MCP jest preferred"):
  - Otwiera ticket dryfu w `drift_audit.jsonl`
  - Backlog: "Update Księga lub naprawić radę"

**Stan (typowo):** drift = 0, system pracuje zgodnie z Księgą.

---

### **Faza 15 — Memory Compact**

**Co robi system (cron co 30 dni):**
- Stare audit chains (>90 dni) są kompresowane:
  - Wszystkie `council_wedge.jsonl` w danym miesiącu → jeden
    `monthly_summary.jsonl`
  - Statystyki: ile decyzji per verdict, jakie najczęstsze obiekcje
  - Tail full chains zachowywany w archive
- Księga regeneruje się: jeśli miesiąc był spokojny, dodaje sekcję
  "lessons learned" do canonical_book

**Stan:** Pamięć skompresowana, system gotowy na kolejny cykl.

---

## 5. Jak modele dyskutują — Protokół Council Hybrid

### 5.1. Schemat sesji

```
┌─────────────────────────────────────────────────────┐
│  POST /api/v1/workspace/council/sessions            │
│  body: {topic, decision_class, context}              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  Session created     │
        │  session_id: 8c4f... │
        └──────────┬──────────┘
                   │
                   ▼
   ┌──────────────────────────────────┐
   │ POST /sessions/{sid}/analyze     │
   │ — każda rola dostaje prompt      │
   │ — wywołanie równoległe (Thread)  │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ Parallel role calls:              │
   │  planner → Claude Opus            │
   │  critic → Claude Opus             │
   │  security → GPT-5                 │
   │  legal → Gemini 2.5 Pro           │
   │  finance → GPT-5                  │
   │  red → Grok-3                     │
   │  governance → Claude Opus         │
   │  qa → GPT-5                       │
   │  council_chair → Claude Opus      │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ POST /sessions/{sid}/discuss      │
   │ — runda dyskusji (round 2)        │
   │ — role widzą cudze odpowiedzi     │
   │ — mogą zmienić verdict            │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ POST /sessions/{sid}/critic/sign  │
   │ — krytyk MUSI podpisać            │
   │ — bez sygnatury: blok             │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ POST /sessions/{sid}/sentinels    │
   │ — Cost Sentinel sprawdza budżet   │
   │ — Security Sentinel scan tagów    │
   │ — może zablokować                 │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ POST /sessions/{sid}/consolidate  │
   │ — ważone głosowanie               │
   │ — verdict końcowy                 │
   │ — wpis do council_wedge.jsonl     │
   └──────────────────────────────────┘
```

### 5.2. Format promptów per rola

Każda rola dostaje prompt o **tej samej strukturze**, ale z różnymi
focus areas:

```
SYSTEM:
Jesteś {role_name} w Radzie SYLION AEIS.
Twoje obszary: {role_focus}
Twoja waga w głosowaniu: {weight}
Twoja klasa decyzji: {decision_class}

Zasady:
- Odpowiadasz tylko w zakresie swojej roli
- Verdict MUSI być jednym z: approve / conditional / reject / abstain
- Dissent MUSI mieć min. 1 zdanie uzasadnienia
- Sentinel block MUSI mieć typ + reason

KONTEKST:
Idea: {idea_text}
Tags: {tags}
Affected modules: {modules}
Canonical book reference: {book_section}

POPRZEDNIA RUNDA (jeśli round > 1):
{previous_round_summary}

WYMAGANA ODPOWIEDŹ (JSON):
{
  "verdict": "approve|conditional|reject|abstain",
  "reasoning": "krótko, max 200 słów",
  "dissents": [
    {"reason": "...", "severity": "low|med|high"}
  ],
  "sentinel_blocks": [
    {"sentinel": "cost|security|legal", "reason": "..."}
  ]
}
```

### 5.3. Ważone głosowanie

Po wszystkich rundach:

```python
def consolidate(votes: list[Vote]) -> CouncilDecision:
    weights = {"approve": 0.0, "conditional": 0.0, "reject": 0.0, "abstain": 0.0}
    for v in votes:
        weights[v.verdict] += v.role_weight

    # Verdict to ten z najwyższą wagą
    winner = max(weights, key=weights.get)

    # Ale: jeśli reject ma > 30% wagi → conditional eskalacja
    total = sum(weights.values())
    if weights["reject"] / total > 0.3:
        winner = "conditional"  # eskaluj na human

    return CouncilDecision(
        verdict=winner,
        weights=weights,
        dissents=collect_dissents(votes),
        sentinel_blocks=collect_blocks(votes),
    )
```

### 5.4. Sygnatura krytyka — mechanizm

Krytyk to **specjalna rola** — niezależnie od składu 4/4, **ZAWSZE**
wywoływany dla decyzji ≥D3.

```python
def require_critic_signature(session_id: str, decision: CouncilDecision):
    if decision.verdict == "approve":
        # Krytyk widzi finalny verdict i ma 2 wybory:
        # - Sign (zgadza się)
        # - Refuse (nie zgadza się — blokuje pipeline)
        critic_response = await critic.review(decision)
        if critic_response.refused:
            # Pipeline ZATRZYMANY — wymaga eskalacji do D4
            raise CriticRefusalError(
                f"Critic refused to sign D{decision.class}: {critic_response.reason}"
            )
        # Sygnatura zapisana w governance.jsonl
        append_to_chain(GOVERNANCE_LOG, {
            "kind": "critic.signature",
            "session_id": session_id,
            "approved": True,
            "ts": time.time(),
        })
```

### 5.5. Sentinels — Cost & Security

```python
class CostSentinel:
    def evaluate(self, decision: CouncilDecision) -> SentinelResult:
        estimated_cost = sum(role.last_call_cost for role in decision.roles)
        budget_remaining = get_daily_budget()
        if estimated_cost > budget_remaining * 0.8:  # 80% budgetu
            return SentinelResult(
                blocked=True,
                reason=f"Cost ${estimated_cost} > 80% of budget ${budget_remaining}"
            )
        return SentinelResult(blocked=False)


class SecuritySentinel:
    HIGH_RISK_TAGS = {"auth", "logowanie", "secrets", "production-deploy"}

    def evaluate(self, decision: CouncilDecision) -> SentinelResult:
        risky = decision.affected_tags & self.HIGH_RISK_TAGS
        if risky and decision.class < "D4":
            return SentinelResult(
                blocked=True,
                reason=f"Tags {risky} require D4+ — auto-escalating"
            )
        return SentinelResult(blocked=False)
```

---

## 6. HumanGates i Guardy

### 6.1. Typy HumanGate (10 zdefiniowanych)

| Gate ID | Trigger | Wymóg człowieka |
|---|---|---|
| `idea_intake` | Nowy pomysł | NIE (auto) |
| `council_d3` | Klasyfikacja D3 | OPCJONALNY |
| `council_d4` | Klasyfikacja D4 | TAK |
| `council_d5` | Klasyfikacja D5 | TAK + ZEWNĘTRZNY RECENZENT |
| `dpia_required` | Tag PII high | TAK (DPO) |
| `cost_threshold` | Budget > 80% | TAK |
| `security_high` | Tag security/auth | TAK |
| `production_deploy` | Deploy do prod | TAK + 2 operatorów |
| `gdpr_erasure` | Article 17 request | TAK + audit |
| `mid_flight_pause` | Worker conflict | OPCJONALNY |

### 6.2. Cykl życia HG ticket'u

```
┌─────────┐     pending → reviewed
│ created │ ──────────────────────┐
└─────────┘                       │
                                  ▼
                          ┌──────────────┐
                          │ approved     │ → pipeline.proceed
                          │ rejected     │ → pipeline.halt
                          │ needs_info   │ → re-deliberate
                          └──────────────┘

                       eskalacja po 3× needs_info → D4
```

### 6.3. Audit ścieżki HG

Każdy gate emituje **3 wpisy** w `governance.jsonl`:

```jsonl
{ "kind": "human_gate.requested", "request_id": ..., "gate_id": ..., "ts": T1 }
{ "kind": "human_gate.assigned",  "reviewer": ..., "ts": T2 }
{ "kind": "human_gate.review",    "decision": "approved", "comment": ..., "ts": T3 }
```

### 6.4. Guardy — runtime ochrona

Guardy to **policy-as-code** (W19 evaluator, Jinja2 sandbox):

```yaml
# Przykładowe guardy w policy_v2/policies/
guards:
  no_prod_deploy_friday:
    when: "deploy.environment == 'prod' and date.weekday() == 4"
    block: true
    message: "Brak deploy w piątki — kompromisy weekendowe"

  pii_high_requires_dpia:
    when: "tags includes 'pii_high' and dpia.signed != true"
    block: true
    message: "Wymagana DPIA przed dowolną akcją na PII high"

  cost_cap_per_idea:
    when: "session.total_cost_usd > 50"
    block: true
    message: "Idea przekroczyła $50 budget LLM"

  council_no_quorum:
    when: "council.votes_count < 4 and decision_class >= 'D3'"
    block: true
    message: "D3+ wymaga min. 4 głosów"
```

Każdy guard jest **renderowany w sandboxed Jinja2** przed
ewaluacją — nie ma możliwości RCE/SSTI (testy chaos pokrywają
CWE-94).

### 6.5. Kaskadowa eskalacja

Jeśli kilka guardów odpala jednocześnie:
```
1. Cost guard (block) + Security guard (block) →
   eskalacja do D4 + 2 operatorów + DPO sign-off
2. Council quorum brak → automatyczne dospraszanie pozostałych ról
3. Drift detected → ticket zamiast block
```

---

## 7. Co AEIS robi w skrócie (TL;DR)

```
1.  Operator wpisuje pomysł
2.  System loguje + klasyfikuje (D0-D5)
3.  Rada 9 ról deliberuje (równolegle, 3 rundy)
4.  Krytyk podpisuje (lub blokuje)
5.  Sentinels sprawdzają cost + security
6.  HumanGate (jeśli D3+ z eskalacją)
7.  Operator zatwierdza lub odrzuca
8.  Plan rozkłada na lane'y + workery
9.  Workery wykonują, każdy emituje audit
10. Operator weryfikuje wizualnie (UI clicks)
11. Final approval D4 + 2 ops + DPO
12. Deploy (canary 0→100%)
13. Snapshot + replay-fork ready
14. Drift detection (cron)
15. Memory compact (cron)
```

**Kluczowa różnica vs zwykły CI/CD:**
- Każdy krok generuje **append-only hash-chained audit** (cofnięcie =
  niemożliwe bez wykrycia)
- Każda decyzja ≥D3 ma **podpis krytyka** + **ważone głosowanie**
- Każda zmiana parametru jest **replay'owalna** (divergence score)
- HumanGate jest **w każdym krytycznym miejscu**, nie tylko na końcu
- Rada **rozmawia ze sobą** — nie jest to seria niezależnych
  zapytań do LLM

---

## 8. Bibliografia kodu

| Co | Gdzie |
|---|---|
| Council Hybrid silnik | `governance/council_hybrid.py` |
| Decision Ladder | `governance/decision_ladder.py` |
| Audit Chain | `aeis_v2/audit_chain/chain.py` |
| Replay-as-fork | `aeis_v2/replay_v2/` |
| W19 Policy Evaluator | `aeis_v2/policy_v2/` |
| Workflow Engine | `aeis_v2/workflow_v2/` |
| Apps Builder Wizard | `src/sylion-frontend/src/app/(app)/apps-builder/wizard/` |
| Idea Vault | `src/sylion-frontend/src/app/(app)/idea-vault/` |
| Governance UI | `src/sylion-frontend/src/app/(app)/governance/` |
| Admin Dashboard | `src/sylion-frontend/src/app/(app)/v2/admin/` |
| Symulacja E2E | `src/sylion-frontend/e2e/aeis_simulation_4_products.spec.ts` |
| Verify CLI | `scripts/v2/verify_audit_chains.py` |

