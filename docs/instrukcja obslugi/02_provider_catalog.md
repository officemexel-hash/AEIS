# FAZA 2 — Provider Catalog Configuration

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (2 z 11)
> **Typ**: iteracyjna, operator wraca tu wielokrotnie w cyklu życia
> **Czas wykonania**: 5-10 min (pierwszy provider) / 10-30 min (3-5 providerów) / godziny (50+ providerów + lokalne)
> **D-level**: D2 — dodawanie kluczy ma znaczenie kosztowe i bezpieczeństwa
> **Zależności**: Faza 1 zakończona (workspace + master password + min 1 model wykryty)
> **Następnik**: Faza 3 (Environment Configuration)
>
> **Spis sekcji**:
> - 2.1 — Sense fazy i jej miejsce w cyklu
> - 2.2 — Architektura katalogu (3 widoki z toggle)
> - 2.3 — Auto-detection lokalnych modeli (4 triggers + benchmark)
> - 2.4 — Encryption sekretów (SQLite encrypted column)
> - 2.5 — Predefined templates (24 providers + custom workflow)
> - 2.6 — Capability matrix expanded (12 capabilities + scoring + gap detection)
> - 2.7 — Sugestie lokalnych instalacji (image-gen + TTS multi-language)
> - 2.8 — Acquisition advisor (quality-first recommendation)
> - 2.9 — Cost & priority profiles (chains, limits, exhaustion behavior)
> - 2.10 — Health monitoring + quota tracking (5-level + dashboards)
> - 2.11 — Edge cases (30 cases w 6 hybrid kategoriach)
> - 2.12 — Inheritance + DoD + acceptance criteria

---

## 2.1. Sens fazy i jej miejsce w cyklu

### 2.1.1. Czemu ta faza istnieje

AEIS jest **abstraction layer** nad LLM providerami. Bez providerów AEIS
jest jak komputer bez procesora — instaluje się, uruchamia, ale nic nie
może faktycznie zrobić.

Faza 2 jest tym momentem gdzie operator daje AEIS-owi **dostęp do
inteligencji**. Może to robić na 4 sposoby:

1. **Dodanie kluczy API** do komercyjnych providerów (Anthropic, OpenAI,
   Google, OpenRouter, Mistral, ...) — operator płaci, AEIS używa
2. **Konfiguracja lokalnych modeli** wykrytych w fazie 1 (Ollama,
   LM Studio, llama.cpp) — operator hostuje, AEIS używa
3. **Sugestie instalacji** nowych lokalnych modeli których operator nie
   ma — system proponuje co warto mieć
4. **Custom providers** — własne endpointy (self-hosted vLLM, własny TGI,
   provider którego nie ma w predefined catalog)

### 2.1.2. Dlaczego "iteracyjna" zamiast "jednorazowa"

W przeciwieństwie do fazy 1 (jednorazowa per operator), **faza 2 jest
żywa**. Operator wraca tu:

- **Po każdym dodaniu nowego providera** (nowy klucz API, nowy lokalny
  model, nowa subskrypcja)
- **Gdy AEIS wykrywa gap w capability matrix** (np. brak modelu polskiego)
- **Gdy provider rate-limit lub price changes** (rebalancing)
- **Gdy operator dostaje sugestię od acquisition advisor** ("warto kupić X")
- **Po acquisition** (nowy klucz dodany przez operator po sign-up)
- **Mid-project gdy projekt wymaga capability** której nikt nie ma
- **Periodically** dla health checks i quota monitoring

To NIE jest faza "skonfiguruj raz i zapomnij". To jest **żyjący katalog**
który ewoluuje z operator's needs.

### 2.1.3. Wynik fazy (definition of done — minimum viable)

Po fazie 2, operator może mieć:

**Minimum (po pierwszym przejściu)**:
- ✓ Min 1 provider dodany i zweryfikowany (lokalny lub API)
- ✓ Wszystkie wykryte lokalne modele potwierdzone (akceptowane lub odrzucone)
- ✓ Capability matrix wstępnie wypełniona

**Rekomendowane (po pełnej konfiguracji)**:
- ✓ 2-5 providerów (mix lokalnych + API)
- ✓ Polish model dostępny (Bielik lub PLLuM lub przez Claude/GPT)
- ✓ Code model dostępny (Claude/GPT lub Qwen Coder lokalnie)
- ✓ Cost limits zdefiniowane per provider
- ✓ Fallback chains skonfigurowane
- ✓ Health monitoring włączone

**Zaawansowane (power users, opcjonalne)**:
- ✓ 10+ providerów z różnych źródeł (API + lokalne + custom + edge)
- ✓ OpenRouter dla maximum capability coverage
- ✓ Image-gen / audio / vision providers
- ✓ Per-capability priority chains
- ✓ Per-project budget allocations

### 2.1.4. Co NIE jest w tej fazie

| Element | Dlaczego nie w fazie 2 | Gdzie |
|---|---|---|
| Cloud providers (Hetzner, AWS) | To środowiska deploy, nie LLM providers | Faza 3 |
| Subskrypcje payment-related | Faza 2 dodaje keys, nie zarządza billingami | Faza 4 + provider-side |
| Council templates per D-level | Modele już dodane, ale rozdzielenie ich do ról to inna faza | Faza 12 |
| Konkretny projekt z konkretnymi modelami | Project-level mapping w fazie 17/22 | Fazy 17+ |
| Workspace defaults używające tych providerów | Faza 4 (Workspace Defaults) | Faza 4 |

---

## 2.2. Architektura katalogu

### 2.2.1. Trzy poziomy hierarchii (P2.1=d — wszystkie 3 widoki z toggle)

AEIS organizuje providerów na trzech poziomach:

```
PROVIDER (np. Anthropic, OpenAI, Ollama-local, OpenRouter)
   │
   ├── ENDPOINT (instance providera)
   │       np. Ollama @ localhost:11434
   │       np. Ollama @ ssh://vps-warsaw.sylion.dev:11434
   │       np. Anthropic API @ https://api.anthropic.com
   │
   └── MODEL (konkretny model na endpoint)
           np. claude-opus-4-7
           np. claude-sonnet-4-6
           np. qwen2.5:7b-instruct
```

**Provider** to logiczna grupa — np. "Ollama" jest jeden provider mimo że
operator może mieć 3 instances Ollama (lokalny laptop, VPS warsaw, edge
device w fabryce).

**Endpoint** to konkretne URL/socket. Każdy endpoint ma własny health
status, latency, koszt.

**Model** to konkretny model dostępny na danym endpoint. Ten sam model
może być na różnych endpointach (np. `qwen2.5:7b` w lokalnym Ollama
i w VPS Ollama — operator widzi 2 instances tego samego modelu).

### 2.2.2. Trzy widoki (toggle)

Operator może w każdej chwili przełączyć widok katalogu jednym klikiem.

#### Widok 1 — Provider-first (default)

Hierarchiczna lista providerów, expand pokazuje endpointy + modele:

```
┌──────────────────────────────────────────────────────────────┐
│  Provider Catalog                          [+ Add Provider]  │
│  Widok: [● Provider]  [○ Model]  [○ Capability]              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ Anthropic                            ●  3 modele · API    │
│       Endpoint: https://api.anthropic.com                    │
│       Status: ✓ Healthy  Latency: 412ms  Quota: 78% used     │
│       Models:                                                │
│         • claude-opus-4-7    [Premium] $15/$75 per 1M tok    │
│         • claude-sonnet-4-6  [Standard] $3/$15 per 1M tok    │
│         • claude-haiku-4-5   [Fast] $0.80/$4 per 1M tok      │
│       Last used: 12 min ago  ·  This month: $23.40           │
│                                                              │
│  ▼ Ollama (local)                       ●  3 modele · Local  │
│       Endpoint: http://localhost:11434                       │
│       Status: ✓ Running  Latency: 42ms  Models loaded: 3     │
│       Models:                                                │
│         • llama3.1:8b         [Generic] 4.5 GB  $0          │
│         • qwen2.5:7b-instruct [Generic] 4.7 GB  $0          │
│         • bielik-11b-v2.6     [Polish]  6.2 GB  $0          │
│       Last used: 2 min ago  ·  Lifetime: 1247 calls         │
│                                                              │
│  ▶ OpenRouter                           ●  47 modele · API   │
│  ▶ Google                               ●  4 modele · API    │
│  ▶ LM Studio (local)                    ●  2 modele · Local  │
│                                                              │
│  Empty slots:                                                │
│  ◌ OpenAI            [+ Add]                                 │
│  ◌ Mistral           [+ Add]                                 │
│  ◌ Custom provider   [+ Configure]                           │
│                                                              │
│  Total: 5 providers, 11 models active                        │
│  This month spend: $89.40 / $200 budget (44%)                │
└──────────────────────────────────────────────────────────────┘
```

**Decision points w widoku Provider-first**:
- Click [+ Add Provider] → wizard add new (sekcja 2.4)
- Click provider name → expand/collapse
- Click model name → model details + per-model settings
- Click [+ Add] empty slot → quick-add z predefined template
- Right-click provider → context menu (Disable, Remove, Edit, Test, Stats)

#### Widok 2 — Model-first

Płaska lista wszystkich modeli, sortable/filterable:

```
┌──────────────────────────────────────────────────────────────┐
│  Provider Catalog                          [+ Add Provider]  │
│  Widok: [○ Provider]  [● Model]  [○ Capability]              │
│  Filter: [All capabilities ▼]  Sort: [Cost ↑]               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Model Name           Provider      Type     Cost     Status │
│  ──────────────────── ──────────── ──────── ──────── ─────── │
│  llama3.1:8b          Ollama-local local    $0       ✓       │
│  qwen2.5:7b-instruct  Ollama-local local    $0       ✓       │
│  bielik-11b-v2.6      Ollama-local local    $0       ✓       │
│  qwen3.5:latest       LM Studio    local    $0       ✓       │
│  gemini-1.5-flash     Google       api      $0.075   ✓       │
│  claude-haiku-4-5     Anthropic    api      $0.80    ✓       │
│  gpt-5-mini           OpenAI       (none)   $1.50    ◌       │
│  gemini-2.5-pro       Google       api      $1.25    ✓       │
│  claude-sonnet-4-6    Anthropic    api      $3.00    ✓       │
│  mistral-large-2      Mistral      (none)   $4.00    ◌       │
│  gpt-5                OpenAI       (none)   $10.00   ◌       │
│  claude-opus-4-7      Anthropic    api      $15.00   ✓       │
│                                                              │
│  Cost shown: per 1M input tokens. Output 4-5x higher.        │
│                                                              │
│  ✓ = available  ◌ = not configured (click to add provider)   │
│  api = remote API call  local = lokalne, $0                  │
└──────────────────────────────────────────────────────────────┘
```

**Decision points w widoku Model-first**:
- Filter dropdown: text/code/vision/audio/image-gen/embedding
- Sort: cost / latency / quality / name / recency
- Click model name → details panel (capabilities, pricing breakdown,
  benchmarks, sample prompts)
- Click ◌ status → "Add provider that has this model" wizard

#### Widok 3 — Capability-first

Capability matrix — co AEIS umie i z jakimi modelami:

```
┌──────────────────────────────────────────────────────────────┐
│  Provider Catalog — Capability Matrix                        │
│  Widok: [○ Provider]  [○ Model]  [● Capability]              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CAPABILITY        AVAILABLE MODELS                  GAP?    │
│  ────────────────  ──────────────────────────────── ──────── │
│  Text generation   12 models                         ✓       │
│  Code generation   8 models                          ✓       │
│  Polish text       3 models (Bielik, Claude, GPT)    ✓       │
│  Long context      5 models (>100K)                  ✓       │
│  Vision (image in) 4 models                          ✓       │
│  Function calling  9 models                          ✓       │
│  Embeddings        2 models (nomic local + OpenAI)   ✓       │
│  Reasoning (deep)  3 models (o1, claude-opus, ...)   ✓       │
│  ────────────────  ──────────────────────────────── ──────── │
│  Image generation  0 models                         ⚠ GAP    │
│      Recommended: + OpenRouter (Flux, DALL-E)                │
│                   + Replicate (pay-per-use)                  │
│                   + Local Stable Diffusion (8GB+ VRAM)       │
│                                                              │
│  Audio gen (TTS)   0 models                         ⚠ GAP    │
│      Recommended: + ElevenLabs (best quality)                │
│                   + OpenAI TTS (cheaper)                     │
│                   + Local Coqui TTS (lokalnie)               │
│                                                              │
│  Audio transcription 1 model (Whisper local)        ✓       │
│  Video analysis     0 models                        ⚠ GAP    │
│  3D model gen       0 models                        ◌ N/A    │
│                                                              │
│  Coverage: 9/12 capabilities (75%)                           │
│  [Show acquisition advisor for gaps]                         │
└──────────────────────────────────────────────────────────────┘
```

**Decision points w widoku Capability-first**:
- Click capability → lista modeli które ją wspierają z benchmarkami
- Click "GAP" → acquisition advisor (sekcja 2.10 w części 2)
- Hover capability → tooltip z explainer co to znaczy

### 2.2.3. Toggle preferences

Operator może wybrać default widok per kontekst:

| Kontekst | Default widok | Powód |
|---|---|---|
| Pierwsza wizyta po fazie 1 | Provider | Najlepsze dla orientacji |
| Codzienna praca | Model | Szybki overview wszystkiego |
| Project planning (faza 22) | Capability | Patrzysz przez pryzmat "czego potrzebujesz" |
| Cost analysis | Model (sort by cost) | Najlepsze dla decyzji finansowych |
| Health debugging | Provider | Hierarchiczne, łatwo zlokalizować problem |

System pamięta ostatni widok per kontekst. Operator może to zmieniać.

---

## 2.3. Auto-detection lokalnych modeli (P2.2=d hybrid)

### 2.3.1. Strategie detection

System ma **4 triggers** dla scanowania lokalnych modeli:

**Trigger 1 — On launch (każde uruchomienie AEIS)**:
- Quick scan (~3-5 sek)
- Sprawdza: czy znane endpointy odpowiadają, jakie modele są loaded
- NIE skanuje filesystem dla nowych binaries

**Trigger 2 — Manual ("Re-scan local models" button)**:
- Full deep scan (~10-30 sek)
- Skanuje: PATH, common installation directories, GGUF files
- GPU benchmark dla nowo wykrytych modeli
- Aktualizuje capability tags

**Trigger 3 — File system events (continuous w tle)**:
- Watch directories: `~/.ollama/models/`, `~/.cache/lm-studio/`,
  `~/Models/`, `~/Downloads/` (dla GGUF)
- Triggered gdy: nowy plik GGUF dodany, nowy model pulled przez Ollama,
  LM Studio pobiera nowy model
- Wykrycie → toast notification "Wykryto nowy model: bielik-11b. Add?"

**Trigger 4 — Periodic background (co 30 min)**:
- Lekki ping endpointów (sprawdza czy nadal up)
- Jeśli znany endpoint ZNIKAŁ → notification + status RED
- Jeśli nowy endpoint POJAWIŁ się (np. operator uruchomił LM Studio) →
  notification "Wykryto nowy provider: LM Studio. Configure?"

