"""Tests for sylion.cognitive.feedback_collector"""

import json
import time
import threading

import pytest

from sylion.cognitive.feedback_collector import (
    FeedbackCollector,
    get_feedback_collector,
    reset_feedback_collector,
)
from sylion.core.event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def fc(bus):
    return FeedbackCollector(":memory:", event_bus=bus)


# --- Basic CRUD ---

class TestFeedbackCollector:

    def test_submit_feedback_basic(self, fc):
        r = fc.submit_feedback("u1", 5)
        assert r["feedback_id"]
        assert r["user_id"] == "u1"
        assert r["rating"] == 5
        assert r["category"] == "general"
        assert r["created_at"] > 0

    def test_submit_feedback_all_fields(self, fc):
        r = fc.submit_feedback("u1", 4, category="accuracy", comment="great",
                               session_id="s1", message_id="m1",
                               metadata={"key": "val"})
        assert r["session_id"] == "s1"
        assert r["message_id"] == "m1"
        assert r["comment"] == "great"
        assert r["category"] == "accuracy"

    def test_submit_feedback_invalid_rating_low(self, fc):
        with pytest.raises(ValueError, match="1-5"):
            fc.submit_feedback("u1", 0)

    def test_submit_feedback_invalid_rating_high(self, fc):
        with pytest.raises(ValueError, match="1-5"):
            fc.submit_feedback("u1", 6)

    def test_submit_feedback_invalid_category(self, fc):
        with pytest.raises(ValueError, match="Invalid category"):
            fc.submit_feedback("u1", 3, category="bogus")

    def test_get_feedback_exists(self, fc):
        r = fc.submit_feedback("u1", 4)
        got = fc.get_feedback(r["feedback_id"])
        assert got["feedback_id"] == r["feedback_id"]
        assert got["rating"] == 4

    def test_get_feedback_not_found(self, fc):
        assert fc.get_feedback("nonexistent") is None

    def test_list_feedback_all(self, fc):
        fc.submit_feedback("u1", 5)
        fc.submit_feedback("u2", 3)
        result = fc.list_feedback()
        assert len(result) == 2

    def test_list_feedback_by_user(self, fc):
        fc.submit_feedback("u1", 5)
        fc.submit_feedback("u2", 3)
        result = fc.list_feedback(user_id="u1")
        assert len(result) == 1
        assert result[0]["user_id"] == "u1"

    def test_list_feedback_by_session(self, fc):
        fc.submit_feedback("u1", 5, session_id="s1")
        fc.submit_feedback("u1", 4, session_id="s2")
        result = fc.list_feedback(session_id="s1")
        assert len(result) == 1

    def test_list_feedback_by_category(self, fc):
        fc.submit_feedback("u1", 5, category="accuracy")
        fc.submit_feedback("u1", 3, category="speed")
        result = fc.list_feedback(category="accuracy")
        assert len(result) == 1
        assert result[0]["category"] == "accuracy"

    def test_list_feedback_min_rating(self, fc):
        fc.submit_feedback("u1", 2)
        fc.submit_feedback("u1", 4)
        result = fc.list_feedback(min_rating=3)
        assert all(r["rating"] >= 3 for r in result)

    def test_list_feedback_max_rating(self, fc):
        fc.submit_feedback("u1", 2)
        fc.submit_feedback("u1", 4)
        result = fc.list_feedback(max_rating=3)
        assert all(r["rating"] <= 3 for r in result)

    def test_list_feedback_since(self, fc):
        old = time.time() - 1000
        fc.submit_feedback("u1", 5)
        result = fc.list_feedback(since=old)
        assert len(result) >= 1

    def test_list_feedback_since_future(self, fc):
        future = time.time() + 1000
        fc.submit_feedback("u1", 5)
        result = fc.list_feedback(since=future)
        assert len(result) == 0

    def test_list_feedback_limit(self, fc):
        for i in range(10):
            fc.submit_feedback("u1", 3)
        result = fc.list_feedback(limit=5)
        assert len(result) == 5

    def test_list_feedback_ordering(self, fc):
        fc.submit_feedback("u1", 3)
        time.sleep(0.01)
        fc.submit_feedback("u1", 5)
        result = fc.list_feedback()
        assert result[0]["rating"] == 5  # newest first

    def test_delete_feedback(self, fc):
        r = fc.submit_feedback("u1", 5)
        assert fc.delete_feedback(r["feedback_id"]) is True
        assert fc.get_feedback(r["feedback_id"]) is None

    def test_delete_feedback_not_found(self, fc):
        assert fc.delete_feedback("nonexistent") is False

    # --- Average rating ---

    def test_get_average_rating_basic(self, fc):
        fc.submit_feedback("u1", 5)
        fc.submit_feedback("u1", 3)
        result = fc.get_average_rating()
        assert result["average"] == 4.0
        assert result["count"] == 2

    def test_get_average_rating_by_user(self, fc):
        fc.submit_feedback("u1", 5)
        fc.submit_feedback("u2", 1)
        result = fc.get_average_rating(user_id="u1")
        assert result["average"] == 5.0
        assert result["count"] == 1

    def test_get_average_rating_by_category(self, fc):
        fc.submit_feedback("u1", 5, category="accuracy")
        fc.submit_feedback("u1", 1, category="speed")
        result = fc.get_average_rating(category="accuracy")
        assert result["average"] == 5.0

    def test_get_average_rating_distribution(self, fc):
        fc.submit_feedback("u1", 1)
        fc.submit_feedback("u1", 3)
        fc.submit_feedback("u1", 5)
        result = fc.get_average_rating()
        assert result["distribution"][1] == 1
        assert result["distribution"][3] == 1
        assert result["distribution"][5] == 1

    def test_get_average_rating_empty(self, fc):
        result = fc.get_average_rating()
        assert result["average"] == 0.0
        assert result["count"] == 0
        assert result["distribution"] == {}

    # --- Stats ---

    def test_get_feedback_stats(self, fc):
        fc.submit_feedback("u1", 5, category="accuracy")
        fc.submit_feedback("u1", 3, category="speed")
        stats = fc.get_feedback_stats()
        assert stats["total"] == 2
        assert "accuracy" in stats["by_category"]
        assert stats["by_rating"][5] == 1
        assert stats["by_rating"][3] == 1

    def test_get_feedback_stats_avg_overall(self, fc):
        fc.submit_feedback("u1", 4)
        fc.submit_feedback("u1", 2)
        stats = fc.get_feedback_stats()
        assert stats["avg_overall"] == 3.0

    # --- Summaries ---

    def test_generate_summary(self, fc):
        fc.submit_feedback("u1", 5, category="accuracy")
        result = fc.generate_summary("2026-01-01", category="accuracy")
        assert result["period"] == "2026-01-01"
        assert result["category"] == "accuracy"

    def test_generate_summary_upsert(self, fc):
        fc.submit_feedback("u1", 5, category="general")
        r1 = fc.generate_summary("2026-01-01")
        fc.submit_feedback("u2", 1, category="general")
        r2 = fc.generate_summary("2026-01-01")
        assert r1["summary_id"] == r2["summary_id"]

    def test_get_summaries(self, fc):
        fc.generate_summary("2026-01-01")
        fc.generate_summary("2026-01-02")
        summaries = fc.get_summaries()
        assert len(summaries) == 2

    def test_get_summaries_by_category(self, fc):
        fc.generate_summary("2026-01-01", category="accuracy")
        fc.generate_summary("2026-01-01", category="speed")
        summaries = fc.get_summaries(category="accuracy")
        assert len(summaries) == 1

    # --- Trend ---

    def test_get_trend(self, fc):
        fc.submit_feedback("u1", 5)
        trend = fc.get_trend(days=7)
        assert isinstance(trend, list)

    def test_get_trend_with_category(self, fc):
        fc.submit_feedback("u1", 5, category="accuracy")
        trend = fc.get_trend(days=7, category="accuracy")
        assert isinstance(trend, list)

    # --- EventBus ---

    def test_event_bus_submitted(self, fc, bus):
        fc.submit_feedback("u1", 5)
        events = bus.query(topic="feedback.submitted")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["rating"] == 5
        assert payload["user_id"] == "u1"

    def test_event_bus_multiple_submissions(self, fc, bus):
        fc.submit_feedback("u1", 5)
        fc.submit_feedback("u2", 3)
        events = bus.query(topic="feedback.submitted")
        assert len(events) == 2

    # --- Singleton ---

    def test_singleton_get(self):
        reset_feedback_collector()
        a = get_feedback_collector()
        b = get_feedback_collector()
        assert a is b

    def test_singleton_reset(self):
        reset_feedback_collector()
        a = get_feedback_collector()
        b = reset_feedback_collector()
        assert a is not b

    # --- Thread safety ---

    def test_concurrent_submissions(self, fc):
        results = []
        errors = []

        def submit(n):
            try:
                r = fc.submit_feedback(f"u{n}", (n % 5) + 1)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        all_fb = fc.list_feedback(limit=100)
        assert len(all_fb) == 20

    # --- Metadata ---

    def test_metadata_stored_as_json(self, fc):
        r = fc.submit_feedback("u1", 5, metadata={"foo": "bar"})
        got = fc.get_feedback(r["feedback_id"])
        assert got["metadata"] == {"foo": "bar"}

    def test_metadata_none(self, fc):
        r = fc.submit_feedback("u1", 5)
        got = fc.get_feedback(r["feedback_id"])
        assert got["metadata"] is None

    # --- All valid categories ---

    def test_all_valid_categories(self, fc):
        for cat in ("general", "accuracy", "speed", "relevance", "quality"):
            r = fc.submit_feedback("u1", 4, category=cat)
            assert r["category"] == cat

    # --- All valid ratings ---

    def test_all_valid_ratings(self, fc):
        for rating in range(1, 6):
            r = fc.submit_feedback("u1", rating)
            assert r["rating"] == rating

    # --- Edge cases ---

    def test_list_feedback_empty(self, fc):
        assert fc.list_feedback() == []

    def test_get_summaries_empty(self, fc):
        assert fc.get_summaries() == []

    def test_get_feedback_stats_empty(self, fc):
        stats = fc.get_feedback_stats()
        assert stats["total"] == 0
        assert stats["avg_overall"] == 0.0

    def test_no_event_bus(self):
        fc_no_bus = FeedbackCollector(":memory:", event_bus=None)
        r = fc_no_bus.submit_feedback("u1", 5)
        assert r["feedback_id"]
