"""Tests for SYLION Cellular Security Research Lab modules (Class O)."""
import time

import pytest


# ===========================================================================
# O1 — RANLabOrchestrator
# ===========================================================================

class TestRANLab:
    def test_create_stack(self, bus):
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s = ran.create_stack("4G", stack_name="test-ran", frequency=1800e6,
                             power_dbm=-20, plmn_mcc="001", plmn_mnc="01")
        assert s["technology"] == "4G"
        assert s["stack_name"] == "test-ran"
        assert s["status"] == "created"
        assert s["frequency"] == 1800e6

    def test_start_test_plmn(self, bus):
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s = ran.create_stack("5G", plmn_mcc="001")
        result = ran.start(s["stack_id"])
        assert result["status"] == "running"

    def test_start_rejects_non_test_plmn(self, bus):
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s = ran.create_stack("4G", plmn_mcc="260", plmn_mnc="06")
        result = ran.start(s["stack_id"])
        assert "error" in result
        assert "non-test PLMN" in result["error"]

    def test_stop_stack(self, bus):
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s = ran.create_stack("4G", plmn_mcc="001")
        ran.start(s["stack_id"])
        result = ran.stop(s["stack_id"])
        assert result["status"] == "stopped"

    def test_get_and_list(self, bus):
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s1 = ran.create_stack("4G")
        s2 = ran.create_stack("5G")
        assert ran.get(s1["stack_id"]) is not None
        assert ran.get("nonexistent") is None
        all_stacks = ran.list_stacks()
        assert len(all_stacks) == 2
        running = ran.list_stacks(status="running")
        assert len(running) == 0

    def test_start_emits_event(self, bus):
        import json
        from sylion.cellular.ran_lab import RANLabOrchestrator
        ran = RANLabOrchestrator(event_bus=bus)
        s = ran.create_stack("4G", plmn_mcc="999")
        ran.start(s["stack_id"])
        events = bus.query(topic="cellular.ran.started")
        assert len(events) == 1
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["stack_id"] == s["stack_id"]


# ===========================================================================
# O2 — CoreNetworkEmulator
# ===========================================================================

class TestCoreNetwork:
    def test_create_core(self, bus):
        from sylion.cellular.core_network import CoreNetworkEmulator
        cn = CoreNetworkEmulator(event_bus=bus)
        c = cn.create("4G", stack_name="test-core")
        assert c["technology"] == "4G"
        assert c["status"] == "created"
        assert c["has_internet"] == 0

    def test_create_rejects_internet(self, bus):
        from sylion.cellular.core_network import CoreNetworkEmulator
        cn = CoreNetworkEmulator(event_bus=bus)
        result = cn.create("4G", has_internet=True)
        assert "error" in result
        assert "Internet" in result["error"]

    def test_start_stop(self, bus):
        from sylion.cellular.core_network import CoreNetworkEmulator
        cn = CoreNetworkEmulator(event_bus=bus)
        c = cn.create("5G")
        started = cn.start(c["core_id"])
        assert started["status"] == "running"
        stopped = cn.stop(c["core_id"])
        assert stopped["status"] == "stopped"

    def test_get_and_list(self, bus):
        from sylion.cellular.core_network import CoreNetworkEmulator
        cn = CoreNetworkEmulator(event_bus=bus)
        c1 = cn.create("4G")
        c2 = cn.create("5G")
        assert cn.get(c1["core_id"]) is not None
        assert cn.get("nonexistent") is None
        all_cores = cn.list_cores()
        assert len(all_cores) == 2

    def test_start_emits_event(self, bus):
        from sylion.cellular.core_network import CoreNetworkEmulator
        cn = CoreNetworkEmulator(event_bus=bus)
        c = cn.create("4G")
        cn.start(c["core_id"])
        events = bus.query(topic="cellular.core.started")
        assert len(events) == 1


# ===========================================================================
# O3 — UEEmulator
# ===========================================================================

class TestUEEmulator:
    def test_create_ue(self, bus):
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u = ue.create(stack_name="test-ue", technology="4G")
        assert u["status"] == "detached"
        assert u["technology"] == "4G"
        assert len(u["imsi"]) > 0

    def test_auto_generates_test_imsi(self, bus):
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u = ue.create()
        imsi = u["imsi"]
        assert imsi.startswith("00101")
        assert len(imsi) == 15  # MCC(3) + MNC(2) + MSIN(10)

    def test_custom_imsi(self, bus):
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u = ue.create(imsi="999990000000001")
        assert u["imsi"] == "999990000000001"

    def test_attach_detach(self, bus):
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u = ue.create()
        attached = ue.attach(u["ue_id"], "ran001", "core001")
        assert attached["status"] == "attached"
        assert attached["ran_id"] == "ran001"
        detached = ue.detach(u["ue_id"])
        assert detached["status"] == "detached"
        assert detached["ran_id"] == ""

    def test_attach_emits_event(self, bus):
        import json
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u = ue.create()
        ue.attach(u["ue_id"], "ran1", "core1")
        events = bus.query(topic="cellular.ue.attached")
        assert len(events) == 1
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["ue_id"] == u["ue_id"]

    def test_get_and_list(self, bus):
        from sylion.cellular.ue_emulator import UEEmulator
        ue = UEEmulator(event_bus=bus)
        u1 = ue.create()
        u2 = ue.create()
        assert ue.get(u1["ue_id"]) is not None
        assert ue.get("nonexistent") is None
        all_ues = ue.list_ues()
        assert len(all_ues) == 2
        attached = ue.list_ues(status="attached")
        assert len(attached) == 0


