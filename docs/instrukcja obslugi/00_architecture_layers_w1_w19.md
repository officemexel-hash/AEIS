# AEIS Architecture Layers W1-W19

Ten rozdział jest kanoniczną mapą warstw architektury AEIS. Fazy 1-41 opisują przebieg pracy operatora, a warstwy W1-W19 opisują subsystemy, które działają pod dashboardem.

Ten plik opisuje **model roboczy operatora** używany przez dashboard `/architecture-layers`. Równolegle istnieje mapa implementacyjna v2 w `00_ARCHITEKTURA_W1_W19.md`, gdzie W1-W19 są nazwane według płaszczyzn runtime repo. Dashboard pokazuje oba ujęcia razem: model roboczy, mapę implementacyjną, Advisor W13 i patche faz z `00_PATCHES_FAZ.md`.

## Podział

```text
W1-W9   fundament systemu
W10-W13 rozumienie projektu, Rada, Source of Truth i Masterplan
W14-W17 jakość, wykonanie, integracje i działania zewnętrzne
W18     stała powierzchnia sterowania operatora
W19     audyt, zamknięcie i uczenie systemu
```

## Warstwy

```text
W1   Canon / Konstytucja systemu
W2   Bootstrap / Instalacja / Workspace
W3   Operator Identity / Uprawnienia / Profil operatora
W4   Provider & Model Catalog
W5   Runtime / Environment / Infrastruktura
W6   Defaults / Autonomia / Polityki systemowe
W7   Guards / Human Gate / Governance
W8   Memory Layer / Pamięć systemu
W9   Skills Layer / Kompetencje systemu
W10  Project Intake / Rozumienie projektu
W11  Model Council / Rada modeli
W12  Source of Truth / Księga
W13  Masterplan / Koordynacja / Plan wykonania
W14  Quality Gates / Testy / Weryfikacja
W15  Ontology / Contracts / Model domenowy
W16  Worker Execution / Artefakty / Build
W17  Integrations / External Actions / Funding / Devices
W18  Operator Console / W18 Terminal
W19  Audit / Closure / Learning / Evolution
```

## Zasady nadrzędne

1. Najpierw prawda, potem realizacja.
2. Najpierw plan, potem wykonanie.
3. Modele proponują, operator zatwierdza.
4. Human Gate obejmuje kierunek, Source of Truth, Masterplan, koszty, produkcję, external actions i final closure.
5. Autonomia jest risk-based, nie task-based.
6. W18 jest stałym cockpittem operatora przez cały projekt.
7. W19 zamyka pętlę przez audit, memory snapshot i lessons learned.

## Domyślne ustawienia kanoniczne

```text
Runtime: local-first
Autonomia: medium
Produkcja: zawsze Human Gate
External upload/submit: zawsze Human Gate
Final action: zawsze Human Gate
Koszt pojedynczej płatnej akcji: approval powyżej ok. 25 EUR
Koszt miesięczny: approval powyżej ok. 100 EUR
VPS workers: approval powyżej ok. 3 workerów
Mobile approval: tylko zbindowane urządzenie, secure token, follow-me off
Memory: similarity search on, zapisy po głównych etapach
Skills: auto-dobór, ryzykowne rozszerzenia przez człowieka
```

## Przykład przepływu

```text
W1   Canon mówi: modele proponują, operator zatwierdza.
W2   Workspace działa lokalnie.
W3   Operator Ylion ma uprawnienia właściciela.
W4   Dostępne są modele lokalne i/lub API.
W5   Runtime ustawiony local-first.
W6   Autonomia ustawiona medium.
W7   Human Gate aktywny dla kierunku, SoT, Masterplanu, kosztów i produkcji.
W8   Memory szuka podobnych projektów operatorskich.
W9   Skills dobierają operator_console, source_of_truth, model_council.
W10  Intake przyjmuje pomysł panelu AEIS.
W11  Rada modeli analizuje i proponuje warianty A/B/C/D/E.
W12  Księga zapisuje wybrany kierunek jako Source of Truth.
W13  Masterplan dzieli projekt na moduły.
W15  Ontology definiuje Project, CouncilSession, HumanGateTicket, SoTEntry.
W16  Workery budują UI, API, testy i dokumentację.
W14  Quality Gates sprawdzają wynik.
W17  External actions są zablokowane, funding/mobile/lab jako future.
W18  Operator prowadzi wszystko przez terminal W18.
W19  Audit i memory zapisują wnioski końcowe.
```

Dashboardowa wersja tej mapy jest dostępna w aplikacji pod `/architecture-layers`, a źródło danych API pod `/api/v1/architecture-layers`.
