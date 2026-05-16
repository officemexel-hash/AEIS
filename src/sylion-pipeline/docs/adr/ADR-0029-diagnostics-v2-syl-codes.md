# ADR-0029: Diagnostyka v2 z 82 kodami SYL-*

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/diagnostyka_deep  

---

## Kontekst

Audyt mega_audit/diagnostyka_deep wykazał krytyczne braki w systemie diagnostycznym SYLION:

1. **Brak ustrukturyzowanych kodów błędów**: komunikaty błędów w logach (`dashboard/db.py`, `agents/`) były wolnymi stringami (`"Error: connection failed"`, `"Invalid config"`). Niemożność programatycznego parsowania logów przez monitoring (Prometheus, Grafana Loki).
2. **Brak wersjonowania diagnostyki**: system v1 (ad-hoc logi) uniemożliwiał korelację błędów między wersjami SYLION.
3. **87 kategorii błędów bez kodu**: audyt zidentyfikował 87 unikalnych klas błędów (network, auth, db, pipeline, agent, config, migration, backup), z których 0 miało ustrukturyzowany kod.
4. **Niemożność SRE triage**: gdy agent zwracał błąd, SRE musiał czytać pełny traceback zamiast szybkiego lookup kodu SYL-XXX w runbooku.

Rozważane warianty:
- **D1** — Structured logging z JSON (bez kodów) — parsowalne, ale brak kodów dla runbooków
- **D2** — Kody SYL-* jako enum + middleware logowania (wybrana)
- **D3** — OpenTelemetry semantic conventions z `error.type` attribute
- **D4** — Sentry SDK z issue grouping (wymaga zewnętrznego serwisu)

## Decyzja

Wdrożenie **D2**: hierarchiczny system 82 kodów `SYL-XXXX` podzielonych na domeny:

| Zakres | Domena | Przykłady |
|--------|--------|-----------|
| SYL-1000..1099 | Auth & Session | SYL-1001 (token expired), SYL-1002 (invalid CSRF) |
| SYL-2000..2099 | Database | SYL-2001 (db lock timeout), SYL-2002 (migration failed) |
| SYL-3000..3099 | Agent | SYL-3001 (agent timeout), SYL-3002 (ollama unreachable) |
| SYL-4000..4099 | Pipeline | SYL-4001 (zip too large), SYL-4002 (extraction failed) |
| SYL-5000..5099 | Config | SYL-5001 (invalid yaml), SYL-5002 (missing required key) |
| SYL-6000..6099 | Network/VPN | SYL-6001 (wg tunnel down), SYL-6002 (dns leak detected) |
| SYL-7000..7099 | Backup | SYL-7001 (wal checkpoint failed), SYL-7002 (fs read-only) |
| SYL-8000..8099 | Security | SYL-8001 (rate limit exceeded), SYL-8002 (csrf mismatch) |

Kody zdefiniowane w `dashboard/diagnostics.py` jako `DiagCode(Enum)`. Każdy kod ma: `code`, `message_pl`, `message_de`, `severity` (DEBUG/INFO/WARN/ERROR/CRITICAL), `runbook_url`. Middleware `DiagnosticsMiddleware` enriches odpowiedzi HTTP 4xx/5xx z `X-Syl-Code` header i strukturalnym JSON body `{"syl_code": "SYL-2001", "detail": "..."}`.

## Konsekwencje

### Pozytywne
- 82 kody pokrywają 94% zaobserwowanych błędów (audyt diagnostyka_deep)
- SRE triage: lookup SYL-XXXX → runbook → 5 kroków naprawczych (zamiast pełnego traceback)
- Prometheus alert rules (mega_audit/prometheus_alert_rules) mogą filtrować po `syl_code`
- Wielojęzyczność: kody w PL i DE (BDSG compliance)

### Negatywne
- 82 kody wymagają utrzymania przy każdej nowej klasie błędów — ryzyko code drift
- `X-Syl-Code` header nie jest standardem — klienci zewnętrzni muszą znać schemat SYLION
- Migracja istniejących logów (v1 → v2): grep + replace 200+ miejsc w kodzie

### Neutralne
- Kody 83..99 zarezerwowane dla przyszłych domen (IoT, KSEF, federation)
- Backward compat: przy braku kodu system fallbackuje do `SYL-0000` (generic error)

## Alternatywy odrzucone

- **OpenTelemetry (D3)**: poprawne technicznie, ale wymaga OTel collector — nadmierna złożoność dla self-hosted lokalnej instancji
- **Sentry (D4)**: wymaga zewnętrznego serwisu — naruszenie data sovereignty (dane błędów mogą zawierać PII)

## Referencje

- `mega_audit/diagnostyka_deep/` — pełna analiza systemu diagnostycznego
- `mega_audit/diagnostyka/` — wstępny audyt (faza 1)
- `dashboard/diagnostics.py` — `DiagCode`, `DiagnosticsMiddleware`
- `mega_audit/prometheus_alert_rules/` — reguły alertowania Prometheus z filtrami SYL-*
- `docs/RUNBOOK.md` — runbook z opisem kodów SYL-* (do stworzenia w v5.9.2)
- `mega_audit/sre_incidents/`, `mega_audit/sre_incident_oncall/` — incydenty SRE
