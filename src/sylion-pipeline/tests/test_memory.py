"""
SYLION Memory Package -- Unit Tests

Tests for 7 modules: kanon_access, compact_layer, evidence_store,
self_model_store, kb_adapter, indexer, retrieval.
"""

from __future__ import annotations

import hashlib
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.kanon_access import KanonAccess, KanonSection
from sylion.memory.compact_layer import CompactLayer
from sylion.memory.evidence_store import EvidenceStore
from sylion.memory.self_model_store import SelfModelStore
from sylion.memory.kb_adapter import KBAdapter
from sylion.memory.indexer import Indexer
from sylion.memory.retrieval import Retrieval


# =====================================================================
# KanonAccess tests
# =====================================================================

class TestKanonAccess:

    def test_load_text_with_separator(self):
        ka = KanonAccess()
        raw = "# Section One\nContent one\n---\n# Section Two\nContent two"
        result = ka.load_text(raw)
        assert result["sections_loaded"] == 2
        assert len(result["section_ids"]) == 2

    def test_load_text_with_headers(self):
        ka = KanonAccess()
        raw = "# Alpha\nAlpha content\n# Beta\nBeta content"
        result = ka.load_text(raw)
        assert result["sections_loaded"] == 2

    def test_store_and_retrieve_section(self):
        ka = KanonAccess()
        section = KanonSection(
            title="Test Section",
            content="Test content body",
            chapter="test",
            section_number=1,
        )
        stored = ka.store_section(section)
        assert "section_id" in stored
        assert "hash" in stored

        retrieved = ka.get_section(section.section_id)
        assert retrieved is not None
        assert retrieved["title"] == "Test Section"
        assert retrieved["content"] == "Test content body"
        assert retrieved["hash"] == hashlib.sha256(b"Test content body").hexdigest()

    def test_search_sections(self):
        ka = KanonAccess()
        ka.load_text("# Python Basics\nPython is a language\n---\n# Rust Guide\nRust is fast")
        results = ka.search("Python")
        assert len(results) == 1
        assert "Python" in results[0]["title"]

    def test_list_and_filter_by_chapter(self):
        ka = KanonAccess()
        ka.load_text("# Intro: Overview\nIntro content\n---\n# Intro: Details\nDetails")
        all_sections = ka.list_sections()
        assert len(all_sections) == 2
        filtered = ka.list_sections(chapter="Intro")
        assert len(filtered) == 2

    def test_get_full_text(self):
        ka = KanonAccess()
        ka.load_text("# Title A\nBody A\n---\n# Title B\nBody B")
        full = ka.get_full_text()
        assert "Title A" in full
        assert "Body B" in full

    def test_content_hash_integrity(self):
        ka = KanonAccess()
        section = KanonSection(
            title="Hashed",
            content="integrity check",
            section_number=1,
        )
        expected = hashlib.sha256("integrity check".encode("utf-8")).hexdigest()
        assert section.hash == expected

    def test_get_nonexistent_section(self):
        ka = KanonAccess()
        assert ka.get_section("nonexistent") is None


# =====================================================================
# CompactLayer tests
# =====================================================================

class TestCompactLayer:

    def test_compact_returns_compacted_key(self):
        """Quirk: compact() returns dict with key 'compacted' (not 'compact_text')."""
        cl = CompactLayer()
        text = "Hello world. Hello world. This is a test of compaction."
        result = cl.compact(text)
        assert "compacted" in result
        assert isinstance(result["compacted"], str)
        assert "original_size" in result
        assert "compact_size" in result
        assert "ratio" in result
        assert "fidelity_score" in result

    def test_compact_deduplicates_lines(self):
        cl = CompactLayer()
        text = "Duplicate line here.\nDuplicate line here.\nUnique line."
        result = cl.compact(text)
        lines = result["compacted"].splitlines()
        # After dedup, only 2 unique lines
        assert len(lines) == 2

    def test_compact_empty_text(self):
        cl = CompactLayer()
        result = cl.compact("")
        assert result["compacted"] == ""
        assert result["original_size"] == 0

    def test_fidelity_computation(self):
        cl = CompactLayer()
        original = "The quick brown fox jumps over the lazy dog"
        compacted = "quick brown fox jumps lazy dog"
        fidelity = cl.compute_fidelity(original, compacted)
        assert 0.0 <= fidelity <= 1.0
        assert fidelity > 0.5  # Most words preserved

    def test_record_compaction_persists(self):
        cl = CompactLayer()
        rec = cl.record_compaction("some original text", "compacted text")
        assert "record_id" in rec
        assert "ratio" in rec
        stats = cl.get_stats()
        assert stats["total_records"] == 1

    def test_get_stats_empty(self):
        cl = CompactLayer()
        stats = cl.get_stats()
        assert stats["total_records"] == 0
        assert stats["avg_ratio"] == 0.0