# ===========================================================================
# O4 — RFIsolationValidator
# ===========================================================================

class TestRFIsolation:
    def test_pass_threshold(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        result = rf.validate(1800e6, -100)
        assert result["result"] == "PASS"

    def test_warn_threshold(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        result = rf.validate(1800e6, -85)
        assert result["result"] == "WARN"

    def test_fail_threshold(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        result = rf.validate(1800e6, -70)
        assert result["result"] == "FAIL"

    def test_boundary_pass_warn(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        # Exactly -90 is WARN (not < -90)
        result = rf.validate(1800e6, -90)
        assert result["result"] == "WARN"
        # Just below -90 is PASS
        result2 = rf.validate(1800e6, -91)
        assert result2["result"] == "PASS"

    def test_boundary_warn_fail(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        # Exactly -80 is FAIL (not < -80)
        result = rf.validate(1800e6, -80)
        assert result["result"] == "FAIL"
        # Just below -80 is WARN
        result2 = rf.validate(1800e6, -81)
        assert result2["result"] == "WARN"

    def test_is_valid_fresh_pass(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        rf.validate(1800e6, -100)
        assert rf.is_valid(1800e6) is True

    def test_is_valid_fresh_fail(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        rf.validate(1800e6, -70)
        assert rf.is_valid(1800e6) is False

    def test_is_valid_expired(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        result = rf.validate(1800e6, -100)
        # Manually expire the check by setting valid_until to the past
        import sqlite3
        with rf._lock:
            rf._conn.execute(
                "UPDATE isolation_checks SET valid_until = ? WHERE check_id = ?",
                (time.time() - 1, result["check_id"])
            )
            rf._conn.commit()
        assert rf.is_valid(1800e6) is False

    def test_is_valid_no_check(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        assert rf.is_valid(9999) is False

    def test_latest_and_get(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        r1 = rf.validate(900e6, -100)
        r2 = rf.validate(1800e6, -95)
        latest = rf.latest()
        assert latest is not None
        fetched = rf.get(r1["check_id"])
        assert fetched is not None
        assert fetched["experiment_freq"] == 900e6

    def test_validate_emits_event(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        rf.validate(1800e6, -100)
        events = bus.query(topic="cellular.rf.isolation.checked")
        assert len(events) == 1

    def test_list_checks(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        rf.validate(900e6, -100)
        rf.validate(1800e6, -95)
        checks = rf.list_checks()
        assert len(checks) == 2

    def test_harmonics_stored(self, bus):
        from sylion.cellular.rf_isolation import RFIsolationValidator
        rf = RFIsolationValidator(event_bus=bus)
        result = rf.validate(1800e6, -100, harmonics=[{"freq": 3600e6, "dbm": -110}])
        assert len(result["harmonics"]) == 1
        assert result["harmonics"][0]["freq"] == 3600e6


# ===========================================================================
# O5 — AttackVectorLibrary
# ===========================================================================

class TestAttackVectors:
    def test_register_vector(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        v = avl.register("vec-001", "IMSI Catcher", technology="4G",
                         decision_class="D3", legal_basis="court-order-123")
        assert v["vector_id"] == "vec-001"
        assert v["name"] == "IMSI Catcher"
        assert v["lifecycle"] == "DRAFT"

    def test_publish_vector(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        avl.register("vec-002", "Downgrade Attack")
        result = avl.publish("vec-002")
        assert result["lifecycle"] == "PUBLISHED"

    def test_deprecate_vector(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        avl.register("vec-003", "DoS on RACH")
        avl.publish("vec-003")
        result = avl.deprecate("vec-003")
        assert result["lifecycle"] == "DEPRECATED"

    def test_publish_only_from_draft(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        avl.register("vec-004", "Test")
        avl.publish("vec-004")
        result = avl.publish("vec-004")  # already published
        assert "error" in result

    def test_deprecate_only_from_published(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        avl.register("vec-005", "Test")
        result = avl.deprecate("vec-005")  # still DRAFT
        assert "error" in result

    def test_get_list_stats(self, bus):
        from sylion.cellular.attack_vectors import AttackVectorLibrary
        avl = AttackVectorLibrary(event_bus=bus)
        avl.register("vec-a", "V1", technology="4G")
        avl.register("vec-b", "V2", technology="5G")
        avl.publish("vec-a")
        assert avl.get("vec-a") is not None
        assert avl.get("nonexistent") is None
        all_v = avl.list_vectors()
        assert len(all_v) == 2
        v4g = avl.list_vectors(technology="4G")
        assert len(v4g) == 1
        stats = avl.get_stats()
        assert stats["total"] == 2
        assert stats["PUBLISHED"] == 1
        assert stats["DRAFT"] == 1


# ===========================================================================
# O6 — ControlPlaneAnalyzer
# ===========================================================================

class TestControlPlane:
    def test_analyze(self, bus):
        from sylion.cellular.control_plane import ControlPlaneAnalyzer
        cp = ControlPlaneAnalyzer(event_bus=bus)
        result = cp.analyze("capture.pcap", technology="4G", protocol="NAS")
        assert result["pcap_source"] == "capture.pcap"
        assert result["technology"] == "4G"
        assert len(result["messages"]) >= 2  # stub always returns 2

    def test_get_and_list(self, bus):
        from sylion.cellular.control_plane import ControlPlaneAnalyzer
        cp = ControlPlaneAnalyzer(event_bus=bus)
        a1 = cp.analyze("c1.pcap")
        a2 = cp.analyze("c2.pcap", technology="5G")
        assert cp.get(a1["analysis_id"]) is not None
        assert cp.get("nonexistent") is None
        all_a = cp.list_analyses()
        assert len(all_a) == 2
        v5g = cp.list_analyses(technology="5G")
        assert len(v5g) == 1

    def test_detect_anomalies(self, bus):
        from sylion.cellular.control_plane import ControlPlaneAnalyzer
        cp = ControlPlaneAnalyzer(event_bus=bus)
        a = cp.analyze("test.pcap")
        result = cp.detect_anomalies(a["analysis_id"])
        assert "anomalies" in result
        assert isinstance(result["anomalies"], list)

    def test_detect_anomalies_missing_analysis(self, bus):
        from sylion.cellular.control_plane import ControlPlaneAnalyzer
        cp = ControlPlaneAnalyzer(event_bus=bus)
        result = cp.detect_anomalies("nonexistent")
        assert "error" in result


# ===========================================================================
# O7 — CellularEvidenceWriter
# ===========================================================================

class TestCellularEvidence:
    def test_write_evidence(self, bus):
        from sylion.cellular.evidence_writer import CellularEvidenceWriter
        ew = CellularEvidenceWriter(event_bus=bus)
        e = ew.write("ev-001", "exp-001", attack_vector="vec-001",
                     isolation={"check_id": "c1", "result": "PASS"},
                     governance={"approved": True},
                     findings="Downgrade attack confirmed",
                     pcap_cp="cp.pcap", pcap_up="up.pcap", iq_recording="iq.bin")
        assert e["evidence_id"] == "ev-001"
        assert e["experiment_id"] == "exp-001"
        assert e["isolation"]["result"] == "PASS"

    def test_get_and_list(self, bus):
        from sylion.cellular.evidence_writer import CellularEvidenceWriter
        ew = CellularEvidenceWriter(event_bus=bus)
        ew.write("ev-010", "exp-a")
        ew.write("ev-011", "exp-a")
        ew.write("ev-012", "exp-b")
        assert ew.get("ev-010") is not None
        assert ew.get("nonexistent") is None
        all_ev = ew.list_evidence()
        assert len(all_ev) == 3
        exp_a = ew.list_evidence(experiment_id="exp-a")
        assert len(exp_a) == 2

    def test_validate_complete(self, bus):
        from sylion.cellular.evidence_writer import CellularEvidenceWriter
        ew = CellularEvidenceWriter(event_bus=bus)
        ew.write("ev-020", "exp-x", attack_vector="vec-1",
                 isolation={"check_id": "c1", "result": "PASS"},
                 governance={"approved": True},
                 findings="Confirmed vulnerability")
        result = ew.validate("ev-020")
        assert result["valid"] is True

    def test_validate_missing_fields(self, bus):
        from sylion.cellular.evidence_writer import CellularEvidenceWriter
        ew = CellularEvidenceWriter(event_bus=bus)
        ew.write("ev-030", "exp-y")  # missing most fields
        result = ew.validate("ev-030")
        assert result["valid"] is False
        assert "missing_fields" in result
        assert "attack_vector" in result["missing_fields"]
        assert "findings" in result["missing_fields"]

    def test_validate_nonexistent(self, bus):
        from sylion.cellular.evidence_writer import CellularEvidenceWriter
        ew = CellularEvidenceWriter(event_bus=bus)
        result = ew.validate("nonexistent")
        assert result["valid"] is False
        assert "error" in result
