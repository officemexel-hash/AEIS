# W15 Ontology Runtime Plane — DDL Preview

Poniżej znajduje się poglądowy wynik kompilatora schematów W15 dla pięciu manifestów.
DDL pokazuje tabele, indeksy i triggery wynikające z `dedicated_columns`, `relations`, `audit` i `search`.

## `customer.yaml`

```sql
-- Generated from customer.yaml (W15 schema compiler)
CREATE TABLE IF NOT EXISTS sylion_v2.customer (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    email               TEXT NOT NULL,
    phone               TEXT NULL,
    company             TEXT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','active','archived')),
    parent_project_id   UUID NULL, -- relations.parent_project -> project
    extension           JSONB NOT NULL DEFAULT '{}'::jsonb, -- jsonb_extension.field
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sylion_v2.customer
    ADD CONSTRAINT customer_parent_project_fk
    FOREIGN KEY (parent_project_id)
    REFERENCES sylion_v2.project(id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS customer_name_btree ON sylion_v2.customer (name); -- dedicated_columns.name.indexed
CREATE INDEX IF NOT EXISTS customer_email_btree ON sylion_v2.customer (email); -- dedicated_columns.email.indexed
CREATE INDEX IF NOT EXISTS customer_name_trgm ON sylion_v2.customer USING GIN (name gin_trgm_ops); -- search.columns_to_index
CREATE INDEX IF NOT EXISTS customer_company_trgm ON sylion_v2.customer USING GIN (company gin_trgm_ops); -- searchable/company

CREATE TRIGGER customer_updated_at
BEFORE UPDATE ON sylion_v2.customer
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER customer_audit_lineage
AFTER INSERT OR UPDATE OF name, email, status ON sylion_v2.customer
FOR EACH ROW EXECUTE FUNCTION sylion_v2.emit_object_lineage();
```

## `vehicle.yaml`

```sql
-- Generated from vehicle.yaml (W15 schema compiler)
CREATE TABLE IF NOT EXISTS sylion_v2.vehicle (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vin                 TEXT NOT NULL,
    plate               TEXT NOT NULL,
    make                TEXT NOT NULL,
    model               TEXT NOT NULL,
    year                INTEGER NOT NULL,
    owner_id            UUID NOT NULL, -- dedicated_columns.owner_id
    mileage_km          BIGINT NULL,
    extension           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT vehicle_vin_unique UNIQUE (vin)
);

ALTER TABLE sylion_v2.vehicle
    ADD CONSTRAINT vehicle_owner_fk
    FOREIGN KEY (owner_id)
    REFERENCES sylion_v2.customer(id)
    ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS vehicle_vin_btree ON sylion_v2.vehicle (vin); -- indexed + unique
CREATE INDEX IF NOT EXISTS vehicle_plate_btree ON sylion_v2.vehicle (plate);
CREATE INDEX IF NOT EXISTS vehicle_owner_id_btree ON sylion_v2.vehicle (owner_id);
CREATE INDEX IF NOT EXISTS vehicle_plate_trgm ON sylion_v2.vehicle USING GIN (plate gin_trgm_ops); -- search.columns_to_index
CREATE INDEX IF NOT EXISTS vehicle_make_trgm ON sylion_v2.vehicle USING GIN (make gin_trgm_ops);
CREATE INDEX IF NOT EXISTS vehicle_model_trgm ON sylion_v2.vehicle USING GIN (model gin_trgm_ops);

CREATE TRIGGER vehicle_updated_at
BEFORE UPDATE ON sylion_v2.vehicle
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER vehicle_audit_lineage
AFTER INSERT OR UPDATE OF vin, plate, owner_id, mileage_km ON sylion_v2.vehicle
FOR EACH ROW EXECUTE FUNCTION sylion_v2.emit_object_lineage();
```

## `inspection.yaml`

```sql
-- Generated from inspection.yaml (W15 schema compiler)
CREATE TABLE IF NOT EXISTS sylion_v2.inspection (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id          UUID NOT NULL, -- dedicated_columns.vehicle_id
    inspector           TEXT NOT NULL,
    inspected_at        TIMESTAMPTZ NOT NULL,
    findings_count      INTEGER NOT NULL DEFAULT 0,
    verdict             TEXT NOT NULL DEFAULT 'draft'
                            CHECK (verdict IN ('draft','passed','conditional','failed','void')),
    notes               TEXT NULL,
    extension           JSONB NOT NULL DEFAULT '{}'::jsonb, -- extension.findings
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sylion_v2.inspection
    ADD CONSTRAINT inspection_vehicle_fk
    FOREIGN KEY (vehicle_id)
    REFERENCES sylion_v2.vehicle(id)
    ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS inspection_vehicle_id_btree ON sylion_v2.inspection (vehicle_id);
CREATE INDEX IF NOT EXISTS inspection_inspector_btree ON sylion_v2.inspection (inspector);
CREATE INDEX IF NOT EXISTS inspection_inspected_at_btree ON sylion_v2.inspection (inspected_at);
CREATE INDEX IF NOT EXISTS inspection_verdict_btree ON sylion_v2.inspection (verdict);
CREATE INDEX IF NOT EXISTS inspection_inspector_trgm ON sylion_v2.inspection USING GIN (inspector gin_trgm_ops);
CREATE INDEX IF NOT EXISTS inspection_notes_trgm ON sylion_v2.inspection USING GIN (notes gin_trgm_ops);

CREATE TRIGGER inspection_updated_at
BEFORE UPDATE ON sylion_v2.inspection
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER inspection_audit_lineage
AFTER INSERT OR UPDATE OF vehicle_id, inspector, inspected_at, verdict ON sylion_v2.inspection
FOR EACH ROW EXECUTE FUNCTION sylion_v2.emit_object_lineage();
```

