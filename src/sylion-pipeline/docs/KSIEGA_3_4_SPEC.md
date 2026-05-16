# Księga SYLION 3.4 FIXED — Specyfikacja produktu

**Status:** Placeholder dla BookGuardian baseline (v5.9.1)  
**SHA-256:** `<zostanie obliczone przy pierwszym starcie>`  
**Wersja pipeline:** v5.9.1  
**Data:** 2026-04-19

---

(Treść Księgi 3.4 FIXED — aktualna specyfikacja produktu SYLION — jest zarządzana przez właściciela produktu. Ten plik jest monitorowany przez BookGuardian na każdym etapie pipeline'u. Zmiana SHA-256 = halt pipeline.)

---

## Integracja

- Watchdog: `book_guardian.py`
- Gate level: **CRITICAL**
- Auto-halt: **TRUE**
- Re-baseline: manual via `python dashboard/book_guardian_rebase.py`

---

## Informacje techniczne

### Ścieżka pliku
```
docs/KSIEGA_3_4_SPEC.md
```

### Mechanizm monitorowania
BookGuardian (`book_guardian.py`) oblicza SHA-256 tego pliku przy każdym uruchomieniu pipeline'u i porównuje z zarejestrowaną wartością baseline. Zmiana skrótu bez ręcznego re-baseline'u (`book_guardian_rebase.py`) powoduje natychmiastowe zatrzymanie pipeline'u na poziomie CRITICAL.

### Re-baseline (procedura)
```bash
# Tylko gdy zmiana specyfikacji jest świadoma i autoryzowana przez właściciela produktu:
python dashboard/book_guardian_rebase.py \
    --file docs/KSIEGA_3_4_SPEC.md \
    --reason "Opis zmiany" \
    --approved-by "Imię Nazwisko"
```

### Konfiguracja config.py
```python
BOOK_GUARDIAN_TARGETS = [
    {
        "path": "docs/KSIEGA_3_4_SPEC.md",
        "label": "Ksiega_3_4_FIXED",
        "gate": "CRITICAL",
        "sha256_baseline": None,  # ustawi book_guardian_rebase.py przy pierwszym starcie
    }
]
```

---

## Historia

| Wersja | Data | Zmiana | SHA-256 |
|--------|------|--------|---------|
| 5.9.1  | 2026-04-19 | Placeholder initial — BookGuardian gate aktywowany | TBD przy starcie |

---

## Powiązane pliki

- [`book_guardian.py`](../book_guardian.py) — implementacja watchdoga
- [`dashboard/book_guardian_rebase.py`](../dashboard/book_guardian_rebase.py) — narzędzie re-baseline
- [`docs/PHANTOM_V3_SPEC.md`](./PHANTOM_V3_SPEC.md) — warstwa anty-halucynacyjna
- [`docs/FIX_MAP_v5.9.1.md`](./FIX_MAP_v5.9.1.md) — mapa napraw v5.9.1
