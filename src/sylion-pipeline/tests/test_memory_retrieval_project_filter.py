from sylion.memory.indexer import Indexer
from sylion.memory.retrieval import Retrieval


def test_search_similar_filters_by_project_id(tmp_path):
    indexer = Indexer(db_path=tmp_path / "memory.sqlite")
    indexer.index_section(
        "sec-a",
        "Shared term",
        "alpha project specific content",
        project_id="project-a",
    )
    indexer.index_section(
        "sec-b",
        "Shared term",
        "alpha other project content",
        project_id="project-b",
    )

    retrieval = Retrieval(indexer=indexer)
    hits = retrieval.search_similar("alpha", k=10, project_id="project-a")

    assert [hit.section_id for hit in hits] == ["sec-a"]
    assert hits[0].project_id == "project-a"
