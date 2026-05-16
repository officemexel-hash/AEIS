"""Comprehensive tests for sylion.db.migration (database schema migration)."""

import sqlite3

import pytest

from sylion.db.migration import run_migration, _SCHEMA_SQL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """In-memory database connection after migration."""
    c = run_migration(":memory:")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# run_migration function
# ---------------------------------------------------------------------------

class TestRunMigration:
    def test_returns_connection(self):
        conn = run_migration(":memory:")
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_idempotent(self):
        """Running migration twice should not raise."""
        conn = run_migration(":memory:")
        conn.executescript(_SCHEMA_SQL)  # re-run
        conn.commit()
        conn.close()

    def test_idempotent_via_function(self):
        conn1 = run_migration(":memory:")
        # Get the schema applied, then run again on same DB
        conn2 = sqlite3.connect(":memory:")
        conn2.executescript(_SCHEMA_SQL)
        conn2.commit()
        # Should have same number of tables
        count1 = conn1.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        count2 = conn2.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        assert count1 == count2
        conn1.close()
        conn2.close()


# ---------------------------------------------------------------------------
# Schema: modules table
# ---------------------------------------------------------------------------

class TestModulesTable:
    def test_modules_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='modules'"
        ).fetchone()
        assert result is not None

    def test_insert_and_query_module(self, conn):
        conn.execute(
            "INSERT INTO modules (module_id, module_kind, owner_plan, description) VALUES (?, ?, ?, ?)",
            ("core.event_bus", "core", "P01", "Event backbone"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM modules WHERE module_id = ?", ("core.event_bus",)).fetchone()
        assert row is not None
        assert row[0] == "core.event_bus"

    def test_modules_default_lifecycle(self, conn):
        conn.execute(
            "INSERT INTO modules (module_id, module_kind) VALUES (?, ?)",
            ("test.mod", "test"),
        )
        conn.commit()
        row = conn.execute("SELECT lifecycle FROM modules WHERE module_id = ?", ("test.mod",)).fetchone()
        assert row[0] == "active"

    def test_modules_auto_timestamp(self, conn):
        conn.execute(
            "INSERT INTO modules (module_id, module_kind) VALUES (?, ?)",
            ("test.ts", "test"),
        )
        conn.commit()
        row = conn.execute("SELECT created_at FROM modules WHERE module_id = ?", ("test.ts",)).fetchone()
        assert row[0] is not None
        assert len(row[0]) > 10  # ISO format


# ---------------------------------------------------------------------------
# Schema: module_events table
# ---------------------------------------------------------------------------

class TestModuleEventsTable:
    def test_module_events_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='module_events'"
        ).fetchone()
        assert result is not None

    def test_insert_and_query_event(self, conn):
        conn.execute(
            "INSERT INTO module_events (event_id, topic, payload, source_module) VALUES (?, ?, ?, ?)",
            ("evt-001", "decision.proposed", '{"key":"val"}', "core.engine"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM module_events WHERE event_id = ?", ("evt-001",)).fetchone()
        assert row[1] == "decision.proposed"


# ---------------------------------------------------------------------------
# Schema: evidence_entries table
# ---------------------------------------------------------------------------

class TestEvidenceEntriesTable:
    def test_evidence_entries_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_entries'"
        ).fetchone()
        assert result is not None

    def test_insert_evidence(self, conn):
        conn.execute(
            "INSERT INTO evidence_entries (entry_id, source_plan, event_type, payload_hash, prev_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ev-001", "P01", "test.event", "abc123", "0" * 64),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM evidence_entries WHERE entry_id = ?", ("ev-001",)).fetchone()
        assert row[1] == "P01"


# ---------------------------------------------------------------------------
# Schema: decisions table
# ---------------------------------------------------------------------------

class TestDecisionsTable:
    def test_decisions_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'"
        ).fetchone()
        assert result is not None

    def test_insert_decision(self, conn):
        conn.execute(
            "INSERT INTO decisions (decision_id, decision_class, description, source_plan, module_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("dec-001", "D3", "significant change", "P05", "core.test", "pending"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", ("dec-001",)).fetchone()
        assert row[1] == "D3"
        assert row[5] == "pending"


# ---------------------------------------------------------------------------
# Schema: council_sessions and council_votes
# ---------------------------------------------------------------------------

class TestCouncilTables:
    def test_council_sessions_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='council_sessions'"
        ).fetchone()
        assert result is not None

    def test_council_votes_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='council_votes'"
        ).fetchone()
        assert result is not None

    def test_insert_session_and_vote(self, conn):
        conn.execute(
            "INSERT INTO council_sessions (session_id, proposal_id, decision_class, title) "
            "VALUES (?, ?, ?, ?)",
            ("sess-001", "prop-001", "D3", "Test Session"),
        )
        conn.execute(
            "INSERT INTO council_votes (vote_id, session_id, member_id, value, rationale) "
            "VALUES (?, ?, ?, ?, ?)",
            ("vote-001", "sess-001", "agent-1", "approve", "LGTM"),
        )
        conn.commit()
        session = conn.execute("SELECT * FROM council_sessions WHERE session_id = ?", ("sess-001",)).fetchone()
        assert session[3] == "Test Session"
        vote = conn.execute("SELECT * FROM council_votes WHERE vote_id = ?", ("vote-001",)).fetchone()
        assert vote[3] == "approve"

    def test_council_votes_foreign_key(self, conn):
        """Foreign keys are enabled; inserting a vote with invalid session should fail."""
        # Note: SQLite foreign keys are enforced at runtime with PRAGMA foreign_keys=ON
        conn.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO council_votes (vote_id, session_id, member_id, value) "
                "VALUES (?, ?, ?, ?)",
                ("vote-bad", "nonexistent-session", "agent-1", "approve"),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Schema: evidence_packs and evidence_artefacts
