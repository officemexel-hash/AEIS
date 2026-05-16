"""Comprehensive tests for sylion.surface.artifact_control module.

Covers: initiate_upload, finalize_upload, publish, deprecate,
        get_artifact, list_artifacts, get_versions, get_upload_session,
        stats, edge cases, thread safety, event emission.
"""
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.surface.artifact_control import (
    Artifact,
    ArtifactControl,
    UploadSession,
    get_artifact_control,
)
import sylion.surface.artifact_control as mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._ctrl = None
    yield
    mod._ctrl = None


@pytest.fixture
def ctrl():
    return ArtifactControl()


@pytest.fixture
def ctrl_with_events():
    eb = EventBus()
    collected = []
    eb.subscribe("*", lambda e: collected.append(e))
    ac = ArtifactControl(event_bus=eb)
    return ac, collected


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestArtifactDataclass:
    def test_auto_id(self):
        a = Artifact(name="test")
        assert len(a.artifact_id) == 32

    def test_auto_timestamp(self):
        a = Artifact(name="test")
        assert a.created_at > 0

    def test_defaults(self):
        a = Artifact(name="test")
        assert a.artifact_type == "DOCUMENT"
        assert a.version == 1
        assert a.status == "DRAFT"
        assert a.metadata == {}


class TestUploadSessionDataclass:
    def test_auto_id(self):
        s = UploadSession()
        assert len(s.session_id) == 32

    def test_auto_timestamp(self):
        s = UploadSession()
        assert s.created_at > 0

    def test_defaults(self):
        s = UploadSession()
        assert s.status == "INITIATED"


# ---------------------------------------------------------------------------
# Initiate upload
# ---------------------------------------------------------------------------

class TestInitiateUpload:
    def test_basic(self, ctrl):
        result = ctrl.initiate_upload("config.yaml", "CONFIG", uploaded_by="dev")
        assert result["status"] == "DRAFT"
        assert len(result["artifact_id"]) == 32
        assert len(result["session_id"]) == 32
        assert "signed_url" in result
        assert result["artifact_id"] in result["signed_url"]

    def test_signed_url_format(self, ctrl):
        result = ctrl.initiate_upload("report.pdf")
        assert result["signed_url"].startswith("http://localhost:5805/upload/")

    def test_default_type(self, ctrl):
        ctrl.initiate_upload("file.txt")
        arts = ctrl.list_artifacts()
        assert arts[0]["artifact_type"] == "DOCUMENT"

    def test_with_size(self, ctrl):
        result = ctrl.initiate_upload("big.bin", size_bytes=1048576)
        art = ctrl.get_artifact(result["artifact_id"])
        assert art["size_bytes"] == 1048576

    def test_creates_session(self, ctrl):
        result = ctrl.initiate_upload("test.txt")
        session = ctrl.get_upload_session(result["session_id"])
        assert session is not None
        assert session["status"] == "INITIATED"
        assert session["artifact_id"] == result["artifact_id"]


# ---------------------------------------------------------------------------
# Finalize upload
# ---------------------------------------------------------------------------

