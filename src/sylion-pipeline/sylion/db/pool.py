"""
SYLION DB -- PostgreSQL Connection Pool

Async SQLAlchemy connection pool for SYLION modules.
Provides a shared engine that any async module can use.

Usage:
    from sylion.db.pool import get_engine, get_session

    async with get_session() as session:
        result = await session.execute(text("SELECT 1"))
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_DEFAULT_POOL_SIZE = 10
_DEFAULT_MAX_OVERFLOW = 20


@lru_cache(maxsize=1)
def get_engine(
    db_url: str | None = None,
    pool_size: int = _DEFAULT_POOL_SIZE,
    max_overflow: int = _DEFAULT_MAX_OVERFLOW,
) -> AsyncEngine:
    """Get or create the shared async SQLAlchemy engine.

    Parameters
    ----------
    db_url : str, optional
        PostgreSQL async connection string. Falls back to ``SYLION_DB_URL`` env var.
    pool_size : int
        Number of persistent connections in the pool.
    max_overflow : int
        Additional connections allowed beyond pool_size.
    """
    url = db_url or os.environ.get("SYLION_DB_URL", "")
    if not url:
        raise ValueError("PostgreSQL URL required: pass db_url or set SYLION_DB_URL")
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=False,
    )


_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine or get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-style async session dependency.

    Usage as a FastAPI dependency::

        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose of the shared engine (for graceful shutdown)."""
    global _session_factory
    _session_factory = None
    engine = get_engine()
    await engine.dispose()
    get_engine.cache_clear()
