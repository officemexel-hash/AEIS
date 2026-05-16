# AEIS CANON VS REALITY

**Data:** 2026-04-24
**Zakres:** Book v3.5 + Extended Model (adaptive multi-team learning) vs runtime 2026-04-24

## Matryca zgodności

### Warstwy (9 vs 9)

| Warstwa | Kanon spec | Reality | Zgodność |
|---|---|---|---|
| Canon (L0) | 6 modułów + 119 manifestów ładowanych | Moduły OK, **manifesty nie ładowane** | PARTIAL |
| Memory (L2) | Rdzeń — project/ops/config/effectiveness/similarity | 18 modułów istnieje, **0 funkcjonalnej pamięci** w runtime | STUB |
| Skills | Katalog kompetencji + auto-dobór + reuse | **Brak warstwy w runtime** | MISSING |
| Planning (L3) | Adaptive, dobiera topologię i skills | Stały szablon 5-15 kroków LLM, **silent fallback** | PARTIAL |
| Coordination | Orkiestracja zespołów + kolejek + HG | 1 sekwencyjny agent, zero HG | STUB |
| Worker (L4) | Zespoły wykonawcze + skills | 1 generic generator, `execution_guard: OFF` | STUB |
| Integration | gRPC + proto + device + VPS | 2× proto generations (kanon vs legacy), LAB działa | PARTIAL |
| Governance (L6) | Approval + policies + limits + RBAC | 7.1/12 avg, moduły istnieją ale rozłączone | PARTIAL |
| Operator Console (L8) | Dashboard + decyzje + monitoring + mobile | 1.67/12 avg, STUB, 0 mobile | STUB |

### Human Gate 12 osi

| Oś | Kanon | Runtime (best module) | Runtime (pipeline integration) |
|---|---|---|---|
| Q1 risk_level | risk-based classification | human_gate module 10.5/12 | **0% — classifier zawsze D0** |
| Q2 reversibility | checked per decyzja | evidence_spine 11/12 | **0% — niewołane** |
| Q3 blast_radius | assessed | policy_engine 5/12 | **impact_radius=local zawsze** |
| Q4 data_sensitivity | classified | policy_engine | **0% — brak classifier** |
| Q5 compliance | policy check | policy_engine partial | **0% — nie wpięty w pipeline** |
| Q6 cost | evaluated | **BRAK — wszystkie 0** | **0%** |
| Q7 time_sensitivity | tracked | kilka modułów partial | **0%** |
| Q8 autonomy_level | 0-5 respected | autonomy_stages istnieje | **0% — nieegzekwowane** |
| Q9 evidence_required | collected | evidence_spine 11/12 | **0% — wpisywane po execute** |
| Q10 approval_quorum | enforced | council_workflow 10/12 | **0% — nie wymagane** |
| Q11 escalation_path | defined | human_gate module | **0%** |
| Q12 override_policy | audited | evidence_signer | **0%** |

**System-wide pipeline integration: 0/12 osi.**

### Extended Model A1-A7

| Oś | Kanon | Reality |
|---|---|---|
| A1 dobór zespołów | Dynamiczny per projekt | 1 agent zawsze |
| A2 pamięć podobnych | Similarity search z reuse | `/memory/search` 404 |
| A3 skills | Katalog + auto-match | Brak warstwy |
| A4 reuse | Historyczne konfiguracje | 0% |
| A5 autonomia sterowana | Limits + policies | Stała |
| A6 topologia | local/VPS/hybrid | Brak wyboru |
| A7 HG systemowy | Per decyzja w całym flow | HG w izolacji |

**Extended model pokrycie: 0/7.**

## Gdzie kanon JEST wdrożony (mimo drifts)

| Obszar | Status |
|---|---|
| Core evidence spine (11/12 HG na poziomie modułu) | ✅ |
| Human Gate module (10.5/12 modułowo) | ✅ (ale w izolacji) |
| Council workflow (10/12) | ✅ |
| Decision ladder (9/12) | ✅ |
| Decision snapshot (9/12) | ✅ |
| Manifest definitions (119 na dysku) | ✅ (nie ładowane) |
| Proto generations (kanon + legacy) | ✅ (migracja w planie) |
| Multi-phase architecture (9 warstw istnieje) | ✅ (rozłączone) |

**System ma dobre cegły, ale nie ma zaprawy.** Pipeline jako "zaprawa" musi łączyć L3-L8 przez decision_gate→human_gate→evidence_spine → dziś nie łączy.

## Top 3 decyzje nie-zgodne z kanonem

### 1. Pipeline skipuje D-ladder
Kanon: każdy krok klasyfikowany, D3+ blokowany.
Reality: wszystko D0 auto-approve.
**Impact:** cały model governance Book v3.5 nie działa w runtime.

### 2. Memory nie jest rdzeniem
Kanon Extended Model: Memory to 2. warstwa rdzenia.
Reality: 18 modułów memory, ale `/memory/search` 404, zero użycia.
**Impact:** AEIS nie jest "uczący się" wbrew deklaracji.

### 3. Skills nie istnieją jako warstwa
Kanon Extended Model: Skills to 3. warstwa rdzenia (katalog kompetencji).
Reality: pojęcie skills nie ma odzwierciedlenia w manifestach ani runtime.
**Impact:** każdy run startuje od zera, brak transferu kompetencji.

## Ścieżka konwergencji

Patrz [AEIS_REPAIR_BACKLOG.md](AEIS_REPAIR_BACKLOG.md) — 4 sprinty, 232h.

Po Sprint 4: **7/7 A + 12/12 HG**. Runtime zbliża się do kanonu.

Przed Sprint 1: **0/7 A + 0/12 HG**. Kanon istnieje wyłącznie w dokumentach.
