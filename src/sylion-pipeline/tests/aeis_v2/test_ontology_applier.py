"""Tests for sylion.aeis_v2.ontology.applier — W15 G1 DDL applier.

Covers:
- ``apply_manifest`` with ``dry_run=True`` returns preview-only result.
- PG unreachable -> applier falls back to preview-only without raising.
- PG reachable -> every compiled DDL statement is executed and committed.
- PG raises mid-flight -> result captures error, executed count, rationale.
- ``apply_all`` aggregates per-manifest results; per-type pool failures
  do not block subsequent manifests in the list.

Implementation notes:
- We don't connect to a real PostgreSQL — every test monkeypatches
  ``sylion.aeis_v2.ontology.applier._get_pg_connection`` to return a
  hand-rolled stub pool so we can observe execution and inject failures.
- Stubs implement only the slice of the psycopg API the applier touches:
  ``pool.connection() -> conn`` (context manager), ``conn.cursor()`` (also
  CM), ``cur.execute(stmt)``, and ``conn.commit()``.
"""
from __future__ import annotations

import pytest

from sylion.aeis_v2.ontology import (
    DedicatedColumn,
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
)
from sylion.aeis_v2.ontology import applier as applier_mod
from sylion.aeis_v2.ontology.applier import (
    ApplyResult,
    apply_all,
    apply_manifest,
)


# --------------------------------------------------------------------------
# Stubs — minimal psycopg pool/conn/cursor surface
# --------------------------------------------------------------------------


class _StubCursor:
    """Records every ``execute()`` call into the parent connection.

    P0-1 fix awareness: the applier now issues ``SET LOCAL statement_timeout``
    as the first statement of every transaction. That's session config, not
    manifest DDL, so it's recorded into a *separate* list (``session_config``)
    on the connection and does NOT count toward ``executed`` for purposes of
    the ``fail_after`` counter or ``len(conn.executed)`` assertions in the
    pre-existing tests. New P0-1 tests that need to observe SET LOCAL
    inspect ``conn.session_config`` directly.

    P0-2 fix awareness: ``executed`` represents COMMITTED state (post-commit).
    In-flight DDL accumulates in ``pending`` and is moved to ``executed`` on
    ``conn.commit()``. If the connection exits without commit (rollback),
    ``pending`` is discarded — matching real PG transactional semantics so
    atomic-batch tests can assert "zero rows in executed after rollback".
    The ``fail_after`` counter uses ``len(pending)`` so it triggers based on
    in-flight stmt count, not committed count.
    """

    def __init__(self, conn: "_StubConnection") -> None:
        self._conn = conn

    def __enter__(self) -> "_StubCursor":
        return self

    def __exit__(self, *exc) -> None:  # noqa: D401, ANN001
        return None

    def execute(self, stmt: str, params=None) -> None:  # noqa: ANN001
        # Route SET LOCAL session config away from the manifest DDL list so
        # the existing tests' assertions about executed counts/contents remain
        # accurate (the SET LOCAL is infrastructure plumbing, not user DDL).
        if stmt.lstrip().lower().startswith("set local"):
            self._conn.session_config.append(stmt)
            return
        # P0-2: in-flight DDL goes to pending; committed only on conn.commit().
        self._conn.pending.append(stmt)
        # Optional fail-after-N hook for the rollback test (counts in-flight,
        # not committed — matches the legacy contract where fail_after meant
        # "raise on the (N+1)-th DDL execute call").
        if (
            self._conn.fail_after is not None
            and len(self._conn.pending) > self._conn.fail_after
        ):
            raise RuntimeError(
                f"stub PG error at stmt #{len(self._conn.pending)}"
            )


