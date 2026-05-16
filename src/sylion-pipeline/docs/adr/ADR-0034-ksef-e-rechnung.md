# ADR-001: KSeF / JPK / GoBD / E-Rechnung — Compliance Architecture Decision Record

**Status:** Accepted  
**Date:** 2026-02  
**Authors:** SYLION Platform Team  
**Scope:** SYLION sp. z o.o. (PL) + RSDG GmbH (DE), v5.10  

---

## Context

SYLION operates two legal entities:

| Entity | Jurisdiction | Key obligations |
|---|---|---|
| SYLION sp. z o.o. | PL | KSeF (oblig. 2026-02-01), JPK_V7M(3), VAT-UE |
| RSDG GmbH | DE | GoBD (BMF 2019), E-Rechnung (XRechnung 3.0.1 / ZUGFeRD 2.3), HGB §257 / AO §147 |

SYLION v5.9.1 is a developer tooling SaaS platform. The `cost_log` table captures per-user resource consumption and serves as the basis for intercompany transfer pricing invoices (SYLION sp. z o.o. ↔ RSDG GmbH). These must comply with both Polish and German e-invoicing and archiving mandates.

---

## Decision 1: KSeF API Version

**Decision:** Target KSeF 2.0 API with FA(2) schema (schema version `1-0E`).

