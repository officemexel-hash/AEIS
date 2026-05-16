"""
SYLION Anti-Hallucination Layer 4: SemanticDedup

Uses sentence-transformers (or a lightweight fallback) to deduplicate
audit findings by semantic similarity. Multiple auditors often report
the same issue with different wording — this layer groups them and
assigns a canonical representative per cluster.

Prevents double-counting of findings during merge (Stage 4) and
reduces noise in the final report.

Phase: Enhancement (not a blocker for Phase 1, required for Phase 2-3 autonomy)
Estimated effort: ~120 lines, 2 days (embedding model setup + tuning)

Dependencies (optional):
    pip install sentence-transformers   # Full mode
    pip install scikit-learn            # Fallback TF-IDF mode

If sentence-transformers is unavailable, falls back to TF-IDF + cosine
similarity (scikit-learn), which is less accurate but requires no GPU.
If neither is available, falls back to keyword overlap (Jaccard similarity).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("semantic_dedup")


class DedupBackend(str, Enum):
    """Which embedding backend is being used."""
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    TFIDF = "tfidf"
    JACCARD = "jaccard"  # Pure-Python fallback


@dataclass
class FindingCluster:
    """A group of semantically similar findings."""
    cluster_id: int
    canonical_id: str           # ID of the representative finding
    member_ids: list[str]       # All finding IDs in this cluster
    similarity_scores: list[float]  # Pairwise similarities to canonical
    file_path: str              # Common file (if any)
    title: str                  # Title from the canonical finding

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "canonical_id": self.canonical_id,
            "member_ids": self.member_ids,
            "similarity_scores": [round(s, 3) for s in self.similarity_scores],
            "file_path": self.file_path,
            "title": self.title,
            "size": len(self.member_ids),
        }


@dataclass
class DedupResult:
    """Outcome of semantic deduplication."""
    backend: DedupBackend
    total_findings: int
    unique_clusters: int
    duplicates_removed: int
    clusters: list[FindingCluster]
    similarity_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend.value,
            "total_findings": self.total_findings,
            "unique_clusters": self.unique_clusters,
            "duplicates_removed": self.duplicates_removed,
            "dedup_ratio": round(
                self.duplicates_removed / self.total_findings, 3
            ) if self.total_findings > 0 else 0.0,
            "similarity_threshold": self.similarity_threshold,
            "clusters": [c.to_dict() for c in self.clusters],
        }


class SemanticDedup:
    """Layer 4 anti-hallucination: semantic deduplication of audit findings.

    Groups findings that describe the same issue in different words.
    Supports three backends (auto-selects best available):
      1. sentence-transformers (best accuracy, needs torch)
      2. TF-IDF + cosine (good accuracy, needs scikit-learn)
      3. Jaccard keyword overlap (basic, no dependencies)

    Usage:
        sd = SemanticDedup(similarity_threshold=0.75)
        findings = [
            {"id": "FIND-001", "file": "pkg/auth/handler.go", "line": 42,
             "title": "XFF header trusted without validation", ...},
            {"id": "FIND-099", "file": "pkg/auth/handler.go", "line": 42,
             "title": "Unsafe use of X-Forwarded-For header", ...},
        ]
        result = sd.deduplicate(findings)
        # result.unique_clusters == 1 (both findings describe the same issue)
    """

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.75,
        model_name: str = "all-MiniLM-L6-v2",
        log_dir: Path | None = None,
        force_backend: DedupBackend | None = None,
    ):
        """
        Args:
            similarity_threshold: Minimum cosine similarity to consider findings duplicates.
            model_name: Sentence-transformers model name (only if that backend is used).
            log_dir: Directory to write dedup logs.
            force_backend: Force a specific backend instead of auto-detection.
        """
        self.similarity_threshold = similarity_threshold
        self.model_name = model_name
        self.log_dir = log_dir
        self._encoder = None

        if force_backend:
            self.backend = force_backend
        else:
            self.backend = self._detect_backend()

        log.info("SemanticDedup initialized with backend: %s", self.backend.value)

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate(self, findings: list[dict[str, Any]]) -> DedupResult:
        """Deduplicate a list of audit findings by semantic similarity.

        Args:
            findings: List of finding dicts. Must have at least 'id' and 'title' fields.
                      Optional: 'file', 'line', 'description', 'evidence'.

        Returns:
            DedupResult with clusters of similar findings.
        """
        if not findings:
            return DedupResult(
                backend=self.backend,
                total_findings=0,
                unique_clusters=0,
                duplicates_removed=0,
                clusters=[],
                similarity_threshold=self.similarity_threshold,
            )

        # Build text representations
        texts = [self._finding_to_text(f) for f in findings]
        ids = [f.get("id", f.get("finding_id", f"UNKNOWN-{i}")) for i, f in enumerate(findings)]

        # Compute similarity matrix
        sim_matrix = self._compute_similarity_matrix(texts)

        # Cluster by greedy nearest-neighbor
        clusters = self._cluster_findings(ids, findings, sim_matrix)

        duplicates = sum(len(c.member_ids) - 1 for c in clusters)

        result = DedupResult(
            backend=self.backend,
            total_findings=len(findings),
            unique_clusters=len(clusters),
            duplicates_removed=duplicates,
            clusters=clusters,
            similarity_threshold=self.similarity_threshold,
        )

        if self.log_dir:
            self._save_report(result)

        log.info(
            "SemanticDedup: %d findings → %d clusters (%d duplicates removed, threshold=%.2f)",
            len(findings), len(clusters), duplicates, self.similarity_threshold,
        )
        return result

    def get_canonical_findings(
        self,
        findings: list[dict[str, Any]],
        result: DedupResult,
    ) -> list[dict[str, Any]]:
        """Return only the canonical (representative) finding from each cluster.

        Args:
            findings: Original findings list.
            result: DedupResult from deduplicate().

        Returns:
            Deduplicated list of findings (one per cluster).
        """
        canonical_ids = {c.canonical_id for c in result.clusters}
        id_key = "id" if any("id" in f for f in findings) else "finding_id"
        return [f for f in findings if f.get(id_key) in canonical_ids]

    # ------------------------------------------------------------------
    # Backend detection
    # ------------------------------------------------------------------

    def _detect_backend(self) -> DedupBackend:
        """Auto-detect the best available backend."""
        try:
            import sentence_transformers  # noqa: F401
            return DedupBackend.SENTENCE_TRANSFORMERS
        except ImportError:
            pass

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401
            from sklearn.metrics.pairwise import cosine_similarity  # noqa: F401
            return DedupBackend.TFIDF
        except ImportError:
            pass

        log.warning(
            "SemanticDedup: neither sentence-transformers nor scikit-learn available. "
            "Falling back to Jaccard similarity (less accurate)."
        )
        return DedupBackend.JACCARD

    # ------------------------------------------------------------------
    # Similarity computation per backend
    # ------------------------------------------------------------------

    def _compute_similarity_matrix(self, texts: list[str]) -> list[list[float]]:
        """Compute pairwise similarity matrix using the active backend."""
        n = len(texts)
        if n == 0:
            return []

        if self.backend == DedupBackend.SENTENCE_TRANSFORMERS:
            return self._sim_sentence_transformers(texts)
        elif self.backend == DedupBackend.TFIDF:
            return self._sim_tfidf(texts)
        else:
            return self._sim_jaccard(texts)

    def _sim_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        """Compute cosine similarity using sentence-transformers embeddings."""
        from sentence_transformers import SentenceTransformer
        import numpy as np

        if self._encoder is None:
            self._encoder = SentenceTransformer(self.model_name)

        embeddings = self._encoder.encode(texts, show_progress_bar=False)
        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normed = embeddings / norms
        sim = (normed @ normed.T).tolist()
        return sim

    def _sim_tfidf(self, texts: list[str]) -> list[list[float]]:
        """Compute cosine similarity using TF-IDF vectors."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim = cosine_similarity(tfidf_matrix).tolist()
        return sim

    def _sim_jaccard(self, texts: list[str]) -> list[list[float]]:
        """Compute Jaccard similarity using token sets (pure-Python fallback)."""
        tokenized = [self._tokenize(t) for t in texts]
        n = len(tokenized)
        sim = [[0.0] * n for _ in range(n)]
        for i in range(n):
            sim[i][i] = 1.0
            for j in range(i + 1, n):
                intersection = len(tokenized[i] & tokenized[j])
                union = len(tokenized[i] | tokenized[j])
                score = intersection / union if union > 0 else 0.0
                sim[i][j] = score
                sim[j][i] = score
        return sim

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def _cluster_findings(
        self,
        ids: list[str],
        findings: list[dict[str, Any]],
        sim_matrix: list[list[float]],
    ) -> list[FindingCluster]:
        """Greedy nearest-neighbor clustering.

        Iterates through findings in order. For each finding, checks if it
        is similar enough to any existing cluster's canonical. If so, merges.
        Otherwise, starts a new cluster.
        """
        n = len(ids)
        assigned = [False] * n
        clusters: list[FindingCluster] = []
        cluster_id = 0

        for i in range(n):
            if assigned[i]:
                continue

            # Start new cluster with i as canonical
            members = [ids[i]]
            scores = [1.0]
            assigned[i] = True

            # Find all unassigned findings similar to i
            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                # Also require same file (if specified) for tighter dedup
                file_i = findings[i].get("file", "")
                file_j = findings[j].get("file", "")
                if file_i and file_j and file_i != file_j:
                    continue

                if sim_matrix[i][j] >= self.similarity_threshold:
                    members.append(ids[j])
                    scores.append(sim_matrix[i][j])
                    assigned[j] = True

            clusters.append(FindingCluster(
                cluster_id=cluster_id,
                canonical_id=ids[i],
                member_ids=members,
                similarity_scores=scores,
                file_path=findings[i].get("file", ""),
                title=findings[i].get("title", ""),
            ))
            cluster_id += 1

        return clusters

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _finding_to_text(self, finding: dict[str, Any]) -> str:
        """Convert a finding dict to a single text string for embedding."""
        parts = [
            finding.get("title", ""),
            finding.get("description", ""),
            finding.get("evidence", ""),
            finding.get("fix_suggestion", ""),
        ]
        # Include file path as context
        file_path = finding.get("file", "")
        if file_path:
            parts.append(f"file: {file_path}")
        return " ".join(p for p in parts if p).strip()

    def _tokenize(self, text: str) -> set[str]:
        """Simple tokenization for Jaccard fallback."""
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]+', text.lower())
        # Remove very short or very common tokens
        stop = {"the", "and", "for", "with", "this", "that", "from", "are", "was"}
        return {t for t in tokens if len(t) >= 3 and t not in stop}

    def _save_report(self, result: DedupResult) -> None:
        """Save dedup report to log directory."""
        if not self.log_dir:
            return
        report_path = self.log_dir / "semantic_dedup_report.json"
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.warning("Failed to write dedup report to %s: %s", report_path, e)
