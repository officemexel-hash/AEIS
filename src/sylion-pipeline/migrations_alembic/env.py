"""Alembic environment for the SQLite runtime schema capture."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import MetaData, create_engine, engine_from_config, pool
from sqlalchemy.engine import Connection, make_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

log = logging.getLogger("alembic.env")

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def _resolve_sqlite_url(raw_url: str) -> str:
    """Resolve a relative sqlite:/// URL against the project or repo root."""
    url = make_url(raw_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return raw_url
    db_path = Path(url.database)
    if db_path.is_absolute():
        return raw_url
    project_candidate = PROJECT_DIR / db_path
    repo_candidate = REPO_ROOT / db_path
    resolved = repo_candidate if repo_candidate.exists() else project_candidate
    return f"sqlite:///{resolved.as_posix()}"


def _candidate_module_names() -> list[str]:
    sylion_root = PROJECT_DIR / "sylion"
    markers = (
        "DeclarativeBase",
        "declarative_base",
        "mapped_column",
        "__tablename__",
        "Table(",
        "MetaData(",
    )
    candidates: list[str] = []
    for py_file in sylion_root.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not any(marker in text for marker in markers):
            continue
        module_name = ".".join(py_file.relative_to(PROJECT_DIR).with_suffix("").parts)
        candidates.append(module_name)
    return sorted(set(candidates))


def _collect_metadata_from_module(module: object) -> list[MetaData]:
    discovered: list[MetaData] = []
    for value in vars(module).values():
        metadata = None
        if isinstance(value, MetaData):
            metadata = value
        elif hasattr(value, "metadata") and isinstance(value.metadata, MetaData):
            metadata = value.metadata
        if metadata is not None and metadata.tables:
            discovered.append(metadata)
    return discovered


def _discover_sqlalchemy_metadata() -> MetaData | None:
    aggregate = MetaData()
    module_names = _candidate_module_names()
    if not module_names:
        log.info("No SQLAlchemy model candidates found under sylion/.")
        return None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - defensive import guard
            log.warning("Skipping %s during Alembic discovery: %s", module_name, exc)
            continue
        for metadata in _collect_metadata_from_module(module):
            for table in metadata.sorted_tables:
                table.to_metadata(aggregate)
    if not aggregate.tables:
        log.info("SQLAlchemy model candidates imported, but no metadata was exposed.")
        return None
    log.info("Loaded SQLAlchemy metadata for %d tables.", len(aggregate.tables))
    return aggregate


def _reflect_runtime_metadata(resolved_url: str) -> MetaData | None:
    url = make_url(resolved_url)
    if url.drivername != "sqlite" or not url.database:
        return None
    db_path = Path(url.database)
    if not db_path.exists():
        log.warning("Reflection fallback skipped because %s does not exist.", db_path)
        return None
    engine = create_engine(resolved_url, future=True)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        if metadata.tables:
            log.info("Reflected %d tables from %s.", len(metadata.tables), db_path)
            return metadata
        return None
    finally:
        engine.dispose()


runtime_url = os.environ.get("ALEMBIC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
resolved_runtime_url = _resolve_sqlite_url(runtime_url)
config.set_main_option("sqlalchemy.url", resolved_runtime_url)
target_metadata = _discover_sqlalchemy_metadata() or _reflect_runtime_metadata(resolved_runtime_url)


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=resolved_runtime_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
