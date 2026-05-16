# Surface: Onboarding Wizard (`/onboarding`)
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dziesięciokrokowy wizard pierwszego uruchomienia SYLION AEIS. Konfiguruje wszystkie kluczowe preferencje operatora, klucze API, budżety, autonomię, Radę i opcjonalny moduł Funding.

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
| Route | `/onboarding` |
| Plik strony | `src/sylion-frontend/src/app/(app)/onboarding/page.tsx` |
| Plik layoutu | `src/sylion-frontend/src/app/(app)/onboarding/layout.tsx` |
| Komponenty kroków | `src/sylion-frontend/src/components/wizard/Step{1..10}*.tsx` |
| Persona docelowa | Operator (przy pierwszym uruchomieniu); admin (przy resetach onboardingu) |
| Liczba kroków | 10 (kroki 9 i 10 są opcjonalne) |
| Backend prefix | `/api/v1/advisor/onboarding` |

**Co operator robi na tej stronie:**

1. Wprowadza tożsamość (imię, główne cele, kadencja użycia).
2. Wkleja klucze API providerów LLM (Anthropic, OpenAI, Google) lub konfiguruje lokalny Ollama.
3. Ustawia limity budżetu USD per poziom ryzyka decyzji.
4. Wybiera domyślną domenę projektową (z 14 wbudowanych lub `custom:*`).
5. Wybiera poziom autonomii: manual / suggest / auto.
6. Konfiguruje rozmiar Rady (1–11) i routing modeli sędziowskich per ryzyko.
7. Ustawia wagi Quality / Speed / Cost (suma musi być równa 1,00).
8. Oznacza zaufanych i zablokowanych providerów.
9. (Opcjonalnie) Włącza moduł Funding Advisor i wybiera kraje/regiony.
10. (Opcjonalnie) Wprowadza zalążek pierwszego pomysłu do IdeaVault.

Po ukończeniu wizard zapisuje całość przez `POST /api/v1/advisor/onboarding/complete` i nawiguje do:
- `/projects/{first_idea_project_id}/lifecycle` — gdy operator dodał pierwszy pomysł i ma `project_id`,
- `/dashboard/operator-monitor` — w pozostałych przypadkach.

Wizard ma osobny layout (`onboarding/layout.tsx`) z gradientowym tłem, bez nawigacji bocznej — pełna szerokość ekranu.

---

## 2. Komponenty UI

### 2.1 Hierarchia

```
OnboardingPage (page.tsx)
└── WizardShell (components/wizard/WizardShell.tsx)
    ├── nawigacja kroków (1..10) z indicators ukończenia
    ├── Step1Welcome   (operator_name, goals, usage_cadence)
    ├── Step2Providers (api_key_anthropic, api_key_openai, api_key_google, ollama_base_url)
    ├── Step3Budget    (cost_ceilings: low/medium/high/critical)
    ├── Step4Domain    (default_project_domain, custom_domain_prefix)
    ├── Step5Autonomy  (autonomy_level: manual/suggest/auto)
    ├── Step6Council   (council_size 1..11, llm_judge_routing per ryzyko)
    ├── Step7QualitySpeedCost (quality + speed + cost = 1.0)
    ├── Step8TrustedBlocked   (trusted_providers[], blocked_providers[])
    ├── Step9Funding   (funding_advisor_enabled, funding_countries, funding_pl_regions)
    └── Step10FirstIdea (first_idea_title/description/project_type/domain/id)
```

Dodatkowy komponent `IncompleteBanner` (`onboarding/_components/IncompleteBanner.tsx`) jest renderowany **poza** `/onboarding`, na innych stronach (np. `/dashboard`) — pokazuje pomarańczowy pasek „Konfiguracja niekompletna (X/10 kroków)” i link `Wznów`.

### 2.2 Tabela komponentów

| Komponent | Plik | Rola | Walidacja `canAdvance` |
|-----------|------|------|------------------------|
| `WizardShell` | `components/wizard/WizardShell.tsx` | Skeleton: progress bar, prev/next/skip/complete buttons | n/d |
| `Step1Welcome` | `components/wizard/Step1Welcome.tsx` | Imię operatora, cele, kadencja | `operator_name.trim() && goals.length > 0 && usage_cadence` |
| `Step2Providers` | `components/wizard/Step2Providers.tsx` | Klucze API + Ollama URL | zawsze `true` (możliwy skip wszystkich kluczy — system użyje rule_engine fallback) |
| `Step3Budget` | `components/wizard/Step3Budget.tsx` | Pułapy USD per ryzyko | `c.low >= 0 && c.medium >= 0 && c.high >= 0 && c.critical >= 0` |
| `Step4Domain` | `components/wizard/Step4Domain.tsx` | Domena domyślna (14 typów + custom) | `default_project_domain` ustawione |
| `Step5Autonomy` | `components/wizard/Step5Autonomy.tsx` | Manual / Suggest / Auto | `autonomy_level` ustawione |
| `Step6Council` | `components/wizard/Step6Council.tsx` | Council size + routing | `council_size in [1..11]` |
| `Step7QualitySpeedCost` | `components/wizard/Step7QualitySpeedCost.tsx` | 3-wymiarowy slider | `isValidQSC(...)`: |q+s+c − 1| ≤ ε |
| `Step8TrustedBlocked` | `components/wizard/Step8TrustedBlocked.tsx` | Listy provider preferences | zawsze `true` |
| `Step9Funding` | `components/wizard/Step9Funding.tsx` | Opt-in funding (`optional: true`) | zawsze `true` |
| `Step10FirstIdea` | `components/wizard/Step10FirstIdea.tsx` | Pierwsze idea seed (`optional: true`) | zawsze `true` |
| `IncompleteBanner` | `onboarding/_components/IncompleteBanner.tsx` | Pasek w innych stronach | warunkowy: `!state.completed_at` |

### 2.3 Definicja kroków (z `page.tsx:23-34`)

