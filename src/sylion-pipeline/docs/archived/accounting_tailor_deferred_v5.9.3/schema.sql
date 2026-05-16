-- ============================================================
-- SYLION v5.9.1 — Compliance DB Schema
-- PL: KSeF (KSeF 2.0 / FA(2)), JPK_V7M(3)
-- DE: GoBD, E-Rechnung (XRechnung 3.0.1 / ZUGFeRD 2.3)
-- HGB §257 / AO §147 — 10-year retention
-- ============================================================

-- -------------------------------------------------------
-- 1. INVOICES
-- Master invoice table — shared PL + DE entities
-- Status: DRAFT | PENDING_KSEF | KSEF_OK | KSEF_REJECTED |
--         PENDING_ERECHNUNG | ERECHNUNG_OK | CANCELLED
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer_id        UUID NOT NULL REFERENCES entities(id),
    buyer_id         UUID NOT NULL REFERENCES entities(id),
    number           VARCHAR(64)  NOT NULL,           -- np. SYL/2026/001
    issue_date       DATE         NOT NULL,
    due_date         DATE,
    currency         CHAR(3)      NOT NULL DEFAULT 'PLN',
    net              NUMERIC(18,2) NOT NULL,
    vat              NUMERIC(18,2) NOT NULL DEFAULT 0,
    gross            NUMERIC(18,2) GENERATED ALWAYS AS (net + vat) STORED,
    vat_rate         NUMERIC(5,2),                    -- 0, 5, 8, 23 (PL); 0, 7, 19 (DE)
    status           VARCHAR(32)  NOT NULL DEFAULT 'DRAFT',
    -- KSeF (PL)
    ksef_id          VARCHAR(128),                    -- NumerKSeF przydzielony przez MF
    ksef_session_id  VARCHAR(128),
    ksef_sent_at     TIMESTAMPTZ,
    ksef_status      VARCHAR(32),                     -- RECEIVED | PROCESSING | OCR | REJECTED
    upo_bytes        BYTEA,                           -- Urzędowe Poświadczenie Odbioru (PDF)
    -- DE E-Rechnung
    e_rechnung_id    VARCHAR(128),                    -- Leitweg-ID (routing)
    e_rechnung_format VARCHAR(16),                    -- XRECHNUNG | ZUGFERD
    e_rechnung_xml   TEXT,                            -- raw CII/UBL XML stored for GoBD
    -- Intercompany transfer pricing
    intercompany     BOOLEAN      NOT NULL DEFAULT FALSE,
    tp_document_ref  VARCHAR(128),                    -- reference to TP documentation
    -- Audit / retention
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_by       UUID,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    is_worm_locked   BOOLEAN      NOT NULL DEFAULT FALSE,  -- GoBD WORM flag
    worm_locked_at   TIMESTAMPTZ,
    hash_sha256      CHAR(64),                        -- SHA-256 of canonical XML at WORM lock
    retain_until     DATE GENERATED ALWAYS AS (issue_date + INTERVAL '10 years') STORED,

    CONSTRAINT invoices_status_check CHECK (status IN (
        'DRAFT','PENDING_KSEF','KSEF_OK','KSEF_REJECTED',
        'PENDING_ERECHNUNG','ERECHNUNG_OK','CANCELLED'
    )),
    CONSTRAINT invoices_currency_check CHECK (currency ~ '^[A-Z]{3}$')
);

-- Prevent UPDATE on WORM-locked invoices (trigger-enforced, see below)
-- ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;  -- enable in prod with policy

-- -------------------------------------------------------
-- 2. INVOICE_LINES
-- Line items per invoice (VAT rates may differ per line)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoice_lines (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id   UUID NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    line_number  SMALLINT NOT NULL,
    description  TEXT NOT NULL,
    qty          NUMERIC(12,4) NOT NULL DEFAULT 1,
    unit         VARCHAR(16)  NOT NULL DEFAULT 'szt',    -- szt | h | pcs | stk
    unit_price   NUMERIC(18,4) NOT NULL,                 -- netto per unit
    vat_rate     NUMERIC(5,2) NOT NULL DEFAULT 23,       -- 0 | 5 | 8 | 23 (PL) / 0 | 7 | 19 (DE)
    vat_amount   NUMERIC(18,2) GENERATED ALWAYS AS (
                    ROUND(qty * unit_price * vat_rate / 100, 2)
                 ) STORED,
    net_amount   NUMERIC(18,2) GENERATED ALWAYS AS (
                    ROUND(qty * unit_price, 2)
                 ) STORED,
    gttin        VARCHAR(32),                            -- opcjonalny kod towaru

    CONSTRAINT invoice_lines_qty_positive CHECK (qty > 0),
    CONSTRAINT invoice_lines_price_positive CHECK (unit_price >= 0)
);

-- -------------------------------------------------------
-- 3. COMPLIANCE_REPORTS
-- Periodic exports: JPK_V7M, JPK_FA, GoBD-Export, VAT-UE, OSS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS compliance_reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period       VARCHAR(7)  NOT NULL,          -- format: YYYY-MM
    type         VARCHAR(16) NOT NULL,          -- JPK_V7M | JPK_FA | GOBD | VAT_UE | OSS
    entity_id    UUID NOT NULL REFERENCES entities(id),
    status       VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    xml_payload  TEXT,                          -- wygenerowany XML (zaszyfrowany at-rest)
    exported_at  TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    submission_ref VARCHAR(128),               -- numer referencyjny MF / Finanzamt
    hash         CHAR(64),                     -- SHA-256 of xml_payload
    file_path    TEXT,                         -- S3/GCS WORM bucket path
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by   UUID,
    is_worm_locked BOOLEAN NOT NULL DEFAULT FALSE,
    retain_until   DATE NOT NULL,              -- calculated: period + 10 years

    CONSTRAINT compliance_reports_type_check CHECK (type IN (
        'JPK_V7M','JPK_V7K','JPK_FA','GOBD','VAT_UE','OSS'
    )),
    CONSTRAINT compliance_reports_status_check CHECK (status IN (
        'PENDING','GENERATING','READY','SUBMITTED','ACCEPTED','REJECTED','ARCHIVED'
    ))
);

