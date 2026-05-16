# GPT-5.4 — LLM Routing: Cheaper Models dla Trivial Tasks

*Rola: GPT 5.4 | Perspektywa: Routing logika i model selection*

---

## 1. Routing Framework — Zasady Podstawowe

Efektywny routing LLM opiera się na trzech osiach decyzyjnych:

```
                    TASK COMPLEXITY
                    LOW          HIGH
                ┌────────────┬────────────┐
    STAKES  LOW │  Tier 1    │  Tier 2    │
                │ (Flash/mini│ (Sonnet/   │
                │            │  GPT-mini) │
                ├────────────┼────────────┤
           HIGH │  Tier 3    │  Tier 4    │
                │ (Sonnet +  │ (Full      │
                │  verify)   │  Council)  │
                └────────────┴────────────┘
```

---

## 2. Model Catalog dla Routingu (aktualne ceny LLM market)

### Modele dostępne w SYLION ecosystem

| Model | Input $/1M | Output $/1M | Jakość (1-5) | Latency | Best for |
|-------|-----------|------------|--------------|---------|----------|
| **Gemini Flash 2.0** | $0.075 | $0.30 | ★★★ | ~200ms | MICRO, klasyfikacja, summarize |
| **GPT-4o-mini** | $0.15 | $0.60 | ★★★ | ~300ms | SMALL code fixes, validations |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | ★★★★ | ~600ms | MEDIUM reasoning, drafts |
| **Gemini 1.5 Pro** | $3.50 | $10.50 | ★★★ | ~500ms | Large context, broad research |
| **GPT-5.4** | $10.00 | $30.00 | ★★★★★ | ~800ms | Logic, math, structured reasoning |
| **Claude Opus 4.7** | $15.00 | $75.00 | ★★★★★ | ~1200ms | CRITICAL, architecture, complex |
| **Perplexity Sonar** | $1.00 | $1.00 | ★★★ | ~400ms | Web search, grounding only |

---

## 3. Routing Rules per Task Class

### MICRO Tasks — "Trivial Edits"
**Trigger signals:** single token change, rename, typo fix, comment update, formatting

```yaml
routing:
  primary: gemini-flash-2.0
  fallback: gpt-4o-mini
  council: DISABLED
  max_tokens_in: 2000
  max_tokens_out: 500
  estimated_cost: $0.0003–$0.001
```

**Przykłady:** rename variable, fix import path, update docstring, reformat indentation

### SMALL Tasks — "Contained Fixes"
**Trigger signals:** single bug report + stack trace, <30 lines diff, clear scope

```yaml
routing:
  primary: gpt-4o-mini
  secondary: gemini-flash-2.0 (verify only)
  council: DISABLED
  max_tokens_in: 4000
  max_tokens_out: 1500
  estimated_cost: $0.003–$0.008
```

**Przykłady:** fix null pointer, add input validation, correct regex, fix off-by-one

### MEDIUM Tasks — "Feature Additions"
**Trigger signals:** 30–200 LOC, 2+ files, new functionality, requires design decisions

```yaml
routing:
  primary: claude-sonnet-4.6
  secondary: gpt-5.4 (logic verification)
  tertiary: gemini-flash-2.0 (syntax check)
  council: PARTIAL (3 models)
  max_tokens_in: 12000
  max_tokens_out: 4000
  estimated_cost: $0.05–$0.15
```

**Przykłady:** nowa klasa z testami, integracja API, refactor modułu

### LARGE Tasks — "Major Changes"
**Trigger signals:** 200+ LOC, architektura, cross-module impact, ambiguity

```yaml
routing:
  primary: claude-opus-4.7
  secondary: gpt-5.4
  tertiary: gemini-pro
  quaternary: perplexity (research only)
  council: FULL (4 models)
  max_tokens_in: 30000
  max_tokens_out: 10000
  estimated_cost: $0.30–$0.80
```

### CRITICAL Tasks — "Security/Data/Breaking"
**Trigger signals:** security keywords, data migration, breaking API change, production

