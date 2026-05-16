"""
Tests for KnowledgeDistiller -- CRUD, search, linking, distillation jobs,
stats, singleton, thread safety.
"""

from __future__ import annotations

import json
import time
import threading

import pytest

from sylion.cognitive.knowledge_distiller import (
    KnowledgeDistiller,
    get_knowledge_distiller,
    reset_knowledge_distiller,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_knowledge_distiller()
    yield
    reset_knowledge_distiller()


@pytest.fixture
def kd() -> KnowledgeDistiller:
    """Fresh in-memory KnowledgeDistiller instance."""
    return KnowledgeDistiller()


@pytest.fixture
def bus():
    """Fresh in-memory EventBus that captures published events."""
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def kd_bus(bus) -> KnowledgeDistiller:
    """KnowledgeDistiller with EventBus attached."""
    return KnowledgeDistiller(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_entry(kd, title="Test entry", content="Test content", entry_type="pattern",
               domain=None, source_type="manual", **kwargs):
    """Shorthand to add a knowledge entry."""
    return kd.add_entry(
        title=title,
        content=content,
        entry_type=entry_type,
        domain=domain,
        source_type=source_type,
        **kwargs,
    )


# ===========================================================================
# TestAddEntry
# ===========================================================================

class TestAddEntry:

    def test_returns_entry_id(self, kd):
        result = _add_entry(kd)
        assert "entry_id" in result
        assert isinstance(result["entry_id"], str)
        assert len(result["entry_id"]) == 12

    def test_stores_title_and_content(self, kd):
        result = _add_entry(kd, title="My Title", content="My Content")
        assert result["title"] == "My Title"
        assert result["content"] == "My Content"

    def test_entry_type_stored(self, kd):
        result = _add_entry(kd, entry_type="lesson")
        assert result["entry_type"] == "lesson"

    def test_domain_stored(self, kd):
        result = _add_entry(kd, domain="security")
        assert result["domain"] == "security"

    def test_domain_none_by_default(self, kd):
        result = _add_entry(kd)
        assert result["domain"] is None

    def test_source_type_manual_default(self, kd):
        result = _add_entry(kd)
        assert result["source_type"] == "manual"

    def test_source_ids_stored(self, kd):
        result = _add_entry(kd, source_ids=["DEC-001", "DEC-002"])
        assert result["source_ids"] == ["DEC-001", "DEC-002"]

    def test_confidence_default(self, kd):
        result = _add_entry(kd)
        assert result["confidence"] == 0.5

    def test_custom_confidence(self, kd):
        result = _add_entry(kd, confidence=0.9)
        assert result["confidence"] == 0.9

    def test_applicability_default(self, kd):
        result = _add_entry(kd)
        assert result["applicability"] == "broad"

    def test_tags_stored(self, kd):
        result = _add_entry(kd, tags=["arch", "perf"])
        assert result["tags"] == ["arch", "perf"]

    def test_empty_tags_default(self, kd):
        result = _add_entry(kd)
        assert result["tags"] == []

    def test_times_applied_zero(self, kd):
        result = _add_entry(kd)
        assert result["times_applied"] == 0

    def test_times_validated_zero(self, kd):
        result = _add_entry(kd)
        assert result["times_validated"] == 0

    def test_created_at_present(self, kd):
        result = _add_entry(kd)
        assert result["created_at"] > 0
        assert result["updated_at"] > 0

    def test_related_entries_empty(self, kd):
        result = _add_entry(kd)
        assert result["related_entries"] == []

    def test_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        _add_entry(kd, title="Event test")
        assert len(bus._captured) == 1
        assert bus._captured[0].topic == "knowledge.entry.added"


# ===========================================================================
# TestUpdateEntry
# ===========================================================================

class TestUpdateEntry:

    def test_update_title(self, kd):
        e = _add_entry(kd, title="Old")
        result = kd.update_entry(e["entry_id"], title="New")
        assert result["title"] == "New"

    def test_update_content(self, kd):
        e = _add_entry(kd, content="Old content")
        result = kd.update_entry(e["entry_id"], content="New content")
        assert result["content"] == "New content"

    def test_update_confidence(self, kd):
        e = _add_entry(kd, confidence=0.5)
        result = kd.update_entry(e["entry_id"], confidence=0.9)
        assert result["confidence"] == 0.9

    def test_update_tags(self, kd):
        e = _add_entry(kd, tags=["old"])
        result = kd.update_entry(e["entry_id"], tags=["new", "tags"])
        assert result["tags"] == ["new", "tags"]

    def test_update_multiple_fields(self, kd):
        e = _add_entry(kd, title="A", content="B")
        result = kd.update_entry(e["entry_id"], title="C", content="D", confidence=0.8)
        assert result["title"] == "C"
        assert result["content"] == "D"
        assert result["confidence"] == 0.8

    def test_update_nonexistent_returns_none(self, kd):
        result = kd.update_entry("nonexistent", title="x")
        assert result is None

    def test_update_nothing_returns_existing(self, kd):
        e = _add_entry(kd, title="Keep")
        result = kd.update_entry(e["entry_id"])
        assert result["title"] == "Keep"

    def test_updated_at_changes(self, kd):
        e = _add_entry(kd)
        old_updated = e["updated_at"]
        time.sleep(0.01)
        result = kd.update_entry(e["entry_id"], title="Changed")
        assert result["updated_at"] >= old_updated


# ===========================================================================
# TestGetEntry
# ===========================================================================

class TestGetEntry:

    def test_get_existing(self, kd):
        e = _add_entry(kd, title="Fetch me")
        result = kd.get_entry(e["entry_id"])
        assert result is not None
        assert result["title"] == "Fetch me"

    def test_get_nonexistent(self, kd):
        assert kd.get_entry("nonexistent") is None

    def test_json_fields_parsed(self, kd):
        e = _add_entry(kd, source_ids=["A", "B"], tags=["t1", "t2"])
        result = kd.get_entry(e["entry_id"])
        assert result["source_ids"] == ["A", "B"]
        assert result["tags"] == ["t1", "t2"]


# ===========================================================================
# TestSearchEntries
# ===========================================================================

class TestSearchEntries:

    def test_search_by_title(self, kd):
        _add_entry(kd, title="Security pattern for auth")
        _add_entry(kd, title="Performance tip")
        results = kd.search_entries("Security")
        assert len(results) == 1
        assert "Security" in results[0]["title"]

    def test_search_by_content(self, kd):
        _add_entry(kd, title="Entry A", content="This is about database optimization")
        _add_entry(kd, title="Entry B", content="This is about caching")
        results = kd.search_entries("database")
        assert len(results) == 1
        assert "database" in results[0]["content"]

    def test_search_case_insensitive(self, kd):
        _add_entry(kd, title="UPPERCASE Title")
        results = kd.search_entries("uppercase")
        assert len(results) == 1

    def test_search_with_type_filter(self, kd):
        _add_entry(kd, title="Pattern X", entry_type="pattern")
        _add_entry(kd, title="Lesson X", entry_type="lesson")
        results = kd.search_entries("X", entry_type="pattern")
        assert len(results) == 1
        assert results[0]["entry_type"] == "pattern"

    def test_search_with_domain_filter(self, kd):
        _add_entry(kd, title="Sec entry", domain="security")
        _add_entry(kd, title="Perf entry", domain="performance")
        results = kd.search_entries("entry", domain="security")
        assert len(results) == 1
        assert results[0]["domain"] == "security"

    def test_search_limit(self, kd):
        for i in range(10):
            _add_entry(kd, title=f"Searchable {i}")
        results = kd.search_entries("Searchable", limit=3)
        assert len(results) == 3

    def test_search_no_results(self, kd):
        results = kd.search_entries("zzz_nonexistent_zzz")
        assert results == []


# ===========================================================================
# TestListEntries
# ===========================================================================

class TestListEntries:

    def test_list_all(self, kd):
        _add_entry(kd, title="A")
        _add_entry(kd, title="B")
        _add_entry(kd, title="C")
        assert len(kd.list_entries()) == 3

    def test_filter_by_type(self, kd):
        _add_entry(kd, entry_type="pattern")
        _add_entry(kd, entry_type="lesson")
        results = kd.list_entries(entry_type="pattern")
        assert len(results) == 1
        assert results[0]["entry_type"] == "pattern"

    def test_filter_by_domain(self, kd):
        _add_entry(kd, domain="security")
        _add_entry(kd, domain="performance")
        results = kd.list_entries(domain="security")
        assert len(results) == 1

    def test_filter_by_confidence_min(self, kd):
        _add_entry(kd, confidence=0.3, title="Low")
        _add_entry(kd, confidence=0.9, title="High")
        results = kd.list_entries(confidence_min=0.8)
        assert len(results) == 1
        assert results[0]["title"] == "High"

    def test_combined_filters(self, kd):
        _add_entry(kd, entry_type="pattern", domain="security", confidence=0.9, title="Match")
        _add_entry(kd, entry_type="pattern", domain="security", confidence=0.2, title="Low conf")
        _add_entry(kd, entry_type="lesson", domain="security", confidence=0.9, title="Wrong type")
        results = kd.list_entries(entry_type="pattern", domain="security", confidence_min=0.8)
        assert len(results) == 1
        assert results[0]["title"] == "Match"

    def test_limit_respected(self, kd):
        for i in range(10):
            _add_entry(kd, title=f"E{i}")
        assert len(kd.list_entries(limit=3)) == 3


# ===========================================================================
# TestValidateEntry
# ===========================================================================

class TestValidateEntry:

    def test_increments_validated(self, kd):
        e = _add_entry(kd)
        result = kd.validate_entry(e["entry_id"])
        assert result["times_validated"] == 1

    def test_multiple_validations(self, kd):
        e = _add_entry(kd)
        kd.validate_entry(e["entry_id"])
        kd.validate_entry(e["entry_id"])
        result = kd.validate_entry(e["entry_id"])
        assert result["times_validated"] == 3

    def test_nonexistent_returns_none(self, kd):
        assert kd.validate_entry("nonexistent") is None

    def test_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        kd.validate_entry(e["entry_id"])
        topics = [ev.topic for ev in bus._captured]
        assert "knowledge.entry.validated" in topics


# ===========================================================================
# TestApplyEntry
# ===========================================================================

class TestApplyEntry:

    def test_increments_applied(self, kd):
        e = _add_entry(kd)
        result = kd.apply_entry(e["entry_id"])
        assert result["times_applied"] == 1

    def test_multiple_applies(self, kd):
        e = _add_entry(kd)
        kd.apply_entry(e["entry_id"])
        kd.apply_entry(e["entry_id"])
        result = kd.apply_entry(e["entry_id"])
        assert result["times_applied"] == 3

    def test_nonexistent_returns_none(self, kd):
        assert kd.apply_entry("nonexistent") is None

    def test_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        kd.apply_entry(e["entry_id"])
        topics = [ev.topic for ev in bus._captured]
        assert "knowledge.entry.applied" in topics


# ===========================================================================
# TestGetRelated
# ===========================================================================

class TestGetRelated:

    def test_no_related_initially(self, kd):
        e = _add_entry(kd)
        related = kd.get_related(e["entry_id"])
        assert related == []

    def test_related_after_linking(self, kd):
        e1 = _add_entry(kd, title="First")
        e2 = _add_entry(kd, title="Second")
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        related = kd.get_related(e1["entry_id"])
        assert len(related) == 1
        assert related[0]["entry_id"] == e2["entry_id"]

    def test_related_nonexistent(self, kd):
        assert kd.get_related("nonexistent") == []

    def test_bidirectional_related(self, kd):
        e1 = _add_entry(kd, title="A")
        e2 = _add_entry(kd, title="B")
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        related_to_e2 = kd.get_related(e2["entry_id"])
        assert len(related_to_e2) == 1
        assert related_to_e2[0]["entry_id"] == e1["entry_id"]


# ===========================================================================
# TestLinkEntries
# ===========================================================================

class TestLinkEntries:

    def test_bidirectional_link(self, kd):
        e1 = _add_entry(kd)
        e2 = _add_entry(kd)
        assert kd.link_entries(e1["entry_id"], e2["entry_id"]) is True
        r1 = kd.get_entry(e1["entry_id"])
        r2 = kd.get_entry(e2["entry_id"])
        assert e2["entry_id"] in r1["related_entries"]
        assert e1["entry_id"] in r2["related_entries"]

    def test_link_nonexistent_first(self, kd):
        e2 = _add_entry(kd)
        assert kd.link_entries("nonexistent", e2["entry_id"]) is False

    def test_link_nonexistent_second(self, kd):
        e1 = _add_entry(kd)
        assert kd.link_entries(e1["entry_id"], "nonexistent") is False

    def test_link_idempotent(self, kd):
        e1 = _add_entry(kd)
        e2 = _add_entry(kd)
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        r1 = kd.get_entry(e1["entry_id"])
        assert r1["related_entries"].count(e2["entry_id"]) == 1

    def test_link_three_entries(self, kd):
        e1 = _add_entry(kd)
        e2 = _add_entry(kd)
        e3 = _add_entry(kd)
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        kd.link_entries(e1["entry_id"], e3["entry_id"])
        r1 = kd.get_entry(e1["entry_id"])
        assert len(r1["related_entries"]) == 2

    def test_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e1 = _add_entry(kd)
        e2 = _add_entry(kd)
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        topics = [ev.topic for ev in bus._captured]
        assert "knowledge.entries.linked" in topics


# ===========================================================================
# TestDistillFromDecisions
# ===========================================================================

class TestDistillFromDecisions:

    def _ensure_decision_tables(self, kd):
        """Create decision_snapshots table in KD's DB if not present."""
        with kd._lock:
            kd._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id       TEXT PRIMARY KEY,
                    decision_id       TEXT NOT NULL,
                    decision_class    TEXT NOT NULL DEFAULT 'D0',
                    module_states     TEXT NOT NULL DEFAULT '{}',
                    choice_made       TEXT,
                    is_active         INTEGER DEFAULT 1,
                    superseded_by     TEXT,
                    created_at        REAL NOT NULL
                )
            """)
            kd._conn.commit()

    def _seed_decisions(self, kd, count=5, decision_class="D0", **overrides):
        """Insert mock decision snapshots directly into the DB."""
        self._ensure_decision_tables(kd)
        now = time.time()
        with kd._lock:
            for i in range(count):
                snap_id = f"snap_{i:04d}"
                states = overrides.get("module_states", json.dumps({"mod_core": {"status": "active"}}))
                kd._conn.execute("""
                    INSERT OR REPLACE INTO decision_snapshots
                    (snapshot_id, decision_id, decision_class, module_states,
                     choice_made, is_active, superseded_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snap_id,
                    overrides.get("decision_id", f"DEC-{i:04d}"),
                    decision_class,
                    states,
                    overrides.get("choice_made", "approved"),
                    overrides.get("is_active", 1),
                    overrides.get("superseded_by"),
                    now - (count - i),
                ))
            kd._conn.commit()

    def test_returns_empty_on_no_data(self, kd):
        result = kd.distill_from_decisions()
        assert result == []

    def test_detects_repeated_decision_class(self, kd):
        self._seed_decisions(kd, count=5, decision_class="D2")
        entries = kd.distill_from_decisions()
        assert len(entries) >= 1
        pattern_entries = [e for e in entries if e["entry_type"] == "pattern"]
        assert len(pattern_entries) >= 1
        assert "D2" in pattern_entries[0]["title"]

    def test_detects_module_overlap(self, kd):
        states = json.dumps({"shared_module": {"status": "active"}})
        self._seed_decisions(kd, count=5, module_states=states)
        entries = kd.distill_from_decisions()
        heuristic_entries = [e for e in entries if e["entry_type"] == "heuristic"]
        assert len(heuristic_entries) >= 1
        assert "shared_module" in heuristic_entries[0]["content"]

    def test_detects_superseded_lessons(self, kd):
        self._seed_decisions(kd, count=3, superseded_by="snap_new")
        entries = kd.distill_from_decisions()
        lesson_entries = [e for e in entries if e["entry_type"] == "lesson"]
        assert len(lesson_entries) >= 1

    def test_detects_stable_best_practices(self, kd):
        self._seed_decisions(kd, count=6, is_active=1, superseded_by=None)
        entries = kd.distill_from_decisions()
        bp_entries = [e for e in entries if e["entry_type"] == "best_practice"]
        assert len(bp_entries) >= 1

    def test_time_filter_from(self, kd):
        self._seed_decisions(kd, count=3)
        future = time.time() + 10000
        entries = kd.distill_from_decisions(from_time=future)
        assert entries == []

    def test_source_type_is_decision_analysis(self, kd):
        self._seed_decisions(kd, count=5, decision_class="D1")
        entries = kd.distill_from_decisions()
        for e in entries:
            assert e["source_type"] == "decision_analysis"


