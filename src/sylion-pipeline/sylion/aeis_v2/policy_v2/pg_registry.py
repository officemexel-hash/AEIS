"""W19 PgPolicyRegistry — operator-stored policy templates.

Sprint 4 deliverable. Pairs with :class:`RoutingGate` (commit 146c2404):
production federation routing pulls the **active** policy template
from PG via this registry, instead of accepting it as a parameter
on every call.

Schema (mirrors the in-memory contract used in tests)::

    CREATE TABLE IF NOT EXISTS policies (
        policy_id    text        PRIMARY KEY,
        name         text        NOT NULL,
        template_str text        NOT NULL,
        enabled      boolean     NOT NULL DEFAULT false,
        version      bigint      NOT NULL DEFAULT 1,
        created_at   timestamptz NOT NULL DEFAULT now(),
        updated_at   timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS policies_enabled_name_idx
        ON policies (enabled, name)
        WHERE enabled = true;

Per Kimi review k3 round 56:00:

* ``template_str`` is plain ``text`` (not jsonb) — jinja2 templates are
  free-form strings, jsonb only adds parse overhead.
* ``version`` increments on every UPDATE so consumers can pin a known
  version (post-Council sign-off) and detect drift.
* ``enabled = true`` is the active set — production deployments query
  ``WHERE enabled = true ORDER BY name`` (uses the partial index).
* Pre-storage validation via :func:`validate_policy_template` catches
  banned tokens + syntax errors at operator-time, not at runtime.

Public surface::

    reg = PgPolicyRegistry(connection_factory=...)
    reg.ensure_schema()
    reg.create_policy("admin-only", template_str="...", enabled=True)
    pol = reg.get_active_policy()  # latest enabled template
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.aeis_v2.policy_v2.jinja_runner import validate_policy_template
from pathlib import Path

log = logging.getLogger(__name__)

#: Idempotent DDL.
PG_POLICY_DDL: str = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id    text        PRIMARY KEY,
    name         text        NOT NULL,
    template_str text        NOT NULL,
    enabled      boolean     NOT NULL DEFAULT false,
    version      bigint      NOT NULL DEFAULT 1,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS policies_enabled_name_idx
    ON policies (enabled, name)
    WHERE enabled = true;
"""

#: Audit JSONL — chained per ac97e957.
POLICY_REGISTRY_AUDIT_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "policy_registry.jsonl"
)


@dataclass(frozen=True, slots=True)
class Policy:
    """One row in the ``policies`` table."""

    policy_id: str
    name: str
    template_str: str
    enabled: bool
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "template_str": self.template_str,
            "enabled": self.enabled,
            "version": self.version,
        }


