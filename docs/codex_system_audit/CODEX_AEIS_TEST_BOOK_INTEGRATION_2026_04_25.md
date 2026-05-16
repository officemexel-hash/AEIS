# CODEX AEIS Test Book Integration 2026-04-25

**Źródło:** [AEIS_KSIEGA_TESTOW_500_SCENARIUSZY.pdf](C:/Users/razor/Downloads/AEIS_KSIEGA_TESTOW_500_SCENARIUSZY.pdf)  
**Cel:** określić, jak Księga Testów 500 scenariuszy wchodzi do masterplanu naprawczego AEIS i które części tej księgi są używane na poszczególnych etapach

## 1. Werdykt

Ten PDF należy traktować jako:

- kanoniczną księgę testową AEIS,
- specyfikację końcowej walidacji production readiness,
- specyfikację pętli auto-repair,
- specyfikację checkpointów jakości dowodów,
- specyfikację poziomów autonomii testowej.

To nie jest dokument „na koniec projektu”. On wpływa na cały program naprawczy od pierwszego dnia.

## 2. Najważniejsze ustalenia z księgi

### 2.1. Zasada nadrzędna

Na stronach 2-4 księga ustawia trzy reguły, które są całkowicie zgodne z naszym re-audytem:

1. testy mają próbować obalić deklarację `production-ready`,
2. prawda ma być badana w kolejności:
   `kod -> runtime -> API -> UI -> testy -> dokumentacja`,
3. każdy wykryty błąd ma uruchamiać kontrolowaną pętlę `auto-repair`, ale bez obchodzenia Human Gate.

To oznacza, że księga nie jest tylko katalogiem testów. To jest procedura dowodowa.

### 2.2. Zakres systemowy

Strona 2 mówi wprost, że zakres obejmuje:

- Idea lifecycle,
- Human Gate od momentu wpisania pomysłu,
- Source of Truth,
- Masterplan,
- Council,
- Skills,
- Memory,
- Funding,
- Mobile,
- Security,
- Observability,
- Chaos,
- Recovery,
- Auto-Repair,
- test uczenia się AEIS.

To pokrywa dokładnie te obszary, które w re-audycie wyszły jako krytyczne truth planes.

### 2.3. Wymagane skills testowe

Strony 2-3 definiują zestaw potrzebnych skilli testowych, m.in.:

- `S-AUDIT-01 Repo Auditor`
- `S-AUDIT-02 Runtime Inspector`
- `S-AUDIT-03 API Contract Tester`
- `S-AUDIT-04 Browser Human Tester`
- `S-GOV-01 Human Gate Specialist`
- `S-GOV-02 Idea Lifecycle Specialist`
- `S-COUNCIL-01 Council Verifier`
- `S-MEM-01 Memory Tester`
- `S-SKILL-01 Skills Tester`
- `S-FUND-01 Funding Tester`
- `S-MOB-01 Mobile Tester`
- `S-SEC-01 Security Tester`
- `S-OBS-01 Observability Tester`
- `S-CHAOS-01 Chaos Tester`
- `S-REPAIR-01 Auto-Repair Engineer`
- `S-QA-01 Regression Coordinator`

To nie są jeszcze gotowe implementacje repo, ale bardzo dobra specyfikacja ról testowych dla późniejszego podziału prac i końcowej walidacji.

### 2.4. Poziomy autonomii testowej

Strona 3 definiuje poziomy `A0-A5`:

- `A0 Observe only`
- `A1 Recommend`
- `A2 Sandbox patch`
- `A3 Auto repair low risk`
- `A4 Repair with Human Gate`
- `A5 Emergency controlled`

To jest bardzo ważne, bo daje nam gotowy model sterowania auto-repair w fazie testów.

### 2.5. Pętla auto-repair

Strony 3-4 definiują pętlę `R0-R9`:

- `R0 Detect`
- `R1 Reproduce`
- `R2 Classify`
- `R3 Localize`
- `R4 Patch`
- `R5 Regression`
- `R6 Evidence`
- `R7 Human retest`
- `R8 Learning`
- `R9 Gate`

To jest szczególnie ważne dla końcowego etapu, bo księga mówi wprost:
- nie wolno kończyć na samym raporcie błędu,
- nie wolno naprawiać przez ukryty mock, fallback, usunięcie testu ani budowę równoległego subsystemu.

### 2.6. Checkpointy jakości

Strona 4 definiuje checkpointy `C1-C10`, m.in.:

- `C1 Evidence`
- `C2 Runtime`
- `C3 Operator clarity`
- `C4 Gate correctness`
- `C5 No split plane`
- `C6 Audit trail`
- `C7 Learning`
- `C8 Retest`
- `C9 Negative path`
- `C10 No hidden mock`

To jest bardzo mocne doprecyzowanie tego, czego ma dotyczyć finalny audit.

### 2.7. Kategorie 500 testów

Na stronach 4-5 księga dzieli testy na 13 grup:

- `SMOKE` 18
- `CODE` 32
- `API` 34
- `UI` 42
- `IDEA` 55
- `COUNCIL` 30
- `PLAN` 38
- `SKILL` 30
- `MEM` 35
- `MOBILE` 30
- `FUND` 38
- `SEC` 35
- `CHAOS` 35
- `REPAIR` 33
- `E2E` 15

Razem daje to 500 scenariuszy.

## 3. Co w księdze jest szczególnie cenne wobec naszego re-audytu

Księga bardzo dobrze pokrywa dokładnie te dziury, które wyszły w re-audycie:

1. `CODE`
   Testy route/service mismatch i split planes.
   To trafia w nasze:
   - `workspace Human Gate`
   - `workspace ideas`
   - split `skills`
   - split `memory`
   - split `funding approvals`

2. `API`
   Testy shadowingu dynamic routes, zgodności OpenAPI z runtime i złych payloadów.
   To trafia w nasze broken API surfaces.

3. `UI`
   Testy mock fallback i prawdziwego data plane.
   To trafia w:
   - `/projects`
   - `/workers`
   - `/observability`
   - `operator-mobile`

4. `IDEA`
   Testy first Human Gate od pomysłu, delete/archive i change proposal.
   To trafia w dokładnie ten kierunek, który wspólnie ustaliliśmy dla AEIS.

5. `COUNCIL`
   Testy critic signature, voting weights, tie handling i wpływu councilu na plan.
   To trafia w centralną lukę naszego stanu obecnego.

6. `PLAN`
   Testy Source of Truth, Masterplan i worker_pool reconciliation.
   To trafia w blocker `RB-002`.

7. `SKILL`
   Testy `loaded_skills vs registry` oraz execute path.
   To trafia w blocker `RB-P2-003`.

8. `MEM`
   Testy similarity, durability i `API memory vs frontend`.
   To trafia w `RB-003`, `RB-014` i `RB-015`.

9. `MOBILE`
   Testy `queue routing per operator`, `approval/reject -> unified governance`, `mock fallback`.
   To trafia w `RB-P2-007`.

10. `FUND`
    Testy `submit without approval` i `approval przez unified governance`.
    To trafia w `RB-P2-004`.

11. `SEC`, `CHAOS`, `REPAIR`, `E2E`
    To są doskonałe końcowe filtry przeciwko ogłoszeniu zbyt wczesnego `production-ready`.

## 4. Jak księga wchodzi do masterplanu

Księga nie powinna być użyta dopiero w Fazie 8. Powinna być rozpięta przez cały masterplan.

### Faza 0: Zamrożenie bazowe i kontrakt integracyjny

Używamy z księgi:

- reguły prawdy `kod -> runtime -> API -> UI -> testy -> dokumentacja`
- checkpointy `C1-C10`
- poziomy autonomii `A0-A5`
- pętlę `R0-R9`

W tej fazie księga jest źródłem polityki wykonawczej, nie jeszcze pełnego retestu.

### Faza 1: Runtime Spine Recovery

Używamy:

- `SMOKE`
- część `CODE`
- część `API`

Priorytety:
- boot
- route count
- health
- log startu
- manifest/register errors

To jest pierwsza fala testów obowiązkowych po każdej zmianie w spine.

### Faza 2: Workspace Recovery

Używamy:

- `SMOKE`
- `API`
- `UI`
- `IDEA`

Priorytety:
- workspace minimal requests
- workspace ideas lifecycle
- workspace Human Gate od momentu pomysłu
- brak `500`

### Faza 3: Governance + Council Unification

Używamy:

- `IDEA`
- `COUNCIL`
- `PLAN`
- część `SEC`

Priorytety:
- direction approval
- critic signature
- voting weights
- tie -> Human Gate
- change proposal po SoT
- Source of Truth i Masterplan z prawidłowymi gate'ami

### Faza 4: Memory + Skills Unification

Używamy:

- `SKILL`
- `MEM`
- część `PLAN`
- część `REPAIR`

Priorytety:
- `loaded_skills vs registry`
- execute dla seed i registry skill
- similarity hit
- durability po restarcie
- memory API vs frontend
- learning po poprawce

### Faza 5: Funding Governance Convergence

Używamy:

- `FUND`
- część `SEC`
- część `MOBILE`

Priorytety:
- submit without approval blocked
- unified governance tickets
- external/final gate correctness
- brak lokalnego funding truth plane

### Faza 6: Operator Surfaces Recovery

Używamy:

- `UI`
- `API`
- `MOBILE`
- `OBS`

Priorytety:
- brak `500`
- brak ukrytego fallbacku udającego live
- poprawny data plane dla operatora
- routing per operator

### Faza 7: Runtime Topology + Orchestration Recovery

Używamy:

- `PLAN`
- `CHAOS`
- część `SEC`

Priorytety:
- worker_pool reconciliation
- concurrency
- recovery
- brak cross-run pollution
- brak fake success przy degradacji

### Faza 8: Proof, Hardening, Production Readiness

Tutaj wchodzi pełna księga.

Obowiązkowy zakres:

- pełen `SMOKE`
- pełen `CODE`
- pełen `API`
- pełen `UI`
- pełen `IDEA`
- pełen `COUNCIL`
- pełen `PLAN`
- pełen `SKILL`
- pełen `MEM`
- pełen `MOBILE`
- pełen `FUND`
- pełen `SEC`
- pełen `CHAOS`
- pełen `REPAIR`
- pełen `E2E`

## 5. Co z tego wynika dla podziału prac między modele

Księga testów zmienia jedną ważną rzecz:

Nie wystarczy podzielić napraw. Trzeba też podzielić odpowiedzialność za klasy testów i auto-repair.

### Lider architektoniczny

Powinien odpowiadać za:

- `SMOKE`
- `CODE`
- krytyczne `API`
- `IDEA`
- `COUNCIL`
- `PLAN`

Bo to testy rdzenia systemu i truth planes.

### Strumień średni

Powinien odpowiadać za:

- `SKILL`
- `MEM`
- część `UI`
- część `MOBILE`

Bo to są warstwy adaptacyjne i operatorskie, ale już po ustabilizowaniu core contracts.

### Strumień lżejszy

Powinien odpowiadać za:

- `FUND`
- `OBS`
- lżejsze `UI`
- lżejsze `SEC`
- część `CHAOS`

To dobrze pasuje do proceduralnych napraw i testów domenowych.

### Integrator końcowy

Powinien odpowiadać za:

- pełny `REPAIR`
- pełny `E2E`
- końcowy browser walk
- pełny retest po poprawkach

## 6. Co należy dopisać do zasad wykonania masterplanu

Od teraz masterplan powinien przyjąć trzy dodatkowe reguły:

1. Żadna faza nie kończy się bez przypisanych kategorii testów z Księgi 500.

2. Finalne `production-ready` wolno ogłosić dopiero po przejściu pełnej Księgi 500 albo uzasadnionej, jawnie opisanej jej podmacierzy z planem domknięcia reszty.

3. Każdy ważniejszy fix powinien być domykany w logice:
   `R0-R9`, nie tylko przez „patch i commit”.

## 7. Rekomendacja

Ten dokument należy traktować jako obowiązkowy załącznik do:

- [CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md](C:/Users/razor/Desktop/pipeline_glm/docs/codex_system_audit/CODEX_AEIS_UNIFIED_REPAIR_MASTERPLAN_2026_04_25.md)

Księga Testów 500 nie zmienia kierunku masterplanu. Ona go uszczelnia.

Najważniejszy efekt:

- potwierdza, że nasz obecny porządek faz jest dobry,
- potwierdza, że nie wolno zbyt wcześnie ogłaszać `production-ready`,
- daje gotowy kanon końcowego dowodu jakości i auto-repair.

## 8. Wniosek końcowy

`AEIS_KSIEGA_TESTOW_500_SCENARIUSZY.pdf` należy uznać za kanoniczny dokument walidacyjny AEIS.

Nie jest to dokument „opcjonalny”.

Od teraz należy go używać:

- częściowo już od Fazy 0,
- obowiązkowo od Fazy 1 do Fazy 7 jako selektywnej matrycy testów,
- w pełni w Fazie 8 jako końcowego dowodu production readiness.