```typescript
const STEPS: WizardStepDef[] = [
  { id: 1,  title: "Witaj",                    description: "Podaj imię operatora i główne cele pracy." },
  { id: 2,  title: "Klucze API",               description: "Anthropic / OpenAI / Google / Ollama (lokalnie)." },
  { id: 3,  title: "Limity budżetu",           description: "Pułapy USD per poziom ryzyka dla wywołań LLM." },
  { id: 4,  title: "Domena domyślna",          description: "Wybierz domenę, w której pracujesz najczęściej." },
  { id: 5,  title: "Autonomia",                description: "Ręcznie, sugeruj lub automatycznie (dla decyzji D0–D2)." },
  { id: 6,  title: "Rada + sędziowie",         description: "Rozmiar Rady oraz model sędziowski per poziom ryzyka." },
  { id: 7,  title: "Jakość / Prędkość / Koszt", description: "Wagi muszą sumować się do 1,00." },
  { id: 8,  title: "Zaufani / zablokowani dostawcy", description: "Oznacz preferowanych i zablokowanych providerów." },
  { id: 9,  title: "Doradca grantów",          description: "Opcjonalnie: wyszukiwanie i scoring grantów.", optional: true },
  { id: 10, title: "Pierwszy pomysł",          description: "Opcjonalnie: zalążek do Skarbca Pomysłów.",   optional: true },
];
```

---

## 3. Wszystkie controls + interactions

### 3.1 WizardShell — kontrolki nawigacyjne

| Control | Akcja | API call | State change |
|---------|-------|----------|--------------|
| Klik w step indicator (1..10) | `onStepChange(s)` | `PUT /api/v1/advisor/onboarding/step/{s}` (z pustym `values`) | `setCurrent(s)`, `saveStep(s, {})` |
| Przycisk `Next` | `goNext()` | `PUT /onboarding/step/{s+1}` | `setCurrent(s+1)`, walidacja `canAdvance` przed enablem |
| Przycisk `Prev` | `goPrev()` | brak | `setCurrent(s-1)` (lokalnie, bez backend save) |
| Przycisk `Pomine na razie` (kroki 9, 10) | `onSkip()` | `PUT /onboarding/step/{s+1}` | `setCurrent(s+1)`, krok zostaje w `completed_steps` |
| Przycisk `Complete` (krok 10) | `onComplete()` | `POST /api/v1/advisor/onboarding/complete` | `setState({ completed_at })`, `router.push(...)` |

`canAdvance` jest obliczane z `canAdvance(current, values)` przy każdym renderze i przekazane do `WizardShell` jako prop. Gdy false — przycisk `Next` jest disabled.

### 3.2 Step 1 — Welcome

| Control | Pole w `values` | Walidacja |
|---------|-----------------|-----------|
| Input `operator_name` | `operator_name: string` | non-empty po `trim()` |
| Multi-select `goals[]` | `goals: string[]` | min. 1 wybrany cel (np. „research”, „production deploy”, „cost optimization”) |
| Radio `usage_cadence` | `usage_cadence: "daily" \| "weekly" \| "occasional"` | wybrany jeden |

### 3.3 Step 2 — Providers

Sprint 2 (consolidated commit 9c45020) przebudował ten krok z czterech statycznych
pól na dynamiczną listę wpisów z dwoma sekcjami.

#### Sekcja A — klucze API (AI providers)

| Element | Opis |
|---------|------|
| Dropdown `provider` | Wybór z 8 providerów AI: Anthropic, OpenAI, Google AI, OpenRouter, Mistral, xAI/Grok, Groq, Ollama (lokalny) |
| Input `key` | Pole klucza/URL — maskowane dla providerów sekretowych; placeholder dynamiczny (np. `sk-ant-…` dla Anthropic, `http://localhost:11434` dla Ollama) |
| Przycisk reveal/hide | Ikona `Eye`/`EyeOff` per wpis — toggle widoczności klucza |
| Przycisk usuń | Ikona `Trash2` — usuwa wiersz z listy |
| Przycisk `+ Dodaj kolejny` | Dodaje nowy pusty wiersz `ApiKeyEntry` |

Struktura `ApiKeyEntry`:
```typescript
interface ApiKeyEntry {
  id: string;         // losowy 8-znakowy identyfikator (generowany loklanie)
  provider: string;   // id z AI_PROVIDERS (np. "anthropic", "ollama")
  key: string;        // surowy klucz lub URL
}
```

Dostępni AI providerzy:

| id | Label | Placeholder klucza |
|----|-------|-------------------|
| `anthropic` | Anthropic | `sk-ant-…` |
| `openai` | OpenAI | `sk-…` |
| `google` | Google AI | `AIza…` |
| `openrouter` | OpenRouter | `sk-or-…` |
| `mistral` | Mistral | `…` |
| `xai` | xAI / Grok | `xai-…` |
| `groq` | Groq | `gsk_…` |
| `ollama` | Ollama (lokalny) | `http://localhost:11434` |

#### Sekcja B — providerzy hostingu

| Element | Opis |
|---------|------|
| Dropdown `provider` | Wybór platformy chmurowej (8 opcji + custom) |
| Dynamiczne pola | Zależne od wybranego providera (token, region, account_id, itp.) |
| Pola sekretowe | Oznaczone `secret: true` — maskowane + reveal toggle |
| Przycisk usuń | Ikona `Trash2` per wiersz |
| Przycisk `+ Dodaj dostawcę hostingu` | Dodaje nowy pusty wiersz `HostingEntry` |

Dostępni providerzy hostingu:

| id | Label | Pola |
|----|-------|------|
| `cloudflare` | Cloudflare | API Token, Account ID |
| `aws` | AWS | Access Key ID, Secret Access Key, Region |
| `vercel` | Vercel | Token, Team ID |
| `render` | Render | API Key |
| `flyio` | Fly.io | Token |
| `railway` | Railway | API Key |
| `digitalocean` | DigitalOcean | Personal Access Token |
| `custom` | Inny dostawca | Nazwa, Token/klucz, Endpoint (opcjonalne) |

