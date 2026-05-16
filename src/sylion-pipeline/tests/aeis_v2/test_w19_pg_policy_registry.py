"""Tests for PgPolicyRegistry — sprint 4 W19 production storage."""
from __future__ import annotations

import json
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.policy_v2.pg_registry import (
    PG_POLICY_DDL,
    PgPolicyRegistry,
    Policy,
)


# ---------------------------------------------------------------------------
# Fake psycopg backed by an in-memory dict.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn
        self._fetchone_result: Any = None
        self._fetchall_result: list[Any] = []
        self.rowcount: int = 0

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._conn._handle(self, sql, params)

    def fetchone(self) -> Any:
        return self._fetchone_result

    def fetchall(self) -> list[Any]:
        return self._fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _handle(self, cur: _FakeCursor, sql: str, params: tuple) -> None:
        sql_n = " ".join(sql.split()).strip().lower()

        if "create table" in sql_n or "create index" in sql_n:
            return

        if sql_n.startswith("insert into policies"):
            policy_id, name, template_str, enabled = params
            self.rows[policy_id] = {
                "policy_id": policy_id, "name": name,
                "template_str": template_str, "enabled": enabled,
                "version": 1,
            }
            cur.rowcount = 1
            return

        if sql_n.startswith(
            "select policy_id, name, template_str, enabled, version "
            "from policies where policy_id"
        ):
            # get_policy
            policy_id = params[0]
            row = self.rows.get(policy_id)
            cur._fetchone_result = (
                None if row is None
                else (
                    row["policy_id"], row["name"], row["template_str"],
                    row["enabled"], row["version"],
                )
            )
            return

        if sql_n.startswith(
            "select policy_id, name, template_str, enabled, version from policies"
        ):
            # list_policies — optional WHERE enabled = ?
            filter_enabled = None
            if " where enabled" in sql_n and params:
                filter_enabled = params[0]
            rows = []
            for r in self.rows.values():
                if filter_enabled is None or r["enabled"] == filter_enabled:
                    rows.append((
                        r["policy_id"], r["name"], r["template_str"],
                        r["enabled"], r["version"],
                    ))
            rows.sort(key=lambda t: t[1])
            cur._fetchall_result = rows
            return

        if sql_n.startswith("update policies set"):
            # Last param is policy_id.
            policy_id = params[-1]
            row = self.rows.get(policy_id)
            if row is None:
                cur.rowcount = 0
                return
            # Crudely update by parsing field positions.
            fields = []
            if "name = %s" in sql_n:
                fields.append("name")
            if "template_str = %s" in sql_n:
                fields.append("template_str")
            if "enabled = %s" in sql_n:
                fields.append("enabled")
            for i, f in enumerate(fields):
                row[f] = params[i]
            row["version"] += 1
            cur.rowcount = 1
            return

        if sql_n.startswith("delete from policies"):
            policy_id = params[0]
            if policy_id in self.rows:
                del self.rows[policy_id]
                cur.rowcount = 1
            else:
                cur.rowcount = 0
            return


@pytest.fixture
def conn() -> _FakeConn:
    return _FakeConn()


@pytest.fixture
def registry(conn: _FakeConn, tmp_path) -> PgPolicyRegistry:
    return PgPolicyRegistry(
        connection_factory=lambda: conn,
        audit_log_path=tmp_path / "registry.jsonl",
    )


# ---------------------------------------------------------------------------
# Module invariants
# ---------------------------------------------------------------------------


def test_pg_policy_ddl_idempotent() -> None:
    assert "CREATE TABLE IF NOT EXISTS policies" in PG_POLICY_DDL
    assert "CREATE INDEX IF NOT EXISTS policies_enabled_name_idx" in PG_POLICY_DDL


def test_policy_to_dict_serialisable() -> None:
    p = Policy(
        policy_id="p1", name="n", template_str="t",
        enabled=True, version=2,
    )
    d = p.to_dict()
    json.dumps(d)
    assert d["enabled"] is True
    assert d["version"] == 2


# ---------------------------------------------------------------------------
# CRUD happy paths
# ---------------------------------------------------------------------------


def test_create_policy_inserts_row(
    registry: PgPolicyRegistry, conn: _FakeConn,
) -> None:
    p = registry.create_policy(
        "admin-only",
        name="admin gate",
        template_str="{% if request.role == 'admin' %}allow{% else %}deny{% endif %}",
        enabled=True,
    )
    assert isinstance(p, Policy)
    assert "admin-only" in conn.rows
    assert conn.rows["admin-only"]["enabled"] is True


def test_create_policy_rejects_invalid_template(
    registry: PgPolicyRegistry,
) -> None:
    with pytest.raises(ValueError):
        registry.create_policy(
            "bad", name="n",
            template_str="{{ bad",  # malformed jinja2
        )


