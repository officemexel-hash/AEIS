# Surface: Advisor Feed (`/advisor`)
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Główna powierzchnia operatora dla SYLION AEIS Advisor — strumień rekomendacji w czasie rzeczywistym, modale akcji oraz powiązany komponent „pływającej” bańki (AdvisorBubble).

## Spis treści

1. [Cel + URL](#1-cel--url)
2. [Komponenty UI](#2-komponenty-ui)
3. [Wszystkie controls + interactions](#3-wszystkie-controls--interactions)
4. [State management](#4-state-management)
5. [API integration](#5-api-integration)
6. [Persistence (localStorage, cookies, sessionStorage)](#6-persistence-localstorage-cookies-sessionstorage)
7. [Modes / variants](#7-modes--variants)
8. [Accessibility](#8-accessibility)
9. [Przykładowe operator flows (step-by-step)](#9-przykładowe-operator-flows-step-by-step)
10. [Cross-references](#10-cross-references)

---

## 1. Cel + URL

| Pole | Wartość |
|------|---------|
| Route podstawowa | `/advisor` |
| Route szczegółowa | `/advisor/[cardId]` |
| Route Cockpit v4 | `/advisor/cockpit` (sprint2, 2026-04-26) |
| Plik strony | `src/sylion-frontend/src/app/(app)/advisor/page.tsx` |
| Plik szczegółu | `src/sylion-frontend/src/app/(app)/advisor/[cardId]/page.tsx` |
| Plik Cockpit v4 | `src/sylion-frontend/src/app/(app)/advisor/cockpit/page.tsx` |
| Plik bańki globalnej | `src/sylion-frontend/src/components/advisor/AdvisorBubble.tsx` |
| Persona docelowa | Operator (główny), audytor (do podglądu Evidence Pack), admin (do override) |
| Klasa decyzji | D0–D5 (cały zakres; D3+ wymaga Evidence Pack) |
| Refresh interval | 6 sekund (override domyślnego 8 s w hooku) |

### 1.1. Cockpit v4 — Orbital Glass Command Deck (sprint2)

Sprint 2 (2026-04-26) wprowadził nową route `/advisor/cockpit` jako główny widok operatora.
Po zakończeniu onboardingu (`complete()`) redirect trafia teraz do `/advisor/cockpit` zamiast
do `/dashboard/operator-monitor`. Sidebar ma "Centrum dowodzenia" jako pierwszy element.

Cockpit v4 to pełnowymiarowa strona z designem "Orbital Glass" (glassmorphism, aurora background,
głębokość 5 warstw CSS). Składa się z 6 sekcji:

```
CockpitV4Page (advisor/cockpit/page.tsx — "use client")
├── Visual Hero (panel gradient + MetricTiles + AdvisorCore)
│   ├── MetricTile ×4: Tryb strategii | Human Gates | Aktywne projekty | Srednia pewnosc
│   └── AdvisorCore: Live Advisor Bubble z top-priority card (orb + speech)
├── Co wymaga decyzji teraz (DecisionCommandCard grid)
│   ├── criticalCard → variant="featured" (max D4+/D3)
│   └── otherCards[0..3] → variant="compact" (stack boczny)
├── Lifecycle Rail: 15 faz projektu (LifecycleRail)
├── Topologia zespołów agentów (AgentTopology — SVG)
├── Audit Trail: ostatnie 5 zdarzeń (AuditTrailCard)
└── Konfiguracja operator-facing (ConfigurationControlCards)
```

**CSS:** `src/sylion-frontend/src/app/(app)/advisor/cockpit/operating-advisor-v4.css` (601 linii)
Klasy scoped pod `.cockpit-v4` — brak globalnego zabrudzenia innych stron.

**Nowe komponenty** w `src/sylion-frontend/src/components/advisor/`:

| Komponent | Plik | Opis |
|-----------|------|------|
| `AdvisorCore` | `AdvisorCore.tsx` | "Live Advisor Bubble" — animowany orb z etykietami (koszty, modele, testy, Council) + speech bubble z najważniejszą kartą |
| `DecisionCommandCard` | `DecisionCommandCard.tsx` | Karta decyzyjna w dwóch wariantach: `featured` (pełna) + `compact` (lista boczna). Sortowana D5→D4→D3 |
| `LifecycleRail` | `LifecycleRail.tsx` | 15 faz lifecycle projektu: `idea_intake`, `clarification`, `council_vote`, `memory_match`, `skills_binding`, `operator_approval`, `sot_setup`, `masterplan`, `plan_hg`, `runtime_selection`, `execution`, `risk_hg`, `testing`, `final_review`, `memory_update`. Stany: `done`/`now`/`blocked` |
| `AgentTopology` | `AgentTopology.tsx` | SVG diagram: Planner → Workers → Verifier/Critic → Council/HG |
| `ConfigurationControlCards` | `ConfigurationControlCards.tsx` | Siatka konfiguracji: API keys, lokalne modele, routing, Skills — tryb operatora |
| `AuditTrailCard` | `AuditTrailCard.tsx` | Ostatnie 5 zdarzeń z audit trail |

**Hooki używane:**
- `useAdvisorFeed({ refreshMs: 8000 })` — karty dla AdvisorCore + DecisionCommandCard
- `useMonitoringSnapshot(30_000)` — projekt dla MetricTiles + LifecycleRail
- `useProjectLifecycle(activeProjectId)` — fazy lifecycle dla LifecycleRail

**Logika priorytetu kart:**

```typescript
const criticalCard =
  cards.find((c) => dNum(c) >= 4) ??   // D4 lub D5
  cards.find((c) => dNum(c) >= 3) ??   // D3
  cards[0] ?? null;                     // fallback: pierwsza karta

const otherCards = cards
  .filter((c) => c.header.card_id !== criticalCard?.header.card_id)
  .slice(0, 4);
```

**Co operator robi na tej stronie:**

- Przegląda wszystkie żywe rekomendacje (Decision Card, Funding, Security, Scaling, Onboarding) dla swoich aktywnych projektów.
- Filtruje feed po poziomie ryzyka (low / medium / high / critical), domenie projektu oraz fladze „history-aligned only”.
- Otwiera modal akcji dla kart wysokiego/krytycznego ryzyka (modal pojawia się automatycznie, dopóki użytkownik nie odrzuci karty albo nie wykona akcji).
- Akceptuje, odrzuca, modyfikuje rekomendację albo eskaluje do Human Gate / Masterplan change / preferencji.
- Otwiera Evidence Pack dla decyzji D3+ (wbudowany Dialog z `EvidencePackViewer`).
- Klikiem w kartę przechodzi do widoku szczegółowego (`/advisor/[cardId]`).
- Z poziomu pływającej bańki (AdvisorBubble) — bez wchodzenia na `/advisor` — widzi licznik aktywnych kart, top 3 nagłówków oraz „nieprzeczytane” diff od ostatniego otwarcia.

Strona jest w pełni klientowa (`"use client"`), bez SSR-owanego danych — każda nawigacja powoduje ponowny start polling-u.

---

## 2. Komponenty UI

### 2.1 Hierarchia komponentów

```
AdvisorFeedPage (page.tsx)
├── FeedHeader            -> tytuł, badge LIVE/MOCK, licznik kart, przycisk Refresh
├── MockBanner            -> ostrzeżenie offline / fallback do mocków
├── FilterBar             -> filtr risk, filtr domain, switch history-aligned-only
├── FeedList              -> lista kart (DecisionCardCard) z animacją AnimatePresence
├── ToastQueue            -> kolejka toastów dla low/medium (max 3 widoczne)
│   └── CardToast         -> pojedynczy toast (auto-dismiss 5 s, hover pause)
├── CardModal             -> modal eskalacji dla high/critical (mandatorny — must act)
└── Dialog (Evidence)     -> modal Evidence Pack (zawiera EvidencePackViewer)
```

Globalnie (z root layoutu):

```
AdvisorBubble (komponent fixed bottom-right)
├── Pływająca bańka z licznikiem kart oraz badge nieprzeczytanych
└── Panel dropdown z top 3 kart i linkiem „otwórz feed →”
```

### 2.2 Tabela komponentów

| Komponent | Plik źródłowy | Rola | Dane wejściowe | Eventy wyjściowe |
|-----------|---------------|------|----------------|------------------|
| `AdvisorFeedPage` | `advisor/page.tsx` | Orkiestrator strony | brak (root) | nawigacja `router.push` |
| `FeedHeader` | `advisor/_components/FeedHeader.tsx` | Nagłówek + status `live/mock/loading` | `totalCards`, `filteredCount`, `source`, `criticalCount`, `onRefresh` | `onRefresh()` |
| `FilterBar` | `advisor/_components/FilterBar.tsx` | Filtry risk + domain + history-only | `risk`, `domain`, `domains[]`, `historyOnly` | `onRiskChange`, `onDomainChange`, `onHistoryOnlyChange` |
| `FeedList` | `advisor/_components/FeedList.tsx` | Animowana lista kart | `cards[]`, `filtered`, `onOpenEvidence` | `onOpenEvidence(packId, cardId)` |
| `EmptyState` | `advisor/_components/EmptyState.tsx` | Komunikat pustego stanu (z trybem filtrowanym) | `filtered: boolean` | brak |
| `CardModal` | `advisor/_components/CardModal.tsx` | Modal blokujący dla high/critical | `card`, `onClose`, `onOpenEvidence` | `onClose()`, `onOpenEvidence` |
| `ToastQueue` | `advisor/_components/ToastQueue.tsx` | Kontener fixed toastów | `cards[]` | brak (samosterowny) |
| `CardToast` | `advisor/_components/CardToast.tsx` | Pojedynczy toast | `card`, `onDismiss` | `onDismiss(cardId)` |
| `DecisionCardCard` | `components/advisor/DecisionCardCard.tsx` | Renderowanie ciała karty (rekomendacja, impact, akcje) | `envelope`, `variant`, `onOpenEvidence`, `onActionComplete` | wywołania API z `useCardActions` |
| `EvidencePackViewer` | `components/advisor/EvidencePackViewer.tsx` | Pełny widok Evidence Pack + przyciski sign/finalize | `pack`, `onSigned` | `onSigned()` |
| `MockBanner` | `components/advisor/MockBanner.tsx` | Pasek ostrzegawczy „dane demonstracyjne” | `source` | brak |
| `RiskBadge`, `DLevelBadge`, `ConfidenceMeter`, `PhaseTimeline` | `components/advisor/*` | Wizualne primitives (re-used) | różne | brak |
| `AdvisorBubble` | `components/advisor/AdvisorBubble.tsx` | Globalna bańka pływająca | brak (sam wczytuje feed) | nawigacja do `/advisor` |
| `BubbleItem` | wewnętrzny w `AdvisorBubble.tsx` | Pojedynczy element w panelu bańki | `card` | brak |

### 2.3 Komponent `DecisionCardCard` — wewnętrzna struktura

Mimo że `DecisionCardCard` żyje w katalogu `components/advisor/`, jest sercem rekomendacji i operator wchodzi z nim w największą interakcję. Renderuje:

- nagłówek z `RiskBadge`, `DLevelBadge`, znacznikiem czasu i `ConfidenceMeter`,
- tytuł rekomendacji + rationale,
- sekcję wpływu (cost / token / time impact) z deltami,
- listę alternatyw (z trade-off summary),
- przyciski akcji (Accept / Reject / Modify / Remind later / Not useful / Convert to Human Gate / Convert to Masterplan change / Save as preference / Don’t learn from this) — wszystkie 9 typów `CardAction`,
- pole tekstowe na `operator_note` przy Modify,
- przycisk „Open Evidence Pack” widoczny gdy `card.header.evidence_pack_id` istnieje.

---

## 3. Wszystkie controls + interactions

### 3.1 FeedHeader

| Control | Test ID | Akcja | API call | State change |
|---------|---------|-------|----------|--------------|
| Badge `LIVE / MOCK / LOADING` | `feed-source-indicator` | wyłącznie informacyjny | brak | brak |
| Badge `X / Y cards` | `feed-count-total` | informacyjny | brak | brak |
| Badge `N critical` | `feed-count-critical` | informacyjny (warunkowy: gdy `criticalCount > 0`) | brak | brak |
| Przycisk `Refresh` | `feed-refresh` | wymusza ponowny fetch przed kolejnym ticke’m | `GET /api/v1/advisor/cards?operator_id=...&limit=50` | `useFetch.run()` aktualizuje `data, source` |

### 3.2 FilterBar

| Control | Test ID | Akcja | API call | State change |
|---------|---------|-------|----------|--------------|
| Przyciski risk (`all/low/medium/high/critical`) | `filter-risk-{value}` | ustawia `filterRisk` | brak (filtrowanie klientowe) | `setFilterRisk(value)` → `filtered` recompute |
| Badge domain (`all` + każda domena z feedu) | brak (badge bez data-testid) | ustawia `filterDomain` | brak | `setFilterDomain(value)` |
| Switch `History-aligned only` | `filter-history-only` | toggle filtra `header.history_based` | brak | `setHistoryOnly(boolean)` |

### 3.3 FeedList + DecisionCardCard

| Control | Akcja | API call | State change |
|---------|-------|----------|--------------|
| Klik w kartę (kontener) | nawigacja do szczegółu karty | brak (Next router) | `router.push('/advisor/{cardId}')` |
| Przycisk `Accept` | wysyła akcję `accept` | `POST /api/v1/advisor/cards/{cardId}/actions` z `{ action: "accept" }` | `useCardActions.submit` → `setSubmitting`, po sukcesie zwraca `HandleActionResponse` |
| Przycisk `Reject` | wysyła akcję `reject` | `POST .../actions` z `{ action: "reject" }` | jak wyżej |
| Przycisk `Modify` | otwiera pole `operator_note` + `modified_recommendation`, wysyła `modify` | `POST .../actions` z `{ action: "modify", operator_note, modified_recommendation }` | jak wyżej |
| Przycisk `Remind later` | odkłada kartę | `POST .../actions` z `{ action: "remind_later" }` | jak wyżej |
| Przycisk `Not useful` | sygnał negatywny do learning loop | `POST .../actions` z `{ action: "not_useful" }` | jak wyżej |
| Przycisk `Convert to Human Gate` | tworzy ticket Human Gate | `POST .../actions` z `{ action: "convert_to_human_gate" }` | response: `created_human_gate_ticket_id` |
| Przycisk `Convert to Masterplan change` | tworzy proposal masterplanu | `POST .../actions` z `{ action: "convert_to_masterplan_change" }` | response: `created_masterplan_proposal_id` |
| Przycisk `Save as preference` | zapisuje wybór operatora jako preferencję | `POST .../actions` z `{ action: "save_as_preference" }` | response: `saved_preference_id` |
| Przycisk `Don’t learn from this` | flaga `dont_learn` na karcie | `POST .../actions` z `{ action: "dont_learn_from_this" }` | brak learning |
| Przycisk `Open Evidence Pack` | otwiera Dialog z `EvidencePackViewer` | `GET /api/v1/advisor/evidence/{packId}` (przez `useEvidencePack`) | `setEvidencePackId(packId)` |

#### Header `X-Biometric-Verified`

Karty z `requires_biometric: true` (np. critical block deploy) wymagają potwierdzenia biometrycznego — operator wykonuje WebAuthn challenge w UI (poza zakresem `/advisor`, w mobile companion), po czym `useCardActions.submit` jest wywoływane z `biometricVerified=true`, co dodaje header `X-Biometric-Verified: true` do POST.

### 3.4 CardModal (high / critical)

| Control | Test ID | Akcja | State change |
|---------|---------|-------|--------------|
| Przycisk `Open detail` | `advisor-modal-open-detail` | nawigacja do `/advisor/[cardId]` i zamyka modal | `router.push`, `onClose()` |
| Akcje karty (jak w 3.3) | `advisor-modal-action-*` | identyczne jak w `DecisionCardCard` | po sukcesie `onActionComplete()` → `closeModal()` |
| Outside click / ESC | `advisor-modal` | **zablokowane** — `disablePointerDismissal` jest aktywne; `reason in ["outside-press","escape-key","focus-out"]` ignorowane | brak |

Modal jest „mandatorny”: nie można go zamknąć kliknięciem poza dialogiem ani ESC; jedyne sposoby:

1. Wykonanie dowolnej akcji na karcie (`onActionComplete` → `closeModal()`).
2. Klik w `Open detail` (operator deklaruje że obejrzy szczegół).

Po zamknięciu karta jest dodawana do `dismissedRef` — `useRef<Set<string>>` lokalnego, nie persystowanego, więc po reload modal wskoczy ponownie jeśli karta nadal wisi.

### 3.5 ToastQueue + CardToast

| Control | Test ID | Akcja | State change |
|---------|---------|-------|--------------|
| Klik w toast „Open card” | `advisor-toast-open` | nawigacja `/advisor/[cardId]` + dismiss | `router.push`, `dismiss(cardId)` |
| Klik X (Dismiss) | `advisor-toast-dismiss` | usuwa toast z kolejki | `dismiss(cardId)` |
| Hover na toascie | brak | pauzuje auto-dismiss 5 s | `setHovered(true)` → `clearTimeout` |
| Counter `+N more` | `advisor-toast-queue-counter` | informacyjny | brak |

Tylko karty `low` / `medium` trafiają do `ToastQueue`. Karty `high` / `critical` zawsze otwierają `CardModal`.

### 3.6 AdvisorBubble (komponent globalny)

| Control | Akcja | State change |
|---------|-------|--------------|
| Klik w bańkę (Bell) | toggle panelu dropdown | `setOpen(v => !v)`; po otwarciu `setSeen(new Set(allCards))` |
| Klik w `otwórz feed →` | nawigacja `/advisor` | `setOpen(false)` (pasywne) |
| Brak interakcji przez 6 s | bezautomatycznego zamknięcia (panel zostaje otwarty dopóki user nie kliknie) | brak |

Bańka pulsuje czerwono (`animate-pulse`) jeśli `cards.some(c => c.risk_level === "critical")`.

---

## 4. State management

### 4.1 Stan lokalny komponentu `AdvisorFeedPage`

```typescript
const [filterRisk, setFilterRisk] = useState<RiskLevel | "all">("all");
const [filterDomain, setFilterDomain] = useState<string>("all");
const [historyOnly, setHistoryOnly] = useState<boolean>(false);
const [modalCard, setModalCard] = useState<AdvisorCardEnvelope | null>(null);
const dismissedRef = useRef<Set<string>>(new Set());
const [evidencePackId, setEvidencePackId] = useState<string | null>(null);
```

- `filterRisk` / `filterDomain` / `historyOnly` — wszystkie czysto klientowe; **nie** są persystowane (reset po reload).
- `modalCard` — aktualnie otwarta karta high/critical w modalu; sterowane efektem `useEffect` który automatycznie pickuje pierwszą niezedismissowaną kartę.
- `dismissedRef` — Set w pamięci sesji (`useRef`), nie persystowany. Reset po reload.
- `evidencePackId` — id otwartego Evidence Pack w Dialog; null = zamknięty.

### 4.2 Hook `useAdvisorFeed`

```typescript
const { data: cards, source, refresh } = useAdvisorFeed({ refreshMs: 6000 });
```

- Wewnętrznie używa `useFetch<AdvisorCardEnvelope[]>` z fetcherem `advisorApi.listCards(...)`.
- TTL reachability: 15 sekund (cache `_reachable` w module).
- Polling: `setInterval(run, refreshMs)` w `useEffect`.
- Cleanup: w unmount kasuje interval i ustawia `mounted.current = false`.
- Fallback: jeśli `isBackendReachable()` zwraca `false`, hook ustawia `source = "mock"` i zwraca pustą tablicę `[]` (sprint2 usunął demo karty z `advisorMocks.cards()`).

### 4.3 Hook `useEvidencePack`

```typescript
const { pack: evidencePack } = useEvidencePack(evidencePackId);
```

- Fetch: `advisorApi.getEvidencePack(packId)`.
- Fallback: `null` — sprint2 usunął `advisorMocks.evidencePack()`; brak pakietu danych demonstracyjnych.
- **Bez** polling-u (brak `refreshMs`).

### 4.4 Hook `useCardActions`

```typescript
const { submit, submitting, error } = useCardActions();
```

- Stan: `submitting: boolean`, `error: string | null`.
- Bez fallbacku — jeśli backend nieosiągalny, zwraca lokalny stub `HandleActionResponse` (id `mock-{cardId}-{Date.now()}`), żeby UI nie pęczniał.
- Po sukcesie nie odświeża feedu automatycznie — wywołujący komponent (`DecisionCardCard`) decyduje co zrobić (zwykle `onActionComplete()` zamyka modal, a kolejny tick pollingu przyniesie nowy stan).

### 4.5 Cache invalidation

| Wydarzenie | Inwalidacja |
|------------|-------------|
| `setInterval` co 6 s | re-fetch całego `cards[]` |
| Klik `Refresh` w nagłówku | `useFetch.run()` natychmiast |
| Akcja na karcie (`accept`/`reject`/...) | brak natychmiastowej inwalidacji — kolejny tick pollingu zaktualizuje listę (backend usuwa zaakceptowaną/odrzuconą kartę z aktywnego feedu) |
| `useEffect` na zmianę `cards[]` | weryfikuje czy `modalCard.card_id` nadal istnieje; jeśli nie — auto-zamyka modal |

Brak jest globalnego cache (TanStack Query / SWR). Wszystko leci przez prosty `useFetch` zaimplementowany w `lib/hooks/advisor.ts`.

---

## 5. API integration

### 5.1 Wszystkie endpointy używane przez `/advisor`

| Metoda | Endpoint | Wywołujący | Typ odpowiedzi |
|--------|----------|------------|----------------|
| GET | `/api/v1/advisor/cards?operator_id={uuid}&limit=50` | `useAdvisorFeed` | `{ cards: AdvisorCardEnvelope[] }` |
| GET | `/api/v1/advisor/cards/{cardId}` | `useAdvisorCard` (na `/advisor/[cardId]`) | `AdvisorCardEnvelope` |
| POST | `/api/v1/advisor/cards/{cardId}/actions` | `useCardActions.submit` | `HandleActionResponse` |
| GET | `/api/v1/advisor/evidence/{packId}` | `useEvidencePack` | `EvidencePack` |
| POST | `/api/v1/advisor/evidence/{packId}/finalize` | `EvidencePackViewer` (przy finalize) | `{ ok: true }` |
| POST | `/api/v1/advisor/evidence/{packId}/sign` | `EvidencePackViewer` (przy sign) | `{ signature_id: string }` |
| GET | `/health` | `isBackendReachable()` | `{ status: "ok", ... }` (TTL 15 s) |

Bazowy URL: `process.env.NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8010`). Prefix: `/api/v1/advisor`.

### 5.2 Schematy TypeScript (z `lib/api/advisor.ts`)

```typescript
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type DLevel = "D0" | "D1" | "D2" | "D3" | "D4" | "D5";
export type CardType = "decision" | "funding" | "security" | "scaling" | "onboarding";
export type CardAction =
  | "accept"
  | "reject"
  | "modify"
  | "remind_later"
  | "not_useful"
  | "convert_to_human_gate"
  | "convert_to_masterplan_change"
  | "save_as_preference"
  | "dont_learn_from_this";

export interface AdvisorCardHeader {
  card_id: string;
  schema_version: string;
  card_type: CardType;
  parent_card_id?: string;
  title: string;
  rationale: string;
  confidence_score: number;          // 0..1
  confidence_label: "low" | "med" | "high" | "very_high" | "certain";
  sources: ("rule_engine" | "llm_judge" | "history_match" | "council_vote" | "hybrid")[];
  risk_level: RiskLevel;
  risk_explanation?: string;
  project_domain: string;
  project_type?: string;
  project_id?: string;
  idea_id?: string;
  d_level: DLevel;
  evidence_pack_id?: string;
  history_based: boolean;
  related_history_card_ids: string[];
  historical_acceptance_rate: number; // 0..1
  created_at: number;                  // unix seconds
  updated_at: number;
  expires_at?: number;
  priority: "low" | "normal" | "high" | "urgent";
  tags: string[];
  dont_learn: boolean;
  human_gate_required: boolean;
  mobile_allowed: boolean;
  requires_biometric: boolean;
  push_priority: "silent" | "low" | "normal" | "high" | "urgent";
  audit_trail_id: string;
  llm_judge_audit_id?: string;
  operator_id: string;
  emitting_module: string;
  used_local_fallback: boolean;
  local_fallback_reason?: string;
}

export interface AdvisorCardEnvelope {
  envelope_version: string;       // e.g. "1.0.0"
  header: AdvisorCardHeader;
  body: DecisionCardBody | FundingCardBody | Record<string, unknown>;
}

export interface HandleActionResponse {
  action_event_id: string;
  recorded_at: number;
  soft_learning_triggered: boolean;
  hard_learning_pending_confirmation: boolean;
  created_human_gate_ticket_id?: string;
  created_masterplan_proposal_id?: string;
  saved_preference_id?: string;
}
```

### 5.3 Request body — POST /actions

```json
{
  "action": "accept",
  "operator_note": "Looks good — proceed.",
  "modified_recommendation": null
}
```

Headers:

```
Content-Type: application/json
X-Biometric-Verified: true   // opcjonalnie, gdy karta requires_biometric
```

### 5.4 Tryb mock

Gdy `/health` zwraca błąd lub timeout (2.5 s):

- `source = “mock”` w odpowiedzi `useFetch`.
- `cards` wracają do `[]` (pusta tablica — sprint2 consolidated commit usunął demo karty z `advisorMocks`).
- `useCardActions.submit` zwraca syntetyczny `HandleActionResponse` z `action_event_id = “mock-{cardId}-{ts}”`.
- `MockBanner` renderuje pomarańczowy pasek „Backend offline — wyświetlam dane demonstracyjne”.
- `EmptyState filtered={false}` widoczny gdy brak kart z feedu.

---

## 6. Persistence (localStorage, cookies, sessionStorage)

| Klucz / mechanizm | Typ | Co przechowywane | TTL | Plik źródłowy |
|-------------------|-----|------------------|-----|---------------|
| `dismissedRef.current` | in-memory `Set<string>` | id kart które operator dismissował (modal) | sesja (do reload) | `advisor/page.tsx:24` |
| `_reachable`, `_checkedAt` | module-level (singleton hook) | wynik ostatniego `/health` | 15 s | `lib/hooks/advisor.ts:29-30` |
| `seen` (AdvisorBubble) | komponentowy `useState<Set<string>>` | id kart które operator widział w bańce | sesja | `AdvisorBubble.tsx:16` |

**Strona `/advisor` nie używa localStorage ani cookies.** Filtr risk/domain/history-only nie jest persystowany — operator po reload zaczyna od `all`/`all`/`false`.

> Uwaga: hook `useOnboarding()` (używany przez inne surface) **używa** localStorage z kluczem `sylion.advisor.onboarding`. To nie dotyczy `/advisor` Feed bezpośrednio, ale ten sam moduł hooków go eksponuje.

---

## 7. Modes / variants

### 7.1 Tryby źródła danych

| Tryb | Trigger | Znacznik UI | Zachowanie |
|------|---------|-------------|------------|
| `live` | `/health` zwraca `200 ok` | Zielony badge `LIVE` w `FeedHeader` + brak `MockBanner` | Pełny polling, akcje idą do backendu |
| `mock` | `/health` timeout/error lub `_reachable=false` | Pomarańczowy badge `MOCK` + `MockBanner` | `cards = []` (brak demo kart); akcje zwracają `HandleActionResponse` ze stubem |
| `loading` | Pierwszy fetch przed odpowiedzią | Szary badge `LOADING` | `data = []`, brak listy |

### 7.2 Empty states

| Stan | Renderowany komponent | Tekst |
|------|----------------------|-------|
| `cards.length === 0`, brak filtrów | `EmptyState filtered={false}` | „Brak aktywnych rekomendacji — Doradca pokaże tu rekomendacje, gdy tylko zadziała pierwszy hook cyklu życia.” |
| `cards.length > 0`, ale `filtered.length === 0` | `EmptyState filtered={true}` | „Brak kart pasujących do filtrów — Wyczyść filtry ryzyka, domeny lub historii powyżej.” |
| `cards.length === 0` na `/advisor/[cardId]` | `Card` z linkiem „Back to feed” | „Card not found — No card with id ... exists in the current feed.” |

### 7.3 Loading states

- Pierwszy render `useAdvisorFeed`: `data = []` (fallback z mock), `source = "loading"`. UI pokazuje pusty `FeedList` lub `EmptyState`. Po pierwszej odpowiedzi z `/health` przełącza na `live` lub `mock`.
- `/advisor/[cardId]`: `loading && !card` → renderuje `Card p-8 text-center: Loading card...`.
- Evidence pack wewnątrz Dialog: `evidencePack === null` → `Loading evidence pack...`.

### 7.4 Error states

- Błąd `/health`: po stronie kompodów niewidoczny — przełącza tylko na `mock`. `error` jest set w `useFetch`, ale UI nie pokazuje go w `/advisor` (decyzja produktowa: lepsze UX).
- Błąd POST `/actions`: `useCardActions.error` jest ustawiany, `DecisionCardCard` może go wyrenderować (zwykle pomarańczowy banner pod przyciskami).
- Błąd GET `/evidence/{id}`: Dialog pokazuje placeholder „Loading evidence pack...” przez czas nieokreślony; brak fallbacku do mock pack (`advisorMocks.evidencePack()` usunięty w sprint2).

### 7.5 Variants karty (w `DecisionCardCard`)

- `variant="full"` — używane na `/advisor` i `/advisor/[cardId]`. Pełne body, alternatywy, akcje.
- `variant="compact"` — używane gdzie indziej (Lifecycle dashboard, Active Cards Panel) — bez alternatyw, akcje schowane.

---

## 8. Accessibility

### 8.1 ARIA & semantyka

- `FeedHeader` używa nagłówka `<h1 className="text-xl font-semibold">Advisor feed</h1>` — jeden h1 na stronę.
- `EmptyState` ma podtytuł `<h2>` zachowując hierarchię.
- `CardModal` używa `Dialog`/`DialogContent`/`DialogTitle` z Radix; modal jest `role="dialog"` `aria-modal="true"` automatycznie.
- `ToastQueue` ma `data-testid="advisor-toast-queue"`. Toasty pojedyncze mają `aria-label="Dismiss"` na X-ie (`CardToast.tsx:80-87`).
- `FilterBar` używa `<button>` z `data-active="true|false"` (state) — czytelne dla AT.
- `AdvisorBubble` button ma `aria-label="Advisor feed"`.
- `Switch` (Radix) w `FilterBar` jest dostępny klawiaturą natywnie.

### 8.2 Keyboard navigation

| Skrót | Akcja |
|-------|-------|
| `Tab` | przechodzi przez badge filtrów risk → badge domain → switch history-only → karty (każda focusable) → przyciski akcji wewnątrz karty |
| `Enter` / `Space` | aktywuje aktualnie ufocusowany przycisk (filtr, refresh, akcję karty) |
| `Esc` | **nie zamyka** `CardModal` (mandatorny modal — `disablePointerDismissal`); zamyka tylko Dialog Evidence Pack |
| Klik przez klawisz | Radix dialog zarządza focus trap i return-focus po zamknięciu |

### 8.3 Color contrast

- Tła kart: `bg-card` na `bg-background` — kontrast WCAG AA ≥4.5:1 dla tekstów `text-foreground` i `text-muted-foreground`.
- `RiskBadge`:
  - `low` — niebieski `sylion-blue` na ciemnym (#0f1629) — OK
  - `medium` — bursztynowy `sylion-amber` — OK
  - `high` — pomarańczowy 400 — OK
  - `critical` — `sylion-red` (#F31260) — wyróżnia się czerwoną pulsacją w bańce
- `DLevelBadge` używa monospace + obwódki, bez polegania wyłącznie na kolorze.

### 8.4 Screen reader

- `data-testid` używane do testów Playwright (`feed-card`, `advisor-modal`, `advisor-toast`), nie konfliktują z aria.
- Live region: `ToastQueue` mógłby być `aria-live="polite"`, ale obecnie nie jest — TODO dla a11y review.
- `MockBanner` ma `role="alert"` (sprawdzić w `MockBanner.tsx`) — pomarańczowy banner widoczny dla AT.

---

## 9. Przykładowe operator flows (step-by-step)

### 9.1 Happy path: Akceptacja rekomendacji typu `decision` (low risk)

1. Operator wchodzi na `/advisor` przez nawigację z sidebar lub bezpośrednio z URL.
2. Frontend (`AdvisorFeedPage`) montuje się; `useAdvisorFeed` startuje pierwszy fetch.
3. `isBackendReachable()` sprawdza `/health` (TTL 15 s) — backend działa, zwraca `200 ok`.
4. Hook wywołuje `GET /api/v1/advisor/cards?operator_id={uuid}&limit=50`.
5. Backend (mobile_gateway) zwraca `{ cards: [...] }` zawierający trzy karty: jedną low (history-aligned), jedną medium (funding) i jedną low (decision).
6. UI renderuje `FeedHeader` z badge `LIVE`, licznikiem `3 / 3 cards`, oraz `FeedList` z trzema kartami posortowanymi po risk DESC + timestamp DESC.
7. `ToastQueue` pokazuje dwa toasty (low + medium) w prawym dolnym rogu — żaden nie jest critical/high, więc `CardModal` nie pojawia się automatycznie.
8. Operator klika kartę low „Council size larger than your default”.
9. Klik w kontener karty uruchamia `router.push('/advisor/demo-card-low')` (encodeURIComponent jest stosowane).
10. Strona `/advisor/[cardId]` montuje się, hook `useAdvisorCard` wywołuje `GET /api/v1/advisor/cards/demo-card-low`.
11. Operator czyta szczegóły, klika `Accept` w `DecisionCardCard`.
12. `useCardActions.submit("demo-card-low", "accept")` wywołuje `POST /api/v1/advisor/cards/demo-card-low/actions` z body `{ "action": "accept" }`.
13. Backend zwraca 200: `{ "action_event_id": "evt-7821", "recorded_at": 1745625600, "soft_learning_triggered": true, "hard_learning_pending_confirmation": false }`.
14. UI pokazuje toast / inline confirmation „Decision recorded”. Po następnym ticku polling-u (≤6 s) karta znika z aktywnego feedu.
15. Operator klika `Back to feed` (przycisk `ArrowLeft Feed` z `PageHeader`) — `router.push('/advisor')`.
16. Lista jest odświeżana, demo-card-low już nie istnieje. `criticalCount` pozostaje 0.

### 9.2 Happy path: Critical card → mandatorny modal → Convert to Human Gate

1. Operator pracuje w innej części aplikacji (`/dashboard`). Z `AdvisorBubble` widzi pulsującą czerwono bańkę z licznikiem `3 (1)` — 3 karty, 1 nieprzeczytana.
2. Klika bańkę; panel pokazuje top 3 nagłówków posortowanych DESC po risk. Pierwszy jest critical: „BLOCK production deploy — SoT not approved”.
3. Operator klika `otwórz feed →`; nawigacja `/advisor`, `setOpen(false)`.
4. `AdvisorFeedPage` montuje się; `useAdvisorFeed` zwraca te same karty.
5. `useEffect` w `page.tsx:56-71` automatycznie wykrywa pierwszą critical kartę nie z `dismissedRef` i ustawia `setModalCard(card)`.
6. `CardModal` otwiera się z `disablePointerDismissal=true`. Operator nie może zamknąć ESC/outside-click.
7. Operator czyta rationale: „The deploy request for masterplan mp-42 references SoT sot-7 which has not been approved.”
8. Klika `Open Evidence Pack` (button `Open Evidence Pack` widoczny bo `header.evidence_pack_id="demo-pack-1"`).
9. `setEvidencePackId("demo-pack-1")` → wewnętrzny Dialog otwiera się z `EvidencePackViewer`.
10. `useEvidencePack("demo-pack-1")` wywołuje `GET /api/v1/advisor/evidence/demo-pack-1`.
11. Backend zwraca pełny D5 pack: rationale, rollback_plan, fidelity_test, confidence_breakdown, risk_analysis, compliance_check, sentinel_signoffs.
12. Operator weryfikuje rollback plan, zamyka Evidence Dialog (`onOpenChange(false)`).
13. Wraca do `CardModal`, klika `Convert to Human Gate` (rekomendacja wymaga `human_gate_required=true`).
14. `useCardActions.submit("demo-card-critical", "convert_to_human_gate")` wywołuje POST z body `{ "action": "convert_to_human_gate" }`. Header zawiera `X-Biometric-Verified: true` jeśli karta `requires_biometric`.
15. Backend zwraca 200: `{ "action_event_id": "evt-9876", "recorded_at": 1745625800, "created_human_gate_ticket_id": "hg-tkt-44", "soft_learning_triggered": false, "hard_learning_pending_confirmation": false }`.
16. `onActionComplete()` zamyka `CardModal`.
17. `dismissedRef.current.add("demo-card-critical")` zapobiega ponownemu otwarciu modala dla tej samej karty (do reload).
18. Po następnym ticku karta znika z feedu (backend ją zarchiwizował). UI dispatcheruje notyfikację z `created_human_gate_ticket_id`, którą operator może otworzyć w Human Gate UI.

### 9.3 Error path: Backend offline → tryb MOCK

1. Operator otwiera `/advisor` po restarcie maszyny. Backend `uvicorn` jeszcze nie wystartował.
2. `isBackendReachable()` próbuje `fetch("/health", { signal: AbortSignal.timeout(2500) })`.
3. Po 2,5 s timeout — `_reachable = false`, `_checkedAt = Date.now()`.
4. `useFetch.run()` widzi `reachable === false`, ustawia `data = []`, `source = “mock”`.
5. UI renderuje:
   - `FeedHeader` z badge pomarańczowym `MOCK`.
   - `MockBanner` (pomarańczowy pasek): „Backend offline — wyświetlam dane demonstracyjne. Akcje nie zostaną zapisane.”
   - `EmptyState filtered={false}` — brak kart demonstracyjnych (usunięte w sprint2).
6. Operator klika `Accept` na karcie — niemożliwe w stanie offline (brak kart).
7. `useCardActions.submit` wywołuje `isBackendReachable()` (cache TTL 15 s) — nadal false.
8. Zwraca syntetyczny stub: `{ action_event_id: "mock-demo-card-low-1745625600000", recorded_at: 1745625600, soft_learning_triggered: false, hard_learning_pending_confirmation: false }`.
9. UI pokazuje confirmation, ale na backendzie nic się nie dzieje.
10. Operator startuje backend (`python -m uvicorn sylion.api.app:app --port 8010`).
11. Po 15 s TTL wygasa, `isBackendReachable()` znów strzela do `/health` → tym razem `200 ok`. `_reachable = true`.
12. Następny tick polling-u (≤6 s) pobiera prawdziwe karty. UI przełącza badge na zielony `LIVE`, `MockBanner` znika.

### 9.4 Edge case: Modify z notatką operatora

1. Operator widzi kartę medium „Reduce ensemble size for cost optimization (3→2 models)”.
2. Klika `Modify` w `DecisionCardCard`.
3. UI renderuje inline-form z dwoma polami: textarea `operator_note` i textarea `modified_recommendation`.
4. Operator wpisuje:
   - operator_note: „Zaakceptowane częściowo: tylko dla project_type=research, nie production.”
   - modified_recommendation: „Use 2 models for research project, keep 3 for production.”
5. Klika `Submit modification`.
6. `useCardActions.submit("card-id-789", "modify", { operator_note: "...", modified_recommendation: "..." })`.
7. POST `/api/v1/advisor/cards/card-id-789/actions` z body:
   ```json
   {
     "action": "modify",
     "operator_note": "Zaakceptowane częściowo...",
     "modified_recommendation": "Use 2 models for research..."
   }
   ```
8. Backend zwraca 200 z `soft_learning_triggered: true` (modifikacja sygnalizuje preference shift) + `hard_learning_pending_confirmation: true` (system rozważa zaproponowanie hard preference D3).
9. UI pokazuje banner: „Modyfikacja zapisana. System rozważa propozycję hard preference — czeka na confirmation.”
10. Po następnym ticku polling-u, jeśli `hard_learning_pending_confirmation`, system wyemituje **nową** kartę typu `decision` z proposalem („Zapisz jako preferencję per project_type=research?”) — operator decyduje w kolejnym kroku.

---

## 10. Cross-references

### 10.1 Powiązane moduły backend

| Moduł | Plik | Rola |
|-------|------|------|
| `sylion.aeis.advisor.mobile_gateway` | `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway.py` | FastAPI mount obsługujący prefix `/api/v1/advisor` |
| `sylion.aeis.advisor.engine` | `src/sylion-pipeline/sylion/aeis/advisor/engine/` | Generuje karty (rule_engine, llm_judge, history_match, council_vote, hybrid) |
| `sylion.aeis.advisor.engine._models` | tamże | Dataclasses `AdvisorCardEnvelope`, `AdvisorCardHeader`, `DecisionCardBody` (źródło prawdy dla TS interfaces) |
| `sylion.aeis.advisor.persistence` | `persistence/` | PostgreSQL pgvector — `cards`, `evidence_packs`, `card_actions`, `audit_trail` |
| `sylion.aeis.advisor.evidence` | `evidence/` | Generowanie i finalizacja Evidence Pack (D3-light, D5-full) |
| `sylion.aeis.council` | `src/sylion-pipeline/sylion/aeis/council/` | Council vote source dla kart `source: "council_vote"` |
| `sylion.aeis.governance.human_gate` | `governance/human_gate.py` | Tworzenie ticketów po `convert_to_human_gate` |
| `sylion.aeis.masterplan` | `masterplan/` | Tworzenie proposali po `convert_to_masterplan_change` |

### 10.2 Architecture docs

- `docs/claude_parallel/aeis_advisor/00_architecture/00_master_spec.md` — pełna specyfikacja Advisor Layer.
- `docs/claude_parallel/aeis_advisor/00_architecture/01_advisor_card_schema.md` — schema kanoniczna karty (header/body/envelope).
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — DDL dla persystencji.
- `docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md` — 16 hooków cyklu życia (H01–H16) emitujących karty.
- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — drabina decyzyjna D0–D5.
- `docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md` — szablony Evidence Pack.
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — taksonomia eventów `aeis.*`.

### 10.3 Pokrewne surfaces (UI)

| Surface | Route | Dlaczego powiązane |
|---------|-------|--------------------|
| Advisor card detail | `/advisor/[cardId]` | Bezpośredni szczegół karty z feedu |
| **Cockpit v4** | `/advisor/cockpit` | Główny widok operatora post-onboarding (sprint2) |
| Lifecycle Dashboard | `/projects/[projectId]/lifecycle` | Pokazuje karty w kontekście fazy projektu (H01–H16) |
| Operator Monitor | `/dashboard/operator-monitor` | Multi-project KPI + alerts feed (zachowany jako fallback/technical) |
| Settings Advisor | `/settings/advisor` | Edycja preferencji wpływających na sortowanie i routing kart |
| Onboarding wizard | `/onboarding` | 10 kroków konfigurujących domyślne autonomy, council, QSC, providers |
| Evidence Viewer | `/evidence` | Globalny katalog Evidence Pack (rozszerza inline Dialog z `/advisor`) |
| Governance | `/governance` | Council voting + policies (źródło `source: "council_vote"`) |
| Audit | `/audit` | Globalny audit trail (każda akcja na karcie generuje wpis `audit_trail_id`) |

### 10.4 Powiązana dokumentacja `docs/dokumentacja/`

- [`01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — opis modułu Advisor end-to-end.
- [`02_operational_manual.md`](../02_operational_manual.md) — runbooks operatora (incydenty, restart, chaos drills).
- [`03_governance_audit_compliance.md`](../03_governance_audit_compliance.md) — gates D3+, audit chain, compliance.
- [`04_dla_developera.md`](../04_dla_developera.md) — instrukcja dla developerów (uruchomienie, mock fallback, polling).
