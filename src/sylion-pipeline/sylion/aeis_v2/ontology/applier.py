"""W15 G1 DDL Applier — apply manifest-generated DDL to PostgreSQL.

PDF reference: §3.4 G1 — schema compiler MVP, applier wykonuje DDL
faktycznie (a nie tylko renderuje string jak Phase 0).

Charter ``docs/v2/charters/W15_ontology_runtime.md`` G1 deliverables:
operator wywołuje ``POST /api/v1/ontology/types/{type_id}/apply``
i system idempotentnie aplikuje DDL do schematu ``sylion_v2``.

Behavior:
- PG reachable + non-dry-run -> wykonuje wszystkie DDL statement w jednej
  transakcji, ``ApplyResult.applied = True``.
- PG unreachable -> ``preview_only = True``, brak side-effectu, rationale
  PL informuje operatora że trzeba sprawdzić połączenie.
- ``dry_run = True`` -> jak unreachable: bez side-effectu, ale rationale
  rozróżnia od PG-down (operator wybrał świadomie).
- DDL error mid-flight -> commit nie wystąpił (whole-transaction rollback
  via context manager), ``applied = False``, ``error`` wypełnione,
  ``statements_executed`` mówi do którego stmt udało się dojść.

Idempotencja: opiera się na ``CREATE ... IF NOT EXISTS`` w compilerze.
Dwukrotne ``apply_manifest(m)`` na tym samym typie nie zmienia stanu PG
(no-op po pierwszym razie).

G2 wniesie: dedykowany v2 pool, audit log per-apply (kto, kiedy, sha256
DDL), per-statement savepoints (zamiast all-or-nothing transakcji),
auto-detection drift między manifestem a runtime schematem.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sylion.aeis_v2.ontology.compiler import SchemaCompiler, compile_to_ddl
from sylion.aeis_v2.ontology.manifest import ObjectTypeManifest

log = logging.getLogger(__name__)


# P0-1 fix: cap concurrent applier connections at 2 of the v1 advisor
# pool's 10 slots. Two parallel POST /apply calls won't starve v1
# advisor handlers (which still have 8 slots free worst case).
APPLIER_POOL_SEMAPHORE = threading.BoundedSemaphore(value=2)

# Per-session DDL timeout — never hold a slot for more than 60s if a
# DDL hangs (network drop, lock wait). Without this, the slot stays
# locked until TCP keepalive notices, ~2 hours.
APPLIER_STATEMENT_TIMEOUT_MS = 60_000


# Audit log path (relative to repo root, created on first write).
# parents[3] resolves: applier.py -> ontology -> aeis_v2 -> sylion -> sylion-pipeline/
AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "apply_audit.jsonl"
)


# P0-4 fix: differentiate "transient infrastructure" errors from "actual
# DDL bug" errors so the operator UI can branch on prefix
# (``connectivity:`` vs ``ddl:``). Connectivity-class exceptions mean
# "retry, the database wobbled"; DDL-class exceptions mean "the manifest
# itself produced bad SQL — operator must inspect the compiled DDL".
# psycopg may not be installed in every deployment (SQLite-only smoke
# tests, CI without the advisor extra) so we fall back to stdlib-only
# exceptions in that case.
try:
    import psycopg as _psycopg
    _CONNECTIVITY_EXCS: tuple[type[BaseException], ...] = (
        _psycopg.OperationalError,
        _psycopg.InterfaceError,
        BrokenPipeError,
        ConnectionError,
        OSError,
    )
except ImportError:
    _CONNECTIVITY_EXCS = (BrokenPipeError, ConnectionError, OSError)


def _ddl_sha256(statements: list[str]) -> str:
    """Hash the canonical DDL bytestring for change detection across applies.

    Concatenates each statement followed by ``\\n`` (UTF-8) and returns the
    hex digest. Stable across runs for the same compile output, so the
    operator can ask "did the DDL for customer.yaml change since last
    apply?" by comparing two ``ddl_sha256`` audit rows.
    """
    h = hashlib.sha256()
    for stmt in statements:
        h.update(stmt.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _emit_apply_audit(
    *,
    type_id: str,
    actor: str,
    statements_total: int,
    statements_executed: int,
    applied: bool,
    preview_only: bool,
    ddl_sha256: str,
    error: str | None,
    rationale: str,
) -> None:
    """Write a structured audit row to the JSONL log + event bus.

    Format (one JSON object per line):
      {ts, type_id, actor, applied, preview_only, statements_total,
       statements_executed, ddl_sha256, error, rationale}

    Failure to write the audit log is itself logged at WARNING level but
    does NOT raise — apply must complete even if audit infra is down.
    Phase 0: file-only fallback. G2 will move to a PG audit table; the
    file remains as fallback when PG unreachable.
    """
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type_id": type_id,
        "actor": actor,
        "applied": applied,
        "preview_only": preview_only,
        "statements_total": statements_total,
        "statements_executed": statements_executed,
        "ddl_sha256": ddl_sha256,
        "error": error,
        "rationale": rationale[:200],   # truncate to keep line manageable
    }
    # 1. JSONL log (append-only)
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "apply_audit: failed to write JSONL (%s)", exc,
        )
    # 2. Event bus (best-effort; signature mismatch is fine — debug-level swallow)
    try:
        from sylion.core.event_bus import get_event_bus
        bus = get_event_bus()
        if hasattr(bus, "publish"):
            bus.publish("aeis.v2.ontology.apply", row)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).debug(
            "apply_audit: event bus emit failed (%s)", exc,
        )


@dataclass
class ApplyResult:
    """Result of applying a manifest's DDL to a target database.

    Attributes
    ----------
    type_id:
        The ``metadata.id`` of the manifest applied (or attempted).
    applied:
        ``True`` iff every statement executed and the transaction committed.
    preview_only:
        ``True`` when no DDL touched the database — either because PG is
        unreachable or because the caller passed ``dry_run=True``.
    statements_executed:
        Count of statements that ran before either success or error.
    statements_total:
        Total compiled DDL statements for the manifest.
    error:
        Stringified PG error, prefix-tagged so the operator UI can branch
        on failure class. ``None`` on clean run or when
        ``preview_only=True``. P0-4 introduced two prefixes:

        - ``"connectivity: <ExcType>: <msg>"`` — transient infrastructure
          failure (psycopg ``OperationalError``/``InterfaceError``,
          ``BrokenPipeError``, ``ConnectionError``, ``OSError``). UI
          should suggest "retry — the database wobbled".
        - ``"ddl: <ExcType>: <msg>"`` — the manifest's compiled DDL
          itself is bad (syntax error, constraint conflict, missing
          extension). UI should surface for operator inspection of the
          compiled DDL artifact; retrying without changing the manifest
          will fail again.
    rationale:
        Human-readable PL message intended for the operator UI.
    """

    type_id: str
    applied: bool
    preview_only: bool
    statements_executed: int = 0
    statements_total: int = 0
    error: str | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "applied": self.applied,
            "preview_only": self.preview_only,
            "statements_executed": self.statements_executed,
            "statements_total": self.statements_total,
            "error": self.error,
            "rationale": self.rationale,
        }


def _get_pg_connection():
    """Return a psycopg pool or ``None`` if PG unreachable / pool init failed.

    W15 G2 phase 1: prefer the dedicated v2 pool
    (``sylion.aeis_v2.db.get_v2_pool``) with stricter defaults (max=20,
    REPEATABLE READ on DDL, statement_timeout=60000ms). Fall back to the
    v1 advisor pool (``sylion.aeis.advisor._db.get_pool``) when the v2
    pool returns ``None`` (e.g. PG unreachable from v2's perspective) or
    the v2 module is not importable (packaging defect). The v1 path
    retains its fail-fast ``PGUnreachable`` plumbing with a 60s
    negative-cache, so we don't pay 2s per call when PG is offline.

    Operator rollback: set ``SYLION_USE_V2_POOL=0`` to force the v1
    advisor pool path immediately - useful when the v2 pool misbehaves
    and we need the legacy code path without redeploying.

    Three log severity gradients (mirrored across both pools - applier
    keeps using the same operator UI hooks):

    - ``ImportError`` (advisor pool module missing): log.error, return
      ``None``. Packaging defect - preview-only.
    - ``PGUnreachable`` (typed exception from v1 ``_db``): log.info,
      return ``None``. Routine - PG offline.
    - any other ``Exception``: log.error with ``exc_info=True``, return
      ``None``. Unexpected - pool init blew up.

    The actual decision logic lives in
    ``sylion.aeis_v2.db.get_pool_with_fallback`` so the cost-ledger PG
    layer can share the same code path; this wrapper exists so legacy
    callers / monkeypatching tests still see ``applier._get_pg_connection``.
    """
    from sylion.aeis_v2.db import get_pool_with_fallback
    return get_pool_with_fallback(logger=log)


def _execute_statements_with_conn(
    conn, statements: list[str],
) -> tuple[int, str | None]:
    """Run every DDL statement on an existing connection (no commit, no release).

    Helper extracted from ``_execute_statements`` so both the per-manifest
    path and the atomic-batch path can share the inner loop. The caller
    owns the connection lifecycle (acquire, commit/rollback, release) and
    the semaphore. This function only opens a cursor and runs statements.

    Returns ``(executed_count, error_or_None)``. The error string is
    prefix-tagged per P0-4: ``"connectivity: <ExcType>: <msg>"`` for
    transient infra failures (broken pipe, server kill, OS-level network
    error) vs ``"ddl: <ExcType>: <msg>"`` for actual SQL/DDL bugs that
    operators must inspect.
    """
    executed = 0
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
                executed += 1
    except _CONNECTIVITY_EXCS as exc:
        return executed, f"connectivity: {type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — DDL/SQL error class
        return executed, f"ddl: {type(exc).__name__}: {exc}"
    return executed, None


def _execute_statements(pool, statements: list[str]) -> tuple[int, str | None]:
    """Run every DDL statement in one transaction.

    P0-1 fix: budgeted with ``APPLIER_POOL_SEMAPHORE`` so the applier
    never holds more than 2 of the v1 advisor pool's 10 slots concurrently
    (avoids starving v1 advisor handlers under parallel apply traffic).
    Per-session ``statement_timeout`` is set so a stuck DDL doesn't
    permanently hold a pool slot.

    Returns ``(executed_count, error_or_None)``. On error the
    ``with pool.connection()`` context manager rolls back automatically
    (psycopg semantics), so ``executed_count`` is the number that ran
    before the failure even though none of them are committed. The
    ``SET LOCAL statement_timeout`` issued first is NOT counted in
    ``executed`` (it's session config, not part of the manifest's DDL).
    """
    executed = 0
    # Block here if 2 applier connections are already in flight.
    with APPLIER_POOL_SEMAPHORE:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Per-session DDL timeout (don't count toward executed total —
                    # this is infrastructure config, not manifest DDL).
                    cur.execute(
                        f"SET LOCAL statement_timeout = '{APPLIER_STATEMENT_TIMEOUT_MS}ms'"
                    )
                executed, error = _execute_statements_with_conn(conn, statements)
                if error is not None:
                    return executed, error
                conn.commit()
        except _CONNECTIVITY_EXCS as exc:
            # P0-4: pool/connection-acquire-time connectivity failure.
            return executed, f"connectivity: {type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 — pool/commit-level DDL error
            return executed, f"ddl: {type(exc).__name__}: {exc}"
    return executed, None


def apply_manifest(
    manifest: ObjectTypeManifest,
    *,
    dry_run: bool = False,
    actor: str = "system",
) -> ApplyResult:
    """Compile manifest, apply DDL to PG (or preview when unreachable).

    Args:
        manifest: validated ObjectTypeManifest from registry.
        dry_run: when True, returns preview without touching PG even if reachable.
        actor: who triggered the apply — recorded in the JSONL audit log
            alongside ``ts``, ``ddl_sha256``, and the result fields. P0-3
            wired this through; G2 will move the audit row to a PG table.

    Returns:
        ApplyResult with execution details. ``preview_only=True`` when
        PG unreachable OR ``dry_run=True``.

    Side effect:
        Appends one JSON line to ``logs/v2/apply_audit.jsonl`` (created on
        first write) and best-effort publishes to the ``sylion.core``
        event bus on topic ``aeis.v2.ontology.apply``.
    """
    type_id = manifest.metadata.id
    artifacts = compile_to_ddl(manifest)
    statements = artifacts.all_statements()
    total = len(statements)
    ddl_hash = _ddl_sha256(statements)

    if dry_run:
        result = ApplyResult(
            type_id=type_id,
            applied=False,
            preview_only=True,
            statements_total=total,
            rationale="Dry run — DDL nie zostal wykonany; podglad dostepny w /ddl.",
        )
        _emit_apply_audit(
            type_id=type_id, actor=actor, statements_total=total,
            statements_executed=0, applied=False, preview_only=True,
            ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
        )
        return result

    pool = _get_pg_connection()
    if pool is None:
        result = ApplyResult(
            type_id=type_id,
            applied=False,
            preview_only=True,
            statements_total=total,
            rationale=(
                f"PostgreSQL niedostepny - DDL skompilowany ({total} stmt) ale nie "
                "zaaplikowany. Sprawdz polaczenie i sprobuj ponownie."
            ),
        )
        _emit_apply_audit(
            type_id=type_id, actor=actor, statements_total=total,
            statements_executed=0, applied=False, preview_only=True,
            ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
        )
        return result

    executed, error = _execute_statements(pool, statements)
    if error is not None:
        log.exception(
            "ontology applier: DDL failed for %s at stmt %d/%d",
            type_id, executed + 1, total,
        )
        result = ApplyResult(
            type_id=type_id,
            applied=False,
            preview_only=False,
            statements_executed=executed,
            statements_total=total,
            error=error,
            rationale=(
                f"DDL wykonany do {executed}/{total} statement gdy wystapil blad. "
                "Transakcja wycofana. Szczegoly w error."
            ),
        )
        _emit_apply_audit(
            type_id=type_id, actor=actor, statements_total=total,
            statements_executed=executed, applied=False, preview_only=False,
            ddl_sha256=ddl_hash, error=error, rationale=result.rationale,
        )
        return result

    result = ApplyResult(
        type_id=type_id,
        applied=True,
        preview_only=False,
        statements_executed=executed,
        statements_total=total,
        rationale=f"Zaaplikowano {executed} statement do schematu sylion_v2.",
    )
    _emit_apply_audit(
        type_id=type_id, actor=actor, statements_total=total,
        statements_executed=executed, applied=True, preview_only=False,
        ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
    )
    return result


def apply_all(
    manifests: list[ObjectTypeManifest],
    *,
    dry_run: bool = False,
    actor: str = "system",
    atomic_batch: bool = False,
) -> list[ApplyResult]:
    """Apply many manifests sequentially, optionally as one atomic transaction.

    Args:
        manifests: validated ObjectTypeManifests from registry.
        dry_run: when True, no DDL touches PG; per-manifest preview rows.
        actor: who triggered the apply — recorded in the JSONL audit log.
        atomic_batch: when False (default), each manifest gets its own
            transaction (legacy behavior — mid-batch failure leaves earlier
            manifests committed). When True, the entire batch runs inside
            a single outer transaction: ANY failure rolls back everything,
            so the database is never left in a half-applied "Frankenstein"
            state. The atomic-batch path also acquires
            ``APPLIER_POOL_SEMAPHORE`` once for the whole loop (not per
            manifest) and emits a final ``type_id="<batch>"`` summary
            audit row in addition to the N per-manifest rows.

    Returns:
        Per-manifest ``ApplyResult`` list. In atomic-batch mode, on first
        failure: every result has ``applied=False``; results before the
        failure show their committed-state-but-rolled-back ``executed``
        count, results after are skipped (statements_executed=0,
        rationale="Pominiety - batch przerwany przed tym manifestem.").

    Phase 0 keeps it simple — sequential, no parallelism. The single
    ``SchemaCompiler`` is reused so the shared bootstrap (extensions,
    helpers) is only emitted in the first manifest.
    """
    if atomic_batch and not dry_run:
        return _apply_all_atomic(manifests, actor=actor)

    out: list[ApplyResult] = []
    compiler = SchemaCompiler()

    for m in manifests:
        artifacts = compiler.compile(m)
        statements = artifacts.all_statements()
        total = len(statements)
        type_id = m.metadata.id
        ddl_hash = _ddl_sha256(statements)

        if dry_run:
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=True,
                statements_total=total,
                rationale="Dry run.",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=0, applied=False, preview_only=True,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
            out.append(result)
            continue

        pool = _get_pg_connection()
        if pool is None:
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=True,
                statements_total=total,
                rationale="PG niedostepny.",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=0, applied=False, preview_only=True,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
            out.append(result)
            continue

        executed, error = _execute_statements(pool, statements)
        if error is not None:
            log.exception(
                "ontology applier: DDL failed for %s at stmt %d/%d",
                type_id, executed + 1, total,
            )
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=False,
                statements_executed=executed,
                statements_total=total,
                error=error,
                rationale=f"Blad przy stmt {executed + 1}/{total}.",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=executed, applied=False, preview_only=False,
                ddl_sha256=ddl_hash, error=error, rationale=result.rationale,
            )
            out.append(result)
        else:
            result = ApplyResult(
                type_id=type_id,
                applied=True,
                preview_only=False,
                statements_executed=executed,
                statements_total=total,
                rationale=f"Zaaplikowano {executed} stmt.",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=executed, applied=True, preview_only=False,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
            out.append(result)
    return out


def _apply_all_atomic(
    manifests: list[ObjectTypeManifest],
    *,
    actor: str,
) -> list[ApplyResult]:
    """Atomic-batch path for ``apply_all(atomic_batch=True)``.

    Wraps the entire batch in ONE outer transaction with ONE semaphore
    acquire and ONE ``SET LOCAL statement_timeout`` at session start.
    Mid-batch failure rolls back the whole transaction (no partial
    commits). Manifests after the failure get a "skipped" result with
    ``applied=False`` and a clear rationale.

    Audit trail:
      - One per-manifest row (applied=False on rollback, success/fail
        captured in ``error``).
      - One final batch-summary row with ``type_id="<batch>"``,
        ``applied=<bool aggregate>`` (True iff every manifest succeeded
        AND commit happened), ``error=<first_error_or_None>``.
    """
    out: list[ApplyResult] = []
    compiler = SchemaCompiler()

    # Pre-compile every manifest so we have ddl_hash + statements for the
    # audit trail even on early failure (the first commit-or-bust runs
    # them in order; pre-compile doesn't talk to PG so it's cheap).
    compiled: list[tuple[ObjectTypeManifest, list[str], str]] = []
    for m in manifests:
        artifacts = compiler.compile(m)
        statements = artifacts.all_statements()
        ddl_hash = _ddl_sha256(statements)
        compiled.append((m, statements, ddl_hash))

    pool = _get_pg_connection()
    if pool is None:
        # PG unreachable -> every manifest in batch becomes preview-only.
        # No outer transaction even attempted; emit one audit row per
        # manifest plus a batch-summary row for forensics.
        for m, statements, ddl_hash in compiled:
            type_id = m.metadata.id
            total = len(statements)
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=True,
                statements_total=total,
                rationale="PG niedostepny - batch atomowy nieuruchomiony.",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=0, applied=False, preview_only=True,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
            out.append(result)
        _emit_apply_audit(
            type_id="<batch>", actor=actor,
            statements_total=sum(len(s) for _, s, _ in compiled),
            statements_executed=0, applied=False, preview_only=True,
            ddl_sha256="", error=None,
            rationale=(
                f"Batch atomowy przerwany - PG niedostepny "
                f"({len(compiled)} manifestow w batch)."
            ),
        )
        return out

    # Outer atomic transaction: ONE semaphore acquire, ONE connection,
    # ONE commit-or-rollback for the entire batch.
    first_error: str | None = None
    failed_index: int | None = None
    per_manifest_executed: list[int] = [0] * len(compiled)
    committed = False

    with APPLIER_POOL_SEMAPHORE:
        try:
            with pool.connection() as conn:
                # Issue SET LOCAL once at session start.
                with conn.cursor() as cur:
                    cur.execute(
                        f"SET LOCAL statement_timeout = '{APPLIER_STATEMENT_TIMEOUT_MS}ms'"
                    )

                for idx, (_m, statements, _hash) in enumerate(compiled):
                    executed, error = _execute_statements_with_conn(
                        conn, statements,
                    )
                    per_manifest_executed[idx] = executed
                    if error is not None:
                        first_error = error
                        failed_index = idx
                        # Bail out — outer `with` triggers rollback.
                        raise _BatchAbort(error)

                conn.commit()
                committed = True
        except _BatchAbort:
            # Expected control-flow exception used to trigger rollback.
            # `first_error` and `failed_index` already set (already
            # prefix-tagged by _execute_statements_with_conn).
            pass
        except _CONNECTIVITY_EXCS as exc:
            # P0-4: pool/connection-acquire-time connectivity failure
            # outside the per-manifest loop (e.g. could not even open the
            # outer transaction).
            first_error = f"connectivity: {type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 — pool/commit-level DDL error
            first_error = f"ddl: {type(exc).__name__}: {exc}"
            # No manifest got a chance to run (or failed_index already set
            # if exception leaked from inside the loop).

    # Build per-manifest results from the recorded state.
    total_stmts = 0
    for idx, (m, statements, ddl_hash) in enumerate(compiled):
        type_id = m.metadata.id
        total = len(statements)
        total_stmts += total

        if committed:
            executed = per_manifest_executed[idx]
            result = ApplyResult(
                type_id=type_id,
                applied=True,
                preview_only=False,
                statements_executed=executed,
                statements_total=total,
                rationale=f"Zaaplikowano {executed} stmt (batch atomowy).",
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=executed, applied=True, preview_only=False,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
        elif failed_index is not None and idx < failed_index:
            # Ran successfully but rolled back when later manifest failed.
            executed = per_manifest_executed[idx]
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=False,
                statements_executed=executed,
                statements_total=total,
                error=None,
                rationale=(
                    "Batch atomowy wycofany - manifest wykonany ale nie "
                    "zatwierdzony (inny manifest w batch zawiodl)."
                ),
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=executed, applied=False, preview_only=False,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
        elif failed_index is not None and idx == failed_index:
            # The manifest whose DDL raised.
            executed = per_manifest_executed[idx]
            log.exception(
                "ontology applier: atomic batch failed at %s stmt %d/%d",
                type_id, executed + 1, total,
            )
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=False,
                statements_executed=executed,
                statements_total=total,
                error=first_error,
                rationale=(
                    f"Batch atomowy: blad przy stmt {executed + 1}/{total} "
                    "- caly batch wycofany."
                ),
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=executed, applied=False, preview_only=False,
                ddl_sha256=ddl_hash, error=first_error, rationale=result.rationale,
            )
        else:
            # Skipped — batch aborted before reaching this manifest, OR a
            # pool-level failure happened before the loop entered.
            result = ApplyResult(
                type_id=type_id,
                applied=False,
                preview_only=False,
                statements_executed=0,
                statements_total=total,
                error=None,
                rationale=(
                    "Pominiety - batch atomowy przerwany przed tym manifestem."
                ),
            )
            _emit_apply_audit(
                type_id=type_id, actor=actor, statements_total=total,
                statements_executed=0, applied=False, preview_only=False,
                ddl_sha256=ddl_hash, error=None, rationale=result.rationale,
            )
        out.append(result)

    # Final batch-summary audit row.
    aggregate_applied = committed and first_error is None
    if aggregate_applied:
        batch_rationale = (
            f"Batch atomowy zatwierdzony - {len(compiled)} manifestow zaaplikowanych."
        )
    elif first_error is not None:
        batch_rationale = (
            f"Batch atomowy wycofany - blad w manifeście "
            f"#{(failed_index or 0) + 1}/{len(compiled)}: {first_error[:100]}"
        )
    else:
        batch_rationale = "Batch atomowy nieuruchomiony - awaria infrastruktury."
    _emit_apply_audit(
        type_id="<batch>", actor=actor,
        statements_total=total_stmts,
        statements_executed=sum(per_manifest_executed),
        applied=aggregate_applied,
        preview_only=False,
        ddl_sha256="",
        error=first_error,
        rationale=batch_rationale,
    )
    return out


class _BatchAbort(Exception):
    """Internal sentinel used to short-circuit the atomic-batch loop.

    Raised when a manifest's DDL fails inside the outer transaction so the
    surrounding ``with pool.connection()`` triggers rollback. Caught at
    the same level — never escapes ``_apply_all_atomic``.
    """