class _StubConnection:
    def __init__(self, fail_after: int | None = None) -> None:
        # P0-2: ``executed`` is committed state only. Use ``pending`` to
        # observe in-flight DDL before commit/rollback decision.
        self.executed: list[str] = []
        self.pending: list[str] = []
        # P0-1: SET LOCAL statement_timeout lands here, separate from manifest DDL.
        self.session_config: list[str] = []
        self.committed = False
        self.fail_after = fail_after

    def __enter__(self) -> "_StubConnection":
        return self

    def __exit__(self, *exc) -> None:  # noqa: D401, ANN001
        # P0-2: rollback semantics — if no commit happened, drop pending.
        # If commit already moved pending to executed, this is a no-op.
        if not self.committed:
            self.pending = []
        return None

    def cursor(self) -> _StubCursor:
        return _StubCursor(self)

    def commit(self) -> None:
        # P0-2: move pending to executed; clear pending for any subsequent
        # SAVEPOINT or follow-up operations on the same connection.
        self.executed.extend(self.pending)
        self.pending = []
        self.committed = True


class _StubPool:
    """Minimal pool — yields a single, reusable ``_StubConnection``.

    Reusing one connection is fine for our purposes: every test creates
    a fresh pool, and the applier opens one ``with pool.connection()``
    block per manifest.
    """

    def __init__(self, fail_after: int | None = None) -> None:
        self.conn = _StubConnection(fail_after=fail_after)

    def connection(self) -> _StubConnection:
        return self.conn


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _redirect_audit_log(tmp_path, monkeypatch):
    """Redirect AUDIT_LOG_PATH to tmp_path for every test in this module.

    Without this fixture, the audit-trail emit from P0-3 would pollute the
    real ``logs/v2/apply_audit.jsonl`` file under the repo whenever the
    pre-existing 5 tests run. With it, every test gets an isolated audit
    log under ``tmp_path`` and the real file is never touched.
    """
    monkeypatch.setattr(
        applier_mod, "AUDIT_LOG_PATH", tmp_path / "apply_audit.jsonl",
    )


def _manifest(type_id: str = "customer") -> ObjectTypeManifest:
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id, name_pl="X", name_en="X",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
            ],
        ),
    )


# --------------------------------------------------------------------------
# 1. dry_run path
# --------------------------------------------------------------------------


def test_apply_manifest_dry_run_returns_preview_only(monkeypatch):
    """``dry_run=True`` -> preview_only=True, applied=False, no PG side-effect.

    Even if PG would otherwise be reachable, ``dry_run`` short-circuits
    *before* calling ``_get_pg_connection``. We assert side-effect freedom
    by patching the connector to a sentinel that would explode if invoked.
    """
    def _should_not_be_called():
        raise AssertionError("dry_run must not query PG connectivity")

    monkeypatch.setattr(applier_mod, "_get_pg_connection", _should_not_be_called)

    res = apply_manifest(_manifest(), dry_run=True)

    assert isinstance(res, ApplyResult)
    assert res.preview_only is True
    assert res.applied is False
    assert res.statements_total > 0
    assert res.statements_executed == 0
    assert res.error is None
    assert "Dry run" in res.rationale


# --------------------------------------------------------------------------
# 2. PG unreachable
# --------------------------------------------------------------------------


def test_apply_manifest_pg_unreachable_returns_preview_only(monkeypatch):
    """When ``_get_pg_connection`` returns ``None`` we degrade gracefully."""
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: None)

    res = apply_manifest(_manifest())

    assert res.applied is False
    assert res.preview_only is True
    assert res.statements_total > 0
    assert res.statements_executed == 0
    assert res.error is None
    assert "niedostepny" in res.rationale.lower() or "niedostępny" in res.rationale.lower()


# --------------------------------------------------------------------------
# 3. PG reachable + clean run
# --------------------------------------------------------------------------


def test_apply_manifest_pg_reachable_executes_all_statements(monkeypatch):
    """Happy path: every compiled statement is executed and the txn commits."""
    pool = _StubPool()
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    res = apply_manifest(_manifest())

    assert res.applied is True
    assert res.preview_only is False
    assert res.error is None
    assert res.statements_total > 0
    assert res.statements_executed == res.statements_total
    assert len(pool.conn.executed) == res.statements_total
    assert pool.conn.committed is True
    # Sanity: at least one of the statements is the main CREATE TABLE.
    assert any('CREATE TABLE IF NOT EXISTS "sylion_v2"."customer"' in s
               for s in pool.conn.executed)


