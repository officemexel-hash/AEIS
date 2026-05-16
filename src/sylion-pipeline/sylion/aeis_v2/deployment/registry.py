"""W17 Federation — in-memory NodeRegistry + process singleton.

Phase 0: czysty słownik chroniony ``threading.RLock``-iem. Operacje są
idempotentne (``register`` zastępuje istniejącego node-a po ``node_id``),
a ``list_active`` filtruje po ``last_heartbeat`` (default próg
``STALE_THRESHOLD_S`` = 60 s) + ``status == ONLINE``.

Brak persystencji — restart backendu czyści registry. W G2 ten moduł
zostanie zastąpiony adapterem do W15 OSDK (PG hybrid storage), a
heartbeaty wpadną do append-only event log z hash-chainem dla replay.

API:

- ``register(node)``         → ``Node``  (replace if exists)
- ``update_heartbeat(...)``  → ``bool``  (False = unknown node_id)
- ``unregister(node_id)``    → ``bool``
- ``get(node_id)``           → ``Node | None``
- ``list_all()``             → ``list[Node]``  (sortowane po name)
- ``list_active(stale_secs, clock_skew_buffer_s)``
  → ``list[Node]`` (heartbeat świeży + ``ONLINE``)
- ``clear()``                → ``None`` (test convenience)
- ``size()``                 → ``int``  (test convenience)
"""
from __future__ import annotations

import logging
import threading
import time
import uuid

from sylion.aeis_v2.deployment.nodes import Node, NodeStatus

log = logging.getLogger(__name__)

# W17 P1-4 fix: hoisted from magic 60s to module-level constant so the
# default is documented, monkey-patchable in tests, and overridable via
# ``list_active(stale_secs=...)``.
STALE_THRESHOLD_S = 60.0

# W17 P1-4: tolerance for clock skew between nodes — a heartbeat that
# claims to be "60s ago" by the registering node's clock might really be
# 55-65s ago by the registry's clock under typical NTP drift. Operators
# in multi-node deployments can override via
# ``list_active(clock_skew_buffer_s=10.0)`` when NTP is loose. The default
# 5s covers typical LAN drift and makes the registry slightly stricter
# (mark stale earlier) so heartbeat traffic has a 5s slack to arrive.
CLOCK_SKEW_BUFFER_S = 5.0


