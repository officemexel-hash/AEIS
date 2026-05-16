# 02 · HUMAN GATE — Framework audytu kanonicznego

**Status:** kanoniczny framework potwierdzony przez użytkownika 2026-04-24.
**Użycie:** każdy moduł w ETAP 3 musi być sprawdzony wg tego frameworku.

---

## 5 ról Human Gate w AEIS

1. **Warstwa decyzyjna całego systemu** — centralny mechanizm kontroli ryzyka dla WSZYSTKICH agentów, workerów, Dockerów, VPS-ów, modułów finansowych, prawnych, deploymentowych, browserowych, operatorskich.

2. **Orchestrator przepływu pracy** — decyduje:
   - co idzie automatycznie
   - co zamrozić
   - co oddelegować
   - co zbatchować
   - co wymaga natychmiastowej reakcji operatora

3. **Mechanizm budowania źródła prawdy** — wpisany w fazę idei:
   - modele dyskutują → generują warianty → proponują człowiekowi opcje
   - człowiek zatwierdza kierunek
   - z zatwierdzonych decyzji powstaje source of truth
   - potem masterplan
   - potem realizacja

4. **System polityk autonomii** — **risk-based, nie task-based**:
   - nie każdy krok wymaga człowieka
   - zatwierdza działania zależnie od: ryzyka, kosztu, skutków prawnych, produkcyjnych, bezpieczeństwa, działań zewnętrznych
   - steruje poziomem autonomii systemu

5. **Globalny interfejs operatorski** — Dashboard + Mobile jako **frontend do Human Gate**, nie tylko widok statusu:
   - kolejki decyzji
   - priorytety
   - batch approval
   - delegacja
   - audit trail
   - tokeny approval
   - tryby operatora

---

## Cykl życia decyzji — gdzie Human Gate ma działać

```
idea → dyskusja modeli → wybór wariantu → source of truth → masterplan
→ wybór topologii wykonania (1-model/multi, local/VPS/hybrid) → realizacja
→ testy → działania zewnętrzne → deployment → produkcja → późniejsze zmiany
```

Human Gate jest wpisany w **KAŻDY** z tych etapów, nie tylko na końcu.

---

## Osie konfiguracji (minimum 12 wymiarów)

| # | Oś | Przykładowe wartości |
|---|---|---|
| 1 | Ryzyko | low / medium / high / critical |
| 2 | Typ działania | techniczne / prawne / finansowe / produkcyjne / bezpieczeństwo / komunikacja zewnętrzna / upload zewnętrzny |
| 3 | Środowisko | local / dev / staging / production |
| 4 | Moduł | per-moduł policies |
| 5 | Operator | per-operator policies |
| 6 | Koszt | progi kosztowe |
| 7 | Liczba zasobów | Docker count, VPS count, API usage thresholds |
| 8 | Tryb wykonania | single-model / multi-model / local-only / hybrid / VPS-only |
| 9 | Etap procesu | idea / planning / build / test / deploy / submit / production |
| 10 | Blocking | blocking / non-blocking |
| 11 | Grupowanie | batch / single |
| 12 | Timeout/Eskalacja | timeout rules, escalation chain, delegation rules |

---

## Checklist audytu per moduł (ETAP 3)

Dla KAŻDEGO modułu sprawdzam:

- [ ] **Gdzie generuje decyzje?** (akcje wywołujące Human Gate)
- [ ] **Jakie to decyzje?** (typ z osi 2)
- [ ] **Czy są klasyfikowane?** (ryzyko, typ, pilność)
- [ ] **Czy są blokujące?** (blocking/non-blocking, wpływ na zależne taski)
- [ ] **Czy można je grupować?** (batch approval możliwy?)
- [ ] **Jakie mają progi autoapproval?** (policy engine aktywny?)
- [ ] **Czy mają audit trail?** (kto, kiedy, co, dowody)
- [ ] **Czy mają delegację i eskalację?** (CTO/CFO/prawnik/PM fallback)
- [ ] **Czy system umie pracować dalej poza zależnym fragmentem?** (execution continuity)
- [ ] **Czy operator może to konfigurować?** (polityki per moduł w UI)
- [ ] **Czy decyzja ma timeout?** (co się dzieje po timeout)
- [ ] **Czy decyzja jest podpisywana?** (approval token, signature)

---

## Formularz wyniku audytu (szablon)

Dla każdego modułu w ETAP 3 raport będzie miał strukturę:

```markdown
### Moduł: <nazwa>

**Typy decyzji generowane:** ...
**Klasyfikacja:** YES/NO + dowód
**Blocking vs non-blocking:** ...
**Batch-owalne:** ...
**Autoapproval policy:** ...
**Audit trail:** ...
**Delegacja/Eskalacja:** ...
**Execution continuity:** ...
**Konfigurowalność z UI:** ...
**Timeout rules:** ...
**Approval signature:** ...

**Ocena Human Gate compliance:** GOOD / PARTIAL / MISSING / N/A
**Luki do naprawy:** ...
```

---

## Uwagi wdrożeniowe

- **Risk-based nie task-based** = decyzje są przypisywane do ryzyka, nie do każdego kroku automatycznie
- **Execution Continuity Engine** jest kluczowy — Docker/VPS nie mogą stać bo czekają na Human Gate
- **Dyskusja modeli PRZED pytaniem człowieka** — człowiek dostaje gotowe warianty, nie puste pole
- **Source of truth jest produktem Human Gate**, nie input'em do niego
- **Konfigurowalność per oś** — UI Polityk musi pozwalać ustawić każdą z 12 osi niezależnie