### 2.3.2. Co dokładnie system skanuje

#### Ollama detection

```python
# Sequence:
1. Sprawdź `which ollama` (PATH)
   → jeśli istnieje:
2. Sprawdź czy `ollama serve` jest running:
   - Próba connect do localhost:11434/api/version
   - Jeśli timeout → "Ollama installed but not running. Start it?"
3. Lista modeli:
   - GET localhost:11434/api/tags
   - Parse: name, size, modified, family, parameter_size, quantization
4. Per model:
   - Tag jako "ollama-local"
   - Capability inference z model name (qwen* = generic, *coder* = code,
     bielik* = polish, llava* = vision)
   - Jeśli wcześniej benchmark robione → reuse, else → schedule benchmark
5. Multi-instance check:
   - Czy są running ollama na innych portach? (np. 11435, 11500)
   - Czy są ollama via Docker?
   - Czy są ollama via SSH na innych maszynach (znanych z faza 3)?
```

#### LM Studio detection

```python
1. Sprawdź `~/.lmstudio/` lub `~/.cache/lm-studio/`
2. Sprawdź czy LM Studio server is running (port 1234 default)
3. Lista modeli z `~/.lmstudio/models/`:
   - GGUF files
   - Read metadata z header GGUF (jeśli możliwe)
   - Capability inference z filename
4. Per file size: classify jako fast (<7B) / balanced (7-13B) / heavy (>13B)
```

#### llama.cpp / vLLM / TGI detection

```python
1. Sprawdź PATH dla `llama-server`, `vllm`, `text-generation-inference`
2. Sprawdź running processes (psutil)
3. Sprawdź Docker containers: `docker ps` filter na image names
4. Per running instance:
   - Probe API endpoint
   - Identyfikuj framework (różne API)
   - List models
```

#### GGUF files w common paths

```python
Search paths (configurable):
  ~/Models/
  ~/Downloads/
  ~/Documents/Models/
  /opt/models/
  /shared/models/

Per .gguf file (>1GB):
  - Filename heuristics (model family, size, quantization)
  - Sample first 1KB → check GGUF header valid
  - "Inactive model — wymaga loading via Ollama/LM Studio/llama.cpp"
  - Operator option: "Load in Ollama" → automatic `ollama create`
```

### 2.3.3. Benchmark workflow

Po wykryciu nowego modelu, system robi benchmark żeby klasyfikować:

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ  Benchmarking newly detected model: bielik-11b-v2.6      │
│                                                              │
│  Test sequence (40-60 sek total):                            │
│   ⠋  Cold start latency...        4.2s                       │
│   ⠋  First token latency...       0.8s                       │
│   ⠋  Tokens/sec (warm)...         42 tok/s                   │
│   ⠋  Polish prompt quality...     8.2/10                     │
│   ⠋  Code prompt quality...       6.1/10                     │
│   ⠋  Long-context handling...     OK (32K tested)            │
│   ⠋  Memory peak...               6.8 GB RAM                 │
│   ⠋  GPU usage...                 14 GB VRAM                 │
│                                                              │
│  Classification:                                             │
│   • Speed class: BALANCED (7B-13B equivalent)                │
│   • Best for: Polish text, content writing                   │
│   • Not great for: Code generation, complex reasoning        │
│   • Recommended roles: Polish translator, Polish writer,     │
│                         Polish summarizer                    │
│                                                              │
│  [Save to catalog]  [Re-benchmark]  [Skip]                   │
└──────────────────────────────────────────────────────────────┘
```

**Operator może**:
- Save to catalog (default — model dostępny dla future projektów)
- Re-benchmark (jeśli wynik wygląda anomalous)
- Skip (model wykryty ale nie używany — można później enable)

### 2.3.4. Auto-detection settings

Operator kontroluje detection w settings:

```
Settings → Provider Catalog → Detection
─────────────────────────────────────────────────

  ☑ On launch quick scan       (default ON)
  ☑ Manual deep scan available (default ON)
  ☑ Background file watch      (default ON)
  ☑ Periodic health check      Frequency: [30 min ▼]
  ☑ Auto-benchmark new models  (default ON)
  ☐ Auto-add detected to catalog (default OFF — ask first)

  Watch directories:
    ✓ ~/.ollama/models/
    ✓ ~/.cache/lm-studio/
    ✓ ~/Models/
    ☐ ~/Downloads/
    [+ Add custom path]

  Notify on:
    ✓ New model detected
    ✓ Provider becomes unavailable
    ✓ Quota approaching limit
    ☐ Latency degradation > 50%

  [Save]  [Restore defaults]
```

---

## 2.4. Encryption sekretów (P2.3=a — SQLite encrypted column)

### 2.4.1. Architektura storage

Zgodnie z P2.3=a, wszystkie sekrety w **jednej tabeli SQLite z encrypted
column**:

```sql
CREATE TABLE provider_credentials (
    provider_id     TEXT PRIMARY KEY,
    provider_type   TEXT NOT NULL,         -- 'anthropic', 'openai', 'custom', etc.
    display_name    TEXT NOT NULL,
    endpoint_url    TEXT NOT NULL,
    api_key_encrypted BLOB NOT NULL,        -- ENCRYPTED z master_key
    api_key_hint    TEXT,                   -- "sk-...3f8a" (last 4 chars only)
    metadata_json   TEXT,                   -- JSON: rate_limits, custom headers, etc.
    created_at      TIMESTAMP NOT NULL,
    last_used_at    TIMESTAMP,
    health_status   TEXT,                   -- 'healthy', 'degraded', 'down'
    FOREIGN KEY (provider_id) REFERENCES providers(id)
);
```

**Encryption details**:

```
Master key = derive(master_password, salt, iterations=200000) via PBKDF2-SHA256
   ↓
Per-credential nonce = random(12 bytes)
   ↓
Ciphertext = AES-256-GCM(master_key, nonce, plaintext_api_key)
   ↓
Stored: nonce || ciphertext || auth_tag
   ↓
Hint = "sk-..." + last_4_chars(plaintext_api_key) [BEZPIECZNE — nie odzyskuje klucza]
```

**Decryption flow**:

```
1. Operator akcja wymaga klucza (np. wywołanie Anthropic API)
2. AEIS sprawdza czy master_key jest cached w memory:
   - YES → użyj cached
   - NO → prompt operator dla master_password
3. Decrypt klucza on-demand (nie cache plaintext!)
4. Use klucz dla API call
5. Zero out plaintext z memory natychmiast po użyciu
```

### 2.4.2. Master key lifecycle

**Co mieści się w memory** (i jak długo):

```
master_key (derived from password):
  Cached in memory: PRZEZ CAŁĄ SESJĘ (do exit AEIS)
  Reason: PBKDF2 derivation kosztuje ~200ms per użycie

plaintext_api_keys:
  Cached in memory: BARDZO KRÓTKO (only during API call duration)
  Reason: minimize attack surface
  Implementation: secret library (Python) z auto-zeroing memory

