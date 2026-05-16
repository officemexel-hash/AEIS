"""Tests for sylion.memory.retrieval module."""
import pytest
from sylion.memory.indexer import Indexer
from sylion.memory.retrieval import Retrieval


class TestRetrieval:
    @pytest.fixture
    def retrieval(self):
        idx = Indexer()
        return Retrieval(indexer=idx)

    def _seed(self, retrieval):
        retrieval._indexer.index_section("r1", "Python Basics", "python is a popular programming language used for web development and data science")
        retrieval._indexer.index_section("r2", "JavaScript Guide", "javascript is used for frontend web development and node.js backend")
        retrieval._indexer.index_section("r3", "Rust Systems", "rust is a systems programming language focused on safety and performance")

    def test_retrieve(self, retrieval):
        self._seed(retrieval)
        results = retrieval.retrieve("python programming")
        assert len(results) >= 1
        assert hasattr(results[0], "section_id")
        assert hasattr(results[0], "score")

    def test_retrieve_with_limit(self, retrieval):
        self._seed(retrieval)
        results = retrieval.retrieve("web development", limit=2)
        assert len(results) <= 2

    def test_retrieve_with_min_score(self, retrieval):
        self._seed(retrieval)
        results = retrieval.retrieve("programming", min_score=1.0)
        assert isinstance(results, list)

    def test_retrieve_no_results(self, retrieval):
        results = retrieval.retrieve("zzzznonexistentxyz")
        assert isinstance(results, list)

    def test_get_context(self, retrieval):
        self._seed(retrieval)
        context = retrieval.get_context("python programming", max_tokens=100)
        assert isinstance(context, str)

    def test_get_context_empty(self, retrieval):
        context = retrieval.get_context("zzzznonexistentxyz")
        assert isinstance(context, str)
