"""
Comprehensive tests for sylion.cognitive.idea_vault -- IdeaVault

Covers:
  - create_idea CRUD (create, get, list, update, delete)
  - Tag management (create with tags, filter by tag)
  - Voting (upvote, downvote, change vote, get_votes)
  - Status workflow and validation
  - search_ideas (title and description)
  - get_idea_stats aggregation
  - EventBus emission (idea_created, idea_updated, idea_voted, idea_status_changed)
  - Input validation
  - Edge cases (empty db, unknown IDs)
  - Thread safety
  - Singleton get/reset
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.idea_vault import (
    IdeaVault,
    get_idea_vault,
    reset_idea_vault,
    VALID_STATUSES,
    VALID_VOTE_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vault():
    return IdeaVault()


@pytest.fixture
def vault_with_bus():
    bus = EventBus()
    v = IdeaVault(event_bus=bus)
    return v, bus


# ===========================================================================
# 1. create_idea()
# ===========================================================================

class TestCreateIdea:

    def test_returns_idea_dict(self, vault):
        idea = vault.create_idea("Test idea")
        assert "idea_id" in idea
        assert len(idea["idea_id"]) == 32
        assert idea["title"] == "Test idea"
        assert idea["status"] == "draft"

    def test_description_and_author(self, vault):
        idea = vault.create_idea("Title", description="Desc", author="alice")
        assert idea["description"] == "Desc"
        assert idea["author"] == "alice"

    def test_with_tags(self, vault):
        idea = vault.create_idea("Title", tags=["ai", "ml"])
        assert "ai" in idea["tags"]
        assert "ml" in idea["tags"]
        assert len(idea["tags"]) == 2

    def test_empty_tags_list(self, vault):
        idea = vault.create_idea("Title", tags=[])
        assert idea["tags"] == []

    def test_none_tags(self, vault):
        idea = vault.create_idea("Title", tags=None)
        assert idea["tags"] == []

    def test_auto_timestamps(self, vault):
        before = time.time()
        idea = vault.create_idea("Title")
        after = time.time()
        assert before <= idea["created_at"] <= after
        assert before <= idea["updated_at"] <= after

    def test_upvotes_downvotes_init_zero(self, vault):
        idea = vault.create_idea("Title")
        assert idea["upvotes"] == 0
        assert idea["downvotes"] == 0

    def test_submit_workspace_empty_content_rejected(self, vault):
        with pytest.raises(ValueError, match="must not be empty"):
            vault.submit_idea("   ")


# ===========================================================================
# 2. get_idea()
# ===========================================================================

class TestGetIdea:

    def test_returns_created_idea(self, vault):
        created = vault.create_idea("Test", author="bob")
        fetched = vault.get_idea(created["idea_id"])
        assert fetched is not None
        assert fetched["title"] == "Test"
        assert fetched["author"] == "bob"

    def test_nonexistent_returns_none(self, vault):
        assert vault.get_idea("does_not_exist") is None

    def test_includes_tags(self, vault):
        created = vault.create_idea("Test", tags=["x", "y"])
        fetched = vault.get_idea(created["idea_id"])
        assert set(fetched["tags"]) == {"x", "y"}

    def test_includes_vote_counts(self, vault):
        created = vault.create_idea("Test")
        iid = created["idea_id"]
        vault.vote_idea(iid, "user1", "upvote")
        vault.vote_idea(iid, "user2", "upvote")
        vault.vote_idea(iid, "user3", "downvote")
        fetched = vault.get_idea(iid)
        assert fetched["upvotes"] == 2
        assert fetched["downvotes"] == 1


# ===========================================================================
# 3. update_idea()
# ===========================================================================

class TestUpdateIdea:

    def test_update_title(self, vault):
        created = vault.create_idea("Old title")
        result = vault.update_idea(created["idea_id"], title="New title")
        assert result["title"] == "New title"

    def test_update_description(self, vault):
        created = vault.create_idea("Title")
        result = vault.update_idea(created["idea_id"], description="New desc")
        assert result["description"] == "New desc"

    def test_update_author(self, vault):
        created = vault.create_idea("Title", author="old")
        result = vault.update_idea(created["idea_id"], author="new")
        assert result["author"] == "new"

    def test_update_status(self, vault):
        created = vault.create_idea("Title")
        result = vault.update_idea(created["idea_id"], status="approved")
        assert result["status"] == "approved"

    def test_update_positive_status_requires_human_gate_when_pending(self, vault):
        created = vault.create_idea("Title")
        gated = vault.request_approval(created["idea_id"], requested_by="alice")
        assert gated["human_gate_required"] == 1

        with pytest.raises(ValueError, match="HumanGate approval required"):
            vault.update_idea(created["idea_id"], status="accepted")

    def test_human_gate_decision_can_approve_gated_idea(self, vault):
        created = vault.create_idea("Title")
        vault.request_approval(created["idea_id"], requested_by="alice")

        approved = vault.record_human_gate_decision(
            created["idea_id"],
            "approved",
            reviewer="owner",
            rationale="direction accepted",
        )

        assert approved["status"] == "accepted"
        assert approved["human_gate_decision"] == "approved"

    def test_update_multiple_fields(self, vault):
        created = vault.create_idea("Old")
        result = vault.update_idea(
            created["idea_id"], title="New", description="D", status="submitted",
        )
        assert result["title"] == "New"
        assert result["description"] == "D"
        assert result["status"] == "submitted"

    def test_update_nonexistent_returns_none(self, vault):
        result = vault.update_idea("nonexistent", title="X")
        assert result is None

    def test_update_invalid_status_raises(self, vault):
        created = vault.create_idea("Title")
        with pytest.raises(ValueError, match="Invalid status"):
            vault.update_idea(created["idea_id"], status="invalid")

    def test_no_fields_returns_idea(self, vault):
        created = vault.create_idea("Title")
        result = vault.update_idea(created["idea_id"])
        assert result is not None
        assert result["title"] == "Title"


# ===========================================================================
# 4. delete_idea()
# ===========================================================================

class TestDeleteIdea:

    def test_delete_existing(self, vault):
        created = vault.create_idea("Title")
        assert vault.delete_idea(created["idea_id"]) is True

    def test_delete_nonexistent(self, vault):
        assert vault.delete_idea("nonexistent") is False

    def test_delete_removes_tags_and_votes(self, vault):
        created = vault.create_idea("Title", tags=["a"])
        iid = created["idea_id"]
        vault.vote_idea(iid, "user1", "upvote")
        vault.delete_idea(iid)
        assert vault.get_idea(iid) is None
        assert vault.get_votes(iid) == []


# ===========================================================================
# 5. list_ideas()
# ===========================================================================

class TestListIdeas:

    def test_list_all(self, vault):
        vault.create_idea("A")
        vault.create_idea("B")
        results = vault.list_ideas()
        assert len(results) == 2

    def test_filter_by_status(self, vault):
        i1 = vault.create_idea("A")
        vault.create_idea("B")
        vault.update_idea(i1["idea_id"], status="approved")
        results = vault.list_ideas(status="approved")
        assert len(results) == 1
        assert results[0]["status"] == "approved"

    def test_filter_by_tag(self, vault):
        vault.create_idea("A", tags=["ml"])
        vault.create_idea("B", tags=["nlp"])
        results = vault.list_ideas(tag="ml")
        assert len(results) == 1

    def test_filter_by_author(self, vault):
        vault.create_idea("A", author="alice")
        vault.create_idea("B", author="bob")
        results = vault.list_ideas(author="alice")
        assert len(results) == 1
        assert results[0]["author"] == "alice"

    def test_filter_combined(self, vault):
        i1 = vault.create_idea("A", author="alice", tags=["ml"])
        vault.create_idea("B", author="bob", tags=["ml"])
        vault.update_idea(i1["idea_id"], status="approved")
        results = vault.list_ideas(status="approved", tag="ml")
        assert len(results) == 1

    def test_limit(self, vault):
        for i in range(10):
            vault.create_idea(f"Idea {i}")
        results = vault.list_ideas(limit=3)
        assert len(results) == 3

    def test_empty_result(self, vault):
        vault.create_idea("A")
        results = vault.list_ideas(status="implemented")
        assert results == []

    def test_invalid_status_raises(self, vault):
        with pytest.raises(ValueError, match="Invalid status"):
            vault.list_ideas(status="bogus")


# ===========================================================================
# 6. vote_idea() and get_votes()
# ===========================================================================

class TestVoting:

    def test_upvote(self, vault):
        created = vault.create_idea("Title")
        result = vault.vote_idea(created["idea_id"], "user1", "upvote")
        assert result["vote_type"] == "upvote"

    def test_downvote(self, vault):
        created = vault.create_idea("Title")
        result = vault.vote_idea(created["idea_id"], "user1", "downvote")
        assert result["vote_type"] == "downvote"

    def test_change_vote(self, vault):
        created = vault.create_idea("Title")
        iid = created["idea_id"]
        vault.vote_idea(iid, "user1", "upvote")
        vault.vote_idea(iid, "user1", "downvote")
        fetched = vault.get_idea(iid)
        assert fetched["upvotes"] == 0
        assert fetched["downvotes"] == 1

    def test_multiple_users(self, vault):
        created = vault.create_idea("Title")
        iid = created["idea_id"]
        vault.vote_idea(iid, "u1", "upvote")
        vault.vote_idea(iid, "u2", "upvote")
        vault.vote_idea(iid, "u3", "downvote")
        fetched = vault.get_idea(iid)
        assert fetched["upvotes"] == 2
        assert fetched["downvotes"] == 1

    def test_get_votes_returns_list(self, vault):
        created = vault.create_idea("Title")
        iid = created["idea_id"]
        vault.vote_idea(iid, "u1", "upvote")
        votes = vault.get_votes(iid)
        assert len(votes) == 1
        assert votes[0]["user_id"] == "u1"

    def test_vote_nonexistent_idea_returns_none(self, vault):
        result = vault.vote_idea("nonexistent", "user1", "upvote")
        assert result is None

    def test_invalid_vote_type_raises(self, vault):
        created = vault.create_idea("Title")
        with pytest.raises(ValueError, match="Invalid vote_type"):
            vault.vote_idea(created["idea_id"], "u1", "meh")

    def test_get_votes_empty(self, vault):
        created = vault.create_idea("Title")
        assert vault.get_votes(created["idea_id"]) == []


# ===========================================================================
# 7. search_ideas()
# ===========================================================================

class TestSearchIdeas:

    def test_search_by_title(self, vault):
        vault.create_idea("Machine learning model")
        vault.create_idea("Data pipeline")
        results = vault.search_ideas("Machine")
        assert len(results) == 1
        assert results[0]["title"] == "Machine learning model"

    def test_search_by_description(self, vault):
        vault.create_idea("A", description="Uses neural networks")
        vault.create_idea("B", description="Simple rule engine")
        results = vault.search_ideas("neural")
        assert len(results) == 1

    def test_search_no_match(self, vault):
        vault.create_idea("A")
        results = vault.search_ideas("zzz_nonexistent_zzz")
        assert results == []

    def test_search_case_insensitive(self, vault):
        vault.create_idea("Machine Learning")
        results = vault.search_ideas("machine")
        assert len(results) == 1


# ===========================================================================
# 8. get_idea_stats()
# ===========================================================================

class TestGetIdeaStats:

    def test_empty_db(self, vault):
        stats = vault.get_idea_stats()
        assert stats["total"] == 0
        assert stats["total_votes"] == 0

    def test_counts_by_status(self, vault):
        i1 = vault.create_idea("A")
        i2 = vault.create_idea("B")
        vault.create_idea("C")
        vault.update_idea(i1["idea_id"], status="approved")
        vault.update_idea(i2["idea_id"], status="rejected")
        stats = vault.get_idea_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["draft"] == 1
        assert stats["by_status"]["approved"] == 1
        assert stats["by_status"]["rejected"] == 1

    def test_top_tags(self, vault):
        vault.create_idea("A", tags=["ml", "ai"])
        vault.create_idea("B", tags=["ml"])
        stats = vault.get_idea_stats()
        tag_names = [t[0] for t in stats["top_tags"]]
        assert "ml" in tag_names

    def test_total_votes(self, vault):
        i1 = vault.create_idea("A")
        i2 = vault.create_idea("B")
        vault.vote_idea(i1["idea_id"], "u1", "upvote")
        vault.vote_idea(i2["idea_id"], "u2", "downvote")
        stats = vault.get_idea_stats()
        assert stats["total_votes"] == 2

    def test_all_status_keys_present(self, vault):
        stats = vault.get_idea_stats()
        for s in VALID_STATUSES:
            assert s in stats["by_status"]


# ===========================================================================
# 9. Event emission
# ===========================================================================

class TestEventEmission:

    def test_create_emits_idea_created(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_created", lambda e: events.append(e))
        v.create_idea("Title", author="alice")
        assert len(events) == 1
        assert events[0].payload["title"] == "Title"
        assert events[0].payload["author"] == "alice"

    def test_update_emits_idea_updated(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_updated", lambda e: events.append(e))
        created = v.create_idea("Title")
        v.update_idea(created["idea_id"], title="New")
        assert len(events) == 1

    def test_status_change_emits_status_changed(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_status_changed", lambda e: events.append(e))
        created = v.create_idea("Title")
        v.update_idea(created["idea_id"], status="approved")
        assert len(events) == 1
        assert events[0].payload["old_status"] == "draft"
        assert events[0].payload["new_status"] == "approved"

    def test_same_status_no_event(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_status_changed", lambda e: events.append(e))
        created = v.create_idea("Title")
        v.update_idea(created["idea_id"], status="draft")
        assert len(events) == 0

    def test_vote_emits_idea_voted(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_voted", lambda e: events.append(e))
        created = v.create_idea("Title")
        v.vote_idea(created["idea_id"], "u1", "upvote")
        assert len(events) == 1
        assert events[0].payload["vote_type"] == "upvote"

    def test_no_bus_does_not_raise(self):
        v = IdeaVault()
        created = v.create_idea("Title")
        v.update_idea(created["idea_id"], title="New")
        v.vote_idea(created["idea_id"], "u1", "upvote")

    def test_event_source_module(self, vault_with_bus):
        v, bus = vault_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("idea_created", lambda e: events.append(e))
        v.create_idea("Title")
        assert events[0].source_module == "cognitive.idea_vault"


# ===========================================================================
# 10. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_creates(self):
        v = IdeaVault()
        results: list[dict] = []
        results_lock = threading.Lock()

        def create_idea(idx):
            idea = v.create_idea(f"Idea {idx}", author=f"user{idx}")
            with results_lock:
                results.append(idea)

        threads = [threading.Thread(target=create_idea, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        ids = [r["idea_id"] for r in results]
        assert len(set(ids)) == 20
        assert v.get_idea_stats()["total"] == 20

    def test_concurrent_votes(self):
        v = IdeaVault()
        created = v.create_idea("Title")
        iid = created["idea_id"]
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def vote(user_idx):
            try:
                v.vote_idea(iid, f"user{user_idx}", "upvote")
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=vote, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        fetched = v.get_idea(iid)
        assert fetched["upvotes"] == 20


# ===========================================================================
# 11. Singleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_same(self):
        reset_idea_vault()
        v1 = get_idea_vault()
        v2 = get_idea_vault()
        assert v1 is v2
        reset_idea_vault()

    def test_reset_creates_new(self):
        reset_idea_vault()
        v1 = get_idea_vault()
        reset_idea_vault()
        v2 = get_idea_vault()
        assert v1 is not v2
        reset_idea_vault()

    def test_singleton_with_custom_params(self):
        reset_idea_vault()
        bus = EventBus()
        v = get_idea_vault(event_bus=bus)
        assert v is not None
        reset_idea_vault()


# ===========================================================================
# 12. Status validation
# ===========================================================================

class TestStatusValidation:

    def test_all_valid_statuses(self, vault):
        for s in VALID_STATUSES:
            created = vault.create_idea("Title")
            result = vault.update_idea(created["idea_id"], status=s)
            assert result["status"] == s

    def test_invalid_status_message(self, vault):
        created = vault.create_idea("Title")
        with pytest.raises(ValueError) as exc_info:
            vault.update_idea(created["idea_id"], status="bad_status")
        assert "bad_status" in str(exc_info.value)

    def test_all_valid_vote_types(self, vault):
        created = vault.create_idea("Title")
        for vt in VALID_VOTE_TYPES:
            result = vault.vote_idea(created["idea_id"], f"user_{vt}", vt)
            assert result["vote_type"] == vt