password (operator's input):
  Cached in memory: NIE
  Reason: nigdy nie przechowywany
  Lifecycle: input → derive master_key → drop password z memory
```

### 2.4.3. Re-prompt scenarios

Czasem AEIS musi re-promptować dla password mimo że master_key jest cached:

```
Scenarios for force re-prompt:
  1. Critical action (deploy do prod, payment trigger, GDPR delete)
     → "Confirm action with master password"

  2. Adding new high-risk provider (np. cloud credentials)
     → "Setting up cloud provider — confirm with password"

  3. Exporting sensitive data (backup z secrets)
     → "Exporting credentials — confirm"

  4. Idle timeout (configurable, default 30 min)
     → "Session inactive — re-authenticate"

  5. After security event (failed login attempt elsewhere, suspicious activity)
     → "Re-authenticate due to security event"

  6. After sleep/wake on laptop
     → "Resume from sleep — re-authenticate"

  7. Operator explicit "Lock session" button
     → "Session locked — enter password to resume"
```

Operator może wyłączyć niektóre re-prompts w settings (security/convenience
trade-off):

```
Settings → Security → Re-prompt Policy

  Re-prompt for:
    ✓ Critical actions (recommended)
    ✓ New high-risk providers (recommended)
    ✓ Sensitive exports (recommended)
    ☑ Idle timeout                   Threshold: [30 min ▼]
    ☑ Sleep/wake events              (default ON)
    ☑ Security events                (always ON, not toggleable)
    ☐ After every API call           (most secure, annoying)
```

### 2.4.4. Backup considerations

Backup z fazy 1 (Daily, 30d retention) **automatycznie** szyfruje sekrety:

```
Backup file structure (encrypted bundle):
  ─────────────────────────────────────────
  metadata.json               (NOT encrypted — operator-readable)
  workspace.db.encrypted      (full DB including credentials table)
  audit_chains.tar.encrypted  (audit logs)
  artifacts/                  (per-project files, encrypted if contain secrets)

Restore flow:
  1. Operator wybiera backup file
  2. AEIS prompt dla master_password z TEGO backup-u (może być inny niż current!)
  3. Decrypt backup
  4. Re-encrypt z current master_key (jeśli operator ma już active workspace)
     LUB: replace current workspace całkowicie (clean restore)
```

---

## 2.5. Predefined provider templates (P2.4=b)

### 2.5.1. Template catalog

AEIS zna **default templates** dla najczęstszych providerów. Każdy template
zawiera:

```yaml
provider_template:
  id: anthropic
  display_name: Anthropic
  category: api  # api / local / agg / custom
  website: https://anthropic.com
  description: Claude family — Opus, Sonnet, Haiku
  
  endpoint:
    base_url: https://api.anthropic.com
    api_version: 2023-06-01
    auth_type: bearer
    auth_header: x-api-key
  
  key_format:
    pattern: "^sk-ant-[a-zA-Z0-9_-]{50,}$"
    example: "sk-ant-api03-XXXXXXXXX"
    masked_display: "sk-ant-...{last_4}"
  
  models:
    - id: claude-opus-4-7
      display_name: Claude Opus 4.7
      tier: premium
      capabilities: [text, code, vision, function_calling, long_context, reasoning]
      context_window: 200000
      max_output: 64000
      cost_per_1m_input: 15.00
      cost_per_1m_output: 75.00
      latency_class: balanced  # fast / balanced / slow
      best_for: [complex_reasoning, security_critical, code_review]
    
    - id: claude-sonnet-4-6
      display_name: Claude Sonnet 4.6
      tier: standard
      ...
    
    - id: claude-haiku-4-5
      display_name: Claude Haiku 4.5
      tier: fast
      ...
  
  rate_limits:
    rpm: 4000  # requests per minute
    tpm: 400000  # tokens per minute
    rpd: 5000000  # requests per day
  
  pricing_model: pay_as_you_go
  billing_notes:
    - Prepaid credits albo postpaid invoice
    - Volume discounts powyżej $1k/month
    - Beta features dostępne dla Tier 4+ accounts
  
  acquisition:
    signup_url: https://console.anthropic.com/signup
    signup_difficulty: easy  # easy / medium / hard
    requires_payment_method: true
    free_credits_signup: $5
    typical_time_to_first_call: 5_min
  
  health_check:
    method: GET
    path: /v1/models
    expected_status: 200
    timeout_seconds: 10
  
  test_prompt:
    model: claude-haiku-4-5  # use cheapest for test
    prompt: "Reply with just 'OK'"
    expected_pattern: "OK|ok"
    max_cost: 0.001
```

### 2.5.2. Predefined templates list (24 templates na start)

**Tier 1 — Most common** (auto-suggested w wizard):

| Template | Type | Models count | Quality | Setup difficulty |
|---|---|---|---|---|
| Anthropic | api | 3 (Opus/Sonnet/Haiku) | Premium | Easy |
| OpenAI | api | 6+ (GPT-5, GPT-4o, o1, o3) | Premium | Easy |
| Google | api | 4 (Gemini 2.5 Pro/Flash, etc.) | Premium | Medium |
| OpenRouter | agg | 100+ (proxy do innych) | Variable | Easy |
| Ollama (local) | local | unlimited | Variable | Auto-detected |
| LM Studio (local) | local | unlimited | Variable | Auto-detected |

**Tier 2 — Common alternatives**:

| Template | Type | Models | Strength |
|---|---|---|---|
| Mistral | api | Mistral Large/Small/Codestral | EU-based, GDPR-friendly |
| Together AI | agg | 50+ open source models | Cheap |
| Groq | api | Llama, Mixtral on LPU | Bardzo szybki |
| DeepSeek | api | DeepSeek V3, R1 | Tani, dobry code |
| Cohere | api | Command R+ | Embeddings + RAG |
| Replicate | agg | image/audio/video models | Multi-modal |

**Tier 3 — Specialized**:

| Template | Type | Specialization |
|---|---|---|
| ElevenLabs | api | TTS (text-to-speech) |
| OpenAI (TTS only) | api | Cheaper TTS |
| Whisper API | api | Audio transcription |
| Stability AI | api | Image generation |
| Runway | api | Video generation |
| Suno | api | Music generation |
| Perplexity | api | Web-augmented search |

**Tier 4 — Polish & EU specific**:

| Template | Type | Specialization |
|---|---|---|
| SpeakLeash (Bielik) | local/api | Polish text |
| PLLuM | local | Polish gov/law |
| Mistral (EU hosted) | api | GDPR-compliant |

**Tier 5 — Custom & specialized**:

| Template | Type | Use case |
|---|---|---|
| Custom HTTP | custom | Wszystko co wystawia OpenAI-compatible API |
| Custom Ollama remote | custom | Ollama na własnym VPS |
| Custom vLLM | custom | Self-hosted vLLM server |
| Custom Tabby | custom | Self-hosted code AI |

### 2.5.3. Template update mechanism

Templates są **versioned i updatable**:

```
Settings → Provider Catalog → Template Updates

  Current template version: 2026-04-15
  Latest available: 2026-04-29 (4 dni temu)
  
  Changes since current:
    + Added: Anthropic Claude 4.7 Opus (new model)
    + Added: Mistral Large 3
    ~ Updated: OpenAI pricing (gpt-5 input -20%)
    ~ Updated: OpenRouter — 12 new models added
    - Removed: Cohere Command (deprecated by vendor)
  
  [Update templates now]  [Schedule auto-update]
  
  Update policy:
    [● Notify when updates available]
    [○ Auto-install updates]
    [○ Manual only]
```

**Template updates są bezpieczne**:
- Nie zmieniają operator's existing credentials
- Tylko dodają nowe modele do already-configured providers
- Pricing changes wyświetlane jako notification (nie auto-overwrite)
- Operator może rollback do poprzedniej wersji templates

### 2.5.4. Custom provider workflow

Operator może dodać nowy provider którego nie ma w templates. Wizard:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Custom Provider                                      │
│                                                              │
│  Step 1/4 — Identify provider type                           │
│                                                              │
│  [○] OpenAI-compatible API (most modern providers)           │
│        np. Groq, Together, custom vLLM, LiteLLM proxy        │
│                                                              │
│  [○] Anthropic-compatible API                                │
│                                                              │
│  [○] Custom HTTP (you define request/response format)        │
│                                                              │
│  [○] Local CLI tool (np. ollama-style command)               │
│                                                              │
│  [○] Don't know — let AEIS detect                            │
│        AEIS sprawdzi URL i spróbuje rozpoznać format         │
│                                                              │
│                              [Cancel]    [Next →]           │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Custom Provider                                      │
│                                                              │
│  Step 2/4 — Connection details                               │
│                                                              │
│  Provider name (display):                                    │
│  [ My Custom vLLM                                       ]    │
│                                                              │
│  Provider ID (system):                                       │
│  [ custom-vllm-1                                       ]     │
│  ↑ auto-generated from name, edit if needed                  │
│                                                              │
│  Endpoint URL:                                               │
│  [ http://192.168.1.100:8000/v1                       ]     │
│  ↑ z protokołem (http:// lub https://)                       │
│                                                              │
│  Authentication:                                             │
│  [○ Bearer token (most APIs)]                                │
│  [○ API key in header]   Header name: [ X-API-Key       ]    │
│  [○ Basic auth]                                              │
│  [○ None (unauthenticated)]                                  │
│                                                              │
│  API key:                                                    │
│  [ ••••••••••••••••••••••••••••• 👁 ]                        │
│                                                              │
│                              [← Back]    [Next →]           │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Custom Provider                                      │
│                                                              │
│  Step 3/4 — Model discovery                                  │
│                                                              │
│  AEIS spróbuje wykryć dostępne modele.                       │
│                                                              │
│  Method:                                                     │
│  [● Auto-detect (call /v1/models endpoint)]                  │
│  [○ Manual list (operator wpisuje model names)]              │
│  [○ Skip — add models później ręcznie]                       │
│                                                              │
│  ⠋ Probing http://192.168.1.100:8000/v1/models...           │
│                                                              │
│  ✓ Connected successfully                                    │
│  ✓ Found 4 models:                                           │
│                                                              │
│      ☑ qwen2.5-72b-instruct                                  │
│         Context: 32K  ·  Capabilities: text, code            │
│                                                              │
│      ☑ qwen2.5-coder-32b                                     │
│         Context: 32K  ·  Capabilities: text, code            │
│                                                              │
│      ☑ deepseek-coder-v2-16b                                 │
│         Context: 16K  ·  Capabilities: code                  │
│                                                              │
│      ☐ embedding-v2                                          │
│         Context: 8K  ·  Capabilities: embedding              │
│                                                              │
│  Per model: można edytować capabilities, set cost (default $0│
│  for self-hosted), set tier classification.                  │
│                                                              │
│                              [← Back]    [Next →]           │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Custom Provider                                      │
│                                                              │
│  Step 4/4 — Test & save                                      │
│                                                              │
│  Pre-save tests (P2.6=b — test inference):                   │
│                                                              │
│   ✓ Endpoint reachable                                       │
│   ✓ Authentication valid                                     │
│   ✓ Models list retrieved                                    │
│   ⠋ Test inference (qwen2.5-coder-32b)...                    │
│                                                              │
│   Sending: "Reply with just 'OK'"                            │
│   Received: "OK"                                             │
│   Latency: 412 ms                                            │
│   Cost: $0 (self-hosted)                                     │
│                                                              │
│   ✓ Test inference passed                                    │
│                                                              │
│  Save to catalog?                                            │
│                                                              │
│  Provider: My Custom vLLM                                    │
│  Models: 3 enabled (qwen2.5-72b, qwen2.5-coder-32b,          │
│          deepseek-coder-v2)                                  │
│  Endpoint: http://192.168.1.100:8000/v1                      │
│  Cost class: $0 (self-hosted)                                │
│                                                              │
│                              [← Back]    [Save provider]    │
└──────────────────────────────────────────────────────────────┘
```

**Edge case** — auto-detect failed, operator musi configure ręcznie:

```
⚠ Auto-detection failed.

Endpoint odpowiedział, ale w nieznanym formacie.

Operator może:
  [○ Wpisać modele ręcznie] (operator wie co provider serwuje)
  [○ Spróbować innego API protocol] (np. Anthropic-compatible
       gdy provider implementuje custom format)
  [○ Definiować custom request/response template]
       (advanced — operator pisze JSON template)
  [○ Skip detection, save provider bez modeli]
       (operator doda modele później)
```

---

## Status Część 1

---

## 2.6. Capability Matrix expanded

### 2.6.1. Lista 12 capabilities (P2C.1=a)

System śledzi 12 capabilities. Każda ma:
- **Display name** (PL+EN)
- **Internal tag** (machine-readable)
- **Description** (co to znaczy)
- **Test prompt template** (dla auto-discovery)
- **Quality benchmark** (jak system mierzy quality)
- **Default models per tier** (które są standardem)

```
┌──────────────────────────────────────────────────────────────┐
│                  AEIS CAPABILITY ONTOLOGY                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  GENERIC TEXT (text_generation)                              │
│    Generic conversational, summarization, Q&A                │
│    Test: "Summarize: 'Lorem ipsum...'"                       │
│    Quality metric: BLEU + manual rating                      │
│    Standard models: Claude/GPT/Gemini, Llama 70B+            │
│                                                              │
│  CODE GENERATION (code_generation)                           │
│    Pisanie i rozumienie kodu, refactor, debug                │
│    Test: "Write Python function that..."                     │
│    Quality metric: HumanEval / MBPP pass rate                │
│    Standard: Claude Opus, GPT-5, DeepSeek Coder, Qwen Coder  │
│                                                              │
│  POLISH TEXT (polish_text)                                   │
│    Pisanie, rozumienie, gramatyka polska                     │
│    Test: "Napisz krótkie opowiadanie po polsku..."           │
│    Quality metric: PolEval benchmark + manual                │
│    Standard: Bielik, PLLuM, Claude/GPT (multilingual)        │
│                                                              │
│  LONG CONTEXT (long_context)                                 │
│    Context window > 100K tokens, "needle in haystack"        │
│    Test: "Find specific fact in 80K token doc"               │
│    Quality metric: RULER benchmark                           │
│    Standard: Claude Opus (200K), Gemini 2.5 Pro (2M+)        │
│                                                              │
│  VISION INPUT (vision_input)                                 │
│    Rozumienie obrazów: opis, OCR, diagram analysis           │
│    Test: "Describe this image: <base64>"                     │
│    Quality metric: VQA benchmark                             │
│    Standard: GPT-5, Claude Opus (vision), Gemini, LLaVA      │
│                                                              │
│  FUNCTION CALLING (function_calling)                         │
│    Strukturyzowane tool use, JSON schema compliance          │
│    Test: "Call function get_weather with args..."            │
│    Quality metric: BFCL benchmark                            │
│    Standard: GPT, Claude, Gemini (modern), Mistral           │
│                                                              │
│  EMBEDDINGS (embeddings)                                     │
│    Vector embeddings dla semantic search, RAG                │
│    Test: similarity score na known pairs                     │
│    Quality metric: MTEB benchmark                            │
│    Standard: nomic-embed, OpenAI text-embedding-3, mxbai     │
│                                                              │
│  REASONING (reasoning_deep)                                  │
│    Multi-step logical reasoning, math, planning              │
│    Test: GSM8K, MATH problems                                │
│    Quality metric: GPQA, ARC-AGI                             │
│    Standard: o1, o3, Claude Opus, R1                         │
│                                                              │
│  IMAGE GENERATION (image_generation)                         │
│    Tworzenie obrazów z text prompt                           │
│    Test: prompt → image, manual quality                      │
│    Standard: Flux, DALL-E 3, SD3, Midjourney (przez API)     │
│                                                              │
│  AUDIO GENERATION (audio_generation)                         │
│    TTS (text-to-speech), music                               │
│    Test: text → audio, voice consistency check               │
│    Standard: ElevenLabs, OpenAI TTS, Coqui TTS               │
│                                                              │
│  AUDIO TRANSCRIPTION (audio_transcription)                   │
│    Speech-to-text                                            │
│    Test: audio sample → text, WER measurement                │
│    Standard: Whisper (lokalny lub API)                       │
│                                                              │
│  VIDEO ANALYSIS (video_analysis)                             │
│    Rozumienie video: actions, scenes, transcripts            │
│    Test: video → description                                 │
│    Standard: Gemini 2.5 Pro (video), GPT-4o (frames)         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.6.2. Capability assignment do modeli (P2C.2=d hybrid)

Per model, capability tags powstają z **3 źródeł** w kolejności priorytetu:

**Źródło 1 — Predefined template** (najsilniejsze):
```yaml
# Z template Anthropic
claude-opus-4-7:
  capabilities:
    - text_generation: { quality: 9.5, default_for: ["complex_reasoning"] }
    - code_generation: { quality: 9.2 }
    - polish_text:    { quality: 8.5 }
    - long_context:   { window: 200000 }
    - vision_input:   { quality: 9.0 }
    - function_calling: { quality: 9.3 }
    - reasoning_deep: { quality: 9.7, default_for: ["security_critical"] }
```

**Źródło 2 — Manual override** (operator decision):
```
Settings → Model: claude-opus-4-7 → Capabilities

  text_generation        9.5  [✓]  Inherited from template
  code_generation        9.2  [✓]  Inherited
  polish_text            8.5  [✓]  Inherited (override: 9.0)  ←── operator zmienia
  ...

  Custom capabilities:
  [ + Add capability ]   ← operator może dodać własne tagi
```

**Źródło 3 — Auto-discovery** (opt-in, kosztuje):
```
Settings → Model → "Run capability discovery"
  
  AEIS uruchomi ~15 test promptów ($0.20-1.50 cost zależnie od modelu)
  Każdy test mierzy konkretną capability:
    - text_generation: 3 prompty (summarize, expand, Q&A)
    - code_generation: 3 prompty (write, refactor, debug)
    - polish_text: 2 prompty (write PL, translate to PL)
    - reasoning: 3 prompty (math, logic, planning)
    - function_calling: 2 prompty (single call, multi-call)
    - long_context: 1 prompt (needle-in-haystack)
    - vision_input: 1 prompt (description) — jeśli model obsługuje
  
  Wyniki:
    Auto-detected:
      ✓ text_generation: 8.7/10
      ✓ code_generation: 7.2/10
      ✗ polish_text: 4.1/10 (poor — ten model słabo PL)
      ✓ reasoning: 8.5/10
      ✗ function_calling: 5.5/10 (inconsistent JSON)
    
    [Apply to model]  [Discard]  [Re-run]
```

### 2.6.3. Capability matrix UI

Główny screen capability matrix:

```
┌──────────────────────────────────────────────────────────────┐
│  Capability Matrix                            [Refresh stats]│
│                                                              │
│  Filter: [● All capabilities] [○ Gaps only] [○ Strong only]  │
│  Sort: [Coverage ↓]                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CAPABILITY          MODELS  BEST              QUALITY  STAT │
│  ─────────────────── ──────  ──────────────────  ─────  ──── │
│  Text generation     12      claude-opus-4-7     9.5    ✓✓✓ │
│  Code generation     8       claude-opus-4-7     9.2    ✓✓✓ │
│  Polish text         3       Bielik-11b-v2.6     8.7    ✓✓  │
│  Long context        5       gemini-2.5-pro      9.8    ✓✓✓ │
│  Vision input        4       gpt-5               9.4    ✓✓  │
│  Function calling    9       claude-sonnet-4.6   9.0    ✓✓✓ │
│  Embeddings          2       nomic-embed-text    7.5    ✓   │
│  Reasoning deep      3       o3                  9.6    ✓✓  │
│  Image generation    0       —                   —      ✗GAP│
│  Audio generation    0       —                   —      ✗GAP│
│  Audio transcript    1       whisper-large-v3    8.8    ✓   │
│  Video analysis      0       —                   —      ✗GAP│
│                                                              │
│  Coverage: 9/12 capabilities (75%)                           │
│                                                              │
│  Status legend:                                              │
│    ✓✓✓  3+ models, multiple quality tiers (resilient)        │
│    ✓✓   2+ models, has fallback                              │
│    ✓    1 model only (no fallback)                           │
│    ✗GAP no models                                            │
│                                                              │
│  [View gap details]  [Acquisition advisor]                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.6.4. Gap detection (P2C.3=hybrid)

Gap pojawia się gdy:

**Always-gap** (oczywiste, niezależne od projektu):
- 0 modeli z daną capability
- 1 model z capability + flag "single point of failure"

**Project-driven gap** (z heurystyką projektowej potrzeby):

Operator goals z fazy 1 wpływają na które gaps są highlighted:

```python
# Pseudokod heurystyki

def detect_relevant_gaps(operator_goals, available_capabilities):
    relevant_gaps = []
    
    if "public_products" in operator_goals:
        # Public products zwykle potrzebują UI/UX → image gen przydatne
        if not has_capability("image_generation"):
            relevant_gaps.append("image_generation")
        # Multi-language likely → polish_text, multilingual
        if not has_capability("polish_text"):
            relevant_gaps.append("polish_text")
    
    if "cybersecurity" in operator_goals:
        # Security-heavy → reasoning_deep important
        if not has_capability("reasoning_deep"):
            relevant_gaps.append("reasoning_deep")
        # Long context dla security audits (large codebases)
        if not has_capability("long_context"):
            relevant_gaps.append("long_context")
    
    if "research" in operator_goals:
        # Research → deep reasoning + long context
        if not has_capability("reasoning_deep"):
            relevant_gaps.append("reasoning_deep")
    
    if "apps_internal" in operator_goals:
        # Internal tools — basic capabilities wystarczą
        # Tylko critical gaps: text + code
        pass
    
    return relevant_gaps
```

**Gap levels**:

```
CRITICAL  — capability brakująca + operator goals jej wymagają
            → Notification: "Bez X nie zbudujesz typowych projektów dla
              twoich goals. Sugerujemy acquisition."
WARNING   — capability brakująca, ale niekrytyczna dla goals
            → Sugestia w panel "Co warto rozważyć"
INFO      — capability ma 1 model (no fallback)
            → "Single point of failure dla X. Rozważ dodanie alternatywy"
OK        — capability ma 2+ models
```

### 2.6.5. Settings — capability tracking

```
Settings → Capability Matrix → Detection

  ☑ Auto-detect capabilities z templates
  ☑ Allow manual override per model
  ☐ Auto-run discovery dla nowych modeli (kosztuje)
  
  Discovery cost limit:
    Per model:    [ $1.50 ▼ ]
    Per session:  [ $10.00 ▼ ]
  
  Gap detection sensitivity:
    [● Goal-driven (only relevant gaps shown)]
    [○ Strict (all gaps shown, even if not relevant to goals)]
    [○ Permissive (only critical gaps shown)]
  
  Update capability scores:
    [● Manual] (operator zmienia)
    [○ Auto from project usage] (po N projektach, system uczy się)
    [○ Auto from external benchmarks] (gdy publikowane)
```

---

## 2.7. Sugestie lokalnych instalacji

### 2.7.1. Image generation lokalnie (P2C.4 image=d)

Operator wybrał **pełną listę z categorization**. Lista sugerowanych modeli
image-gen lokalnych:

```
Image Generation — Local Models Catalog

═══ GENERAL PURPOSE ═══

  Stable Diffusion 3.5 Large
    Size: 8.5 GB (FP16)
    VRAM: 16+ GB rekomendowane
    Quality: 9.0/10 (general)
    Speed: 8-15 sek per image (RTX 4090)
    License: Stability Community (commercial OK pod warunkiem)
    Install: Diffusers / ComfyUI / Automatic1111
    Strengths: Photorealistic, prompt adherence
    Weaknesses: Wymaga VRAM, slow

  Stable Diffusion XL
    Size: 6.5 GB
    VRAM: 12+ GB
    Quality: 8.5/10
    Speed: 5-10 sek per image
    License: SDXL CreativeML Open RAIL++-M
    Best for: Most general use

  FLUX.1 Schnell  ← lekka, dobra dla testów
    Size: 23 GB (FP8 reduced: 12 GB)
    VRAM: 24 GB (FP16) lub 16 GB (FP8)
    Quality: 9.5/10 (one of best)
    Speed: 1-2 sek per image (4 step diffusion)
    License: Apache 2.0 (open!)
    Best for: Fast iteration, high quality

  FLUX.1 Dev
    Size: 23 GB
    VRAM: 24 GB+
    Quality: 9.7/10
    Speed: 8-15 sek (50 steps)
    License: FLUX.1 [dev] Non-Commercial
    Best for: Final renders, non-commercial use only

═══ ARTISTIC / STYLIZED ═══

  Stable Diffusion 1.5 + LoRAs
    Size: 4 GB base + LoRA per style
    VRAM: 8 GB
    Quality: 7.5/10 (depends on LoRA)
    Speed: 3-5 sek
    Best for: Specific art styles, anime, manga, painterly

  Pony Diffusion v6 XL
    Size: 6.5 GB
    VRAM: 12 GB
    Quality: 8.5/10 (artistic)
    Best for: Artistic, character art, illustration
    ⚠ Trained on diverse content — review terms carefully

═══ PHOTO-REALISTIC ═══

  Juggernaut XL (FP16)
    Size: 6.5 GB
    VRAM: 12 GB
    Quality: 9.0/10 (photo)
    Best for: Photorealism, marketing imagery

  RealVisXL
    Size: 6.5 GB
    VRAM: 12 GB
    Quality: 8.8/10 (photo)
    Best for: Realistic portraits, product photography

═══ ANIME / MANGA ═══

  Animagine XL 4
    Size: 7 GB
    VRAM: 12 GB
    Quality: 9.0/10 (anime)
    Best for: Anime, manga style

  NovelAI-style models (community)
    Various sizes 4-8 GB
    Quality: 8.5/10 (anime)

═══ NSFW-EXPLICIT — ⚠ WARNINGS ═══

  System NIE auto-installs ani auto-suggests NSFW models.
  Operator może dodać manually z disclaimers:
  - Confirm legal age in jurisdiction
  - Confirm intended use (research, art, etc.)
  - Sign-off "I understand content moderation is my responsibility"
  
  Examples (only listed for awareness):
    Pony Diffusion (NSFW variant)
    NovelAI uncensored variants
    Etc.
  
  AEIS recommends:
  ✗ DO NOT use NSFW models w projektach komercyjnych dla klientów
  ✗ DO NOT publish NSFW outputs bez explicit user consent
  ✓ DO use w research/art context z proper disclaimers
  ✓ DO use moderation pipeline (W19 Policy Plane) na outputs
```

**UI dla operatora**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Local Image Generation Setup                             │
│                                                              │
│  AEIS wykrył że masz GPU (RTX 4090, 24 GB VRAM).             │
│  Sugerowane modele dla twojego sprzętu:                      │
│                                                              │
│  ┌─ PRIMARY (start tu) ─────────────────────────────────┐    │
│  │  ★ FLUX.1 Schnell                                    │    │
│  │    Quality: 9.5/10 · Speed: fast (1-2s) · 23 GB      │    │
│  │    [Install via ComfyUI]  [Why Schnell first?]       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ ALTERNATIVES ────────────────────────────────────────┐   │
│  │  ☐ Stable Diffusion 3.5 Large (general, 8.5 GB)     │   │
│  │  ☐ FLUX.1 Dev (best quality, non-commercial)         │   │
│  │  ☐ Juggernaut XL (photo-realistic)                   │   │
│  │  ☐ SDXL base (most flexible)                         │   │
│  │  [Show artistic / anime / specialized]               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ⚠ NSFW models hidden by default. [Show with disclaimers]    │
│                                                              │
│  ┌─ INSTALLATION FRAMEWORK ─────────────────────────────┐    │
│  │  [● ComfyUI (recommended, flexible)        ]          │   │
│  │  [○ Diffusers (Python library, lightweight)]          │   │
│  │  [○ Automatic1111 WebUI (most features)    ]          │   │
│  │  [○ Already installed — just register endpoint]       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Skip image generation]  [Install selected]                 │
└──────────────────────────────────────────────────────────────┘
```

### 2.7.2. TTS lokalnie (P2C.4 TTS=d) — Multiple z language matrix

```
TTS Local Models — Language Coverage Matrix

                      PL    EN    DE    FR    UK    ES    IT
                      ───   ───   ───   ───   ───   ───   ───
