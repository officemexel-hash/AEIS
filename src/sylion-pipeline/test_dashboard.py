"""
Tests for dashboard_server.py — SYLION embedded web dashboard.

Covers:
  - Import & instantiation
  - State collection & JSON serialization
  - Stage lifecycle callbacks (running/completed/skipped/failed)
  - Pipeline status changes
  - Security event log
  - HTTP handler (/  and /api/state endpoints)
  - Server start/stop lifecycle
  - Thread safety of concurrent updates
  - Edge cases (unknown stage IDs, overflow events)
"""

import json
import threading
import time
import unittest
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch

from dashboard_server import (
    DASHBOARD_HTML,
    PIPELINE_STAGES,
    DashboardServer,
    DashboardState,
    StageInfo,
)


# ---------------------------------------------------------------------------
# Unit: Data model
# ---------------------------------------------------------------------------

class TestStageInfo(unittest.TestCase):
    """StageInfo dataclass defaults."""

    def test_defaults(self):
        s = StageInfo()
        self.assertEqual(s.id, "")
        self.assertEqual(s.name, "")
        self.assertEqual(s.status, "pending")
        self.assertEqual(s.progress, 0)
        self.assertEqual(s.started_at, 0.0)
        self.assertEqual(s.finished_at, 0.0)

    def test_custom_values(self):
        s = StageInfo(id="5", name="Patch", status="running", progress=50)
        self.assertEqual(s.id, "5")
        self.assertEqual(s.name, "Patch")
        self.assertEqual(s.status, "running")


class TestDashboardState(unittest.TestCase):
    """DashboardState serialization."""

    def test_to_json_valid(self):
        state = DashboardState()
        raw = state.to_json()
        data = json.loads(raw)
        self.assertIsInstance(data, dict)
        self.assertIn("stages", data)
        self.assertIn("pipeline_status", data)
        self.assertEqual(data["pipeline_status"], "idle")

    def test_to_json_with_stages(self):
        state = DashboardState(stages=[{"id": "1", "name": "Config Load"}])
        data = json.loads(state.to_json())
        self.assertEqual(len(data["stages"]), 1)
        self.assertEqual(data["stages"][0]["id"], "1")


class TestPipelineStages(unittest.TestCase):
    """Pipeline stage definitions match expected count and IDs."""

    def test_stage_count(self):
        self.assertEqual(len(PIPELINE_STAGES), 14)

    def test_stage_ids(self):
        ids = [sid for sid, _ in PIPELINE_STAGES]
        expected = ["1", "2", "3", "4", "5", "5.5", "5.6", "6", "6.5", "7", "7.5", "8", "8.5", "9"]
        self.assertEqual(ids, expected)


# ---------------------------------------------------------------------------
# Unit: DashboardServer — state management
# ---------------------------------------------------------------------------

class TestDashboardServerState(unittest.TestCase):
    """Test stage callbacks and state collection without starting HTTP."""

    def setUp(self):
        self.srv = DashboardServer(port=0)  # port=0, won't actually start

    def test_initial_state(self):
        state = self.srv._collect_state()
        self.assertEqual(state.pipeline_status, "idle")
        self.assertEqual(state.current_stage, "")
        self.assertEqual(len(state.stages), 14)
        # All stages should be pending initially
        for s in state.stages:
            self.assertEqual(s["status"], "pending")

    def test_set_pipeline_status(self):
        self.srv.set_pipeline_status("running")
        state = self.srv._collect_state()
        self.assertEqual(state.pipeline_status, "running")

    def test_stage_running(self):
        self.srv.set_stage_running("1", "Config Load")
        state = self.srv._collect_state()
        self.assertEqual(state.current_stage, "Config Load")
        s1 = next(s for s in state.stages if s["id"] == "1")
        self.assertEqual(s1["status"], "running")

    def test_stage_completed(self):
        self.srv.set_stage_running("2", "Audit")
        self.srv.set_stage_completed("2", "Audit")
        state = self.srv._collect_state()
        s2 = next(s for s in state.stages if s["id"] == "2")
        self.assertEqual(s2["status"], "completed")
        self.assertEqual(s2["progress"], 100)
        self.assertEqual(state.completed_gates, 1)

    def test_stage_skipped(self):
        self.srv.set_stage_skipped("5.6", "Fact Check")
        state = self.srv._collect_state()
        s = next(s for s in state.stages if s["id"] == "5.6")
        self.assertEqual(s["status"], "skipped")

    def test_stage_failed(self):
        self.srv.set_stage_failed("6", "Deploy")
        state = self.srv._collect_state()
        s = next(s for s in state.stages if s["id"] == "6")
        self.assertEqual(s["status"], "failed")

    def test_unknown_stage_id_ignored(self):
        """Setting status on unknown stage ID should not raise."""
        self.srv.set_stage_running("99", "Nonexistent")
        state = self.srv._collect_state()
        # current_stage is updated regardless
        self.assertEqual(state.current_stage, "Nonexistent")
        # No crash, no new stage entry
        self.assertEqual(len(state.stages), 14)

    def test_multiple_stages_sequence(self):
        """Simulate a realistic multi-stage run."""
        self.srv.set_pipeline_status("running")
        for sid, sname in PIPELINE_STAGES[:5]:
            self.srv.set_stage_running(sid, sname)
            time.sleep(0.001)
            self.srv.set_stage_completed(sid, sname)
        state = self.srv._collect_state()
        self.assertEqual(state.completed_gates, 5)
        completed = [s for s in state.stages if s["status"] == "completed"]
        self.assertEqual(len(completed), 5)

    def test_elapsed_time_format(self):
        """Stage elapsed time should be a string like '0s' or '1s'."""
        self.srv.set_stage_running("1", "Config Load")
        time.sleep(0.05)
        self.srv.set_stage_completed("1", "Config Load")
        state = self.srv._collect_state()
        s1 = next(s for s in state.stages if s["id"] == "1")
        self.assertRegex(s1["elapsed"], r"^\d+s$")


