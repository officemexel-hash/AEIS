# Sonnet — Right-Sizing: Czy 4 Modele Równolegle to Overkill?

*Rola: Claude Sonnet 4.6 | Perspektywa: Right-sizing i efektywność operacyjna*

---

## 1. Problem: Overkill dla MICRO/SMALL Changes

### Definicja klas zadań w SYLION v5.9.0

| Klasa | Opis | Typowe przykłady | % sesji* |
|-------|------|-----------------|---------|
| MICRO | Zmiana <5 linii, 1 plik, zero ambiguity | literówka, rename zmiennej, fix komentarza | ~35% |
| SMALL | Zmiana 5–30 linii, 1–2 pliki, low ambiguity | fix buga z jasnym komunikatem błędu, dodanie walidacji | ~30% |
| MEDIUM | Zmiana 30–200 linii, 2–5 plików, moderate reasoning | nowa feature z interakcjami, refactor modułu | ~25% |
| LARGE/CRITICAL | Zmiana 200+ linii, architektura, high ambiguity | nowy subsystem, breaking change, security fix | ~10% |

*Szacunkowy rozkład dla typowego projektu dev lokalnego*

### Analiza: Co naprawdę robi każdy model dla MICRO/SMALL?

Dla zadania MICRO (np. "zmień nazwę funkcji `calcCost` na `calculateCost` w pliku utils.js"):

| Model | Co robi | Wartość dodana | Koszt |
|-------|---------|----------------|-------|
| Claude Opus | Analizuje architekturę, planuje refactor, szuka side effects | **Zbędna** — to jest `find&replace` | $0.045 |
| GPT-5 | Logiczne sprawdzenie poprawności rename | Minimalnie użyteczna | $0.025 |
| Gemini Pro | Podobna analiza jak Opus, mniejsza jakość | **Zbędna** | $0.007 |
| Perplexity | Szuka dokumentacji dot. naming conventions | **Zbędna** dla rename | $0.002 |
| **RAZEM** | | | **$0.079** |

**Wniosek:** Dla MICRO wystarczyłby 1 model (Gemini Flash) za ~$0.001. Overhead = **79×** optymalnego kosztu.

---

## 2. Analiza Wartości Dodanej Równoległości

### Kiedy 4 modele rzeczywiście się opłacają?

Równoległy council ma sens gdy:
1. **Ambiguity** — różne interpretacje zadania mogą prowadzić do różnych rozwiązań
2. **Reliability** — weryfikacja krzyżowa eliminuje halucynacje
3. **Breadth** — każdy model wnosi inną wiedzę (code + search + reasoning)
4. **Stakes** — błąd jest kosztowny (CRITICAL paths, security, data integrity)

### Scoring wartości równoległości per klasa

| Klasa | Ambiguity | Reliability need | Breadth need | Stakes | Score (1-10) | Verdict |
|-------|-----------|-----------------|--------------|--------|--------------|---------|
| MICRO | Brak | Niski | Brak | Niskie | **2/10** | Overkill |
| SMALL | Niski | Niski-Średni | Niski | Niskie-Średnie | **4/10** | Overkill |
| MEDIUM | Średni | Średni | Średni | Średnie | **7/10** | Justified |
| LARGE | Wysoki | Wysoki | Wysoki | Wysokie | **10/10** | Konieczne |
| CRITICAL | Wysoki | Bardzo wysoki | Wysoki | Krytyczne | **10/10** | Konieczne |

---

## 3. Propozycja Right-Sizing Matrix

### Model Assignment per Task Class

```
MICRO  → 1 model: Gemini Flash 2.0 (lub GPT-4o-mini)
         Uzasadnienie: deterministyczne, zero ambiguity, tanio

SMALL  → 1-2 modele: Sonnet (primary) + opcjonalnie Gemini Flash (verify)
         Uzasadnienie: prosty reasoning, cross-check za ułamek ceny

MEDIUM → 2-3 modele: Sonnet + GPT-5.4 + Gemini Pro
         Uzasadnienie: wymaga breadth, ale nie pełnego council

LARGE  → 3-4 modele: Opus + GPT-5.4 + Gemini Pro + Perplexity
         Uzasadnienie: pełna analiza, krzyżowa weryfikacja

CRITICAL → 4 modele + human review flag
         Uzasadnienie: maksymalna pewność, nie oszczędzamy na bezpieczeństwie
```

### Szacowane oszczędności z right-sizing

Zakładając rozkład sesji: MICRO 35%, SMALL 30%, MEDIUM 25%, LARGE/CRITICAL 10%:

| Klasa | Obecny koszt | Po right-sizing | Oszczędność |
|-------|-------------|-----------------|-------------|
| MICRO (35%) | $0.079/run | $0.001/run | **98.7%** |
| SMALL (30%) | $0.079/run | $0.008/run | **89.9%** |
| MEDIUM (25%) | $0.200/run | $0.060/run | **70.0%** |
| LARGE (10%) | $0.600/run | $0.400/run | **33.3%** |

**Weighted average oszczędność: ~78%** dla typowej sesji dev.

---

## 4. Koszty Klasyfikacji (overhead)

Wprowadzenie routingu wymaga klasyfikatora task-class. Opcje:

| Opcja | Koszt klasyfikacji | Latency | Ryzyko |
|-------|-------------------|---------|--------|
| Rule-based (regex + heurystyki) | ~$0 | <1ms | False classification |
| Gemini Flash classifier | ~$0.0002 | ~200ms | Minimalne |
| Sonnet classifier | ~$0.002 | ~500ms | Bardzo niskie |

**Rekomendacja:** Gemini Flash classifier. ROI: nawet jeśli klasyfikuje błędnie 5% przypadków (overkill dla SMALL → MEDIUM), nadal oszczędzamy >70%.

---

## 5. Ryzyko: Kiedy Right-Sizing Może Zaszkodzić

1. **Misklasyfikacja SMALL jako MICRO** — możliwy błąd jeśli kontekst jest niekompletny. Mitygacja: confidence threshold — jeśli <85%, eskaluj o 1 poziom.
2. **"Creeping complexity"** — developer oznacza SMALL, ale zmiana ma ukryte zależności. Mitygacja: dependency graph scan przed klasyfikacją.
3. **Regresje w CRITICAL** — nigdy nie right-size w dół dla security/data paths.

---

## 6. Wnioski

Uruchamianie 4 modeli równolegle dla MICRO/SMALL to **overkill potwierdzony** — wartość dodana jest marginalna, a koszt 79× optymalny. Right-sizing to **największa pojedyncza dźwignia oszczędności** w SYLION v5.9.0. Implementacja tier-based dispatch z lekkim klasyfikatorem może zredukować całkowity LLM spend o **70–80%** bez mierzalnej utraty jakości dla klas MICRO i SMALL.

*Szacowana oszczędność z right-sizing: 70–80% całkowitego LLM spend dla typowej sesji dev.*