Coqui XTTS-v2         ✓✓    ✓✓✓   ✓✓✓   ✓✓✓   ✓     ✓✓✓   ✓✓✓
Piper                 ✓     ✓✓✓   ✓✓    ✓✓    ✗     ✓✓    ✓✓
Tortoise TTS          ✗     ✓✓✓   ✗     ✗     ✗     ✗     ✗
Bark                  ✓     ✓✓    ✓✓    ✓✓    ✗     ✓✓    ✓
Mimic 3 (Mycroft)     ✗     ✓✓    ✓     ✗     ✗     ✗     ✗
Marytts               ✗     ✓✓    ✓✓    ✓✓    ✗     ✓     ✓
F5-TTS                ✓     ✓✓✓   ✓     ✓     ✗     ✓     ✗

Quality:  ✓ basic · ✓✓ good · ✓✓✓ excellent

═══ DEFAULT RECOMMENDATIONS ═══

For Polish + English (typical SYLION operator):
  Primary: Coqui XTTS-v2
    - Multilingual (16 languages)
    - Voice cloning from 6-30 sec sample
    - Good Polish quality
    - Apache 2.0 license
    Size: 2 GB · VRAM: 4-8 GB · Latency: 0.5-2s
  
  Alternative (lighter): Piper
    - Fast, CPU-friendly
    - Polish OK (limited voices)
    - MIT license
    Size: 50-200 MB · CPU only · Latency: 0.2-1s

For broader language coverage:
  Primary: Coqui XTTS-v2
  Backup: F5-TTS (newer, very natural English)

For voice cloning needs:
  Coqui XTTS-v2 is best (built-in cloning)
```

**UI dla TTS setup**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Local TTS Setup                                          │
│                                                              │
│  Languages you'll use most:                                  │
│  [☑ Polski]  [☑ English]  [☐ Deutsch]                       │
│  [☐ Français]  [☐ Українська]  [☐ Other...]                 │
│                                                              │
│  Based on your selection, recommended:                       │
│                                                              │
│  ┌─ PRIMARY ───────────────────────────────────────────┐     │
│  │  ★ Coqui XTTS-v2                                    │     │
│  │    Excellent PL + EN, voice cloning, 2 GB           │     │
│  │    [Install via Python]  [Why this?]                │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─ LIGHTER ALTERNATIVE ──────────────────────────────┐      │
│  │  ☐ Piper                                           │      │
│  │    Fast, CPU-only, smaller. Limited voices.        │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ☐ Also install Whisper (audio transcription) — completes   │
│     the audio stack for STT ↔ TTS                            │
│                                                              │
│  [Skip TTS]  [Install selected]                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.7.3. Auto-install workflow (P2C.5=b)

Operator wybrał **pull + benchmark + add to catalog automatically**.

```
Operator klika [Install via ComfyUI] dla FLUX Schnell:

  ┌────────────────────────────────────────────────────────┐
  │  ⚙ Installing FLUX.1 Schnell                           │
  │                                                        │
  │  [1/4] Checking ComfyUI installation...                │
  │        ✓ ComfyUI detected at /opt/comfyui              │
  │                                                        │
  │  [2/4] Downloading model (23 GB)...                    │
  │        ████████████░░░░░░░░  62% (14.2 GB / 23 GB)    │
  │        Speed: 45 MB/s · ETA: 3 min 15s                 │
  │                                                        │
  │  [3/4] Verifying integrity...                          │
  │        Pending                                         │
  │                                                        │
  │  [4/4] Loading + benchmark...                          │
  │        Pending                                         │
  │                                                        │
  │  [Cancel install]                                      │
  └────────────────────────────────────────────────────────┘

After completion:
  ┌────────────────────────────────────────────────────────┐
  │  ✓ FLUX.1 Schnell installed and benchmarked            │
  │                                                        │
  │  Benchmark results:                                    │
  │   • Cold start: 8.2s                                   │
  │   • Generation (1024x1024, 4 steps): 1.8s             │
  │   • VRAM peak: 18.4 GB                                 │
  │   • Quality (sample prompt): 9.4/10                    │
  │                                                        │
  │  Auto-classified as:                                   │
  │   • Capability: image_generation                       │
  │   • Tier: premium                                      │
  │   • Speed class: fast                                  │
  │   • Best for: rapid prototyping, hero images          │
  │                                                        │
  │  Added to provider catalog:                            │
  │   • Provider: ComfyUI (local)                          │
  │   • Endpoint: http://localhost:8188                    │
  │   • Model: FLUX.1 Schnell                              │
  │                                                        │
  │  Capability matrix updated:                            │
  │   • image_generation: 0 → 1 model ✓ (gap closed!)      │
  │                                                        │
  │  [View in catalog]  [Done]                             │
  └────────────────────────────────────────────────────────┘
```

### 2.7.4. Co jeśli brak Ollama / framework (P2C.6=d)

Operator wybrał **alternative — system może sugerować lighter alternative**.

```
Sugestia: "Install Bielik 11B" → operator klika [Install]

System sprawdza:
  ✗ Ollama: not detected
  ✗ LM Studio: not detected
  ✗ llama.cpp: not detected

┌──────────────────────────────────────────────────────────────┐
│  ⚠  Local model framework not installed                      │
│                                                              │
│  Aby zainstalować lokalny model, potrzebujesz frameworka.    │
│                                                              │
│  Opcje (od najlepszego do alternatyw):                       │
│                                                              │
│  ┌─ RECOMMENDED ────────────────────────────────────────┐    │
│  │  Ollama                                               │   │
│  │  Najpopularniejszy, easy install, dobry wsparcie     │   │
│  │  Detect OS:  macOS                                   │   │
│  │  Install via: Homebrew                               │   │
│  │  Command: `brew install ollama`                      │   │
│  │  [Install Ollama via Homebrew]                       │   │
│  │  [Manual install — open ollama.ai]                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ ALTERNATIVES ──────────────────────────────────────┐     │
│  │  LM Studio                                          │     │
│  │  GUI-based, dobry dla początkujących                │     │
│  │  [Open lmstudio.ai download page]                   │     │
│  │                                                     │     │
│  │  llama-cpp-python                                   │     │
│  │  Pure Python, lightweight, bez extra service        │     │
│  │  Command: `pip install llama-cpp-python`            │     │
│  │  [Install via pip]                                  │     │
│  │                                                     │     │
│  │  Skip — użyć tylko API providers                    │     │
│  │  [Continue without local models]                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  Bundle Ollama z AEIS?                                       │
│  [○ Yes, bundle next install]                                │
│  ↑ Future AEIS installs zawierają Ollama (+150 MB)           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.7.5. Sugestie kontekstowe (kiedy AEIS proponuje)

Triggers dla sugestii lokalnych instalacji:

| Trigger | Czego sugeruje | Przykład |
|---|---|---|
| Operator wybrał goal "polish content" w fazie 1 | Polish text model | "Brakuje Bielik 11B" |
| Capability gap detected | Model pokrywający gap | "No image-gen — install FLUX?" |
| Project requires capability operator nie ma | Solution dla projektu | "Twój projekt wymaga TTS — install Coqui?" |
| Operator dodał API provider | Local fallback dla cost | "Anthropic dodany. Lokalny fallback dla Polish?" |
| Periodic check (co 7 dni) | Nowe modele opublikowane | "Nowy: Bielik 13B v3.0 — upgrade?" |
| Quota threshold (80%+) | Lokalny offload | "Kończysz API quota — install lokalny dla bulk?" |
| Operator profile-based | Personalizowane | "Dla SYLION-style projektów warto: ..." |

Operator może wyłączyć każdy trigger w settings:

```
Settings → Local Suggestions

  Triggers (when to suggest):
    ☑ Capability gaps (default ON)
    ☑ Project-driven needs
    ☑ Periodic update checks    Frequency: [Weekly ▼]
    ☑ Quota threshold alerts    Threshold: [80% ▼]
    ☐ Profile-based proactive   (default OFF — może być spammy)
    ☐ After API provider added  (default OFF)
  
  Notifications:
    [● In-app + email]
    [○ In-app only]
    [○ Silent (log only, no alerts)]
  
  Cooldown:
    Suggested model rejected → don't suggest again for: [7 days ▼]
    "Ignore future" → permanently
```

---

## 2.8. Acquisition Advisor

### 2.8.1. Recommendation logic (P2C.7=b — best quality)

Operator wybrał **best quality** jako primary recommendation. To znaczy że
gdy AEIS proponuje "kup nowy provider", primary suggestion jest tym który
**maksymalizuje quality**, nawet jeśli kosztuje więcej.

Pseudokod:

```python
def recommend_acquisition(missing_capability, operator_profile):
    candidates = find_providers_offering(missing_capability)
    
    # Score per candidate
    for candidate in candidates:
        quality_score = candidate.benchmark_for(missing_capability)
        cost_score = inverse(candidate.cost_per_unit)
        setup_score = inverse(candidate.setup_difficulty)
        
        # P2C.7=b: quality dominant
        composite_score = quality_score * 0.7 + cost_score * 0.15 + setup_score * 0.15
    
    primary = max(candidates, key=composite_score)
    secondary = second_best
    alternatives = remaining_top_5
    
    return {
        "primary": primary,
        "secondary": secondary,
        "alternatives": alternatives,
        "comparison": full_table
    }
```

**Konsekwencje wyboru "best quality"**:
- Primary suggestion zwykle drogi (ElevenLabs > OpenAI TTS)
- Operator widzi quality-first ranking
- "Cheap alternatives" są pokazywane ale nie jako primary

