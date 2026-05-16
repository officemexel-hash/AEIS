# AEIS v6.2.0 — DIAGRAM GANTT I HARMONOGRAM

**Czas całkowity:** 7 tygodni (288h)  
**Zespoły:** 5 agentów równoległych (A/B/K/D/E)  
**Start:** T+0  
**Koniec:** T+49 dni

---

## 1. DIAGRAM GANTT — ASCII

```
AGENT / TYDZIEŃ ->   1        2        3        4        5        6        7
                  [||||||||][||||||||][||||||||][||||||||][||||||||][||||||||][||||||||]

AGENT A (Governance)
  P0-001 Human Gate      [=======]
  P0-003 Memory          [=======]
  P0-008 Model Council   [=======]
  P0-009 Autonomy        [=======]
  P0-010 Gov Ticket      [====]
  P1-005 LLM Quality            [=======]
  P1-010 Council UI                    [====]

AGENT B (Adaptive + Mobile)
  P0-005 Skills Runtime  [==========]
  P0-007 Worker Pool       [======]
  P1-001 Memory Bootstrap       [======]
  P1-002 Mobile Backend              [========]
  P1-003 Mobile Frontend              [======]
  P1-004 Mobile Surface                    [======]
  P2-004 Mobile Runtime                           [========]
  P2-005 Demo Projects                            [======]
  P2-007 Obsidian Memory                               [====]

AGENT K (Surface + Hygiene)
  ZAD-002 Inventory      [====]
  P0-011 Fix CORS          [==]
  P0-012 Fix WS            [==]
  P1-006 Metrics Dedup          [====]
  P1-008 Frontend Mock               [======]
  P1-009 Security Dedup              [====]
  P2-001 Funding Scan                     [========]
  P2-002 Grant Auto                          [========]
  P2-003 Grant Report                             [======]
  P2-006 Agent Theater                              [====]
  P2-008 Polish Loc                                      [====]
  P3-001 Dead Code                                   [========]
  P3-002 Remove Legacy                                   [====]
  P3-003 Funding Polish                                     [======]

AGENT D (Integration)
  ZAD-000 Backup         [==]
  ZAD-001 Setup          [==]
  ZAD-004 CI Setup       [==]
  ZAD-006 DoD            [=]
  ZAD-007 Test Data      [=]
  P3-004 Docs Update                                         [======]
  P3-005 Coverage ≥80%                                       [====]
  P3-006 Security Scan                                       [====]
  S5-001 Staging Deploy                                           [========]
  S5-002 Staging Tests                                            [========]
  S5-003 Perf Test                                                    [====]
  S5-004 Load Test                                                    [====]
  S5-005 DR Test                                                      [====]
  S5-006 Prod Harden                                                  [========]
  S5-007 Production Deploy                                                 [========]
  S5-008 Calibration                                                            [====]

AGENT E (Watchdog)
  ZAD-005 Baseline       [==]
  Daily Cycles           [W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W][W]
```

**Legenda:** `[====]` = aktywność agenta w danym tygodniu | `W` = cykl Watchdog (co 4-6h)

---

## 2. DIAGRAM GANTT — MERMAID

