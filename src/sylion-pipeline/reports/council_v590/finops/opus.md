# Opus — Architektura Kosztów: Mapa Wywołań LLM w SYLION v5.9.0

*Rola: Claude Opus 4.7 | Perspektywa: Architekt kosztów*

---

## 1. Topologia Pipeline SYLION v5.9.0

SYLION v5.9.0 uruchamia 4 modele LLM równolegle na każde żądanie. Poniżej mapa wywołań z identyfikacją punktów kosztowych:

```
[USER REQUEST]
      │
      ▼
[ROUTER / DISPATCHER]  ← overhead: klasyfikacja zadania ~500 tokenów
      │
   ┌──┴──────────────────────────────────┐
   │                                     │
   ▼                                     ▼
[PREPROCESSING]                    [CONTEXT FETCH]
 • prompt normalization            • historia konwersacji
 • task-class detection            • relevant snippets
 ~200 tokens                       ~1000–3000 tokens
   │                                     │
   └──────────────┬──────────────────────┘
                  ▼
     [4× PARALLEL LLM INFERENCE]
     ┌──────────────────────────────────────────────────┐
     │ Claude Opus       │ GPT-4o/GPT-5   │             │
     │ CRITICAL path     │ code/logic     │  Gemini Pro │
     │ ~2000-8000 tok    │ ~2000-5000 tok │ ~1500-4000  │
     │                   │                │   tok       │
     │              Perplexity            │             │
     │              search/grounding      │             │
     │              ~800-2000 tok         │             │
     └──────────────────────────────────────────────────┘
                  │
                  ▼
     [AGGREGATOR / MERGER]  ← overhead: scalanie odpowiedzi ~1000–2000 tokenów
                  │
                  ▼
     [POST-PROCESSOR]       ← formatting, validation ~300–500 tokenów
                  │
                  ▼
     [RESPONSE → USER]
```

---

## 2. Identyfikacja Drogich Wywołań

### A. Hotspot #1 — Parallel Fanout (krytyczny)

Każde żądanie wyzwala **4 równoległe wywołania**, niezależnie od złożoności. Dla prostego zadania MICRO (np. literówka w komentarzu):

| Model | Est. tokeny (in+out) | Cena/1M tok (in) | Cena/1M tok (out) | Est. koszt |
|-------|---------------------|-----------------|-----------------|------------|
| Claude Opus | 3 000 | $15 | $75 | ~$0.045 |
| GPT-5 | 2 500 | $10 | $30 | ~$0.025 |
| Gemini Pro | 2 000 | $3.5 | $10.5 | ~$0.007 |
| Perplexity | 1 500 | $1 | $1 | ~$0.002 |
| **TOTAL** | **9 000** | | | **~$0.079** |

Dla zadania LARGE: ~$0.40–$1.20 per run.

### B. Hotspot #2 — Aggregator / Merger

Po równoległym inference, agregator musi przeczytać **wszystkie 4 odpowiedzi** + wygenerować syntezę. To dodatkowe ~1 000–2 000 tokenów *na każdym* drogim modelu (jeśli agregacja też idzie przez Opus).

**Szacowany narzut agregacji:** 15–25% całkowitego kosztu per run.

### C. Hotspot #3 — Context Fetch przy każdym wywołaniu

Każdy z 4 modeli otrzymuje pełny context (historia + snippety) — **4× duplikacja** tych samych tokenów wejściowych.

Dla kontekstu 2 000 tokenów wysłanego do 4 modeli = 8 000 tokenów input zamiast 2 000.

**Współczynnik duplikacji kontekstu: 4×.**

### D. Hotspot #4 — Dashboard queries (M-06 target)

Przed M-06: N zapytań per widget → N × LLM call dla formatowania wyników.  
Po M-06 (GROUP BY): 1 zapytanie zbiorcze → 1× LLM call.

**M-06 eliminuje hotspot dashboardowy** — szacowana redukcja: 60–80% wywołań dashboard.

### E. Hotspot #5 — Cold Start (M-07 target)

Przed M-07: każdy subprocess inicjalizuje model od zera (load weights, warmup).  
Po M-07 (batch subprocess): modele utrzymują ciepły kontekst.

**M-07 redukuje latency** i eliminuje koszt reinicjalizacji (~200–500 tokenów "system prompt reload" per call).

---

## 3. Ranking Kosztów wg Ważności

| Ranking | Hotspot | Koszt względny | Możliwość optymalizacji |
|---------|---------|----------------|------------------------|
| 1 | Parallel fanout — 4 modele zawsze | 55–65% całości | WYSOKA — routing |
| 2 | Context duplikacja 4× | 15–20% | WYSOKA — shared context |
| 3 | Aggregator przez Opus | 10–15% | ŚREDNIA — tańszy aggregator |
| 4 | Dashboard queries (pre-M-06) | 5–10% | ZREALIZOWANA przez M-06 |
| 5 | Cold start (pre-M-07) | 3–5% | ZREALIZOWANA przez M-07 |

---

## 4. Rekomendacje Architektoniczne

### R1: Shared Context Bus
Zamiast wysyłać pełny kontekst do każdego modelu osobno — jeden centralny fetch, pointer do cache. Potencjalna oszczędność: **15–20% całkowitego kosztu**.

### R2: Hierarchical Fanout
Nie uruchamiać 4 modeli dla wszystkich klas zadań. Implementacja tier-based dispatch:
- MICRO/SMALL → 1 model (Gemini Flash lub GPT-mini)
- MEDIUM → 2 modele (Sonnet + GPT-5.4)
- LARGE/CRITICAL → 4 modele (full council)

### R3: Tani Aggregator
Agregacja 4 odpowiedzi nie wymaga Opus — Sonnet lub Gemini Flash wystarczy. Oszczędność na agregacji: **8–12%**.

### R4: Lazy Context Loading
Context fetch tylko dla modeli, które go faktycznie potrzebują (Opus dla reasoning, Perplexity dla search). Redukcja input tokenów: **20–30%**.

---

## 5. Wnioski

Dominującym kosztem jest **bezwarunkowy parallel fanout** do 4 modeli. M-06 i M-07 adresują drugoplanowe hotspoty (dashboard, cold start) — dobrze zaprojektowane. Główna okazja oszczędności leży w **warunkowym routingu** opartym na klasie zadania, co może zredukować koszt o **40–60%** dla typowego rozkładu sesji (gdzie MICRO/SMALL stanowią 60–70% wywołań).

*Szacowana potencjalna oszczędność z optymalizacji architektury: 45–60% całkowitego LLM spend.*
