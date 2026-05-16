# Gemini — Forecasting: Koszt per Pipeline Run dla SYLION v5.9.0

*Rola: Gemini 3.1 Pro | Perspektywa: Forecasting, token accounting, cost modeling*

---

## 1. Metodologia Token Estimation

### Komponenty tokenowe w każdym pipeline run

Każde wywołanie SYLION v5.9.0 składa się z następujących segmentów tokenowych:

```
TOKEN BREAKDOWN PER PIPELINE RUN:
┌─────────────────────────────────────────────────────────┐
│ SEGMENT                  │ MIN    │ TYP    │ MAX        │
├─────────────────────────────────────────────────────────┤
│ System prompt (per model)│  300   │  500   │  800       │
│ User task description    │  100   │  250   │  800       │
│ Context: conversation    │  500   │ 1,500  │ 5,000      │
│ Context: code snippets   │  200   │ 1,000  │ 4,000      │
│ Context: file structure  │  100   │  400   │ 1,500      │
│ TOTAL INPUT per model    │ 1,200  │ 3,650  │ 12,100     │
├─────────────────────────────────────────────────────────┤
│ Output per model         │  200   │  800   │  3,000     │
│ Aggregator input         │  800   │ 2,400  │  6,000     │
│ Aggregator output        │  200   │  600   │  1,500     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Cennik Modeli (market rates, Q2 2025)

| Model | Input $/1M tok | Output $/1M tok |
|-------|---------------|----------------|
| Claude Opus 4.7 | $15.00 | $75.00 |
| GPT-5 (est.) | $10.00 | $30.00 |
| Gemini 1.5 Pro | $3.50 | $10.50 |
| Perplexity Sonar Pro | $3.00 | $15.00 |
| Claude Sonnet 4.6 | $3.00 | $15.00 |
| GPT-4o-mini | $0.15 | $0.60 |
| Gemini Flash 2.0 | $0.075 | $0.30 |

---

## 3. Cost Model per Task Class — Obecny Stan (4 modele zawsze)

### MICRO Task (typowa sesja: rename, literówka, comment)

```
Input tokens per model: ~1,200 (system + task + minimal context)
Output tokens per model: ~300

Costs:
  Claude Opus:   1,200 × $15/1M + 300 × $75/1M = $0.018 + $0.023 = $0.041
  GPT-5:         1,200 × $10/1M + 300 × $30/1M = $0.012 + $0.009 = $0.021
  Gemini Pro:    1,200 × $3.5/1M + 300 × $10.5/1M = $0.0042 + $0.0032 = $0.0074
  Perplexity:    1,200 × $3/1M + 300 × $15/1M = $0.0036 + $0.0045 = $0.0081

Aggregator (via Opus): 1,200 in + 400 out = $0.018 + $0.030 = $0.048
(aggregator reads all 4 responses: ~1,200 tokens each + synthesis)

TOTAL MICRO RUN: ~$0.041 + $0.021 + $0.0074 + $0.0081 + $0.048 = $0.126
(konservative upper bound z aggregatorem przez Opus)

Uproszczony szacunek (bez heavy aggregator): ~$0.075–$0.085
```

### SMALL Task (typowa sesja: bug fix z stack trace)

```
Input tokens per model: ~3,500 (task + stack trace + relevant code)
Output tokens per model: ~800

Costs:
  Claude Opus:   3,500 × $15/1M + 800 × $75/1M = $0.053 + $0.060 = $0.113
  GPT-5:         3,500 × $10/1M + 800 × $30/1M = $0.035 + $0.024 = $0.059
  Gemini Pro:    3,500 × $3.5/1M + 800 × $10.5/1M = $0.012 + $0.0084 = $0.021
  Perplexity:    3,500 × $3/1M + 800 × $15/1M = $0.011 + $0.012 = $0.023

Aggregator (Opus): 4,000 in + 600 out = $0.060 + $0.045 = $0.105

TOTAL SMALL RUN: ~$0.113 + $0.059 + $0.021 + $0.023 + $0.105 = $0.321
Uproszczony szacunek: ~$0.18–$0.25
```

### MEDIUM Task (nowa feature, refactor)

```
Input tokens per model: ~8,000
Output tokens per model: ~2,500

Costs:
  Claude Opus:   $0.120 + $0.188 = $0.308
  GPT-5:         $0.080 + $0.075 = $0.155
  Gemini Pro:    $0.028 + $0.026 = $0.054
  Perplexity:    $0.024 + $0.038 = $0.062

Aggregator (Opus): 12,000 in + 1,500 out = $0.180 + $0.113 = $0.293