```mermaid
gantt
    title AEIS v6.2.0 — Plan Naprawczy (7 tygodni)
    dateFormat  YYYY-MM-DD
    axisFormat  %d.%m
    todayMarker off

    section FAZA 0
    ZAD-000 Backup              :done, z0, 2026-05-13, 1d
    ZAD-001 Setup 5 agentów     :done, z1, after z0, 1d
    ZAD-002 Inventory scan      :done, z2, after z1, 2d
    ZAD-003 Standup + Ownership :done, z3, after z2, 1d
    ZAD-004 CI Setup            :done, z4, after z1, 1d
    ZAD-005 Watchdog Baseline   :done, z5, after z3, 1d
    ZAD-006 DoD                 :done, z6, after z3, 0.5d
    ZAD-007 Test Data           :done, z7, after z1, 0.5d

    section AGENT A — Governance
    P0-001 Human Gate           :active, a1, 2026-05-13, 2d
    P0-002 Human Gate UI        :active, a2, after a1, 1d
    P0-003 Memory Global        :active, a3, after a1, 2d
    P0-004 Memory UI            :active, a4, after a3, 1d
    P0-008 Model Council        :active, a5, after a4, 2d
    P0-009 Autonomy             :active, a6, after a5, 1.5d
    P0-010 Gov Ticket           :active, a7, after a6, 1d
    P1-005 LLM Quality          :active, a8, after a7, 1.5d
    P1-010 Council Frontend     :active, a9, after a8, 1d

    section AGENT B — Adaptive
    P0-005 Skills Runtime       :active, b1, 2026-05-13, 2.5d
    P0-006 Skills UI            :active, b2, after b1, 1d
    P0-007 Worker Pool          :active, b3, after b2, 1.5d
    P1-001 Memory Bootstrap     :active, b4, after b3, 1.5d
    P1-002 Mobile Backend       :active, b5, after b4, 2d
    P1-003 Mobile Frontend      :active, b6, after b5, 1.5d
    P1-004 Mobile Surface       :active, b7, after b6, 1.5d
    P2-004 Mobile Integration   :active, b8, after b7, 2d
    P2-005 Demo Projects        :active, b9, after b8, 1.5d
    P2-007 Obsidian Memory      :active, b10, after b9, 1d

    section AGENT K — Surface
    P0-011 Fix CORS             :active, k1, 2026-05-15, 1d
    P0-012 Fix WS               :active, k2, after k1, 1d
    P1-006 Metrics Dedup        :active, k3, after k2, 1d
    P1-008 Frontend Mock        :active, k4, after k3, 1.5d
    P1-009 Security Dedup       :active, k5, after k4, 1d
    P2-001 Funding Scan         :active, k6, after k5, 2d
    P2-002 Grant Auto           :active, k7, after k6, 2d
    P2-003 Grant Report         :active, k8, after k7, 1.5d
    P2-006 Agent Theater        :active, k9, after k8, 1d
    P2-008 Polish Loc           :active, k10, after k9, 1d
    P3-001 Dead Code            :active, k11, after k10, 2d
    P3-002 Remove Legacy        :active, k12, after k11, 1d
    P3-003 Funding Polish       :active, k13, after k12, 1.5d

    section AGENT D — Integration
    P3-004 Docs Update          :active, d1, 2026-06-02, 1.5d
    P3-005 Coverage ≥80%        :active, d2, after d1, 1d
    P3-006 Security Scan        :active, d3, after d2, 1d
    S5-001 Staging Deploy       :active, d4, after d3, 2d
    S5-002 Staging Tests        :active, d5, after d4, 2d
    S5-003 Perf Test            :active, d6, after d5, 1d
    S5-004 Load Test            :active, d7, after d6, 1d
    S5-005 DR Test              :active, d8, after d7, 1d
    S5-006 Prod Hardening       :active, d9, after d8, 2d
    S5-007 Production Deploy    :active, d10, after d9, 2d
    S5-008 Calibration          :active, d11, after d10, 1d

    section FAZA 5 — Milestones
    P0 CLEAR                    :milestone, m1, 2026-05-27, 0d
    STAGING LIVE                :milestone, m2, 2026-06-10, 0d
    PRODUCTION LIVE             :milestone, m3, 2026-06-24, 0d
    PROJECT COMPLETE            :milestone, m4, 2026-06-26, 0d
```

---

## 3. HARMONOGRAM TYGODNIOWY

| Tydzień | Od | Do | Faza | Zespoły | Kluczowe cele |
|---------|-----|-----|------|---------|---------------|
| **1** | 13.05 | 19.05 | F0 + P0 start | D, K, A | Backup, setup 5 agentów, inventory, Human Gate start |
| **2** | 20.05 | 26.05 | P0 Blockers | A, B | Memory, Skills, Worker pool, Council — **P0 CLEAR** |
| **3** | 27.05 | 02.06 | P0 finisz + P1 | A, B, K | Autonomy, Gov ticket, Mobile backend, Metrics dedup |
| **4** | 03.06 | 09.06 | P1 + P2 | B, K | Mobile frontend, Decomposition, Funding scan, Agent Theater |
| **5** | 10.06 | 16.06 | P2 + P3 | K, B | Polish loc, Demo projects, Dead code, Remove legacy |
| **6** | 17.06 | 23.06 | P3 + Staging | K, D | Docs, coverage ≥80%, security scan, **STAGING LIVE** |
| **7** | 24.06 | 30.06 | Production | D, E | Load test, DR test, hardening, canary, **PRODUCTION LIVE** |