Struktura `HostingEntry`:
```typescript
interface HostingEntry {
  id: string;                       // losowy 8-znakowy id
  provider: string;                 // id z HOSTING_PROVIDERS (np. "cloudflare")
  fields: Record<string, string>;   // per-provider: { token: "…", account_id: "…" }
}
```

#### Sekcja C — Modele lokalne (Ollama) [sprint4, commit de60df95]

Trzecia sekcja Step 2, dodana w sprint4. Pozwala operatorowi pobrać i zarządzać modelami Ollama bezpośrednio z kroku konfiguracji providerów.

| Element | Opis |
|---------|------|
| Chips sugestii | 6 predefiniowanych modeli z etykietą, rozmiarem i opisem — klik uruchamia `pullModel(name)` |
| Input `Nazwa modelu` | Dowolna nazwa modelu Ollama (np. `codellama:13b`); po Enter lub kliknięciu przycisku `+` uruchamia `pullModel` |
| Status badge | `not_installed` / `downloading` / `installed` / `error` per model |
| Przycisk usuń | Ikona `Trash2` — usuwa wpis z listy (lokalna operacja; nie odpinacza modelu z Ollamy) |

Sugerowane modele (`SUGGESTED_OLLAMA_MODELS`):

| Nazwa | Rozmiar | Opis |
|-------|---------|------|
| `qwen2.5:7b-instruct` | 4.7 GB | Szybki uniwersalny — code + chat + reasoning |
| `qwen2.5:72b-instruct` | 47 GB | Najmocniejszy lokalny — wymaga 64+ GB RAM |
| `llama3.2:3b` | 2.0 GB | Najlżejszy — szybkie odpowiedzi, słabsze reasoning |
| `mistral:7b` | 4.4 GB | Dobry balans szybkości i jakości |
| `gemma2:9b` | 5.4 GB | Google — silne reasoning, multilingual |
| `phi3:mini` | 2.3 GB | Microsoft — tiny ale skuteczny dla code |

Typy TypeScript:

```typescript
export type LocalModelStatus = "not_installed" | "downloading" | "installed" | "error";

export interface LocalModelEntry {
  id: string;           // losowy 8-znakowy id (generowany lokalnie)
  name: string;         // nazwa modelu Ollama (np. "qwen2.5:7b-instruct")
  status: LocalModelStatus;
  error?: string;       // komunikat błędu, gdy status === "error"
}
```

Logika `pullModel(name: string)`:
1. Sprawdza `isModelInList(name)` — jeśli model już jest, pomija.
2. Dodaje `LocalModelEntry { status: "downloading" }` do lokalnej listy i wywołuje `onChange({ local_models })`.
3. `POST ${NEXT_PUBLIC_API_URL}/api/v1/brain/models/pull` z `{ model: name }`.
4. Po sukcesie: `updateModel(id, { status: "installed" })`.
5. Po błędzie: `updateModel(id, { status: "error", error: message })`.

#### Nowe pola w `values`

| Pole | Typ | Poprzednio |
|------|-----|------------|
| `api_keys` | `ApiKeyEntry[]` | `api_key_anthropic`, `api_key_openai`, `api_key_google`, `ollama_base_url` (flat) |
| `hosting_providers` | `HostingEntry[]` | brak |
| `local_models` | `LocalModelEntry[]` | brak (dodane sprint4) |

`canAdvance(2)` nadal zawsze `true` — operator może przejść bez kluczy (system użyje rule_engine fallback).
Brak pre-fill przy ponownym wejściu — listy startują z wartości `values.api_keys ?? []`, `values.hosting_providers ?? []` i `values.local_models ?? []`.

### 3.4 Step 3 — Budget

```typescript
DEFAULT_CEILINGS = { low: 0.10, medium: 0.40, high: 1.60, critical: 6.00 }; // USD per call
```

| Control | Pole | Walidacja |
|---------|------|-----------|
| Input number `cost_ceilings.low` | `cost_ceilings.low` | ≥ 0 |
| Input number `cost_ceilings.medium` | `cost_ceilings.medium` | ≥ 0 |
| Input number `cost_ceilings.high` | `cost_ceilings.high` | ≥ 0 |
| Input number `cost_ceilings.critical` | `cost_ceilings.critical` | ≥ 0 |

Gdy operator zmieni budżet **po** zakończeniu wizardu (np. w `/settings/advisor`), system traktuje to jako D3+ change i wymaga Evidence Pack.

#### 3.4.1 Sekcja "Aktywne subskrypcje" w Step 3 [sprint4, commit d6eb4d15]

Sprint4 dodal do Step 3 (Budget) nowa sekcje subskrypcji PRZED sekcja cost_ceilings. Zrodlo: `components/wizard/Step3Budget.tsx` + `_lib/subscriptions.ts`.

**Nowe pole `WizardValues.subscriptions`:**

```typescript
interface SubscriptionEntry {
  id: string;
  provider: string;
  plan_id: string;
  monthly_fee_usd: number;
  monthly_quota_tokens?: number;
  monthly_quota_usd?: number;
  models_covered: string[];
  reset_day_of_month: number;
}
```

**Struktury UI (od gory na dol w Step 3):**

1. **Sekcja "Aktywne subskrypcje"** — lista `SubscriptionRow` edytowalnych wierszy z polami: provider, plan_id, monthly_fee_usd, quota_tokens/quota_usd, modele. Przycisk "Dodaj subskrypcje" dodaje pusty wiersz.
2. **Grid sugerowanych planow (2 kolumny)** — 6 kart z `SUGGESTED_PLANS` (patrz ponizej). Klikniecie karty pre-filluje nowy wiersz.
3. **Sekcja cost_ceilings** — bez zmian (pola low/medium/high/critical).
4. **Wizualizacja waterfall** — diagram przeplywu decyzyjnego na dole (opis ponizej).

**SUGGESTED_PLANS (6 planow, `_lib/subscriptions.ts`):**

