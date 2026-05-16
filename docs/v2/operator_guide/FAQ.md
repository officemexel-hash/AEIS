# FAQ - SYLION v2

> Polish-language operator FAQ. Curated from `docs/v2/_drafts/ollama_batch/06_sylion_faq.md`
> by the v2 cron and aligned with ADR-001 / ADR-002.

## 1. W czym SYLION v2 różni się od wersji v1?

SYLION v2 wprowadza modularny system mikro-serwisów (manifest-driven ontology, federation, cost ledger, terminal) oraz Multi-Model Routing (ADR-002), co znacznie przyspiesza wdrażanie i redukuje koszty.
Wersja v1 korzystała z bardziej monolitycznego podejścia, które wymagało ręcznej konfiguracji zasobów i była mniej elastyczna przy dynamicznych zmianach obciążenia.

## 2. Dlaczego SYLION v2 wykorzystuje YAML do manifestów?

YAML zapewnia czytelny, zwięzły i łatwy do wersjonowania format, który jest natywnie wspierany przez większość narzędzi DevOps i jest podstawą formatu manifestu (decyzja A z ADR-001).
Dzięki temu konfiguracja typów obiektów, ról RBAC i zasobów staje się przyjazna dla operatora, a automatyzacja CI/CD jest prostsza.

## 3. Jakie LLM-y obsługuje SYLION v2?

Routing wielomodelowy (ADR-002) integruje modele lokalne (Ollama: `gpt-oss:20b`, `qwen3:8b`, `llama3.1:8b`, `gemma3:4b`, `phi3:3.8b`) oraz modele zdalne (Codex / Anthropic / Kimi) zgodnie z macierzą decyzji w ADR-002.
Operator może rozszerzyć tę macierz w `docs/v2/decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md`, dodając własne modele i progi kosztowe.

## 4. Czy SYLION v2 działa offline?

Tak - SYLION v2 może być uruchamiany w środowiskach offline z wykorzystaniem lokalnych modeli Ollama oraz lokalnego rejestru typów obiektów (PostgreSQL z rozszerzeniem JSONB).
Wymaga to wcześniejszego pobrania modeli (`ollama pull <model>`), skonfigurowania PG i zarejestrowania typów obiektów przez API `apply`.

## 5. Jak wygenerować aplikację w SYLION v2?

Proces polega na przygotowaniu manifestu YAML (typ obiektu lub szablon aplikacji), zatwierdzeniu go przez Human Gate (gdy `d_level >= D3`) i wywołaniu `POST /api/v1/ontology/types/{id}/apply` lub odpowiednika dla aplikacji.
Platforma waliduje manifest, generuje DDL (dla typów) lub szablon (dla aplikacji), a w przypadku decyzji D3+ wymaga Evidence Pack (rationale, rollback_plan, fidelity_test) zgodnie z mechanizmem decision-gate.

## Powiązane dokumenty

- **ADR-001** - `docs/v2/decisions/ADR-001-five-architectural-decisions-2026-04-27.md`
- **ADR-002** - `docs/v2/decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md`
- **W19 (parking)** - decyzja o czasowym wstrzymaniu W19 znajduje się w ADR-001.
- **Demo data** - `src/sylion-pipeline/sylion/aeis_v2/ontology/manifests/_demos/`
- **Glossary** - `glossary.md`
- **Tooltips PL** - `tooltips.md`
- **Sidebar overview** - `sidebar_overview.md`