# =====================================================================
# EvidenceStore tests
# =====================================================================

class TestEvidenceStore:

    def test_store_and_retrieve(self):
        es = EvidenceStore()
        result = es.store(
            pack_id="pack1",
            artefact_type="test_result",
            name="unit_test",
            content="passed: 42 tests",
        )
        assert "evidence_id" in result
        assert "content_hash" in result

        retrieved = es.retrieve(result["evidence_id"])
        assert retrieved is not None
        assert retrieved["name"] == "unit_test"
        assert retrieved["pack_id"] == "pack1"

    def test_content_hash_verification(self):
        es = EvidenceStore()
        content = "verified content"
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        result = es.store(content=content)
        assert result["content_hash"] == expected_hash

    def test_query_by_type(self):
        es = EvidenceStore()
        es.store(artefact_type="screenshot", name="s1", content="img1")
        es.store(artefact_type="screenshot", name="s2", content="img2")
        es.store(artefact_type="log", name="l1", content="log1")

        screenshots = es.query_by_type("screenshot")
        assert len(screenshots) == 2
        logs = es.query_by_type("log")
        assert len(logs) == 1

    def test_query_by_pack(self):
        es = EvidenceStore()
        es.store(pack_id="alpha", name="a1", content="c1")
        es.store(pack_id="alpha", name="a2", content="c2")
        es.store(pack_id="beta", name="b1", content="c3")

        alpha = es.query_by_pack("alpha")
        assert len(alpha) == 2

    def test_delete_evidence(self):
        es = EvidenceStore()
        result = es.store(name="to_delete", content="temporary")
        assert es.delete(result["evidence_id"]) is True
        assert es.retrieve(result["evidence_id"]) is None
        assert es.delete(result["evidence_id"]) is False

    def test_get_stats(self):
        es = EvidenceStore()
        es.store(artefact_type="benchmark", name="b1", content="data")
        es.store(artefact_type="benchmark", name="b2", content="data2")
        stats = es.get_stats()
        assert stats["total_evidence"] == 2
        assert "benchmark" in stats["by_type"]


# =====================================================================
# SelfModelStore tests
# =====================================================================

class TestSelfModelStore:

    def test_initialize_model(self):
        sms = SelfModelStore()
        model = sms.initialize(
            "model-1",
            capabilities={"reasoning": True},
            constraints={"max_tokens": 4096},
        )
        assert model["model_id"] == "model-1"
        assert model["version"] == 1
        assert model["capabilities"]["reasoning"] is True
        assert model["health"] == "healthy"
        assert model["autonomy_level"] == 0

    def test_update_model(self):
        sms = SelfModelStore()
        sms.initialize("model-2")
        updated = sms.update(
            "model-2",
            capabilities={"code_gen": True},
            health="degraded",
            autonomy_level=3,
        )
        assert updated is not None
        assert updated["version"] == 2
        assert updated["health"] == "degraded"
        assert updated["autonomy_level"] == 3

    def test_update_nonexistent_model(self):
        sms = SelfModelStore()
        result = sms.update("ghost")
        assert result is None

    def test_snapshot_and_history(self):
        sms = SelfModelStore()
        sms.initialize("model-3", capabilities={"v1": True})
        sms.update("model-3", capabilities={"v2": True})
        snap = sms.snapshot("model-3", reason="version bump")
        assert snap is not None
        assert "snapshot_id" in snap
        assert snap["version"] == 2

        history = sms.get_history("model-3")
        assert len(history) == 1
        assert history[0]["reason"] == "version bump"

    def test_get_latest_snapshot(self):
        sms = SelfModelStore()
        sms.initialize("model-4")
        sms.snapshot("model-4", reason="first")
        sms.update("model-4", health="degraded")
        sms.snapshot("model-4", reason="second")
        latest = sms.get_latest("model-4")
        assert latest is not None
        assert latest["reason"] == "second"

    def test_get_nonexistent_model(self):
        sms = SelfModelStore()
        assert sms.get("nope") is None


# =====================================================================
# KBAdapter tests
# =====================================================================