def test_create_policy_rejects_banned_token(
    registry: PgPolicyRegistry,
) -> None:
    with pytest.raises(ValueError):
        registry.create_policy(
            "bad", name="n",
            template_str="{{ ''.__class__.__mro__ }}",
        )


def test_get_policy_returns_row(registry: PgPolicyRegistry) -> None:
    registry.create_policy(
        "p1", name="N", template_str="allow", enabled=False,
    )
    got = registry.get_policy("p1")
    assert got is not None
    assert got.policy_id == "p1"
    assert got.name == "N"
    assert got.enabled is False


def test_get_policy_missing_returns_none(registry: PgPolicyRegistry) -> None:
    assert registry.get_policy("nope") is None


def test_update_policy_increments_version(
    registry: PgPolicyRegistry, conn: _FakeConn,
) -> None:
    registry.create_policy("p1", name="n", template_str="allow")
    updated = registry.update_policy("p1", template_str="deny")
    assert updated is not None
    assert updated.version == 2
    assert conn.rows["p1"]["template_str"] == "deny"


def test_update_policy_no_op_when_no_fields(
    registry: PgPolicyRegistry,
) -> None:
    registry.create_policy("p1", name="n", template_str="allow")
    out = registry.update_policy("p1")  # no fields
    assert out is not None
    assert out.version == 1  # unchanged


def test_update_policy_missing_returns_none(
    registry: PgPolicyRegistry,
) -> None:
    assert registry.update_policy("absent", enabled=True) is None


def test_update_policy_rejects_invalid_template(
    registry: PgPolicyRegistry,
) -> None:
    registry.create_policy("p1", name="n", template_str="allow")
    with pytest.raises(ValueError):
        registry.update_policy("p1", template_str="{{ ''.__class__ }}")


def test_delete_policy_returns_true_on_hit(
    registry: PgPolicyRegistry, conn: _FakeConn,
) -> None:
    registry.create_policy("p1", name="n", template_str="allow")
    assert registry.delete_policy("p1") is True
    assert "p1" not in conn.rows


def test_delete_policy_returns_false_on_miss(
    registry: PgPolicyRegistry,
) -> None:
    assert registry.delete_policy("absent") is False


# ---------------------------------------------------------------------------
# list_policies + get_active_policy
# ---------------------------------------------------------------------------


def test_list_policies_all(registry: PgPolicyRegistry) -> None:
    registry.create_policy("a", name="A", template_str="allow", enabled=True)
    registry.create_policy("b", name="B", template_str="allow", enabled=False)
    registry.create_policy("c", name="C", template_str="allow", enabled=True)
    out = registry.list_policies()
    assert len(out) == 3
    # Sorted by name.
    assert [p.name for p in out] == ["A", "B", "C"]


def test_list_policies_enabled_only(registry: PgPolicyRegistry) -> None:
    registry.create_policy("a", name="A", template_str="allow", enabled=True)
    registry.create_policy("b", name="B", template_str="allow", enabled=False)
    out = registry.list_policies(enabled=True)
    assert [p.name for p in out] == ["A"]


def test_get_active_policy_returns_first_enabled(
    registry: PgPolicyRegistry,
) -> None:
    registry.create_policy("a", name="A", template_str="allow", enabled=True)
    registry.create_policy("z", name="Z", template_str="allow", enabled=True)
    p = registry.get_active_policy()
    assert p is not None
    assert p.name == "A"  # first by name


def test_get_active_policy_none_when_no_enabled(
    registry: PgPolicyRegistry,
) -> None:
    registry.create_policy("a", name="A", template_str="allow", enabled=False)
    assert registry.get_active_policy() is None


# ---------------------------------------------------------------------------
# Audit chain integrity
# ---------------------------------------------------------------------------


def test_registry_audit_chain_verifies(
    registry: PgPolicyRegistry, tmp_path,
) -> None:
    registry.ensure_schema()
    registry.create_policy("p1", name="n", template_str="allow")
    registry.update_policy("p1", template_str="deny")
    registry.delete_policy("p1")
    audit = registry._audit_log_path
    assert verify_chain(audit) == []


def test_registry_audit_excludes_template_str_pii_signal(
    registry: PgPolicyRegistry, tmp_path,
) -> None:
    """The audit row contains template_str — defensive: caller must
    NOT embed PII in templates. This test pins the contract that the
    audit DOES echo template_str so reviewers can reconstruct decisions."""
    registry.create_policy("p1", name="n", template_str="allow secret-token-xyz")
    audit = registry._audit_log_path
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    create_rows = [c for c in contents if c.get("kind") == "policy_registry.create"]
    assert len(create_rows) == 1
    assert "secret-token-xyz" in create_rows[0]["template_str"]
