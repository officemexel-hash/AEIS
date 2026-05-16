# ADR-002: Świadomy scope mismatch między PDF "SYLION v5.8.8 dokumentacja" a rzeczywistym diff

**Status:** Accepted (documentation alignment)
**Data:** 2026-04-18
**Autor:** dokument-analiza-council + pr-reviewer-council (consensus Opus + GPT-5.4 + Sonnet + Gemini)

## Kontekst

Dokumentacja `SYLION_v588_dokumentacja.pdf` deklaruje 18 napraw, z czego analiza rady 4 modeli (Opus v588doc-opus.md) wykazała:
- **2 naprawy rzeczywiście zaimplementowane** (11%)
- **16 napraw fikcyjnych** (89%) — odnoszą się m.in. do modułu `sylion_deps.py`, który **nie istnieje** w projekcie

Weryfikacja: `find /home/user/workspace/SYLION_v588_work -name "sylion_deps*"` → **0 wyników**.

## Decyzja

**Dokumentacja PDF zostaje jako historical document** (opis zamierzonego scope), ale faktyczne zmiany w v5.8.8.1 są udokumentowane **wyłącznie** w:

1. `CHANGELOG_v5.8.8.md` — 10 napraw z v5.8.8 (Bugs 1–10)
2. `CHANGELOG_v5.8.8.1.md` — 4 dodatkowe naprawy v5.8.8.1 (H-01 do H-03 z matrycy findings)
3. Pliki ADR-001 i niniejsze ADR-002

CHANGELOG jawnie przyznaje: *"release oparty nie na liście z PDF"* (v5.8.8 linia 30+).

## Uzasadnienie

- **Evidence-based release**: zgodnie z instrukcją użytkownika *"lista napraw w dokumencie to jedno, a to jak działa system w rzeczywistości to drugie"*
- **PDF był draftem** zamiar napraw przed rozpoczęciem rady modeli — rada zidentyfikowała inne (rzeczywiste) bugi (Bug 2, 3, 8, 9, Opcja C, port migration, malformed-id guard)
- **Refactor `sylion_deps.py`** odłożony — wymaga osobnego cyklu deweloperskiego

## Rzeczywiste naprawy v5.8.8 → v5.8.8.1

Patrz CHANGELOG v5.8.8.1:
- H-01: dedup `compute_sha256` w `db.py`
- H-02: `_db_init_lock` w `bridge.py`
- H-03: bump VERSION → `5.8.8.1`, header `health_check.py`

## Konsekwencje

- Developer otwierając PDF musi wiedzieć że jest to dokument deklaracji, nie rzeczywistości
- CHANGELOG.md jest **źródłem prawdy** o tym co zostało zrobione
- Roadmap v5.8.9 będzie pisany bezpośrednio w CHANGELOG zamiast odrębnego PDF