---

## 4. KRZYŻOWANIE ZALEŻNOŚCI

```
P0-001 (Human Gate) ───┬───> P0-002 (HG UI)
                       ├───> P0-010 (Gov Ticket)
                       └───> P1-002 (Mobile Backend)

P0-003 (Memory) ───────┬───> P0-004 (Memory UI)
                       ├───> P1-001 (Memory Bootstrap)
                       └───> P0-009 (Autonomy)

P0-005 (Skills) ───────┬───> P0-006 (Skills UI)
                       └───> P1-007 (Decomposition)

P0-008 (Council) ──────┬───> P0-009 (Autonomy)
                       └───> P1-010 (Council UI)

P1-002 (Mobile BE) ────┬───> P1-003 (Mobile FE)
                       └───> P1-004 (Mobile Surface)
                       └───> P2-004 (Mobile Runtime)

P0-011 (CORS) ─────────> P1-008 (Frontend Mock)
P0-012 (WS) ───────────> P1-008 (Frontend Mock)

P2-001 (Funding) ──────> P2-002 (Grant Auto)
P2-002 (Grant Auto) ───> P2-003 (Grant Report)

P3-001 (Dead Code) ────> P3-002 (Remove Legacy)
P3-002 (Legacy) ───────> P3-004 (Docs)

S5-001 (Staging) ──────┬───> S5-002 (Staging Tests)
S5-002 (Tests) ────────┬───> S5-003 (Perf)
                       ├───> S5-004 (Load)
                       ├───> S5-005 (DR)
                       └───> S5-006 (Hardening)
S5-006 (Harden) ───────> S5-007 (Production)
S5-007 (Prod) ─────────> S5-008 (Calibration)
```

---

## 5. MAPA CIEPLNA — OBCIĄŻENIE AGENTÓW

```
         Tydzień 1    Tydzień 2    Tydzień 3    Tydzień 4    Tydzień 5    Tydzień 6    Tydzień 7
         ████████     ████████     ████████     ████████     ████████     ████████     ████████

AGENT A  ████████     ██████████   ████████     ████         ░░░░░░░░     ░░░░░░░░     ░░░░░░░░
         F0+P0        P0           P0+P1        P1           idle         idle         standby

AGENT B  ████████     ████████     ████████     ██████████   ████████     ░░░░░░░░     ░░░░░░░░
         F0+P0        P0           P0+P1        P1+P2        P2           idle         standby

AGENT K  ████████     ████████     ████████     ████████     ██████████   ████████     ░░░░░░░░
         F0+P0        P0           P1           P1+P2        P2+P3        P3           standby

AGENT D  ██████████   ░░░░░░░░     ░░░░░░░░     ░░░░░░░░     ░░░░░░░░     ████████     ██████████
         F0 setup     idle         idle         idle         idle         P3+Staging   Production

AGENT E  ██           ██           ██           ██           ██           ██           ██
         Watchdog     Watchdog     Watchdog     Watchdog     Watchdog     Watchdog     Watchdog

Legenda: ████ = praca  |  ░░░░ = idle/standby  |  ██ = Watchdog cycle (4-6h)
```

---

## 6. TIMELINE — MILESTONES

```
T+0  (13.05)  ████ START — Faza 0: Backup, Setup, Inventory
T+7  (20.05)  ████ Milestone: Faza 0 Complete
              ████ P0 START — Human Gate, Memory, Skills, Worker Pool

T+14 (27.05)  ████ Milestone: P0 CLEAR — 8/8 blockers naprawionych
              ████ P1 START — Mobile, Decomposition, Council, Frontend

T+21 (03.06)  ████ P2 START — Funding scan, Agent Theater, Demo projects

T+28 (10.06)  ████ P3 START — Cleanup, docs, tests, security scan

T+35 (17.06)  ████ Milestone: STAGING LIVE
              ████ S5 START — Load test, DR, hardening

T+42 (24.06)  ████ Milestone: PRODUCTION LIVE — Canary deploy
              ████ 24h observation period

T+49 (01.07)  ████ Milestone: PROJECT COMPLETE
              ████ Calibration, handoff, warranty start
```

---

*Generated 2026-05-12 | AEIS v6.2.0 Repair Plan | Kimi Code CLI*