| id | provider | label | fee/mo | quota_tokens | modele |
|----|----------|-------|--------|-------------|--------|
| `claude-pro` | anthropic | Claude Pro | $20 | 5M | sonnet-4-6, haiku-4-5 |
| `claude-max` | anthropic | Claude Max | $100 | 30M | sonnet-4-6, opus-4-7, haiku-4-5 |
| `chatgpt-plus` | openai | ChatGPT Plus | $20 | 5M | gpt-5, gpt-4.1-mini |
| `openrouter-credits` | openrouter | OpenRouter prepaid | $25 | — | quota_usd=$25 (`openrouter/auto`) |
| `gemini-advanced` | google | Gemini Advanced | $20 | 10M | gemini-2.5-pro, gemini-2.5-flash |
| `custom` | custom | Inny plan (wlasny) | $0 | — | reczne wypelnienie |

**Wizualizacja waterfall** (dolna czesc Step 3):

```
Model X jest potrzebny
       │
       ▼
Subskrypcja pokrywa X? ──TAK──► Koszt $0 (quota decremented)
       │NIE
       ▼
PAYG koszt < ceiling?  ──TAK──► Koszt wg cennika
       │NIE
       ▼
Odrzucenie + suggested_alternative
```

Diagram jest renderowany jako SVG/Tailwind flow-chart w komponencie `SubscriptionWaterfall` (inline w Step3Budget.tsx).

**Walidacja `canAdvance(3)`:** niezmieniona — `c.low >= 0 && c.medium >= 0 && c.high >= 0 && c.critical >= 0`. Subskrypcje sa opcjonalne.

### 3.5 Step 4 — Domain

| Control | Pole | Wartości |
|---------|------|----------|
| Select `default_project_domain` | `default_project_domain` | 14 wbudowanych: `software`, `research`, `funding`, `governance`, `marketing`, `infrastructure`, `data_science`, `product`, `legal`, `compliance`, `security`, `operations`, `customer_support`, `analytics` + opcja `custom` |
| Input text `custom_domain_prefix` | `custom_domain_prefix` | widoczne tylko gdy `default_project_domain === "custom"`; zapisywane jako `custom:{prefix}` |

### 3.6 Step 5 — Autonomy

| Radio | Pole | Znaczenie |
|-------|------|-----------|
| `manual` | `autonomy_level: "manual"` | każda decyzja D0–D5 wymaga klika operatora |
| `suggest` | `autonomy_level: "suggest"` | system pokazuje rekomendację, operator akceptuje (default) |
| `auto` | `autonomy_level: "auto"` | D0–D2 wykonywane automatycznie, D3+ nadal require Human Gate |

Zmiana `autonomy_level` po onboardingu jest **hard preference** — wymaga D3+ confirmation w `/settings/advisor`.

### 3.7 Step 6 — Council + Judges [adaptive, sprint4]

Sprint4 (commit `634027e1`) przebudował Step6Council z prostego slidera i statycznych selectów na **widok adaptywny** zbudowany na inwentarzu modeli dostępnych u operatora.

```typescript
DEFAULT_ROUTING: JudgeRouting = {
  low: "qwen2.5:7b-instruct",    // lokalny (bez kosztów)
  medium: "qwen2.5:72b-instruct",
  high: "claude-sonnet-4-6",
  critical: "claude-sonnet-4-6+gpt-5",  // dual-judge (jeśli dostępny)
};
```

Krok 6 przyjmuje nowe propsy:

```typescript
interface Props {
  values: Step6Values;
  onChange: (patch: Step6Values) => void;
  apiKeys: ApiKeyEntry[];          // z Step2 — klucze API
  localModels: LocalModelEntry[];  // z Step2 — zainstalowane modele Ollama
  onJumpToStep2?: () => void;      // callback "Wróć do kroku 2"
}
```

| Control | Pole | Walidacja |
|---------|------|-----------|
| Slider `council_size` | `council_size: 1..maxCouncil` | max = `Math.min(11, models.length)` (dynamiczny) |
| Select `llm_judge_routing.low` | `llm_judge_routing.low` | tylko modele z `inventory.models` |
| Select `llm_judge_routing.medium` | analogicznie | |
| Select `llm_judge_routing.high` | analogicznie | |
| Select `llm_judge_routing.critical` | analogicznie + opcja dual-judge (gdy `can_dual_judge`) | |
| Pasek statusu | wyświetla `cloud_count`, `local_count`, status dual-judge | wyłącznie informacyjny |
| Banner ostrzegawczy | widoczny gdy `inventory.models.length < 2` | zawiera link do kroku 2 |

`canAdvance(6)` sprawdza `council_size in [1..11]` (niezmienione).

### 3.8 Step 7 — Quality / Speed / Cost

```typescript
DEFAULT_QSC = { quality: 0.4, speed: 0.3, cost: 0.3 }; // sum = 1.0
isValidQSC(qsc) => Math.abs(qsc.quality + qsc.speed + qsc.cost - 1.0) < 1e-3
```

| Control | Pole | Walidacja |
|---------|------|-----------|
| Slider `quality` | `quality_speed_cost.quality` | 0..1 |
| Slider `speed` | `quality_speed_cost.speed` | 0..1 |
| Slider `cost` | `quality_speed_cost.cost` | 0..1 |
| Sum indicator | sum auto-computed | musi = 1.00 ± 0.001 |

### 3.9 Step 8 — Trusted / Blocked

| Control | Pole | |
|---------|------|---|
| Multi-select `trusted_providers` | `trusted_providers: string[]` | id providerów (np. `anthropic`, `openai`) |
| Multi-select `blocked_providers` | `blocked_providers: string[]` | reguła: `blocked` przebija `trusted`, jeśli oba ustawione na ten sam id |

### 3.10 Step 9 — Funding (opcjonalny)

| Control | Pole | Default |
|---------|------|---------|
| Switch `funding_advisor_enabled` | `funding_advisor_enabled: boolean` | `false` |
| Multi-select `funding_countries` | `funding_countries: string[]` (np. `["PL", "EU"]`) | `[]` |
| Multi-select `funding_pl_regions` | `funding_pl_regions: string[]` | `[]` |

### 3.11 Step 10 — First idea (opcjonalny)

