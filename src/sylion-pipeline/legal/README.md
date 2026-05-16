# Legal Documents Index — Sylion v5.9.2

**Generated:** 2026-04-19  
**Scope:** Sylion Sp. z o.o. (PL) + RSDG GmbH (DE)  
**Pipeline:** sylion-pipeline / legal

---

## 🇵🇱 Polish Documents (`pl/`)

| File | Description | Source |
|------|-------------|--------|
| `pl/PRIVACY_POLICY.md` | Polityka Prywatności v5.9.1 | PP_v591_PL.md |
| `pl/REGULAMIN.md` | Regulamin świadczenia usług (ToS) | ToS_PL.md |
| `pl/UMOWA_POWIERZENIA.md` | Umowa powierzenia przetwarzania danych (DPA) | DPA_PL.md |
| `pl/NDA.md` | Umowa o zachowaniu poufności (NDA) | NDA_PL.md |
| `pl/COOKIE_POLICY.md` | Polityka cookies | Cookie_Policy_PL.md |
| `pl/TP_LOCAL_FILE.md` | Dokumentacja cen transferowych — plik lokalny (TP) | TP_LOCAL_FILE_PL.md |

---

## 🇩🇪 German Documents (`de/`)

| File | Description | Source |
|------|-------------|--------|
| `de/DATENSCHUTZERKLAERUNG.md` | Datenschutzerklärung v5.9.1 | PP_v591_DE.md |
| `de/AGB.md` | Allgemeine Geschäftsbedingungen | AGB_DE.md |
| `de/AVV.md` | Auftragsverarbeitungsvertrag (AVV/DPA) | AVV_DE.md |
| `de/NDA_DE.md` | Geheimhaltungsvereinbarung (NDA) | NDA_DE.md |
| `de/COOKIE_RICHTLINIE.md` | Cookie-Richtlinie | Cookie_Policy_DE.md |
| `de/VP_DOKUMENTATION.md` | Verrechnungspreisdokumentation — lokale Datei | TP_LOCAL_FILE_DE.md |

---

## 🌐 Bilingual Documents (`bilingual/`)

| File | Description | Source |
|------|-------------|--------|
| `bilingual/SCC_MODULE_2_DEEPSEEK_TIA.md` | Standard Contractual Clauses Module 2 — DeepSeek TIA | SCC_Module_2.md |
| `bilingual/IC_AGREEMENT_SYLION_RSDG.md` | Intercompany Agreement PL/DE — Sylion & RSDG GmbH | IC_AGREEMENT_PL_DE.md |

---

## 📋 Audit & Compliance Reports (root `legal/`)

| File | Description | Source |
|------|-------------|--------|
| `RODO_AUDIT_REPORT_v5.9.2.md` | Pełny audyt RODO/GDPR — Sylion v5.9.2 (2026-04-19) | rodo_full_audit/REPORT.md |

---

## 📎 Related Modules

### Finance (`../finance/`)
| File | Description |
|------|-------------|
| `cost_allocation.py` | Transfer pricing cost allocation module |

### Accounting (`../accounting/`)
| File | Description |
|------|-------------|
| `ksef_client.py` | KSeF e-invoicing client (PL) |
| `jpk_exporter.py` | JPK XML exporter (PL) |
| `e_rechnung_de.py` | E-Rechnung integration (DE) |
| `gobd_retention.py` | GoBD retention policy enforcer (DE) |
| `schema.sql` | Database schema for accounting modules |

### Architecture Decision Records (`../docs/adr/`)
| File | Description |
|------|-------------|
| `ADR-0034-ksef-e-rechnung.md` | ADR: KSeF + E-Rechnung integration decision |

---

## Document Counts

- PL documents: **6**
- DE documents: **6**
- Bilingual documents: **2**
- Audit reports: **1**
- **Total legal docs: 15**
- Finance modules: **1**
- Accounting modules: **5** (+ 1 ADR)
