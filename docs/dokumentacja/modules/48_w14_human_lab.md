# W14 Human Lab — 8 person + 10 scenariuszy startowych
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Moduł: `sylion.aeis.testing.personas`
> Commit: `4faab428` — E8
> Pliki: `personas/_starter/*.json` + `personas/scenarios.py`

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura](#2-architektura)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje — PersonaRegistry i PersonaRuntime](#4-funkcje--personaregistry-i-personaruntime)
5. [8 person — szczegóły](#5-8-person--szczegóły)
6. [10 scenariuszy startowych](#6-10-scenariuszy-startowych)
7. [Przykład użycia](#7-przykład-użycia)
8. [Weryfikacja](#8-weryfikacja)
9. [Rozwiązywanie problemów](#9-rozwiązywanie-problemów)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modułu

Human Lab dostarcza **realistyczne symulacje zachowań ludzkich operatorów** w procesie
testowania W14. Każda persona modeluje konkretny profil użytkownika (poziom kompetencji,
zmęczenie, presja czasowa, skłonność do pomijania ostrzeżeń). Scenariusze łączą personę
z konkretnymi krokami operacyjnymi i oczekiwanymi wynikami.

Moduł służy do:
- Wykrywania podatności systemu na błędy ludzkie (7 klas HumanError per kanon)
- Testowania zabezpieczeń D-ladder przy różnych profilach ryzyka
- Kalibracji wymagań Test Center dla projektów demo E11

E8 dodał 4 nowe persony (05–08) do istniejących 4 (01–04 z E3), kompletując zestaw 8.
Dodał też 10 gotowych scenariuszy startowych.

---

## 2. Architektura

```
testing/personas/
  _starter/
    01_operator_beginner.json
    02_operator_power_user.json
    03_auditor.json
    04_operator_overloaded.json
    05_admin_overconfident.json     # NOWE E8
    06_viewer_curious.json          # NOWE E8
    07_mobile_first_operator.json   # NOWE E8
    08_incident_responder.json      # NOWE E8
  scenarios.py                      # NOWE E8 — 10 scenariuszy
  registry.py                       # PersonaRegistry (z E3)
  runtime.py                        # PersonaRuntime (z E3)
  tests/
    test_scenarios.py               # 14 testow (8 persona + 6 scenario)
```

Każda persona to plik JSON z trzema blokami: `baseline`, `dynamic_state_initial`,
`behavior_modifiers`. `PersonaRegistry` ładuje je i rejestruje w `OntologyStore`.
`PersonaRuntime` symuluje workflow/decyzje z uwzględnieniem modyfikatorów behawioralnych.

---

## 3. Konfiguracja

Brak dedykowanych zmiennych środowiskowych. Persony ładowane z katalogu `_starter/`
względem pliku `registry.py`. Można dodać własne persony przez umieszczenie pliku
JSON z wymaganymi polami w podkatalogu `_starter/` lub dowolnym podkatalogu.

Wymagane pola JSON persony:

| Pole | Typ | Opis |
|------|-----|------|
| `name` | str | ID persony (bez prefixu `persona_`) |
| `description` | str | Opis tekstowy (imię + rola + cecha) |
| `baseline.capability_level` | str | `beginner \| intermediate \| expert` |
| `baseline.error_proneness` | float 0–1 | Bazowe prawdopodobieństwo błędu |
| `baseline.risk_tolerance` | str | `low \| medium \| high` |
| `dynamic_state_initial` | dict | Stan startowy: fatigue/cognitive_load/time_pressure |
| `behavior_modifiers` | dict | Modyfikatory decyzji (latency/hesitation/skips_warnings) |

---

## 4. Funkcje — PersonaRegistry i PersonaRuntime

### PersonaRegistry (z E3, rozszerzony w E8)

| Metoda | Opis |
|--------|------|
| `load_starter()` | Laduje wszystkie 8 person z `_starter/` do OntologyStore |
| `register(persona)` | Rejestruje pojedynczą personę |
| `get(persona_id)` | Pobiera personę z OntologyStore |
| `list_all()` | Lista wszystkich zarejestrowanych person |

### PersonaRuntime (z E3)

| Metoda | Opis |
|--------|------|
| `simulate_workflow(persona, scenario)` | Symuluje przepływ kroków z modyfikatorami behawioralnymi |
| `simulate_decision(persona, decision_point)` | Modeluje pojedynczą decyzję (latency, hesitation) |
| `inject_error(persona, error_class)` | Wstrzykuje konkretną klasę błędu ludzkiego |

### starter_scenarios() (z E8)

```python
from sylion.aeis.testing.personas.scenarios import starter_scenarios

scenarios = starter_scenarios()  # zwraca list[HumanScenario], 10 elementów
```

Każdy `HumanScenario` zawiera:
- `persona_id` (z prefixem `persona_`)
- `domain` (obszar systemu)
- `workflow_steps` (lista kroków)
- `decision_points` (punkty decyzyjne)
- `success_criteria` (warunki sukcesu)
- `comprehension_check` (pytanie weryfikujące zrozumienie)
- `difficulty` (`easy | medium | hard`)

---

## 5. 8 person — szczegóły

### Persony oryginalne (E3, 01–04)

| # | Nazwa | Imię | Poziom | error_proneness | Kluczowe modyfikatory |
|---|-------|------|--------|-----------------|----------------------|
| 01 | `operator_beginner` | Anna | beginner | 0.45 | hesitation 0.6, double_check 0.8, latency 2.5× |
| 02 | `operator_power_user` | Marek | expert | 0.08 | skips_warnings 0.35, latency 0.4×, hesitation 0.05 |
| 03 | `auditor` | Katarzyna | expert | 0.05 | verifies_evidence 0.98, double_check 0.95, latency 1.8× |
| 04 | `operator_overloaded` | Tomek | intermediate | 0.32 | fatigue 0.78, cognitive_load 0.85, approve_all_temptation 0.4 |

**operator_beginner (Anna)** — pierwsza sesja z AEIS. Ostrożna, łatwo zdezorientowana.
Trust_in_ai 0.7 (wysokie zaufanie, ale małe kompetencje). 2× wolniejsze decyzje.
Testuje: komunikaty błędów, onboarding flow, czytelność wymagań.

**operator_power_user (Marek)** — 2+ lata w AEIS. Szybki, zna skróty. Pomija ostrzeżenia
w 35% przypadków. Testuje: zabezpieczenia przed rutynowymi pomyłkami ekspertów.

**auditor (Katarzyna)** — compliance auditor. Metodyczna, evidence-driven. Weryfikuje
dowody w 98% przypadków. Testuje: kompletność audit chain, Evidence Pack.

**operator_overloaded (Tomek)** — 7h w pracy, 11 poprzednich decyzji z rzędu. Fatigue 0.78,
cognitive_load 0.85. Skips warnings 0.55, approve_all_temptation 0.4. Testuje: zachowanie
systemu przy wyczerpaniu operatora.

### Nowe persony (E8, 05–08)

| # | Nazwa | Imię | Poziom | error_proneness | Kluczowe modyfikatory |
|---|-------|------|--------|-----------------|----------------------|
| 05 | `admin_overconfident` | Marcin | expert | 0.18 | skips_warnings 0.7, attempts_d5_solo 0.4, latency 0.3× |
| 06 | `viewer_curious` | Piotr | intermediate | 0.55 | attempts_unauthorized 0.6, hesitation 0.4 |
| 07 | `mobile_first_operator` | Ewa | intermediate | 0.28 | small_screen_misclick 0.15, time_pressure 0.6 |
| 08 | `incident_responder` | Adam | expert | 0.15 | cognitive_load 0.9, time_pressure 0.95, panic_action 0.2 |

**admin_overconfident (Marcin)** — admin role, szybki klikacz, nadmierna wiara we własny
osąd. Trust_in_ai 0.3 (niskie). Próbuje D5 solo w 40% przypadków. Risk tolerance: high.
Testuje: blokady D5 Council requirement, governance gate przy próbach obejścia.

**viewer_curious (Piotr)** — rola viewer, eksploruje przyciski bez uprawnień. Próbuje
nieautoryzowanych akcji w 60% przypadków. Risk tolerance: medium.
Testuje: RBAC enforcement, widoczność błędów 403.

**mobile_first_operator (Ewa)** — zatwierdza przez telefon w trakcie spotkań. Małe okno,
presja czasowa 0.6, możliwość misclick 0.15. D3+ świadomie odsyła na desktop.
Testuje: mobile UI guards, ograniczenie decyzji D3+ na urządzeniach mobilnych.

**incident_responder (Adam)** — on-call SRE, alert P0, bardzo wysoka presja (time_pressure
0.95, cognitive_load 0.9, fatigue 0.5). Panic_action 0.2 — ryzyko pochopnych decyzji.
Testuje: rollback flow, SLA 15-minutowe, zachowanie systemu pod presją incydentu.

---

## 6. 10 scenariuszy startowych

Funkcja `starter_scenarios()` zwraca 10 kanonicznych `HumanScenario` pokrywających
wszystkie 8 person i kluczowe przepływy AEIS.

| # | Nazwa | Persona | Domena | Trudność | Kluczowe decision points |
|---|-------|---------|--------|----------|--------------------------|
| 1 | First HMEP project | operator_beginner | hmep | easy | approve_charter_d3, approve_release_d3 |
| 2 | Approve 5 D2 in batch | operator_power_user | advisor | medium | batch_approve_d2 (D3 zabronione w batchu) |
| 3 | Verify audit chain | auditor | compliance | medium | accept_evidence_complete, flag_evidence_gap |
| 4 | 12 pending end of shift | operator_overloaded | advisor | hard | approve_or_defer_each_of_12 |
| 5 | Admin attempts D5 solo | admin_overconfident | release | hard | respect_block_or_attempt_bypass |
| 6 | Viewer tries unauthorized | viewer_curious | exploration | easy | accept_block_or_complain |
| 7 | Quick mobile approval | mobile_first_operator | mobile | medium | approve_or_defer_to_desktop |
| 8 | P0 production rollback | incident_responder | incident | hard | rollback_within_15min |
| 9 | Funding application submission | operator_power_user | funding | medium | accept_or_revise_application |
| 10 | Loop Governor escalation review | auditor | incident | hard | accept_known_issue / change_masterplan / abandon / reassign |

### Szczegóły wybranych scenariuszy

**Scenariusz 5 — Admin attempts D5 solo** (admin_overconfident, hard):

Kroki: `open_release_candidate -> click_promote_to_production -> see_council_required_block`
Punkt decyzyjny: `respect_block_or_attempt_bypass`
Sukces: `block_respected_or_audit_attempt_logged`
Pytanie comprehension: "Why does D5 require Council?"

Weryfikuje, że system nie pozwala adminowi zatwierdzić D5 bez sesji Rady, a próba obejścia
jest logowana w audit trail.

**Scenariusz 8 — P0 rollback** (incident_responder, hard):

Kroki: `see_p0_alert -> open_release_candidate -> trigger_rollback -> verify_state`
Punkt decyzyjny: `rollback_within_15min`
Sukces: `rollback_initiated` + `audit_recorded`
Pytanie comprehension: "What is the rollback SLA for P0?"

**Scenariusz 10 — Loop Governor escalation** (auditor, hard):

Kroki: `open_loop_report -> review_attempts -> review_root_cause -> decide_human_action`
Punkty decyzyjne: `accept_known_issue | change_masterplan | abandon | reassign`
Sukces: `decision_recorded_in_audit`
Pytanie comprehension: "What does close_loop_as_blocked do?"

---

## 7. Przykład użycia

### Załadowanie person i uruchomienie scenariusza

```python
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.personas.registry import PersonaRegistry
from sylion.aeis.testing.personas.scenarios import starter_scenarios
from sylion.aeis.testing.personas.runtime import PersonaRuntime

ontology = OntologyStore(db_path=":memory:")
registry = PersonaRegistry(ontology)
registry.load_starter()  # załaduj 8 person

scenarios = starter_scenarios()
scenario_d5 = next(s for s in scenarios if "D5" in s.scenario_id or "admin" in s.persona_id)

# Pobierz personę
persona = registry.get("persona_admin_overconfident")

# Symuluj przepływ
runtime = PersonaRuntime()
result = runtime.simulate_workflow(persona, scenario_d5)
print(result["outcome"])  # "block_respected" lub "bypass_attempted"
```

### Sprawdzenie cognitive runtime po N decyzjach

```python
# Persona overloaded po 11 decyzjach — sprawdź cognitive_load
persona = registry.get("persona_operator_overloaded")
runtime = PersonaRuntime()

for i in range(12):
    runtime.simulate_decision(persona, {"d": "approve_or_defer"})

state = runtime.get_state(persona)
print(state["cognitive_load"])  # > 0.9 — ryzyko approve_all_temptation
```

---

## 8. Weryfikacja

```bash
cd src/sylion-pipeline

# Testy person + scenariuszy (14 testów)
python -m pytest tests/aeis/testing/personas/test_scenarios.py -v

# Wszystkie testy E7+E8 razem
python -m pytest tests/aeis/testing/ -v
# Oczekiwany wynik: 27 (E7) + 14 (E8) = 41 testów, wszystkie zielone

# Sprawdź listę scenariuszy bez uruchamiania testów
cd src/sylion-pipeline
python -c "
from sylion.aeis.testing.personas.scenarios import starter_scenarios
for s in starter_scenarios():
    print(s.persona_id, s.domain, s.difficulty)
"
```

---

## 9. Rozwiązywanie problemów

### `ValueError: persona_id must start with 'persona_'`

`HumanScenario` wymaga prefiksu `persona_` w polu `persona_id`. Funkcja `_scn()` w
`scenarios.py` dodaje prefix automatycznie. Przy ręcznym tworzeniu scenariuszy upewnij
się, że `persona_id = f"persona_{raw_id}"`.

### Persona nie jest ładowana z `_starter/`

Sprawdź, czy plik JSON ma wszystkie wymagane bloki: `name`, `baseline`, `dynamic_state_initial`,
`behavior_modifiers`. Brakujące pola powodują `KeyError` przy `registry.load_starter()`.

### Scenariusz nie kończy się sukcesem

Persona z wysokim `cognitive_load` lub `time_pressure` może generować inną ścieżkę niż
oczekiwana. Sprawdź `behavior_modifiers` dla danej persony i dostosuj `success_criteria`
w teście lub przyjmij alternatywny wynik w asercji.

---

## 10. Cross-references

- [`46_w14_ontology.md`](./46_w14_ontology.md) — `HumanScenario`, `PersonaRegistry`,
  `PersonaRuntime`, 7 klas błędów ludzkich (E3), oryginalne 4 persony
- [`49_w14_test_center.md`](./49_w14_test_center.md) — Test Center UI `/test-center/human-lab`
  wyświetla siatkę 8 person z opisami
- [`50_w14_demo_projects.md`](./50_w14_demo_projects.md) — 6 manifestów projektów demo
  wskazuje wymagane persony z tego katalogu
- [`modules/31_d_ladder_complete.md`](./31_d_ladder_complete.md) — D-ladder determinuje
  wymagany poziom gate dla decyzji testowanych przez scenariusze
- [`modules/33_council_hybrid.md`](./33_council_hybrid.md) — scenariusz D5 solo wymaga
  sesji Rady jako blokady; council_session_id referencja w CharterStore.approve()