# ===========================================================================
# TestDistillFromPipeline
# ===========================================================================

class TestDistillFromPipeline:

    def _ensure_pipeline_tables(self, kd):
        """Create pipeline tables in KD's DB if not present."""
        with kd._lock:
            kd._conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_run_states (
                    run_id             TEXT PRIMARY KEY,
                    current_state      TEXT NOT NULL DEFAULT 'idle',
                    previous_state     TEXT,
                    paused_from        TEXT,
                    state_entered_at   REAL NOT NULL,
                    total_revisions    INTEGER DEFAULT 0,
                    cancelled          INTEGER DEFAULT 0,
                    cancellation_reason TEXT,
                    updated_at         REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_state_log (
                    log_id       TEXT PRIMARY KEY,
                    run_id       TEXT NOT NULL,
                    from_state   TEXT NOT NULL,
                    to_state     TEXT NOT NULL,
                    trigger      TEXT NOT NULL,
                    snapshot_id  TEXT,
                    gate_id      TEXT,
                    decision_id  TEXT,
                    metadata     TEXT,
                    created_at   REAL NOT NULL
                );
            """)
            kd._conn.commit()

    def _seed_pipeline(self, kd, runs, logs=None):
        """Insert mock pipeline run states and logs directly."""
        self._ensure_pipeline_tables(kd)
        now = time.time()
        with kd._lock:
            for r in runs:
                kd._conn.execute("""
                    INSERT OR REPLACE INTO pipeline_run_states
                    (run_id, current_state, previous_state, paused_from,
                     state_entered_at, total_revisions, cancelled,
                     cancellation_reason, updated_at)
                    VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?)
                """, (
                    r["run_id"],
                    r.get("current_state", "complete"),
                    r.get("previous_state", "reviewing"),
                    r.get("state_entered_at", now),
                    r.get("total_revisions", 0),
                    r.get("cancelled", 0),
                    r.get("updated_at", now),
                ))
            if logs:
                for lg in logs:
                    kd._conn.execute("""
                        INSERT OR REPLACE INTO pipeline_state_log
                        (log_id, run_id, from_state, to_state, trigger,
                         snapshot_id, gate_id, decision_id, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?)
                    """, (
                        lg.get("log_id", f"log_{lg['run_id']}"),
                        lg["run_id"],
                        lg.get("from_state", "reviewing"),
                        lg.get("to_state", "complete"),
                        lg.get("trigger", "auto"),
                        lg.get("created_at", now),
                    ))
            kd._conn.commit()

    def test_empty_pipeline_data(self, kd):
        result = kd.distill_from_pipeline()
        assert result == []

    def test_high_success_rate(self, kd):
        runs = [{"run_id": f"run_{i}", "current_state": "complete"} for i in range(5)]
        self._seed_pipeline(kd, runs)
        entries = kd.distill_from_pipeline()
        bp = [e for e in entries if e["entry_type"] == "best_practice"]
        assert len(bp) >= 1
        assert "success rate" in bp[0]["title"].lower()

    def test_high_cancellation_rate(self, kd):
        runs = [{"run_id": f"run_{i}", "current_state": "cancelled"} for i in range(4)]
        runs.append({"run_id": "run_4", "current_state": "complete"})
        self._seed_pipeline(kd, runs)
        entries = kd.distill_from_pipeline()
        ap = [e for e in entries if e["entry_type"] == "anti_pattern"]
        assert len(ap) >= 1
        assert "cancellation" in ap[0]["title"].lower()

    def test_revision_loops(self, kd):
        runs = [
            {"run_id": f"run_{i}", "current_state": "complete", "total_revisions": 4}
            for i in range(3)
        ]
        self._seed_pipeline(kd, runs)
        entries = kd.distill_from_pipeline()
        ap = [e for e in entries if "revision" in e["title"].lower()]
        assert len(ap) >= 1

    def test_decision_change_rollbacks(self, kd):
        runs = [{"run_id": f"run_{i}", "current_state": "complete"} for i in range(3)]
        logs = [
            {"run_id": f"run_{i}", "trigger": "decision_change", "to_state": "planning",
             "log_id": f"log_{i}"}
            for i in range(3)
        ]
        self._seed_pipeline(kd, runs, logs)
        entries = kd.distill_from_pipeline()
        lesson_entries = [e for e in entries if "rollback" in e["title"].lower()]
        assert len(lesson_entries) >= 1

    def test_clean_completions(self, kd):
        runs = [
            {"run_id": f"run_{i}", "current_state": "complete", "total_revisions": 0}
            for i in range(4)
        ]
        self._seed_pipeline(kd, runs)
        entries = kd.distill_from_pipeline()
        heuristics = [e for e in entries if "clean" in e["title"].lower()]
        assert len(heuristics) >= 1

    def test_source_type_is_pipeline(self, kd):
        runs = [{"run_id": f"run_{i}", "current_state": "complete"} for i in range(5)]
        self._seed_pipeline(kd, runs)
        entries = kd.distill_from_pipeline()
        for e in entries:
            assert e["source_type"] == "pipeline_execution"


# ===========================================================================
# TestRunDistillation
# ===========================================================================

class TestRunDistillation:

    def test_returns_job_record(self, kd):
        result = kd.run_distillation()
        assert "job_id" in result
        assert result["status"] == "completed"

    def test_entries_extracted_count(self, kd):
        # Seed some decisions to extract from
        now = time.time()
        with kd._lock:
            kd._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id       TEXT PRIMARY KEY,
                    decision_id       TEXT NOT NULL,
                    decision_class    TEXT NOT NULL DEFAULT 'D0',
                    module_states     TEXT NOT NULL DEFAULT '{}',
                    choice_made       TEXT,
                    is_active         INTEGER DEFAULT 1,
                    superseded_by     TEXT,
                    created_at        REAL NOT NULL
                )
            """)
            for i in range(5):
                kd._conn.execute("""
                    INSERT OR REPLACE INTO decision_snapshots
                    (snapshot_id, decision_id, decision_class, module_states,
                     choice_made, is_active, superseded_by, created_at)
                    VALUES (?, ?, 'D2', '{"m1":{}}', 'approved', 1, NULL, ?)
                """, (f"snap_d_{i}", f"DEC-{i}", now))
            kd._conn.commit()
        result = kd.run_distillation(source_type="decisions")
        assert result["entries_extracted"] > 0

    def test_job_status_completed(self, kd):
        result = kd.run_distillation()
        assert result["status"] == "completed"

    def test_completed_at_set(self, kd):
        result = kd.run_distillation()
        assert result["completed_at"] is not None
        assert result["completed_at"] > 0

    def test_started_at_set(self, kd):
        result = kd.run_distillation()
        assert result["started_at"] is not None

    def test_source_type_all(self, kd):
        result = kd.run_distillation(source_type="all")
        assert result["source_type"] == "all"

    def test_source_type_decisions_only(self, kd):
        result = kd.run_distillation(source_type="decisions")
        assert result["source_type"] == "decisions"

    def test_source_type_pipeline_only(self, kd):
        result = kd.run_distillation(source_type="pipeline")
        assert result["source_type"] == "pipeline"

    def test_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        kd.run_distillation()
        topics = [ev.topic for ev in bus._captured]
        assert "knowledge.distillation.completed" in topics


