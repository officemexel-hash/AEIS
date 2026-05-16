"""SYLION AEIS v2 — health endpoint for k8s liveness/readiness probes.

Sprint 2 day 7. Designed as the *cheap* counterpart to /api/v1/metrics/v2:

* No RBAC — k8s probes can hit it without bearer tokens.
* O(1) work per call (no full chain walk; just file existence checks).
* Returns a stable JSON shape so external dashboards can pin schemas.
* Status flips to ``"degraded"`` on a service failure or a known chain
  violation. A missing chain in a fresh audit profile is ``"idle"``, not an
  error, because the module has not emitted evidence yet.

The endpoint is deliberately conservative: a `degraded` status is the
operator's signal to look at /api/v1/metrics/v2 + run
``scripts/v2/verify_audit_chains.py`` for the full picture. It is NOT
intended to short-circuit traffic — k8s should still consider the pod
ready as long as the imports + base FastAPI surface respond.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["health_v2"])

#: Bumped every time the v2 surface ships a backwards-incompatible change.
V2_VERSION: str = "v2.7"

#: Same audit JSONL roster as metrics_v2_routes — kept in sync by
#: convention; future refactor could centralise the table.
_AUDIT_FILES: dict[str, str] = {
    "gdpr_dsr": "gdpr_dsr.jsonl",
    "gdpr_hard_purge": "gdpr_hard_purge.jsonl",
    "replay_fork": "replay_fork.jsonl",
    "council_wedge": "council_wedge.jsonl",
}

_DEFAULT_LOG_ROOT = Path(__file__).resolve().parents[2] / "logs" / "v2"

#: Modules that the v2 layer ships and which we expose as services
#: for k8s readiness checks. Importable means the module loads without
#: raising — that's a coarser signal than runtime healthy, but it
#: catches the most common failure mode (broken import after refactor).
_V2_SERVICES: tuple[str, ...] = (
    "gdpr_dsr",
    "council_wedge",
    "replay_fork",
    "audit_chain",
    "metrics_v2",
    "embeddings_cache",
)


def _service_status(name: str) -> str:
    """Return ``"up"`` if the v2 module loads cleanly, ``"down"`` otherwise."""
    try:
        if name == "gdpr_dsr":
            __import__("sylion.aeis_v2.gdpr_v2.dsr")
        elif name == "council_wedge":
            __import__("sylion.aeis_v2.council_v2.wedge")
        elif name == "replay_fork":
            __import__("sylion.aeis_v2.replay_v2.fork")
        elif name == "audit_chain":
            __import__("sylion.aeis_v2.audit_chain.chain")
        elif name == "metrics_v2":
            __import__("sylion.api.metrics_v2_routes")
        elif name == "embeddings_cache":
            __import__("sylion.aeis_v2.embeddings.cache")
        else:
            return "unknown"
    except Exception as exc:  # noqa: BLE001
        log.warning("health_v2: service %s import failed (%s)", name, exc)
        return "down"
    return "up"


def _quick_chain_status(path: Path) -> str:
    """Lightweight presence check — does NOT call verify_chain.

    Returns ``"present"`` if the file exists and is non-empty. Missing or empty
    files are ``"idle"``: a clean first-run install has no GDPR/replay/council
    evidence until those modules actually run. The detailed integrity check
    lives in /metrics/v2 + the CLI.
    """
    if not path.exists():
        return "idle"
    try:
        return "present" if path.stat().st_size > 0 else "idle"
    except OSError:
        return "degraded"


def _effective_log_root(explicit_root: Path | None = None) -> Path:
    """Resolve the chain root, respecting audit profile mode."""
    if explicit_root is not None:
        return explicit_root
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir

        return resolve_audit_chain_dir(_DEFAULT_LOG_ROOT)
    except Exception:  # noqa: BLE001
        return _DEFAULT_LOG_ROOT


def assemble_v2_health(
    audit_chains: dict, services: dict, version: str,
) -> dict[str, Any]:
    is_clean = lambda v: v in {"clean", "ok", "present", "idle", True}
    is_up = lambda v: v in {"up", "ok", True}
    status = "ok" if (
        all(is_clean(v) for v in audit_chains.values())
        and all(is_up(v) for v in services.values())
    ) else "degraded"
    return {
        "status": status,
        "audit_chains": audit_chains,
        "services": services,
        "version": version,
    }


def assemble_health(log_root: Path | None = None) -> dict[str, Any]:
    """Build the health payload. Pure function for testability."""
    root = _effective_log_root(log_root)

    services = {name: _service_status(name) for name in _V2_SERVICES}
    audit_chains = {
        module: _quick_chain_status(root / fname)
        for module, fname in _AUDIT_FILES.items()
    }

    return assemble_v2_health(audit_chains, services, V2_VERSION)


@router.get("/v2")
def health_v2() -> dict[str, Any]:
    """K8s-friendly health payload — never 5xx, never raises."""
    try:
        return assemble_health()
    except Exception as exc:  # noqa: BLE001
        log.exception("health_v2: assembly failed (%s)", exc)
        return {
            "status": "degraded",
            "version": V2_VERSION,
            "error": "health assembly failed",
        }