```yaml
routing:
  primary: claude-opus-4.7
  secondary: gpt-5.4
  tertiary: gemini-pro
  quaternary: perplexity
  council: FULL + human_review_flag
  escalation: true
  estimated_cost: $0.50–$1.50
```

---

## 4. Routing Decision Tree (implementacja)

```python
def route_task(task):
    # Step 1: Fast classifier (Gemini Flash, <$0.0001)
    task_class = classify(task)  # MICRO/SMALL/MEDIUM/LARGE/CRITICAL
    confidence = classify_confidence(task)
    
    # Step 2: Confidence escalation
    if confidence < 0.85:
        task_class = escalate_one_tier(task_class)
    
    # Step 3: Keyword overrides (always CRITICAL)
    if any(kw in task for kw in CRITICAL_KEYWORDS):
        task_class = "CRITICAL"
    
    # Step 4: Route to model set
    return ROUTING_TABLE[task_class]

CRITICAL_KEYWORDS = [
    "security", "auth", "password", "token", "migration",
    "production", "breaking", "delete", "drop table"
]
```

---

## 5. Specjalne Przypadki Routingu

### 5a. Perplexity — tylko dla web-grounded tasks
Perplexity Sonar powinien być wywoływany **tylko** gdy:
- Task wymaga aktualnych informacji (library versions, CVE, changelog)
- Nie ma pewności co do aktualnego API spec
- **NIE** dla code generation, refactoring, logic tasks

Obecnie (bez routingu): Perplexity na każde wywołanie. Zbędne dla >70% tasków.

### 5b. Opus — tylko dla architectural decisions
Claude Opus justified gdy:
- Cross-system architectural analysis
- Novel algorithms requiring deep reasoning
- CRITICAL security review

Obecny % wywołań gdzie Opus jest faktycznie potrzebny: ~15–20% (szacunek).

### 5c. Model Cache / Response Reuse
Dla identycznych lub bardzo podobnych MICRO tasków (np. multiple renames w tej samej sesji) — response cache po stronie SYLION eliminuje powtórne wywołania.

**Potencjalna redukcja:** 10–20% wywołań dla długich sesji edycyjnych.

---

## 6. Implementacja: Router jako Osobny Moduł

```
[INCOMING TASK]
      │
      ▼
[FAST CLASSIFIER - Gemini Flash]  ~$0.0001, ~150ms
      │
      ├─ MICRO  → [Single: Gemini Flash]
      ├─ SMALL  → [Single: GPT-4o-mini]  
      ├─ MEDIUM → [Dual: Sonnet + GPT-5.4]
      ├─ LARGE  → [Triple: Opus + GPT-5.4 + Gemini Pro]
      └─ CRITICAL → [Full Council + flag]
```

Koszt klasyfikatora: ~$0.0001 per task — amortyzuje się w **pierwszym** wywołaniu.

---

## 7. Szacowane Oszczędności z Routingu

| Scenariusz | Bez routingu | Z routingiem | Oszczędność |
|------------|-------------|--------------|-------------|
| MICRO task | $0.079 | $0.0005 | **99.4%** |
| SMALL task | $0.079 | $0.006 | **92.4%** |
| MEDIUM task | $0.200 | $0.080 | **60.0%** |
| LARGE task | $0.600 | $0.400 | **33.3%** |
| Typowa sesja mixed | $0.180 avg | $0.038 avg | **78.9%** |

---

## 8. Wnioski

LLM routing to **najwyższy ROI investment** w SYLION v5.9.x. Implementacja prostego klasyfikatora (Gemini Flash + rule-based override dla CRITICAL) przy koszcie ~$0.0001/task pozwala zaoszczędzić 79–99% kosztów LLM na zadaniach MICRO/SMALL. Kluczowa zasada: **drogi model = rzadkie wywołanie, częste = tanie modele**.

Gemini Flash i GPT-4o-mini są wystarczające dla większości codziennych dev tasków — różnica jakości dla MICRO/SMALL jest statystycznie nieistotna dla prawidłowo opisanych zadań.

*Szacowana oszczędność z intelligent routingu: 70–80% całkowitego LLM spend.*
