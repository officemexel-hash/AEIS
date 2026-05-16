"""
SYLION API -- Surface routes.

Endpoints for: console_api, console_ui, ws_gateway.
"""

from fastapi import APIRouter, HTTPException

from sylion.surface.console_api import get_console_api
from sylion.surface.console_ui import get_console_ui
from sylion.surface.ws_gateway import get_ws_gateway

router = APIRouter(prefix="/api/v1/surface", tags=["surface"])


# ---------------------------------------------------------------------------
# Console API
# ---------------------------------------------------------------------------

@router.post("/console/endpoints", status_code=201)
def register_console_endpoint(path: str, method: str = "GET",
                              handler: str = "",
                              auth_required: bool = True,
                              rbac_roles: str = "",
                              description: str = ""):
    """Register a console API endpoint."""
    api = get_console_api()
    roles = [r.strip() for r in rbac_roles.split(",") if r.strip()]
    return api.register(path, method=method, handler=handler,
                        auth_required=auth_required,
                        rbac_roles=roles if roles else None,
                        description=description)


@router.get("/console/endpoints")
def list_console_endpoints(active_only: bool = True, limit: int = 100):
    """List console API endpoints."""
    api = get_console_api()
    return {"endpoints": api.list_endpoints(active_only=active_only,
                                            limit=limit)}


@router.get("/console/endpoints/{endpoint_id}")
def get_console_endpoint(endpoint_id: str):
    """Get a console endpoint by ID."""
    api = get_console_api()
    result = api.get_endpoint(endpoint_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Endpoint {endpoint_id} not found")
    return result


@router.post("/console/requests", status_code=201)
def record_console_request(endpoint_id: str, user_id: str = "",
                           status_code: int = 200, latency_ms: int = 0):
    """Record a console API request."""
    api = get_console_api()
    return api.record_request(endpoint_id, user_id=user_id,
                              status_code=status_code,
                              latency_ms=latency_ms)


@router.get("/console/stats")
def console_stats():
    """Get console API statistics."""
    api = get_console_api()
    return api.get_stats()


# ---------------------------------------------------------------------------
# Console UI
# ---------------------------------------------------------------------------

@router.post("/ui/components", status_code=201)
def register_ui_component(name: str, panel: str = "",
                          component_type: str = "panel",
                          config: str = "{}", order_num: int = 0):
    """Register a UI component."""
    import json
    ui = get_console_ui()
    return ui.register_component(
        name, panel=panel, component_type=component_type,
        config=json.loads(config) if isinstance(config, str) else None,
        order_num=order_num,
    )


@router.get("/ui/components")
def list_ui_components(panel: str | None = None, active_only: bool = True,
                       limit: int = 100):
    """List UI components."""
    ui = get_console_ui()
    return {"components": ui.list_components(panel=panel,
                                             active_only=active_only,
                                             limit=limit)}


@router.post("/ui/layouts", status_code=201)
def create_ui_layout(name: str, panels: str = "", role: str = "viewer"):
    """Create a UI layout."""
    ui = get_console_ui()
    panel_list = [p.strip() for p in panels.split(",") if p.strip()]
    return ui.create_layout(name, panels=panel_list if panel_list else None,
                            role=role)


@router.get("/ui/layouts")
def list_ui_layouts(role: str | None = None, active_only: bool = True,
                    limit: int = 100):
    """List UI layouts."""
    ui = get_console_ui()
    return {"layouts": ui.list_layouts(role=role, active_only=active_only,
                                       limit=limit)}


@router.get("/ui/layouts/{layout_id}")
def get_ui_layout(layout_id: str):
    """Get a UI layout by ID."""
    ui = get_console_ui()
    result = ui.get_layout(layout_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Layout {layout_id} not found")
    return result


# ---------------------------------------------------------------------------
# WebSocket Gateway
# ---------------------------------------------------------------------------

@router.post("/ws/connect", status_code=201)
def ws_connect(user_id: str = "", client_id: str = "",
               channels: str = ""):
    """Register a WebSocket connection."""
    gw = get_ws_gateway()
    ch_list = [c.strip() for c in channels.split(",") if c.strip()]
    return gw.connect(user_id=user_id, client_id=client_id,
                      channels=ch_list if ch_list else None)


@router.post("/ws/{conn_id}/disconnect")
def ws_disconnect(conn_id: str):
    """Disconnect a WebSocket connection."""
    gw = get_ws_gateway()
    return gw.disconnect(conn_id)


@router.get("/ws/connections")
def ws_connections(status: str | None = None, limit: int = 100):
    """List WebSocket connections."""
    gw = get_ws_gateway()
    return {"connections": gw.get_connections(status=status, limit=limit)}


@router.post("/ws/{conn_id}/subscribe")
def ws_subscribe(conn_id: str, channels: str = ""):
    """Subscribe a connection to channels."""
    gw = get_ws_gateway()
    ch_list = [c.strip() for c in channels.split(",") if c.strip()]
    return gw.subscribe(conn_id, ch_list)


@router.post("/ws/{conn_id}/send")
def ws_send(conn_id: str, channel: str, payload: str = "{}"):
    """Send a message to a specific connection."""
    import json
    gw = get_ws_gateway()
    return gw.send(conn_id, channel,
                   payload=json.loads(payload) if isinstance(payload, str) else None)


@router.post("/ws/broadcast")
def ws_broadcast(channel: str, payload: str = "{}"):
    """Broadcast a message to all connections on a channel."""
    import json
    gw = get_ws_gateway()
    return gw.broadcast(channel,
                        payload=json.loads(payload) if isinstance(payload, str) else None)


@router.get("/ws/messages")
def ws_messages(conn_id: str | None = None, channel: str | None = None,
                limit: int = 100):
    """Get WebSocket message history."""
    gw = get_ws_gateway()
    return {"messages": gw.get_messages(conn_id=conn_id, channel=channel,
                                        limit=limit)}


@router.get("/ws/stats")
def ws_stats():
    """Get WebSocket gateway statistics."""
    gw = get_ws_gateway()
    return gw.get_stats()