| Control | Pole | |
|---------|------|---|
| Input `first_idea_title` | `first_idea_title` | tytuł idei |
| Textarea `first_idea_description` | `first_idea_description` | opis 100–2000 zn. |
| Select `first_idea_project_type` | `first_idea_project_type` | `research` / `production` / `experiment` |
| Select `first_idea_project_domain` | `first_idea_project_domain` | dziedziczy z `default_project_domain` |
| Hidden `first_idea_project_id` | `first_idea_project_id` | wypełniane po POST do IdeaVault (jeśli istnieje) |

---

## 4. State management

### 4.1 Hook `useOnboarding`

```typescript
const { state, saveStep, complete, reset, submitting } = useOnboarding();
```

Zwracany obiekt:

```typescript
interface OnboardingState {
  step: number;                      // ostatni aktywny krok (1..10)
  completed_steps: number[];         // unikalne id kroków potwierdzonych
  values: Record<string, unknown>;   // wszystkie pola z wszystkich kroków
  completed_at?: number;             // unix seconds, ustawiane po `complete()`
}
```

Source of truth: `localStorage` z kluczem `sylion.advisor.onboarding`. Backend `PUT/POST` jest „best-effort” — jeśli backend nie odpowiada, lokalnie state jest zapisywany.

### 4.2 Lokalny state strony

```typescript
const [current, setCurrent] = useState<number>(1);
const [mounted, setMounted] = useState(false);
```

- `current` — aktualny krok (rezynkronizowany z `state.step` na pierwszy paint).
- `mounted` — flag używany do uniknięcia hydration mismatch (SSR vs. client localStorage).
- Pre-mount renderuje placeholder „Loading wizard…”.

### 4.3 Cykl saveStep

```typescript
const onChange = useCallback(
  (patch: Partial<WizardValues>) => {
    saveStep(current, patch as Record<string, unknown>);
  },
  [current, saveStep],
);
```

Wewnątrz `saveStep`:

1. `next = { step, completed_steps: [...], values: { ...state.values, ...values } }`.
2. `setState(next)` (React).
3. `writeLocalOnboarding(next)` (localStorage).
4. Jeśli backend dostępny — `await advisorApi.saveOnboardingStep(step, values)`.

### 4.4 Cache invalidation

| Wydarzenie | Inwalidacja |
|------------|-------------|
| `onChange(patch)` | natychmiastowy update React + localStorage; backend best-effort PUT |
| `goNext` / `goPrev` / `onStepChange` | wywołują `saveStep(step, {})` żeby zaktualizować pole `step` w storage |
| `onComplete` | `complete()` — set `completed_at`, POST do backend, nawigacja |
| `reset()` | przywraca `{ step: 1, completed_steps: [], values: {} }` w obu warstwach |

---

## 5. API integration

### 5.1 Endpointy

| Metoda | Endpoint | Wywołujący | Payload |
|--------|----------|------------|---------|
| GET | `/api/v1/advisor/onboarding/state` | `advisorApi.getOnboardingState()` | brak |
| PUT | `/api/v1/advisor/onboarding/step/{step}` | `saveStep(step, values)` | `{ "values": Record<string, unknown> }` |
| POST | `/api/v1/advisor/onboarding/complete` | `complete()` | `{ "values": Record<string, unknown> }` (snapshot wszystkich) |
| POST (opcjonalnie) | `/api/v1/idea-vault/ideas` | Step10 → tworzy idea seed | `{ title, description, project_type, project_domain }` |
| POST (opcjonalnie) | `/api/v1/advisor/providers/test` | Step2 test connection | `{ provider_id, api_key }` |

### 5.2 TypeScript interface

```typescript
export interface OnboardingState {
  step: number;
  completed_steps: number[];
  values: Record<string, unknown>;
  completed_at?: number;
}

interface WizardValues {
  operator_name?: string;
  goals?: string[];
  usage_cadence?: string;
  /** Sprint2: zastąpiło płaskie pola api_key_anthropic / openai / google / ollama_base_url */
  api_keys?: ApiKeyEntry[];
  hosting_providers?: HostingEntry[];
  /** Sprint4: modele lokalne Ollama (status pobierania śledzony w UI) */
  local_models?: LocalModelEntry[];
  cost_ceilings?: { low: number; medium: number; high: number; critical: number };
  default_project_domain?: string;
  custom_domain_prefix?: string;
  autonomy_level?: "manual" | "suggest" | "auto";
  council_size?: number;
  llm_judge_routing?: { low: string; medium: string; high: string; critical: string };
  quality_speed_cost?: { quality: number; speed: number; cost: number };
  trusted_providers?: string[];
  blocked_providers?: string[];
  funding_advisor_enabled?: boolean;
  funding_countries?: string[];
  funding_pl_regions?: string[];
  first_idea_title?: string;
  first_idea_description?: string;
  first_idea_project_type?: string;
  first_idea_project_domain?: string;
  first_idea_project_id?: string;
}
```

### 5.3 Przykład payloadu PUT step 6

```http
PUT /api/v1/advisor/onboarding/step/6
Content-Type: application/json

{
  "values": {
    "council_size": 5,
    "llm_judge_routing": {
      "low": "claude-haiku",
      "medium": "claude-sonnet",
      "high": "claude-opus",
      "critical": "claude-opus"
    }
  }
}
```

Backend zwraca pełny `OnboardingState` po stronie serwerowej (mergowany z lokalnym).

### 5.4 Przykład payloadu POST complete

```http
POST /api/v1/advisor/onboarding/complete
Content-Type: application/json

{
  "values": {
    "operator_name": "Razor",
    "goals": ["research", "cost_optimization"],
    "usage_cadence": "daily",
    "ollama_base_url": "http://localhost:11434",
    "cost_ceilings": { "low": 0.1, "medium": 0.4, "high": 1.6, "critical": 6.0 },
    "default_project_domain": "research",
    "autonomy_level": "suggest",
    "council_size": 5,
    "llm_judge_routing": { "low": "claude-haiku", "medium": "claude-sonnet", "high": "claude-opus", "critical": "claude-opus" },
    "quality_speed_cost": { "quality": 0.4, "speed": 0.3, "cost": 0.3 },
    "trusted_providers": ["anthropic"],
    "blocked_providers": [],
    "funding_advisor_enabled": false
  }
}
```

