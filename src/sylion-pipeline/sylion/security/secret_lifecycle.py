"""Production secret lifecycle policy and dummy flow.

This module is intentionally value-safe: public methods never return a
plaintext secret. The backing store may be in-memory in tests, but staging and
production policy only accept external secret backends such as SOPS or Vault.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from sylion.security.key_store_unified import KeyStoreUnified, get_key_store_unified

APPROVED_PRODUCTION_SECRET_BACKENDS: tuple[str, ...] = ("sops", "vault")
FORBIDDEN_SECRET_BACKENDS: tuple[str, ...] = (
    "env",
    "environment",
    "file",
    "key_vault",
    "memory",
    "plaintext",
    "secret_provider",
)
DEFAULT_ROTATION_DAYS = 90
_SECRET_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,127}$")


@dataclass(frozen=True)
class SecretLifecyclePolicy:
    backend: str
    rotation_period_days: int = DEFAULT_ROTATION_DAYS
    strict_external_backend: bool = False

    def validate(self) -> list[str]:
        backend = self.backend.strip().lower()
        failures: list[str] = []
        if not backend:
            failures.append("secret backend is required")
        if self.rotation_period_days <= 0:
            failures.append("secret rotation period must be positive")
        if self.rotation_period_days > DEFAULT_ROTATION_DAYS:
            failures.append("secret rotation period must be <= 90 days")
        if self.strict_external_backend and backend not in APPROVED_PRODUCTION_SECRET_BACKENDS:
            failures.append(
                "staging/production require SYLION_SECRETS_BACKEND to be "
                "one of: " + ", ".join(APPROVED_PRODUCTION_SECRET_BACKENDS)
            )
        if backend in FORBIDDEN_SECRET_BACKENDS and self.strict_external_backend:
            failures.append(f"secret backend {backend!r} is not production-safe")
        return failures


def _runtime_env(env: dict[str, str]) -> str:
    return (env.get("SYLION_AEIS_ENV", "") or "").strip().lower() or "dev"


def _parse_rotation_days(raw: str | None) -> int:
    if raw is None or not str(raw).strip():
        return DEFAULT_ROTATION_DAYS
    try:
        return int(str(raw).strip())
    except ValueError:
        return DEFAULT_ROTATION_DAYS + 1


def load_secret_lifecycle_policy(env: dict[str, str]) -> SecretLifecyclePolicy:
    runtime_env = _runtime_env(env)
    strict = runtime_env in {"staging", "production"}
    backend = (env.get("SYLION_SECRETS_BACKEND") or "").strip().lower()
    if not backend and not strict:
        backend = "memory"
    return SecretLifecyclePolicy(
        backend=backend,
        rotation_period_days=_parse_rotation_days(env.get("SYLION_SECRETS_ROTATION_DAYS")),
        strict_external_backend=strict,
    )


class SecretLifecycleViolation(ValueError):
    """Raised when a lifecycle operation violates the secret policy."""


class SecretLifecycleService:
    """Add, validate and rotate secrets through the unified key store."""

    def __init__(
        self,
        store: KeyStoreUnified | None = None,
        policy: SecretLifecyclePolicy | None = None,
        *,
        clock=time.time,
    ):
        self._store = store or get_key_store_unified()
        self._policy = policy or SecretLifecyclePolicy(backend="memory")
        self._clock = clock

    def _now(self) -> float:
        return float(self._clock())

    def _assert_policy(self) -> None:
        failures = self._policy.validate()
        if failures:
            raise SecretLifecycleViolation("; ".join(failures))

    @staticmethod
    def _validate_name(name: str) -> str:
        clean = name.strip()
        if not _SECRET_NAME_RE.match(clean):
            raise SecretLifecycleViolation(
                "secret name must be 3-128 chars and use letters, digits, _, ., :, -"
            )
        return clean

    @staticmethod
    def _assert_value(value: str) -> None:
        if not value:
            raise SecretLifecycleViolation("secret value must be non-empty")

    def add_secret(
        self,
        name: str,
        value: str,
        *,
        scope: str = "secrets",
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a secret and return only lifecycle metadata."""
        self._assert_policy()
        secret_name = self._validate_name(name)
        self._assert_value(value)
        now = self._now()
        rotation_seconds = self._policy.rotation_period_days * 24 * 60 * 60
        lifecycle_metadata = {
            "backend": self._policy.backend,
            "created_by": actor,
            "last_validated_at": None,
            "last_rotated_at": None,
            "next_rotation_due_at": now + rotation_seconds,
            "rotation_period_days": self._policy.rotation_period_days,
        }
        if metadata:
            lifecycle_metadata.update(metadata)
        record = self._store.put(
            secret_name,
            value,
            scope=scope,
            metadata=lifecycle_metadata,
            actor=actor,
        )
        self._store.record_audit(
            secret_name,
            "lifecycle.add",
            actor=actor,
            details={"scope": scope, "backend": self._policy.backend},
        )
        return {
            "secret_id": secret_name,
            "scope": record["scope"],
            "version": record["version"],
            "backend": self._policy.backend,
            "next_rotation_due_at": lifecycle_metadata["next_rotation_due_at"],
        }

    def validate_secret(self, name: str, *, actor: str = "system") -> dict[str, Any]:
        self._assert_policy()
        secret_name = self._validate_name(name)
        desc = self._store.describe(secret_name)
        if not desc:
            self._store.record_audit(secret_name, "lifecycle.validate_miss", actor=actor)
            return {"secret_id": secret_name, "valid": False, "reason": "not_found"}

        metadata = desc.get("metadata") or {}
        backend = str(metadata.get("backend") or self._policy.backend).lower()
        now = self._now()
        due_at = float(metadata.get("next_rotation_due_at") or 0)
        failures = []
        if backend not in APPROVED_PRODUCTION_SECRET_BACKENDS and self._policy.strict_external_backend:
            failures.append("backend_not_production_safe")
        if due_at and due_at <= now:
            failures.append("rotation_due")
        if int(metadata.get("rotation_period_days") or self._policy.rotation_period_days) > DEFAULT_ROTATION_DAYS:
            failures.append("rotation_period_too_long")

        result = {
            "secret_id": secret_name,
            "valid": not failures,
            "version": desc["version"],
            "backend": backend,
            "rotation_due": bool(due_at and due_at <= now),
            "next_rotation_due_at": due_at or None,
            "failures": failures,
        }
        self._store.record_audit(
            secret_name,
            "lifecycle.validate",
            actor=actor,
            details={"valid": result["valid"], "failures": failures},
        )
        return result

    def rotate_secret(
        self,
        name: str,
        new_value: str,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._assert_policy()
        secret_name = self._validate_name(name)
        self._assert_value(new_value)
        now = self._now()
        rotation_seconds = self._policy.rotation_period_days * 24 * 60 * 60
        result = self._store.rotate(
            secret_name,
            new_value,
            actor=actor,
            metadata_update={
                "backend": self._policy.backend,
                "last_rotated_at": now,
                "next_rotation_due_at": now + rotation_seconds,
                "rotation_period_days": self._policy.rotation_period_days,
            },
        )
        if result is None:
            return {"secret_id": secret_name, "rotated": False, "reason": "not_found"}
        self._store.record_audit(
            secret_name,
            "lifecycle.rotate",
            actor=actor,
            details={"version": result["version"], "backend": self._policy.backend},
        )
        return {
            "secret_id": secret_name,
            "rotated": True,
            "version": result["version"],
            "backend": self._policy.backend,
            "next_rotation_due_at": now + rotation_seconds,
        }

    def run_dummy_flow(
        self,
        *,
        name: str = "AEIS_DUMMY_ROTATION_SECRET",
        actor: str = "production-roadmap",
        initial_value: str = "fixture-initial-value",
        rotated_value: str = "fixture-rotated-value",
    ) -> dict[str, Any]:
        """Run add -> validate -> rotate -> validate without leaking values."""
        added = self.add_secret(name, initial_value, actor=actor)
        first_validation = self.validate_secret(name, actor=actor)
        rotated = self.rotate_secret(name, rotated_value, actor=actor)
        second_validation = self.validate_secret(name, actor=actor)
        passed = (
            added.get("version") == 1
            and first_validation.get("valid") is True
            and rotated.get("rotated") is True
            and rotated.get("version") == 2
            and second_validation.get("valid") is True
        )
        return {
            "status": "pass" if passed else "fail",
            "secret_id": name,
            "backend": self._policy.backend,
            "rotation_period_days": self._policy.rotation_period_days,
            "final_version": second_validation.get("version"),
            "steps": [
                {"name": "add", "ok": added.get("version") == 1},
                {"name": "validate_initial", "ok": first_validation.get("valid") is True},
                {"name": "rotate", "ok": rotated.get("rotated") is True},
                {"name": "validate_rotated", "ok": second_validation.get("valid") is True},
            ],
        }


__all__ = [
    "APPROVED_PRODUCTION_SECRET_BACKENDS",
    "DEFAULT_ROTATION_DAYS",
    "FORBIDDEN_SECRET_BACKENDS",
    "SecretLifecyclePolicy",
    "SecretLifecycleService",
    "SecretLifecycleViolation",
    "load_secret_lifecycle_policy",
]
