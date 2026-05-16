"""SYLION AEIS v2 - Audit Profile Mode (W14 round_meta BE-4).

Round-meta-orchestration enabler. When ``SYLION_AUDIT_PROFILE_ID`` is set
the runtime resolves DB / log / evidence / audit-chain paths into an
isolated per-audit subtree so an external auditor can run a clean
human-like simulation without colliding with operator data.

Layout (relative to repo root - parents[3] from this file)::

    data/audit/<id>/aeis_clean.db          # SYLION_DB_PATH override
    logs/audit/<id>/<module>.log           # operational logs
    evidence/audit/<id>/                   # evidence pack root
    src/sylion-pipeline/sylion/logs/audit/<id>/*.jsonl   # audit chains

Resolution rules:

* ``SYLION_AUDIT_PROFILE_ID`` empty/unset -> defaults preserved (legacy
  ``data/aeis.db`` / ``sylion/logs/v2``). Operator data stays untouched.
* ``SYLION_AUDIT_PROFILE_ID`` set -> resolve_*_path() returns the
  audit-isolated path, auto-creating parent directories on first
  access.

Public surface (what callers import):

* :func:`get_audit_profile_id` -> ``str`` (empty when not in audit mode).
* :func:`is_audit_mode` -> ``bool`` -- convenience predicate.
* :func:`resolve_db_path` -> :class:`Path` -- audit DB or default.
* :func:`resolve_log_dir` -> :class:`Path` -- audit log root or default.
* :func:`resolve_evidence_dir` -> :class:`Path` -- audit evidence root.
* :func:`resolve_audit_chain_dir` -> :class:`Path` -- audit-chain JSONL root.
* :func:`ensure_audit_layout` -> ``None`` -- mkdir -p every directory.

This module is intentionally side-effect free at import time so it can
be safely imported by tests and the CLI initializer (see
``scripts/v2/audit_profile_init.py``).
"""
from __future__ import annotations

import os
from pathlib import Path

#: Env var that toggles audit profile mode. Empty/unset means "no audit".
ENV_AUDIT_PROFILE_ID: str = "SYLION_AUDIT_PROFILE_ID"

#: Repo root resolved relative to this file. ``parents[3]`` from
#: ``src/sylion-pipeline/sylion/aeis_v2/audit_profile.py`` lands on
#: ``src/sylion-pipeline``. ``parents[5]`` lands on the repo root.
_REPO_ROOT: Path = Path(__file__).resolve().parents[4]

#: Pipeline package root (where ``sylion/`` lives).
_PIPELINE_ROOT: Path = Path(__file__).resolve().parents[2]

#: Default DB path when not in audit mode (legacy SYLION_DB_PATH default).
_DEFAULT_DB_PATH: Path = _REPO_ROOT / "data" / "aeis.db"

#: Default log root for v2 chains (mirrors metrics_v2_routes._DEFAULT_LOG_ROOT).
_DEFAULT_LOG_ROOT: Path = _PIPELINE_ROOT / "logs" / "v2"

#: Default evidence root.
_DEFAULT_EVIDENCE_ROOT: Path = _REPO_ROOT / "evidence"

#: Default audit chain JSONL root (same as v2 logs).
_DEFAULT_AUDIT_CHAIN_ROOT: Path = _PIPELINE_ROOT / "sylion" / "logs" / "v2"


def get_audit_profile_id() -> str:
    """Return the active audit profile id, or empty string when unset."""
    return (os.environ.get(ENV_AUDIT_PROFILE_ID) or "").strip()


def is_audit_mode() -> bool:
    """``True`` when ``SYLION_AUDIT_PROFILE_ID`` is set to a non-empty value."""
    return bool(get_audit_profile_id())


#: Names that map onto the canonical clean DB (shared store). Anything else
#: keeps its basename so module-specific DBs stay isolated.
_SHARED_DB_NAMES: frozenset[str] = frozenset({
    "sylion_aeis.db",      # legacy operator DB (most modules)
    "aeis.db",             # alternate legacy basename
    "aeis_clean.db",       # already-redirected basename (idempotency)
})


def _redirect_db_to_audit(default: Path, audit_id: str) -> Path:
    """Map ``default`` onto an audit-isolated location.

    Shared-store DBs collapse onto ``aeis_clean.db``. Module-specific DBs
    preserve their basename so e.g. ``project_freeze.db`` -> ``audit/<id>/
    project_freeze.db``. Callers receive an absolute path inside
    ``data/audit/<id>/``.
    """
    base = default.name or "aeis_clean.db"
    target_name = "aeis_clean.db" if base in _SHARED_DB_NAMES else base
    return _REPO_ROOT / "data" / "audit" / audit_id / target_name


