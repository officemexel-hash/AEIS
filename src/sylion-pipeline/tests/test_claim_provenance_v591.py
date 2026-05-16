#!/usr/bin/env python3
"""
SYLION v5.9.1 — ClaimProvenance test suite
==========================================

Tests for Layer 3 Anti-Hallucination: ClaimProvenance.

Run:
    cd sylion-pipeline
    /tmp/sylion_venv/bin/python -m pytest tests/test_claim_provenance_v591.py -v
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_provenance import (
    ClaimProvenance,
    ProvenanceClaim,
    ProvenanceResult,
    ProvenanceVerdict,
)


class _Base(unittest.TestCase):
    """Base: temp workspace with sample source files."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sylion_cprov_")
        self.workspace = Path(self.tmp)
        self.cp = ClaimProvenance(workspace=self.workspace)

        # Create a sample Go file with real content
        self._write(
            "pkg/auth/handler.go",
            "\n".join([
                "package auth",
                "",
                'import "net/http"',
                "",
                "// Handler handles auth requests",
                "func Handler(w http.ResponseWriter, r *http.Request) {",
                '    xff := r.Header.Get("X-Forwarded-For")',
                '    if xff == "" {',
                "        xff = r.RemoteAddr",
                "    }",
                "    // validate token",
                '    token := r.Header.Get("AuthToken")',
                "    if token == \"\" {",
                '        http.Error(w, "Unauthorized", 401)',
                "        return",
                "    }",
                "}",
            ]) + "\n",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel: str, content: str) -> Path:
        p = self.workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _claim(self, *, finding_id="F-001", agent="agent_a",
               file_path="pkg/auth/handler.go", line=7,
               keywords=None, title="", evidence=""):
        return ProvenanceClaim(
            finding_id=finding_id,
            agent_name=agent,
            file_path=file_path,
            line_number=line,
            keywords=keywords or [],
            title=title,
            evidence_snippet=evidence,
        )


# ---------------------------------------------------------------------------
# Test 1: Provenance linkage — two agents chain claims
# ---------------------------------------------------------------------------

class TestProvenanceLinkage(_Base):
    """Two agents both reference the same code location; provenance tracks both."""

    def test_provenance_linkage(self):
        # Agent A claims XFF is read at line 7
        claim_a = self._claim(
            finding_id="FIND-A-001",
            agent="auditor_a",
            line=7,
            keywords=["X-Forwarded-For", "xff"],
        )
        result_a = self.cp.verify_claim(claim_a)
        self.assertEqual(result_a.verdict, ProvenanceVerdict.VERIFIED,
                         f"Expected VERIFIED, got {result_a.verdict}: {result_a.missing_keywords}")

        # Agent B independently claims AuthToken at line 12
        claim_b = self._claim(
            finding_id="FIND-B-001",
            agent="auditor_b",
            line=12,
            keywords=["AuthToken", "token"],
        )
        result_b = self.cp.verify_claim(claim_b)
        self.assertEqual(result_b.verdict, ProvenanceVerdict.VERIFIED,
                         f"Expected VERIFIED, got {result_b.verdict}: {result_b.missing_keywords}")

        # Both results tracked internally
        stats = self.cp.get_stats()
        self.assertEqual(stats["total_checks"], 2)
        self.assertEqual(stats["verified"], 2)

        # Export contains both
        report = self.cp.export_report()
        finding_ids = {r["finding_id"] for r in report["results"]}
        self.assertIn("FIND-A-001", finding_ids)
        self.assertIn("FIND-B-001", finding_ids)


# ---------------------------------------------------------------------------
# Test 2: Provenance orphan rejected (FILE_MISSING)
# ---------------------------------------------------------------------------

class TestProvenanceOrphanRejected(_Base):
    """Claim referencing a non-existent file → FILE_MISSING (orphan rejected)."""

    def test_provenance_orphan_rejected(self):
        claim = self._claim(
            finding_id="ORPHAN-001",
            agent="rogue_agent",
            file_path="nonexistent/phantom.go",
            line=42,
            keywords=["SomeFunc", "dangerous"],
        )
        result = self.cp.verify_claim(claim)
        self.assertEqual(result.verdict, ProvenanceVerdict.FILE_MISSING)
        # All keywords are missing
        self.assertEqual(set(result.missing_keywords), {"SomeFunc", "dangerous"})
        self.assertEqual(result.matched_keywords, [])
        self.assertEqual(result.match_ratio, 0.0)

    def test_provenance_orphan_no_keywords_gives_no_evidence(self):
        """Claim with empty keywords → NO_EVIDENCE (also an orphan-like rejection)."""
        claim = self._claim(
            finding_id="ORPHAN-002",
            agent="rogue_agent",
            file_path="pkg/auth/handler.go",
            line=7,
            keywords=[],  # No keywords = no evidence to check
        )
        result = self.cp.verify_claim(claim)
        self.assertEqual(result.verdict, ProvenanceVerdict.NO_EVIDENCE)


# ---------------------------------------------------------------------------
# Test 3: "Anti-Hallucination Layer 3" marker in module docstring
# ---------------------------------------------------------------------------

class TestProvenanceLogLayer3Marker(_Base):
    """The string 'Anti-Hallucination Layer 3' must appear in the module."""

    def test_provenance_log_layer_3_marker(self):
        import claim_provenance as cp_module
        doc = cp_module.__doc__ or ""
        self.assertIn(
            "Anti-Hallucination Layer 3",
            doc,
            "claim_provenance module docstring must contain 'Anti-Hallucination Layer 3'",
        )

    def test_claim_provenance_class_docstring_present(self):
        """ClaimProvenance class must have a non-empty docstring."""
        doc = ClaimProvenance.__doc__ or ""
        self.assertTrue(len(doc.strip()) > 0, "ClaimProvenance must have a docstring")

    def test_verdict_verified_threshold(self):
        """Verify with >= 30% keywords matched → VERIFIED (default min_match_ratio=0.3)."""
        # keywords: XFF matches, AuthToken matches, fake doesn't → 2/3 = 0.67 >= 0.30
        claim = self._claim(
            finding_id="THRESHOLD-001",
            agent="auditor",
            line=7,
            keywords=["X-Forwarded-For", "AuthToken", "nonexistent_keyword_xyz"],
        )
        result = self.cp.verify_claim(claim)
        self.assertEqual(result.verdict, ProvenanceVerdict.VERIFIED)
        self.assertGreaterEqual(result.match_ratio, 0.3)

    def test_verdict_weak_below_threshold(self):
        """Keywords that don't exist in context → WEAK (< 30% match)."""
        claim = self._claim(
            finding_id="WEAK-001",
            agent="auditor",
            line=7,
            keywords=["FakeAPI", "NonExistentEndpoint", "POST", "X-API-Key"],
        )
        result = self.cp.verify_claim(claim)
        self.assertEqual(result.verdict, ProvenanceVerdict.WEAK)
        self.assertLess(result.match_ratio, 0.3)


if __name__ == "__main__":
    unittest.main()
