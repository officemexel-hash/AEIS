# ADR-001: Zachowanie defense-in-depth guardu w `_seed_agents`

**Status:** Accepted
**Data:** 2026-04-18
**Autor:** kod-szachista-council (rada 4 modeli × 4 scenariusze = 16 subagentów)

## Kontekst

W v5.8.7 wykryto potencjalny bug: `_seed_agents` mógł crashować gdy `agents.yaml` zawierał malformed entry (np. `None`, dict bez `id`, int zamiast dict). Opcje rozważane:

- **W1** — `isinstance(a, dict) and "id" in a and a["id"]` guard + `locals().get("agent_id", "<unknown>")` w except (defense-in-depth, current)
- **W2** — migracja na Pydantic BaseModel z ValidationError
- **W3** — early return przy pustym YAML (`if not agents_from_yaml: return`)
- **W4** — fail-fast (podnieś wyjątek i zatrzymaj startup)

## Ocena szachisty (16 subagentów)

| Wariant | S1 Attacker | S2 Regression | S3 Consistency | S4 Future |
|---|---|---|---|---|
| W1 | RISK 78% (10 edge cases) | RISK (scope leak w pętli for) | **SAFE** (C-001..C-006 PASS) | SAFE z kotwicą |
| W2 | SAFE | RISK (dict→object refactor w 3 plikach) | PASS conditional | POMAGA w v5.8.9 |
| W3 | SAFE | SAFE | SAFE (najlepszy per CL) | Cichy wipe risk |
| W4 | FAIL C-003 | FAIL | **FAIL konflikt skip vs raise** | FAIL |

## Decyzja

**Utrzymać W1 w v5.8.8.1.**

### Uzasadnienie

1. **Constraint List preserved**: W1 jako jedyny przechodzi wszystkie MUST-constraints (C-001..C-006) bez warunków.
2. **Partial-seed fault tolerance** (C-003): 47/48 agentów seeded OK gdy 1 malformed — wariant W4 (fail-fast) łamał tę zasadę.
3. **Brak breaking API change**: zachowany shape return `upserted: int`, zachowane signature `_seed_agents(conn, agents=None) -> int`.
4. **Testy regresji 15/15 passed** po zmianie: `test_bug1..9`, `test_concurrency_*`.

### Warunki retention (anchor do v5.8.9)

- Komentarz `# stop-gap — REMOVE when Pydantic validation lands` (grepowalny TODO)
- Test-kanarek `test_seed_agents_skips_malformed_entries` wymusza synchroniczną migrację fixa+walidacji
- Wpis w CHANGELOG jako formalny ślad intencji

## Roadmap na v5.8.9

- **W2 (Pydantic)** zaplanowany gdy `pydantic` zostanie dodany do `requirements.txt` (obecnie jest w `start.py` ale nie w deps file)
- Nowy test `test_seed_agents_pydantic_rejects_missing_id`
- Zachować defense-in-depth `try/except` wokół `cur.execute` (Pydantic waliduje shape, nie `IntegrityError`)

## Konsekwencje

**Pozytywne:**
- Zero regresji vs v5.8.7
- Wszystkie constraints preserved
- Szybka ścieżka do v5.8.8.1 bez dodawania deps

**Negatywne:**
- Tech debt: guard zostaje jako "paranoidalny" zamiast Pydantic-validator
- Scope leak w zmiennej pętli `agent_id` — mitigowane przez `locals().get(..., default)`
- W2 czeka w kolejce na v5.8.9

## Referencje

- `council/v588_1/szachista/W1-S1-attacker-sonnet.md`
- `council/v588_1/szachista/W1-S2-regression-gemini.md`
- `council/v588_1/szachista/W1-S3-consistency-opus.md`
- `council/v588_1/szachista/W1-S4-future-opus.md`
