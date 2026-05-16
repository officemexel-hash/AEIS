"""
SYLION API -- FastAPI REST routes for the SYLION AEIS v3.5 system.

Exposes all 65 SYLION modules through versioned REST endpoints.
"""

try:
    from sylion.api.router import router
except ImportError:
    # Package init must remain importable even if a downstream route module
    # has a broken import. Direct importers of `sylion.api.router` will still
    # surface the underlying error explicitly.
    router = None

__all__ = ["router"]
