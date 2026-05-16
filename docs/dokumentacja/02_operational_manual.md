# Operational Manual — codzienna praca z SYLION AEIS

> Praktyczny przewodnik operatora. Co kliknąć, kiedy, dlaczego.
> Wersja: 2026-04-26.

## Spis treści

- [1. Pierwsze uruchomienie — Onboarding Wizard (10 kroków)](#1-pierwsze-uruchomienie--onboarding-wizard-10-kroków)
- [2. Codzienny workflow](#2-codzienny-workflow)
- [3. Konfiguracja i preferencje](#3-konfiguracja-i-preferencje)
- [4. Funding Advisor — opt-in](#4-funding-advisor--opt-in)
- [5. Decyzje D3+ i Evidence Pack](#5-decyzje-d3-i-evidence-pack)
- [6. Council Hybrid — kiedy i jak](#6-council-hybrid--kiedy-i-jak)
- [7. Mobile (Etap 2 preview)](#7-mobile-etap-2-preview)
- [8. Switch to Technical Mode](#8-switch-to-technical-mode)
- [9. Pricing + budget](#9-pricing--budget)
- [10. Rozwiązywanie problemów](#10-rozwiązywanie-problemów)

---

## 1. Pierwsze uruchomienie — Onboarding Wizard (10 kroków)

### Co

Wizard prowadzi przez konfigurację bazową. Można skipnąć w dowolnym kroku — system wyświetli
trwały banner *"incomplete setup"* aż do uzupełnienia.

### 10 kroków

| # | Krok | Co konfigurujemy | Można skip? |
|---|---|---|---|
| 1 | Identyfikacja operatora | imię, rola, kontakt | nie |
| 2 | Lokalizacja + język | kraj, województwo (PL), język UI | tak |
| 3 | Risk profile | risk tolerance: conservative / balanced / aggressive | tak (default: balanced) |
| 4 | Cost ceilings | per risk level (low/med/high/critical/funding) | tak (defaults z W11) |
| 5 | Autonomy level | manual / suggest / auto | tak (default: suggest) |
| 6 | LLM providers | wybór + API keys (Anthropic, OpenAI, Google, Ollama) | nie (min 1) |
| 7 | LLM pool routing | który model do której roli (planner/critic/governance) | tak (defaults) |
| 8 | Notifications | Slack / email / FCM (mobile) — channels i rules | tak |
| 9 | Funding subsystem | enable/disable + per-country settings | tak (default: OFF) |
| 10 | Project domains | wybór z 14 base + opcjonalne custom | tak (defaults: all 14) |

### Po onboardingu

- Operator ląduje na **Project Lifecycle Dashboard** (primary entry point).
- Wszystkie pozostałe surface dostępne w nawigacji bocznej.
- "Switch to Technical Mode" widoczny jako link w nav (zawsze dostępny).

---

## 2. Codzienny workflow

### Live Feed (toast/modal hybrid)

Operator pracuje na 2 płaszczyznach:
1. **Aktywne klikanie** w dashboardach.
2. **Reakcja na Live Feed** — advisor podpowiada w tle.

#### Anatomia karty (AdvisorCard)

```
┌──────────────────────────────────────────────────────────┐
│  [risk: high]  [D-level: D3]  [confidence: 0.82]         │
│  ──────────────────────────────────────────────────────  │
│  REC_TYPE_VPS_SCALING                                    │
│                                                          │
│  RATIONALE:                                              │
│   Plan przekracza 1000 LoC i 8h estimated. Local FE+BE   │
│   nie wystarczy — sugeruję local + 1 VPS dla critic+test │
│   bundle. Rationale: ...                                  │
│                                                          │
│  TRADE-OFF:                                              │
│   +$45/mies VPS  vs  -2h execution time per project       │
│                                                          │
│  RISK:                                                   │
│   VPS provider downtime (~99.5% SLA). Mitigation: ...    │
│                                                          │
│  Akcje:                                                  │
│  [Accept] [Reject] [Modify] [Remind] [Not useful]        │
│  [Convert→HG] [Convert→Masterplan]                       │
│                                                          │
│  [ ] Don't learn from this decision                      │
└──────────────────────────────────────────────────────────┘
```

#### Reguły wyświetlania

| risk_level | Sposób | Auto-dismiss |
|---|---|---|
| `low` | toast | 5s |
| `medium` | toast persistent | manual |
| `high` | modal non-blocking | manual |
| `critical` | modal blocking | wymaga akcji |

Max 3 widoczne karty + counter `+N more` → klik otwiera Live Feed sidebar.

### Project Lifecycle Dashboard

**Co**: Primary entry point. Wizualizacja 16 hooks per aktywny projekt.

**Layout**:
```
┌──────────────────── PROJECT: my-research-app ────────────────────┐
│ Phase: drafting (faza 7/15)                                      │
│                                                                  │
│  ●───●───●───●───●───●───○───○───○───○───○───○───○───○───○      │
│ H01 H02 H03 H04 H05 H06 H07 H08 H09 H10 H11 H12 H13 H14 H15      │
│                                                                  │
│  Active cards: 2 (1 high, 1 medium)                              │
│  Last action: 12 min temu — accepted SoT model selection         │
│  Estimated cost so far: $2.40 / budget $25.00                   │
│                                                                  │
│  [View masterplan] [View SoT] [View history] [Switch to tech]    │
└──────────────────────────────────────────────────────────────────┘
```

### Monitoring Dashboard

**Co**: Multi-project matrix.

| Project | Phase | Risk | Cost (used/budget) | Active cards | Last activity |
|---|---|---|---|---|---|
| my-research-app | drafting | medium | $2.40/$25 | 2 | 12m |
| internal-tool-x | execution | low | $8.10/$50 | 0 | 1h |
| audit-q2-2026 | testing | high | $14.20/$30 | 3 | 5m |

Sortowalne po każdej kolumnie. Filtry: risk, phase, owner, domain.

### Codzienna kolejność (suggested)

1. Sprawdź Monitoring Dashboard — czy są red flagi.
2. Otwórz Live Feed — przejrzyj zaległe karty (oldest first).
3. Wejdź w aktywne projekty po kolei (Project Lifecycle Dashboard).
4. Reaguj na critical/high modal blocking gdy się pojawiają.
5. Batch low-risk HG tickets (advisor sugeruje gdy `pending_count` rośnie).

---

## 3. Konfiguracja i preferencje

### Settings page

Layout 3D matrix preferencji:

```
Filtry: [Project Type ▼] [Project Domain ▼]   →  pokazuje preferencje na tym poziomie

Preferencje:
  ┌─────────────────────────────────────────────────┐
  │ autonomy_level         [suggest ▼]    HARD      │
  │ runtime_strategy       [hybrid ▼]      HARD      │
  │ trusted_providers      [anthropic, openai] HARD  │
  │ blocked_providers      [—]             HARD      │
  │ preferred_council_size [3]            soft      │
  │ card_visibility_threshold [confidence>0.5] soft │
  │ funding_advisor_enabled [OFF]         HARD      │
  └─────────────────────────────────────────────────┘
```

### 4-level cascade — przykład

Operator ustawia `preferred_council_size = 5` na poziomie `(user, type=research, domain=funding)`.

Resolution dla różnych kontekstów:
```
(user, type=research, domain=funding) → 5    ← Level 1 hit
(user, type=research, domain=software) → fallback do Level 2/3/4 → użyje per-user lub system default
(user, type=production_app, domain=funding) → fallback (Level 1 miss, Level 3 może mieć)
```

### Soft preference learning

Działa AUTOMATYCZNIE, bez zgody operatora:
- Operator akceptuje 5x z rzędu kartę z `council_size=3` → soft preference auto-update.
- Operator odrzuca 3x z rzędu kartę typu `REC_TYPE_PURCHASE_PLAN` → reduced surfacing dla tego typu.

Zobacz historię w `Settings → Learning History`.

### Hard preference change

Próba zmiany hard preference → wymaga 2 kliknięć:
1. Klik na zmianę (np. `autonomy_level: suggest → auto`).
2. Modal: *"To jest hard preference. Confirm?"* + podpis operatora (timestamp + user_id).

Audit trail w `advisor_preferences.preferences_audit` (forever retention).

---

## 4. Funding Advisor — opt-in

### Włączenie

`Settings → Funding subsystem → Enable`. To jest **hard preference** — wymaga confirmation.

Po włączeniu:
1. Wybór kraju (PL z województwami / EU z państwami członkowskimi / US states / globally).
2. Profil firmy: NIP, KRS, formy prawne, lokalizacja, branża, wielkość.
3. Token budget separate (default $20/mies, configurable).
4. Per-grant scoring profiles auto-loaded (PARP, FENG, Horizon Europe, ...).

### Stan runtime po R3.14

Aktywny workflow operatora jest w `/funding` i dziala w unified backendzie `sylion.api.app:app`.

| Obszar | Co robi operator |
|---|---|
| Firma | uzupelnia profil, KRS/RDF, dokumenty i readiness |
| Nabory | przeglada zrodla, dodaje programy i uruchamia scan |
| Pomysly | generuje idee i konwertuje je do projektow z Human Gate |
| Dopasowanie | uruchamia matching, scoring, konsorcjum i outreach |
| Wnioski | tworzy, przeglada i eksportuje pakiety aplikacji |
| Zlozenie i CRM | przygotowuje submission, prosi o zatwierdzenie i zapisuje finalna referencje |
| Raporty | oglada wykresy pipeline/success/ROI, eksportuje CSV/PDF/XLSX i tworzy szkice e-mail |

Eksport raportow:

- `CSV pipeline` jest generowany w przegladarce z aktualnie zaladowanych danych.
- `PDF wniosku` i `XLSX budzetu` sa pobierane z backendu przez `GET /api/v1/funding/application/{application_id}/export/{artifact_type}`.
- Backend generuje XLSX deterministycznie takze bez `openpyxl`.
- Powiadomienia e-mail sa szkicami `mailto`; automatyczna wysylka nie jest jeszcze wdrozona.

### Workflow

```
┌─ Idea created ─┐
       ↓
┌─ Advisor: "Potencjał dotacyjny?" ─┐  (hook H04, jeśli funding enabled)
       ↓
┌─ Operator: yes ─┐
       ↓
┌─ Funding scanning: PARP / FENG / Horizon / regional ─┐
       ↓
┌─ Per-grant scoring (effective_score = profile.apply(...)) ─┐
       ↓
┌─ Top-3 grants surfaced jako FundingCard ─┐
       ↓
┌─ Operator: review → "Co potrzebne by qualified?" ─┐  (FUNDING_HOW_TO_QUALIFY, D1)
       ↓
┌─ Gap analysis: brakuje X, Y, Z ─┐
       ↓
┌─ FundingCard suggestions:
     - FUNDING_FORM_COMPANY (D3, Light Evidence Pack required)
     - FUNDING_FIND_CONSORTIUM (D2)
     - FUNDING_REGIONAL_RELOCATION (D3, Light Evidence Pack)
     - FUNDING_ADJUST_IDEA_FOR_GRANT (D2/D3)
       ↓
┌─ Operator decision (HG dla D3+) ─┐
       ↓
┌─ Document package generation ─┐
       ↓
┌─ Browser submission (HG required, external-action) ─┐
       ↓
┌─ Post-grant monitoring (deadlines, milestones) ─┐
```

### 3-mode simulator

`Funding → Simulator`:

| Mode | Co robi |
|---|---|
| **Single-grant** | What-if dla 1 grantu. Zmiana parametru → zmiana score. |
| **Multi-grant comparison** | N grantów obok siebie, ranking po effective_score. |
| **Consortium impact** | Dodaj/usuń członka konsorcjum → wpływ na score per grant. |

### Per-grant scoring profile (kluczowe)

Ten sam company + ta sama idea → różne granty produkują różne score:
```
PARP            → użyje (eligibility, thematic_alignment, capacity, regional_fit)
FENG            → użyje (thematic_alignment, competitive_position, consortium_readiness)
Horizon Europe  → użyje (eligibility, competitive_position, consortium_readiness, timeline_fit)
```

Każdy z własnymi wagami i hard floors.

### Funding Card actions

Domyślne akcje + funding-specific:
- `Generate document package` — auto-generuj wymagane dokumenty (CV, opis, budget).
- `Find consortium partners` — z internal directory + external scraping.
- `Adjust idea` → konwersja do ChangeProposal SoT.

---

## 5. Decyzje D3+ i Evidence Pack

### Kiedy Evidence Pack jest wymagany

| Sytuacja | Template |
|---|---|
| `d_level == D5` (zawsze) | **D5 Full** |
| `d_level == D4` | **D5 Full** |
| Cost/subscription rec @ D3 | **D3 Light** |
| Funding `FORM_COMPANY` / `CHANGE_LEGAL_FORM` / `REGIONAL_RELOCATION` | **D3 Light** |
| Production deploy override | **D5 Full** |

### Flow finalizacji D3 Light

```
1. Engine wykrywa: D-level >= D3 + cost-related → tworzy Evidence Pack draft
2. LLM-judge wypełnia draft:
   - rationale (200-800 słów)
   - rollback_plan (100-400 słów)
   - fidelity_test (50-200 słów)
3. Karta surface'uje się w Live Feed z badge "Evidence Pack draft"
4. Operator klika [Accept] → Modal otwiera Evidence Pack:
   - Może edytować draft (autosave)
   - Musi potwierdzić każdą sekcję (checkboxes)
   - Podpis: confirm + timestamp + user_id
5. Po podpisaniu: status='finalized', karta wykonana
```

### Flow finalizacji D5 Full

Wszystko z D3 Light + dodatkowo:
1. **Risk analysis** — identified_risks + worst_case_scenario.
2. **Simulation results** — score impact across N scenarios.
3. **Council vote** required (z weighted vote + critic gate).
4. **Sentinel signoff** — cost_sentinel + security_sentinel.
5. **≥2 podpisy** (operator + jeden z Council).
6. Multi-signature dla deployment override.

### Hard preferences wymagające operator click

Próba zmiany przez advisor / soft learning → MODAL:
- `autonomy_level`
- `runtime_strategy`
- `approval_timeout_behavior`
- `trusted_providers`
- `blocked_providers`
- `funding_advisor_enabled`
- `meta_recommendations_enabled`

Click required — bez click change nie zostaje zapisana.

### Sentinel signoffs

Dwóch sentineli ma prawo zablokować D4+:
- **cost_sentinel** — sprawdza czy cost impact jest acceptable
- **security_sentinel** — sprawdza czy nie ma security implications

Sentinel block w `consensus.sentinel_blocks` → consolidation gated, operator widzi reason.

---

## 6. Council Hybrid — kiedy i jak

### Kiedy się angażuje

- **D2+ decyzje** — operator może requestować formację rady (opcjonalne).
- **D4+ decyzje** — Council vote wymagany (mandatory).
- **D5 decyzje** — Council vote + critic + sentinele (multi-sig).

### Tworzenie sesji

```
1. Operator klika [Form Council] na karcie/decyzji
2. Wybiera proposed_council_size (default z preferences: preferred_council_size)
3. System auto-suggests roles based on decision type:
   - software project → planner + architect + critic + verifier
   - funding decision → planner + funding_specialist + critic + governance
   - production deploy → planner + verifier + critic + cost_sentinel + security_sentinel
4. Operator może override (POST /sessions/{sid}/participants)
5. Każdy uczestnik ma rangę (primary/senior/support/...)
```

### Weighted vote

```
voting_weight = DEFAULT_ROLE_WEIGHTS[role] × RANK_MULTIPLIER[rank]
```

| Role | Default weight | Najsensowniejsza ranga |
|---|---|---|
| critic | 1.0 | primary |
| planner | 1.0 | primary/senior |
| architect | 0.9 | senior |
| verifier | 0.9 | senior |
| governance | 0.8 | senior |
| cost_sentinel | 0.7 | support |
| security_sentinel | 0.7 | support |
| domain_specialist | 0.6 | support |
| funding_specialist | 0.6 | support |

### Critic gate (mandatory dla D4+)

Bez przynajmniej 1 podpisu od `role=critic` → consolidation jest **blocked**.

`record_critic_signature(session_id, model_id)` — model musi być uczestnikiem
w `role='critic'`. Inaczej `ValueError`.

### Atomic gated consolidation

```python
council.consolidate_with_signatures(
    text=consensus_text,
    require_critic=True,
    require_sentinels_pass=True
)
```

Egzekwuje OBA gate'y atomowo. Bez tego — legacy `set_consolidated()` istnieje dla back-compat
ale NIE używaj w nowych przepływach.

---

## 7. Mobile (Etap 2 preview)

### Status

Etap 1: tylko REST gateway (`mobile_gateway`) jest gotowy. Brak rzeczywistej app.
Etap 2: Android Kotlin Multiplatform.
Etap 3: iOS via SwiftUI/KMP.

### Pairing (Etap 2)

```
1. Web: Settings → Mobile → "Pair new device"
2. Web pokazuje QR code (one-time pairing token, TTL 5 min)
3. Mobile app skanuje QR → token wymienia na device-bound JWT
4. JWT przechowywany w Android Keystore (hardware-backed)
5. Każde request mobile → JWT w Authorization header → mobile_gateway weryfikuje
```

### Biometric step-up

Dla D3+ akcji z mobile:
```
Operator klika [Accept] na D3+ karcie
        ↓
BiometricPrompt: "Confirm with fingerprint/face"
        ↓
Po sukces → mobile_gateway dostaje signed_step_up_token (krótki TTL ~2 min)
        ↓
Akcja wykonana
```

### Offline mode

Read-only cache:
- Last 50 cards (newest first)
- 10 active projects (Last activity)
- Human Gate pending (wszystkie operatora)
- 30 funding deadlines (najbliższe)
- Settings snapshot

**No write queue** — wszystkie write operations wymagają online. Próba write offline →
banner "You're offline — action will be lost".

### Follow-me mode (default OFF)

Gdy ON, każda zmiana focus na desktop dashboard → push notification na mobile z
context preview. Operator może świadomie włączyć (hard preference, audit trail).

---

## 8. Switch to Technical Mode

### Co to robi

Przełączenie z guided UX na **legacy technical dashboards**. Cel: power-user tooling +
debugging.

### Kiedy używać

- Gdy potrzebujesz drill-down do konkretnego endpointu / modułu.
- Gdy debug'ujesz konfigurację (np. dlaczego dana karta NIE wystrzeliła).
- Gdy oglądasz raw event log / audit chain / hash chain.
- Gdy operator jest zaawansowany i guided UX go spowalnia.

### Co dostajesz w Technical Mode

| Surface | Cel |
|---|---|
| `/agents` | Lista agentów (workers), state machine |
| `/audit` | Raw audit log, hash chain verification |
| `/budget` | Detail budgets, cost breakdown per provider |
| `/costs` | Cost breakdown across all dimensions |
| `/decisions` | Decision Gates (5 zakładek: Active Chain, Timeline, Cascade, Diff, Gates) |
| `/idea-vault` | Idea management raw (15 statusów) |
| `/security-scan` | Security audits, scans |
| `/evidence-spine` | Hash chain visualization |
| `/governance` | Proposals, voting, policies, compliance |
| `/auth` | Identity, sessions |
| `/operator-mobile` | Mobile pairing, devices, push tokens |

### Powrót do Guided

Sticky button `[Switch to Guided Mode]` zawsze widoczny w nav (mirror Switch to Technical).

---

## 9. Pricing + budget

### Defaults z onboardingu

```
low risk      $0.10 / call
medium risk   $0.40 / call
high risk     $1.60 / call
critical risk $6.00 / call
funding       $3.00 / call (separate token budget)
```

### Per-action / per-month limits

Domyślnie:
- Pojedyncza akcja >25 EUR → HG (financial type)
- Miesięcznie >100 EUR → HG (przy crossing threshold)

Operator może podnieść / obniżyć w `Settings → Cost ceilings`.

### Hard gate auto-purchase

**ZAWSZE** wymagany Human Gate przed:
- Purchase nowego LLM plan/subscription.
- Add provider z paid API key (nawet free tier add → soft warning).
- Scale up beyond local (VPS).
- External upload/submit (e.g. browser submission do grantu).

Engine NIE może auto-pur­chasować nawet z `autonomy=auto`. Hard governance rule.

### Pricing data — 3 source priorytety

```
1. live      → real-time z provider metadata API (najświeższe)
2. profile   → declarative pricing tables (z adapter config)
3. assumption → no data → mark "ASSUMPTION" badge na karcie
```

ASSUMPTION powoduje obniżenie `pricing_quality` → confidence overall niższy.

### Budget threshold crossing

Przy `actual_usage > configured_threshold`:
- Event: `aeis.system.budget_threshold_crossed`
- Subscriber: `advisor.engine` + `advisor.subscription`
- Output: warning card surfacing → "spent $X of $Y this month, suggested actions: ..."

### Funding token budget separate

Funding ma **własny** budget (default $20/mies). Token-heavy operations (scanning, scoring,
LLM-judge dla per-grant analysis) idą z tego budżetu, NIE z global.

---

## 10. Rozwiązywanie problemów

### Karta nie wystrzeliła chociaż spodziewałem się

Możliwe przyczyny:
1. **Dedup**: ta sama karta wystrzeliła w ostatnich N minut → dedup window.
2. **TTL**: poprzednia karta tego typu jest jeszcze active.
3. **Confidence threshold**: `confidence < 0.5` → karta zsuppressed (sprawdź preferences `card_visibility_threshold`).
4. **Anti-spam rule**: operator odrzucił 3x z rzędu → reduced surfacing dla tego typu.
5. **Schema validation failed**: payload nie pasuje do proto → check `aeis.advisor.events.validation_failed` w logu.

**Debug**: `Settings → Card Diagnostics` → query po hook + project + okres.

### Hard preference change zignorowany

Hard preferences wymagają operator click:
- Czy zobaczyłeś modal confirmation?
- Czy kliknąłeś "Confirm" przed nawigacją?

Sprawdź `advisor_preferences.preferences_audit` w technical mode.

### Evidence Pack draft nie jest wypełniony

Możliwe:
1. LLM-judge call timed out → check `llm_judge_audit` table.
2. Local fallback used + `confidence × 0.8` → niższe wymagania.
3. Brak history match → LLM ma mniej kontekstu.

**Fix**: edytuj draft ręcznie. Operator może override LLM-judge content.

### Council session nie consolidate

```
ValueError: critic signature required
```

Wymagany podpis modelu w `role='critic'`. Sprawdź:
- Czy uczestnik z `role='critic'` jest w sesji?
- Czy `record_critic_signature(session_id, critic_model_id)` zostało wywołane?

```
sentinel_blocks: [{role: 'cost_sentinel', verdict: 'reject', reason: '...'}]
```

Sentinel zablokował. Adresuj reason → potem retry consolidation.

### Provider API key nie działa

```
Settings → AI Providers → [Test connection]
```

Common issues:
- Wrong env var (`SYLION_LLM_API_KEY` musi być set dla active provider).
- Wrong model ID (sprawdź `SYLION_LLM_MODEL`).
- Quota exceeded (sprawdź provider dashboard).
- IP allowlist (jeśli skonfigurowane).

### Budget overrun

```
Cost dashboard → Cost ceiling crossed
```

Akcje:
- Reduce premium model usage (advisor sugeruje `REC_TYPE_REDUCE_PREMIUM_USAGE`).
- Move to cheaper model (`REC_TYPE_MOVE_TO_CHEAPER_MODEL`).
- Increase budget ceiling (Settings, hard preference).
- Pause non-critical projects.

### Frontend live data nie pokazuje się

Common issues:
- WebSocket bridge nie wystartował (sprawdź `start_event_bridge` w lifespan).
- `backendLive` flag false → fallback do mock data.
- Hook returns shape mismatch — sprawdź `useHealth` pattern (`{data, loading, error, refresh}`).

**Fix**: backend restart:
```bash
cd src/sylion-pipeline && python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010
```

### Mobile pairing fails

- QR code expired (5 min TTL) → re-generate.
- JWT verification fails → device-bound check (sprawdź czy device fingerprint matches).
- Biometric prompt fails → fallback do PIN (jeśli skonfigurowane), inaczej re-pair.

### "Switch to Technical" nie działa

Link powinien być zawsze w nav. Jeśli nie:
- Sprawdź `AppSidebar.tsx` → czy link jest renderowany.
- Sprawdź flagi feature: `SYLION_TECHNICAL_MODE_ENABLED=true`.

---

## Powiązane dokumenty

- [00_architektura_systemu.md](./00_architektura_systemu.md) — całościowy obraz
- [01_modul_aeis_advisor.md](./01_modul_aeis_advisor.md) — Advisor deep-dive
- [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) — D-ladder + Evidence Pack
- [04_dla_developera.md](./04_dla_developera.md) — onboarding developera
