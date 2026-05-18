from __future__ import annotations

import json

import pytest

from sylion.security.key_store_unified import KeyStoreUnified
from sylion.security.secret_lifecycle import (
    SecretLifecyclePolicy,
    SecretLifecycleService,
    SecretLifecycleViolation,
    load_secret_lifecycle_policy,
)


def _service(now: float = 1000.0) -> tuple[SecretLifecycleService, KeyStoreUnified]:
    store = KeyStoreUnified(":memory:", backend="memory")
    policy = SecretLifecyclePolicy(
        backend="sops",
        rotation_period_days=90,
        strict_external_backend=True,
    )
    return SecretLifecycleService(store=store, policy=policy, clock=lambda: now), store


def test_policy_accepts_sops_backend_for_staging():
    policy = load_secret_lifecycle_policy({
        "SYLION_AEIS_ENV": "staging",
        "SYLION_SECRETS_BACKEND": "sops",
        "SYLION_SECRETS_ROTATION_DAYS": "90",
    })

    assert policy.validate() == []


def test_policy_rejects_plaintext_backend_for_production():
    policy = load_secret_lifecycle_policy({
        "SYLION_AEIS_ENV": "production",
        "SYLION_SECRETS_BACKEND": "plaintext",
    })

    failures = policy.validate()

    assert any("staging/production require" in item for item in failures)
    assert any("not production-safe" in item for item in failures)


def test_add_validate_rotate_dummy_flow_returns_no_plaintext():
    service, store = _service()

    result = service.run_dummy_flow(
        name="AEIS_DUMMY_ROTATION_SECRET",
        initial_value="fixture-initial-value",
        rotated_value="fixture-rotated-value",
    )

    assert result["status"] == "pass"
    assert result["final_version"] == 2
    assert result["rotation_period_days"] == 90

    encoded = json.dumps(result)
    assert "fixture-initial-value" not in encoded
    assert "fixture-rotated-value" not in encoded
    assert store.get("AEIS_DUMMY_ROTATION_SECRET") == "fixture-rotated-value"


def test_lifecycle_validate_marks_overdue_rotation():
    service, _store = _service(now=1000.0)
    service.add_secret("AEIS_ROTATION_DUE", "fixture-value")
    later = 1000.0 + (91 * 24 * 60 * 60)
    overdue = SecretLifecycleService(
        store=service._store,  # noqa: SLF001 - same in-memory store for clock test
        policy=SecretLifecyclePolicy(
            backend="sops",
            rotation_period_days=90,
            strict_external_backend=True,
        ),
        clock=lambda: later,
    )

    result = overdue.validate_secret("AEIS_ROTATION_DUE")

    assert result["valid"] is False
    assert result["rotation_due"] is True
    assert "rotation_due" in result["failures"]


def test_lifecycle_records_safe_audit_actions():
    service, store = _service()

    service.run_dummy_flow(
        name="AEIS_AUDITED_SECRET",
        initial_value="fixture-initial-value",
        rotated_value="fixture-rotated-value",
    )

    actions = [row["action"] for row in store.audit_log("AEIS_AUDITED_SECRET")]

    assert "lifecycle.add" in actions
    assert "lifecycle.validate" in actions
    assert "lifecycle.rotate" in actions
    assert "rotate" in actions


def test_lifecycle_rejects_unsafe_policy():
    store = KeyStoreUnified(":memory:", backend="memory")
    service = SecretLifecycleService(
        store=store,
        policy=SecretLifecyclePolicy(
            backend="file",
            rotation_period_days=120,
            strict_external_backend=True,
        ),
    )

    with pytest.raises(SecretLifecycleViolation):
        service.add_secret("AEIS_BAD_POLICY", "fixture-value")
