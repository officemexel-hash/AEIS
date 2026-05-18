"""Phase 3 W2.2 - production-mode fail-fast startup checks.

Runs at FastAPI startup (lifespan). When ``SYLION_AEIS_ENV=production``,
asserts that none of the well-known dev defaults survived into the
environment. When ``SYLION_AEIS_ENV`` is ``staging`` or ``production``,
asserts that the runtime is configured for PostgreSQL via asyncpg.
Dev / test continue to work without any env vars set.

Fail-fast philosophy: a dev default in prod is a *configuration*
incident, not a runtime defect - refuse to boot rather than serve
forgeable signatures or unencrypted vault data.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from sylion.security.secret_lifecycle import load_secret_lifecycle_policy

log = logging.getLogger("sylion.security.startup_check")

# Mirror of the in-code defaults we must never ship with.
# Keep this list in sync with the modules that own each default;
# a leak here is the *only* place we encode the dev-default value
# explicitly outside its origin file.
_FORBIDDEN_DEFAULTS: dict[str, tuple[str, ...]] = {
    # operator_mobile signing — see sylion/operator_mobile/bridge.py:68
    "SYLION_MOBILE_SIGNING_SECRET": ("operator-mobile-dev-secret",),
    # key vault encryption — see sylion/security/key_vault.py:54
    "SYLION_VAULT_SECRET": (
        "sylion-vault-default-secret-key-change-me",
        # Pre-Phase-3 default kept in git history; reject anyway.
        "sylion-default-secret",
    ),
}

# Vars that MUST be set in production (any value is fine; emptiness is
# the failure mode). Add to this list as new prod-required secrets land.
_REQUIRED_IN_PRODUCTION: tuple[str, ...] = (
    "SYLION_VAULT_SECRET",
    "SYLION_MOBILE_SIGNING_SECRET",
)

# Vars that MUST NOT be set to a "disabled" value in production. The
# value-checks here mirror the runtime bypass parsers exactly, so we
# refuse boot iff the flag would *actually* disable the protection at
# request time. A leftover env from tests or a developer's terminal
# carrying into a prod deploy is the threat model.
_FORBIDDEN_IN_PRODUCTION: dict[str, tuple[str, ...]] = {
    # rbac.py / rbac_enforcement.py both check `strip() == "1"` only.
    "SYLION_RBAC_DISABLED": ("1",),
    # rate_limit.py checks this flag before all accounting.
    "SYLION_RATE_LIMIT_DISABLED": ("1",),
}

_STRICT_DB_ENVS: frozenset[str] = frozenset({"staging", "production"})
_POSTGRES_ASYNC_PREFIX = "postgresql+asyncpg://"


@dataclass
class StartupCheckResult:
    env: str
    failures: list[str]

    @property
    def ok(self) -> bool:
        return not self.failures


def is_production() -> bool:
    """True iff SYLION_AEIS_ENV is exactly 'production' (case-insensitive)."""
    return os.environ.get("SYLION_AEIS_ENV", "").strip().lower() == "production"


def _runtime_env(e: dict[str, str]) -> str:
    return (e.get("SYLION_AEIS_ENV", "") or "").strip().lower() or "dev"


def _configured_db_url(e: dict[str, str]) -> str:
    return (e.get("SYLION_DB_URL") or e.get("DATABASE_URL") or "").strip()


def _configured_db_mode(e: dict[str, str]) -> str:
    explicit = (e.get("SYLION_DB_MODE", "") or "").strip().lower()
    if explicit:
        return explicit
    if _configured_db_url(e).startswith(_POSTGRES_ASYNC_PREFIX):
        return "postgres"
    return "sqlite"


def _configured_cache_url(e: dict[str, str]) -> str:
    return (e.get("SYLION_CACHE_URL") or "").strip()


def check_secrets(env: dict[str, str] | None = None) -> StartupCheckResult:
    """Run the prod-mode default-secret audit.

    Pure function: pass ``env`` for testability; defaults to
    ``os.environ``. Returns ``StartupCheckResult`` — caller decides
    whether to raise.
    """
    e = env if env is not None else dict(os.environ)
    current_env = _runtime_env(e)

    failures: list[str] = []
    if current_env == "production":
        for var in _REQUIRED_IN_PRODUCTION:
            raw = (e.get(var, "") or "").strip()
            if not raw:
                failures.append(f"{var}: required in production but unset/empty")
                continue
            forbidden = _FORBIDDEN_DEFAULTS.get(var, ())
            if raw in forbidden:
                failures.append(
                    f"{var}: matches forbidden dev default - rotate before deploying"
                )

        for var, forbidden_values in _FORBIDDEN_IN_PRODUCTION.items():
            raw = (e.get(var, "") or "").strip()
            if raw in forbidden_values:
                failures.append(
                    f"{var}={raw} disables a security guard in production "
                    f"- unset before deploying"
                )

    if current_env in _STRICT_DB_ENVS:
        db_mode = _configured_db_mode(e)
        db_url = _configured_db_url(e)
        if db_mode != "postgres":
            failures.append(
                "SYLION_DB_MODE: staging/production require postgres; "
                f"got {db_mode or 'unset'}"
            )
        if not db_url:
            failures.append(
                "SYLION_DB_URL or DATABASE_URL: required in staging/production"
            )
        elif not db_url.startswith(_POSTGRES_ASYNC_PREFIX):
            failures.append(
                "SYLION_DB_URL or DATABASE_URL: must start with "
                f"{_POSTGRES_ASYNC_PREFIX} in staging/production"
            )

        secret_policy = load_secret_lifecycle_policy(e)
        for failure in secret_policy.validate():
            failures.append(f"SYLION_SECRETS_BACKEND: {failure}")

        cache_url = _configured_cache_url(e)
        if not cache_url or cache_url.lower() == "memory":
            failures.append(
                "SYLION_CACHE_URL: staging/production require Redis cache "
                "for global rate limiting"
            )
        elif not cache_url.lower().startswith(("redis://", "rediss://")):
            failures.append(
                "SYLION_CACHE_URL: must start with redis:// or rediss:// "
                "in staging/production"
            )

    return StartupCheckResult(env=current_env, failures=failures)


class StartupSecretsViolation(RuntimeError):
    """Raised when prod-mode startup detects an unsafe default."""


def assert_safe_to_serve(env: dict[str, str] | None = None) -> None:
    """Raise StartupSecretsViolation if production mode has unsafe defaults.

    Wire from app.py lifespan() before any request handler runs. In dev
    this is a no-op.
    """
    result = check_secrets(env)
    if not result.ok:
        # Log structured, then raise — operator gets both UI + logs.
        for line in result.failures:
            log.error("startup_check FAIL: %s", line)
        raise StartupSecretsViolation(
            "startup blocked by production safety check; failures: "
            + "; ".join(result.failures)
        )
    if result.env == "production":
        log.info("startup_check: production secret check PASS")