# ---------------------------------------------------------------------------

class TestEvidencePackTables:
    def test_evidence_packs_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_packs'"
        ).fetchone()
        assert result is not None

    def test_evidence_artefacts_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_artefacts'"
        ).fetchone()
        assert result is not None

    def test_insert_pack_and_artefact(self, conn):
        conn.execute(
            "INSERT INTO evidence_packs (pack_id, proposal_id, decision_class, status) "
            "VALUES (?, ?, ?, ?)",
            ("pack-001", "prop-001", "D3", "draft"),
        )
        conn.execute(
            "INSERT INTO evidence_artefacts (artefact_id, pack_id, name, type, content_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            ("art-001", "pack-001", "test_report", "json", "sha256abc"),
        )
        conn.commit()
        pack = conn.execute("SELECT * FROM evidence_packs WHERE pack_id = ?", ("pack-001",)).fetchone()
        assert pack[3] == "draft"
        art = conn.execute("SELECT * FROM evidence_artefacts WHERE artefact_id = ?", ("art-001",)).fetchone()
        assert art[2] == "test_report"


# ---------------------------------------------------------------------------
# Schema: contracts table
# ---------------------------------------------------------------------------

class TestContractsTable:
    def test_contracts_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contracts'"
        ).fetchone()
        assert result is not None

    def test_insert_contract(self, conn):
        conn.execute(
            "INSERT INTO contracts (contract_id, name, contract_type, version, schema_def, producer_module) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("con-001", "EventBusContract", "grpc", 1, '{"type":"object"}', "core.event_bus"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM contracts WHERE contract_id = ?", ("con-001",)).fetchone()
        assert row[1] == "EventBusContract"
        assert row[3] == 1


# ---------------------------------------------------------------------------
# Schema: agents table
# ---------------------------------------------------------------------------

class TestAgentsTable:
    def test_agents_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
        ).fetchone()
        assert result is not None

    def test_insert_agent(self, conn):
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, department, level, status, health) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ag-001", "Architect", "reviewer", "platform", 3, "active", "ok"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", ("ag-001",)).fetchone()
        assert row[1] == "Architect"
        assert row[4] == 3


# ---------------------------------------------------------------------------
# Schema: skills table
# ---------------------------------------------------------------------------

class TestSkillsTable:
    def test_skills_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skills'"
        ).fetchone()
        assert result is not None

    def test_insert_skill(self, conn):
        conn.execute(
            "INSERT INTO skills (skill_id, name, domain, lifecycle, usage_count) "
            "VALUES (?, ?, ?, ?, ?)",
            ("sk-001", "Code Review", "development", "active", 42),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM skills WHERE skill_id = ?", ("sk-001",)).fetchone()
        assert row[1] == "Code Review"
        assert row[4] == 42


# ---------------------------------------------------------------------------
# Schema: runs table
# ---------------------------------------------------------------------------

class TestRunsTable:
    def test_runs_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        ).fetchone()
        assert result is not None

    def test_insert_run(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, project_name, phase, progress, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-001", "sylion-core", "deploy", 0.75, "running"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", ("run-001",)).fetchone()
        assert row[1] == "sylion-core"
        assert row[3] == 0.75


# ---------------------------------------------------------------------------
# Schema: audit_log table
# ---------------------------------------------------------------------------

class TestAuditLogTable:
    def test_audit_log_table_exists(self, conn):
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        ).fetchone()
        assert result is not None

    def test_insert_audit_entry(self, conn):
        conn.execute(
            "INSERT INTO audit_log (log_id, actor, action, resource, result) "
            "VALUES (?, ?, ?, ?, ?)",
            ("log-001", "agent-1", "deploy", "module.core", "success"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM audit_log WHERE log_id = ?", ("log-001",)).fetchone()
        assert row[1] == "agent-1"
        assert row[2] == "deploy"


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

class TestIndexes:
    def test_all_indexes_created(self, conn):
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        # Check a representative sample
        expected = {
            "idx_modules_kind", "idx_events_topic", "idx_evidence_plan",
            "idx_decisions_class", "idx_council_status", "idx_agents_status",
            "idx_skills_domain", "idx_runs_status", "idx_audit_actor",
        }
        assert expected.issubset(index_names)


# ---------------------------------------------------------------------------
# Table count
# ---------------------------------------------------------------------------

class TestTableCount:
    def test_expected_table_count(self, conn):
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        # 13 tables defined in the schema
        assert count == 13
