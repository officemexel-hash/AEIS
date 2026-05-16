# 03 · S4 SCENARIUSZ — "Multi-platform SaaS z 6 zespołami" (ADAPTIVE TOPOLOGY TEST)

**Data:** 2026-04-24
**Cel:** sprawdzić czy pipeline rozpoznaje projekt wymagający pracy równoległej i dobiera topologię zespołów (A1, A3, A6)

## Idea zgłoszona

"Multi-platform SaaS: iOS (Swift) + Android (Kotlin) + Next.js + FastAPI + PyTorch ML + WebSocket + PostgreSQL + Redis + Kafka. Requires parallel teams: mobile, frontend, backend, ML/data, DevOps, QA. Multi-month project."

**Oczekiwanie wg kanonu:** planner proponuje 6 równoległych zespołów, dobiera skills (mobile-swift, mobile-kotlin, backend-fastapi, ml-pytorch, devops-kafka), wybiera topologię (VPS/hybrid), D3+ classification.

## Wynik (run_id=331e5490bcfc42968b24820d64d45c4f)

- **5 kroków planu** — DRASTYCZNY SPADEK vs S1=6, S2=11, S3=15
- `step_id: "s1".."s5"` — **STRING zamiast INT** (inna struktura niż S1-S3!)
- Kroki: `analyze → design → implement → test → review` — stub template
- Wszystkie kroki wykonane sekwencyjnie, gate=pass
- `artifacts: None`
- 100 sekund na wykonanie (vs S3 ~60s dla 15 kroków)

## 🔴 DRIFT J — Silent fallback na stub planner dla złożonych idei

Dla najbardziej złożonego scenariusza system zwraca NAJUBOŻSZY plan:

| Scenariusz | Złożoność | Kroki planu | Struktura step_id |
|---|---|---|---|
| S1 Hello World | trivial | 6 | int |
| S2 TODO CRUD | simple | 11 | int |
| S3 Auth deploy | medium | 15 | int |
| **S4 Multi-platform SaaS** | **complex** | **5 STUB** | **string** |

**System zachowuje się odwrotnie do oczekiwań.** Prostsze projekty → bogatsze plany. Najtrudniejszy → stub fallback.

**Prawdopodobne root cause:**
- LLM timeout / context overflow z długiej idei
- Silent exception w primary planner → fallback do `planner_stub.py`
- Brak obserwowalności: run ma `status=complete` mimo fallbacku

## 🔴 Zero oznak multi-team / parallel execution

| Oś A | S4 wynik |
|---|---|
| A1 dobór zespołów | Jeden agent sekwencyjnie, `s1→s2→s3→s4→s5` ❌ |
| A2 pamięć podobnych projektów | Brak referencji do S1-S3 ❌ |
| A3 skills | Brak `mobile-swift`, `ml-pytorch`, `kafka-ops`, itd. ❌ |
| A4 reuse | Brak ❌ |
| A5 autonomia | Stała, brak polityk ❌ |
| A6 topologia local/VPS/hybrid | Brak wyboru ❌ |
| A7 Human Gate systemowy | 0/5 kroków ma HG ❌ |

**Dla projektu explicitly "multi-month, 6 parallel teams" — system nie zaproponował ANI JEDNEGO zespołu.**

## LLM znów generuje Python zamiast deliverable

Step s1 ("analyze") zwrócił *"Python script that outlines the requirements... and simulates the analysis of teams, their skills, and tasks"*. Znowu generic code, nie analiza wymagań.

## Compliance 12-HG

5/5 kroków: **0/12 osi**. Scenariusz typu "produkcyjny multi-platform SaaS z Kafka i PII" powinien być ZAWSZE D3+ z wymaganym Human Gate. Runtime: D0 auto-approve.

## Najgroźniejszy wniosek

**System nie tylko ignoruje Human Gate — dla skomplikowanych projektów CAŁKOWICIE SIĘ CHOWA pod template'em stub.** Operator który zaufa `status=complete` nie wie że dostał generic plan typu "analyze/design/implement/test/review" zamiast prawdziwego masterplanu dla 6-zespołowego projektu.

**To jest kłamstwo systemowe** — kontraktowe API deklaruje że dostarczyło plan, runtime dostarczył stub.

## Nowe FIX-y

| ID | Opis | Effort |
|---|---|---|
| FIX-024 | Obserwowalność fallbacku — `plan.source: "llm" \| "stub"` w odpowiedzi | 2h |
| FIX-025 | Dla ideas >N tokenów — automatyczny chunking / multi-pass planner | 8h |
| FIX-026 | Gdy planner wraca <7 kroków dla explicit-multi-domain idei — flag warning | 3h |
| FIX-027 | Team decomposition engine — analizuje idea → proponuje liczbę zespołów | 16h |
| FIX-028 | Parallel execution — kroki bez zależności uruchamiane równolegle | 12h |

## Dalej

S5 — scenariusz wymagający pamięci między projektami (reuse skills z S2/S3). Zobaczymy czy AEIS "pamięta" cokolwiek z poprzednich runów.
