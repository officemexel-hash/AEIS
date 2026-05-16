"""
SYLION VPS -- Provider Manager

Manages compute providers with state machine:
candidate -> qualified -> approved -> review -> blocked

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.vps.provider_manager")

VALID_TIERS = ("STANDARD", "PRO", "STATE", "PHANTOM")
VALID_STATES = ("candidate", "qualified", "approved", "review", "blocked")
STATE_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"qualified", "blocked"},
    "qualified": {"approved", "blocked"},
    "approved": {"review", "blocked"},
    "review": {"approved", "blocked"},
    "blocked": set(),
}
CERT_STAGES = ("A3.1", "A3.2", "A3.3", "A3.4", "A3.5", "A3.6", "A3.7")


class ProviderManager:
    """Manages VPS providers, allocations, certifications, and health probes."""

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS vps_providers (
                provider_id      TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                tier             TEXT NOT NULL DEFAULT 'STANDARD',
                state            TEXT NOT NULL DEFAULT 'candidate',
                region           TEXT NOT NULL DEFAULT '',
                vcpu_total       INTEGER NOT NULL DEFAULT 0,
                ram_gb_total     INTEGER NOT NULL DEFAULT 0,
                storage_gb_total INTEGER NOT NULL DEFAULT 0,
                price_vcpu_h_usd REAL NOT NULL DEFAULT 0.0,
                certified_at     REAL,
                last_probe_at    REAL,
                rebuild_role     TEXT NOT NULL DEFAULT 'none',
                cutover_strategy TEXT NOT NULL DEFAULT '',
                created_at       REAL NOT NULL,
                updated_at       REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vps_allocations (
                alloc_id     TEXT PRIMARY KEY,
                provider_id  TEXT NOT NULL,
                run_id       TEXT NOT NULL DEFAULT '',
                vcpu         INTEGER NOT NULL DEFAULT 0,
                ram_gb       INTEGER NOT NULL DEFAULT 0,
                allocated_at REAL NOT NULL,
                released_at  REAL,
                state        TEXT NOT NULL DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS vps_certifications (
                stage_id     TEXT PRIMARY KEY,
                provider_id  TEXT NOT NULL,
                stage_code   TEXT NOT NULL,
                state        TEXT NOT NULL DEFAULT 'pending',
                started_at   REAL,
                finished_at  REAL,
                decision_class TEXT NOT NULL DEFAULT '',
                reviewer_id  TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS vps_health_probes (
                probe_id     TEXT PRIMARY KEY,
                provider_id  TEXT NOT NULL,
                timestamp    REAL NOT NULL,
                up           INTEGER NOT NULL DEFAULT 1,
                latency_ms   INTEGER NOT NULL DEFAULT 0,
                cpu_pct      REAL NOT NULL DEFAULT 0.0,
                ram_pct      REAL NOT NULL DEFAULT 0.0,
                iops         INTEGER NOT NULL DEFAULT 0,
                error_code   TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_vp_state ON vps_providers(state);
            CREATE INDEX IF NOT EXISTS idx_vp_tier ON vps_providers(tier);
            CREATE INDEX IF NOT EXISTS idx_va_provider ON vps_allocations(provider_id);
            CREATE INDEX IF NOT EXISTS idx_va_run ON vps_allocations(run_id);
            CREATE INDEX IF NOT EXISTS idx_vc_provider ON vps_certifications(provider_id);
            CREATE INDEX IF NOT EXISTS idx_vh_provider ON vps_health_probes(provider_id);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="vps.provider_manager",
            ))

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return dict(row)

    # ------------------------------------------------------------------
    # Provider CRUD
    # ------------------------------------------------------------------

    def create_provider(self, name: str, tier: str = "STANDARD",
                        region: str = "", vcpu_total: int = 0,
                        ram_gb_total: int = 0, storage_gb_total: int = 0,
                        price_vcpu_h_usd: float = 0.0) -> dict:
        if tier not in VALID_TIERS:
            raise ValueError(f"Invalid tier '{tier}'. Must be one of {VALID_TIERS}")
        provider_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO vps_providers
                (provider_id, name, tier, state, region, vcpu_total, ram_gb_total,
                 storage_gb_total, price_vcpu_h_usd, created_at, updated_at)
                VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?)
            """, (provider_id, name, tier, region, vcpu_total, ram_gb_total,
                  storage_gb_total, price_vcpu_h_usd, now, now))
            # Seed certification stages
            for stage_code in CERT_STAGES:
                self._conn.execute("""
                    INSERT INTO vps_certifications
                    (stage_id, provider_id, stage_code, state, started_at)
                    VALUES (?, ?, ?, 'pending', ?)
                """, (self._uid(), provider_id, stage_code, now))
            self._conn.commit()
        self._emit("vps.provider.created", {"provider_id": provider_id, "name": name})
        log.info("created provider %s (%s)", name, provider_id[:12])
        return {"provider_id": provider_id, "name": name, "state": "candidate"}

    def get_provider(self, provider_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM vps_providers WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_providers(self, state: str | None = None,
                       tier: str | None = None,
                       limit: int = 500) -> list[dict]:
        conditions: list[str] = []
        params: list[Any] = []
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        if tier is not None:
            conditions.append("tier = ?")
            params.append(tier)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM vps_providers {where} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_provider(self, provider_id: str, **fields) -> dict | None:
        allowed = {"name", "tier", "region", "vcpu_total", "ram_gb_total",
                   "storage_gb_total", "price_vcpu_h_usd", "rebuild_role",
                   "cutover_strategy"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_provider(provider_id)
        updates["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [provider_id]
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE vps_providers SET {cols} WHERE provider_id = ?",
                vals,
            )
            self._conn.commit()
        if cur.rowcount == 0:
            return None
        self._emit("vps.provider.updated", {"provider_id": provider_id, "fields": list(updates.keys())})
        return self.get_provider(provider_id)

    def transition_state(self, provider_id: str, new_state: str) -> dict:
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid state '{new_state}'")
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM vps_providers WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Provider {provider_id} not found")
            current = row["state"]
            if new_state not in STATE_TRANSITIONS.get(current, set()):
                raise ValueError(f"Invalid transition: {current} -> {new_state}")
            now = time.time()
            extra = {}
            if new_state == "qualified":
                extra["certified_at"] = now
            self._conn.execute(f"""
                UPDATE vps_providers
                SET state = ?, updated_at = ?{', certified_at = ?' if new_state == 'qualified' else ''}
                WHERE provider_id = ?
            """, (new_state, now, now, provider_id) if new_state == "qualified" else (new_state, now, provider_id))
            self._conn.commit()
        self._emit("vps.provider.transition", {"provider_id": provider_id, "from": current, "to": new_state})
        return {"provider_id": provider_id, "previous": current, "state": new_state}

    def delete_provider(self, provider_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM vps_providers WHERE provider_id = ?",
                (provider_id,),
            )
            self._conn.commit()
        if cur.rowcount:
            self._emit("vps.provider.deleted", {"provider_id": provider_id})
        return bool(cur.rowcount)

    # ------------------------------------------------------------------
    # Allocations
    # ------------------------------------------------------------------

    def allocate(self, provider_id: str, run_id: str,
                 vcpu: int, ram_gb: int) -> dict:
        alloc_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO vps_allocations
                (alloc_id, provider_id, run_id, vcpu, ram_gb, allocated_at, state)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (alloc_id, provider_id, run_id, vcpu, ram_gb, now))
            self._conn.commit()
        self._emit("vps.allocated", {"alloc_id": alloc_id, "provider_id": provider_id, "run_id": run_id})
        return {"alloc_id": alloc_id, "provider_id": provider_id, "run_id": run_id, "state": "active"}

    def release_allocation(self, alloc_id: str) -> bool:
        now = time.time()
        with self._lock:
            cur = self._conn.execute("""
                UPDATE vps_allocations
                SET state = 'released', released_at = ?
                WHERE alloc_id = ? AND state = 'active'
            """, (now, alloc_id))
            self._conn.commit()
        return bool(cur.rowcount)

    def list_allocations(self, provider_id: str | None = None,
                         run_id: str | None = None,
                         state: str | None = None,
                         limit: int = 500) -> list[dict]:
        conditions: list[str] = []
        params: list[Any] = []
        if provider_id:
            conditions.append("provider_id = ?")
            params.append(provider_id)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if state:
            conditions.append("state = ?")
            params.append(state)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM vps_allocations {where} ORDER BY allocated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    def update_certification(self, stage_id: str, state: str,
                             decision_class: str = "",
                             reviewer_id: str = "") -> dict | None:
        if state not in ("pending", "running", "passed", "failed"):
            raise ValueError(f"Invalid cert state '{state}'")
        now = time.time()
        with self._lock:
            cur = self._conn.execute("""
                UPDATE vps_certifications
                SET state = ?, finished_at = ?, decision_class = ?, reviewer_id = ?
                WHERE stage_id = ?
            """, (state, now, decision_class, reviewer_id, stage_id))
            self._conn.commit()
        if cur.rowcount == 0:
            return None
        return self._get_cert(stage_id)

    def _get_cert(self, stage_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM vps_certifications WHERE stage_id = ?",
                (stage_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_certifications(self, provider_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM vps_certifications WHERE provider_id = ? ORDER BY stage_code",
                (provider_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Health probes
    # ------------------------------------------------------------------

    def record_probe(self, provider_id: str, up: bool = True,
                     latency_ms: int = 0, cpu_pct: float = 0.0,
                     ram_pct: float = 0.0, iops: int = 0,
                     error_code: str = "") -> dict:
        probe_id = self._uid()
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO vps_health_probes
                (probe_id, provider_id, timestamp, up, latency_ms, cpu_pct, ram_pct, iops, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (probe_id, provider_id, now, int(up), latency_ms, cpu_pct, ram_pct, iops, error_code))
            self._conn.execute(
                "UPDATE vps_providers SET last_probe_at = ? WHERE provider_id = ?",
                (now, provider_id),
            )
            self._conn.commit()
        self._emit("vps.probe.recorded", {"provider_id": provider_id, "up": up})
        return {"probe_id": probe_id, "provider_id": provider_id, "up": up}

    def list_probes(self, provider_id: str, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM vps_health_probes WHERE provider_id = ? ORDER BY timestamp DESC LIMIT ?",
                (provider_id, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM vps_providers").fetchone()[0]
            by_state_rows = self._conn.execute(
                "SELECT state, COUNT(*) as cnt FROM vps_providers GROUP BY state"
            ).fetchall()
            by_tier_rows = self._conn.execute(
                "SELECT tier, COUNT(*) as cnt FROM vps_providers GROUP BY tier"
            ).fetchall()
            active_allocs = self._conn.execute(
                "SELECT COUNT(*) FROM vps_allocations WHERE state = 'active'"
            ).fetchone()[0]
        return {
            "total_providers": total,
            "by_state": {r["state"]: r["cnt"] for r in by_state_rows},
            "by_tier": {r["tier"]: r["cnt"] for r in by_tier_rows},
            "active_allocations": active_allocs,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: ProviderManager | None = None


def get_provider_manager(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> ProviderManager:
    global _manager
    if _manager is None:
        _manager = ProviderManager(db_path, event_bus)
    return _manager


def reset_provider_manager(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> ProviderManager:
    global _manager
    _manager = ProviderManager(db_path, event_bus)
    return _manager
