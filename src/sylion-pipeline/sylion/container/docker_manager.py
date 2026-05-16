"""
SYLION Container -- Docker & Kubernetes Manager

Manages Docker containers, images, K8s pods and deployments.
SQLite-backed with WAL mode. Thread-safe via threading.RLock().
Singleton via get_container_manager() / reset_container_manager().
Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.container.docker_manager")


class ContainerManager:
    """Docker & K8s container manager backed by SQLite."""

    def __init__(self, db_path: str = ":memory:", event_bus: EventBus | None = None):
        self._db_path = db_path
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS docker_containers (
                container_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                ports TEXT NOT NULL DEFAULT '[]',
                env TEXT NOT NULL DEFAULT '{}',
                labels TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS docker_images (
                image_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tag TEXT NOT NULL DEFAULT 'latest',
                size_mb INTEGER NOT NULL DEFAULT 0,
                labels TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS k8s_pods (
                pod_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL DEFAULT 'Pending',
                node TEXT NOT NULL DEFAULT '',
                containers TEXT NOT NULL DEFAULT '[]',
                labels TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS k8s_deployments (
                deployment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                replicas INTEGER NOT NULL DEFAULT 1,
                available INTEGER NOT NULL DEFAULT 0,
                strategy TEXT NOT NULL DEFAULT 'RollingUpdate',
                labels TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="container.docker_manager",
            ))

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for k in ("ports", "env", "labels", "containers"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    # ------------------------------------------------------------------
    # Docker Containers
    # ------------------------------------------------------------------

    def register_container(self, name: str, image: str = "", status: str = "created",
                           ports: list | None = None, env: dict | None = None,
                           labels: dict | None = None) -> dict:
        cid = self._uid()
        now = time.time()
        ports = ports or []
        env = env or {}
        labels = labels or {}
        with self._lock:
            self._conn.execute("""
                INSERT INTO docker_containers (container_id, name, image, status, ports, env, labels, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, name, image, status, json.dumps(ports), json.dumps(env), json.dumps(labels), now))
            self._conn.commit()
        self._emit("container.registered", {"container_id": cid, "name": name})
        return {"container_id": cid, "name": name, "image": image, "status": status, "created_at": now}

    def list_containers(self, status: str | None = None) -> list[dict]:
        q, p = "SELECT * FROM docker_containers WHERE 1=1", []
        if status:
            q += " AND status = ?"; p.append(status)
        with self._lock:
            rows = self._conn.execute(q + " ORDER BY created_at DESC", p).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_container(self, container_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM docker_containers WHERE container_id = ?", (container_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def update_container(self, container_id: str, **fields) -> dict | None:
        allowed = {"name", "image", "status", "ports", "env", "labels"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_container(container_id)
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM docker_containers WHERE container_id = ?", (container_id,)).fetchone()
            if not row:
                return None
            for k, v in updates.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                self._conn.execute(f"UPDATE docker_containers SET {k} = ? WHERE container_id = ?", (v, container_id))
            self._conn.commit()
        self._emit("container.updated", {"container_id": container_id})
        return self.get_container(container_id)

    def delete_container(self, container_id: str) -> bool:
        with self._lock:
            n = self._conn.execute("DELETE FROM docker_containers WHERE container_id = ?", (container_id,)).rowcount
            self._conn.commit()
        if n:
            self._emit("container.deleted", {"container_id": container_id})
        return bool(n)

    # ------------------------------------------------------------------
    # Docker Images
    # ------------------------------------------------------------------

    def register_image(self, name: str, tag: str = "latest", size_mb: int = 0,
                       labels: dict | None = None) -> dict:
        iid = self._uid()
        now = time.time()
        labels = labels or {}
        with self._lock:
            self._conn.execute("""
                INSERT INTO docker_images (image_id, name, tag, size_mb, labels, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (iid, name, tag, size_mb, json.dumps(labels), now))
            self._conn.commit()
        self._emit("image.registered", {"image_id": iid, "name": name, "tag": tag})
        return {"image_id": iid, "name": name, "tag": tag, "size_mb": size_mb, "created_at": now}

    def list_images(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM docker_images ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_image(self, image_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM docker_images WHERE image_id = ?", (image_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_image(self, image_id: str) -> bool:
        with self._lock:
            n = self._conn.execute("DELETE FROM docker_images WHERE image_id = ?", (image_id,)).rowcount
            self._conn.commit()
        return bool(n)

    # ------------------------------------------------------------------
    # K8s Pods
    # ------------------------------------------------------------------

    def register_pod(self, name: str, namespace: str = "default", status: str = "Pending",
                     node: str = "", containers: list | None = None,
                     labels: dict | None = None) -> dict:
        pid = self._uid()
        now = time.time()
        containers = containers or []
        labels = labels or {}
        with self._lock:
            self._conn.execute("""
                INSERT INTO k8s_pods (pod_id, name, namespace, status, node, containers, labels, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pid, name, namespace, status, node, json.dumps(containers), json.dumps(labels), now))
            self._conn.commit()
        self._emit("pod.registered", {"pod_id": pid, "name": name, "namespace": namespace})
        return {"pod_id": pid, "name": name, "namespace": namespace, "status": status, "created_at": now}

    def list_pods(self, namespace: str | None = None) -> list[dict]:
        q, p = "SELECT * FROM k8s_pods WHERE 1=1", []
        if namespace:
            q += " AND namespace = ?"; p.append(namespace)
        with self._lock:
            rows = self._conn.execute(q + " ORDER BY created_at DESC", p).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_pod(self, pod_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM k8s_pods WHERE pod_id = ?", (pod_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def update_pod(self, pod_id: str, **fields) -> dict | None:
        allowed = {"name", "namespace", "status", "node", "containers", "labels"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_pod(pod_id)
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM k8s_pods WHERE pod_id = ?", (pod_id,)).fetchone()
            if not row:
                return None
            for k, v in updates.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                self._conn.execute(f"UPDATE k8s_pods SET {k} = ? WHERE pod_id = ?", (v, pod_id))
            self._conn.commit()
        return self.get_pod(pod_id)

    def delete_pod(self, pod_id: str) -> bool:
        with self._lock:
            n = self._conn.execute("DELETE FROM k8s_pods WHERE pod_id = ?", (pod_id,)).rowcount
            self._conn.commit()
        return bool(n)

    # ------------------------------------------------------------------
    # K8s Deployments
    # ------------------------------------------------------------------

    def register_deployment(self, name: str, namespace: str = "default", replicas: int = 1,
                            available: int = 0, strategy: str = "RollingUpdate",
                            labels: dict | None = None) -> dict:
        did = self._uid()
        now = time.time()
        labels = labels or {}
        with self._lock:
            self._conn.execute("""
                INSERT INTO k8s_deployments (deployment_id, name, namespace, replicas, available, strategy, labels, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (did, name, namespace, replicas, available, strategy, json.dumps(labels), now))
            self._conn.commit()
        self._emit("deployment.registered", {"deployment_id": did, "name": name, "namespace": namespace})
        return {"deployment_id": did, "name": name, "namespace": namespace, "replicas": replicas, "available": available, "strategy": strategy, "created_at": now}

    def list_deployments(self, namespace: str | None = None) -> list[dict]:
        q, p = "SELECT * FROM k8s_deployments WHERE 1=1", []
        if namespace:
            q += " AND namespace = ?"; p.append(namespace)
        with self._lock:
            rows = self._conn.execute(q + " ORDER BY created_at DESC", p).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_deployment(self, deployment_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM k8s_deployments WHERE deployment_id = ?", (deployment_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def update_deployment(self, deployment_id: str, **fields) -> dict | None:
        allowed = {"name", "namespace", "replicas", "available", "strategy", "labels"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_deployment(deployment_id)
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM k8s_deployments WHERE deployment_id = ?", (deployment_id,)).fetchone()
            if not row:
                return None
            for k, v in updates.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                self._conn.execute(f"UPDATE k8s_deployments SET {k} = ? WHERE deployment_id = ?", (v, deployment_id))
            self._conn.commit()
        return self.get_deployment(deployment_id)

    def delete_deployment(self, deployment_id: str) -> bool:
        with self._lock:
            n = self._conn.execute("DELETE FROM k8s_deployments WHERE deployment_id = ?", (deployment_id,)).rowcount
            self._conn.commit()
        return bool(n)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        with self._lock:
            containers = self._conn.execute("SELECT COUNT(*) as cnt FROM docker_containers").fetchone()["cnt"]
            images = self._conn.execute("SELECT COUNT(*) as cnt FROM docker_images").fetchone()["cnt"]
            pods = self._conn.execute("SELECT COUNT(*) as cnt FROM k8s_pods").fetchone()["cnt"]
            deployments = self._conn.execute("SELECT COUNT(*) as cnt FROM k8s_deployments").fetchone()["cnt"]
        return {
            "docker_containers": containers,
            "docker_images": images,
            "k8s_pods": pods,
            "k8s_deployments": deployments,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: ContainerManager | None = None


def get_container_manager(db_path: str = ":memory:", event_bus: EventBus | None = None) -> ContainerManager:
    """Get or create the global ContainerManager singleton."""
    global _instance
    if _instance is None:
        _instance = ContainerManager(db_path, event_bus)
    return _instance


def reset_container_manager() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
