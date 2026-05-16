import json

from sylion.governance.purge_decision_log import PurgeDecisionLog, log_purge


def test_log_purge_builds_dataclass():
    entry = log_purge("u1", 1712345678.5, "admin", "gdpr")
    assert entry == PurgeDecisionLog("u1", 1712345678.5, "admin", "gdpr")


def test_to_jsonl_line_returns_json_string():
    raw = PurgeDecisionLog("u1", 1.25, "system", "retention").to_jsonl_line()
    assert json.loads(raw) == {"actor": "system", "reason": "retention", "ts": 1.25, "user_id": "u1"}


def test_from_jsonl_line_parses_back():
    raw = '{"user_id":"u1","ts":2.0,"actor":"ops","reason":"cleanup"}'
    assert PurgeDecisionLog.from_jsonl_line(raw) == PurgeDecisionLog("u1", 2.0, "ops", "cleanup")


def test_round_trip_with_newline():
    entry = PurgeDecisionLog("u2", 3.5, "cron", "expiry")
    assert PurgeDecisionLog.from_jsonl_line(entry.to_jsonl_line() + "\n") == entry