class PgPolicyRegistry:
    """psycopg-backed CRUD for policy templates.

    Construction does NOT open a connection — every method call lazily
    resolves a fresh connection from the supplied ``connection_factory``
    (or ``psycopg.connect(self._dsn)`` if no factory was supplied).
    Tests inject a mock factory; production injects a pool.

    All public methods are thread-safe via a module-level RLock; the
    actual concurrency control on the database side is row-level
    locking inside an explicit transaction (per Kimi k2 finding on
    ON CONFLICT semantics).
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Any | None = None,
        audit_log_path: Path | str | None = None,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else POLICY_REGISTRY_AUDIT_PATH
        )
        self._lock = threading.RLock()
        self._init_done = False

    def _get_connection(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(self._dsn)

    def _emit_audit(self, payload: dict[str, Any]) -> None:
        try:
            append_to_chain(self._audit_log_path, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("policy_registry: audit emit failed (%s)", exc)

    def ensure_schema(self) -> None:
        with self._lock:
            if self._init_done:
                return
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(PG_POLICY_DDL)
                conn.commit()
            self._init_done = True
        self._emit_audit({"kind": "policy_registry.schema_applied"})

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_policy(
        self,
        policy_id: str,
        *,
        name: str,
        template_str: str,
        enabled: bool = False,
        actor: str = "anonymous",
    ) -> Policy:
        """Insert a new policy. Validates template first (operator-time gate)."""
        ok, detail = validate_policy_template(template_str)
        if not ok:
            raise ValueError(f"invalid template: {detail}")

        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO policies
                            (policy_id, name, template_str, enabled, version)
                        VALUES (%s, %s, %s, %s, 1)
                        """,
                        (policy_id, name, template_str, enabled),
                    )
                conn.commit()
        policy = Policy(
            policy_id=policy_id, name=name,
            template_str=template_str, enabled=enabled, version=1,
        )
        self._emit_audit({
            "kind": "policy_registry.create",
            "actor": actor,
            **policy.to_dict(),
        })
        return policy

    def get_policy(self, policy_id: str) -> Policy | None:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT policy_id, name, template_str, enabled, version "
                        "FROM policies WHERE policy_id = %s",
                        (policy_id,),
                    )
                    row = cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return Policy(
                policy_id=row["policy_id"], name=row["name"],
                template_str=row["template_str"],
                enabled=bool(row["enabled"]), version=int(row["version"]),
            )
        return Policy(
            policy_id=row[0], name=row[1],
            template_str=row[2], enabled=bool(row[3]), version=int(row[4]),
        )

    def update_policy(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        template_str: str | None = None,
        enabled: bool | None = None,
        actor: str = "anonymous",
    ) -> Policy | None:
        """Selective UPDATE; bumps version every time at least one field changes."""
        if template_str is not None:
            ok, detail = validate_policy_template(template_str)
            if not ok:
                raise ValueError(f"invalid template: {detail}")

        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if template_str is not None:
            sets.append("template_str = %s")
            params.append(template_str)
        if enabled is not None:
            sets.append("enabled = %s")
            params.append(enabled)
        if not sets:
            return self.get_policy(policy_id)
        sets.append("version = version + 1")
        sets.append("updated_at = now()")

        sql = (
            "UPDATE policies SET " + ", ".join(sets)
            + " WHERE policy_id = %s"
        )
        params.append(policy_id)

        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params))
                    affected = cur.rowcount
                conn.commit()

        if not affected:
            return None

        updated = self.get_policy(policy_id)
        if updated is not None:
            self._emit_audit({
                "kind": "policy_registry.update",
                "actor": actor,
                **updated.to_dict(),
            })
        return updated

    def delete_policy(
        self, policy_id: str, *, actor: str = "anonymous",
    ) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM policies WHERE policy_id = %s",
                        (policy_id,),
                    )
                    affected = cur.rowcount
                conn.commit()
        ok = bool(affected)
        self._emit_audit({
            "kind": "policy_registry.delete",
            "actor": actor,
            "policy_id": policy_id,
            "deleted": ok,
        })
        return ok

    def list_policies(self, enabled: bool | None = None) -> list[Policy]:
        sql = "SELECT policy_id, name, template_str, enabled, version FROM policies"
        params: tuple = ()
        if enabled is not None:
            sql += " WHERE enabled = %s"
            params = (enabled,)
        sql += " ORDER BY name"
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
        out: list[Policy] = []
        for r in rows:
            if isinstance(r, dict):
                out.append(Policy(
                    policy_id=r["policy_id"], name=r["name"],
                    template_str=r["template_str"],
                    enabled=bool(r["enabled"]), version=int(r["version"]),
                ))
            else:
                out.append(Policy(
                    policy_id=r[0], name=r[1],
                    template_str=r[2], enabled=bool(r[3]),
                    version=int(r[4]),
                ))
        return out

    def get_active_policy(self) -> Policy | None:
        """Return the first ``enabled = true`` policy by name (deterministic)."""
        active = self.list_policies(enabled=True)
        return active[0] if active else None


__all__ = [
    "PG_POLICY_DDL",
    "POLICY_REGISTRY_AUDIT_PATH",
    "PgPolicyRegistry",
    "Policy",
]
