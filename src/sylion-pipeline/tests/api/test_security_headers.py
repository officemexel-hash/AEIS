from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from sylion.api.security_headers import SecurityHeadersMiddleware


async def _ok(request):
    return JSONResponse({"ok": True})


async def _custom_csp(request):
    return JSONResponse(
        {"ok": True},
        headers={"Content-Security-Policy": "default-src 'self'"},
    )


def _client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/health", _ok),
            Route("/docs", _ok),
            Route("/custom-csp", _custom_csp),
        ],
        middleware=[Middleware(SecurityHeadersMiddleware)],
    )
    return TestClient(app)


def test_security_headers_are_added_to_api_response():
    response = _client().get("/health")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_docs_route_uses_docs_safe_csp():
    response = _client().get("/docs")

    assert response.status_code == 200
    assert "default-src 'self' https:" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_existing_csp_is_not_overwritten():
    response = _client().get("/custom-csp")

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
    assert response.headers["X-Frame-Options"] == "DENY"
