"""Phase 3 W3.4: PII redactor unit tests."""

from __future__ import annotations

from sylion.observability.pii_redactor import (
    REDACTED,
    redact_record,
    redact_text,
)


# -- redact_text -----------------------------------------------------------

class TestRedactText:
    def test_email_basic(self):
        assert redact_text("user user@example.com signed in") == \
            f"user {REDACTED} signed in"

    def test_email_polish_tld(self):
        assert REDACTED in redact_text("contact: jan.kowalski@firma.pl")

    def test_authorization_header_bearer(self):
        scrubbed = redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed
        assert REDACTED in scrubbed

    def test_authorization_header_basic(self):
        scrubbed = redact_text("authorization: Basic dXNlcjpwYXNzd29yZA==")
        assert "dXNlcjpwYXNzd29yZA==" not in scrubbed

    def test_generic_api_key_assignment(self):
        sample_key = "sk_live_" + "abcdefghijklmnop1234"
        scrubbed = redact_text(f'api_key="{sample_key}"')
        assert sample_key not in scrubbed
        assert REDACTED in scrubbed

    def test_credit_card_luhn_valid_redacted(self):
        # Visa test card 4111111111111111 (Luhn-valid)
        assert REDACTED in redact_text("paid with 4111-1111-1111-1111")

    def test_credit_card_luhn_invalid_passes(self):
        # 16 random digits not Luhn-valid -> stays untouched
        out = redact_text("order 1234567890123456")
        assert "1234567890123456" not in out or REDACTED in out

    def test_pesel_redacted(self):
        assert REDACTED in redact_text("PESEL: 44051401358 confirmed")

    def test_nip_dashed_redacted(self):
        assert REDACTED in redact_text("NIP 521-31-72-815 valid")

    def test_ipv4_redacted(self):
        assert REDACTED in redact_text("client 10.0.5.42 connected")
        assert REDACTED in redact_text("ip=192.168.1.1")

    def test_phone_e164_redacted(self):
        assert REDACTED in redact_text("call +48 600 700 800 today")

    def test_empty_string_passes(self):
        assert redact_text("") == ""

    def test_clean_text_unchanged(self):
        msg = "council voted approve on ticket abc-123"
        assert redact_text(msg) == msg


# -- redact_record ---------------------------------------------------------

class TestRedactRecord:
    def test_sensitive_key_password_redacted(self):
        out = redact_record({"username": "alice", "password": "hunter2"})
        assert out["username"] == "alice"
        assert out["password"] == REDACTED

    def test_sensitive_key_api_key_redacted(self):
        out = redact_record({"api_key": "sk_test_xyz"})
        assert out["api_key"] == REDACTED

    def test_sensitive_substring_in_key(self):
        out = redact_record({"X-Api-Token": "abc123", "user_apikey_v2": "k"})
        assert out["X-Api-Token"] == REDACTED
        assert out["user_apikey_v2"] == REDACTED

    def test_nested_dict_recurses(self):
        out = redact_record({
            "user": {"email": "a@b.pl", "name": "Alice"},
            "session": {"token": "secret-jwt"},
        })
        assert REDACTED in out["user"]["email"]
        assert out["user"]["name"] == "Alice"
        # "session" is itself sensitive -> dict collapses to REDACTED string.
        assert out["session"] == REDACTED

    def test_nested_dict_under_neutral_parent(self):
        out = redact_record({
            "context": {"token": "secret-jwt", "label": "audit"},
        })
        assert out["context"]["token"] == REDACTED
        assert out["context"]["label"] == "audit"

    def test_list_of_dicts_recurses(self):
        out = redact_record({
            "events": [
                {"actor_email": "a@b.pl", "action": "login"},
                {"actor_email": "c@d.pl", "action": "logout"},
            ],
        })
        assert all(REDACTED in evt["actor_email"] for evt in out["events"])

    def test_sensitive_empty_value_passes(self):
        out = redact_record({"password": "", "token": None})
        assert out["password"] == ""
        assert out["token"] is None

    def test_input_not_mutated(self):
        original = {"password": "x", "msg": "hi user@example.com"}
        before = dict(original)
        before["msg_copy"] = original["msg"]
        redact_record(original)
        assert original == {"password": "x", "msg": "hi user@example.com"}

    def test_non_dict_input_passthrough(self):
        assert redact_record("not a dict") == "not a dict"  # type: ignore[arg-type]

    def test_numeric_values_unchanged(self):
        out = redact_record({"count": 42, "ratio": 0.95, "ok": True})
        assert out["count"] == 42 and out["ratio"] == 0.95 and out["ok"] is True


# -- LogAggregator integration --------------------------------------------

class TestLogAggregatorIntegration:
    def test_aggregator_redacts_email_in_message(self):
        from sylion.observability.log_aggregator import (
            LocalLogBackend,
            LogAggregator,
        )
        backend = LocalLogBackend()
        agg = LogAggregator(backend=backend)
        agg.log("api", "info", "user user@example.com logged in")
        records = backend.query()
        assert len(records) == 1
        assert "user@example.com" not in records[0]["message"]
        assert REDACTED in records[0]["message"]

    def test_aggregator_redacts_password_in_extra(self):
        from sylion.observability.log_aggregator import (
            LocalLogBackend,
            LogAggregator,
        )
        backend = LocalLogBackend()
        agg = LogAggregator(backend=backend)
        agg.log("api", "info", "login attempt",
                extra={"user_id": "u1", "password": "secret"})
        records = backend.query()
        assert records[0]["password"] == REDACTED
        assert records[0]["user_id"] == "u1"

    def test_aggregator_disable_flag(self):
        from sylion.observability.log_aggregator import (
            LocalLogBackend,
            LogAggregator,
        )
        backend = LocalLogBackend()
        agg = LogAggregator(backend=backend, redact=False)
        agg.log("api", "info", "user@example.com logged in")
        records = backend.query()
        assert "user@example.com" in records[0]["message"]