TOTAL MEDIUM RUN: ~$0.308 + $0.155 + $0.054 + $0.062 + $0.293 = $0.872
Uproszczony szacunek: ~$0.55–$0.90
```

### LARGE Task (subsystem, breaking change)

```
Input tokens per model: ~20,000
Output tokens per model: ~6,000

Costs:
  Claude Opus:   $0.300 + $0.450 = $0.750
  GPT-5:         $0.200 + $0.180 = $0.380
  Gemini Pro:    $0.070 + $0.063 = $0.133
  Perplexity:    $0.060 + $0.090 = $0.150

Aggregator (Opus): 28,000 in + 3,000 out = $0.420 + $0.225 = $0.645

TOTAL LARGE RUN: ~$0.750 + $0.380 + $0.133 + $0.150 + $0.645 = $2.058
Uproszczony szacunek: ~$1.20–$2.10
```

---

## 4. Typowa Sesja v5.9.0 — Composite Forecast

### Sesja: 20 tasków (typowy dzień lokalnego dev)

Zakładając rozkład: 7 MICRO + 6 SMALL + 5 MEDIUM + 2 LARGE

| Klasa | Liczba | Koszt/run (avg) | Subtotal |
|-------|--------|----------------|----------|
| MICRO | 7 | $0.080 | $0.560 |
| SMALL | 6 | $0.215 | $1.290 |
| MEDIUM | 5 | $0.700 | $3.500 |
| LARGE | 2 | $1.600 | $3.200 |
| **SUMA** | **20** | **$0.428 avg** | **$8.550** |

**Typowa sesja 20 tasków: ~$8–9/dzień**  
**Miesięcznie (20 dni roboczych): ~$170–$180/miesiąc**

---

## 5. Post-Optimization Forecast (z routingiem + right-sizing)

| Klasa | Liczba | Koszt/run (po optymalizacji) | Subtotal |
|-------|--------|------------------------------|----------|
| MICRO | 7 | $0.001 | $0.007 |
| SMALL | 6 | $0.007 | $0.042 |
| MEDIUM | 5 | $0.080 | $0.400 |
| LARGE | 2 | $0.600 | $1.200 |
| **SUMA** | **20** | **$0.082 avg** | **$1.649** |

**Po optymalizacji: ~$1.65/dzień**  
**Miesięcznie: ~$33–35/miesiąc**  
**Oszczędność: ~80.7% całkowitego kosztu**

---

## 6. M-06 i M-07 — Wpływ na Koszty v5.9.0

### M-07 (batch subprocess — cold start reduction)
- Cold start eliminuje: ~200–400 tokenów system prompt reload per subprocess
- Dla sesji 20 tasków × 4 modele = 80 subprocess calls
- Oszczędność: 80 × 300 × $15/1M (Opus share) ≈ $0.36/sesję
- **Szacowana redukcja: 3–4% całkowitego kosztu sesji**

### M-06 (GROUP BY — dashboard query reduction)
- Pre-M-06: N dashboard widgets × N queries = N² LLM format calls
- Post-M-06: 1 aggregated query → 1 LLM format call
- Dla dashboardu z 10 widgetami: 10× redukcja dashboard-LLM calls
- Szacowana wartość dla typowej sesji: **5–8% redukcji** (dashboard queries są mniejsze)

**M-06 + M-07 razem: ~8–12% redukcji na szczycie obecnych kosztów.**  
*(Dobre, ale routing/right-sizing da 80% — tam jest główna dźwignia)*

---

## 7. Summary: Kluczowe Liczby

```
┌──────────────────────────────────────────────────────────────┐
│ SYLION v5.9.0 — COST FORECAST SUMMARY                        │
├──────────────────────────────────────────────────────────────┤
│ Typowy fix SMALL = ~3,500 tok input + ~800 tok output        │
│                  = 4,300 tokenów per model × 4 modele        │
│                  = ~17,200 tokenów TOTAL                     │
│                  = ~$0.18–$0.25 (current)                    │
│                  = ~$0.007 (po optymalizacji)                │
├──────────────────────────────────────────────────────────────┤
│ Typowa sesja (20 tasków): $8.55/dzień → $1.65/dzień         │
│ Oszczędność z pełnej optymalizacji: ~80%                     │
├──────────────────────────────────────────────────────────────┤
│ M-06 + M-07 contribution: 8–12% (incremental na dzisiaj)    │
│ Routing + Right-sizing: 75–80% (główna dźwignia)            │
└──────────────────────────────────────────────────────────────┘
```

*Szacowana oszczędność z forecasting perspective: 78–82% całkowitego LLM spend przy wdrożeniu routingu.*