class TestFinalizeUpload:
    def test_finalize_success(self, ctrl):
        upload = ctrl.initiate_upload("report.pdf")
        result = ctrl.finalize_upload(
            upload["session_id"], checksum="abc123", size_bytes=1024,
        )
        assert result["status"] == "COMPLETED"
        assert result["artifact_id"] == upload["artifact_id"]

        art = ctrl.get_artifact(upload["artifact_id"])
        assert art["checksum"] == "abc123"
        assert art["size_bytes"] == 1024

    def test_finalize_updates_session(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(upload["session_id"])
        session = ctrl.get_upload_session(upload["session_id"])
        assert session["status"] == "COMPLETED"
        assert session["completed_at"] > 0

    def test_finalize_nonexistent(self, ctrl):
        result = ctrl.finalize_upload("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_finalize_already_completed(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(upload["session_id"])
        result = ctrl.finalize_upload(upload["session_id"])
        assert "error" in result

    def test_finalize_with_checksum(self, ctrl):
        upload = ctrl.initiate_upload("hash.txt")
        ctrl.finalize_upload(upload["session_id"], checksum="sha256:abc")
        art = ctrl.get_artifact(upload["artifact_id"])
        assert art["checksum"] == "sha256:abc"


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

class TestPublish:
    def test_publish_draft(self, ctrl):
        upload = ctrl.initiate_upload("model.pkl", "MODEL")
        ctrl.finalize_upload(upload["session_id"])
        result = ctrl.publish(upload["artifact_id"], publisher="ml_team")
        assert result["status"] == "PUBLISHED"

    def test_publish_sets_published_at(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(upload["session_id"])
        ctrl.publish(upload["artifact_id"])
        art = ctrl.get_artifact(upload["artifact_id"])
        assert art["published_at"] > 0

    def test_publish_nonexistent(self, ctrl):
        result = ctrl.publish("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_publish_already_published(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(upload["session_id"])
        ctrl.publish(upload["artifact_id"])
        result = ctrl.publish(upload["artifact_id"])
        assert "error" in result
        assert "not publishable" in result["error"]

    def test_publish_deprecated_fails(self, ctrl):
        upload = ctrl.initiate_upload("old.txt")
        ctrl.finalize_upload(upload["session_id"])
        ctrl.publish(upload["artifact_id"])
        ctrl.deprecate(upload["artifact_id"])
        result = ctrl.publish(upload["artifact_id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# Deprecate
# ---------------------------------------------------------------------------

class TestDeprecate:
    def test_deprecate(self, ctrl):
        upload = ctrl.initiate_upload("old.yaml")
        ctrl.finalize_upload(upload["session_id"])
        ctrl.publish(upload["artifact_id"])
        result = ctrl.deprecate(
            upload["artifact_id"], reason="superseded", deprecator="admin",
        )
        assert result["status"] == "DEPRECATED"

    def test_deprecate_nonexistent(self, ctrl):
        result = ctrl.deprecate("nonexistent")
        assert "error" in result

    def test_deprecate_draft(self, ctrl):
        upload = ctrl.initiate_upload("draft.txt")
        result = ctrl.deprecate(upload["artifact_id"])
        assert result["status"] == "DEPRECATED"


# ---------------------------------------------------------------------------
# Get / List
# ---------------------------------------------------------------------------

class TestQuery:
    def test_get_artifact_found(self, ctrl):
        upload = ctrl.initiate_upload("test.txt", "DOCUMENT", uploaded_by="dev")
        art = ctrl.get_artifact(upload["artifact_id"])
        assert art is not None
        assert art["name"] == "test.txt"
        assert art["uploaded_by"] == "dev"

    def test_get_artifact_not_found(self, ctrl):
        assert ctrl.get_artifact("nonexistent") is None

    def test_get_artifact_metadata_parsed(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        art = ctrl.get_artifact(upload["artifact_id"])
        assert isinstance(art["metadata"], dict)

    def test_list_all_artifacts(self, ctrl):
        ctrl.initiate_upload("a.txt")
        ctrl.initiate_upload("b.bin")
        assert len(ctrl.list_artifacts()) == 2

    def test_list_by_status(self, ctrl):
        u1 = ctrl.initiate_upload("a.txt")
        ctrl.initiate_upload("b.txt")
        ctrl.finalize_upload(u1["session_id"])
        ctrl.publish(u1["artifact_id"])
        drafts = ctrl.list_artifacts(status="DRAFT")
        published = ctrl.list_artifacts(status="PUBLISHED")
        assert len(drafts) == 1
        assert len(published) == 1

    def test_list_by_type(self, ctrl):
        ctrl.initiate_upload("a.txt", "DOCUMENT")
        ctrl.initiate_upload("b.bin", "BINARY")
        docs = ctrl.list_artifacts(artifact_type="DOCUMENT")
        assert len(docs) == 1
        assert docs[0]["artifact_type"] == "DOCUMENT"

    def test_list_respects_limit(self, ctrl):
        for i in range(10):
            ctrl.initiate_upload(f"f{i}.txt")
        assert len(ctrl.list_artifacts(limit=3)) == 3

    def test_list_combined_filters(self, ctrl):
        ctrl.initiate_upload("a.txt", "DOCUMENT")
        ctrl.initiate_upload("b.bin", "BINARY")
        result = ctrl.list_artifacts(status="DRAFT", artifact_type="DOCUMENT")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

class TestVersions:
    def test_get_versions(self, ctrl):
        ctrl.initiate_upload("dataset.csv", "DATASET")
        ctrl.initiate_upload("dataset.csv", "DATASET")
        versions = ctrl.get_versions("dataset.csv")
        assert len(versions) == 2

    def test_get_versions_empty(self, ctrl):
        versions = ctrl.get_versions("nonexistent.csv")
        assert versions == []

    def test_versions_ordered_by_version(self, ctrl):
        ctrl.initiate_upload("file.txt")
        ctrl.initiate_upload("file.txt")
        versions = ctrl.get_versions("file.txt")
        assert versions[0]["version"] <= versions[1]["version"]


# ---------------------------------------------------------------------------
# Upload session
# ---------------------------------------------------------------------------

class TestUploadSession:
    def test_get_session(self, ctrl):
        upload = ctrl.initiate_upload("test.txt")
        session = ctrl.get_upload_session(upload["session_id"])
        assert session is not None
        assert session["artifact_id"] == upload["artifact_id"]

    def test_get_session_not_found(self, ctrl):
        assert ctrl.get_upload_session("nonexistent") is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty_stats(self, ctrl):
        stats = ctrl.get_stats()
        assert stats["total_artifacts"] == 0
        assert stats["by_status"] == {}
        assert stats["by_type"] == {}

    def test_stats_with_data(self, ctrl):
        ctrl.initiate_upload("a.yaml", "CONFIG")
        ctrl.initiate_upload("b.yaml", "CONFIG")
        ctrl.initiate_upload("c.bin", "BINARY")
        stats = ctrl.get_stats()
        assert stats["total_artifacts"] == 3
        assert stats["by_status"]["DRAFT"] == 3
        assert stats["by_type"]["CONFIG"] == 2
        assert stats["by_type"]["BINARY"] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_initiate_emits(self, ctrl_with_events):
        ctrl, events = ctrl_with_events
        ctrl.initiate_upload("test.txt")
        assert any("upload_initiated" in e.topic for e in events)

    def test_finalize_emits(self, ctrl_with_events):
        ctrl, events = ctrl_with_events
        u = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(u["session_id"])
        assert any("upload_finalized" in e.topic for e in events)

    def test_publish_emits(self, ctrl_with_events):
        ctrl, events = ctrl_with_events
        u = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(u["session_id"])
        ctrl.publish(u["artifact_id"])
        assert any("artifact_published" in e.topic for e in events)

    def test_deprecate_emits(self, ctrl_with_events):
        ctrl, events = ctrl_with_events
        u = ctrl.initiate_upload("test.txt")
        ctrl.finalize_upload(u["session_id"])
        ctrl.publish(u["artifact_id"])
        ctrl.deprecate(u["artifact_id"])
        assert any("artifact_deprecated" in e.topic for e in events)

    def test_no_event_bus_no_crash(self, ctrl):
        ctrl.initiate_upload("test.txt")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_returns_same(self):
        a1 = get_artifact_control()
        a2 = get_artifact_control()
        assert a1 is a2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_uploads(self, ctrl):
        errors = []
        results = []

        def upload(idx):
            try:
                r = ctrl.initiate_upload(f"file_{idx}.txt", uploaded_by=f"user_{idx}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=upload, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert ctrl.get_stats()["total_artifacts"] == 20

    def test_concurrent_publish(self, ctrl):
        errors = []
        u = ctrl.initiate_upload("shared.txt")
        ctrl.finalize_upload(u["session_id"])
        barrier = threading.Barrier(3)

        def try_publish():
            barrier.wait()
            try:
                ctrl.publish(u["artifact_id"], publisher="t")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=try_publish) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        art = ctrl.get_artifact(u["artifact_id"])
        assert art["status"] == "PUBLISHED"