-- -------------------------------------------------------
-- 4. AUDIT_TRAIL_ACCOUNTING
-- 10-year retention (GoBD / HGB §257 / AO §147)
-- NOT the standard 90-day audit_log — separate table
-- Immutable: rows are INSERT-only (no UPDATE, no DELETE)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_trail_accounting (
    id             BIGSERIAL PRIMARY KEY,
    event_time     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id       UUID,                               -- user or service account
    actor_ip       INET,
    actor_service  VARCHAR(64),                        -- 'ksef_client' | 'jpk_exporter' etc.
    object_type    VARCHAR(32) NOT NULL,               -- 'invoice' | 'compliance_report' etc.
    object_id      UUID NOT NULL,
    action         VARCHAR(32) NOT NULL,               -- CREATE | UPDATE | DELETE | WORM_LOCK | EXPORT | SUBMIT
    field_name     VARCHAR(64),                        -- changed field (if UPDATE)
    old_value      TEXT,
    new_value      TEXT,
    ip_hash        CHAR(64),                           -- SHA-256(actor_ip) for GDPR pseudonymisation
    session_id     VARCHAR(128),
    ksef_id        VARCHAR(128),                       -- denormalised for fast audit queries
    retain_until   DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '10 years'),
    payload_hash   CHAR(64),                           -- SHA-256 of full JSON payload for integrity

    CONSTRAINT ata_action_check CHECK (action IN (
        'CREATE','UPDATE','DELETE','WORM_LOCK','EXPORT','SUBMIT','VIEW','DOWNLOAD_UPO'
    ))
);

-- Prevent any modification of audit rows
CREATE OR REPLACE RULE audit_trail_accounting_no_update
    AS ON UPDATE TO audit_trail_accounting DO INSTEAD NOTHING;
CREATE OR REPLACE RULE audit_trail_accounting_no_delete
    AS ON DELETE TO audit_trail_accounting DO INSTEAD NOTHING;

-- Index for time-range queries (common in audits)
CREATE INDEX IF NOT EXISTS idx_ata_event_time
    ON audit_trail_accounting (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_ata_object
    ON audit_trail_accounting (object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_ata_ksef_id
    ON audit_trail_accounting (ksef_id)
    WHERE ksef_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ata_retain_until
    ON audit_trail_accounting (retain_until);

-- -------------------------------------------------------
-- 5. ENTITIES (issuer / buyer master)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS entities (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(256) NOT NULL,
    country      CHAR(2) NOT NULL,                    -- PL | DE
    tax_id       VARCHAR(32)  NOT NULL,               -- NIP (PL) | Steuernummer/USt-IdNr (DE)
    vat_id       VARCHAR(32),                         -- EU VAT: PL1234567890 | DE123456789
    address_line VARCHAR(256),
    city         VARCHAR(128),
    postal_code  VARCHAR(16),
    leitweg_id   VARCHAR(64),                         -- DE B2G only — XRechnung routing
    iban         VARCHAR(34),                         -- for payment data on invoices
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------------------------------------
-- 6. WORM trigger — block UPDATE/DELETE on locked invoices
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_worm_guard()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.is_worm_locked THEN
        RAISE EXCEPTION 'GoBD WORM violation: invoice % is immutable after WORM lock', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_invoices_worm
    BEFORE UPDATE OR DELETE ON invoices
    FOR EACH ROW EXECUTE FUNCTION fn_worm_guard();

-- -------------------------------------------------------
-- 7. Auto-updated_at trigger
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION fn_updated_at();

-- -------------------------------------------------------
-- Comments / documentation
-- -------------------------------------------------------
COMMENT ON TABLE invoices IS
    'Master invoice table. Supports KSeF (PL) and E-Rechnung/XRechnung/ZUGFeRD (DE). '
    'WORM lock enforced by trigger after KSeF confirmation or GoBD archival. '
    'retain_until = issue_date + 10 years (HGB §257, AO §147, GoBD 2019).';

COMMENT ON TABLE audit_trail_accounting IS
    'Immutable accounting audit trail (INSERT-only). '
    'Retention: 10 years per HGB §257 / AO §147 / GoBD. '
    'Separate from standard 90-day audit_log. '
    'Rules prevent UPDATE and DELETE at DB level.';

COMMENT ON COLUMN invoices.ksef_id IS
    'NumerKSeF — unique identifier assigned by Krajowy System e-Faktur (MF). '
    'Mandatory in JPK_V7M(3) from 2026-02-01 if invoice was issued via KSeF.';

COMMENT ON COLUMN invoices.leitweg_id IS
    'Leitweg-ID (routing identifier) for German B2G XRechnung invoices. '
    'Placed in BT-10 BuyerReference per EN 16931 / XRechnung 3.0.1 spec. '
    'Stored on entity level but denormalised here for export convenience.';