Backend:
1. Zapisuje wszystkie pola do tabeli `advisor_preferences.preferences` z `set_by="wizard"`.
2. Loguje wpis `INSERT` do `advisor_preferences.preferences_audit`.
3. Emituje event `aeis.system.onboarding_completed`.
4. Zwraca `{ ...state, completed_at: <unix> }`.

---

## 6. Persistence (localStorage, cookies, sessionStorage)

| Klucz | Mechanizm | Co zawiera | TTL | Reset |
|-------|-----------|------------|-----|-------|
| `sylion.advisor.onboarding` | `localStorage` | cały `OnboardingState` (krok, completed_steps, values, completed_at) | brak (do `reset()` lub manual clear) | hook `reset()` lub DevTools |
| `_reachable`, `_checkedAt` | module-level | TTL backend reachability | 15 s | re-check po wygaśnięciu |
| `mounted` flag | komponent | hydration guard | render | n/d |

### 6.1 Format JSON localStorage

```json
{
  "step": 7,
  "completed_steps": [1, 2, 3, 4, 5, 6, 7],
  "values": {
    "operator_name": "Razor",
    "goals": ["research"],
    "usage_cadence": "daily",
    "cost_ceilings": { "low": 0.1, "medium": 0.4, "high": 1.6, "critical": 6.0 },
    "council_size": 5
  }
}
```

### 6.2 Bezpieczeństwo

> **Uwaga:** klucze API wprowadzone w Step 2 są zapisywane do localStorage **w plaintext**. To celowy kompromis dev-experience, ale w środowisku produkcyjnym zalecane jest:
>
> - hostowanie kluczy w `secrets vault` (vide `/secrets`),
> - przekazywanie do backendu wyłącznie ID secret reference,
> - lokalny localStorage powinien zawierać `secret_ref_id` zamiast surowego klucza.
>
> Obecna implementacja (Etap 1) zapisuje surowe klucze, ponieważ infrastruktura secrets jest jeszcze w fazie wdrożenia.

---

## 7. Modes / variants

### 7.1 First-run vs. re-run

| Tryb | Trigger | Różnica |
|------|---------|---------|
| First-run | brak `completed_at` w state | Pełen flow, wszystkie pola puste; po complete → `/dashboard/operator-monitor` |
| Re-run | operator wchodzi na `/onboarding` mając `completed_at` ustawiony | UI startuje od kroku 1, ale wartości są pre-fill z localStorage; complete wymusza nowy timestamp `completed_at` (override) |

### 7.2 Z perspektywy IncompleteBanner (na innych stronach)

```typescript
if (state.completed_at) return null;        // brak banneru
const total = 10;
const done = state.completed_steps.length;  // ile kroków potwierdzono
```

Banner widoczny dopóki operator nie skończy całości (lub `complete()` nie zostanie wywołane). Jest pomarańczowy (`bg-sylion-amber/5 text-sylion-amber`) z przyciskiem `Wznów` linkującym do `/onboarding`.

### 7.3 Loading states

- Pre-hydration: placeholder „Loading wizard…” (12px text-muted-foreground, padding) — chroni przed mismatch SSR/CSR localStorage.
- Submitting (Save step / complete): nie blokuje UI, ale `submitting` flag z `useOnboarding` jest dostępny dla `WizardShell` (przycisk `Next` może być w trakcie save w tle).

### 7.4 Error states

- `PUT /onboarding/step/{n}` failure: try/catch w `saveStep` cicho ignoruje błąd (lokalnie zachowane).
- `POST /onboarding/complete` failure: ten sam try/catch — `completed_at` jest mimo to ustawiony lokalnie, więc operator nie wisi.
- Brak głośnych error states w UI — celowe (DX > brutalne błędy).

### 7.5 Skip behavior

- Kroki 9 i 10 mają `optional: true`. `WizardShell` renderuje przycisk `Pomine na razie` zamiast `Next` (etykieta zmieniona w sprint2 — poprzednio "Skip").
- `onSkip` zachowuje się jak `goNext` — inkrementuje `current` i wywołuje `saveStep(next, {})`.
- Pominięte kroki **nie** są dodawane do `completed_steps` (operator może je później dokończyć z `/settings/advisor`).

### 7.6 Adaptive Step 6 — inwentarz modeli [sprint4, commit 634027e1]

Step6Council czyta `apiKeys` i `localModels` (wartości z Step2) przez hooki `deriveInventory` + `suggestModelForRisk` z `_lib/available-models.ts`.

**`deriveInventory(apiKeys, localModels) -> ModelInventory`:**

- Dla kazdego `ApiKeyEntry` z niepustym kluczem: dodaje domyslne modele providera jako modele `"cloud"`.
- Dla kazdego `LocalModelEntry` ze `status === "installed"`: dodaje jako model `"local"` (provider `"ollama"`, cost_tier `"free"`).
- Pole `can_dual_judge = uniqueProviders.length >= 2` — dual-judge wymaga min. 2 roznych providerow.
- `recommended_max_council = min(11, max(1, models.length))`.

Modele domyslne per provider API key:

| Provider | Modele |
|----------|--------|
| anthropic | claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5 |
| openai | gpt-5, gpt-4.1-mini |
| google | gemini-2.5-pro, gemini-2.5-flash |
| openrouter | openrouter/auto |
| mistral | mistral-large-latest |
| xai | grok-4 |
| groq | llama-3.3-70b-versatile |

**`suggestModelForRisk(risk, inventory) -> string | null`:**

| Risk | Priorytet sugestii |
|------|-------------------|
| `low` | lokalny[0] → cheap cloud → cloud[0] |
| `medium` | lokalny z `72b`/`9b` → standard cloud → cloud[0] |
| `high` | premium cloud[0] → cloud[0] → lokalny[0] |
| `critical` | dual-judge z 2 premium → dual z roznych providerow → premium[0] |

