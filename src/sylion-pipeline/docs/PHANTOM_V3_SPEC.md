# Phantom v3 — Anti-Hallucination Layer 3

**Wersja:** 3.0 (v5.9.1)  
**Data:** 2026-04-19  
**Gate:** CRITICAL — halt pipeline on any phantom detection (unless override flag set)

---

## Implementacja

- `claim_provenance.py` — rejestracja i weryfikacja źródeł twierdzeń agentów
- `file_verification.py` — weryfikacja istnienia, rozmiaru i SHA-256 plików
- `HallucinationGuard` — główny kontroler warstwy anty-halucynacyjnej (orchestrator gate)

---

## 4 wykrywane typy PHANTOM_FILE

| Typ | Opis | Warunek detekcji |
|-----|------|-----------------|
| **PHANTOM_TYPE_1** | Claim `FIXED`/`MODIFIED` + plik nie istnieje po iteracji | Agent twierdzi, że naprawił plik, ale plik nie istnieje po zakończeniu iteracji |
| **PHANTOM_TYPE_2** | Claim `FIXED`/`MODIFIED` + plik nie istniał też przed | Agent twierdzi, że zmodyfikował plik, który nigdy nie istniał (fikcyjna ścieżka) |
| **PHANTOM_TYPE_3** | Claim `CREATED` + plik nie istnieje po | Agent twierdzi, że stworzył plik, ale plik nie pojawia się w systemie plików |
| **PHANTOM_TYPE_4** | Claim `DELETED` + plik nie istniał przed | Agent twierdzi, że usunął plik, który nie istniał przed operacją |

---

## Dodatkowe typy hallucynacji

| Typ | Opis | Detekcja |
|-----|------|---------|
| **PATH_TRAVERSAL** | Ścieżki `../../../`, symlink escape poza sandbox | Regex + symlink resolution check w `file_verification.py` |
| **SIZE_MISMATCH** | Deklarowany rozmiar pliku w claimie ≠ rzeczywisty rozmiar po operacji | Porównanie `claimed_bytes` vs `os.path.getsize()` |
| **SHA_MISMATCH** | Deklarowany SHA-256 w claimie ≠ obliczony SHA-256 pliku | `hashlib.sha256` weryfikacja w `claim_provenance.py` |

---

## Architektura detekcji

```
Agent Claim
    │
    ▼
claim_provenance.py
  ├── parse_claim(action, path, claimed_sha, claimed_size)
  ├── snapshot_before(path)        ← stan przed operacją
  └── snapshot_after(path)         ← stan po operacji
    │
    ▼
file_verification.py
  ├── verify_exists(path)
  ├── verify_sha256(path, claimed_sha)
  ├── verify_size(path, claimed_size)
  └── verify_no_path_traversal(path)
    │
    ▼
HallucinationGuard
  ├── check_phantom_type_1_4()
  ├── check_path_traversal()
  ├── check_size_mismatch()
  ├── check_sha_mismatch()
  └── emit_halt() ─► Gate CRITICAL → pipeline STOP
```

---

## Testy

- `tests/test_hallucination_guard_v591.py` — testy jednostkowe HallucinationGuard (wszystkie 4 typy PHANTOM + PATH_TRAVERSAL + SIZE_MISMATCH + SHA_MISMATCH)
- `tests/test_claim_provenance_v591.py` — testy parsowania i weryfikacji claimów

### Znane naprawione błędy (v5.9.1)
- **FIX-v591-45** (P3-11 PHANTOM-LOG): `log.warning()` → `logger.warning()` w `file_verification.py:336,344` — naprawiono `NameError` w runtime warstwy anty-halucynacyjnej

---

## Gate

**Gate supervisor: CRITICAL** — halt pipeline przy wykryciu dowolnego phantom, chyba że ustawiono flagę override:

```bash
# Override (tylko w trybie debug/test — NIE na produkcji):
PHANTOM_OVERRIDE=1 python start.py
```

### Zachowanie przy wykryciu

| Sytuacja | Zachowanie |
|----------|-----------|
| PHANTOM_TYPE_1..4 | Immediately halt + log full claim diff |
| PATH_TRAVERSAL | Halt + alert security log |
| SIZE_MISMATCH | Halt + log expected vs actual bytes |
| SHA_MISMATCH | Halt + log expected vs computed SHA-256 |
| PHANTOM_OVERRIDE=1 | Log warning, continue (non-production only) |

---

## Powiązane pliki

- [`claim_provenance.py`](../claim_provenance.py)
- [`file_verification.py`](../file_verification.py)
- [`book_guardian.py`](../book_guardian.py)
- [`docs/KSIEGA_3_4_SPEC.md`](./KSIEGA_3_4_SPEC.md) — dokument monitorowany przez BookGuardian
- [`docs/FIX_MAP_v5.9.1.md`](./FIX_MAP_v5.9.1.md) — patrz FIX-v591-45 (PHANTOM-LOG fix)
