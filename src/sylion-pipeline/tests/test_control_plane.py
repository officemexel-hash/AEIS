"""Tests for sylion.cellular.control_plane — ControlPlaneAnalyzer."""

import json
import threading
import time

import pytest

from sylion.cellular.control_plane import ControlPlaneAnalyzer, get_control_plane_analyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer():
    """Fresh in-memory ControlPlaneAnalyzer per test."""
    return ControlPlaneAnalyzer()


@pytest.fixture
def sample_analysis(analyzer):
    """Create a sample analysis and return its data dict."""
    return analyzer.analyze(pcap_source="/captures/sample.pcap", technology="4G")


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_returns_analysis_record(self, analyzer):
        data = analyzer.analyze(pcap_source="/captures/test.pcap")
        assert "analysis_id" in data
        assert len(data["analysis_id"]) == 12
        assert data["pcap_source"] == "/captures/test.pcap"
        assert data["technology"] == "4G"
        assert data["protocol"] == ""
        assert isinstance(data["messages"], list)
        assert isinstance(data["anomalies"], list)
        assert isinstance(data["created_at"], float)

    def test_default_messages(self, analyzer):
        data = analyzer.analyze(pcap_source="a.pcap")
        assert len(data["messages"]) >= 1
        msg_types = {m["type"] for m in data["messages"]}
        assert "ATTACH_REQUEST" in msg_types

    def test_custom_technology_and_protocol(self, analyzer):
        data = analyzer.analyze(
            pcap_source="b.pcap", technology="5G", protocol="NGAP"
        )
        assert data["technology"] == "5G"
        assert data["protocol"] == "NGAP"

    def test_unique_analysis_ids(self, analyzer):
        a = analyzer.analyze(pcap_source="a.pcap")
        b = analyzer.analyze(pcap_source="b.pcap")
        assert a["analysis_id"] != b["analysis_id"]


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_existing(self, analyzer, sample_analysis):
        result = analyzer.get(sample_analysis["analysis_id"])
        assert result is not None
        assert result["analysis_id"] == sample_analysis["analysis_id"]
        assert result["pcap_source"] == "/captures/sample.pcap"

    def test_nonexistent_returns_none(self, analyzer):
        assert analyzer.get("does-not-exist") is None

    def test_json_fields_parsed(self, analyzer, sample_analysis):
        data = analyzer.get(sample_analysis["analysis_id"])
        assert isinstance(data["messages"], list)
        assert isinstance(data["anomalies"], list)


# ---------------------------------------------------------------------------
# list_analyses
# ---------------------------------------------------------------------------

class TestListAnalyses:
    def test_empty(self, analyzer):
        assert analyzer.list_analyses() == []

    def test_returns_all(self, analyzer):
        analyzer.analyze(pcap_source="a.pcap")
        analyzer.analyze(pcap_source="b.pcap")
        items = analyzer.list_analyses()
        assert len(items) == 2

    def test_filter_technology(self, analyzer):
        analyzer.analyze(pcap_source="a.pcap", technology="4G")
        analyzer.analyze(pcap_source="b.pcap", technology="5G")
        result = analyzer.list_analyses(technology="5G")
        assert len(result) == 1
        assert result[0]["technology"] == "5G"

    def test_limit(self, analyzer):
        for i in range(5):
            analyzer.analyze(pcap_source=f"f{i}.pcap")
        result = analyzer.list_analyses(limit=3)
        assert len(result) == 3

    def test_ordered_by_created_at_desc(self, analyzer):
        analyzer.analyze(pcap_source="first.pcap")
        time.sleep(0.01)
        analyzer.analyze(pcap_source="second.pcap")
        items = analyzer.list_analyses()
        assert items[0]["pcap_source"] == "second.pcap"
        assert items[1]["pcap_source"] == "first.pcap"


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------

