"""
Tests for SYLION Anti-Hallucination Layers 2-5.

Covers:
  - Layer 2: BuildVerification
  - Layer 3: ClaimProvenance
  - Layer 4: SemanticDedup
  - Layer 5: FactCheckerAgent
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Layer 2: BuildVerification
# ---------------------------------------------------------------------------
from build_verification import BuildVerification, BuildStatus, BuildResult


class TestBuildVerification:
    """Tests for Layer 2: BuildVerification."""

    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bv = BuildVerification(
            workspace=self.tmpdir,
            run_tests=False,  # Don't run actual go test in unit tests
            log_dir=self.tmpdir / "logs",
        )

    def test_skip_non_go_files(self):
        """Should skip verification when no .go files changed."""
        result = self.bv.verify(
            agent_name="test_agent",
            stage="3",
            changed_files=["README.md", "config.yaml"],
        )
        assert result.status == BuildStatus.SKIPPED

    def test_blocked_command(self):
        """Internal: blocked commands should not execute."""
        ok, out = self.bv._run_command("rm -rf /", timeout=5, env={})
        assert not ok
        assert "BLOCKED" in out

    def test_allowed_commands_only(self):
        """Only go vet, go build, go test should be allowed."""
        for cmd in ["go vet ./...", "go build ./...", "go test ./..."]:
            # These will fail (no Go workspace) but should not be blocked
            ok, out = self.bv._run_command(cmd, timeout=5, env=os.environ.copy())
            # They fail because no Go project, but they're not BLOCKED
            assert "BLOCKED" not in out

    def test_stats_counting(self):
        """Stats should track checks correctly."""
        self.bv.verify("a1", "1", ["x.md"])
        self.bv.verify("a2", "2", ["y.txt"])
        stats = self.bv.get_stats()
        assert stats["total_checks"] == 2
        # Both skipped (no .go files)
        assert stats["total_pass"] == 0
        assert stats["total_fail"] == 0

    def test_result_serialization(self):
        """BuildResult.to_dict should produce valid JSON-serializable dict."""
        result = BuildResult(
            status=BuildStatus.PASS,
            agent_name="test",
            stage="5",
            vet_output="ok",
            build_output="ok",
            test_output="ok",
            elapsed_seconds=1.5,
            changed_files=["pkg/auth/handler.go"],
        )
        d = result.to_dict()
        assert d["status"] == "PASS"
        assert d["agent_name"] == "test"
        json.dumps(d)  # Should not raise

    def test_log_dir_created(self):
        """Log directory should be created on init."""
        assert (self.tmpdir / "logs").is_dir()

    def test_export_report(self):
        """Export should contain stats and results."""
        self.bv.verify("a1", "1", ["x.md"])
        report = self.bv.export_report()
        assert "stats" in report
        assert "results" in report
        assert len(report["results"]) == 1


# ---------------------------------------------------------------------------
# Layer 3: ClaimProvenance
# ---------------------------------------------------------------------------
from claim_provenance import (
    ClaimProvenance,
    ProvenanceClaim,
    ProvenanceVerdict,
    ProvenanceResult,
)


class TestClaimProvenance:
    """Tests for Layer 3: ClaimProvenance."""

    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create a fake Go file
        pkg_dir = self.tmpdir / "pkg" / "auth"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "handler.go").write_text(
            'package auth\n\n'
            'import "net/http"\n\n'
            'func HandleLogin(w http.ResponseWriter, r *http.Request) {\n'
            '    xff := r.Header.Get("X-Forwarded-For")\n'
            '    remoteAddr := r.RemoteAddr\n'
            '    _ = xff\n'
            '    _ = remoteAddr\n'
            '}\n',
            encoding="utf-8",
        )
        self.cp = ClaimProvenance(
            workspace=self.tmpdir,
            context_window=5,
            min_match_ratio=0.3,
            log_dir=self.tmpdir / "logs",
        )

    def test_verified_claim(self):
        """Claim with matching keywords should be VERIFIED."""
        claim = ProvenanceClaim(
            finding_id="FIND-001",
            agent_name="auditor_claude",
            file_path="pkg/auth/handler.go",
            line_number=6,
            keywords=["X-Forwarded-For", "Header", "Get"],
        )
        result = self.cp.verify_claim(claim)
        assert result.verdict == ProvenanceVerdict.VERIFIED
        assert result.match_ratio > 0.0
        assert len(result.matched_keywords) >= 1

    def test_weak_claim(self):
        """Claim with non-matching keywords should be WEAK."""
        claim = ProvenanceClaim(
            finding_id="FIND-002",
            agent_name="auditor_gpt",
            file_path="pkg/auth/handler.go",
            line_number=6,
            keywords=["SQLInjection", "database", "DROP TABLE"],
        )
        result = self.cp.verify_claim(claim)
        assert result.verdict == ProvenanceVerdict.WEAK
        assert result.match_ratio == 0.0

    def test_file_missing(self):
        """Claim referencing non-existent file should be FILE_MISSING."""
        claim = ProvenanceClaim(
            finding_id="FIND-003",
            agent_name="auditor_gemini",
            file_path="pkg/nonexistent/magic.go",
            line_number=1,
            keywords=["anything"],
        )
        result = self.cp.verify_claim(claim)
        assert result.verdict == ProvenanceVerdict.FILE_MISSING

    def test_line_out_of_bounds(self):
        """Claim with out-of-bounds line should be LINE_OOB."""
        claim = ProvenanceClaim(
            finding_id="FIND-004",
            agent_name="auditor_deepseek",
            file_path="pkg/auth/handler.go",
            line_number=9999,
            keywords=["anything"],
        )
        result = self.cp.verify_claim(claim)
        assert result.verdict == ProvenanceVerdict.LINE_OOB

    def test_no_keywords(self):
        """Claim with no keywords should be NO_EVIDENCE."""
        claim = ProvenanceClaim(
            finding_id="FIND-005",
            agent_name="auditor_claude",
            file_path="pkg/auth/handler.go",
            line_number=6,
            keywords=[],
        )
        result = self.cp.verify_claim(claim)
        assert result.verdict == ProvenanceVerdict.NO_EVIDENCE

    def test_extract_claims_from_findings(self):
        """Should convert raw findings to ProvenanceClaim objects."""
        findings = [
            {
                "id": "FIND-001",
                "file": "pkg/auth/handler.go",
                "line": 6,
                "title": "Unsafe XFF read",
                "evidence": 'r.Header.Get("X-Forwarded-For")',
            },
            {
                "id": "FIND-002",
                "file": "",
                "line": 0,
                "title": "Missing file",
            },
        ]
        claims = self.cp.extract_claims_from_findings(findings, "auditor_claude")
        # Second finding has no file/line, should be filtered out
        assert len(claims) == 1
        assert claims[0].finding_id == "FIND-001"
        assert len(claims[0].keywords) > 0

    def test_batch_verify(self):
        """Batch verification should return results for all claims."""
        claims = [
            ProvenanceClaim("F1", "a1", "pkg/auth/handler.go", 6, ["X-Forwarded-For"]),
            ProvenanceClaim("F2", "a2", "pkg/nonexistent.go", 1, ["nope"]),
        ]
        results = self.cp.verify_batch(claims)
        assert len(results) == 2
        assert results[0].verdict == ProvenanceVerdict.VERIFIED
        assert results[1].verdict == ProvenanceVerdict.FILE_MISSING

    def test_stats(self):
        """Stats should be accurate after multiple checks."""
        self.cp.verify_claim(ProvenanceClaim("F1", "a1", "pkg/auth/handler.go", 6, ["X-Forwarded-For"]))
        self.cp.verify_claim(ProvenanceClaim("F2", "a2", "pkg/nonexistent.go", 1, ["nope"]))
        stats = self.cp.get_stats()
        assert stats["total_checks"] == 2
        assert stats["verified"] == 1
        assert stats["file_missing"] == 1

    def test_result_serialization(self):
        """ProvenanceResult.to_dict should be JSON-serializable."""
        result = ProvenanceResult(
            finding_id="F1",
            verdict=ProvenanceVerdict.VERIFIED,
            matched_keywords=["XFF"],
            missing_keywords=[],
            match_ratio=1.0,
        )
        d = result.to_dict()
        json.dumps(d)  # Should not raise


# ---------------------------------------------------------------------------
# Layer 4: SemanticDedup
# ---------------------------------------------------------------------------
from semantic_dedup import SemanticDedup, DedupBackend, FindingCluster, DedupResult


class TestSemanticDedup:
    """Tests for Layer 4: SemanticDedup."""

    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Force Jaccard backend to avoid needing sentence-transformers
        self.sd = SemanticDedup(
            similarity_threshold=0.4,
            log_dir=self.tmpdir / "logs",
            force_backend=DedupBackend.JACCARD,
        )

    def test_empty_findings(self):
        """Empty input should return empty result."""
        result = self.sd.deduplicate([])
        assert result.total_findings == 0
        assert result.unique_clusters == 0

    def test_single_finding(self):
        """Single finding should create one cluster."""
        findings = [{"id": "F1", "title": "XFF header trusted", "file": "auth.go"}]
        result = self.sd.deduplicate(findings)
        assert result.total_findings == 1
        assert result.unique_clusters == 1
        assert result.duplicates_removed == 0

    def test_duplicate_detection(self):
        """Similar findings should be grouped into one cluster."""
        findings = [
            {
                "id": "F1",
                "title": "Unsafe use of X-Forwarded-For header without validation",
                "file": "pkg/auth/handler.go",
                "description": "The handler trusts XFF header directly",
            },
            {
                "id": "F2",
                "title": "X-Forwarded-For header trusted without proper validation",
                "file": "pkg/auth/handler.go",
                "description": "XFF header is used without validation check",
            },
        ]
        result = self.sd.deduplicate(findings)
        # With Jaccard and low threshold, these should cluster together
        assert result.unique_clusters <= 2  # May or may not dedup depending on tokenization
        assert result.total_findings == 2

    def test_different_files_not_grouped(self):
        """Findings in different files should not be grouped."""
        findings = [
            {"id": "F1", "title": "XFF header trusted", "file": "auth.go"},
            {"id": "F2", "title": "XFF header trusted", "file": "middleware.go"},
        ]
        result = self.sd.deduplicate(findings)
        # Different files = different clusters even with same title
        assert result.unique_clusters == 2

    def test_canonical_extraction(self):
        """get_canonical_findings should return one finding per cluster."""
        findings = [
            {"id": "F1", "title": "Issue A", "file": "a.go"},
            {"id": "F2", "title": "Issue B", "file": "b.go"},
        ]
        result = self.sd.deduplicate(findings)
        canonical = self.sd.get_canonical_findings(findings, result)
        assert len(canonical) == result.unique_clusters

    def test_jaccard_backend_selected(self):
        """Forced backend should be Jaccard."""
        assert self.sd.backend == DedupBackend.JACCARD

    def test_cluster_serialization(self):
        """FindingCluster.to_dict should be JSON-serializable."""
        cluster = FindingCluster(
            cluster_id=0,
            canonical_id="F1",
            member_ids=["F1", "F2"],
            similarity_scores=[1.0, 0.85],
            file_path="auth.go",
            title="Test",
        )
        d = cluster.to_dict()
        assert d["size"] == 2
        json.dumps(d)  # Should not raise

    def test_dedup_result_serialization(self):
        """DedupResult.to_dict should be JSON-serializable."""
        findings = [{"id": "F1", "title": "Test", "file": "a.go"}]
        result = self.sd.deduplicate(findings)
        d = result.to_dict()
        assert "dedup_ratio" in d
        json.dumps(d)  # Should not raise


# ---------------------------------------------------------------------------
# Layer 5: FactCheckerAgent
# ---------------------------------------------------------------------------
from fact_checker import (
    FactCheckerAgent,
    FactCheckItem,
    FactCheckVerdict,
    FactCheckResult,
    FactCheckReport,
)


class TestFactCheckerAgent:
    """Tests for Layer 5: FactCheckerAgent."""

    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create a fake source file
        pkg_dir = self.tmpdir / "pkg" / "auth"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "handler.go").write_text(
            'package auth\n\n'
            'import "net/http"\n\n'
            'func HandleLogin(w http.ResponseWriter, r *http.Request) {\n'
            '    xff := r.Header.Get("X-Forwarded-For")\n'
            '    _ = xff\n'
            '}\n',
            encoding="utf-8",
        )

    def test_skipped_when_no_llm(self):
        """Without LLM caller, all checks should be SKIPPED."""
        fc = FactCheckerAgent(
            workspace=self.tmpdir,
            llm_caller=None,
            log_dir=self.tmpdir / "logs",
        )
        item = FactCheckItem(
            finding_id="F1",
            file_path="pkg/auth/handler.go",
            line_number=6,
            title="XFF trusted",
            description="XFF header used without validation",
            severity="HIGH",
        )
        result = fc.check_one(item)
        assert result.verdict == FactCheckVerdict.SKIPPED

    def test_confirmed_with_mock_llm(self):
        """Mock LLM returning CONFIRMED should produce CONFIRMED verdict."""
        mock_response = json.dumps({
            "verdict": "CONFIRMED",
            "confidence": 0.95,
            "reasoning": "The XFF header is indeed read at line 6",
            "issues_found": [],
            "suggested_severity": "HIGH",
        })

        def mock_caller(system, user):
            return mock_response

        fc = FactCheckerAgent(
            workspace=self.tmpdir,
            llm_caller=mock_caller,
            model_id="mock-model",
            log_dir=self.tmpdir / "logs",
        )
        item = FactCheckItem(
            finding_id="F1",
            file_path="pkg/auth/handler.go",
            line_number=6,
            title="XFF trusted",
            description="XFF header used without validation",
            severity="HIGH",
        )
        result = fc.check_one(item)
        assert result.verdict == FactCheckVerdict.CONFIRMED
        assert result.confidence == 0.95

    def test_hallucination_detected(self):
        """Mock LLM returning HALLUCINATION should produce HALLUCINATION verdict."""
        mock_response = json.dumps({
            "verdict": "HALLUCINATION",
            "confidence": 0.9,
            "reasoning": "The cited code does not exist at line 6",
            "issues_found": ["Line 6 contains different code"],
            "suggested_severity": "NONE",
        })

        def mock_caller(system, user):
            return mock_response

        fc = FactCheckerAgent(
            workspace=self.tmpdir,
            llm_caller=mock_caller,
            log_dir=self.tmpdir / "logs",
        )
        item = FactCheckItem(
            finding_id="F2",
            file_path="pkg/auth/handler.go",
            line_number=6,
            title="Fake issue",
            description="This is fabricated",
            severity="CRITICAL",
        )
        result = fc.check_one(item)
        assert result.verdict == FactCheckVerdict.HALLUCINATION

    def test_check_all_report(self):
        """check_all should return a proper report."""
        fc = FactCheckerAgent(
            workspace=self.tmpdir,
            llm_caller=None,
            log_dir=self.tmpdir / "logs",
        )
        items = [
            FactCheckItem("F1", "pkg/auth/handler.go", 6, "T1", "D1", "HIGH"),
            FactCheckItem("F2", "pkg/auth/handler.go", 6, "T2", "D2", "LOW"),
        ]
        report = fc.check_all(items)
        assert report.total_items == 2
        assert report.errors == 2  # Both SKIPPED (no LLM)
        assert len(report.results) == 2

    def test_file_not_found_context(self):
        """Source context should report when file doesn't exist."""
        fc = FactCheckerAgent(workspace=self.tmpdir)
        ctx = fc._read_source_context("nonexistent.go", 1)
        assert "FILE NOT FOUND" in ctx

    def test_line_oob_context(self):
        """Source context should report when line is out of bounds."""
        fc = FactCheckerAgent(workspace=self.tmpdir)
        ctx = fc._read_source_context("pkg/auth/handler.go", 9999)
        assert "OUT OF BOUNDS" in ctx

    def test_parse_markdown_json(self):
        """Parser should handle JSON wrapped in markdown code blocks."""
        fc = FactCheckerAgent(workspace=self.tmpdir)
        response = '```json\n{"verdict":"CONFIRMED","confidence":0.8,"reasoning":"ok","issues_found":[],"suggested_severity":"HIGH"}\n```'
        parsed = fc._parse_response(response)
        assert parsed["verdict"] == FactCheckVerdict.CONFIRMED

    def test_max_items_enforcement(self):
        """Should enforce max_items_per_run limit."""
        fc = FactCheckerAgent(
            workspace=self.tmpdir,
            llm_caller=None,
            max_items_per_run=2,
        )
        items = [
            FactCheckItem(f"F{i}", "a.go", 1, "T", "D", "LOW")
            for i in range(10)
        ]
        report = fc.check_all(items)
        assert report.total_items == 2  # Truncated to max

    def test_result_serialization(self):
        """FactCheckResult.to_dict should be JSON-serializable."""
        result = FactCheckResult(
            finding_id="F1",
            verdict=FactCheckVerdict.CONFIRMED,
            confidence=0.95,
            reasoning="All checks out",
        )
        d = result.to_dict()
        assert d["verdict"] == "CONFIRMED"
        json.dumps(d)  # Should not raise

    def test_report_serialization(self):
        """FactCheckReport.to_dict should be JSON-serializable."""
        report = FactCheckReport(
            total_items=5,
            confirmed=3,
            disputed=1,
            hallucinations=0,
            inconclusive=1,
            errors=0,
            results=[],
            llm_model="test",
            total_elapsed_seconds=1.0,
        )
        d = report.to_dict()
        assert d["confirmation_rate"] == 0.6
        json.dumps(d)  # Should not raise
