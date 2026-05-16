# 02 · AEIS — Uściślony model adaptacyjnego systemu wielozespołowego

**Data:** 2026-04-24
**Źródło:** uściślenie operatora (kontekst audytu ETAP 3+)

## TL;DR

AEIS to **uczący się system kontrolowanej autonomii**, który na podstawie pamięci, skills i analizy projektu sam dobiera liczbę zespołów agentów, topologię wykonania i workflow. Człowiek steruje kierunkiem i ryzykiem przez Human Gate.

To NIE jest orkiestrator pojedynczych agentów. To system organizujący pracę agentów, pamięci, skills, środowisk i człowieka.

## 1. Dynamiczne dobieranie liczby zespołów

Planning + Coordination musi oceniać projekt pod kątem:
- złożoności, liczby domen, ryzyka, wymagań technicznych
- wymagań UI/API/dokumentacyjnych, potrzeby pracy równoległej
- konieczności urządzeń/browserów/VPS/kontenerów
- potrzeby Human Gate na różnych etapach

Propozycja topologii:
- 1 agent prowadzący
- 2-3 wyspecjalizowane zespoły
- pełny podział (planning / wykonanie / testy / docs / security / deploy)
- wiele środowisk równolegle
- local / hybrid / VPS-only

## 2. Zespół zamiast pojedynczego agenta

Typy zespołów:
- **Deliberacyjny** — warianty, analiza, kontrargumenty
- **Architektoniczny** — source of truth, masterplan, podział modułów
- **Wykonawczy** — kod, integracje, build
- **Walidacyjny** — testy techniczne + "jak człowiek", browser, urządzenia
- **Operatorski** — deployment, runtime, monitoring, rollback
- **Dokumentacyjny** — dokumentacja bieżąca i końcowa

## 3. Sterowana autonomia

Realna autonomia w ramach:
- polityk autonomii, limitów kosztowych, limitów ryzyka
- ograniczeń środowiskowych, reguł Human Gate

## 4. Pamięć jako RDZEŃ (nie dodatek)

- **Projektowa** — cele, decyzje, source of truth, masterplany, odrzucone warianty
- **Operacyjna** — co zrobione, co działa, co się wywaliło, approvale
- **Konfiguracji** — autonomia, liczba zespołów, modele, środowiska, workflow
- **Skuteczności** — które skills/agenci/topologie działały dla typów projektów
- **Podobieństwa** — similarity search poprzednich projektów
- **Decyzji człowieka** — preferencje operatora, próg Human Gate

## 5. Skills jako system kompetencji

Nie "prompt helper", lecz jednostki wiedzy operacyjnej:
- procedury wykonania, reguły jakości, wzorce implementacyjne
- gotowe workflow, reguły walidacji, logika domenowa/narzędziowa

Mechanika:
- wykrywanie potrzebnych skills
- auto-dobór + łączenie w workflow
- ocena skuteczności + zapis w pamięci
- reuse dla podobnych projektów

## 6. 9-warstwowy model architektury (po korekcie)

| Layer | Rola |
|---|---|
| Canon | zasady, polityki, Human Gate |
| **Memory** | projektów/decyzji/skuteczności/podobieństw/preferencji/skills-history |
| **Skills** | katalog kompetencji, workflow, wzorców |
| Planning | analiza projektu, deliberacja, source of truth, dobór zespołów/skills/topologii |
| Coordination | orkiestracja zespołów, kolejek, zależności, Human Gate |
| Worker | agenci i zespoły wykonawcze |
| Integration | API/UI/proto/urządzenia/browser/VPS/Docker |
| Governance | approvale, polityki autonomii, limity, audyt, RBAC, zgodność |
| Operator | dashboard, decyzje, monitoring, konfiguracja, mobile |

## 7. Idealny flow

1. Człowiek wnosi ideę
2. AEIS → analiza + deliberacja modeli
3. AEIS → porównanie z pamięcią podobnych
4. AEIS → dobór wstępnych skills + sugestia topologii
5. **Human Gate** — zatwierdzenie kierunku
6. AEIS → source of truth
7. AEIS → masterplan (liczba zespołów, modele, środowiska, skills, autonomia, local/VPS/hybrid)
8. **Human Gate** — zatwierdzenie planu
9. AEIS realizuje, dynamicznie dobiera skale + skills
10. Human Gate tylko na decyzje ryzykowne/przekraczające polityki
11. Zapis skuteczności + preferencji do pamięci
12. Następny podobny projekt startuje z doświadczeniem

## 8. Rozszerzony checklist audytu

Oprócz 12 pytań Human Gate, per moduł / per warstwa:

- **A1:** Mechanizm doboru liczby zespołów/agentów per projekt?
- **A2:** Pamięć podobnych projektów (similarity search)?
- **A3:** Katalog skills + mechanizm wyboru?
- **A4:** Reuse skutecznych konfiguracji?
- **A5:** Autonomia sterowana politykami (nie flaga)?
- **A6:** Planning uwzględnia skalę projektu?
- **A7:** Human Gate systemowy (nie punktowy)?

## 9. Konsekwencje dla audytu

S1 smoke test już pokazał: pipeline.execute wykonuje **stały schemat 6 kroków** niezależnie od projektu. To oznacza że AEIS dziś:
- NIE dobiera liczby zespołów
- NIE używa pamięci podobnych projektów
- NIE dobiera skills
- NIE proponuje topologii

To drugi (obok braku Human Gate) fundamentalny drift vs kanon. Audyt warstw L0-L8 musi to udokumentować per moduł.
