"""Tests for sylion.cellular.evidence_writer — CellularEvidenceWriter."""

import json
import sqlite3
import threading
import time

import pytest

from sylion.cellular.evidence_writer import CellularEvidenceWriter, get_cellular_evidence_writer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def writer():
    """Fresh in-memory CellularEvidenceWriter per test."""
    return CellularEvidenceWriter()


@pytest.fixture
def sample_evidence(writer):
    """Write a sample evidence record and return its data dict."""
    return writer.write(
        evidence_id="ev-001",
        experiment_id="exp-100",
        attack_vector="IMSI Catcher",
        isolation={"airgap": True, "faraday": True},
        governance={"approval": "council", "decision_class": "D3"},
        findings="Successfully captured IMSIs in isolated environment",
        pcap_cp="/pcap/control_plane.pcap",
        pcap_up="/pcap/user_plane.pcap",
        iq_recording="/iq/recording.bin",
    )


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

class TestWrite:
    def test_returns_full_record(self, writer):
        data = writer.write(
            evidence_id="ev-1",
            experiment_id="exp-1",
            attack_vector="Test Vector",
            isolation={"type": "airgap"},
            governance={"approved": True},
            findings="Some findings",
            pcap_cp="cp.pcap",
            pcap_up="up.pcap",
            iq_recording="iq.bin",
        )
        assert data["evidence_id"] == "ev-1"
        assert data["experiment_id"] == "exp-1"
        assert data["attack_vector"] == "Test Vector"
        assert data["isolation"] == {"type": "airgap"}
        assert data["governance"] == {"approved": True}
        assert data["findings"] == "Some findings"
        assert data["pcap_cp"] == "cp.pcap"
        assert data["pcap_up"] == "up.pcap"
        assert data["iq_recording"] == "iq.bin"
        assert isinstance(data["created_at"], float)

    def test_defaults(self, writer):
        data = writer.write(
            evidence_id="ev-2",
            experiment_id="exp-2",
        )
        assert data["attack_vector"] == ""
        assert data["isolation"] == {}
        assert data["governance"] == {}
        assert data["findings"] == ""
        assert data["pcap_cp"] == ""
        assert data["pcap_up"] == ""
        assert data["iq_recording"] == ""

    def test_duplicate_evidence_id_raises(self, writer):
        writer.write(evidence_id="dup", experiment_id="exp-1")
        with pytest.raises(Exception):
            writer.write(evidence_id="dup", experiment_id="exp-2")

    def test_isolation_and_governance_serialized(self, writer):
        writer.write(
            evidence_id="ev-3",
            experiment_id="exp-3",
            isolation={"nested": {"key": "value"}},
            governance={"list": [1, 2, 3]},
        )
        # Fetch raw from DB to verify JSON serialization
        row = writer._conn.execute(
            "SELECT isolation, governance FROM cellular_evidence WHERE evidence_id = ?",
            ("ev-3",),
        ).fetchone()
        assert json.loads(row["isolation"]) == {"nested": {"key": "value"}}
        assert json.loads(row["governance"]) == {"list": [1, 2, 3]}


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_existing(self, writer, sample_evidence):
        result = writer.get("ev-001")
        assert result is not None
        assert result["evidence_id"] == "ev-001"
        assert result["experiment_id"] == "exp-100"
        assert result["attack_vector"] == "IMSI Catcher"

    def test_nonexistent_returns_none(self, writer):
        assert writer.get("no-such-id") is None

    def test_json_fields_parsed(self, writer, sample_evidence):
        data = writer.get("ev-001")
        assert isinstance(data["isolation"], dict)
        assert isinstance(data["governance"], dict)
        assert data["isolation"]["airgap"] is True
        assert data["governance"]["approval"] == "council"


# ---------------------------------------------------------------------------
# list_evidence
# ---------------------------------------------------------------------------

