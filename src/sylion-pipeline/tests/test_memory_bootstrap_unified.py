"""Regression tests for unified memory bootstrap."""

from sylion.memory.bootstrap import bootstrap
from sylion.memory.compact_layer import get_compact_layer
from sylion.memory.evidence_store import get_evidence_store
from sylion.memory.indexer import get_indexer
from sylion.memory.kanon_access import KanonSection, get_kanon_access
from sylion.memory.kb_adapter import get_kb_adapter


def test_memory_bootstrap_binds_all_store_singletons_to_same_db(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    bootstrap({"db_path": db_path})

    get_kanon_access().store_section(
        KanonSection(
            section_id="kanon_bootstrap_probe",
            title="Bootstrap Probe",
            content="unified memory bootstrap probe",
        )
    )
    get_compact_layer().record_compaction("alpha alpha beta", "alpha beta")
    get_indexer().index_section(
        "index_bootstrap_probe",
        "Bootstrap Probe",
        "unified memory index probe",
    )
    get_evidence_store().store(
        evidence_id="evidence_bootstrap_probe",
        pack_id="bootstrap",
        artefact_type="runtime_probe",
        name="Bootstrap Evidence",
        content="unified memory evidence probe",
    )
    get_kb_adapter().register_source(
        "kb_bootstrap_probe",
        "Bootstrap KB",
        source_type="file",
        path="docs/bootstrap.md",
    )

    bootstrap({"db_path": db_path})

    assert get_kanon_access().get_section("kanon_bootstrap_probe") is not None
    assert get_compact_layer().get_stats()["total_records"] == 1
    assert get_indexer().search("index probe", limit=5)[0]["section_id"] == "index_bootstrap_probe"
    assert get_evidence_store().retrieve("evidence_bootstrap_probe") is not None
    assert get_kb_adapter().get_source("kb_bootstrap_probe") is not None
