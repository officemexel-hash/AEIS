from sylion.memory.indexer import Indexer
from sylion.memory.retrieval import Retrieval


def test_search_similar_returns_normalized_hits():
    indexer = Indexer()
    indexer.index_section(
        "sec-python",
        "Python Guide",
        "Python is a programming language used for automation and data workflows.",
    )
    indexer.index_section(
        "sec-rust",
        "Rust Guide",
        "Rust is a systems language focused on safety and performance.",
    )

    retrieval = Retrieval(indexer=indexer)
    results = retrieval.search_similar("python automation", k=2)

    assert len(results) >= 1
    assert results[0].section_id == "sec-python"
    assert 0.0 <= results[0].score <= 1.0
    assert results[0].source == "index:sec-python"
    assert isinstance(results[0].text, str)
