from sylion.memory import append, bootstrap, get, search_similar, stats
from sylion.memory.evidence_store import reset_evidence_store
from sylion.memory.indexer import reset_indexer
from sylion.memory.retrieval import reset_retrieval
from sylion.memory.self_model_store import reset_self_model_store


def _reset_all() -> None:
    reset_indexer()
    reset_evidence_store()
    reset_retrieval()
    reset_self_model_store()


def test_public_hooks_are_importable_and_work(tmp_path):
    _reset_all()
    bootstrap({"db_path": tmp_path / "memory.sqlite"})

    evidence_id = append({
        "pack_id": "pack-1",
        "artefact_type": "test_result",
        "name": "hook-test",
        "content": "payload",
        "metadata": {"scope": "memory"},
    })

    assert get(evidence_id)["name"] == "hook-test"
    assert stats()["total_evidence"] == 1
    assert search_similar("nonexistent", k=3) == []

    _reset_all()