def resolve_db_path(default: Path | str | None = None) -> Path:
    """Return the SQLite DB path for the current process.

    Behavior:

    * No audit profile set -> ``default`` unchanged (or legacy
      ``data/aeis.db`` when ``default`` is ``None``).
    * Audit profile set + ``default is None`` -> ``data/audit/<id>/
      aeis_clean.db`` (the canonical shared clean DB).
    * Audit profile set + shared default (``sylion_aeis.db`` /
      ``aeis.db``) -> redirected to ``data/audit/<id>/aeis_clean.db``.
    * Audit profile set + module-specific default (any other basename)
      -> ``data/audit/<id>/<basename>`` (filename preserved).
    * In-memory paths (``:memory:``) are returned untouched in every
      mode so unit tests stay isolated.

    The parent directory is auto-created on first call so callers can
    immediately ``sqlite3.connect`` without an explicit ``mkdir``.
    """
    audit_id = get_audit_profile_id()
    # ":memory:" is a SQLite sentinel, not a filesystem path -- never redirect.
    if default is not None and str(default) == ":memory:":
        return Path(":memory:")
    if audit_id:
        if default is None:
            target = _REPO_ROOT / "data" / "audit" / audit_id / "aeis_clean.db"
        else:
            target = _redirect_db_to_audit(Path(default), audit_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    if default is None:
        return _DEFAULT_DB_PATH
    return Path(default)


def resolve_log_dir(default: Path | str | None = None) -> Path:
    """Return the root directory for operational module logs."""
    audit_id = get_audit_profile_id()
    if audit_id:
        return _REPO_ROOT / "logs" / "audit" / audit_id
    if default is None:
        return _DEFAULT_LOG_ROOT
    return Path(default)


def resolve_evidence_dir(default: Path | str | None = None) -> Path:
    """Return the evidence pack root directory."""
    audit_id = get_audit_profile_id()
    if audit_id:
        return _REPO_ROOT / "evidence" / "audit" / audit_id
    if default is None:
        return _DEFAULT_EVIDENCE_ROOT
    return Path(default)


def resolve_audit_chain_dir(default: Path | str | None = None) -> Path:
    """Return the directory holding hash-chained audit JSONL files."""
    audit_id = get_audit_profile_id()
    if audit_id:
        return _PIPELINE_ROOT / "sylion" / "logs" / "audit" / audit_id
    if default is None:
        return _DEFAULT_AUDIT_CHAIN_ROOT
    return Path(default)


def resolve_audit_chain_path(filename: str, default_dir: Path | str | None = None) -> Path:
    """Return a JSONL chain path in the active audit root.

    Producers should use this helper instead of hard-coding ``logs/v2`` so
    audit-mode health, metrics, and emitted evidence all read the same files.
    """
    return resolve_audit_chain_dir(default_dir) / filename


def ensure_audit_layout() -> dict[str, str]:
    """Create every audit-mode directory if missing.

    No-op when not in audit mode. Returns a dict mapping logical name ->
    posix path string for diagnostics / metadata emission.
    """
    layout: dict[str, str] = {
        "db": resolve_db_path().as_posix(),
        "log_dir": resolve_log_dir().as_posix(),
        "evidence_dir": resolve_evidence_dir().as_posix(),
        "audit_chain_dir": resolve_audit_chain_dir().as_posix(),
    }
    if not is_audit_mode():
        return layout
    # Create parent dirs (DB lives inside its parent; the rest are dirs).
    resolve_db_path().parent.mkdir(parents=True, exist_ok=True)
    resolve_log_dir().mkdir(parents=True, exist_ok=True)
    resolve_evidence_dir().mkdir(parents=True, exist_ok=True)
    resolve_audit_chain_dir().mkdir(parents=True, exist_ok=True)
    return layout


__all__ = [
    "ENV_AUDIT_PROFILE_ID",
    "ensure_audit_layout",
    "get_audit_profile_id",
    "is_audit_mode",
    "resolve_audit_chain_dir",
    "resolve_audit_chain_path",
    "resolve_db_path",
    "resolve_evidence_dir",
    "resolve_log_dir",
]