# ---------------------------------------------------------------------------
# Unit: Security events
# ---------------------------------------------------------------------------

class TestSecurityEvents(unittest.TestCase):
    """Test security event log management."""

    def setUp(self):
        self.srv = DashboardServer(port=0)

    def test_add_event(self):
        self.srv.add_security_event({"message": "Test event", "severity": "info"})
        state = self.srv._collect_state()
        self.assertEqual(len(state.security_events), 1)
        self.assertEqual(state.security_events[0]["message"], "Test event")

    def test_event_order_newest_first(self):
        self.srv.add_security_event({"message": "First"})
        self.srv.add_security_event({"message": "Second"})
        state = self.srv._collect_state()
        self.assertEqual(state.security_events[0]["message"], "Second")
        self.assertEqual(state.security_events[1]["message"], "First")

    def test_event_cap_at_50(self):
        for i in range(60):
            self.srv.add_security_event({"message": f"Event {i}"})
        state = self.srv._collect_state()
        # State shows max 20 (frontend slice), internal cap is 50
        self.assertLessEqual(len(state.security_events), 20)

    def test_events_returned_max_20(self):
        """Frontend gets at most 20 events."""
        for i in range(30):
            self.srv.add_security_event({"message": f"Event {i}"})
        state = self.srv._collect_state()
        self.assertEqual(len(state.security_events), 20)


# ---------------------------------------------------------------------------
# Unit: Runtime refs
# ---------------------------------------------------------------------------

class TestRuntimeRefs(unittest.TestCase):
    """Test update_runtime_refs with mock modules."""

    def setUp(self):
        self.srv = DashboardServer(port=0)

    def test_agent_manager_stats(self):
        mock_am = MagicMock()
        mock_am.get_stats.return_value = {"total": 50, "enabled": 12}
        self.srv.update_runtime_refs(agent_manager=mock_am)
        state = self.srv._collect_state()
        self.assertEqual(state.total_agents, 50)
        self.assertEqual(state.active_agents, 12)

    def test_stream_monitor_data(self):
        mock_sm = MagicMock()
        snap = MagicMock()
        snap.latency_p50_ms = 10.5
        snap.latency_p95_ms = 25.3
        snap.bitrate_kbps = 5200.0
        snap.fps = 59.9
        snap.frame_drop_pct = 0.1
        snap.packet_loss_pct = 0.02
        snap.jitter_ms = 1.5
        snap.rtt_ms = 8.2
        snap.resolution = "1920x1080"
        snap.abr_state = "stable"
        snap.security_level = "SECURE"
        snap.security_violations = 0
        mock_sm.get_latest.return_value = snap
        self.srv._stream_monitor = mock_sm
        state = self.srv._collect_state()
        self.assertAlmostEqual(state.latency_p50_ms, 10.5)
        self.assertAlmostEqual(state.fps, 59.9)
        self.assertEqual(state.resolution, "1920x1080")
        self.assertTrue(state.session_active)

    def test_stream_security_data(self):
        mock_sec = MagicMock()
        mock_sec.get_stats.return_value = {
            "overall_level": "DEGRADED",
            "total_violations": 3,
            "total_checks": 42,
            "dtls_status": "active",
            "srtp_status": "AES_128_CM",
        }
        self.srv._stream_security = mock_sec
        state = self.srv._collect_state()
        self.assertEqual(state.security_level, "DEGRADED")
        self.assertEqual(state.security_violations, 3)
        self.assertEqual(state.total_audits, 42)

    def test_device_harness_data(self):
        mock_dh = MagicMock()
        pixel = MagicMock()
        pixel.alive = True
        pixel.battery_pct = 85
        pixel.cpu_pct = 22
        pixel.mem_pct = 45
        router = MagicMock()
        router.alive = False
        mock_dh.health_check_all.return_value = {"pixel-8": pixel, "mudi-router": router}
        self.srv._device_harness = mock_dh
        state = self.srv._collect_state()
        self.assertEqual(len(state.devices), 2)
        pixel_dev = next(d for d in state.devices if "pixel" in d["name"].lower())
        self.assertEqual(pixel_dev["status"], "online")
        self.assertEqual(pixel_dev["battery_pct"], 85)

    def test_runtime_error_graceful(self):
        """Runtime module errors should not crash state collection."""
        mock_sm = MagicMock()
        mock_sm.get_latest.side_effect = RuntimeError("connection lost")
        self.srv._stream_monitor = mock_sm
        # Should not raise
        state = self.srv._collect_state()
        self.assertFalse(state.session_active)