# --------------------------------------------------------------------------
# 4. PG raises mid-flight -> rollback
# --------------------------------------------------------------------------


def test_apply_manifest_pg_error_rolls_back(monkeypatch):
    """When stmt #3 fails: applied=False, executed=2, error set, rollback rationale.

    The ``with pool.connection()`` context manager handles the rollback in
    psycopg semantics (no commit was reached); ``ApplyResult.applied=False``
    means callers should not assume the schema is in the new shape.
    """
    pool = _StubPool(fail_after=2)  # third execute() raises.
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    res = apply_manifest(_manifest())

    assert res.applied is False
    assert res.preview_only is False
    assert res.statements_executed == 2
    assert res.statements_total > 2  # need enough stmts to actually fail
    assert res.error is not None
    assert "RuntimeError" in res.error
    assert "stub PG error" in res.error
    assert "wycofana" in res.rationale.lower()
    # The transaction was NEVER committed.
    assert pool.conn.committed is False


# --------------------------------------------------------------------------
# 5. apply_all aggregates per-manifest results
# --------------------------------------------------------------------------


def test_apply_all_aggregates_results(monkeypatch):
    """Three manifests, the second one's pool fails: results 1 & 3 still applied.

    We hand out a different ``_StubPool`` on each call to
    ``_get_pg_connection`` so that an error in manifest #2 does not affect
    the connections used for #1 and #3.
    """
    pools = [_StubPool(), _StubPool(fail_after=1), _StubPool()]
    iterator = iter(pools)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: next(iterator))

    manifests = [_manifest("customer"), _manifest("project"), _manifest("vehicle")]
    results = apply_all(manifests)

    assert len(results) == 3
    # Result 0 — clean.
    assert results[0].type_id == "customer"
    assert results[0].applied is True
    assert results[0].error is None
    assert pools[0].conn.committed is True

    # Result 1 — failed at stmt #2 (fail_after=1 means second execute raises).
    assert results[1].type_id == "project"
    assert results[1].applied is False
    assert results[1].preview_only is False
    assert results[1].error is not None
    assert "RuntimeError" in results[1].error
    assert results[1].statements_executed == 1
    assert pools[1].conn.committed is False

    # Result 2 — clean (post-failure manifests still proceed).
    assert results[2].type_id == "vehicle"
    assert results[2].applied is True
    assert results[2].error is None
    assert pools[2].conn.committed is True


# --------------------------------------------------------------------------
# 6. P0-3 — Audit trail (JSONL + event bus) per apply call
# --------------------------------------------------------------------------
#
# Adversarial review §P0-3: every apply (success, failure, dry-run,
# PG-unreachable) must record a structured audit row capturing
# (ts, type_id, actor, applied, preview_only, statements_total,
#  statements_executed, ddl_sha256, error, rationale).
#
# Phase 0 implementation: append-only JSONL at ``AUDIT_LOG_PATH`` plus
# a best-effort emit on the ``sylion.core`` event bus. The five tests
# below exercise each return path of ``apply_manifest`` and the loop
# body of ``apply_all``.
#
# Note: the autouse fixture ``_redirect_audit_log`` already pins
# ``AUDIT_LOG_PATH`` to ``tmp_path / "apply_audit.jsonl"`` for every
# test, so each test below re-monkeypatches to a per-test path it knows
# the location of (avoids relying on the fixture's tmp_path indirectly).


