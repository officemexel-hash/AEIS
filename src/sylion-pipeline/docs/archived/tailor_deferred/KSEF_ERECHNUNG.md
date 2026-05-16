# KSeF (PL) + E-Rechnung (DE) — Integration Status v5.9.1

STATUS: NOT INTEGRATED (out of scope for core pipeline).

SYLION processes operational data (users, audit, baselines) — no invoicing.
If invoicing data enters SYLION via future module, KSeF (PL FA(2)) and German E-Rechnung (XRechnung/ZUGFeRD) compliance will be required.

Planned: v5.11 invoice ingestion module with optional KSeF XML export.

---

## Background

### KSeF — Krajowy System e-Faktur (Poland)

KSeF is the Polish national e-invoicing system mandated by the Ministry of Finance (MF).
Polish VAT taxpayers are required to issue structured invoices in the FA(2) XML schema
via the KSeF API once the mandatory rollout dates take effect.

**Applicability to SYLION v5.9.1:** N/A.

- SYLION contains no invoicing module.
- Searches for `ksef`, `faktur`, `jpk`, `nip`, `vat` in `dashboard/app.py` and `dashboard/db.py`
  return zero results related to invoicing.
- The operator (Robert / RSDG GmbH) must register with KSeF independently for their own
  business invoicing — this is not handled by SYLION.

**Future scope (v5.11+):** If an invoice ingestion module is added, the following will be required:
- FA(2) XML schema validation (MF schema: `FA_VAT(2)`)
- KSeF API integration (`https://ksef.mf.gov.pl/api`)
- HMAC-SHA256 session token auth
- Structured invoice storage with 5-year retention (Art.112 VAT Act PL)

---

### E-Rechnung — German Electronic Invoice (XRechnung / ZUGFeRD)

German law requires e-invoicing for B2B transactions with public entities (B2G) since 2020.
B2B mandatory e-invoicing is being phased in under the German Growth Opportunities Act
(Wachstumschancengesetz), with the mandatory B2B e-invoice reception deadline: **2025-01-01**.

Supported formats:
- **XRechnung** (EN 16931 core invoice XML — UBL or CII)
- **ZUGFeRD** (hybrid PDF/A-3 + embedded XML; profiles: MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED)

**Applicability to SYLION v5.9.1:** N/A.

- SYLION processes AI pipeline operational data, not commercial invoices.
- RSDG GmbH (DE operator) must handle its own e-invoice compliance separately.

**Future scope (v5.11+):**
- ZUGFeRD PDF generation (using `factur-x` Python library)
- XRechnung XML generation (using `lxml` + EN 16931 schema)
- GoBD-compliant 10-year retention for invoice records (HGB §257, AO §147)
- Immutable storage (no UPDATE/DELETE on invoice rows)

---

## Action Items for Future Modules

| Item | Owner | Target Version |
|------|-------|---------------|
| KSeF FA(2) XML schema integration | Backend team | v5.11 |
| KSeF API session management | Backend team | v5.11 |
| XRechnung/ZUGFeRD generation | Backend team | v5.11 |
| GoBD 10-year retention + immutability | DB team | v5.11 |
| RSDG GmbH e-invoice workflow documentation | Legal/Finance | Pre-v5.11 |

---

*Document created: 2026-04-19 — Fix Cluster Q (RODO/KSeF compliance, SYLION v5.9.1)*