class TestListEvidence:
    def test_empty(self, writer):
        assert writer.list_evidence() == []

    def test_returns_all(self, writer):
        writer.write(evidence_id="a", experiment_id="exp-1")
        writer.write(evidence_id="b", experiment_id="exp-2")
        items = writer.list_evidence()
        assert len(items) == 2
        ids = {i["evidence_id"] for i in items}
        assert ids == {"a", "b"}

    def test_filter_experiment_id(self, writer):
        writer.write(evidence_id="a", experiment_id="exp-1")
        writer.write(evidence_id="b", experiment_id="exp-2")
        writer.write(evidence_id="c", experiment_id="exp-1")
        result = writer.list_evidence(experiment_id="exp-1")
        assert len(result) == 2
        ids = {i["evidence_id"] for i in result}
        assert ids == {"a", "c"}

    def test_limit(self, writer):
        for i in range(5):
            writer.write(evidence_id=f"ev-{i}", experiment_id="exp-1")
        result = writer.list_evidence(limit=3)
        assert len(result) == 3

    def test_ordered_by_created_at_desc(self, writer):
        writer.write(evidence_id="first", experiment_id="exp-1")
        time.sleep(0.01)
        writer.write(evidence_id="second", experiment_id="exp-1")
        items = writer.list_evidence()
        assert items[0]["evidence_id"] == "second"
        assert items[1]["evidence_id"] == "first"

    def test_json_fields_in_list(self, writer, sample_evidence):
        items = writer.list_evidence()
        assert len(items) == 1
        assert isinstance(items[0]["isolation"], dict)
        assert isinstance(items[0]["governance"], dict)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_evidence(self, writer, sample_evidence):
        result = writer.validate("ev-001")
        assert result["valid"] is True
        assert result["evidence_id"] == "ev-001"

    def test_not_found(self, writer):
        result = writer.validate("nonexistent")
        assert result["valid"] is False
        assert result["error"] == "evidence not found"

    def test_missing_experiment_id(self, writer):
        # Manually insert a record with empty experiment_id
        now = time.time()
        with writer._lock:
            writer._conn.execute("""
                INSERT INTO cellular_evidence
                    (evidence_id, experiment_id, attack_vector, isolation,
                     governance, findings, pcap_cp, pcap_up, iq_recording, created_at)
                VALUES (?, '', 'vec', '{}', '{}', 'f', '', '', '', ?)
            """, ("ev-bad", now))
            writer._conn.commit()
        result = writer.validate("ev-bad")
        assert result["valid"] is False
        assert "experiment_id" in result["missing_fields"]

    def test_missing_attack_vector(self, writer):
        now = time.time()
        with writer._lock:
            writer._conn.execute("""
                INSERT INTO cellular_evidence
                    (evidence_id, experiment_id, attack_vector, isolation,
                     governance, findings, pcap_cp, pcap_up, iq_recording, created_at)
                VALUES (?, 'exp-1', '', '{"x":1}', '{"y":1}', 'f', '', '', '', ?)
            """, ("ev-no-vec", now))
            writer._conn.commit()
        result = writer.validate("ev-no-vec")
        assert result["valid"] is False
        assert "attack_vector" in result["missing_fields"]

    def test_missing_findings(self, writer):
        now = time.time()
        with writer._lock:
            writer._conn.execute("""
                INSERT INTO cellular_evidence
                    (evidence_id, experiment_id, attack_vector, isolation,
                     governance, findings, pcap_cp, pcap_up, iq_recording, created_at)
                VALUES (?, 'exp-1', 'vec', '{"x":1}', '{"y":1}', '', '', '', '', ?)
            """, ("ev-no-findings", now))
            writer._conn.commit()
        result = writer.validate("ev-no-findings")
        assert result["valid"] is False
        assert "findings" in result["missing_fields"]

    def test_empty_isolation_dict(self, writer):
        writer.write(
            evidence_id="ev-empty-iso",
            experiment_id="exp-1",
            attack_vector="vec",
            isolation={},
            governance={"ok": True},
            findings="some findings",
        )
        result = writer.validate("ev-empty-iso")
        assert result["valid"] is False
        assert "isolation" in result["missing_fields"]

    def test_empty_governance_dict(self, writer):
        writer.write(
            evidence_id="ev-empty-gov",
            experiment_id="exp-1",
            attack_vector="vec",
            isolation={"ok": True},
            governance={},
            findings="some findings",
        )
        result = writer.validate("ev-empty-gov")
        assert result["valid"] is False
        assert "governance" in result["missing_fields"]

    def test_multiple_missing_fields(self, writer):
        writer.write(
            evidence_id="ev-multi",
            experiment_id="exp-1",
            # attack_vector default '', findings default '', isolation/governance default {}
        )
        result = writer.validate("ev-multi")
        assert result["valid"] is False
        missing = result["missing_fields"]
        assert "attack_vector" in missing
        assert "findings" in missing
        assert "isolation" in missing
        assert "governance" in missing

    def test_minimal_valid(self, writer):
        writer.write(
            evidence_id="ev-min",
            experiment_id="exp-1",
            attack_vector="v",
            isolation={"x": 1},
            governance={"y": 1},
            findings="f",
        )
        result = writer.validate("ev-min")
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Singleton helper
# ---------------------------------------------------------------------------

class TestGetCellularEvidenceWriter:
    def test_returns_instance(self):
        inst = get_cellular_evidence_writer()
        assert isinstance(inst, CellularEvidenceWriter)

    def test_singleton(self):
        a = get_cellular_evidence_writer()
        b = get_cellular_evidence_writer()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_writes(self, writer):
        errors = []
        results = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def do_write(idx):
            for attempt in range(8):
                try:
                    data = writer.write(
                        evidence_id=f"ev-t{idx}",
                        experiment_id=f"exp-{idx}",
                        attack_vector=f"vec-{idx}",
                        isolation={"idx": idx},
                        governance={"approved": True},
                        findings=f"findings {idx}",
                    )
                    results.append(data["evidence_id"])
                    return
                except retriable:
                    if attempt == 7:
                        errors.append(RuntimeError(f"write gave up at {idx}"))
                    time.sleep(0.05 * (2 ** attempt))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [threading.Thread(target=do_write, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        assert len(set(results)) == 20

        # All records readable
        items = writer.list_evidence()
        assert len(items) == 20

        # All valid
        for eid in results:
            data = writer.get(eid)
            assert data is not None
            assert data["attack_vector"].startswith("vec-")