def test_apply_manifest_emits_audit_jsonl_on_dry_run(tmp_path, monkeypatch):
    """P0-3: dry_run produces an audit JSONL row with applied=false, preview_only=true."""
    audit_path = tmp_path / "apply_audit.jsonl"
    monkeypatch.setattr(applier_mod, "AUDIT_LOG_PATH", audit_path)

    apply_manifest(_manifest("test_obj"), dry_run=True, actor="alice")

    assert audit_path.exists()
    rows = [
        __import__("json").loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["type_id"] == "test_obj"
    assert row["actor"] == "alice"
    assert row["applied"] is False
    assert row["preview_only"] is True
    assert row["statements_total"] > 0
    assert len(row["ddl_sha256"]) == 64


def test_apply_manifest_emits_audit_jsonl_on_pg_unreachable(tmp_path, monkeypatch):
    """P0-3: PG unreachable still produces an audit row (preview_only=true, error=None).

    The PG-unreachable path is *not* an error (operator infrastructure
    issue, not a manifest issue) so ``error`` stays None even though the
    apply is declined.
    """
    audit_path = tmp_path / "apply_audit.jsonl"
    monkeypatch.setattr(applier_mod, "AUDIT_LOG_PATH", audit_path)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: None)

    apply_manifest(_manifest("test_obj"), actor="bob")

    rows = [
        __import__("json").loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["actor"] == "bob"
    assert rows[0]["preview_only"] is True
    assert rows[0]["error"] is None  # PG unreachable is not an error per se


def test_apply_manifest_emits_audit_jsonl_on_pg_error(tmp_path, monkeypatch):
    """P0-3: PG raises mid-DDL -> audit row captures error string + executed count."""
    audit_path = tmp_path / "apply_audit.jsonl"
    monkeypatch.setattr(applier_mod, "AUDIT_LOG_PATH", audit_path)
    pool = _StubPool(fail_after=2)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    result = apply_manifest(_manifest("test_obj"), actor="charlie")
    assert result.applied is False

    rows = [
        __import__("json").loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["actor"] == "charlie"
    assert rows[0]["applied"] is False
    assert rows[0]["error"] is not None
    assert rows[0]["statements_executed"] == 2


def test_ddl_sha256_changes_when_manifest_changes():
    """P0-3: ddl_sha256 must differ when manifest dedicated columns change.

    Validates that the hash function is sensitive to manifest content —
    operators relying on it for "did the DDL change?" forensics need this
    guarantee.
    """
    from sylion.aeis_v2.ontology import compile_to_ddl
    from sylion.aeis_v2.ontology.applier import _ddl_sha256

    m1 = _manifest("test_obj")
    m2 = _manifest("test_obj")
    m2.spec.dedicated_columns.append(
        DedicatedColumn(name="extra", type="text")
    )
    h1 = _ddl_sha256(compile_to_ddl(m1).all_statements())
    h2 = _ddl_sha256(compile_to_ddl(m2).all_statements())
    assert h1 != h2
    assert len(h1) == 64 and len(h2) == 64


def test_apply_all_emits_one_audit_row_per_manifest(tmp_path, monkeypatch):
    """P0-3: apply_all over N manifests writes exactly N audit rows."""
    audit_path = tmp_path / "apply_audit.jsonl"
    monkeypatch.setattr(applier_mod, "AUDIT_LOG_PATH", audit_path)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: None)

    apply_all([_manifest(f"obj_{i}") for i in range(3)], actor="dora")

    rows = [
        __import__("json").loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 3
    assert {r["type_id"] for r in rows} == {"obj_0", "obj_1", "obj_2"}
    assert all(r["actor"] == "dora" for r in rows)


# --------------------------------------------------------------------------
# 7. P0-1 — Pool starvation guard (semaphore + per-session statement_timeout)
# --------------------------------------------------------------------------
#
# Adversarial review §P0-1: applier reused the v1 advisor pool (max_size=10,
# timeout=2.0) and could starve v1 advisor handlers under parallel apply
# traffic. Fix:
#   1. ``APPLIER_POOL_SEMAPHORE = threading.BoundedSemaphore(value=2)`` caps
#      concurrent applier connections at 2 of the 10 slots, leaving 8 for v1.
#   2. ``SET LOCAL statement_timeout = '60000ms'`` per session ensures a
#      stuck DDL releases its slot in 60s rather than ~2h (TCP keepalive).


def test_applier_semaphore_limits_concurrency(monkeypatch):
    """P0-1: APPLIER_POOL_SEMAPHORE caps concurrent applies to 2."""
    from sylion.aeis_v2.ontology import applier as applier_mod

    assert applier_mod.APPLIER_POOL_SEMAPHORE._value == 2  # noqa: SLF001
    # Acquire both slots; 3rd would block (we don't actually block in
    # the test — just verify the semaphore exists and is sized 2).
    acquired = []
    for _ in range(2):
        ok = applier_mod.APPLIER_POOL_SEMAPHORE.acquire(blocking=False)
        assert ok
        acquired.append(True)
    # 3rd acquire should fail non-blocking (semaphore exhausted).
    third = applier_mod.APPLIER_POOL_SEMAPHORE.acquire(blocking=False)
    assert not third
    # Cleanup
    for _ in acquired:
        applier_mod.APPLIER_POOL_SEMAPHORE.release()


def test_apply_with_budget_sets_statement_timeout(monkeypatch):
    """P0-1: applier issues SET LOCAL statement_timeout per session.

    The first cursor.execute() call inside ``_execute_statements`` must be
    ``SET LOCAL statement_timeout = '60000ms'``. The stub routes that call
    into ``conn.session_config`` so we assert against that list (the
    manifest DDL still lands in ``conn.executed`` unchanged).
    """
    pool = _StubPool()
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    apply_manifest(_manifest("test_obj"))
    # First (and only) session config call should be SET LOCAL statement_timeout
    assert len(pool.conn.session_config) == 1, (
        f"expected exactly one SET LOCAL session config call, got: "
        f"{pool.conn.session_config}"
    )
    assert pool.conn.session_config[0].lower().startswith(
        "set local statement_timeout"
    ), (
        "expected SET LOCAL statement_timeout, got: "
        f"{pool.conn.session_config[0][:80]}"
    )


def test_apply_with_budget_holds_then_releases_semaphore(monkeypatch):
    """P0-1: semaphore is acquired during apply and released after."""
    from sylion.aeis_v2.ontology import applier as applier_mod

    initial_value = applier_mod.APPLIER_POOL_SEMAPHORE._value  # noqa: SLF001
    pool = _StubPool()
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    apply_manifest(_manifest("test_obj"))
    # After apply completes, semaphore back to initial value
    assert applier_mod.APPLIER_POOL_SEMAPHORE._value == initial_value  # noqa: SLF001


def test_applier_statement_timeout_constant_60s():
    """P0-1: statement timeout is set to 60_000ms (60s)."""
    from sylion.aeis_v2.ontology.applier import APPLIER_STATEMENT_TIMEOUT_MS
    assert APPLIER_STATEMENT_TIMEOUT_MS == 60_000


# --------------------------------------------------------------------------
# 8. P0-2 — atomic_batch option for apply_all (whole-batch rollback)
# --------------------------------------------------------------------------
#
# Adversarial review §P0-2: ``apply_all`` previously gave each manifest its
# own transaction so a mid-batch failure left the database in a half-applied
# "Frankenstein" state — manifests #1, #2 committed, #3 failed, #4, #5
# skipped. The fix adds an ``atomic_batch=True`` opt-in that wraps the
# entire batch in ONE outer transaction: any failure rolls back everything,
# audit trail records a final ``type_id="<batch>"`` summary row.


def test_apply_all_atomic_batch_rolls_back_on_mid_failure(monkeypatch):
    """P0-2: atomic_batch=True + mid-batch failure -> NO commits anywhere.

    Three manifests, the second one's DDL raises mid-flight. With the
    legacy per-manifest transaction model, manifest #1 would have been
    committed before #2 ran. Under ``atomic_batch=True`` the entire
    batch shares one transaction, so manifest #1's DDL never commits —
    we assert ``pool.conn.executed`` (committed state) is empty.
    """
    # Manifest #1 has 10 stmts, #2 has 9, #3 has 9. We want manifest #2's
    # first stmt to raise -> fail_after = 10 (so 11th execute raises).
    pool = _StubPool(fail_after=10)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    manifests = [_manifest("customer"), _manifest("project"), _manifest("vehicle")]
    results = apply_all(manifests, atomic_batch=True)

    assert len(results) == 3
    # Every result is applied=False — atomic rollback means nothing committed.
    assert all(r.applied is False for r in results), [
        (r.type_id, r.applied) for r in results
    ]
    # Manifest #1 ran some DDL but it was rolled back, not committed.
    assert results[0].statements_executed > 0
    assert results[0].error is None  # failure attributed to #2, not #1.
    # Manifest #2 is the one that failed.
    assert results[1].error is not None
    assert "RuntimeError" in results[1].error
    # Manifest #3 was skipped (never ran a statement).
    assert results[2].statements_executed == 0
    assert "Pominiety" in results[2].rationale or "pominiety" in results[2].rationale.lower()
    # The whole batch was rolled back — committed state is empty, commit
    # never reached.
    assert pool.conn.committed is False
    assert len(pool.conn.executed) == 0, (
        f"expected zero committed stmts after atomic rollback, got "
        f"{len(pool.conn.executed)}: {pool.conn.executed[:3]}"
    )


def test_apply_all_atomic_batch_holds_one_semaphore_acquire(monkeypatch):
    """P0-2: atomic_batch acquires APPLIER_POOL_SEMAPHORE ONCE for whole batch.

    Legacy ``apply_all`` calls ``_execute_statements`` per manifest, so a
    5-manifest batch would acquire/release the semaphore 5 times. Under
    atomic-batch mode, the semaphore is acquired once for the duration of
    the outer transaction. We verify by counting acquire events via a
    monkey-patched semaphore wrapper.
    """
    from sylion.aeis_v2.ontology import applier as applier_mod

    # Wrap the real semaphore to count acquire calls during the apply.
    real_sema = applier_mod.APPLIER_POOL_SEMAPHORE
    acquire_count = {"n": 0}

    class _CountingSema:
        def __enter__(self):
            acquire_count["n"] += 1
            real_sema.acquire()
            return self

        def __exit__(self, *exc):
            real_sema.release()
            return None

        # Forward attribute access for any other usage in the module.
        def __getattr__(self, name):
            return getattr(real_sema, name)

    monkeypatch.setattr(applier_mod, "APPLIER_POOL_SEMAPHORE", _CountingSema())

    pool = _StubPool()
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    manifests = [_manifest("customer"), _manifest("project"), _manifest("vehicle")]
    apply_all(manifests, atomic_batch=True)

    # ONE acquire for the whole batch — not 3.
    assert acquire_count["n"] == 1, (
        f"atomic_batch must hold one semaphore acquire for the whole batch, "
        f"got {acquire_count['n']} acquires"
    )


def test_apply_all_atomic_batch_emits_summary_audit_row(tmp_path, monkeypatch):
    """P0-2: atomic_batch writes N+1 audit rows: per-manifest plus batch summary.

    The batch-summary row uses ``type_id="<batch>"`` and aggregates the
    outcome (applied=True iff every manifest committed; applied=False on
    rollback or any per-manifest failure). Operators reading
    ``apply_audit.jsonl`` can grep for ``"<batch>"`` to find every batch
    operation explicitly.
    """
    audit_path = tmp_path / "apply_audit.jsonl"
    monkeypatch.setattr(applier_mod, "AUDIT_LOG_PATH", audit_path)
    pool = _StubPool()
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    manifests = [_manifest("customer"), _manifest("project"), _manifest("vehicle")]
    apply_all(manifests, atomic_batch=True, actor="erin")

    rows = [
        __import__("json").loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    # 3 per-manifest rows + 1 batch-summary row = 4.
    assert len(rows) == 4, f"expected N+1=4 audit rows, got {len(rows)}: {rows}"
    # Last row is the batch summary.
    summary = rows[-1]
    assert summary["type_id"] == "<batch>"
    assert summary["actor"] == "erin"
    assert summary["applied"] is True  # clean batch -> aggregate applied=True
    assert summary["error"] is None
    # Per-manifest rows still record their type_ids.
    assert {rows[i]["type_id"] for i in range(3)} == {"customer", "project", "vehicle"}


def test_apply_all_default_non_atomic_unchanged(monkeypatch):
    """P0-2 regression: default apply_all (atomic_batch=False) keeps legacy behavior.

    Three manifests, the second one's pool fails: results 1 & 3 still
    committed (per-manifest transaction model). Audit trail emits exactly
    N rows (no batch-summary row when atomic_batch is False). Mirrors
    ``test_apply_all_aggregates_results`` to guard against silent contract
    changes from the P0-2 refactor.
    """
    pools = [_StubPool(), _StubPool(fail_after=1), _StubPool()]
    iterator = iter(pools)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: next(iterator))

    manifests = [_manifest("customer"), _manifest("project"), _manifest("vehicle")]
    # Default call — atomic_batch defaults to False.
    results = apply_all(manifests)

    assert len(results) == 3
    # Manifests #1 and #3 committed despite #2 failing.
    assert results[0].applied is True
    assert pools[0].conn.committed is True
    assert results[1].applied is False
    assert pools[1].conn.committed is False
    assert results[2].applied is True
    assert pools[2].conn.committed is True


# --------------------------------------------------------------------------
# 9. P0-4 — Differentiate connectivity vs DDL errors (prefix-tagged)
# --------------------------------------------------------------------------
#
# Adversarial review §P0-4: the applier had two over-broad ``except
# Exception`` blocks that masked qualitatively different failure modes:
#
#   1. ``_get_pg_connection`` caught everything as "PG unreachable" so a
#      bug in v1 advisor pool init (missing env var, bad URL parse) was
#      logged at INFO and never surfaced — operator just saw "preview
#      only mode" indefinitely.
#   2. ``_execute_statements`` collapsed connectivity failures (broken
#      pipe, server kill) and SQL/DDL bugs into one indistinguishable
#      ``"<ExcType>: <msg>"`` error string, so the operator UI could not
#      branch on "transient — retry" vs "fatal — inspect compiled DDL".
#
# Fix: typed branches in ``_get_pg_connection`` (ImportError → log.error,
# PGUnreachable → log.info, other → log.error+exc_info) and a prefix
# convention in the error string: ``"connectivity: <ExcType>: <msg>"``
# vs ``"ddl: <ExcType>: <msg>"``.


def test_get_pg_connection_distinguishes_unreachable_from_init_failure(
    monkeypatch, caplog,
):
    """P0-4: an unexpected pool init failure logs at ERROR (not INFO).

    Operators previously had no way to tell apart "PG offline" (routine,
    log at INFO) from "advisor pool config is broken" (must investigate,
    log at ERROR). We monkeypatch ``get_pool`` to raise a generic
    ``ValueError`` — neither ``PGUnreachable`` nor ``ImportError`` — and
    assert the failure is escalated to ``ERROR`` level with ``exc_info``
    captured (so the traceback shows up in the logs).

    W15 G2 phase 1 update: with the v2-first / v1-fallback helper in
    place, we must also force the v2 path to return ``None`` so the
    fallback reaches v1. Without this monkeypatch the test would happily
    pick up a real local-PG v2 pool and never exercise the v1 path the
    test is asserting on.
    """
    import logging as _logging

    from sylion.aeis.advisor import _db as advisor_db

    def _raise_value_error():
        raise ValueError("bad config — env var missing or URL malformed")

    monkeypatch.setattr(advisor_db, "get_pool", _raise_value_error)
    # Force the helper past the v2 branch so the patched v1 get_pool runs.
    monkeypatch.setattr("sylion.aeis_v2.db.get_v2_pool", lambda: None)

    with caplog.at_level(_logging.DEBUG, logger="sylion.aeis_v2.ontology.applier"):
        result = applier_mod._get_pg_connection()  # noqa: SLF001

    # Returns None like the other failure paths — apply degrades to preview-only.
    assert result is None
    # The failure is logged at ERROR (not INFO!) so it surfaces in
    # operator dashboards. The legacy code logged at INFO and the bug
    # was invisible.
    error_records = [
        r for r in caplog.records if r.levelno >= _logging.ERROR
    ]
    assert error_records, (
        "expected at least one ERROR-level log record for unexpected "
        f"pool init failure, got: {[r.levelname for r in caplog.records]}"
    )
    # The exception details must be in the message for forensics.
    joined = " ".join(r.getMessage() for r in error_records)
    assert "bad config" in joined, (
        f"expected ValueError message in log output, got: {joined}"
    )


def test_execute_statements_flags_connectivity_error_with_prefix(monkeypatch):
    """P0-4: BrokenPipeError -> error string starts with ``"connectivity:"``.

    The operator UI branches on the prefix to decide whether to surface a
    "retry — transient" toast or a "fatal — inspect compiled DDL" modal.
    A broken pipe is unambiguously transient (server killed mid-DDL or
    network blip) so it must land in the connectivity bucket.
    """
    class _BrokenPipePool:
        """Pool whose first cursor.execute() raises BrokenPipeError."""

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return None

            def execute(self, stmt, params=None):
                raise BrokenPipeError("server killed mid-DDL")

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return None

            def cursor(self):
                return _BrokenPipePool._Cur()

            def commit(self):
                pass

        def connection(self):
            return _BrokenPipePool._Conn()

    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: _BrokenPipePool())

    res = apply_manifest(_manifest("test_obj"))

    assert res.applied is False
    assert res.preview_only is False
    assert res.error is not None
    assert res.error.startswith("connectivity:"), (
        f"expected 'connectivity:' prefix for BrokenPipeError, got: {res.error!r}"
    )
    assert "BrokenPipeError" in res.error


def test_execute_statements_flags_ddl_error_with_prefix(monkeypatch):
    """P0-4: a plain RuntimeError (SQL/DDL bug) -> ``"ddl:"`` prefix.

    The fail-after machinery in ``_StubPool`` raises ``RuntimeError`` —
    not a connectivity exception — so it must be classified as a DDL
    error. The UI surfaces this for operator inspection of the compiled
    DDL artifact (the manifest itself produced bad SQL).
    """
    pool = _StubPool(fail_after=2)
    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: pool)

    res = apply_manifest(_manifest("test_obj"))

    assert res.applied is False
    assert res.preview_only is False
    assert res.error is not None
    assert res.error.startswith("ddl:"), (
        f"expected 'ddl:' prefix for RuntimeError, got: {res.error!r}"
    )
    assert "RuntimeError" in res.error
    assert "stub PG error" in res.error