### 2.8.2. Acquisition advisor UI

Trigger: capability gap + operator klika "Acquisition advisor" lub
project-time advisor automatically pokazuje.

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Acquisition Advisor — Image Generation                   │
│                                                              │
│  Twoje capability matrix nie zawiera image_generation.       │
│  Twój projekt "Sylion Tailor" wymaga generowania zdjęć       │
│  produktów (faza 28).                                        │
│                                                              │
│  ─── PRIMARY RECOMMENDATION ──────────────────────────────   │
│                                                              │
│  ★ OpenRouter                                                │
│                                                              │
│  Why primary:                                                │
│    • Access do FLUX, DALL-E 3, Midjourney, SD3 — najlepsza   │
│      quality jednym kluczem                                   │
│    • Najszybszy time-to-first-call (~5 min sign-up)          │
│    • Pay-per-use, no subscription minimum                    │
│    • Quality score: 9.5/10 (highest among API providers)     │
│                                                              │
│  Cost expectation:                                           │
│    • DALL-E 3: $0.04 per image (1024x1024)                   │
│    • FLUX schnell: $0.003 per image                          │
│    • Midjourney V6: $0.10 per image                          │
│    • Twój projekt potrzebuje ~50 zdjęć produktów             │
│      Expected: $1.50-5.00 total                              │
│                                                              │
│  Setup: 5 minut                                              │
│    1. Sign up at openrouter.ai                               │
│    2. Add credits ($5 minimum)                               │
│    3. Generate API key                                        │
│    4. Paste into AEIS                                        │
│                                                              │
│  [Open OpenRouter signup]  [Setup later]                     │
│                                                              │
│  ─── SECONDARY ───────────────────────────────────────────   │
│                                                              │
│  ◇ Replicate                                                 │
│  Quality: 8.5/10 · Cost: $0.04-0.08 per image                │
│  Time-to-first-call: 10 min                                  │
│  Best for: model variety, video too                          │
│                                                              │
│  [Show details]  [Compare with primary]                      │
│                                                              │
│  ─── ALTERNATIVES ────────────────────────────────────────   │
│                                                              │
│  ▶ Stable Diffusion lokalnie                                 │
│    Quality: 8.0/10 · Cost: $0 · VRAM: 12+ GB needed          │
│    Time-to-first-call: 30 min (download + setup)             │
│                                                              │
│  ▶ Anthropic + Claude vision (analysis only, NIE gen)        │
│    Quality: N/A · Note: Claude widzi obrazy, ale nie         │
│    generuje. Nie pokrywa twojej potrzeby.                    │
│                                                              │
│  ▶ Stability AI direct API                                   │
│    Quality: 8.5/10 · Cost: $0.005-0.04 per image             │
│    Time-to-first-call: 7 min                                 │
│                                                              │
│  [Comparison matrix — show all]                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.8.3. Comparison matrix (expandable)

```
┌──────────────────────────────────────────────────────────────┐
│  Image Generation — Comparison Matrix                        │
│                                                              │
│  Provider          Q/10  Cost/img    Setup   Notes           │
│  ───────────────── ────  ─────────  ──────  ──────────────── │
│  OpenRouter        9.5   $0.003-0.10 5 min  Multi-vendor★    │
│  Replicate         8.5   $0.04-0.08  10 min Multi-modal      │
│  Stability AI      8.5   $0.005-0.04 7 min  SD-focused       │
│  DALL-E (OpenAI)   9.0   $0.04       5 min  W ramach OpenAI  │
│  Midjourney        9.7   $0.10       30 min Discord-based    │
│  Local FLUX        9.5   $0          30 min VRAM 24GB+ req   │
│  Local SDXL        8.5   $0          20 min VRAM 12GB+       │
│  Local SD 1.5      7.5   $0          15 min VRAM 8GB+        │
│                                                              │
│  ★ Primary recommendation                                    │
│                                                              │
│  Sortuj wg:                                                  │
│  [● Quality]  [○ Cost]  [○ Setup speed]  [○ Composite]      │
└──────────────────────────────────────────────────────────────┘
```

### 2.8.4. Acquisition flow (P2C.8=b — aktywny return)

Operator klika "Open OpenRouter signup":

```
Step 1: Browser otwiera openrouter.ai/signup
        AEIS pokazuje persistent banner:
        
  ┌────────────────────────────────────────────────────────┐
  │  🟡  Acquisition in progress: OpenRouter               │
  │  AEIS czeka na twój API key. Powrócę gdy gotowy.       │
  │  [I have my key]  [Cancel acquisition]                 │
  └────────────────────────────────────────────────────────┘

Step 2: Operator sign-up + dostaje key + wraca do AEIS

Step 3: AEIS wykrywa powrót (window focus event):

  ┌────────────────────────────────────────────────────────┐
  │  ●  Welcome back. Did you complete OpenRouter setup?  │
  │                                                        │
  │  Wpisz swój OpenRouter API key:                        │
  │                                                        │
  │  [ sk-or-v1-•••••••••••••••••••••••• 👁 ]              │
  │                                                        │
  │  [Verify and add]  [Not yet — close]                   │
  │                                                        │
  │  Tip: skopiowanie klucza do clipboard auto-paste'uje  │
  │  if you allow detection.                               │
  └────────────────────────────────────────────────────────┘

Step 4: Test inference (P2.6=b):
  
  ⠋ Testing OpenRouter...
  ✓ API key valid
  ✓ Test inference passed (FLUX schnell)
  ✓ Latency: 1.4s
  ✓ Cost: $0.003 (1 image generated as test)
  
  Adding to catalog...
  
  ✓ OpenRouter added with 47 models
  ✓ Capability matrix updated:
     image_generation: 0 → 8 models ✓
     audio_generation: 0 → 3 models ✓
     video_analysis: 0 → 2 models ✓
  ✓ 3 gaps closed!

Step 5: Auto-suggest next steps:
  
  ┌────────────────────────────────────────────────────────┐
  │  🎉  3 gaps closed by adding OpenRouter                │
  │                                                        │
  │  Następne sugerowane kroki:                            │
  │                                                        │
  │  • Configure cost limits dla OpenRouter                │
  │    (faza 2.9 — Cost & Priority Profiles)               │
  │                                                        │
  │  • Add OpenRouter do default fallback chain dla        │
  │    image_generation                                    │
  │                                                        │
  │  • Test image generation w sandbox project             │
  │                                                        │
  │  [Configure cost limits]  [Skip — return to faza 2]    │
  └────────────────────────────────────────────────────────┘
```

### 2.8.5. Acquisition history (P2C.9=c — niezależne sytuacje)

Operator wybrał **każda sytuacja sugestii niezależna** — system nie pamięta
historic decisions, każda sugestia oceniana świeżo.

To znaczy:
- Jeśli operator pominął OpenRouter w marcu, w kwietniu może być znowu sugerowany
- AEIS nie nauczy się że operator "nie chce" konkretnego providera
- Brak persistent "ignore list"

**Konsekwencja**: operator może czuć się "spammed" jeśli stale ignoruje
sugestie. AEIS pokazuje **opt-out** w każdej sugestii:

```
┌────────────────────────────────────────────────────────┐
│  💡  Capability gap: audio_generation                   │
│                                                        │
│  Sugerowane: ElevenLabs (best quality TTS)             │
│                                                        │
│  [Open signup]  [Install local Coqui]                  │
│  [Not interested in TTS]  [Remind me later]            │
│                                                        │
│  ☐ Don't show acquisition advisor for audio_generation │
│      again w tym workspace                             │
└────────────────────────────────────────────────────────┘
```

Mimo P2C.9=c, operator może świadomie suppressować per capability — to
nie jest "history-based" ale "operator-explicit-action".

---

## 2.9. Cost & Priority Profiles

### 2.9.1. Priority chains UX (P2C.10=d hybrid)

Operator wybrał **profile templates + manual override**. Workflow:

**Krok 1**: Operator wybiera template:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Priority Chain Configuration                             │
│                                                              │
│  Chains define: gdy AEIS potrzebuje capability X,            │
│  którego model używa first, second, third, etc.              │
│                                                              │
│  Wybierz starting template:                                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○] Conservative                                     │    │
│  │     Lokalne first, API tylko gdy konieczne           │    │
│  │     Cel: minimum cost                                │    │
│  │     Quality: średnia                                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [●] Balanced (recommended)                           │    │
│  │     Mix lokalnych (cheap tasks) + API (premium)      │    │
│  │     Cel: optimal cost/quality                        │    │
│  │     Quality: wysoka                                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○] Aggressive                                       │    │
│  │     Premium API first, lokalne tylko fallback        │    │
│  │     Cel: maximum quality                             │    │
│  │     Cost: high                                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  [Customize from template]  [Use template as-is]             │
└──────────────────────────────────────────────────────────────┘
```

**Krok 2**: Po klick "Customize", operator widzi chain editor:

```
┌──────────────────────────────────────────────────────────────┐
│  Priority Chain — text_generation                            │
│  Template: Balanced (modified)                               │
│                                                              │
│  Drag to reorder. Click to edit. + add fallback.             │
│                                                              │
│  Priority 1 (primary):                                       │
│    ┌─────────────────────────────────────────────────┐      │
│    │ ⠿  claude-sonnet-4-6        $3/1M         [edit] │      │
│    │    Conditions: cost < $0.50/call               │      │
│    └─────────────────────────────────────────────────┘      │
│                                                              │
│  Priority 2 (high-stakes):                                   │
│    ┌─────────────────────────────────────────────────┐      │
│    │ ⠿  claude-opus-4-7          $15/1M        [edit] │      │
│    │    Conditions: D-level >= D4                    │      │
│    └─────────────────────────────────────────────────┘      │
│                                                              │
│  Priority 3 (cheap fallback):                                │
│    ┌─────────────────────────────────────────────────┐      │
│    │ ⠿  qwen2.5:7b (local)       $0           [edit]  │      │
│    │    Conditions: when API quota exhausted          │      │
│    └─────────────────────────────────────────────────┘      │
│                                                              │
│  Priority 4 (ultimate fallback):                             │
│    ┌─────────────────────────────────────────────────┐      │
│    │ ⠿  bielik-11b (local)       $0           [edit]  │      │
│    │    Conditions: any availability                  │      │
│    └─────────────────────────────────────────────────┘      │
│                                                              │
│  [+ Add fallback model]  [Save chain]  [Reset to Balanced]   │
└──────────────────────────────────────────────────────────────┘
```

**Krok 3**: Per priority entry, conditions editor:

```
┌────────────────────────────────────────────────────────┐
│  Edit Priority Entry — claude-opus-4-7                 │
│                                                        │
│  Use this model when:                                  │
│                                                        │
│  ☑ D-level reaches threshold:  [D4 ▼]                  │
│  ☐ Cost per call < limit:      [$ ___ ]               │
│  ☐ Latency requirement <:      [___ ms]               │
│  ☐ Operator goal includes:     [____________]          │
│  ☐ Project type matches:       [____________]          │
│  ☐ Time of day:                [___ - ___]            │
│  ☐ Budget remaining > %:        [___]%                │
│  ☐ Custom expression (advanced): [_____________]       │
│                                                        │
│  Skip this model when:                                 │
│  ☐ Quota exhausted                                     │
│  ☐ Latency > [___ ms]                                 │
│  ☐ Health degraded                                     │
│  ☐ Cost cap reached                                    │
│                                                        │
│  [Save conditions]  [Cancel]                           │
└────────────────────────────────────────────────────────┘
```

### 2.9.2. Cost limits (P2C.11=d konfigurowalne levels)

Operator wybrał **konfigurowalne — wybiera które levels włączyć**.

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Cost Limits Configuration                                │
│                                                              │
│  Włącz limity na poziomach których chcesz monitorować:       │
│                                                              │
│  ☑ Global / monthly limit                                    │
│      Total monthly spend cap: [$ 500.00 ▼]                   │
│      Alert at: [80%]   Pause at: [95%]   Hard stop: [100%]   │
│                                                              │
│  ☑ Per provider                                              │
│      Anthropic:    [$ 200/mo ▼]  Alert: 80%                  │
│      OpenAI:       [$ 100/mo ▼]  Alert: 75%                  │
│      OpenRouter:   [$  50/mo ▼]  Alert: 80%                  │
│      Google:       [$  50/mo ▼]  Alert: 80%                  │
│      Local models: [$   0    ]   (no cost)                   │
│      [+ Add per-provider limit]                              │
│                                                              │
│  ☑ Per project                                               │
│      Default per-project budget: [$ 50.00 ▼]                 │
│      Override per project w fazie 17                         │
│                                                              │
│  ☑ Per call (single LLM call)                                │
│      Default cap: [$ 1.00 ▼]                                 │
│      Hard limit: [$ 5.00 ▼]                                  │
│                                                              │
│  ☐ Per role w Council (advanced)                             │
│      Can set in faza 12 (Council Templates)                  │
│                                                              │
│  ☐ Per phase                                                 │
│      Can set in workspace defaults (faza 4)                  │
│                                                              │
│  ☐ Per time period                                           │
│      Daily cap: [$ ___ ▼]                                    │
│      Hourly cap: [$ ___ ▼] (rate limiting)                   │
│                                                              │
│  ☐ Per role (across all projects)                            │
│      Critic max: [$ ___/day ▼]                              │
│                                                              │
│  [Save limits]  [Reset to defaults]                          │
└──────────────────────────────────────────────────────────────┘
```

### 2.9.3. Budget exhaustion behavior (P2C.12=d per project)

Operator wybrał **per project define behavior**.

