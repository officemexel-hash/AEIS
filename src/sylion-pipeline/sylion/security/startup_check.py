"""Phase 3 W2.2 — production-mode secret-default fail-fast checks.

Runs at FastAPI startup (lifespan). When ``SYLION_AEIS_ENV=production``,
asserts that none of the well-known dev defaults survived into the
environment. Dev / test continue to work without any env vars set —
this guard only fires in prod mode.

Fail-fast philosophy: a dev default in prod is a *configuration*
incident, not a runtime defect — refuse to boot rather than serve
forgeable signatures or unencrypted vault data.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

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
}


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


def check_secrets(env: dict[str, str] | None = None) -> StartupCheckResult:
    """Run the prod-mode default-secret audit.

    Pure function: pass ``env`` for testability; defaults to
    ``os.environ``. Returns ``StartupCheckResult`` — caller decides
    whether to raise.
    """
    e = env if env is not None else dict(os.environ)
    current_env = (e.get("SYLION_AEIS_ENV", "") or "").strip().lower()
    if current_env != "production":
        return StartupCheckResult(env=current_env or "dev", failures=[])

    failures: list[str] = []
    for var in _REQUIRED_IN_PRODUCTION:
        raw = (e.get(var, "") or "").strip()
        if not raw:
            failures.append(f"{var}: required in production but unset/empty")
            continue
        forbidden = _FORBIDDEN_DEFAULTS.get(var, ())
        if raw in forbidden:
            failures.append(
                f"{var}: matches forbidden dev default — rotate before deploying"
            )

    for var, forbidden_values in _FORBIDDEN_IN_PRODUCTION.items():
        raw = (e.get(var, "") or "").strip()
        if raw in forbidden_values:
            failures.append(
                f"{var}={raw} disables a security guard in production "
                f"— unset before deploying"
            )

    return StartupCheckResult(env="production", failures=failures)


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
            "production startup blocked by secret-default check; failures: "
            + "; ".join(result.failures)
        )
    if result.env == "production":
        log.info("startup_check: production secret check PASS")
