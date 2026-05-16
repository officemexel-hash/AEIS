from pathlib import Path

from sylion.memory import bootstrap
from sylion.memory.evidence_store import get_evidence_store, reset_evidence_store
from sylion.memory.indexer import get_indexer, reset_indexer
from sylion.memory.retrieval import get_retrieval, reset_retrieval
from sylion.memory.self_model_store import get_self_model_store, reset_self_model_store


def _reset_all() -> None:
    reset_indexer()
    reset_evidence_store()
    reset_retrieval()
    reset_self_model_store()


def test_bootstrap_initializes_shared_memory_plane(tmp_path):
    _reset_all()
    db_path = tmp_path / "memory.sqlite"

    bootstrap({"db_path": db_path})

    indexer = get_indexer()
    evidence_store = get_evidence_store()
    retrieval = get_retrieval()
    self_model_store = get_self_model_store()

    assert indexer._db_path == str(db_path)
    assert evidence_store._db_path == str(db_path)
    assert self_model_store._db_path == str(db_path)
    assert retrieval.indexer is indexer

    _reset_all()