def test_execute_statements_psycopg_operational_error_is_connectivity(monkeypatch):
    """P0-4: psycopg.OperationalError -> ``"connectivity:"`` prefix.

    The most common real-world transient failure: PostgreSQL server
    restart, FATAL admin shutdown, or TCP RST mid-transaction. psycopg
    surfaces these as ``OperationalError`` and the applier must classify
    them as connectivity (retry candidate), not DDL (inspect manifest).

    Skipped when psycopg isn't installed (SQLite-only smoke deployments
    where the advisor extra was skipped).
    """
    psycopg = pytest.importorskip("psycopg")

    class _OperationalPool:
        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return None

            def execute(self, stmt, params=None):
                raise psycopg.OperationalError("server gone — admin shutdown")

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return None

            def cursor(self):
                return _OperationalPool._Cur()

            def commit(self):
                pass

        def connection(self):
            return _OperationalPool._Conn()

    monkeypatch.setattr(applier_mod, "_get_pg_connection", lambda: _OperationalPool())

    res = apply_manifest(_manifest("test_obj"))

    assert res.applied is False
    assert res.preview_only is False
    assert res.error is not None
    assert res.error.startswith("connectivity:"), (
        f"expected 'connectivity:' prefix for psycopg.OperationalError, "
        f"got: {res.error!r}"
    )
    assert "OperationalError" in res.error
