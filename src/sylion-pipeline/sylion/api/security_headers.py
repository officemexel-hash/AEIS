"""HTTP security headers middleware for AEIS API responses."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative browser security headers to every API response."""

    API_CSP = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )
    DOCS_CSP = (
        "default-src 'self' https: 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "style-src 'self' https: 'unsafe-inline'; "
        "script-src 'self' https: 'unsafe-inline'; "
        "frame-ancestors 'none'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            self.DOCS_CSP if path in {"/docs", "/redoc"} else self.API_CSP,
        )
        return response


__all__ = ["SecurityHeadersMiddleware"]
