"""Memory bootstrap helpers for the shared memory plane."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _coerce_db_path(config: dict[str, Any]) -> str:
    db_path = (
        config.get("db_path")
        or config.get("memory_db_path")
        or config.get("sqlite_path")
        or config.get("path")
        or "memory.sqlite"
    )
    return str(db_path)


def bootstrap(config: dict[str, Any] | None = None) -> None:
    """
    Hook v1.0 (2026-04-24)
    Changes: initial shared memory bootstrap
    """

    cfg = dict(config or {})
    db_path = _coerce_db_path(cfg)
    event_bus = cfg.get("event_bus")
    evidence_spine = cfg.get("evidence_spine")

    from sylion.memory import evidence_store as evidence_store_mod
    from sylion.memory import indexer as indexer_mod
    from sylion.memory import kanon_access as kanon_access_mod
    from sylion.memory import compact_layer as compact_layer_mod
    from sylion.memory import kb_adapter as kb_adapter_mod
    from sylion.memory import retrieval as retrieval_mod
    from sylion.memory import self_model_store as self_model_store_mod

    kanon_access_mod.reset_kanon_access()
    compact_layer_mod.reset_compact_layer()
    indexer_mod.reset_indexer()
    evidence_store_mod.reset_evidence_store()
    kb_adapter_mod.reset_kb_adapter()
    retrieval_mod.reset_retrieval()
    self_model_store_mod.reset_self_model_store()

    kanon_access_mod.get_kanon_access(event_bus=event_bus, db_path=db_path)
    compact_layer_mod.get_compact_layer(event_bus=event_bus, db_path=db_path)
    idx = indexer_mod.get_indexer(event_bus=event_bus, db_path=db_path)
    evidence_store_mod.get_evidence_store(
        event_bus=event_bus,
        evidence_spine=evidence_spine,
        db_path=db_path,
    )
    kb_adapter_mod.get_kb_adapter(event_bus=event_bus, db_path=db_path)
    retrieval_mod.get_retrieval(indexer=idx, event_bus=event_bus)
    self_model_store_mod.get_self_model_store(event_bus=event_bus, db_path=db_path)
