"""
Comprehensive tests for sylion.cognitive.idea_attachments -- IdeaAttachments

Covers:
  - add_attachment (metadata, base64 storage, input validation)
  - get_attachment and get_attachment_content
  - list_attachments
  - delete_attachment
  - get_attachment_stats
  - EventBus emission (attachment_added, attachment_deleted)
  - Edge cases (empty db, unknown IDs, validation errors)
  - Thread safety
  - Singleton get/reset
"""

from __future__ import annotations

import base64
import io
import threading
import time
import zipfile

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.idea_attachments import (
    IdeaAttachments,
    get_idea_attachments,
    reset_idea_attachments,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def att():
    return IdeaAttachments()


@pytest.fixture
def att_with_bus():
    bus = EventBus()
    a = IdeaAttachments(event_bus=bus)
    return a, bus


# ===========================================================================
# 1. add_attachment()
# ===========================================================================

class TestAddAttachment:

    def test_returns_attachment_dict(self, att):
        result = att.add_attachment("idea1", "file.txt", "text/plain", b"hello")
        assert "attachment_id" in result
        assert len(result["attachment_id"]) == 32
        assert result["idea_id"] == "idea1"
        assert result["filename"] == "file.txt"
        assert result["file_type"] == "text/plain"
        assert result["file_size"] == 5

    def test_empty_content(self, att):
        result = att.add_attachment("idea1", "empty.txt", "text/plain", b"")
        assert result["file_size"] == 0

    def test_large_content(self, att):
        data = b"x" * 100000
        result = att.add_attachment("idea1", "big.bin", "application/octet-stream", data)
        assert result["file_size"] == 100000

    def test_binary_content(self, att):
        data = bytes(range(256))
        result = att.add_attachment("idea1", "binary.bin", "application/octet-stream", data)
        assert result["file_size"] == 256

    def test_empty_idea_id_raises(self, att):
        with pytest.raises(ValueError, match="idea_id"):
            att.add_attachment("", "file.txt", "text/plain", b"data")

    def test_empty_filename_raises(self, att):
        with pytest.raises(ValueError, match="filename"):
            att.add_attachment("idea1", "", "text/plain", b"data")

    def test_non_bytes_raises(self, att):
        with pytest.raises(TypeError, match="content_bytes"):
            att.add_attachment("idea1", "file.txt", "text/plain", "not bytes")

    def test_auto_timestamp(self, att):
        before = time.time()
        result = att.add_attachment("idea1", "f.txt", "text/plain", b"x")
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_various_file_types(self, att):
        for ft in ["text/plain", "application/pdf", "image/png", "application/json"]:
            result = att.add_attachment("idea1", f"f.{ft.split('/')[-1]}", ft, b"data")
            assert result["file_type"] == ft


# ===========================================================================
# 2. get_attachment()
# ===========================================================================

class TestGetAttachment:

    def test_returns_attachment_metadata(self, att):
        created = att.add_attachment("idea1", "file.txt", "text/plain", b"hello")
        fetched = att.get_attachment(created["attachment_id"])
        assert fetched is not None
        assert fetched["filename"] == "file.txt"
        assert fetched["idea_id"] == "idea1"

    def test_nonexistent_returns_none(self, att):
        assert att.get_attachment("nonexistent") is None

    def test_does_not_include_content(self, att):
        created = att.add_attachment("idea1", "f.txt", "text/plain", b"secret")
        fetched = att.get_attachment(created["attachment_id"])
        assert "content_b64" not in fetched


# ===========================================================================
# 3. get_attachment_content()
# ===========================================================================

class TestGetAttachmentContent:

    def test_returns_original_bytes(self, att):
        original = b"hello world"
        created = att.add_attachment("idea1", "f.txt", "text/plain", original)
        content = att.get_attachment_content(created["attachment_id"])
        assert content == original

    def test_nonexistent_returns_none(self, att):
        assert att.get_attachment_content("nonexistent") is None

    def test_roundtrip_binary(self, att):
        data = bytes(range(256))
        created = att.add_attachment("idea1", "bin.dat", "app/bin", data)
        result = att.get_attachment_content(created["attachment_id"])
        assert result == data

    def test_roundtrip_empty(self, att):
        created = att.add_attachment("idea1", "e.txt", "text/plain", b"")
        result = att.get_attachment_content(created["attachment_id"])
        assert result == b""


# ===========================================================================
# 4. attachment analysis
# ===========================================================================

class TestAnalyzeAttachment:

    @staticmethod
    def _zip_bytes(files: dict[str, str]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files.items():
                zf.writestr(filename, content)
        return buf.getvalue()

    def test_zip_archive_gets_inventory_and_text_preview(self, att):
        archive = self._zip_bytes({
            "README.md": "# Demo\nThis is a project brief.",
            "src/app.py": "def run():\n    return 'ok'\n",
            "package.json": '{"scripts":{"dev":"vite","test":"vitest","build":"vite build"}}',
            ".env.example": "DATABASE_URL=sqlite://demo",
        })
        created = att.add_attachment("idea1", "project.zip", "application/zip", archive)

        result = att.analyze_attachment(created["attachment_id"])

        assert result["detected_kind"] == "zip_archive"
        assert "ZIP archive detailed analysis" in result["extracted_text_preview"]
        assert "Project purpose and operating model" in result["extracted_text_preview"]
        assert "Functional capability map" in result["extracted_text_preview"]
        assert "Sandbox deploy and test readiness" in result["extracted_text_preview"]
        assert "Suggested sandbox validation commands" in result["extracted_text_preview"]
        assert "Detailed manifest" in result["extracted_text_preview"]
        assert "Detailed content previews" in result["extracted_text_preview"]
        assert "src/app.py" in result["extracted_text_preview"]
        assert "zip_archive" in result["tags"]
        assert "codebase" in result["tags"]
        assert "zip_attachment_analyzer" in result["suggested_skills"]
        assert result["decision_class"] == "D2"
        assert result["human_gate_required"] is False

    def test_zip_archive_prioritizes_project_content_over_dependencies(self, att):
        archive = self._zip_bytes({
            **{
                f"node_modules/pkg{i}/index.js": f"module.exports = {i};"
                for i in range(80)
            },
            "sylion-tailor-v2/src/app/orders/page.tsx": "export function Orders(){ return 'tailor workflow'; }",
            "sylion-tailor-v2/src/api/customers.ts": "export const pii = 'customer email gdpr retention';",
            "sylion-tailor-v2/docs/architecture.md": "# Architecture\nCRM, grants and production workflow.",
            "sylion-tailor-v2/e2e/orders.spec.ts": "test('order workflow', async () => {});",
            "sylion-tailor-v2/package.json": '{"scripts":{"dev":"vite","test:e2e":"playwright test","build":"vite build"}}',
            "sylion-tailor-v2/docker-compose.yml": "services:\n  app:\n    build: .\n",
            "sylion-tailor-v2/.env.example": "DATABASE_URL=postgres://example",
        })
        created = att.add_attachment("idea1", "tailor.zip", "application/zip", archive)

        result = att.analyze_attachment(created["attachment_id"])
        preview = result["extracted_text_preview"]

        assert "Detailed content previews" in preview
        assert "Project purpose and operating model" in preview
        assert "Likely product purpose" in preview
        assert "Documentation evidence" in preview
        assert "How it appears to work" in preview
        assert "Functional capability map" in preview
        assert "Sandbox deploy and test readiness" in preview
        assert "cd sylion-tailor-v2 && npm run dev" in preview
        assert "cd sylion-tailor-v2 && npm run test:e2e" in preview
        assert "Runtime blockers before automatic deploy" in preview
        assert "UI / frontend screens and components" in preview
        assert "Automated tests and QA" in preview
        assert "sylion-tailor-v2/src/app/orders/page.tsx" in preview
        assert "tailor workflow" in preview
        assert "Dependency/generated files skipped from content previews" in preview
        assert preview.index("Detailed content previews") < preview.index("Detailed manifest")
        assert preview.index("sylion-tailor-v2/src/app/orders/page.tsx") < preview.index("node_modules/pkg0/index.js")

    def test_zip_archive_with_unsafe_path_is_governed(self, att):
        archive = self._zip_bytes({
            "../evil.txt": "bad",
            "safe.txt": "ok",
        })
        created = att.add_attachment("idea1", "unsafe.zip", "application/zip", archive)

        result = att.analyze_attachment(created["attachment_id"])

        assert result["detected_kind"] == "zip_archive"
        assert "Unsafe paths detected" in result["extracted_text_preview"]
        assert result["decision_class"] == "D3"
        assert result["human_gate_required"] is True

    def test_docx_attachment_extracts_document_text(self, att):
        archive = self._zip_bytes({
            "word/document.xml": (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Opis projektu i wymagania Rady</w:t></w:r></w:p></w:body>"
                "</w:document>"
            ),
        })
        created = att.add_attachment(
            "idea1",
            "brief.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            archive,
        )

        result = att.analyze_attachment(created["attachment_id"])

        assert result["detected_kind"] == "docx_document"
        assert "Opis projektu i wymagania Rady" in result["extracted_text_preview"]
        assert "document_content_reviewer" in result["suggested_skills"]
        assert result["decision_class"] == "D2"


# ===========================================================================
# 5. list_attachments()
# ===========================================================================

class TestListAttachments:

    def test_empty_list(self, att):
        assert att.list_attachments("idea1") == []

    def test_returns_all_for_idea(self, att):
        att.add_attachment("idea1", "a.txt", "text/plain", b"a")
        att.add_attachment("idea1", "b.txt", "text/plain", b"b")
        att.add_attachment("idea2", "c.txt", "text/plain", b"c")
        results = att.list_attachments("idea1")
        assert len(results) == 2

    def test_ordered_by_created_at_desc(self, att):
        r1 = att.add_attachment("idea1", "first.txt", "text/plain", b"1")
        r2 = att.add_attachment("idea1", "second.txt", "text/plain", b"2")
        results = att.list_attachments("idea1")
        assert results[0]["attachment_id"] == r2["attachment_id"]
        assert results[1]["attachment_id"] == r1["attachment_id"]

    def test_no_content_in_list(self, att):
        att.add_attachment("idea1", "f.txt", "text/plain", b"data")
        results = att.list_attachments("idea1")
        assert "content_b64" not in results[0]


# ===========================================================================
# 5. delete_attachment()
# ===========================================================================

class TestDeleteAttachment:

    def test_delete_existing(self, att):
        created = att.add_attachment("idea1", "f.txt", "text/plain", b"data")
        assert att.delete_attachment(created["attachment_id"]) is True

    def test_delete_nonexistent(self, att):
        assert att.delete_attachment("nonexistent") is False

    def test_get_after_delete_returns_none(self, att):
        created = att.add_attachment("idea1", "f.txt", "text/plain", b"data")
        att.delete_attachment(created["attachment_id"])
        assert att.get_attachment(created["attachment_id"]) is None

    def test_content_after_delete_returns_none(self, att):
        created = att.add_attachment("idea1", "f.txt", "text/plain", b"data")
        att.delete_attachment(created["attachment_id"])
        assert att.get_attachment_content(created["attachment_id"]) is None

    def test_list_after_delete_empty(self, att):
        created = att.add_attachment("idea1", "f.txt", "text/plain", b"data")
        att.delete_attachment(created["attachment_id"])
        assert att.list_attachments("idea1") == []


# ===========================================================================
# 6. get_attachment_stats()
# ===========================================================================

class TestGetAttachmentStats:

    def test_empty_db(self, att):
        stats = att.get_attachment_stats()
        assert stats["total"] == 0
        assert stats["total_size"] == 0

    def test_counts(self, att):
        att.add_attachment("i1", "a.txt", "text/plain", b"12345")
        att.add_attachment("i1", "b.pdf", "application/pdf", b"123")
        att.add_attachment("i2", "c.txt", "text/plain", b"12")
        stats = att.get_attachment_stats()
        assert stats["total"] == 3
        assert stats["total_size"] == 10

    def test_by_type(self, att):
        att.add_attachment("i1", "a.txt", "text/plain", b"x")
        att.add_attachment("i1", "b.txt", "text/plain", b"x")
        att.add_attachment("i2", "c.pdf", "application/pdf", b"x")
        stats = att.get_attachment_stats()
        assert stats["by_type"]["text/plain"] == 2
        assert stats["by_type"]["application/pdf"] == 1

    def test_top_ideas(self, att):
        att.add_attachment("i1", "a.txt", "text/plain", b"x")
        att.add_attachment("i1", "b.txt", "text/plain", b"x")
        att.add_attachment("i2", "c.txt", "text/plain", b"x")
        stats = att.get_attachment_stats()
        assert stats["top_ideas"]["i1"] == 2
        assert stats["top_ideas"]["i2"] == 1

    def test_after_delete(self, att):
        created = att.add_attachment("i1", "f.txt", "text/plain", b"xxx")
        att.delete_attachment(created["attachment_id"])
        stats = att.get_attachment_stats()
        assert stats["total"] == 0


# ===========================================================================
# 7. Event emission
# ===========================================================================

class TestEventEmission:

    def test_add_emits_attachment_added(self, att_with_bus):
        a, bus = att_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("attachment_added", lambda e: events.append(e))
        a.add_attachment("idea1", "f.txt", "text/plain", b"data")
        assert len(events) == 1
        assert events[0].payload["filename"] == "f.txt"
        assert events[0].payload["file_size"] == 4

    def test_delete_emits_attachment_deleted(self, att_with_bus):
        a, bus = att_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("attachment_deleted", lambda e: events.append(e))
        created = a.add_attachment("idea1", "f.txt", "text/plain", b"data")
        a.delete_attachment(created["attachment_id"])
        assert len(events) == 1
        assert events[0].payload["idea_id"] == "idea1"

    def test_event_source_module(self, att_with_bus):
        a, bus = att_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("attachment_added", lambda e: events.append(e))
        a.add_attachment("idea1", "f.txt", "text/plain", b"data")
        assert events[0].source_module == "cognitive.idea_attachments"

    def test_no_bus_does_not_raise(self):
        a = IdeaAttachments()
        created = a.add_attachment("idea1", "f.txt", "text/plain", b"data")
        a.delete_attachment(created["attachment_id"])


# ===========================================================================
# 8. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_adds(self):
        a = IdeaAttachments()
        results: list[dict] = []
        results_lock = threading.Lock()

        def add_file(idx):
            r = a.add_attachment("idea1", f"f{idx}.txt", "text/plain", f"data{idx}".encode())
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=add_file, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        ids = [r["attachment_id"] for r in results]
        assert len(set(ids)) == 20
        assert a.get_attachment_stats()["total"] == 20

    def test_concurrent_reads_and_writes(self):
        a = IdeaAttachments()
        created = a.add_attachment("idea1", "f.txt", "text/plain", b"initial")
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def read_content():
            try:
                a.get_attachment_content(created["attachment_id"])
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        def add_more(idx):
            try:
                a.add_attachment("idea1", f"f{idx}.txt", "text/plain", b"x")
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = (
            [threading.Thread(target=read_content) for _ in range(10)]
            + [threading.Thread(target=add_more, args=(i,)) for i in range(10)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert a.get_attachment_stats()["total"] == 11


# ===========================================================================
# 9. Singleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_same(self):
        reset_idea_attachments()
        a1 = get_idea_attachments()
        a2 = get_idea_attachments()
        assert a1 is a2
        reset_idea_attachments()

    def test_reset_creates_new(self):
        reset_idea_attachments()
        a1 = get_idea_attachments()
        reset_idea_attachments()
        a2 = get_idea_attachments()
        assert a1 is not a2
        reset_idea_attachments()

    def test_singleton_with_custom_params(self):
        reset_idea_attachments()
        bus = EventBus()
        a = get_idea_attachments(event_bus=bus)
        assert a is not None
        reset_idea_attachments()