## `project.yaml`

```sql
-- Generated from project.yaml (W15 schema compiler)
CREATE TABLE IF NOT EXISTS sylion_v2.project (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN (
                                'draft',
                                'definition_in_progress',
                                'active',
                                'paused',
                                'completed',
                                'archived',
                                'deleted'
                            )),
    idea                TEXT NULL,
    owner_id            UUID NOT NULL,
    deadline            TIMESTAMPTZ NULL,
    budget_usd          NUMERIC NULL,
    customer_id         UUID NULL, -- relations.customer -> customer
    parent_idea_id      UUID NULL, -- relations.parent_idea -> idea
    extension           JSONB NOT NULL DEFAULT '{}'::jsonb, -- masterplan/council_plan/audit_plan
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sylion_v2.project
    ADD CONSTRAINT project_customer_fk
    FOREIGN KEY (customer_id)
    REFERENCES sylion_v2.customer(id)
    ON DELETE SET NULL;

ALTER TABLE sylion_v2.project
    ADD CONSTRAINT project_parent_idea_fk
    FOREIGN KEY (parent_idea_id)
    REFERENCES sylion_v2.idea(id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS project_title_btree ON sylion_v2.project (title);
CREATE INDEX IF NOT EXISTS project_status_btree ON sylion_v2.project (status);
CREATE INDEX IF NOT EXISTS project_owner_id_btree ON sylion_v2.project (owner_id);
CREATE INDEX IF NOT EXISTS project_deadline_btree ON sylion_v2.project (deadline);
CREATE INDEX IF NOT EXISTS project_title_trgm ON sylion_v2.project USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS project_idea_trgm ON sylion_v2.project USING GIN (idea gin_trgm_ops);

CREATE TRIGGER project_updated_at
BEFORE UPDATE ON sylion_v2.project
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER project_audit_lineage
AFTER INSERT OR UPDATE OF title, status, owner_id, deadline, budget_usd ON sylion_v2.project
FOR EACH ROW EXECUTE FUNCTION sylion_v2.emit_object_lineage();
```

## `idea.yaml`

```sql
-- Generated from idea.yaml (W15 schema compiler)
CREATE TABLE IF NOT EXISTS sylion_v2.idea (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    author              TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN (
                                'draft',
                                'clarification',
                                'submitted',
                                'council_review',
                                'approved',
                                'rejected',
                                'implemented',
                                'archived'
                            )),
    priority            INTEGER NOT NULL DEFAULT 3,
    category            TEXT NULL,
    domain              TEXT NULL,
    tags                TEXT NULL, -- searchable text representation of tags
    extension           JSONB NOT NULL DEFAULT '{}'::jsonb, -- clarification_notes/human_gate_decision/attachments
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idea_title_btree ON sylion_v2.idea (title);
CREATE INDEX IF NOT EXISTS idea_author_btree ON sylion_v2.idea (author);
CREATE INDEX IF NOT EXISTS idea_status_btree ON sylion_v2.idea (status);
CREATE INDEX IF NOT EXISTS idea_priority_btree ON sylion_v2.idea (priority);
CREATE INDEX IF NOT EXISTS idea_category_btree ON sylion_v2.idea (category);
CREATE INDEX IF NOT EXISTS idea_domain_btree ON sylion_v2.idea (domain);
CREATE INDEX IF NOT EXISTS idea_title_trgm ON sylion_v2.idea USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idea_description_trgm ON sylion_v2.idea USING GIN (description gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idea_tags_trgm ON sylion_v2.idea USING GIN (tags gin_trgm_ops);

CREATE TRIGGER idea_updated_at
BEFORE UPDATE ON sylion_v2.idea
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER idea_audit_lineage
AFTER INSERT OR UPDATE OF title, status, priority, category, domain ON sylion_v2.idea
FOR EACH ROW EXECUTE FUNCTION sylion_v2.emit_object_lineage();
```