W fazie 2 operator definiuje **default behavior** dla nowych projektów:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Default Budget Exhaustion Behavior                       │
│                                                              │
│  Co się dzieje gdy projekt zbliża się do budgetu:            │
│                                                              │
│  At 50% budget used:                                         │
│  [○ Silent (just track)]                                     │
│  [● Notification]                                            │
│  [○ Detailed breakdown email]                                │
│                                                              │
│  At 80% budget used:                                         │
│  [○ Just notification]                                       │
│  [● Notification + adaptive switch (start using cheaper      │
│     models from fallback chain)]                             │
│  [○ Pause pipeline (hard)]                                   │
│                                                              │
│  At 95% budget used:                                         │
│  [● Hard pause + require operator approval to continue]      │
│  [○ Adaptive switch only (continue with cheap models)]       │
│  [○ Email + SMS alert + pause]                              │
│                                                              │
│  At 100% budget exceeded:                                    │
│  [● Hard stop — pipeline blocked]                            │
│  [○ Continue with explicit operator override only]           │
│  [○ Allow if operator confirms within 5 min, else stop]      │
│                                                              │
│  Per-project override available w fazie 17                   │
│                                                              │
│  [Save defaults]                                             │
└──────────────────────────────────────────────────────────────┘
```

### 2.9.4. Cost dashboard

W każdym momencie operator może zobaczyć cost breakdown:

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Dashboard                  [This month ▼] [All time]  │
│                                                              │
│  Total: $89.42 / $500 budget (18%)                           │
│  Trend: -12% vs last month                                   │
│                                                              │
│  ┌─ BY PROVIDER ────────────────────────────────────────┐    │
│  │  Anthropic       ████████████░░░░  $54.20  (61%)    │    │
│  │  OpenAI          █████░░░░░░░░░░░  $18.50  (21%)    │    │
│  │  OpenRouter      ██░░░░░░░░░░░░░░   $9.00  (10%)    │    │
│  │  Google          █░░░░░░░░░░░░░░░   $5.20   (6%)    │    │
│  │  Local           ░░░░░░░░░░░░░░░░    $2.52   (3%)    │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ BY MODEL ───────────────────────────────────────────┐    │
│  │  claude-opus-4-7     ████████░░  $34.20  (38%)      │    │
│  │  claude-sonnet-4-6   ████░░░░░░  $20.00  (22%)      │    │
│  │  gpt-5               ████░░░░░░  $18.50  (21%)      │    │
│  │  ... (truncated)                                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ BY PROJECT ─────────────────────────────────────────┐    │
│  │  Sylion Tailor       █████████░░  $42.10  (47%)     │    │
│  │  Lokalny CRM         ████░░░░░░░  $18.20  (20%)     │    │
│  │  Tutorial            ███░░░░░░░░  $12.00  (13%)     │    │
│  │  Other (5 projects)  ███░░░░░░░░  $17.12  (19%)     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ BY ROLE (Council) ──────────────────────────────────┐    │
│  │  Planner             ████████░░  $32.50  (36%)      │    │
│  │  Critic              ██████░░░░  $24.00  (27%)      │    │
│  │  Security            ████░░░░░░  $14.20  (16%)      │    │
│  │  Other (6 roles)     █████░░░░░  $18.72  (21%)      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  Predicted month-end: $147 (z current rate)                  │
│  Projection: ✓ within budget                                 │
└──────────────────────────────────────────────────────────────┘
```

P2C.15=e (wszystko z toggle) — operator może toggle granularity.

---

## 2.10. Health Monitoring + Quota Tracking

### 2.10.1. 5-level health status (P2C.13=c)

Operator wybrał **5-level z konkretnymi thresholds per provider**.

System uczy się baseline per provider i klasyfikuje:

```
HEALTHY    — latency < 1.2x baseline AND success rate > 99%
DEGRADED   — latency 1.2x-2x baseline AND success rate > 95%
SLOW       — latency 2x-5x baseline AND success rate > 90%
UNRELIABLE — latency > 5x OR success rate < 90% OR sporadic timeouts
DOWN       — > 50% requests fail OR connection timeout
```

**Per provider baseline** ustawia się automatycznie w pierwszych 100 calls
albo manualnie:

```
Settings → Provider Health → claude-sonnet-4-6

  Baseline (auto-detected):
    Latency p50: 380 ms
    Latency p95: 950 ms
    Success rate: 99.7%
    Last 1000 calls
  
  Alert thresholds:
    [● Auto from baseline (1.2x / 2x / 5x rule)]
    [○ Manual: latency [___ ms] / success rate [___%]]
  
  Notification severity:
    HEALTHY → DEGRADED:    Notify (info)
    DEGRADED → SLOW:       Email + notify
    SLOW → UNRELIABLE:     Email + Slack + notify
    UNRELIABLE → DOWN:     Email + SMS + notify + auto-failover
  
  Auto-failover:
    [● Enabled — system switches to next chain entry on UNRELIABLE]
    [○ Disabled — operator decides each time]
```

### 2.10.2. Health monitoring UI

```
┌──────────────────────────────────────────────────────────────┐
│  Provider Health                                             │
│  Last updated: 12 sec ago · Auto-refresh: 30s                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Provider          Status      Latency    Success   Last Use │
│  ─────────────────  ──────────  ─────────  ────────  ──────── │
│  Anthropic          ✓ HEALTHY   412ms      99.8%     2m ago  │
│  OpenAI             ⚠ DEGRADED  1.4s ↑     99.2%     5m ago  │
│  Google             ✓ HEALTHY   620ms      99.5%     12m ago │
│  OpenRouter         ✓ HEALTHY   850ms      99.0%     1h ago  │
│  Mistral            ◌ NOT USED  —          —         never   │
│  Ollama (local)     ✓ HEALTHY   42ms       100%      30s ago │
│  ComfyUI (local)    ✓ HEALTHY   1.8s       100%      4h ago  │
│  Custom vLLM        ✗ DOWN      timeout    0%        2h ago  │
│                                                              │
│  ⚠ OpenAI is degraded                                        │
│     Latency 3.5x normal. Likely vendor-side issue.           │
│     [View incident page]                                      │
│                                                              │
│  ✗ Custom vLLM is down                                       │
│     Last successful call: 2h ago. Connection refused.        │
│     Check: VPS up? Service running?                          │
│     [Run diagnostic]  [Disable for now]                      │
│                                                              │
│  Recent incidents (last 7 days):                             │
│   • OpenAI degraded 14:30 today (currently)                  │
│   • Anthropic 5min outage 2026-04-26 16:42                   │
│   • Google rate-limited 2026-04-25 09:15-10:30              │
└──────────────────────────────────────────────────────────────┘
```

### 2.10.3. Quota tracking (P2C.14=d operator-configurable thresholds)

```
┌──────────────────────────────────────────────────────────────┐
│  Quota Status                                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Anthropic                                                   │
│    Tier: Tier 4                                              │
│    RPM (req/min):     ████░░░░░░  234 / 4000  (5.9%)         │
│    TPM (tokens/min):  ██████░░░░  18.2K / 400K (4.6%)        │
│    RPD (req/day):     ████████░░  3.2K / 5M    (0.06%)       │
│                                                              │
│    Plan limits:                                              │
│    Monthly spend:     ████████░░  $54 / $200 cap (27%)       │
│                                                              │
│    Alerts configured:                                        │
│      ☑ Notify at 50% spend                                   │
│      ☑ Email at 80% spend                                    │
│      ☑ Pause new projects at 95% spend                       │
│      ☐ Predictive alert (3-day forecast)                     │
│                                                              │
│  OpenAI                                                      │
│    Tier: Tier 3                                              │
│    RPM:               ████████░░  840 / 3500  (24%)          │
│    TPM:               ██████░░░░  12K / 250K  (5%)           │
│    Monthly:           ████░░░░░░  $18 / $100  (18%)          │
│                                                              │
│  OpenRouter                                                  │
│    Credits remaining: $4.20 / $10 (42%)                      │
│    [Top up credits]                                          │
│                                                              │
│  Predictive alerts:                                          │
│   • Anthropic: at current rate, $200 cap reached around      │
│     2026-05-15 (15 days remaining)                          │
│   • OpenRouter: credits depleted in ~7 days                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2.11. Edge Cases (P2C.15=c hybrid + P2C.16=d operator's call)

Faza 2 ma **bogatszy zakres integration** niż faza 1, więc edge cases są
liczniejsze. Zgodnie z P2C.16=d, operator wybrał **comprehensive 30
cases** (vs minimum 15 lub standard 22 z fazy 1).

30 cases pogrupowanych w 6 hybrid-categorized kategoriach. Każdy case ma:
trigger, ASCII screen, decision points, recovery scenarios.

### Kategoria A — Provider-side issues (6 cases)

#### EC-A1: Provider outage podczas projektu

**Trigger**: Anthropic ma 30-minutowy outage podczas Council deliberation
twojego projektu. AEIS detect (HEALTHY → DOWN).

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Provider outage detected: Anthropic                      │
│                                                              │
│  Status: DOWN since 14:32 (8 min ago)                        │
│  Active project: Sylion Tailor (Council deliberation, faza 23│
│                                                              │
│  Aktualnie używane Anthropic models:                         │
│    • claude-opus-4-7 (Council Chair)                         │
│    • claude-sonnet-4-6 (Planner, UX)                         │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Auto-failover (zalecane)]                                │
│      System użyje fallback z chain:                          │
│        Council Chair: claude-opus → gpt-5 (priority 2)       │
│        Planner: claude-sonnet → bielik-11b local (priority 3)│
│      Pipeline continues po max 60 sek                        │
│                                                              │
│  [○ Pause project]                                           │
│      Wait until Anthropic recovers.                          │
│      Pipeline state preserved.                               │
│                                                              │
│  [○ Manual model selection]                                  │
│      Operator wybiera inne modele dla tej sesji.            │
│                                                              │
│  [○ Cancel current Council round]                            │
│      Lose current round work, restart later.                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: auto-failover (default), pause, manual select, cancel.

**Recovery**: gdy Anthropic wraca, system pyta "Anthropic recovered. Switch
back z fallback do primary?" — operator decyduje.

#### EC-A2: Klucz API expired / revoked

**Trigger**: operator's klucz Anthropic został rotacją zrewokowany
(np. security incident vendor-side, lub operator zmienił account).

```
✗ Authentication failed: Anthropic
  Last successful call: 2026-04-15 (14 dni temu)
  Error: 401 Unauthorized
  
  Możliwe przyczyny:
   • Klucz zrewokowany przez Anthropic
   • Account suspended
   • Klucz expired (rotacja security policy)
   • Operator regenerated klucz w Anthropic console
  
  Akcje:
  [Open Anthropic console]
  [Update klucz w AEIS]
  [Disable Anthropic temporary]
  [Run full diagnostic]
```

#### EC-A3: Rate limit hit (429)

**Trigger**: AEIS dostaje 429 Too Many Requests.

System ma **adaptive backoff**:
- Exponential backoff (1s, 2s, 4s, 8s, 16s, 32s, max 60s)
- Switch do fallback w chain po 3 failed retries
- Show operator notification jeśli persistent

#### EC-A4: Provider zmienia API format (breaking change)

**Trigger**: vendor zmienia API w breaking way (rare ale się zdarza).
AEIS dostaje unexpected response format.

```
⚠ Unexpected response from OpenAI API

Expected: ChatCompletionResponse format
Got: Unknown format (parser failed)

Possible causes:
 • API version changed (vendor-side)
 • Operator's selected API version deprecated
 • Network corruption (rare)

Recommended:
 [Update OpenAI template] (download latest)
 [Pin to old API version] (specify in advanced settings)
 [Disable OpenAI until verified]
```

#### EC-A5: Provider-side bug returning bad data

**Trigger**: provider zwraca syntactically valid ale semantically broken
response (np. JSON ale truncated, incomplete tokens).

System wykrywa przez:
- Response size anomaly (tokens count vs expected)
- JSON parse fails on tool calls
- Response cut off mid-sentence

```
⚠ Response quality issue detected

Provider: OpenAI · Model: gpt-5
Issue: Response truncated at 50 tokens (expected 500+)

Sample: "The masterplan should include the following step"

Likely cause: vendor-side timeout or buffer overflow

Action: Retry with same prompt, fallback if persists
```

#### EC-A6: Provider deprecates model używany przez operatora

**Trigger**: Anthropic ogłasza deprecation `claude-sonnet-4-6` (np. EOL za
6 miesięcy). System wykrywa przy provider template update.

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ  Model deprecation announced                              │
│                                                              │
│  Anthropic ogłosił deprecation:                              │
│   • claude-sonnet-4-6 → EOL 2026-10-15 (6 miesięcy)          │
│   • Replacement: claude-sonnet-5 (preview od 2026-05-01)     │
│                                                              │
│  Twoje użycie:                                               │
│   • 14 active priority chains używają tego modelu            │
│   • 8 Council templates                                      │
│   • 23 active projektów ma go w masterplanach                │
│                                                              │
│  Migration plan suggested:                                   │
│   Phase 1 (next 30 dni):  Test claude-sonnet-5 w sandbox     │
│   Phase 2 (next 60 dni):  Update templates do v5             │
│   Phase 3 (next 90 dni):  Migrate priority chains            │
│   Phase 4 (last 60 dni):  Force-fallback dla przeterminowych │
│                                                              │
│  Akcje:                                                      │
│  [● Schedule auto-migration (rekomendowane)]                 │
│      System automatically updates references w 4 fazach      │
│  [○ Manual migration (operator controls timing)]             │
│      System tylko notify, operator zmienia                   │
│  [○ Test new version first w sandbox]                        │
│      Stwórz test project z claude-sonnet-5 dla validation    │
│  [○ Defer (force-fallback po EOL)]                           │
│      Operator wie, ale woli czekać do końca                  │
│                                                              │
│  ⚠ EOL behavior: 7 dni przed EOL, system shows daily reminder│
│                  EOL day, model przestaje działać. Calls fail.│
│                  Auto-fallback aktywuje się jeśli dostępny.  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: auto-migration (default), manual control, sandbox
test first, defer.

**Recovery**: jeśli operator zignoruje i model EOL → automatic fallback
do najbliższego z chain. System loguje incident "model_eol_force_fallback"
dla audit.

### Kategoria B — Klucze invalid / configuration errors (5 cases)

#### EC-B1: Klucz pomylony — wkleił klucz innego providera

**Trigger**: operator dodaje "Anthropic" provider, ale wkleja klucz OpenAI.

System wykrywa przez **format pattern matching**:

```
⚠ Klucz format mismatch

Provider: Anthropic
Expected pattern: sk-ant-*
Detected pattern: sk-proj-* (looks like OpenAI)

Czy to klucz OpenAI?
[● Yes, switch to OpenAI provider config]
[○ No, force-add as Anthropic anyway]
[○ Cancel — let me re-paste]
```

#### EC-B2: Klucz dla wrong tier / plan

**Trigger**: operator ma free tier OpenAI, próbuje GPT-5 (paid tier only).

```
✗ Model not accessible with current plan

Provider: OpenAI
Klucz tier: Free
Requested model: gpt-5
Required tier: Tier 1+ (paid)

Akcje:
 [Open OpenAI billing — upgrade plan]
 [Use gpt-5-mini instead] (available in free tier)
 [Use OpenRouter] (no tier restrictions)
```

#### EC-B3: Endpoint URL typo

**Trigger**: operator wpisał `https://api.anthropi.com` (literówka).

```
⚠ Endpoint nie odpowiada

URL: https://api.anthropi.com (no SSL response)

Did you mean:
 • https://api.anthropic.com (Anthropic official)?

[Use suggested URL]  [Keep typed URL]  [Cancel]
```

#### EC-B4: Custom provider header konfiguracja błędna

**Trigger**: operator dodaje custom provider z błędnym header name (np.
`Authorization: Bearer X` vs `X-API-Key: X`).

```
✗ Authentication failed for custom provider

Tested headers:
  ✗ X-API-Key: <key>
  ✗ Authorization: Bearer <key>
  ✗ api-key: <key>
  ✗ Authorization: <key>

Vendor docs link: [optional, jeśli operator wpisał]

Akcja:
[Custom header definition] (operator pisze custom)
[Send raw key in body] (some non-standard providers)
[Cancel — review docs]
```

#### EC-B5: Klucz API ujawniony publicznie (leaked)

**Trigger**: operator przypadkowo wkleił klucz w git commit / Slack /
public Discord. Anthropic auto-scan wykrywa i automatycznie revoke'uje
(common practice u top providers). AEIS dostaje 401 z special error code.