# ---------------------------------------------------------------------------
# Integration: HTTP server
# ---------------------------------------------------------------------------

class TestHTTPServer(unittest.TestCase):
    """Test the actual HTTP server start/stop and endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.srv = DashboardServer(port=18421)
        cls.srv.start()
        # Wait for server to be ready
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        time.sleep(0.1)

    def _get(self, path):
        conn = HTTPConnection("127.0.0.1", 18421, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def test_root_serves_html(self):
        resp, body = self._get("/")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type"))
        self.assertIn(b"SYLION", body)

    def test_index_html_serves_html(self):
        resp, body = self._get("/index.html")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"SYLION", body)

    def test_api_state_json(self):
        resp, body = self._get("/api/state")
        self.assertEqual(resp.status, 200)
        self.assertIn("application/json", resp.getheader("Content-Type"))
        data = json.loads(body)
        self.assertIn("stages", data)
        self.assertIn("pipeline_status", data)
        self.assertEqual(len(data["stages"]), 14)

    def test_api_state_cors_header(self):
        resp, _ = self._get("/api/state")
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), "*")

    def test_404_on_unknown_path(self):
        resp, _ = self._get("/nonexistent")
        self.assertEqual(resp.status, 404)

    def test_state_reflects_callbacks(self):
        """Stage changes should be reflected in API response."""
        self.srv.set_pipeline_status("running")
        self.srv.set_stage_running("3", "Cross-Verify")
        resp, body = self._get("/api/state")
        data = json.loads(body)
        self.assertEqual(data["pipeline_status"], "running")
        self.assertEqual(data["current_stage"], "Cross-Verify")
        s3 = next(s for s in data["stages"] if s["id"] == "3")
        self.assertEqual(s3["status"], "running")


# ---------------------------------------------------------------------------
# Concurrency: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):
    """Concurrent state updates should not corrupt state."""

    def test_concurrent_stage_updates(self):
        srv = DashboardServer(port=0)
        errors = []

        def updater(stage_id, stage_name):
            try:
                for _ in range(50):
                    srv.set_stage_running(stage_id, stage_name)
                    srv.set_stage_completed(stage_id, stage_name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=updater, args=(sid, sname))
            for sid, sname in PIPELINE_STAGES[:6]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Errors in concurrent updates: {errors}")
        # State should still be valid JSON
        state = srv._collect_state()
        raw = state.to_json()
        json.loads(raw)  # Should not raise

    def test_concurrent_event_adds(self):
        srv = DashboardServer(port=0)
        errors = []

        def adder(prefix):
            try:
                for i in range(30):
                    srv.add_security_event({"message": f"{prefix}-{i}"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=adder, args=(f"T{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0)


# ---------------------------------------------------------------------------
# Edge: HTML content
# ---------------------------------------------------------------------------

class TestDashboardHTML(unittest.TestCase):
    """Validate the embedded HTML string."""

    def test_html_not_empty(self):
        self.assertGreater(len(DASHBOARD_HTML), 1000)

    def test_html_has_doctype(self):
        self.assertTrue(DASHBOARD_HTML.strip().startswith("<!DOCTYPE html>"))

    def test_html_has_closing_tags(self):
        self.assertIn("</html>", DASHBOARD_HTML)
        self.assertIn("</body>", DASHBOARD_HTML)
        self.assertIn("</script>", DASHBOARD_HTML)

    def test_html_has_api_endpoint(self):
        self.assertIn("/api/state", DASHBOARD_HTML)

    def test_html_has_all_panels(self):
        self.assertIn("Pipeline", DASHBOARD_HTML)
        self.assertIn("Streaming", DASHBOARD_HTML)
        self.assertIn("Security", DASHBOARD_HTML)
        self.assertIn("Devices", DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# Edge: Server lifecycle
# ---------------------------------------------------------------------------

class TestServerLifecycle(unittest.TestCase):
    """Start/stop idempotency and port fallback."""

    def test_double_start_idempotent(self):
        srv = DashboardServer(port=18422)
        srv.start()
        srv.start()  # Should be a no-op
        time.sleep(0.2)
        srv.stop()
        time.sleep(0.1)

    def test_stop_without_start(self):
        srv = DashboardServer(port=0)
        srv.stop()  # Should not raise

    def test_port_fallback(self):
        """If default port is taken, server should try port+1."""
        srv1 = DashboardServer(port=18423)
        srv1.start()
        time.sleep(0.2)
        srv2 = DashboardServer(port=18423)
        srv2.start()
        time.sleep(0.2)
        self.assertEqual(srv2.port, 18424)
        srv2.stop()
        srv1.stop()
        time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()