# ===========================================================================
# TestGetStats
# ===========================================================================

class TestGetStats:

    def test_empty_stats(self, kd):
        stats = kd.get_stats()
        assert stats["total_entries"] == 0
        assert stats["by_type"] == {}
        assert stats["by_domain"] == {}
        assert stats["avg_confidence"] == 0.0
        assert stats["total_validated"] == 0
        assert stats["total_applied"] == 0

    def test_total_entries(self, kd):
        _add_entry(kd)
        _add_entry(kd)
        _add_entry(kd)
        stats = kd.get_stats()
        assert stats["total_entries"] == 3

    def test_by_type(self, kd):
        _add_entry(kd, entry_type="pattern")
        _add_entry(kd, entry_type="pattern")
        _add_entry(kd, entry_type="lesson")
        stats = kd.get_stats()
        assert stats["by_type"]["pattern"] == 2
        assert stats["by_type"]["lesson"] == 1

    def test_by_domain(self, kd):
        _add_entry(kd, domain="security")
        _add_entry(kd, domain="performance")
        stats = kd.get_stats()
        assert stats["by_domain"]["security"] == 1
        assert stats["by_domain"]["performance"] == 1

    def test_avg_confidence(self, kd):
        _add_entry(kd, confidence=0.4)
        _add_entry(kd, confidence=0.6)
        stats = kd.get_stats()
        assert abs(stats["avg_confidence"] - 0.5) < 0.01

    def test_total_validated(self, kd):
        e = _add_entry(kd)
        kd.validate_entry(e["entry_id"])
        kd.validate_entry(e["entry_id"])
        stats = kd.get_stats()
        assert stats["total_validated"] == 2

    def test_total_applied(self, kd):
        e = _add_entry(kd)
        kd.apply_entry(e["entry_id"])
        stats = kd.get_stats()
        assert stats["total_applied"] == 1

    def test_domain_none_excluded(self, kd):
        _add_entry(kd)  # domain=None
        _add_entry(kd, domain="security")
        stats = kd.get_stats()
        assert None not in stats["by_domain"]
        assert stats["by_domain"]["security"] == 1


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_knowledge_distiller(), KnowledgeDistiller)

    def test_idempotent(self):
        a = get_knowledge_distiller()
        b = get_knowledge_distiller()
        assert a is b

    def test_reset_creates_new(self):
        a = get_knowledge_distiller()
        b = reset_knowledge_distiller()
        assert a is not b
        assert isinstance(b, KnowledgeDistiller)

    def test_reset_then_get(self):
        reset = reset_knowledge_distiller()
        get = get_knowledge_distiller()
        assert reset is get


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_adds(self):
        kd = KnowledgeDistiller()
        results = []
        errors = []

        def add_entry(i):
            try:
                r = _add_entry(kd, title=f"Entry {i}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_entry, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        ids = {r["entry_id"] for r in results}
        assert len(ids) == 20

    def test_concurrent_validate_and_apply(self):
        kd = KnowledgeDistiller()
        e = _add_entry(kd)
        errors = []

        def validate():
            try:
                kd.validate_entry(e["entry_id"])
            except Exception as ex:
                errors.append(ex)

        def apply():
            try:
                kd.apply_entry(e["entry_id"])
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=validate) for _ in range(10)]
        threads += [threading.Thread(target=apply) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        result = kd.get_entry(e["entry_id"])
        assert result["times_validated"] == 10
        assert result["times_applied"] == 10

    def test_concurrent_reads_and_writes(self):
        """Readers and writers operating simultaneously must not crash."""
        kd = KnowledgeDistiller()
        _add_entry(kd, title="Seed")
        errors = []
        barrier = threading.Barrier(6)

        def writer(idx):
            try:
                barrier.wait(timeout=5)
                for j in range(10):
                    _add_entry(kd, title=f"W{idx}-{j}")
            except Exception as exc:
                errors.append(exc)

        def reader():
            try:
                barrier.wait(timeout=5)
                for _ in range(20):
                    kd.list_entries()
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=writer, args=(i,)) for i in range(3)]
            + [threading.Thread(target=reader) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:

    def test_special_characters_in_title_and_content(self, kd):
        result = _add_entry(
            kd,
            title="Quotes 'single' \"double\"",
            content="Line1\nLine2\tTabbed <html> & stuff",
        )
        fetched = kd.get_entry(result["entry_id"])
        assert fetched["title"] == "Quotes 'single' \"double\""
        assert "Line1\nLine2\tTabbed <html> & stuff" in fetched["content"]

    def test_unicode_content(self, kd):
        result = _add_entry(
            kd,
            title="Unicode test",
            content="Japanese: 日本語  Korean: 한글  Emoji: \U0001f680",
        )
        fetched = kd.get_entry(result["entry_id"])
        assert "日本語" in fetched["content"]

    def test_very_long_title(self, kd):
        long_title = "A" * 1000
        result = _add_entry(kd, title=long_title, content="C")
        fetched = kd.get_entry(result["entry_id"])
        assert len(fetched["title"]) == 1000

    def test_very_long_content(self, kd):
        long_content = "X" * 10000
        result = _add_entry(kd, title="T", content=long_content)
        fetched = kd.get_entry(result["entry_id"])
        assert len(fetched["content"]) == 10000

    def test_empty_tags_list(self, kd):
        result = _add_entry(kd, tags=[])
        assert result["tags"] == []

    def test_empty_source_ids_list(self, kd):
        result = _add_entry(kd, source_ids=[])
        assert result["source_ids"] == []

    def test_many_tags(self, kd):
        many_tags = [f"tag_{i}" for i in range(50)]
        result = _add_entry(kd, tags=many_tags)
        assert result["tags"] == many_tags

    def test_many_source_ids(self, kd):
        ids = [f"src_{i}" for i in range(30)]
        result = _add_entry(kd, source_ids=ids)
        assert result["source_ids"] == ids

    def test_confidence_boundary_zero(self, kd):
        result = _add_entry(kd, confidence=0.0)
        assert result["confidence"] == 0.0

    def test_confidence_boundary_one(self, kd):
        result = _add_entry(kd, confidence=1.0)
        assert result["confidence"] == 1.0

    def test_self_linking(self, kd):
        """Linking an entry to itself should not crash."""
        e = _add_entry(kd)
        result = kd.link_entries(e["entry_id"], e["entry_id"])
        assert result is True
        fetched = kd.get_entry(e["entry_id"])
        assert fetched["related_entries"].count(e["entry_id"]) == 1

    def test_empty_search_matches_all(self, kd):
        _add_entry(kd, title="Hello", content="World")
        results = kd.search_entries("")
        assert len(results) == 1

    def test_search_orders_by_confidence_desc(self, kd):
        _add_entry(kd, title="Low", content="shared keyword", confidence=0.2)
        _add_entry(kd, title="High", content="shared keyword", confidence=0.9)
        results = kd.search_entries("shared keyword")
        assert results[0]["confidence"] > results[1]["confidence"]

    def test_no_event_bus_does_not_crash(self):
        kd = KnowledgeDistiller(db_path=":memory:", event_bus=None)
        result = _add_entry(kd)
        assert result is not None
        kd.validate_entry(result["entry_id"])
        kd.apply_entry(result["entry_id"])

    def test_malformed_json_in_tags(self, kd):
        """_parse_row should gracefully handle malformed JSON in tags."""
        with kd._lock:
            kd._conn.execute(
                "INSERT INTO knowledge_entries "
                "(entry_id, title, content, entry_type, source_type, "
                "source_ids, tags, related_entries, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("mal1", "T", "C", "pattern", "manual",
                 "not-json", "also-not-json", "[]",
                 time.time(), time.time()),
            )
            kd._conn.commit()
        result = kd.get_entry("mal1")
        assert result is not None
        assert result["title"] == "T"
        # Malformed JSON stays as string
        assert isinstance(result["tags"], str)

    def test_malformed_json_in_source_ids(self, kd):
        """_parse_row handles malformed JSON in source_ids."""
        with kd._lock:
            kd._conn.execute(
                "INSERT INTO knowledge_entries "
                "(entry_id, title, content, entry_type, source_type, "
                "source_ids, tags, related_entries, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("mal2", "T", "C", "pattern", "manual",
                 "{broken", "[]", "[]",
                 time.time(), time.time()),
            )
            kd._conn.commit()
        result = kd.get_entry("mal2")
        assert result is not None
        assert isinstance(result["source_ids"], str)

    def test_multiple_distillation_jobs_unique_ids(self, kd):
        j1 = kd.run_distillation(source_type="all")
        j2 = kd.run_distillation(source_type="all")
        assert j1["job_id"] != j2["job_id"]

    def test_run_distillation_council_noop(self, kd):
        """Council source type is a placeholder -- should complete with 0 entries."""
        result = kd.run_distillation(source_type="council")
        assert result["status"] == "completed"
        assert result["entries_extracted"] == 0

    def test_db_schema_idempotent_double_create(self):
        """Creating two distillers should not fail on schema creation."""
        d1 = KnowledgeDistiller(db_path=":memory:")
        d2 = KnowledgeDistiller(db_path=":memory:")
        d1.add_entry(title="T1", content="C", entry_type="pattern")
        d2.add_entry(title="T2", content="C", entry_type="pattern")
        assert len(d1.list_entries()) == 1
        assert len(d2.list_entries()) == 1

    def test_update_entry_emits_event(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        bus._captured.clear()
        kd.update_entry(e["entry_id"], title="Updated")
        topics = [ev.topic for ev in bus._captured]
        assert "knowledge.entry.updated" in topics

    def test_list_empty_db(self, kd):
        assert kd.list_entries() == []

    def test_distill_from_decisions_time_filter_to(self, kd):
        """Only snapshots before to_time should be considered."""
        now = time.time()
        with kd._lock:
            kd._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    decision_class TEXT NOT NULL DEFAULT 'D0',
                    module_states TEXT NOT NULL DEFAULT '{}',
                    choice_made TEXT,
                    is_active INTEGER DEFAULT 1,
                    superseded_by TEXT,
                    created_at REAL NOT NULL
                )
            """)
            for i in range(4):
                kd._conn.execute(
                    "INSERT INTO decision_snapshots "
                    "(snapshot_id, decision_id, decision_class, module_states, "
                    "choice_made, is_active, superseded_by, created_at) "
                    "VALUES (?, ?, 'D3', '{}', 'yes', 1, NULL, ?)",
                    (f"old_snap_{i}", f"DEC-{i}", now - 200),
                )
            kd._conn.commit()
        # Filter to a time range that excludes all snapshots
        entries = kd.distill_from_decisions(from_time=now - 50, to_time=now + 10)
        # The old snapshots (at now-200) are outside [now-50, now+10]
        assert not any("Repeated D3" in e["title"] for e in entries)

    def test_distill_from_pipeline_time_filter(self, kd):
        """Pipeline data outside time range should be excluded."""
        now = time.time()
        with kd._lock:
            kd._conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_run_states (
                    run_id TEXT PRIMARY KEY,
                    current_state TEXT NOT NULL DEFAULT 'idle',
                    previous_state TEXT,
                    paused_from TEXT,
                    state_entered_at REAL NOT NULL,
                    total_revisions INTEGER DEFAULT 0,
                    cancelled INTEGER DEFAULT 0,
                    cancellation_reason TEXT,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_state_log (
                    log_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    snapshot_id TEXT,
                    gate_id TEXT,
                    decision_id TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL
                );
            """)
            for i in range(5):
                kd._conn.execute(
                    "INSERT INTO pipeline_run_states "
                    "(run_id, current_state, previous_state, paused_from, "
                    "state_entered_at, total_revisions, cancelled, "
                    "cancellation_reason, updated_at) "
                    "VALUES (?, 'complete', 'reviewing', NULL, ?, 0, 0, NULL, ?)",
                    (f"run_{i}", now - 500, now - 500),
                )
            kd._conn.commit()
        # Filter to recent time -- should exclude the old runs
        entries = kd.distill_from_pipeline(from_time=now - 100, to_time=now + 10)
        assert entries == []


