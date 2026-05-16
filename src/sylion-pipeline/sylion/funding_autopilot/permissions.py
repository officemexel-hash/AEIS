from __future__ import annotations

from fastapi import Request


def resolve_actor(request: Request, fallback: str = "workspace-default") -> str:
    header_actor = request.headers.get("x-sylion-actor", "").strip()
    if header_actor:
        return header_actor
    state_user = getattr(request.state, "auth_user", None)
    if isinstance(state_user, dict):
        for key in ("username", "user_id", "email"):
            value = str(state_user.get(key, "")).strip()
            if value:
                return value
    return fallback

