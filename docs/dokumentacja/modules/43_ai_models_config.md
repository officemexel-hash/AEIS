# 43. AI Models Config — strona konfiguracji modeli i dostawcow LLM
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja strony `/ai-models` w panelu operatorskim SYLION AEIS Advisor.
> Strona stanowi jedyne miejsce zarzadzania dostawcami LLM, kluczami API,
> rejestrem modeli, budzetem i Rada modeli.

## Spis tresci

1. [Cel modulu](#1-cel-modulu)
2. [Architektura strony](#2-architektura-strony)
3. [Konfiguracja i dostep](#3-konfiguracja-i-dostep)
4. [Zakladki i funkcje](#4-zakladki-i-funkcje)
5. [Zrodla danych (API)](#5-zrodla-danych-api)
6. [Schemat danych](#6-schemat-danych)
7. [Przykladowe wywolania](#7-przykladowe-wywolania)
8. [Weryfikacja](#8-weryfikacja)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Cel modulu

Strona `/ai-models` jest panelem konfiguracji modeli LLM dla AEIS Advisor. Agreguje w jednym miejscu:
- przeglad zdrowia systemu i aktywnych dostawcow,
- zarzadzanie kluczami API per dostawca,
- rejestr modeli (CRUD z wersjonowaniem),
- budzet tokenow i kontrole dostepu,
- Rade modeli (hierarchie, wagi, role council),
- Ollama (lokalne modele, status, lista dostepnych modeli),
- preferencje routingu domyslnego.

Lokalizacja: `src/sylion-frontend/src/app/(app)/ai-models/page.tsx`.

---

## 2. Architektura strony

```
AIModelsPage (RSC wrapper, "use client")
├── LoadState (interfejs agregatora)
│   ├── health: SystemHealth
│   ├── providers: Provider[]
│   ├── apiKeys: ApiKey[]
│   ├── registeredModels: RegisteredModel[]
│   ├── registryStats: RegistryStats
│   ├── hierarchies: ModelHierarchy[]
│   ├── councilMembers: CouncilMember[]
│   ├── ollama: OllamaState
│   ├── budgets: Budget[]
│   └── routing: RoutingMatrix | null
├── Tabs (shadcn)
│   ├── Przeglad
│   ├── Dostawcy i klucze
│   ├── Rejestr modeli
│   ├── Budzet i dostep
│   ├── Rada modeli
│   ├── Lokalne Ollama
│   └── Preferencje domyslne
└── Helpery: getSettled, parseConfig, providerClass, fmtBytes, fmtUSD, pct
```

Wszystkie dane ladowane przez `Promise.allSettled(...)` — strona renderuje sie nawet jesli czesc API jest niedostepna. Brakujace dane pokazuja puste karty zamiast erroru.

---

## 3. Konfiguracja i dostep

| Pole | Wartosc |
|------|---------|
| Route | `/ai-models` |
| Plik | `src/sylion-frontend/src/app/(app)/ai-models/page.tsx` |
| Auth | wymaga sesji operatora (middleware next.js) |
| RBAC | operator + admin |
| Env var | `NEXT_PUBLIC_API_URL` (domyslnie `http://127.0.0.1:8010`) |

---

## 4. Zakladki i funkcje

### 4.1. Zakladka "Przeglad"

Dwie karty:
- **Health** — status systemu (`health.status`, liczba aktywnych modeli, last check timestamp).
- **Aktywni dostawcy** — lista provider+model z ich statusem i klasyfikacja kolorem (local=green, anthropic/zai=amber, reszta=primary).

### 4.2. Zakladka "Dostawcy i klucze"

- **Lista dostawcow** — provider + czy ma klucz API (`apiKeys.find(...)`).
- **Dodaj klucz API** — formularz: provider (dropdown z 11 opcji), api_key, base_url (opcjonalne). Submit → `api.addApiKey({provider, api_key, base_url})`.
- 11 opcji dostawcow: `openai, anthropic, perplexity, google, zai, ollama, deepseek, mistral, groq, together, localai`.

### 4.3. Zakladka "Rejestr modeli"

- Tabela modeli z polami: model_id, provider, status, max_tokens, cost_per_input_1k, cost_per_output_1k, created_at.
- Statystyki rejestru (total, active, deprecated).
- Dodawanie modelu: `api.registerModel({model_id, provider, max_context_tokens, cost_per_input_token_usd, cost_per_output_token_usd, ...})`.

### 4.4. Zakladka "Budzet i dostep"

- Lista budzetow per operator z polami: `operator_id, monthly_token_limit, used_tokens, period_start, period_end`.
- Wskaznik zuzycia (pasek procentowy) obliczany przez helper `pct(spent, limit)`.
- Informacja o blockedProviders z preferencji.

### 4.5. Zakladka "Rada modeli"

- Hierarchie modeli (model nadrzedny → model podrzedny z waga glosu).
- Lista czlonkow Rady z rola, modelem, waga i statusem aktywnosci.
- Formularz dodawania czlonka Rady.

### 4.6. Zakladka "Lokalne Ollama"

- Status Ollama (`ollama.available`, `ollama.base_url`, lista `ollama.models`).
- Lista rekomendowanych modeli lokalnych: `qwen3-coder:30b`, `gpt-oss:20b`, `deepseek-r1:14b`, `nomic-embed-text`.
- Formatowanie pamieci przez `fmtBytes(value)` (B / MB / GB).

### 4.7. Zakladka "Preferencje domyslne"

- Biezaca macierz routingu (domyslne modele per rola/ryzyko).
- Link do pelnego edytora macierzy: `/orchestration/llm-routing`.

---

## 5. Zrodla danych (API)

Strona wola `Promise.allSettled` z nastepujacymi callami:

| Zrodlo | Endpoint | Opis |
|--------|----------|------|
| `api.getSystemHealth()` | `GET /api/v1/health` | Status systemu |
| `api.listProviders()` | `GET /api/v1/providers` | Dostawcy LLM |
| `api.listApiKeys()` | `GET /api/v1/api-keys` | Klucze API |
| `api.listRegisteredModels()` | `GET /api/v1/models/registry` | Rejestr modeli |
| `api.getRegistryStats()` | `GET /api/v1/models/registry/stats` | Statystyki rejestru |
| `api.listModelHierarchies()` | `GET /api/v1/models/hierarchies` | Hierarchie modeli |
| `api.listCouncilMembers()` | `GET /api/v1/council/members` | Czlonkowie Rady |
| `api.getOllamaStatus()` | `GET /api/v1/ollama/status` | Status Ollama |
| `api.listBudgets()` | `GET /api/v1/budgets` | Budzety tokenow |
| `orchestrationApi.getLLMRouting()` | `GET /api/v1/orchestration/llm-routing` | Macierz routingu |

---

## 6. Schemat danych

### 6.1. `LoadState`

```typescript
type LoadState = {
  health: any;
  providers: any[];
  apiKeys: any[];
  registeredModels: any[];
  registryStats: any;
  hierarchies: any[];
  councilMembers: any[];
  ollama: { available: boolean; models: any[]; error: string; base_url: string };
  budgets: any[];
  routing: any;
};
```

### 6.2. Klasyfikacja kolorem dostawcow

```typescript
function providerClass(provider: string) {
  if (provider === "ollama" || provider === "localai")
    return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (provider === "anthropic" || provider === "zai")
    return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-primary/30 text-primary bg-primary/5";
}
```

---

## 7. Przykladowe wywolania

```typescript
// Ladowanie danych (uproszczone)
const [healthRes, providersRes] = await Promise.allSettled([
  api.getSystemHealth(),
  api.listProviders(),
]);
const health = getSettled(healthRes, null);
const providers = getSettled(providersRes, []);

// Dodanie klucza API
await api.addApiKey({ provider: "anthropic", api_key: "sk-ant-...", base_url: "" });

// Rejestracja modelu
await api.registerModel({
  model_id: "claude-sonnet-4-6",
  provider: "anthropic",
  max_context_tokens: 200000,
  cost_per_input_token_usd: 0.000003,
  cost_per_output_token_usd: 0.000015,
});
```

---

## 8. Weryfikacja

```bash
# Sprawdz czy strona sie renderuje
curl http://localhost:3000/ai-models

# Sprawdz endpointy backend
curl http://127.0.0.1:8010/api/v1/health
curl http://127.0.0.1:8010/api/v1/providers
curl http://127.0.0.1:8010/api/v1/models/registry
```

---

## 9. Troubleshooting

| Problem | Mozliwa przyczyna | Rozwiazanie |
|---------|-------------------|-------------|
| Pusta lista dostawcow | Backend niedostepny lub brak rekordow | Sprawdz `GET /api/v1/providers`; dodaj dostawcow przez formularz |
| Budzet nie wyswietla sie | `listBudgets` zwraca 500 | Sprawdz tabele `advisor_subscriptions` w PG |
| Ollama niedostepna | Ollama nie uruchomiona lub zly port | Uruchom `ollama serve`; sprawdz `ollama.base_url` |
| Pusty rejestr modeli | Brak seed danych | Wywolaj `api.registerModel(...)` lub seed script |

---

## 10. Cross-references

- [`34_llm_pool_routing.md`](34_llm_pool_routing.md) — statyczna routing matrix (backend)
- [`28_orchestration_panel.md`](28_orchestration_panel.md) — pelny edytor macierzy `/orchestration/llm-routing`
- [`08_role_resolver.md`](08_role_resolver.md) — logika wyboru modelu per rola/ryzyko
- [`26_council_voting.md`](26_council_voting.md) — system glosowania Rady
- [`33_council_hybrid.md`](33_council_hybrid.md) — architektura CouncilHybrid
- [`41_environment_variables.md`](41_environment_variables.md) — `NEXT_PUBLIC_API_URL`