**Dual-judge (critical risk):** opcja pojawia sie w select gdy `can_dual_judge`. Wartosc: `"{modelA}+{modelB}"` (pary z roznych providerow). Operator moze wybrac pare lub pozostac przy single judge.

**Banner ostrzegawczy** (`inventory.models.length < 2`): zawiera liczbe dostepnych modeli, rekomendacje pobrania `qwen2.5:7b-instruct` + `mistral:7b` i przycisk powrotu do kroku 2 (`onJumpToStep2` callback).

### 7.7 Modele lokalne (Ollama) — Sekcja C Step 2 [sprint4]

Sekcja C Step 2 ma trzy tryby wyświetlania per model:

| Status | Wygląd w UI | Akcja dostępna |
|--------|-------------|----------------|
| `not_installed` | chip szary z przyciskiem pobierz | klik chip → `pullModel(name)` |
| `downloading` | spinner `Loader2` + tekst „Pobieranie…" | brak (oczekiwanie) |
| `installed` | ikona `CheckCircle2` (zielona) | przycisk `Trash2` (usuń z listy) |
| `error` | czerwony tekst błędu | przycisk `Trash2` (usuń z listy) |

Sekcja renderuje się niezależnie od Sekcji A i B — operacja pull nie blokuje przejścia do kroku 3 (`canAdvance(2)` zawsze `true`). Modele pobierane równolegle do nawigacji wizard.

Endpointy backendu powiązane z Sekcją C:

| Endpoint | Metoda | Akcja |
|----------|--------|-------|
| `/api/v1/brain/models/pull` | POST | Inicjuje pobieranie modelu Ollama; `{ model: string }` |

### 7.8 Step 3 — Subskrypcje + waterfall visualization [sprint4, commit d6eb4d15]

Sprint4 rozszerzyl Step 3 Budget o sekcje subskrypcji i wizualizacje waterfall. Pelny opis komponentow i logiki w sekcji `3.4.1`.

**Kluczowe zachowania trybow:**

| Tryb | Zachowanie |
|------|-----------|
| Brak subskrypcji (pusta lista) | Operator widzi grid SUGGESTED_PLANS i moze dodac plan; waterfall pokazuje sciezke "tylko PAYG" |
| 1+ subskrypcja dodana | Waterfall pokazuje sciezke subscription-first → PAYG fallback; pole cost_ceilings nadal wymagane jako fallback |
| Plan "Inny (wlasny)" | Operator reczne wypelnia wszystkie pola; brak pre-fillu |
| Subskrypcja z quota_usd (np. OpenRouter) | Waterfall pokazuje "remaining $X" zamiast "remaining N tokens" |

**localStorage:** subskrypcje zapisywane do `localStorage["sylion.advisor.onboarding"]` pod kluczem `subscriptions: SubscriptionEntry[]`. Backend persistuje je przez `POST /api/v1/advisor/onboarding/complete` → `preferences.subscriptions` i tworzy wpisy w `advisor_subscription.active_subscriptions`.

**Crossref:**
- `modules/10_subscription.md §10.5` — Quota Tracker i tabele DB.
- `modules/08_role_resolver.md §4.8` — Priority Routing waterfall w backendzie.
- `modules/02_pricing.md §4.9` — `effective_cost_estimate` + `Source.SUBSCRIPTION`.

---

## 8. Accessibility

### 8.1 ARIA

- `WizardShell` używa nagłówka `<h1>` per krok (zmienia się dynamicznie).
- Step indicator (1..10) — każdy element jest `<button aria-current="step"` gdy `current === step`.
- Walidatory typu „suma QSC = 1.0” w Step 7 powinny być `aria-live="polite"` (do zweryfikowania w `Step7QualitySpeedCost.tsx`).
- `IncompleteBanner` używa `role="alert"` (potwierdzone w pliku linia 33).

### 8.2 Keyboard navigation

| Skrót | Akcja |
|-------|-------|
| `Tab` | przechodzi przez pola formularza w kolejności DOM (input → select → switch → przyciski) |
| `Enter` w polu | nie wywołuje `Next` (świadome — żeby uniknąć przypadkowego skipa walidacji) |
| `Tab` na przycisku `Next` + `Enter` | wywołuje `goNext()` jeśli `canAdvance` |
| `Esc` | brak akcji (wizard nie jest modalem) |

### 8.3 Color contrast

- Tło layoutu: gradient niebieski/bursztynowy (radial-gradient), tekst białymi/szarymi tonami — kontrast WCAG AA.
- Step indicator: aktywny krok = `text-foreground bg-primary/10`, ukończony = `text-sylion-green`, niedotknięty = `text-muted-foreground`.

---

## 9. Przykładowe operator flows (step-by-step)

### 9.1 Happy path: First-run end-to-end

1. Świeży operator otwiera aplikację po pierwszej instalacji. URL przekierowuje go na `/onboarding`.
2. Strona montuje się; `useOnboarding` czyta `localStorage["sylion.advisor.onboarding"]` — brak. Zwraca `{ step: 1, completed_steps: [], values: {} }`.
3. UI pokazuje krok 1 „Witaj”. Operator wpisuje:
   - operator_name: „Razor”
   - goals: zaznacza `research`, `cost_optimization`
   - usage_cadence: `daily`
