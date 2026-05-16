"""
SYLION Core — NATS JetStream Health Check

Lightweight connectivity probe used by the /health endpoint.
Connects, reads server info, and returns a structured status dict.
Gracefully handles the case where NATS is not running or nats-py is not installed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("sylion.core.nats_health")


def check_nats_health(nats_url: str) -> dict[str, Any]:
    """Check NATS connectivity.

    Returns a dict with:
        connected      — bool
        server_id      — str (server name / id, or empty)
        cluster        — str (cluster name, or empty)
        streams_count  — int (number of JetStream streams, or 0)

    Falls back gracefully when NATS is unreachable or nats-py is missing.
    """
    try:
        return asyncio.run(_check_async(nats_url))
    except Exception as exc:
        log.debug("NATS health check failed: %s", exc)
        return {
            "connected": False,
            "server_id": "",
            "cluster": "",
            "streams_count": 0,
            "error": str(exc),
        }


async def _check_async(nats_url: str) -> dict[str, Any]:
    try:
        import nats
    except ImportError:
        return {
            "connected": False,
            "server_id": "",
            "cluster": "",
            "streams_count": 0,
            "error": "nats-py not installed",
        }

    nc = None
    try:
        nc = await nats.connect(nats_url, connect_timeout=3, reconnect=False)

        server_info = nc.connected_url
        server_id = nc.servers[0] if nc.servers else ""

        # Try to read JetStream account info for stream count
        streams_count = 0
        cluster_name = ""
        try:
            js = nc.jetstream()
            account_info = await js.account_info()
            streams_count = getattr(account_info, "streams", 0)
            cluster_name = getattr(account_info, "cluster", "")
            if hasattr(cluster_name, "name"):
                cluster_name = cluster_name.name
        except Exception:
            pass  # JetStream not available or not configured

        return {
            "connected": True,
            "server_id": str(server_id) if server_id else str(server_info),
            "cluster": str(cluster_name),
            "streams_count": streams_count,
        }
    except Exception as exc:
        return {
            "connected": False,
            "server_id": "",
            "cluster": "",
            "streams_count": 0,
            "error": str(exc),
        }
    finally:
        if nc is not None:
            try:
                await nc.close()
            except Exception:
                pass