class TestDetectAnomalies:
    def test_no_anomaly_default_messages(self, analyzer, sample_analysis):
        result = analyzer.detect_anomalies(sample_analysis["analysis_id"])
        assert result["anomalies"] == []
        # Verify persisted
        fetched = analyzer.get(sample_analysis["analysis_id"])
        assert fetched["anomalies"] == []

    def test_analysis_not_found(self, analyzer):
        result = analyzer.detect_anomalies("nonexistent")
        assert "error" in result
        assert result["error"] == "analysis not found"

    def test_detect_missing_security_mode(self, analyzer):
        # Create an analysis, then manually inject messages with IDENTITY_REQUEST
        # but no SECURITY_MODE_COMMAND
        data = analyzer.analyze(pcap_source="anom.pcap")
        aid = data["analysis_id"]
        # Overwrite messages directly in DB to simulate captured traffic
        fake_messages = json.dumps([
            {"type": "IDENTITY_REQUEST", "direction": "DL"},
            {"type": "ATTACH_ACCEPT", "direction": "DL"},
        ])
        with analyzer._lock:
            analyzer._conn.execute(
                "UPDATE cp_analyses SET messages = ? WHERE analysis_id = ?",
                (fake_messages, aid),
            )
            analyzer._conn.commit()

        result = analyzer.detect_anomalies(aid)
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["pattern"] == "missing_security_mode"
        assert result["anomalies"][0]["severity"] == "HIGH"

    def test_detect_reject_message(self, analyzer):
        data = analyzer.analyze(pcap_source="rej.pcap")
        aid = data["analysis_id"]
        fake_messages = json.dumps([
            {"type": "REJECT", "direction": "DL"},
        ])
        with analyzer._lock:
            analyzer._conn.execute(
                "UPDATE cp_analyses SET messages = ? WHERE analysis_id = ?",
                (fake_messages, aid),
            )
            analyzer._conn.commit()

        result = analyzer.detect_anomalies(aid)
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["pattern"] == "reject_detected"
        assert result["anomalies"][0]["severity"] == "MEDIUM"

    def test_multiple_anomalies(self, analyzer):
        data = analyzer.analyze(pcap_source="multi.pcap")
        aid = data["analysis_id"]
        fake_messages = json.dumps([
            {"type": "IDENTITY_REQUEST", "direction": "DL"},
            {"type": "REJECT", "direction": "DL"},
        ])
        with analyzer._lock:
            analyzer._conn.execute(
                "UPDATE cp_analyses SET messages = ? WHERE analysis_id = ?",
                (fake_messages, aid),
            )
            analyzer._conn.commit()

        result = analyzer.detect_anomalies(aid)
        assert len(result["anomalies"]) == 2
        patterns = {a["pattern"] for a in result["anomalies"]}
        assert "missing_security_mode" in patterns
        assert "reject_detected" in patterns

    def test_anomaly_persisted(self, analyzer):
        data = analyzer.analyze(pcap_source="persist.pcap")
        aid = data["analysis_id"]
        fake_messages = json.dumps([
            {"type": "IDENTITY_REQUEST", "direction": "DL"},
        ])
        with analyzer._lock:
            analyzer._conn.execute(
                "UPDATE cp_analyses SET messages = ? WHERE analysis_id = ?",
                (fake_messages, aid),
            )
            analyzer._conn.commit()

        analyzer.detect_anomalies(aid)
        fetched = analyzer.get(aid)
        assert len(fetched["anomalies"]) == 1
        assert fetched["anomalies"][0]["pattern"] == "missing_security_mode"


# ---------------------------------------------------------------------------
# Singleton helper
# ---------------------------------------------------------------------------

class TestGetControlPlaneAnalyzer:
    def test_returns_instance(self):
        inst = get_control_plane_analyzer()
        assert isinstance(inst, ControlPlaneAnalyzer)

    def test_singleton(self):
        a = get_control_plane_analyzer()
        b = get_control_plane_analyzer()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_analyzes(self, analyzer):
        errors = []
        results = []

        def do_analyze(idx):
            try:
                data = analyzer.analyze(pcap_source=f"concurrent_{idx}.pcap")
                results.append(data["analysis_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_analyze, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All IDs unique
        assert len(set(results)) == 20