4. Każda zmiana pola woła `onChange(patch)` → `saveStep(1, patch)`. localStorage natychmiast aktualizowany.
5. Backend dostępny → `PUT /api/v1/advisor/onboarding/step/1` z `{ "values": { "operator_name": "Razor", ... } }` → backend zwraca 200.
6. Operator klika `Next`. `goNext()` → `setCurrent(2)`, `saveStep(2, {})`.
7. Krok 2 „Klucze API”. Operator wkleja `sk-ant-...`, klika `Next`.
8. Krok 3 „Limity budżetu”. Operator zostawia defaults (0.10 / 0.40 / 1.60 / 6.00 USD), `Next`.
9. Krok 4 „Domena domyślna”. Wybiera `research` z dropdown, `Next`.
10. Krok 5 „Autonomia”. Wybiera radio `suggest`, `Next`.
11. Krok 6 „Rada + sędziowie”. Slider `council_size = 5`, routing zostaje na default Anthropic, `Next`.
12. Krok 7 „QSC”. Sliders: quality=0.4, speed=0.3, cost=0.3. Sum indicator pokazuje `= 1.00 OK`, `Next`.
13. Krok 8 „Zaufani / zablokowani”. Trusted: `anthropic`, blocked: empty. `Next`.
14. Krok 9 „Doradca grantów”. Operator widzi switch `Włącz Funding Advisor` — pozostawia OFF i klika `Skip`.
15. Krok 10 „Pierwszy pomysł”. Wpisuje:
    - first_idea_title: „Memory profiling pipeline”
    - first_idea_description: „Build internal tool for memory consumption tracing of background workers.”
    - first_idea_project_type: `research`
    - first_idea_project_domain: `research` (auto-prefill z step 4)
16. Klika `Complete`. `onComplete()` woła:
    - `complete()` → `setState({ completed_at: 1745625600 })`, localStorage update.
    - `POST /api/v1/advisor/onboarding/complete` z całością `values`.
    - Backend zapisuje preferencje, emituje `aeis.system.onboarding_completed`, idea seed jest wysyłana do IdeaVault → otrzymuje `project_id="proj-abc-001"`.
17. Frontend (`onComplete`) widzi `values.first_idea_project_id="proj-abc-001"` (bo response API IdeaVault zwrócił ID i Step10 wstawił do values).
18. `router.push("/projects/proj-abc-001/lifecycle")` — operator ląduje na Lifecycle Dashboard.

### 9.2 Path: Resume z połowy (re-run po reload)

1. Operator zaczął wizard, zrobił kroki 1–4, zamknął przeglądarkę.
2. localStorage pozostaje: `{ step: 5, completed_steps: [1,2,3,4], values: {...} }`.
3. Operator wraca następnego dnia. Wchodzi na `/dashboard`.
4. `IncompleteBanner` (renderowany przez global layout) sprawdza `useOnboarding`:
   - `state.completed_at === undefined` → banner widoczny.
   - `state.completed_steps.length === 4` → tekst „Konfiguracja niekompletna (4/10 kroków)”.
5. Operator klika `Wznów`. `<Link href="/onboarding">` — nawigacja.
6. `OnboardingPage` montuje się; `useEffect` (linia 101-106) ustawia `setCurrent(state.step || 1)` → `setCurrent(5)`.
7. UI pokazuje krok 5 z pre-fillem z localStorage. Operator kontynuuje.

### 9.3 Path: Backend offline w trakcie wizard

1. Operator otwiera `/onboarding`. Backend nie działa (nie wstał).
2. `useOnboarding` ma local state z localStorage (lub fresh).
3. `saveStep(1, patch)` próbuje:
   - `setState(next)` ✓
   - `writeLocalOnboarding(next)` ✓
   - `await isBackendReachable()` → `false`.
   - Skip backend call (swallowed).
4. Operator przechodzi przez wszystkie 10 kroków bez problemu. Lokalne dane zachowane.
5. Klika `Complete`. `complete()`:
   - `setState({ completed_at })` ✓
   - `writeLocalOnboarding(...)` ✓
   - Backend POST: skip (offline).
6. `router.push("/dashboard/operator-monitor")` — przechodzi.
7. Backend nadal offline; `IncompleteBanner` jest schowany (bo `completed_at` set).
8. Później backend wstaje. Frontend nie ma mechanizmu retry-sync (TODO) — operator może użyć `/settings/advisor` żeby ręcznie „Save section” każdego, co triggeruje `PUT` do backendu i synchronizuje preferencje.

### 9.4 Edge case: Walidacja Step 7 QSC

1. Operator na Step 7. Sliders przesuwa: quality=0.5, speed=0.3, cost=0.3 → sum = 1.10.
2. `isValidQSC({0.5, 0.3, 0.3}) === false` → `canAdvance(7) === false` → `Next` disabled.
3. UI w Step7 pokazuje pomarańczowy banner: „Suma musi być równa 1.00 (aktualnie 1.10)”.
4. Operator zmniejsza quality do 0.4 → sum = 1.00 → `Next` enabled.

---

## 10. Cross-references

### 10.1 Backend modules

| Moduł | Plik | Rola |
|-------|------|------|
| Onboarding routes | `src/sylion-pipeline/sylion/aeis/advisor/onboarding/routes.py` | FastAPI endpointy `/onboarding/state`, `/step/{n}`, `/complete` |
| Preferences storage | `src/sylion-pipeline/sylion/aeis/advisor/preferences/` | `advisor_preferences.preferences` + audit log |
| IdeaVault | `src/sylion-pipeline/sylion/aeis/idea_vault/` | tworzenie pierwszego idea seed (Step 10) |

### 10.2 Architecture docs

- `docs/claude_parallel/aeis_advisor/00_architecture/00_master_spec.md` — sekcja „Onboarding wizard”.
- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — wyjaśnia że zmiana `autonomy_level` po onboardingu = D3+.

### 10.3 Pokrewne surfaces

| Surface | Powód |
|---------|-------|
| `/settings/advisor` | Edycja każdej decyzji onboardingu post-hoc; dzieli komponenty `Step1..Step9` |
| `/idea-vault` | Step 10 tworzy seed, którego pełny lifecycle jest w IdeaVault |
| `/projects/{id}/lifecycle` | Cel nawigacji po complete (jeśli Step 10 zwrócił project_id) |
| `/dashboard/operator-monitor` | Cel nawigacji po complete (default fallback) |
| `IncompleteBanner` (cross-page) | Renderowany na każdej stronie poza `/onboarding`, dopóki `completed_at === undefined` |

### 10.4 Powiązana dokumentacja

- [`01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md) — Advisor Layer overview.
- [`02_operational_manual.md`](../02_operational_manual.md) — runbook „pierwsze uruchomienie systemu”.
- [`05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md`](../05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md) — decyzje archi związane z onboarding flow.