```
┌──────────────────────────────────────────────────────────────┐
│  🚨  KRYTYCZNY: Klucz API może być ujawniony                 │
│                                                              │
│  Provider: Anthropic                                         │
│  Klucz: sk-ant-...3f8a (zrewokowany 12 min temu)             │
│  Reason: vendor-side automated leak detection                │
│                                                              │
│  Możliwe miejsca leak:                                       │
│   • Git commit (repository scanning)                         │
│   • Public chat (Discord, Slack, forums)                     │
│   • Pastebin / GitHub Gist                                   │
│   • Screenshot / video screenshare                           │
│                                                              │
│  Natychmiastowe akcje:                                       │
│                                                              │
│  [● Generate new klucz]                                      │
│      Otwiera Anthropic console dla operator                  │
│      Po regeneracji, operator wkleja w AEIS                  │
│                                                              │
│  [Audit recent activity]                                     │
│      System pokazuje calls z ostatnich 24h:                  │
│       • Liczba calls                                         │
│       • Total cost                                           │
│       • Suspicious patterns (unusual hours, high volume)     │
│                                                              │
│  [Check git history dla leaked credentials]                  │
│      Auto-scan operator's git repos (jeśli skonfigurowane)   │
│      Reports gdzie klucz mógł trafić                         │
│                                                              │
│  [Notify team] (jeśli Team Lead profile)                     │
│      Email do zespołu: "Possible credential leak"            │
│                                                              │
│  ⚠ Jeśli używasz tego samego klucza w innych aplikacjach,    │
│    one też przestały działać. Update wszędzie.               │
│                                                              │
│  Long-term recommendations:                                  │
│   ☑ Enable git pre-commit hook (block credentials in commit) │
│   ☑ Rotate keys periodically (auto-rotation w fazie 4)       │
│   ☑ Use separate keys for dev/prod                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: regenerate immediately, audit history, scan git, notify
team, configure prevention.

**Recovery flow**:
1. Operator regeneruje klucz w vendor console
2. AEIS waits for new klucz paste
3. System aktualizuje wszystkie references (chains, templates, projects)
4. Auto-rotate worksprzeszczas (jeśli włączone w fazie 4)
5. Audit chain entry: `key_leaked_and_rotated` z timestamp

**Edge case wewnątrz**: jeśli operator nie ma access do vendor console
(stracił password etc.) → emergency disable provider w AEIS, switch do
fallback chain do czasu recovery.

### Kategoria C — Quota / cost edge cases (6 cases)

#### EC-C1: Sudden cost spike (per call > limit)

**Trigger**: jeden call generuje koszt > limit per call (np. operator
wkleił 500K-token prompt do Council).

```
⚠ Cost limit exceeded for single call

Estimated cost: $4.50
Per-call limit: $1.00

Block: [● Block call]  [○ Allow override]

Block (default):
  Operator widzi błąd, prompt jest cancelled.
  
Allow override:
  Operator wpisuje "I authorize $4.50 for this call"
  Call proceeds, cost zaliczony do project budget.
```

#### EC-C2: Monthly budget exhausted mid-project

**Trigger**: środek build phase, miesięczny limit Anthropic = 100% used.

Per P2C.12=d (per-project behavior), domyślnie:

```
⚠ Anthropic monthly limit reached

Active project: Sylion Tailor (build phase)
Status: paused at 78% complete

Adaptive switch options (per fallback chain):
 ✓ Council: Claude Opus → GPT-5
 ✓ Workers: Claude Sonnet → bielik-11b local + qwen-coder
 ✓ Estimated impact: -15% quality, +0% cost

Akcje:
[● Adaptive switch (default)]
[○ Increase Anthropic limit] (opens billing)
[○ Pause project until next month]
```

#### EC-C3: Forex fluctuation on EUR-billed providers

**Trigger**: Mistral bills in EUR, operator's budget w USD. EUR rate
spikes.

```
ℹ Currency rate change

Mistral spend (EUR): €23.40
Equivalent (USD): $26.10 (was $25.20 yesterday)
Difference: +3.6% due to EUR/USD rate change

Action:
 ○ Just track (no action)
 ● Adjust budget to account for forex variance (+5% buffer)
```

#### EC-C4: Hidden costs (volume tier upgrades)

**Trigger**: operator przekracza Tier 1 → Tier 2 OpenAI = automatyczny
upgrade z higher prices.

```
⚠ Tier upgrade detected: OpenAI

Previous tier: Tier 1 ($0.005/1K tokens)
New tier: Tier 2 ($0.0075/1K tokens, +50%)
Reason: monthly spend exceeded $50

Future calls will use new tier pricing automatically.
Adjust budgets accordingly.
```

#### EC-C5: Cost auto-pause race condition

**Trigger**: budget kończy się w trakcie aktywnej Council deliberation.
W trakcie 1 sekundy: 3 modele równolegle wysyłają requesty, każdy
indywidualnie poniżej limitu, ale sumarycznie przekraczają cap.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Concurrent budget overrun detected                       │
│                                                              │
│  W ciągu 800ms:                                              │
│   • Claude Opus call: $0.42 (Council Chair)                  │
│   • Claude Sonnet call: $0.28 (Planner)                      │
│   • GPT-5 call: $0.65 (Critic)                               │
│   ──────────────────────────                                  │
│   Total: $1.35                                               │
│                                                              │
│  Per-call limit: $1.00 ✓ (każdy individual OK)               │
│  Per-deliberation soft cap: $1.20 ✗ EXCEEDED                 │
│                                                              │
│  Co system zrobił:                                           │
│   ✓ Pierwsze 2 calls completed (Claude Opus, Sonnet)         │
│   ⚠ GPT-5 call canceled mid-flight (cancellation token)     │
│   ⚠ Critic round won't complete tym razem                    │
│                                                              │
│  Opcje:                                                      │
│  [● Restart Critic z cheaper model]                          │
│      Auto-fallback: GPT-5 → bielik-11b lokalny ($0)          │
│  [○ Skip Critic dla tej rundy]                               │
│      Council finalize bez Critic signature (degraded mode)   │
│  [○ Increase per-deliberation cap do $2.00]                  │
│      Just for this deliberation, return to defaults after    │
│  [○ Pause project, resume gdy operator increase budget]     │
│                                                              │
│  Long-term fix:                                              │
│   • Configure pre-flight estimate dla każdej rundy           │
│   • Reserve budget upfront przed start round                 │
│   • Use cheaper models dla Critic w D1-D3 projektach         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: fallback Critic, skip Critic, increase cap, pause.

**Recovery**: system implementuje **budget reservation** dla concurrent
calls — przed start round, system "reserves" estimate sum, blokuje calls
gdy reserved+actual > cap.

#### EC-C6: Vendor zmienia pricing mid-month

**Trigger**: Anthropic ogłasza pricing change dla claude-opus z $15/$75 do
$12/$60 per 1M tokens (10% taniej, mid-month). System wykrywa przy template
update.

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ  Pricing change detected                                  │
│                                                              │
│  Provider: Anthropic                                         │
│  Model: claude-opus-4-7                                      │
│                                                              │
│  Old pricing:                                                │
│   • Input:  $15.00 / 1M tokens                               │
│   • Output: $75.00 / 1M tokens                               │
│                                                              │
│  New pricing (effective 2026-04-29):                         │
│   • Input:  $12.00 / 1M tokens (-20%)                        │
│   • Output: $60.00 / 1M tokens (-20%)                        │
│                                                              │
│  Wpływ na twoje projekty:                                    │
│   • Sylion Tailor: estimated savings $12.40/month             │
│   • Lokalny CRM:   estimated savings $3.20/month              │
│   • Total monthly: -$18-25 saved                             │
│                                                              │
│  Akcje:                                                      │
│  [● Update template + recalculate budgets]                   │
│      System updates pricing w wszystkich references          │
│      Cost limits stay same (więcej można zrobić w budget)    │
│  [○ Update template ale recalculate cost projections]        │
│      Pokazuje "you can do 25% more dla same money"           │
│  [○ Ignore — keep using old pricing data]                    │
│      Stary cost calculation stays (operator preference)      │
│                                                              │
│  Edge case: jeśli pricing change to UP (drożej):             │
│   System pokazuje warning + impact analysis                  │
│   Operator może switch do tańszych alternatives              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: update + recalculate, update only, ignore.

**Recovery dla price increase**: system może auto-suggest alternatives:
"Anthropic Opus +20% droższy. Rozważ switch do GPT-5 (cheaper) dla mniej
critical roles?"

### Kategoria D — Multi-instance / federacja (5 cases)

#### EC-D1: Same model na różnych endpointach (lokalny + remote)

**Trigger**: operator ma `qwen2.5:7b` na lokalnym Ollama AND na VPS Ollama.

System pokazuje obu jako separate instances:

```
qwen2.5:7b (Ollama-local)        Latency: 42ms   Cost: $0
qwen2.5:7b (Ollama-vps-warsaw)   Latency: 180ms  Cost: $0 (own VPS)
```

Operator wybiera per priority chain który ma priority dla którego use case.

#### EC-D2: Federation conflict — model dostępny na 2 endpointach z różnymi versions

```
⚠ Version mismatch: bielik-11b

Endpoint 1 (lokalny): bielik-11b-v2.6
Endpoint 2 (VPS):     bielik-11b-v3.0

System może użyć obu, ale outputs będą różne.

Akcja:
[● Treat as different models (different IDs)]
[○ Auto-prefer newer version (v3.0)]
[○ Pin to v2.6 for consistency]
```

#### EC-D3: Endpoint przestaje być reachable (network issue)

**Trigger**: VPS przeszedł offline (operator-side network issue).

```
⚠ Endpoint unreachable: ollama-vps-warsaw

Last seen: 8 min ago
Connection: timeout

Possible:
 • VPS down
 • Network issue (your side)
 • Firewall change

Akcje:
[Try diagnostic]  [Disable temporary]  [Switch to local fallback]
```

#### EC-D4: Load balancing między równoległymi endpointami

**Trigger**: operator ma 3 instancje Ollama (lokalny + 2 VPS). System musi
decide które użyć dla każdego call. Domyślnie chooses najszybszy, ale to
może prowadzić do non-deterministic behavior.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚙  Multi-endpoint load balancing                            │
│                                                              │
│  qwen2.5:7b dostępny na 3 endpoints:                         │
│   • Ollama-local           (latency 42ms)                    │
│   • Ollama-vps-warsaw      (latency 180ms)                   │
│   • Ollama-vps-frankfurt   (latency 220ms)                   │
│                                                              │
│  Aktualny load balancing: [● Latency-based]                  │
│                                                              │
│  Trade-offs:                                                 │
│   ✓ Latency-based: zawsze najszybszy → lokalny dominuje      │
│      ✗ Single point of failure (lokalny down → wszystko down) │
│      ✗ Lokalny limit RAM/GPU concurrent                      │
│                                                              │
│   ✓ Round-robin: 33% każdy → load distributed                │
│      ✗ Wolniej średnio (180ms vs 42ms)                       │
│                                                              │
│   ✓ Weighted: lokalny 60%, VPS 20% each                      │
│      ✓ Balance speed vs distribution                         │
│      ✗ Requires manual tuning                                │
│                                                              │
│   ✓ Smart (zalecane): primary local, failover gdy busy       │
│      ✓ Najszybszy gdy lokalny dostępny                       │
│      ✓ Auto-failover gdy lokalny saturated                   │
│      ✓ Health-aware                                          │
│                                                              │
│  Concurrent capacity:                                        │
│   • Lokalny: max 1 inference at time (1 GPU)                 │
│   • VPS warsaw: max 2 (smaller GPU)                          │
│   • VPS frankfurt: max 4 (larger GPU)                        │
│   • Total combined: 7 concurrent                             │
│                                                              │
│  [Save load balancing strategy]  [Test current setup]        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: latency-based, round-robin, weighted, smart (default).

**Edge case wewnątrz**: jeśli wszystkie 3 endpoints saturated, system queue
dodaje request → operator widzi "Waiting for capacity (3 in queue)".

#### EC-D5: Sharding modelu na multi-host (rare, advanced)

**Trigger**: operator chce uruchomić Claude Opus equivalent (70B model)
ale pojedynczy host nie ma wystarczającego VRAM. Model musi być **sharded**
na 2-4 hosty.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚙  Multi-host model sharding                                │
│                                                              │
│  Wykryto setup capable of sharding:                          │
│   • Llama 70B model wymaga ~140 GB VRAM (FP16)              │
│   • Available hosts:                                         │
│     - Lokalny laptop:     24 GB VRAM                         │
│     - VPS warsaw:         48 GB VRAM                         │
│     - VPS frankfurt:      80 GB VRAM                         │
│   • Combined: 152 GB ✓ wystarczy                             │
│                                                              │
│  Frameworks supporting sharding:                             │
│   ✓ vLLM with tensor parallelism                            │
│   ✓ DeepSpeed-Inference                                      │
│   ✓ Accelerate (HuggingFace)                                 │
│                                                              │
│  Trade-offs:                                                 │
│   ✓ Larger models accessible                                 │
│   ✗ Cross-host network = significant latency overhead        │
│   ✗ Complex setup                                            │
│   ✗ Single-host failure breaks całość                        │
│   ✗ Requires fast network między hosts (10Gbps+)             │
│                                                              │
│  Recommendation:                                             │
│  [● Use API provider zamiast (znacznie prościej)]            │
│      Anthropic Claude / OpenAI GPT-5 są equivalent quality   │
│  [○ Configure sharding (advanced setup, ~30 min)]            │
│  [○ Use smaller model na single host]                        │
│      Llama 8B na lokalny zamiast 70B sharded                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: API provider (default for most), sharding setup
(advanced), smaller model.

**Recovery**: jeśli sharding selected i zawodzi → fallback do single-host
z mniejszym modelem albo do API.

### Kategoria E — Privacy / compliance (4 cases)

#### EC-E1: Sending sensitive data do providera bez DPA

**Trigger**: operator wybrał goal "GDPR-compliant" w fazie 1, ale dodaje
provider który nie ma DPA (Data Processing Agreement).

```
⚠ Privacy compliance warning

Provider: SomeProvider Inc.
DPA available: ✗ No
Data residency: US (no EU servers)

Twój operator profile: GDPR-compliant project goal active

Consequences if you use:
 ✗ Personal data nie powinno iść do tego providera
 ✗ Może wymagać explicit consent w projektach
 ✗ Data subject access requests (DSR) trudne do realizacji

Akcje:
[● Skip — choose GDPR-compliant alternative]
[○ Add anyway, but flag for non-PII tasks only]
[○ Add with PII redaction enabled]
```

#### EC-E2: Region wymaga sovereign provider

**Trigger**: operator pracuje na projekcie dla Polish gov agency. Wymaga
sovereign processing.

```
ℹ Sovereign processing recommended

Project: SYLION Government Communications
Compliance: KRI-PL, LP, TLP:RED