class NodeRegistry:
    """Thread-safe registry członków federacji.

    Phase 0 backend = ``dict``. Wszystkie operacje publiczne trzymają
    ``RLock`` — to chroni przed race-ami między ``register`` →
    ``update_heartbeat`` w sytuacji gdy dwa wątki gada do tego samego
    node-a (REST + sweeper).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, Node] = {}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def register(self, node: Node) -> Node:
        """Zarejestruj lub zastąp istniejącego node-a.

        Jeśli ``node.node_id`` jest pusty/None → wygeneruj uuid hex.
        ``last_heartbeat`` ustawiamy na ``time.time()`` żeby świeżo
        zarejestrowany node od razu kwalifikował się do ``list_active``
        (o ile podany ``status`` to ``ONLINE``).
        """
        with self._lock:
            if not node.node_id:
                node.node_id = uuid.uuid4().hex
            node.last_heartbeat = time.time()
            self._nodes[node.node_id] = node
            return node

    def update_heartbeat(
        self,
        node_id: str,
        status: NodeStatus,
        available_models: list[str] | None = None,
    ) -> bool:
        """Odśwież heartbeat istniejącego node-a.

        Zwraca ``False`` gdy ``node_id`` nieznany. Jeśli
        ``available_models`` podane — zastępuje całą listę (snapshot).
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.status = status
            node.last_heartbeat = time.time()
            if available_models is not None:
                node.available_models = list(available_models)
            return True

    def unregister(self, node_id: str) -> bool:
        """Usuń node-a z registry.

        Zwraca ``True`` jeśli istniał, ``False`` jeśli nie.
        """
        with self._lock:
            return self._nodes.pop(node_id, None) is not None

    def clear(self) -> None:
        """Test convenience — wyczyść cały registry."""
        with self._lock:
            self._nodes.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, node_id: str) -> Node | None:
        with self._lock:
            return self._nodes.get(node_id)

    def list_all(self) -> list[Node]:
        with self._lock:
            return sorted(self._nodes.values(), key=lambda n: n.name)

    def list_active(
        self,
        stale_secs: float = STALE_THRESHOLD_S,
        clock_skew_buffer_s: float = CLOCK_SKEW_BUFFER_S,
    ) -> list[Node]:
        """Lista node-ów z ``status == ONLINE`` i świeżym heartbeatem.

        ``stale_secs`` = ile sekund od ostatniego heartbeatu to jeszcze
        akceptowalna świeżość. Default ``STALE_THRESHOLD_S`` (60 s) jest
        zgodny z PDF §8.4 ("nodes cycle status every minute").

        W17 P1-4 fix:

        - **Magic 60s wyciągnięty** do ``STALE_THRESHOLD_S`` na poziomie
          modułu, żeby był dokumentowalny i nadpisywalny.
        - **Operator porównania ``>``** (strict): node z heartbeatem
          świeższym niż próg jest active; dokładnie na progu lub starszy
          → stale. Łatwiej rezonować niż ``>=``.
        - **``clock_skew_buffer_s``** parametr (default
          ``CLOCK_SKEW_BUFFER_S`` = 5 s) absorbuje znaną drift NTP między
          nodes. Efektywny próg to ``stale_secs - clock_skew_buffer_s``
          — czyli odrobinę stricter (mark stale wcześniej) tak żeby
          heartbeat miał 5 s slack na dotarcie.
        - **Future-heartbeat warning**: jeśli ``last_heartbeat > now()``
          (negative skew → zegar nodes idzie do tyłu) emitujemy WARNING
          do operatora; node nie jest cichcem wykluczany.

        Default semantyka: heartbeat starszy niż
        ``stale_secs - clock_skew_buffer_s`` = 55 s → stale.
        """
        now = time.time()
        threshold = now - (stale_secs - clock_skew_buffer_s)
        with self._lock:
            results: list[Node] = []
            for node in self._nodes.values():
                if node.last_heartbeat > now:
                    log.warning(
                        "node %s last_heartbeat=%.3f in future "
                        "(now=%.3f, skew=%.3fs) — likely clock-backwards "
                        "on registering node",
                        node.node_id,
                        node.last_heartbeat,
                        now,
                        node.last_heartbeat - now,
                    )
                if (
                    node.status == NodeStatus.ONLINE
                    and node.last_heartbeat > threshold
                ):
                    results.append(node)
            return sorted(results, key=lambda n: n.name)

    def size(self) -> int:
        with self._lock:
            return len(self._nodes)


# Process-wide singleton — in-memory, gubi się przy restarcie backendu.
# P0-4 fix: double-checked locking on lazy init to prevent two threads from
# each constructing a NodeRegistry and silently dropping state from the loser.
_registry_singleton: NodeRegistry | None = None
_registry_singleton_lock = threading.Lock()

# Backward-compat alias — old internal name still referenced by some callers.
_registry: NodeRegistry | None = None


def get_node_registry() -> NodeRegistry:
    """Zwróć globalny ``NodeRegistry``. Lazy-init z double-checked locking.

    P0-4: classic ``if _x is None: _x = ...`` allowed two concurrent callers
    to both observe ``None``, both construct, and the loser's state would be
    silently lost. We now use double-checked locking so only one thread builds.

    Testy mogą wymusić reset poprzez ``get_node_registry().clear()``.
    """
    global _registry_singleton, _registry
    # Fast path — already initialized, no lock contention.
    if _registry_singleton is not None:
        return _registry_singleton
    # Slow path — serialize construction.
    with _registry_singleton_lock:
        if _registry_singleton is not None:  # double-check inside lock
            return _registry_singleton
        _registry_singleton = NodeRegistry()
        _registry = _registry_singleton  # keep legacy name in sync
        return _registry_singleton