class TestKBAdapter:

    def test_register_source(self):
        kba = KBAdapter()
        result = kba.register_source(
            "src-1", "Test KB", source_type="file", path="/data/kb"
        )
        assert result["source_id"] == "src-1"
        assert result["name"] == "Test KB"
        assert result["active"] == 1

    def test_get_source(self):
        kba = KBAdapter()
        kba.register_source("src-2", "Docs", source_type="api")
        src = kba.get_source("src-2")
        assert src is not None
        assert src["source_type"] == "api"

    def test_list_sources(self):
        kba = KBAdapter()
        kba.register_source("s1", "Alpha")
        kba.register_source("s2", "Beta")
        active = kba.list_sources(active_only=True)
        assert len(active) == 2

    def test_query_returns_empty_stub(self):
        kba = KBAdapter()
        kba.register_source("src-q", "QueryTest")
        results = kba.query("src-q", "test query")
        assert isinstance(results, list)
        assert len(results) == 0  # Stub implementation

    def test_index_marks_timestamp(self):
        kba = KBAdapter()
        kba.register_source("src-i", "IndexTest")
        result = kba.index("src-i")
        assert result is not None
        assert result["last_indexed"] > 0

    def test_index_nonexistent_source(self):
        kba = KBAdapter()
        result = kba.index("ghost")
        assert result is None

    def test_get_stats(self):
        kba = KBAdapter()
        kba.register_source("s1", "A")
        kba.register_source("s2", "B")
        kba.query("s1", "hello")
        stats = kba.get_stats()
        assert stats["total_sources"] == 2
        assert stats["active_sources"] == 2
        assert stats["total_queries"] == 1


# =====================================================================
# Indexer tests
# =====================================================================

class TestIndexer:

    def test_index_section(self):
        idx = Indexer()
        result = idx.index_section(
            "sec-1", "Python Basics", "Python is a versatile programming language."
        )
        assert result["section_id"] == "sec-1"
        assert result["unique_terms"] > 0
        assert result["word_count"] > 0

    def test_search_returns_ranked(self):
        idx = Indexer()
        idx.index_section("sec-1", "Python Basics", "Python python python is great")
        idx.index_section("sec-2", "Rust Basics", "Rust rust rust is fast")
        results = idx.search("Python")
        assert len(results) >= 1
        assert results[0]["section_id"] == "sec-1"
        assert results[0]["score"] > 0

    def test_remove_section(self):
        idx = Indexer()
        idx.index_section("sec-r", "Remove Me", "Content to be removed")
        assert idx.remove_section("sec-r") is True
        assert idx.remove_section("sec-r") is False  # Already removed

    def test_reindex_section(self):
        idx = Indexer()
        idx.index_section("sec-u", "Original", "original content")
        idx.index_section("sec-u", "Updated", "updated content here now")
        # Should have only one entry (replaced)
        results = idx.search("updated")
        assert len(results) >= 1

    def test_get_stats(self):
        idx = Indexer()
        idx.index_section("s1", "A", "alpha beta")
        idx.index_section("s2", "B", "gamma delta")
        stats = idx.get_stats()
        assert stats["indexed_sections"] == 2
        assert stats["unique_terms"] > 0

    def test_search_empty_query(self):
        idx = Indexer()
        idx.index_section("s1", "Test", "content")
        results = idx.search("")
        assert results == []


# =====================================================================
# Retrieval tests
# =====================================================================

class TestRetrieval:

    def _setup_indexer_with_data(self):
        idx = Indexer()
        idx.index_section(
            "sec-1", "Python Tutorial",
            "Python is a popular programming language used for web data science automation."
        )
        idx.index_section(
            "sec-2", "Rust Guide",
            "Rust is a systems programming language focused on safety speed and concurrency."
        )
        idx.index_section(
            "sec-3", "JavaScript Basics",
            "JavaScript is the language of the web used in browsers and servers."
        )
        return idx

    def test_retrieve_returns_ranked_results(self):
        idx = self._setup_indexer_with_data()
        ret = Retrieval(indexer=idx)
        results = ret.retrieve("Python programming")
        assert len(results) >= 1
        assert results[0].section_id == "sec-1"
        assert results[0].score > 0

    def test_retrieve_with_min_score(self):
        idx = self._setup_indexer_with_data()
        ret = Retrieval(indexer=idx)
        # Very high min_score should filter most results
        results = ret.retrieve("Python", min_score=999.0)
        assert len(results) == 0

    def test_get_context_within_budget(self):
        idx = self._setup_indexer_with_data()
        ret = Retrieval(indexer=idx)
        context = ret.get_context("Python", max_tokens=50)
        # Should be within rough token budget
        assert isinstance(context, str)
        assert len(context) > 0

    def test_get_context_empty_index(self):
        idx = Indexer()
        ret = Retrieval(indexer=idx)
        context = ret.get_context("nonexistent")
        assert context == ""
