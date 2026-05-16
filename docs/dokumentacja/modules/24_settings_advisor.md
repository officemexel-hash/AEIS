# 24. Advisor Settings — Konfigurator preferencji
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja warstwy frontend dla powierzchni `/settings/advisor`. Strona pozwala
> operatorowi edytować decyzje podjęte podczas wizarda onboarding po fakcie, bez
> konieczności ponownego przechodzenia przez 10 kroków. Każda sekcja mapuje się
> na jeden lub więcej kluczy w `advisor_preferences.preferences`. Zmiana preferencji
> typu *hard* (autonomy, blocked providers, funding enable) eskaluje do D3+ i wymaga
> potwierdzenia przez kartę typu `hard_learning_pending_confirmation` w feedzie.

## Spis treści

1. [Cel i URL](#1-cel-i-url)
2. [Komponenty UI](#2-komponenty-ui)
3. [Kontrolki i interakcje](#3-kontrolki-i-interakcje)
4. [Zarządzanie stanem](#4-zarządzanie-stanem)
5. [Integracja API](#5-integracja-api)
6. [Persistencja](#6-persistencja)
7. [Tryby i warianty](#7-tryby-i-warianty)
8. [Dostępność](#8-dostępność)
9. [Przepływy operatora](#9-przepływy-operatora)
10. [Cross-references](#10-cross-references)

---

## 1. Cel i URL

| Pole | Wartość |
|------|---------|
| Ścieżka | `/settings/advisor` |
| Plik źródłowy | `src/sylion-frontend/src/app/(app)/settings/advisor/page.tsx` |
| Komponent główny | `AdvisorSettingsPage` (default export) |
| Kontekst | warstwa **Advisor** (`/api/v1/advisor` w `mobile_gateway`) |
| Layout | `(app)` route group; lewy sidebar widoczny |
| Cel | edycja preferencji operatora po onboardingu, podgląd historii zmian |
| Persona | Operator (właściciel `operator_id`) — pełne uprawnienia do swoich preferencji |
| Maks. szerokość | `max-w-5xl` (centralna kolumna 1024 px) |

Surface ten jest *write-side* odpowiednikiem onboarding wizarda. Wszystkie reguły
walidacji i komponenty kroków `Step1Welcome..Step9Funding` są re-używane bezpośrednio
z folderu `src/sylion-frontend/src/components/wizard/`. Strona nie wymusza kolejności
ani komplecji — operator może edytować dowolną sekcję w izolacji, w przeciwieństwie
do `/onboarding`, gdzie kroki muszą być wypełniane sekwencyjnie.

Strona udostępnia dodatkowo **Audit history panel**, który pokazuje append-only log
zmian preferencji (`preferences_audit`) — ten log jest jedynym miejscem w UI, gdzie
operator widzi historyczne wartości oraz źródło zmiany (`user`, `wizard`, `soft_learning`,
`hard_learning_pending_confirmation`).

---

## 2. Komponenty UI

Strona ma trzy główne strefy:

```
┌─────────────────────────────────────────────────────────────┐
│ Header (title + "Audit history" toggle)                     │
├─────────────────────────────────────────────────────────────┤
│ MockBanner (jeśli source != "live")                         │
│ AuditHistoryPanel (toggle, opcjonalnie)                     │
│ Reset message banner (opcjonalnie)                          │
├─────────────────────────────────────────────────────────────┤
│ 9 sekcji rozwijanych (akordeon, każda re-used Step)         │
│   ├ Section 1. Welcome & goals    [Step1Welcome]            │
│   ├ Section 2. Provider API keys  [Step2Providers]          │
│   ├ Section 3. Budget defaults    [Step3Budget]             │
│   ├ Section 4. Domain default     [Step4Domain]             │
│   ├ Section 5. Default autonomy   [Step5Autonomy]           │
│   ├ Section 6. Council + judge    [Step6Council]            │
│   ├ Section 7. Quality/Speed/Cost [Step7QualitySpeedCost]   │
│   ├ Section 8. Trusted/blocked    [Step8TrustedBlocked]     │
│   └ Section 9. Funding Advisor    [Step9Funding]            │
└─────────────────────────────────────────────────────────────┘
```

### 2.1. Header

Definicja w liniach 101–119 pliku `page.tsx`. Komponenty:

| Element | Tag | Treść |
|---------|-----|-------|
| Eyebrow | `<p>` z ikoną `SettingsIcon` (Lucide) | "ADVISOR SETTINGS" |
| H1 | `<h1>` `text-2xl font-semibold` | "Setup configurator" |
| Sub-line | `<p>` `text-sm` | "Edit any onboarding decision later. Each section maps to one or more entries in `advisor_preferences.preferences`." |
| Re-run wizard link | `<Link>` z ikoną `ExternalLink` | href `/onboarding` |
| Audit toggle button | `<Button variant="outline" size="sm">` z ikoną `HistoryIcon` | "Audit history" |

Header jest `flex flex-wrap items-start justify-between gap-3` — na wąskich ekranach
button "Audit history" zawija się pod tytuł.

### 2.2. MockBanner

`<MockBanner source={source} />` (komponent `src/sylion-frontend/src/components/advisor/MockBanner.tsx`).
Renderuje się tylko gdy `source !== "live"`:

| `source` | Banner |
|----------|--------|
| `"live"` | (ukryty) |
| `"mock"` | ostrzeżenie żółte: "Backend Advisor unreachable; showing mock preferences" |
| `"cache"` | informacja niebieska: "Showing cached preferences (last fetched X ago)" |

### 2.3. AuditHistoryPanel

Toggle widget (linia 228–289). Renderuje się tylko gdy `auditOpen === true`.

| Element | Opis |
|---------|------|
| Header | "Log audytowy preferencji" + sub-line + przycisk "Odswież" |
| Error banner | `border-orange-400/30` jeśli backend zwrócił błąd |
| `<ul>` lista | 1.5 spacing, każdy entry `font-mono text-[11px]` |
| Entry | `changed_at` · `changed_by` (linia 1) → `preference_key` `change_type` `old_value` → `new_value` (linia 2) → `reason` (linia 3, opcjonalnie) |

Po otwarciu panel automatycznie ładuje dane przez `useEffect` (mount trigger).
Nie używa już danych demonstracyjnych (`mockAudit()` usunięte w sprint2 consolidated commit).
Przy błędzie backendu panel pokazuje pusty stan zamiast mock-danych.

### 2.4. Reset message banner

Banner pojawia się po kliknięciu "Reset {key}":

| Stan | Klasa | Tekst |
|------|-------|-------|
| Sukces | `border-sylion-amber/30 bg-sylion-amber/5` | "Preference {key} reset to system default." |
| Mock fallback | (ten sam styl) | "Backend unreachable; preference reset queued locally for {key}." |

Banner jest *non-dismissible* — znika dopiero przy kolejnej akcji (`setResetMessage(null)`
przed `handleSectionSave` lub kolejnym resetem).

### 2.5. Sekcje rozwijane

Każda sekcja jest komponentem `<Card>` z dwoma stanami: collapsed i expanded.

**Header sekcji (zawsze widoczny):**

| Element | Treść |
|---------|-------|
| Chevron | `ChevronDown` (otwarte) / `ChevronRight` (zamknięte) |
| Title | `<h2>` `text-sm font-semibold` z numerem (np. "1. Welcome & goals") |
| Description | `<p>` `text-xs text-muted-foreground` — np. "Operator identity, goals and usage cadence used to weight history-based recommendations." |
| Preference badges | `<Badge variant="outline">` z `font-mono` dla każdego `preferenceKeys[i]` (np. `operator_name`, `goals`, `usage_cadence`) |
| Right column (set-by) | "set by user" / "set by wizard" / "set by soft_learning" / "not set" |
| Right column (updated_at) | sformatowany timestamp z `fmtDateTime(new Date(updatedAt * 1000).toISOString())` |

**Body sekcji (po kliknięciu):**

```tsx
<div className="border-t border-border/50 bg-background p-4">
  <Step values={values} onChange={(patch) => saveStep(state.step, patch)} />
  <Separator className="my-4" />
  <div className="flex flex-wrap items-center justify-between gap-2">
    <div className="flex flex-wrap items-center gap-2">
      {/* Reset buttons per preferenceKey */}
      {/* Disable Funding (tylko sekcja 9) */}
    </div>
    <Button onClick={() => handleSectionSave(section)}>Save section</Button>
  </div>
</div>
```

Component `Step` to oryginalny komponent z folderu `wizard/`, otrzymujący
`values: Record<string, unknown>` (state.values z onboarding hooka) i `onChange`
callback delegujący do `saveStep(state.step, patch)`.

### 2.6. Tabela 9 sekcji

| ID | Tytuł | Step | preferenceKeys | Hard? |
|----|-------|------|----------------|-------|
| `welcome` | 1. Welcome & goals | `Step1Welcome` | `operator_name`, `goals`, `usage_cadence` | nie |
| `providers` | 2. Provider API keys | `Step2Providers` | `anthropic_api_key`, `openai_api_key`, `google_api_key`, `ollama_base_url` | nie |
| `budget` | 3. Budget defaults | `Step3Budget` | `cost_ceilings`, `budget_thresholds` | nie |
| `domain` | 4. Project domain default | `Step4Domain` | `default_project_domain` | nie |
| `autonomy` | 5. Default autonomy | `Step5Autonomy` | `autonomy_level` | **tak (D3+)** |
| `council` | 6. Council size + judge | `Step6Council` | `council_size`, `llm_judge_routing_override` | nie (soft) |
| `qsc` | 7. Quality / Speed / Cost | `Step7QualitySpeedCost` | `quality_speed_cost` | nie |
| `providers_pref` | 8. Trusted / blocked providers | `Step8TrustedBlocked` | `trusted_providers`, `blocked_providers` | **tak (D3+)** |
| `funding` | 9. Funding Advisor | `Step9Funding` | `funding_advisor_enabled`, `funding_countries`, `funding_token_budget_monthly` | **tak (D3+)** |

Hard-preference change generuje na backendzie kartę typu `hard_learning_pending_confirmation`
w advisor feedzie. Karta ta wymaga decyzji `accept` (konfirmacja zmiany)
albo `reject` (rollback do poprzedniej wartości). Patrz [`20_advisor_feed.md`](20_advisor_feed.md#hard-learning).

---

## 3. Kontrolki i interakcje

### 3.1. Kliknięcie nagłówka sekcji

```ts
function toggle(id: string) {
  setOpen((prev) => ({ ...prev, [id]: !prev[id] }));
}
```

Stan `open: Record<string, boolean>` — operator może mieć **wiele sekcji** otwartych
jednocześnie (akordeon nie jest exclusive). Pozwala na porównywanie wartości między
sekcjami, np. budget i autonomy.

### 3.2. Kliknięcie "Save section"

```ts
async function handleSectionSave(section: SectionDef) {
  setSavingId(section.id);
  setResetMessage(null);
  try {
    await saveStep(state.step, values);
    refresh();
  } finally {
    setSavingId(null);
  }
}
```

Disabled-state: `disabled={savingId === section.id}` blokuje wielokrotne kliki.
Tekst zmienia się na `"Saving…"` z ellipsis Unicode (U+2026). `refresh()` re-fetchuje
listę preferencji aby zaktualizować `set_by` i `updated_at` w nagłówku sekcji.

UWAGA: implementacja wywołuje `saveStep(state.step, values)` — **nie** `saveStep(section.step_number, ...)`.
Oznacza to, że operator otwierając sekcję 5 i klikając Save, faktycznie wysyła
patch dla aktualnego `state.step` z onboarding state. To jest **świadomy fallback**:
po onboardingu `state.step === 10`, więc backend obsługuje to jako "save all current
values", a per-step routing jest delegowany na backend.

### 3.3. Kliknięcie "Reset {key}"

```ts
async function handleResetKey(key: string) {
  setResetMessage(null);
  try {
    await advisorApi.resetPreference(MOCK_OPERATOR_ID, key);
    setResetMessage(`reset:${key}`);
    refresh();
  } catch {
    setResetMessage(`mock-reset:${key}`);
  }
}
```

Reset usuwa override operatora i przywraca wartość systemową (np. `cost_ceilings`
wraca do `{ low: 0.05, medium: 0.20, high: 1.00, critical: 5.00 }`). Backend wykonuje
DELETE w `advisor_preferences.preferences` i append do `preferences_audit` z
`change_type='DELETE'`, `new_value=null`, `changed_by='operator'`, `reason='reset_to_default'`.

### 3.4. Kliknięcie "Disable Funding module"

```tsx
{section.preferenceKeys.includes("funding_advisor_enabled") ? (
  <Button onClick={() => saveStep(state.step, { funding_advisor_enabled: false })}>
    <Power className="mr-1 h-3.5 w-3.5" />
    Disable Funding module
  </Button>
) : null}
```

Specjalny shortcut tylko w sekcji 9. Wysyła patch `{ funding_advisor_enabled: false }`,
który backend interpretuje jako D3+ change i wysyła kartę `hard_learning_pending_confirmation`
do feedu. Operator musi potwierdzić wyłączenie modułu w `/advisor`. Color: `text-orange-400`
sygnalizuje destruktywny charakter akcji.

### 3.5. Kliknięcie "Audit history" w nagłówku

```ts
<Button onClick={() => setAuditOpen((v) => !v)}>
```

Toggle panelu `AuditHistoryPanel`. Po otwarciu dane są ładowane automatycznie
(mount trigger — `useEffect(() => { load(); }, [])`). Nie ma fazy
"demo data" — panel startuje z pustą listą i loading spinner-em.

### 3.6. Kliknięcie "Odswież" w AuditHistoryPanel

```ts
async function load() {
  setLoading(true);
  setError(null);
  try {
    const res = await advisorApi.preferenceAudit(MOCK_OPERATOR_ID);
    setEntries(res.entries);
  } catch (e) {
    setError(e instanceof Error ? e.message : String(e));
    setEntries([]);
  } finally {
    setLoading(false);
  }
}
```

Wywoływane automatycznie przy mount (przez `useEffect`) i ręcznie po kliknięciu "Odswież".
Disabled-state: `disabled={loading}`, tekst zmienia się na "Ladowanie…". Przy błędzie
backendu pokazuje banner pomarańczowy z komunikatem błędu; lista pozostaje pusta
(brak fallbacku na mock-dane — sprint2 usunął `mockAudit()`).

### 3.7. Kliknięcie "re-run wizard"

`<Link href="/onboarding">` — przeniesienie do wizarda. Wizard wykryje istniejące
preferencje i zaproponuje pre-populację każdego kroku. Patrz
[`21_onboarding_wizard.md`](21_onboarding_wizard.md).

---

## 4. Zarządzanie stanem

### 4.1. Hooki React

```ts
const { state, saveStep } = useOnboarding();
const { preferences, source, refresh } = usePreferences(MOCK_OPERATOR_ID);
const [open, setOpen] = useState<Record<string, boolean>>({});
const [auditOpen, setAuditOpen] = useState(false);
const [savingId, setSavingId] = useState<string | null>(null);
const [resetMessage, setResetMessage] = useState<string | null>(null);
```

| Stan | Typ | Pochodzenie | Cel |
|------|-----|-------------|-----|
| `state` | `OnboardingState` | `useOnboarding()` | values + step + completed/skipped flags |
| `preferences` | `AdvisorPreference[]` | `usePreferences(operatorId)` | lista key/value z DB |
| `source` | `'live' \| 'mock' \| 'cache'` | `usePreferences()` | sygnalizuje stan połączenia |
| `refresh` | `() => void` | `usePreferences()` | wymusza re-fetch listy |
| `open` | `Record<string, boolean>` | `useState({})` | mapa "section.id → expanded" |
| `auditOpen` | `boolean` | `useState(false)` | toggle panelu audit |
| `savingId` | `string \| null` | `useState(null)` | loading state per-section |
| `resetMessage` | `string \| null` | `useState(null)` | komunikat banner reset (`reset:X` / `mock-reset:X`) |

### 4.2. Memoizacja

```ts
const indexed = useMemo(() => {
  const map = new Map<string, (typeof preferences)[number]>();
  for (const p of preferences) map.set(p.preference_key, p);
  return map;
}, [preferences]);
```

`indexed` to mapa `preference_key → AdvisorPreference`, używana do szybkiego
wyciągania `set_by` i `updated_at` per sekcja. Re-build tylko gdy `preferences`
się zmieni.

### 4.3. Wyliczanie `setBy` i `updatedAt`

Per sekcja:

```ts
const setBy = section.preferenceKeys
  .map((k) => indexed.get(k)?.set_by)
  .filter(Boolean)
  .join(" · ");
const updatedAt = section.preferenceKeys
  .map((k) => indexed.get(k)?.updated_at)
  .filter((v): v is number => typeof v === "number")
  .sort((a, b) => b - a)[0];
```

`setBy` łączy unikalne źródła ustawień separatorem ` · ` (np. `"user · soft_learning"`
gdy `council_size` ustawiony przez `soft_learning` a `llm_judge_routing_override`
przez `user`). `updatedAt` to **najnowszy** timestamp z grupy (deskendingowy sort + first).

### 4.4. AuditHistoryPanel state

```ts
const [entries, setEntries] = useState<Array<Record<string, unknown>>>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

Stan startowy: pusta lista (`[]`) i `loading=true` — natychmiast uruchamia spinner.
`useEffect(() => { load(); }, [])` wyzwala ładowanie przy mount.
`mockAudit()` usunięty w sprint2 consolidated commit (9c45020).

---

## 5. Integracja API

### 5.1. Endpointy

| Metoda | Endpoint | Hook / wywołanie | Cel |
|--------|----------|------------------|-----|
| GET | `/api/v1/advisor/preferences?operator_id={id}` | `usePreferences()` | Pobierz wszystkie preferencje operatora |
| GET | `/api/v1/advisor/onboarding/state?operator_id={id}` | `useOnboarding()` | Pobierz aktualny stan (values + step) |
| POST | `/api/v1/advisor/onboarding/step/{n}` | `saveStep(step, patch)` | Zapis patch do step n |
| POST | `/api/v1/advisor/preferences/{key}/reset?operator_id={id}` | `advisorApi.resetPreference()` | Reset preferencji do default |
| GET | `/api/v1/advisor/preferences/audit?operator_id={id}` | `advisorApi.preferenceAudit()` | Pobierz historię zmian |

### 5.2. Schema `AdvisorPreference`

```ts
interface AdvisorPreference {
  operator_id: string;
  preference_key: string;          // np. "council_size"
  value: unknown;                  // dowolny JSON (number, string, object, array)
  set_by: 'user' | 'wizard' | 'soft_learning' | 'hard_learning' | 'system';
  is_hard_preference: boolean;     // jeśli true, zmiana wymaga D3+
  updated_at: number;              // unix epoch (s)
  change_count: number;            // ile razy zmieniono od insercji
}
```

### 5.3. Schema `PreferenceAuditEntry`

```ts
interface PreferenceAuditEntry {
  audit_id: string;
  operator_id: string;
  preference_key: string;
  change_type: 'INSERT' | 'UPDATE' | 'DELETE';
  old_value: unknown | null;
  new_value: unknown | null;
  changed_by: 'user' | 'wizard' | 'soft_learning' | 'hard_learning_pending_confirmation' | 'operator' | 'system';
  changed_at: string;              // ISO 8601
  reason: string | null;           // np. "rolling acceptance rate ≥ 0.7"
  decision_card_id: string | null; // jeśli zmiana z hard_learning, wskazuje na kartę
}
```

### 5.4. Przykładowy request — Save section 5 (autonomy)

```http
POST /api/v1/advisor/onboarding/step/10 HTTP/1.1
Content-Type: application/json
X-Operator-Id: op_demo_2026

{
  "operator_name": "Razor",
  "goals": ["product", "research"],
  "usage_cadence": "daily",
  "anthropic_api_key": "sk-ant-***",
  "openai_api_key": "sk-***",
  "ollama_base_url": "http://localhost:11434",
  "cost_ceilings": { "low": 0.10, "medium": 0.40, "high": 1.60, "critical": 6.00 },
  "default_project_domain": "research",
  "autonomy_level": "auto",       // ← zmiana z "suggest" na "auto" — D3+ trigger
  "council_size": 4,
  "llm_judge_routing_override": null,
  "quality_speed_cost": { "quality": 0.5, "speed": 0.3, "cost": 0.2 },
  "trusted_providers": ["anthropic"],
  "blocked_providers": [],
  "funding_advisor_enabled": true,
  "funding_countries": ["PL", "EU"],
  "funding_token_budget_monthly": 50000
}
```

### 5.5. Response — D3+ change pending

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "status": "pending_hard_confirmation",
  "operator_id": "op_demo_2026",
  "pending_changes": [
    {
      "preference_key": "autonomy_level",
      "old_value": "suggest",
      "new_value": "auto",
      "decision_card_id": "card_hl_20260426_a1b2c3"
    }
  ],
  "soft_changes_applied": [
    "operator_name", "goals", "usage_cadence",
    "anthropic_api_key", "openai_api_key", "ollama_base_url",
    "cost_ceilings", "default_project_domain",
    "council_size", "llm_judge_routing_override",
    "quality_speed_cost",
    "funding_countries", "funding_token_budget_monthly"
  ]
}
```

Frontend nie wyświetla tego dialogu inline — operator zobaczy kartę
`hard_learning_pending_confirmation` w `/advisor` lub w `AdvisorBubble`. Patrz
[`20_advisor_feed.md`](20_advisor_feed.md#hard-learning).

### 5.6. Response — Reset preference

```http
POST /api/v1/advisor/preferences/cost_ceilings/reset?operator_id=op_demo_2026

HTTP/1.1 200 OK
{
  "status": "reset",
  "preference_key": "cost_ceilings",
  "previous_value": { "low": 0.10, "medium": 0.40, "high": 1.60, "critical": 6.00 },
  "default_value": { "low": 0.05, "medium": 0.20, "high": 1.00, "critical": 5.00 },
  "audit_id": "aud_20260426_xyz"
}
```

### 5.7. Response — Audit log

```http
GET /api/v1/advisor/preferences/audit?operator_id=op_demo_2026&limit=50

HTTP/1.1 200 OK
{
  "operator_id": "op_demo_2026",
  "entries": [
    {
      "audit_id": "aud_20260426_xyz",
      "preference_key": "council_size",
      "change_type": "UPDATE",
      "old_value": 5,
      "new_value": 4,
      "changed_by": "soft_learning",
      "changed_at": "2026-04-26T11:42:18Z",
      "reason": "rolling acceptance rate ≥ 0.7 over last 5 council recommendations",
      "decision_card_id": null
    },
    {
      "audit_id": "aud_20260426_abc",
      "preference_key": "autonomy_level",
      "change_type": "UPDATE",
      "old_value": "manual",
      "new_value": "suggest",
      "changed_by": "user",
      "changed_at": "2026-04-26T09:00:00Z",
      "reason": "wizard step 5 completed",
      "decision_card_id": null
    }
  ],
  "total": 2,
  "source": "live"
}
```

### 5.8. Error handling

| Kod | Sytuacja | UI |
|-----|----------|-----|
| 400 | Invalid value (np. `council_size: 13`) | Banner czerwony przy sekcji "Validation: council_size must be 1-11" |
| 401 | Brak `X-Operator-Id` lub niepoprawny token | redirect do `/auth` (handled by axios interceptor) |
| 403 | Operator próbuje zmienić preferencje innego user | Banner czerwony "Forbidden: cannot modify other operator's preferences" |
| 409 | Konflikt (np. równoległa zmiana z innego device) | Banner amber "Conflict: refresh and re-apply" + auto-`refresh()` |
| 429 | Rate limit | Banner amber "Rate limited; try again in {retry-after}s" |
| 500 | Internal error | Banner czerwony + fallback na mock data |
| Network | Backend unreachable | `MockBanner` `source="mock"` + reset action queued lokalnie (`mock-reset:` prefix) |

---

## 6. Persistencja

### 6.1. Tabela `advisor_preferences.preferences`

```sql
CREATE TABLE advisor_preferences.preferences (
  operator_id TEXT NOT NULL,
  preference_key TEXT NOT NULL,
  value JSONB NOT NULL,
  set_by TEXT NOT NULL CHECK (set_by IN ('user','wizard','soft_learning','hard_learning','system')),
  is_hard_preference BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  change_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (operator_id, preference_key)
);
```

UPSERT z `ON CONFLICT (operator_id, preference_key) DO UPDATE` przy każdym save_step.

### 6.2. Tabela `advisor_preferences.preferences_audit`

```sql
CREATE TABLE advisor_preferences.preferences_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id TEXT NOT NULL,
  preference_key TEXT NOT NULL,
  change_type TEXT NOT NULL CHECK (change_type IN ('INSERT','UPDATE','DELETE')),
  old_value JSONB,
  new_value JSONB,
  changed_by TEXT NOT NULL,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason TEXT,
  decision_card_id TEXT
);
CREATE INDEX idx_audit_operator_changedat ON advisor_preferences.preferences_audit(operator_id, changed_at DESC);
```

Append-only (no UPDATE/DELETE policy enforced by DB role).

### 6.3. Cache w przeglądarce

| Klucz | Storage | Cel | TTL |
|-------|---------|-----|-----|
| `sylion.advisor.preferences.{operatorId}` | localStorage | cache list `AdvisorPreference[]` | 24 h |
| `sylion.advisor.preferences.audit.{operatorId}` | sessionStorage | cache log audit | tylko sesja |
| `sylion.advisor.onboarding` | localStorage | wizard state (values + step) | bez wygasania |

Cache wpisów jest **invalidated** po każdym `saveStep`, `resetPreference`, lub
`disable Funding`.

### 6.4. Server-side cache

`mobile_gateway` używa Redis cache `advisor:preferences:{operatorId}` z TTL 60 s.
Invalidation hook na każdej operacji write. `preferences_audit` nigdy nie jest
cachowany — zawsze fresh read z DB.

---

## 7. Tryby i warianty

### 7.1. `source` (preferences fetch state)

| `source` | Banner | Behavior |
|----------|--------|----------|
| `"live"` | brak | normalny tryb, save działa, refresh hituje backend |
| `"mock"` | `MockBanner` żółty | save queued lokalnie, reset queued lokalnie (banner `mock-reset:`) |
| `"cache"` | `MockBanner` niebieski | save próbuje hitnąć backend i upgradować na live |

### 7.2. Section expanded vs collapsed

| State | Visible elements |
|-------|------------------|
| collapsed | header + chevron right + badges + setBy/updatedAt |
| expanded | header + chevron down + Step component + Separator + Reset buttons + Save button |

Wszystkie sekcje mogą być otwarte równolegle. Brak limitu.

### 7.3. AuditHistoryPanel

| State | Visible |
|-------|---------|
| `auditOpen=false` | brak |
| `auditOpen=true`, loading | spinner "Ladowanie…" |
| `auditOpen=true`, sukces | rzeczywiste entries z DB |
| `auditOpen=true`, error | error banner pomarańczowy + pusta lista (brak mock fallbacku) |

### 7.4. savingId

| `savingId` | Effect |
|-----------|--------|
| `null` | wszystkie sekcje pokazują "Save section" |
| `"welcome"` (np.) | sekcja `welcome` pokazuje "Saving…" i `disabled`; pozostałe normalne |

### 7.5. resetMessage

| Format | Significance |
|--------|--------------|
| `"reset:cost_ceilings"` | Backend response 200, banner `border-sylion-amber/30` |
| `"mock-reset:cost_ceilings"` | Backend nieosiągalny, banner amber + tekst "Backend unreachable; preference reset queued locally" |
| `null` | Banner ukryty |

### 7.6. Hard preferences vs soft

| Sekcja | Klucze | Zmiana wymaga D3+? |
|--------|--------|---------------------|
| 5. Autonomy | `autonomy_level` | tak |
| 8. Trusted/blocked | `trusted_providers`, `blocked_providers` | tak |
| 9. Funding | `funding_advisor_enabled` | tak (włącz/wyłącz) |
| 9. Funding | `funding_countries`, `funding_token_budget_monthly` | nie (soft) |
| Pozostałe | wszystkie | nie (soft) |

W przyszłości backend może dynamicznie zmienić `is_hard_preference` (np. tightening
governance) — frontend nie hardcoduje tej listy, tylko pokazuje banner z odpowiedzi
backendu po `saveStep`.

### 7.7. Tryby interfejsu — Operator vs Techniczny

Sprint 2 (2026-04-26) wprowadził system trybów interfejsu sterowany przez hook `useAdvisorMode`.
Tryb wpływa na wygląd całego układu aplikacji (sidebar, top bar, badge) — nie tylko na stronę `/settings/advisor`.

#### Dwa tryby

| Tryb | Badge | Kolor | Opis |
|------|-------|-------|------|
| `operator` (domyślny) | `UserCog` + "Operator" | niebieski (`blue-500/15`) | Uproszczony interfejs. Sidebar pokazuje tylko 4 sekcje operatorskie. |
| `technical` | `Wrench` + "Techniczny" | bursztynowy (`amber-500/15`) | Pełny dostęp. Sidebar rozszerza się o sekcje developerskie. |

#### Hook `useAdvisorMode`

Plik: `src/sylion-frontend/src/components/layout/useAdvisorMode.ts`

```typescript
export type AdvisorMode = "operator" | "technical";

export function useAdvisorMode(): {
  mode: AdvisorMode;
  setMode: (next: AdvisorMode) => void;
  toggle: () => void;
}
```

Mechanika:
- **Persystencja:** `localStorage` pod kluczem `sylion.advisor.mode`
- **Synchronizacja:** Custom event `sylion:advisor-mode` (CustomEvent) — broadcast do wszystkich listenerów w tej samej karcie
- **Domyślna wartość:** `"operator"` (przy braku klucza w localStorage)
- **SSR-safe:** sprawdzenie `typeof window === "undefined"` chroni przed błędem po stronie serwera

#### Komponent `ModeBadge`

Plik: `src/sylion-frontend/src/components/layout/ModeBadge.tsx`

Wyświetla wizualny wskaźnik aktualnego trybu. Zintegrowany z Tooltip (Radix) — tooltip pokazuje opis trybu przy najechaniu.

```tsx
// operator: niebieski rounded badge
<div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium bg-blue-500/15 text-blue-300 border-blue-500/30">
  <UserCog className="size-3.5" />
  <span>Operator</span>
</div>

// technical: bursztynowy rounded badge
<div className="... bg-amber-500/15 text-amber-300 border-amber-500/30">
  <Wrench className="size-3.5" />
  <span>Techniczny</span>
</div>
```

Tooltip:
- Operator: `"Tryb operatora — uproszczony interfejs dla codziennej pracy"`
- Techniczny: `"Tryb techniczny — pełen dostęp dla deweloperów"`

#### Komponent `ModeSwitcher`

Plik: `src/sylion-frontend/src/components/layout/ModeSwitcher.tsx`

Przełącznik trybu umieszczony w `TopCommandBar`. Wywołuje `toggle()` z `useAdvisorMode()`.
Zmiana trybu rozgłasza zdarzenie `sylion:advisor-mode` — sidebar i `ModeBadge` reagują
natychmiast bez przeładowania strony.

#### Pliki CSS trybu

| Plik | Tryb | Co zmienia |
|------|------|-----------|
| `src/sylion-frontend/src/styles/operator-mode.css` | `operator` | Ukrywa sekcje `.technical-only`, upraszcza spacing i typografię nav |
| `src/sylion-frontend/src/styles/technical-mode.css` | `technical` | Odkrywa `.technical-only`, dodaje dodatkowe granice i metadata w nav |

Klasy CSS zastosowane przez layout:
- Tryb operatora: `body` ma klasę `mode-operator` (dodawaną przez `layout.tsx`)
- Tryb techniczny: klasa `mode-technical`

#### Sekcje sidebar per tryb

W trybie `operator` lewy sidebar (`AppSidebar`) pokazuje 4 sekcje:

| Sekcja | Elementy |
|--------|---------|
| Doradca | Live Feed, Ustawienia doradcy |
| Projekty | Lista projektów, Nowy projekt |
| Decyzje | D-ladder, Głosowanie Rady, Evidence Pack |
| Konfiguracja | Środowisko, Orkiestracja, Funding, Budget |

W trybie `technical` sidebar rozszerza się o dodatkowe pozycje developerskie (sekcje
`.technical-only`): moduły backend, wewnętrzne health-checki, raw API docs.

---

## 8. Dostępność

### 8.1. Klawiatura

| Klawisz | Akcja |
|---------|-------|
| `Tab` / `Shift+Tab` | Nawigacja między sekcjami i kontrolkami |
| `Space` / `Enter` (na nagłówku sekcji) | Toggle sekcji (Radix `<button>` semantyka) |
| `Enter` (na "Save section") | Trigger save |
| `Esc` | (brak globalnego — modale Step mają własne) |

Audit panel również w pełni nawigowalny klawiaturą (button "Reload").

### 8.2. ARIA

- Header sekcji to `<button type="button">` — natywnie focusable i wymawiane przez NVDA/JAWS/VoiceOver.
- Brak explicite `aria-expanded` w tym MVP (TODO: dodać `aria-expanded={isOpen}` i `aria-controls={section.id + '-body'}`).
- Reset buttons: `<Button variant="ghost" size="sm">` z czytelnym tekstem "Reset {key}".
- Disable Funding: `<Button>` z tekstem widocznym + ikoną Power; ikona jest dekoracyjna.

### 8.3. Kontrast i kolory

| Element | Foreground | Background | WCAG AA |
|---------|-----------|------------|---------|
| Header section title | `foreground` | `card` | spełnione |
| Description | `muted-foreground` | `card` | spełnione (4.5:1+) |
| Reset button | `foreground` (ghost) | `transparent` | spełnione |
| Disable Funding | `text-orange-400` | `transparent` | spełnione w dark mode |
| Reset banner | `text-sylion-amber` | `bg-sylion-amber/5` | spełnione |
| Set-by metadata | `muted-foreground` `text-[10px]` | `card` | granica AA — używamy uppercase + tracking dla legibility |

### 8.4. Reduced motion

`framer-motion` `initial/animate` z `transition={{ duration: 0.2 }}` honoruje
`prefers-reduced-motion` automatycznie (built-in `MotionConfig` na poziomie aplikacji).

### 8.5. Screen reader hints

Lista sekcji jest `<div className="space-y-3">` z 9 `<motion.div>`. Każdy `<Card>` zawiera
`<button>` jako pierwszy focusable element. Kolejność tabów jest deterministyczna:
section1 → section2 → ... → section9.

Po expanded każda sekcja dodaje 3-N kolejnych focusable elementów (kontrolki `Step`,
reset buttons, save button). Operator może `Shift+Tab` z powrotem do header.

---

## 9. Przepływy operatora

### 9.1. Edycja autonomy z manual na auto (D3+ flow)

1. Operator wchodzi w `/settings/advisor`.
2. Przewija do **5. Default autonomy** i klika header — sekcja się rozwija.
3. W komponencie `Step5Autonomy` operator wybiera radio "Auto execution" (z "Manual review").
4. Frontend wywołuje `saveStep(state.step, { autonomy_level: 'auto' })` (lokalnie, bez request do backendu — jest to typo w `Step5`'s `onChange` propagacja).
5. Operator klika **"Save section"**.
6. Frontend wysyła `POST /api/v1/advisor/onboarding/step/10` z całym values payload.
7. Backend:
   a. Wykrywa, że `autonomy_level` jest hard-pref i jego wartość się zmieniła.
   b. NIE persiści wartości w `preferences` (jeszcze).
   c. Zapisuje pending entry w `preferences_audit` z `decision_card_id=card_hl_xyz` i `changed_by='hard_learning_pending_confirmation'`.
   d. Tworzy advisor card typu `hard_learning_pending_confirmation` z action `accept` / `reject`.
   e. Zwraca `202 Accepted` z `pending_changes`.
8. Frontend pokazuje toast / banner: "Autonomy change pending operator confirmation. See `/advisor` feed."
9. Operator nawiguje do `/advisor`.
10. Widzi kartę "Hard preference change: autonomy_level manual → auto. Confirm?".
11. Klika **Accept** w karcie → backend persisti `autonomy_level='auto'` w `preferences` i append do audit `change_type='UPDATE'`, `changed_by='hard_learning_confirmed'`.
12. Frontend `/settings/advisor` po następnym refresh pokazuje `set_by: hard_learning` w nagłówku sekcji 5.

### 9.2. Reset cost_ceilings do default

1. Operator wchodzi w `/settings/advisor`.
2. Otwiera sekcję **3. Budget defaults**.
3. Widzi w nagłówku "set by user" — wartości są customowe.
4. Klika `<Button variant="ghost">Reset cost_ceilings</Button>`.
5. Frontend wywołuje `advisorApi.resetPreference(MOCK_OPERATOR_ID, 'cost_ceilings')`.
6. Backend:
   a. Pobiera obecną wartość z `preferences`.
   b. DELETE FROM `preferences` WHERE operator_id, preference_key.
   c. INSERT INTO `preferences_audit` (`change_type='DELETE'`, `old_value`, `new_value=null`, `changed_by='operator'`, `reason='reset_to_default'`).
   d. Zwraca `200 OK` z `default_value`.
7. Frontend ustawia `resetMessage="reset:cost_ceilings"`.
8. Banner: "Preference cost_ceilings reset to system default."
9. `refresh()` re-fetchuje listę preferencji — sekcja 3 teraz pokazuje "not set" w nagłówku.
10. Następne LLM judge call używa default ceilings: `{ low: 0.05, medium: 0.20, high: 1.00, critical: 5.00 }`.

### 9.3. Wyłączenie modułu Funding Advisor

1. Operator wchodzi w `/settings/advisor`.
2. Otwiera sekcję **9. Funding Advisor**.
3. Klika `<Button className="text-orange-400">Disable Funding module</Button>`.
4. Frontend wywołuje `saveStep(state.step, { funding_advisor_enabled: false })` (lokalnie).
5. Operator klika **"Save section"** (potwierdzenie tej akcji wymagane).
6. Frontend `POST /api/v1/advisor/onboarding/step/10`.
7. Backend wykrywa zmianę `funding_advisor_enabled: true → false` jako hard-pref.
8. Tworzy kartę `hard_learning_pending_confirmation` w feedzie z polem `impact: "Funding Advisor module will stop polling deadlines and grants. All scheduled funding card jobs will be cancelled."`.
9. Operator nawiguje do `/advisor`, klika **Accept** w karcie.
10. Backend:
    a. UPDATE `preferences` SET `value=false` WHERE `preference_key='funding_advisor_enabled'`.
    b. Cancel all scheduled jobs `aeis.funding.deadline_check`.
    c. Append do `preferences_audit`.
11. Frontend `/settings/advisor` przy następnej wizycie: sekcja 9 ma badge "DISABLED" + niedostępny `Step9Funding` (komponent renderuje read-only fallback).

### 9.4. Przeglądanie historii zmian

1. Operator klika **"Audit history"** w prawym górnym rogu.
2. Panel otwiera się i automatycznie zaczyna ładować dane (spinner "Ladowanie…").
3. Dane pojawiają się bez konieczności kliknięcia "Odswież".
4. Frontend wywołuje `advisorApi.preferenceAudit(MOCK_OPERATOR_ID)`.
5. Backend zwraca prawdziwy log (np. 47 wpisów).
6. Panel renderuje `<ul>` z każdym wpisem w formacie:

   ```
   2026-04-26 11:42:18    soft_learning
   council_size UPDATE 5 → 4
   rolling acceptance rate ≥ 0.7 over last 5 council recommendations
   ```
7. Operator może zobaczyć:
   - Kto zmienił (`user`, `wizard`, `soft_learning`, `hard_learning_pending_confirmation`).
   - Wartość przed i po.
   - Powód (np. "wizard step 5 completed", "rolling acceptance rate ≥ 0.7").
8. Brak filtrów, paginacji, sortowania w MVP — log jest pre-sorted DESC po `changed_at`.

### 9.5. Zmiana wielu preferencji jednocześnie

1. Operator otwiera sekcje 3 (Budget), 6 (Council), 7 (Quality/Speed/Cost) jednocześnie.
2. Edytuje wartości w trzech sekcjach (każda zmiana propagowana do `state.values` przez `saveStep` z onChange).
3. Klika **"Save section"** w sekcji 3.
4. Frontend wysyła **całość** `state.values` (nie tylko delta sekcji 3) — backend wykonuje upsert na każdy zmieniony klucz.
5. UPSERT na `cost_ceilings`, `budget_thresholds`, `council_size`, `quality_speed_cost`. Każdy oddzielny audit entry.
6. `refresh()` re-fetchuje listę.
7. Wszystkie trzy sekcje teraz pokazują "set by user" + nowy `updated_at`.

### 9.6. Re-run wizard po zmianie strategii

1. Operator decyduje, że chce zmienić "goals" z `["product"]` na `["product", "research", "compliance"]`.
2. Zamiast edytować sekcję 1 z 9 po kolei, klika **"re-run wizard"** w nagłówku.
3. Nawigacja do `/onboarding`. Wizard wykrywa istniejące preferences (`source: 'live'`, `state.completed: true`).
4. Banner w wizardie: "You completed onboarding on 2026-04-21. Re-running will let you adjust answers; existing values are pre-filled."
5. Operator przechodzi przez 10 kroków, zmienia goals.
6. Klika "Complete" w ostatnim kroku.
7. Backend wykonuje `POST /api/v1/advisor/onboarding/complete` z całym values.
8. Hard prefs (autonomy, trusted/blocked, funding_enabled) jeśli zmienione — pending confirmation.
9. Operator wraca do `/settings/advisor`, widzi `set_by: wizard` na zmienionych preferencjach.

---

## 10. Cross-references

### 10.1. Powiązane surfaces

| Surface | Plik dokumentacji | Relacja |
|---------|-------------------|---------|
| `/advisor` | [`20_advisor_feed.md`](20_advisor_feed.md) | Hard-pref changes generują karty `hard_learning_pending_confirmation` w feedzie |
| `/onboarding` | [`21_onboarding_wizard.md`](21_onboarding_wizard.md) | Settings re-używa wszystkich `Step1..Step9` komponentów + `useOnboarding()` hook |
| `/projects/[id]/lifecycle` | [`22_lifecycle_dashboard.md`](22_lifecycle_dashboard.md) | autonomy_level ustawiony tu wpływa na default action mode w lifecycle hooks |
| `/dashboard/operator-monitor` | [`23_operator_monitor.md`](23_operator_monitor.md) | Subscription advisor banner czyta `funding_advisor_enabled` z preferences |
| `/audit` | [`27_audit_viewer.md`](27_audit_viewer.md) | preferences_audit jest osobna od `aeis.audit_events` — nie miesza się w global audit viewer |

### 10.2. Powiązane backend modules

| Moduł | Folder | Rola |
|-------|--------|------|
| Mobile gateway | `src/sylion-pipeline/sylion/api/mobile_gateway/` | Endpoint `/api/v1/advisor/preferences*` |
| Self-limitation | `src/sylion-pipeline/sylion/aeis/self_limitation.py` | Czyta `cost_ceilings` z preferences |
| LLM Judge | `src/sylion-pipeline/sylion/judge/` | Czyta `llm_judge_routing_override`, `quality_speed_cost`, `trusted_providers`, `blocked_providers` |
| Soft learning loop | `src/sylion-pipeline/sylion/advisor/soft_learning.py` | Updateuje `council_size` automatycznie na podstawie acceptance rate (changed_by='soft_learning') |
| Hard learning loop | `src/sylion-pipeline/sylion/advisor/hard_learning.py` | Tworzy karty `hard_learning_pending_confirmation` |
| Funding scheduler | `src/sylion-pipeline/sylion/funding/scheduler.py` | Czyta `funding_advisor_enabled`, cancel jobs gdy zmienione na false |

### 10.3. Powiązane komponenty wizard

| Komponent | Plik |
|-----------|------|
| `Step1Welcome` | `src/sylion-frontend/src/components/wizard/Step1Welcome.tsx` |
| `Step2Providers` | `src/sylion-frontend/src/components/wizard/Step2Providers.tsx` |
| `Step3Budget` | `src/sylion-frontend/src/components/wizard/Step3Budget.tsx` |
| `Step4Domain` | `src/sylion-frontend/src/components/wizard/Step4Domain.tsx` |
| `Step5Autonomy` | `src/sylion-frontend/src/components/wizard/Step5Autonomy.tsx` |
| `Step6Council` | `src/sylion-frontend/src/components/wizard/Step6Council.tsx` |
| `Step7QualitySpeedCost` | `src/sylion-frontend/src/components/wizard/Step7QualitySpeedCost.tsx` |
| `Step8TrustedBlocked` | `src/sylion-frontend/src/components/wizard/Step8TrustedBlocked.tsx` |
| `Step9Funding` | `src/sylion-frontend/src/components/wizard/Step9Funding.tsx` |

### 10.4. Powiązane hooki

| Hook | Plik |
|------|------|
| `useOnboarding()` | `src/sylion-frontend/src/lib/hooks/advisor.ts` |
| `usePreferences()` | `src/sylion-frontend/src/lib/hooks/advisor.ts` |
| `useAdvisorMode()` | `src/sylion-frontend/src/components/layout/useAdvisorMode.ts` |

### 10.5. Powiązane utilities i typy

| Symbol | Plik |
|--------|------|
| `advisorApi` (klient REST) | `src/sylion-frontend/src/lib/api/advisor.ts` |
| `MOCK_OPERATOR_ID` | `src/sylion-frontend/src/lib/api/advisor.ts` |
| `MockBanner` | `src/sylion-frontend/src/components/advisor/MockBanner.tsx` |
| `ModeBadge` | `src/sylion-frontend/src/components/layout/ModeBadge.tsx` |
| `ModeSwitcher` | `src/sylion-frontend/src/components/layout/ModeSwitcher.tsx` |
| `AppSidebar` | `src/sylion-frontend/src/components/layout/AppSidebar.tsx` |
| `operator-mode.css` | `src/sylion-frontend/src/styles/operator-mode.css` |
| `technical-mode.css` | `src/sylion-frontend/src/styles/technical-mode.css` |
| `fmtDateTime` | `src/sylion-frontend/src/lib/utils.ts` |
| `cn` (classnames merge) | `src/sylion-frontend/src/lib/utils.ts` |

### 10.6. Powiązane dokumenty governance

| Dokument | Wpływ |
|----------|-------|
| AEIS Canonical Full Model 2026-04-24 | Definiuje 12 warstw, hard vs soft preferences, D3+ escalation |
| Decision Gates & Governance | Każda zmiana hard-pref jest D3 minimum, wymaga Evidence Pack przy D5 (`d5_full` template) |
| Council canonical | `council_size` i `llm_judge_routing_override` mapują się na 9 ról i 5 rang |
| Idea lifecycle canonical 11-state | Nie dotyczy bezpośrednio — settings nie operują na ideach |

### 10.7. Powiązane testy

| Test | Plik |
|------|------|
| AdvisorSettingsPage smoke | `src/sylion-frontend/src/app/(app)/settings/advisor/__tests__/page.test.tsx` (TBD) |
| `usePreferences` hook | `src/sylion-frontend/src/lib/hooks/__tests__/advisor.test.ts` |
| `advisorApi.preferenceAudit` | `src/sylion-frontend/src/lib/api/__tests__/advisor.test.ts` |
| Backend e2e: hard pref change → card → accept | `src/sylion-pipeline/tests/e2e/test_hard_learning_loop.py` |

### 10.8. Open questions / TODO

- Dodać `aria-expanded` i `aria-controls` na header sekcji.
- Dodać paginację i filtry do `AuditHistoryPanel` (currently no limit).
- Rozważyć blokowanie Save dopóki sekcja ma walidacyjne błędy w komponencie Step.
- Pre-flight call do backend aby pokazać "ta zmiana wygeneruje hard-pref card" PRZED kliknięciem Save (zmniejszenie surprise).
- Eksport preferences i audit log do JSON (download button).
- Compare with "system default" view per sekcja (np. badge "modified from default").