# ===========================================================================
# TestEventBusSourceModule
# ===========================================================================

class TestEventBusSourceModule:

    def test_add_entry_source_module(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        _add_entry(kd)
        assert bus._captured[0].source_module == "cognitive.knowledge_distiller"

    def test_validate_entry_source_module(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        bus._captured.clear()
        kd.validate_entry(e["entry_id"])
        assert bus._captured[0].source_module == "cognitive.knowledge_distiller"

    def test_apply_entry_source_module(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        bus._captured.clear()
        kd.apply_entry(e["entry_id"])
        assert bus._captured[0].source_module == "cognitive.knowledge_distiller"

    def test_link_entries_source_module(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e1 = _add_entry(kd)
        e2 = _add_entry(kd)
        bus._captured.clear()
        kd.link_entries(e1["entry_id"], e2["entry_id"])
        assert bus._captured[0].source_module == "cognitive.knowledge_distiller"

    def test_distillation_completed_source_module(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        kd.run_distillation()
        distill_events = [e for e in bus._captured if e.topic == "knowledge.distillation.completed"]
        assert len(distill_events) == 1
        assert distill_events[0].source_module == "cognitive.knowledge_distiller"

    def test_event_payload_contains_entry_id(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        e = _add_entry(kd)
        assert bus._captured[0].payload["entry_id"] == e["entry_id"]

    def test_event_payload_contains_entry_type(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        _add_entry(kd, entry_type="anti_pattern")
        assert bus._captured[0].payload["entry_type"] == "anti_pattern"

    def test_distillation_event_payload(self, bus):
        kd = KnowledgeDistiller(event_bus=bus)
        kd.run_distillation()
        distill_events = [e for e in bus._captured if e.topic == "knowledge.distillation.completed"]
        payload = distill_events[0].payload
        assert "job_id" in payload
        assert "status" in payload
        assert "entries_extracted" in payload


# ===========================================================================
# TestDistillationDecisionEdgeCases
# ===========================================================================

class TestDistillationDecisionEdgeCases:

    def _ensure_table(self, kd):
        with kd._lock:
            kd._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    decision_class TEXT NOT NULL DEFAULT 'D0',
                    module_states TEXT NOT NULL DEFAULT '{}',
                    choice_made TEXT,
                    is_active INTEGER DEFAULT 1,
                    superseded_by TEXT,
                    created_at REAL NOT NULL
                )
            """)
            kd._conn.commit()

    def test_two_snapshots_no_pattern(self, kd):
        """Fewer than 3 occurrences of a class should NOT trigger a pattern."""
        self._ensure_table(kd)
        now = time.time()
        with kd._lock:
            for i in range(2):
                kd._conn.execute(
                    "INSERT INTO decision_snapshots "
                    "(snapshot_id, decision_id, decision_class, module_states, "
                    "choice_made, is_active, superseded_by, created_at) "
                    "VALUES (?, ?, 'D3', '{}', 'yes', 1, NULL, ?)",
                    (f"snap_{i}", f"DEC-{i}", now),
                )
            kd._conn.commit()
        entries = kd.distill_from_decisions()
        assert not any("Repeated D3" in e["title"] for e in entries)

    def test_confidence_scales_with_count(self, kd):
        """More occurrences should yield higher confidence."""
        self._ensure_table(kd)
        now = time.time()
        with kd._lock:
            for i in range(5):
                kd._conn.execute(
                    "INSERT INTO decision_snapshots "
                    "(snapshot_id, decision_id, decision_class, module_states, "
                    "choice_made, is_active, superseded_by, created_at) "
                    "VALUES (?, ?, 'D3', '{}', 'yes', 1, NULL, ?)",
                    (f"snap5_{i}", f"DEC5-{i}", now),
                )
            kd._conn.commit()
        entries = kd.distill_from_decisions()
        pattern = [e for e in entries if "Repeated D3" in e["title"]][0]
        assert pattern["confidence"] >= 0.7

    def test_most_common_choice_reflected(self, kd):
        """The most frequent choice_made should appear in the pattern content."""
        self._ensure_table(kd)
        now = time.time()
        with kd._lock:
            choices = ["approve", "approve", "reject"]
            for i, c in enumerate(choices):
                kd._conn.execute(
                    "INSERT INTO decision_snapshots "
                    "(snapshot_id, decision_id, decision_class, module_states, "
                    "choice_made, is_active, superseded_by, created_at) "
                    "VALUES (?, ?, 'D2', '{}', ?, 1, NULL, ?)",
                    (f"snap_c_{i}", f"DEC-C-{i}", c, now),
                )
            kd._conn.commit()
        entries = kd.distill_from_decisions()
        pattern = [e for e in entries if "Repeated D2" in e["title"]][0]
        assert "approve" in pattern["content"]

    def test_applicability_broad_at_5_occurrences(self, kd):
        """5+ occurrences should set applicability to 'broad'."""
        self._ensure_table(kd)
        now = time.time()
        with kd._lock:
            for i in range(5):
                kd._conn.execute(
                    "INSERT INTO decision_snapshots "
                    "(snapshot_id, decision_id, decision_class, module_states, "
                    "choice_made, is_active, superseded_by, created_at) "
                    "VALUES (?, ?, 'D4', '{}', 'yes', 1, NULL, ?)",
                    (f"snap_b_{i}", f"DEC-B-{i}", now),
                )
            kd._conn.commit()
        entries = kd.distill_from_decisions()
        pattern = [e for e in entries if "Repeated D4" in e["title"]][0]
        assert pattern["applicability"] == "broad"


# ===========================================================================
# TestDistillationPipelineEdgeCases
# ===========================================================================

class TestDistillationPipelineEdgeCases:

    def _ensure_tables(self, kd):
        with kd._lock:
            kd._conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_run_states (
                    run_id TEXT PRIMARY KEY,
                    current_state TEXT NOT NULL DEFAULT 'idle',
                    previous_state TEXT,
                    paused_from TEXT,
                    state_entered_at REAL NOT NULL,
                    total_revisions INTEGER DEFAULT 0,
                    cancelled INTEGER DEFAULT 0,
                    cancellation_reason TEXT,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_state_log (
                    log_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    snapshot_id TEXT,
                    gate_id TEXT,
                    decision_id TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL
                );
            """)
            kd._conn.commit()

    def test_two_runs_no_best_practice(self, kd):
        """Fewer than 3 runs should NOT trigger success rate pattern."""
        self._ensure_tables(kd)
        now = time.time()
        with kd._lock:
            for i in range(2):
                kd._conn.execute(
                    "INSERT INTO pipeline_run_states "
                    "(run_id, current_state, previous_state, paused_from, "
                    "state_entered_at, total_revisions, cancelled, "
                    "cancellation_reason, updated_at) "
                    "VALUES (?, 'complete', 'reviewing', NULL, ?, 0, 0, NULL, ?)",
                    (f"run_few_{i}", now, now),
                )
            kd._conn.commit()
        entries = kd.distill_from_pipeline()
        assert not any("success rate" in e["title"].lower() for e in entries)

    def test_below_80pct_no_success_pattern(self, kd):
        """Completion rate below 80% should NOT trigger best practice."""
        self._ensure_tables(kd)
        now = time.time()
        with kd._lock:
            # 3 complete, 2 cancelled = 60% completion
            for i in range(3):
                kd._conn.execute(
                    "INSERT INTO pipeline_run_states "
                    "(run_id, current_state, previous_state, paused_from, "
                    "state_entered_at, total_revisions, cancelled, "
                    "cancellation_reason, updated_at) "
                    "VALUES (?, 'complete', 'reviewing', NULL, ?, 0, 0, NULL, ?)",
                    (f"run_comp_{i}", now, now),
                )
            for i in range(2):
                kd._conn.execute(
                    "INSERT INTO pipeline_run_states "
                    "(run_id, current_state, previous_state, paused_from, "
                    "state_entered_at, total_revisions, cancelled, "
                    "cancellation_reason, updated_at) "
                    "VALUES (?, 'cancelled', 'reviewing', NULL, ?, 0, 1, NULL, ?)",
                    (f"run_canc_{i}", now, now),
                )
            kd._conn.commit()
        entries = kd.distill_from_pipeline()
        assert not any("success rate" in e["title"].lower() for e in entries)

    def test_single_high_revision_run_no_pattern(self, kd):
        """Only 1 run with high revisions should NOT trigger anti-pattern (need >= 2)."""
        self._ensure_tables(kd)
        now = time.time()
        with kd._lock:
            kd._conn.execute(
                "INSERT INTO pipeline_run_states "
                "(run_id, current_state, previous_state, paused_from, "
                "state_entered_at, total_revisions, cancelled, "
                "cancellation_reason, updated_at) "
                "VALUES (?, 'complete', 'reviewing', NULL, ?, 5, 0, NULL, ?)",
                ("run_rev_1", now, now),
            )
            kd._conn.commit()
        entries = kd.distill_from_pipeline()
        assert not any("revision" in e["title"].lower() for e in entries)

    def test_distillation_pipeline_tags(self, kd):
        """Pipeline-extracted entries should have pipeline-related tags."""
        self._ensure_tables(kd)
        now = time.time()
        with kd._lock:
            for i in range(4):
                kd._conn.execute(
                    "INSERT INTO pipeline_run_states "
                    "(run_id, current_state, previous_state, paused_from, "
                    "state_entered_at, total_revisions, cancelled, "
                    "cancellation_reason, updated_at) "
                    "VALUES (?, 'complete', 'reviewing', NULL, ?, 0, 0, NULL, ?)",
                    (f"run_tag_{i}", now, now),
                )
            kd._conn.commit()
        entries = kd.distill_from_pipeline()
        assert len(entries) > 0
        for e in entries:
            assert "pipeline" in e["tags"]