Recommended providers:
 ✓ Local models (Bielik, PLLuM) — full sovereign
 ✓ Mistral (EU hosted) — EU sovereignty
 ⚠ Anthropic — US-based (caution dla classified)
 ✗ OpenAI — US-based (not recommended)

Configure preference:
[Set sovereign-first chain]
```

#### EC-E3: Embedding model zbiera dane do training

**Trigger**: niektóre providers używają user inputs do training (chyba że
explicit opt-out).

```
⚠ Provider may use your data for training

OpenAI:
 • Default: data NIE używana dla training (od 2023)
 • Free tier: może być training data
 • Operator should verify in Anthropic console

Anthropic:
 • Default: data nie używana dla training (consumer)
 • API-tier: never used for training

Action:
 [Verify settings in vendor console]
 [Add disclaimer to project Księga]
```

#### EC-E4: Vendor logs prompts (zabezpieczenie compliance)

**Trigger**: operator's projekt zawiera TLP:RED material (security
classified). Niektórzy providers logują prompts dla "safety review" przed
30 dni. To może być compliance violation dla classified data.

```
┌──────────────────────────────────────────────────────────────┐
│  🔴  Compliance ALERT: Vendor prompt logging                 │
│                                                              │
│  Project: SYLION Government Communications                   │
│  Classification: TLP:RED (restricted distribution)           │
│                                                              │
│  Vendor logging policies:                                    │
│   ⚠ Anthropic:                                               │
│      • Prompts logged dla safety review (30 dni retention)   │
│      • Workspace plan dostępny (no logging) — $$$            │
│      • API tier 4+ dostępny (no logging by default)          │
│                                                              │
│   ✗ OpenAI:                                                  │
│      • Prompts logged 30 dni minimum                         │
│      • Enterprise plan może exclude logging — wymaga DPA     │
│                                                              │
│   ✓ Mistral (EU):                                            │
│      • EU GDPR-compliant, no prompt logging by default       │
│      • Best dla classified PL projects                       │
│                                                              │
│   ✓ Lokalny (Bielik, qwen):                                  │
│      • Zero logging — nigdy nie wychodzi z maszyny           │
│      • Best dla TLP:RED                                      │
│                                                              │
│  Recommended dla TLP:RED workload:                           │
│   PRIMARY: Lokalne modele (Bielik, qwen-coder) lub Mistral   │
│   AVOID: Anthropic/OpenAI default tier                       │
│                                                              │
│  Akcje:                                                      │
│  [● Auto-route TLP:RED do lokalnych/Mistral]                 │
│      System recognizes classification tags                   │
│      Inne classifications mogą używać Anthropic/OpenAI       │
│  [○ Upgrade do enterprise tier (no logging)]                 │
│      Anthropic Workspace plan ~$X/month                      │
│  [○ Block all classified projects od non-compliant]          │
│      Strictest: nawet niesklasyfikowane przez compliance     │
│                                                              │
│  Audit chain entry: `compliance_routing_configured`          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: auto-route based on classification (default),
enterprise upgrade, strict block.

**Recovery**: jeśli operator routing source classified data do non-compliant
provider → system blokuje request, audit entry `compliance_violation_blocked`,
notification do DPO/Security team.

### Kategoria F — Recovery / migration (4 cases)

#### EC-F1: Migration from one provider do drugiego

**Trigger**: operator chce switch z OpenAI na Anthropic dla wszystkich
projektów.

```
┌──────────────────────────────────────────────────────────────┐
│  Migration Wizard — OpenAI → Anthropic                       │
│                                                              │
│  Affected:                                                   │
│   • 3 active projects                                        │
│   • 12 archived projects                                     │
│   • 247 audit chain entries                                  │
│   • Council templates: 4 templates use OpenAI                │
│   • Priority chains: 6 chains have OpenAI as primary         │
│                                                              │
│  Migration strategy:                                         │
│  [● Soft migration (gradual)]                                │
│      New projects use Anthropic. Old projects keep OpenAI.   │
│      Operator can re-run old jeśli wants.                    │
│                                                              │
│  [○ Hard migration (replace everywhere)]                     │
│      All references switched. Old projects cant rerun        │
│      without re-adding OpenAI.                               │
│                                                              │
│  [○ Hybrid (keep OpenAI as fallback)]                        │
│      New: Anthropic primary, OpenAI fallback                 │
│      Old: unchanged                                          │
│                                                              │
│  [Run migration]  [Preview changes]  [Cancel]                │
└──────────────────────────────────────────────────────────────┘
```

#### EC-F2: Backup restore — provider catalog

**Trigger**: operator restore'uje workspace z backup. Providers z backup
mogą być stale (klucze rotated).

```
ℹ Backup restored

Provider catalog from backup (2026-04-15):
  ✓ Anthropic — testing klucz...  ✓ OK
  ✗ OpenAI — testing klucz...    ✗ Failed (klucz rotated since backup)
  ✓ Google — testing...           ✓ OK
  ⚠ Local Ollama — endpoint changed (was localhost:11434)

Auto-fix:
 ✓ Anthropic: keep
 ⚠ OpenAI: needs new klucz [Update now]
 ⚠ Local Ollama: re-detect endpoint [Re-scan]
```

#### EC-F3: Workspace export → import na innej maszynie

**Trigger**: operator exports workspace, restoreuje na innej maszynie.
Lokalne modele (z faza 2 detected) nie będą działać na nowej maszynie.

```
ℹ Workspace import

Lokalne modele NIE są transferable:
  ✗ bielik-11b-v2.6 (Ollama localhost) — niedostępne na new machine
  ✗ qwen2.5:7b (Ollama localhost) — niedostępne

Akcja:
 [Re-detect lokalne na new machine]
 [Auto-install same models via Ollama]
 [Skip — use API providers only]
```

#### EC-F4: Catalog corruption — partial recovery

**Trigger**: SQLite write podczas crash (power loss, kernel panic). Tabela
`provider_credentials` ma corrupted entries. Część kluczy nieczytelna.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Provider catalog corruption detected                     │
│                                                              │
│  Status: 5 providers, 2 corrupted                            │
│                                                              │
│  ✓ Anthropic         klucz readable, working                 │
│  ✓ OpenAI            klucz readable, working                 │
│  ✗ Google            klucz: corrupted (decrypt failed)       │
│  ✓ OpenRouter        klucz readable, working                 │
│  ✗ Mistral           klucz: corrupted (encryption mismatch)  │
│                                                              │
│  Recovery options:                                           │
│                                                              │
│  [● Restore from backup]                                     │
│      Backup z 2026-04-28 (1 dzień temu) ma valid:            │
│       ✓ Wszystkie 5 providers działa                         │
│       ✗ Tracisz: 24h zmian (cost ledger entries, etc.)       │
│                                                              │
│  [○ Re-enter corrupted keys ręcznie]                         │
│      Operator wpisuje na nowo Google + Mistral keys          │
│      Reszta state preserved                                  │
│      Czas: 5-10 min                                          │
│                                                              │
│  [○ Disable corrupted providers, continue]                   │
│      Google + Mistral oznaczone jako disabled                │
│      Operator może później naprawić                          │
│      Capability matrix updated (some gaps may appear)        │
│                                                              │
│  [○ Try repair with old master_password]                     │
│      Jeśli master password zmienione recently, corrupted     │
│      entries mogą być z stary key. Try decrypt z poprzednim. │
│                                                              │
│  ⚠ Po recovery: run integrity check                          │
│     System sprawdzi wszystkie providers, audit chains        │
│     Time: 1-3 min                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: restore from backup, re-enter manually, disable +
continue, try old password.

**Recovery dla "re-enter manually"**:
1. System pokazuje listę corrupted providers z hint (last 4 chars)
2. Per provider: operator wkleja klucz na nowo
3. Test inference dla każdego
4. Save → continue
5. Audit chain entry: `partial_recovery_manual_keys`

**Edge case wewnątrz**: jeśli all providers corrupted (catastrophic
corruption) → forced restore from backup (no other option). Jeśli no backup
→ start fresh (faza 2 od początku, all providers re-add).

---

## 2.12. Inheritance + Acceptance Criteria + DoD

### 2.12.1. Inheritance pattern (P2C.17=b — 2-3 przykłady)

**Przykład 1 — Provider preferences propagate do Council templates**:

```
Faza 2 sets:
  Polish text capability: 3 models
    Primary: Bielik-11b-v2.6 (lokalny, $0)
    Secondary: claude-sonnet-4-6 (api, $3/1M)
    Tertiary: gpt-5-mini (api, $1.50/1M)

   ↓
Faza 12 (Council Templates):
  When defining "Compliance" role for Polish projects:
    Default model: Bielik-11b-v2.6 (z faza 2 polish_text primary)
    Reasoning: lowest cost dla Polish text role
    
   ↓
Faza 17 (Per-project override):
  For project with strict Compliance review (D5 + GDPR):
    Override: claude-sonnet-4-6 (better quality > cost)
    Reason: D5 wymaga premium, willing to pay
   
   ↓
Faza 22 (Per-deliberation):
  Mid-Council, operator może wybrać per-round override
```

**Przykład 2 — Cost limits cascade**:

```
Faza 2: Global monthly cap: $500
   ↓
Faza 4 (Workspace Defaults): Default per-project budget: $50
   ↓
Faza 17 (Per-project): override za projekt:
  Sylion Tailor: $80 (większy projekt)
  Lokalny CRM: $20 (mniejszy)
   ↓
Faza 30 (Pre-flight cost preview):
  Pre-flight check: estimated $42 dla Sylion Tailor (under $80 limit)
  ✓ Approved budget
```

**Przykład 3 — Capability matrix → masterplan generation**:

```
Faza 2: Capability matrix shows:
  ✓ image_generation: OpenRouter (FLUX schnell)
  ✓ polish_text: Bielik
   ↓
Faza 28 (Masterplan synthesis):
  Project requires:
    - 50 product images → routed to OpenRouter/FLUX
    - PL product descriptions → routed to Bielik
  System auto-routes per capability availability
   ↓
Faza 32 (Model Selection round 3 per moduł):
  Per moduł "Product Catalog":
    image_gen: FLUX schnell (z faza 2 chain priority 1)
    pl_descriptions: Bielik (z faza 2 chain)
    en_descriptions: claude-sonnet (z faza 2 chain)
```

### 2.12.2. Acceptance Criteria — DoD (P2C.18=c adaptive per goals)

Faza 2 jest **kompletna gdy** spełnione adaptive criteria zależnie od
operator's goals z fazy 1.

#### Wspólne (zawsze wymagane)

```
✓ Min 1 provider z capability `text_generation` working (test inference pass)
✓ Lokalne modele wykryte (jeśli istnieją w systemie)
✓ Capability matrix wstępnie wypełniona
✓ Master password active (z fazy 1)
✓ Workspace state saved (audit chain entry "phase_2.complete")
```

#### Goal-specific dodatkowe

**Jeśli goal = "public_products"**:
```
✓ Min 1 API provider (lokalne nie wystarcza dla SLA wymagań)
✓ Cost limits zdefiniowane per provider
✓ Health monitoring włączone
✓ Fallback chains skonfigurowane (min 2 entries per critical capability)
```

**Jeśli goal = "cybersecurity"**:
```
✓ Sovereign provider preferred (Bielik, Mistral EU lub local)
✓ Encryption verified (master password active, no plaintext keys w logs)
✓ Audit chain dla provider operations enabled
✓ DPA-compliant providers flagged
```

**Jeśli goal = "research"**:
```
✓ Reasoning_deep capability available (o1, o3, claude-opus)
✓ Long_context capability available (>100K)
✓ Cost limits relaxed (research może wymagać experimentation)
```

**Jeśli goal = "apps_internal"**:
```
✓ Min 1 provider (basic) — lokalne wystarcza
✓ Cost limits low (internal tools nie wymagają premium)
```

**Jeśli goal = "mixed/explore"**:
```
✓ Diverse capabilities (min 6 z 12)
✓ Mix lokalnych + API
```

### 2.12.3. Soft warnings vs hard blocks

**Hard blocks** (operator nie może iść dalej):
- 0 providers z text_generation capability
- Master password not set ALE klucze API skonfigurowane (security risk)
- Capability matrix completely empty (system nie zna co masz)

**Soft warnings** (operator może continue z risk acknowledgement):
- Brak API provider gdy goal = public_products
- Brak lokalnych modeli gdy goal = cybersecurity
- Single point of failure dla critical capabilities
- Cost limits very loose (>$1000/month bez explicit approval)
- Provider z poor health history selected

### 2.12.4. Acceptance test (automated)

```bash
$ aeis-cli phase2-acceptance-test

Running Phase 2 acceptance test...

[Common requirements]
[1/5] At least 1 provider with text_generation     ✓ PASS (5 providers)
[2/5] Local models detection complete              ✓ PASS (3 detected)
[3/5] Capability matrix populated                  ✓ PASS (9/12 capabilities)
[4/5] Master password active                       ✓ PASS
[5/5] Workspace audit chain saved                  ✓ PASS

[Goal-specific: public_products]
[6/8] At least 1 API provider                      ✓ PASS (Anthropic)
[7/8] Cost limits configured                       ✓ PASS ($500/mo)
[8/8] Fallback chains configured                   ⚠ WARN (only 1 chain)

[Goal-specific: cybersecurity]
[9/11] Sovereign provider available                ✓ PASS (Bielik local)
[10/11] Encryption verified                        ✓ PASS
[11/11] Audit chain for providers                  ✓ PASS

DoD: 10/11 ✓ + 1 ⚠
Soft warnings: 1 (fallback chains thin)
Hard blocks: 0

Phase 2 ACCEPTED. Ready to proceed to Phase 3 (Environment Configuration).

Recommended pre-Phase-3 actions:
  • Add 2nd entry to image_generation fallback chain
  • Consider adding Mistral as EU-sovereign API alternative
```

---

## Status fazy 2

🟢 **Wszystkie sekcje 2.1-2.12 complete**

**Zawiera**:
- ✓ Sense + iteracyjny charakter (2.1)
- ✓ Architektura katalogu — 3 widoki z toggle (2.2)
- ✓ Auto-detection lokalnych modeli — 4 triggers + benchmark (2.3)
- ✓ Encryption sekretów — SQLite encrypted column (2.4)
- ✓ Predefined templates — 24 providerów + custom workflow (2.5)
- ✓ Capability Matrix expanded — 12 capabilities + scoring + gap detection (2.6)
- ✓ Local install suggestions — image-gen full categorization + TTS multi-language (2.7)
- ✓ Acquisition Advisor — quality-first recommendation + UI flow (2.8)
- ✓ Cost & Priority Profiles — chains, limits, exhaustion behavior (2.9)
- ✓ Health Monitoring + Quota Tracking — 5-level + dashboards (2.10)
- ✓ Edge cases — 30 cases w 6 hybrid kategoriach (2.11)
- ✓ Inheritance + DoD + acceptance criteria (2.12)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 2** + przejście do **Faza 3 — Environment Configuration**.