**Rationale:**
- KSeF FA(2) has been mandatory since 2023-09-01 ([ksef.podatki.gov.pl](https://ksef.podatki.gov.pl/informacje-ogolne-ksef-20/faktura-ustrukturyzowana-i-struktura-logiczna-fa/)).
- KSeF 2.0 (integrated with PEF) is live from 2026-02-01 ([ksef.podatki.gov.pl](https://ksef.podatki.gov.pl/)).
- The `ksef_client.py` implements token-based auth (HMAC-SHA256 challenge/response) as specified by MF.
- Session lifecycle: `AuthorisationChallenge` → `InitToken` → `Invoice/Send` → `Invoice/Status` → `Session/Terminate` → UPO download.

**Rejected alternatives:**
- FA(1): deprecated since 2023-09-01.
- Batch (offline) API: not suitable for real-time confirmation required by KSeF.

---

## Decision 2: JPK Schema Version

**Decision:** JPK_V7M(3) and JPK_FA(4) — mandatory from 2026-02-01.

**Rationale:**
- JPK_V7M(3) adds mandatory field `NrKSeF` (or flag `OFF`/`BFK`/`DI`) per [CRIDO analysis](https://crido.pl/blog-taxes/jpk_v73-nowa-schema/) and [Microsoft Dynamics 365 release plan](https://learn.microsoft.com/en-us/dynamics365/release-plan/2025wave2/enterprise-resource-planning/dynamics365-finance/use-regulatory-update-jpkv73-schema-vat-declaration-poland).
- New field `K_360`/`P_360` tracks count of invoices without KSeF number.
- `jpk_exporter.py` raises `ValueError` at export time if any invoice line lacks `nr_ksef` and a valid flag — this prevents MF technical rejection.

**Flags for missing KSeF number (from 2026-02-01):**
- `OFF` — obligatory KSeF unavailable (outage)
- `BFK` — invoice exempt from KSeF (B2C, non-VAT, foreign)
- `DI` — other exemption

---

## Decision 3: German E-Rechnung Format

**Decision:** Generate both XRechnung 3.0.1 (UBL 2.1) and ZUGFeRD 2.3 hybrid.

**Rationale:**
- **XRechnung 3.0.1**: required for B2G invoicing (Leitweg-ID in BT-10 BuyerReference). Based on EN 16931-1, CIUS. Supported syntax: UBL 2.1 ([xeinkauf.de](https://xeinkauf.de/xrechnung/)).
- **ZUGFeRD 2.3**: preferred for B2B. Hybrid PDF/A-3b + embedded CII XML (`factur-x.xml`, EN 16931 profile). Fully compatible with Factur-X 1.0.07 ([ferd-net.de](https://www.ferd-net.de/standards/zugferd-version-2.3/)).
- From 2025-01-01 (§14 UStG, Wachstumschancengesetz), B2B receivers must be capable of accepting structured e-invoices. From 2027-01-01, B2B issuers must send them.
- Intercompany SYLION↔RSDG invoices should use ZUGFeRD (both entities are business, no Leitweg-ID required).

**Leitweg-ID:**
- Stored in `entities.leitweg_id` (nullable).
- Required only for B2G. Format: `{Behördenkennziffer}-{Abteilung}-{Prüfziffer}` per [Leitweg-ID 2.0 spec](https://www.xoev.de/die_standards/leitweg_id-16448).
- In `e_rechnung_de.py`, if `leitweg_id` is None and no `purchase_order_ref`, BT-10 defaults to `"NONE"` (XRechnung mandates non-empty value).

---

## Decision 4: GoBD Compliance Architecture

**Decision:** Three-layer WORM implementation — DB trigger + SHA-256 hashchain + Cloud Object Lock.

**Rationale:**
- GoBD 2019 Rn. 103 requires immutability ("Unveränderlichkeit") — either organizational or technical measures.
- DB-level: `fn_worm_guard()` trigger on `invoices` table raises exception on UPDATE/DELETE after `is_worm_locked = TRUE`.
- Application-level: `WORMManager` computes SHA-256 of canonical XML, stores in `invoices.hash_sha256`, appends to `HashChain` for tamper-evidence.
- Storage-level: AWS S3 Object Lock (COMPLIANCE mode) or GCS Bucket Lock — configured via `S3WORMConfig` / `GCSWORMConfig`.
- Audit: `audit_trail_accounting` — INSERT-only table (PG rules block UPDATE/DELETE), 10-year retention.

**Retention periods ([CSP Intelligence GmbH](https://www.csp-sw.com/blog/retention-periods), [Fiskaly](https://www.fiskaly.com/blog/understanding-gobd-compliant-archiving)):**

| Document type | Period | Basis |
|---|---|---|
| Invoices, booking documents | 10 years | HGB §257 / AO §147 / GoBD |
| Commercial letters | 6 years | HGB §257 Abs. 4 |
| Annual accounts, balance sheets | 10 years | HGB §257 / AO §147 |
| Tax-relevant emails | 10 years | AO §147 / GoBD |

Retention clock starts: end of the calendar year in which the document was created.

---

## Decision 5: audit_trail_accounting vs. audit_log

**Decision:** Separate `audit_trail_accounting` table with 10-year retention, distinct from standard `audit_log` (90-day retention).

**Rationale:**
- Standard `audit_log` covers application events (login, settings changes) — 90-day GDPR/operational retention is sufficient.
- `audit_trail_accounting` covers financial and tax events — 10-year statutory retention under HGB §257 / AO §147.
- Mixing these in one table creates conflicting deletion policies and GDPR complexity.
- `audit_trail_accounting` uses PG rules (`DO INSTEAD NOTHING`) to block UPDATE/DELETE at database level — not just application-level.

---

## Decision 6: Transfer Pricing — cost_log as basis

**Decision:** `cost_log` per-user resource metrics serve as the basis for intercompany transfer pricing (TP) documentation between SYLION sp. z o.o. (PL) and RSDG GmbH (DE). Invoices are issued via KSeF (outbound PL) and ZUGFeRD (DE).

**Rationale:**
- SYLION v5.9.1 is developer tooling — it does NOT issue external customer invoices itself.
- Per-user `cost_log` (API calls, compute hours, storage) → aggregated monthly → base for TP invoices under arm's length principle (OECD Transfer Pricing Guidelines).
- `invoices.intercompany = TRUE` + `invoices.tp_document_ref` links the invoice to TP documentation.
- PL entity issues KSeF FA(2) invoice; DE entity receives as ZUGFeRD 2.3 hybrid.
- Dual compliance: PL JPK_V7M(3) NrKSeF required; DE GoBD 10-year archive required.

---

## Decision 7: Python async vs. sync

**Decision:** `ksef_client.py` is fully async (`httpx.AsyncClient`); `jpk_exporter.py`, `e_rechnung_de.py`, `gobd_retention.py` are sync (CPU-bound XML generation).

**Rationale:**
- KSeF API calls are network I/O — async reduces latency in bulk send scenarios.
- XML generation is CPU-bound and fast; sync is simpler and easier to test.
- `gobd_retention.py` DB writes can optionally use async with `asyncpg`.

---

## Decision 8: Cryptographic Integrity

**Decision:** SHA-256 for document hashes; HMAC-SHA256 for KSeF auth tokens; SHA-256 hashchain for audit integrity.

**Rationale:**
- SHA-256: current GoBD/BSI standard (BSI TR-03116).
- KSeF uses HMAC-SHA256 per official MF API specification.
- HashChain: each entry chains `SHA-256(prev_hash || doc_hash)` — detects any retroactive modification.
- IP addresses in audit trail: pseudonymised via SHA-256 (GDPR Art. 25 — Privacy by Design).

---

## Consequences

**Positive:**
- Full compliance with KSeF 2.0 (PL, from 2026-02-01), JPK_V7M(3), XRechnung 3.0.1, ZUGFeRD 2.3, GoBD 2019.
- WORM lock prevents accidental or intentional modification of issued invoices.
- 10-year audit trail with tamper-evident hashchain.
- Separate retention policies for accounting vs. operational data.

**Risks / Mitigations:**
- **KSeF outage** → use `ksef_flag = "OFF"` in JPK, re-send when KSeF restored. Dead letter queue required.
- **Leitweg-ID changes** → store per-entity; update before invoice generation; versioned in `entities` table.
- **Schema updates** (MF publishes new XSDs) → validation step in `_validate_fa2_xml()` must reference current XSD; CI pipeline should pull latest from MF schema repository.
- **reportlab / pypdf unavailable** → `e_rechnung_de.py` gracefully degrades (returns CII XML or stub PDF with warning).
- **GDPR vs. 10-year retention conflict** → personal data in invoices is retained for the statutory period; pseudonymisation of IP in audit trail; access restricted to authorized accounting roles only.

---

## References

- [KSeF oficjalny portal MF](https://ksef.podatki.gov.pl/)
- [JPK_V7M(3) schema — Ministerstwo Finansów](https://www.gov.pl/web/finanse/konsultacje-podatkowe-struktur-jpkv7m3-i-jpkv7k3)
- [CRIDO JPK_V7(3) od 2026-02](https://crido.pl/blog-taxes/jpk_v73-nowa-schema/)
- [XRechnung 3.0.1 — xeinkauf.de](https://xeinkauf.de/xrechnung/)
- [ZUGFeRD 2.3 — ferd-net.de](https://www.ferd-net.de/standards/zugferd-version-2.3/)
- [GoBD BMF-Schreiben 2019 — bundesfinanzministerium.de](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Weitere_Steuerthemen/Abgabenordnung/2019-11-28-GoBD.html)
- [Retention Periods 2026 — CSP Intelligence](https://www.csp-sw.com/blog/retention-periods)
- [GoBD archiving — Fiskaly](https://www.fiskaly.com/blog/understanding-gobd-compliant-archiving)
- [HGB §257 — gesetze-im-internet.de](https://www.gesetze-im-internet.de/hgb/__257.html)
- [AO §147 — gesetze-im-internet.de](https://www.gesetze-im-internet.de/ao_1977/__147.html)
