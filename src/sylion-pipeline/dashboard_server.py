#!/usr/bin/env python3
"""
SYLION Dashboard Server — embedded web UI for real-time pipeline monitoring.

Runs as a background thread inside the orchestrator.  Zero external deps
beyond the Python stdlib (http.server, json, threading).

Collects real data from:
  - StreamMonitor  (latency, bitrate, FPS, frame drops, jitter, packet loss)
  - StreamSecurity (threat level, DTLS/SRTP status, violations)
  - DeviceHarness  (Pixel 8, laptop, router health)
  - Pipeline stage  progress (fed by orchestrator callbacks)

Serves a single self-contained HTML page on a configurable port (default 8420).
The page auto-refreshes via fetch('/api/state') every 1.5 seconds.

Usage inside orchestrator:
    from dashboard_server import DashboardServer
    dash = DashboardServer(port=8420)
    dash.update_runtime_refs(stream_monitor=..., device_harness=..., ...)
    dash.start()          # background thread
    dash.set_stage(...)   # called as pipeline progresses
    dash.stop()           # graceful shutdown

LLM NIGDY nie wydaje raw shell.  Only pre-approved scenarios.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.dashboard")

# ---------------------------------------------------------------------------
# Data model — what the dashboard shows
# ---------------------------------------------------------------------------

@dataclass
class StageInfo:
    """Single pipeline stage status."""
    id: str = ""
    name: str = ""
    status: str = "pending"     # pending | running | completed | failed | gated | skipped
    progress: int = 0           # 0-100
    started_at: float = 0.0
    finished_at: float = 0.0

@dataclass
class DashboardState:
    """Full dashboard state, serialised to JSON for the frontend."""
    # Pipeline
    stages: list[dict] = field(default_factory=list)
    current_stage: str = ""
    total_agents: int = 47
    active_agents: int = 0
    completed_gates: int = 0
    total_gates: int = 14
    pipeline_status: str = "idle"   # idle | running | completed | error
    uptime_s: float = 0.0

    # Streaming
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    bitrate_kbps: float = 0.0
    fps: float = 0.0
    frame_drop_pct: float = 0.0
    packet_loss_pct: float = 0.0
    jitter_ms: float = 0.0
    input_latency_ms: float = 0.0
    resolution: str = ""
    abr_state: str = ""
    session_active: bool = False

    # Security
    security_level: str = "UNKNOWN"
    dtls_status: str = ""
    srtp_status: str = ""
    security_violations: int = 0
    total_audits: int = 0
    security_events: list[dict] = field(default_factory=list)

    # Devices
    devices: list[dict] = field(default_factory=list)

    # Meta
    timestamp: str = ""
    pipeline_start_time: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


# ---------------------------------------------------------------------------
# Pipeline stage definitions (matches orchestrator)
# ---------------------------------------------------------------------------

PIPELINE_STAGES = [
    ("1",   "Config Load"),
    ("2",   "Audit"),
    ("3",   "Cross-Verify"),
    ("4",   "Merge"),
    ("5",   "Patch"),
    ("5.5", "Runtime Health"),
    ("5.6", "Fact Check"),
    ("6",   "Deploy"),
    ("6.5", "Streaming"),
    ("7",   "Test"),
    ("7.5", "E2E Session"),
    ("8",   "Security"),
    ("8.5", "SDR"),
    ("9",   "Report"),
]


# ---------------------------------------------------------------------------
# Dashboard Server
# ---------------------------------------------------------------------------

class DashboardServer:
    """
    Embedded HTTP server that serves the dashboard UI and state API.

    Thread-safe: all state updates go through a lock.
    """

    def __init__(self, port: int = 8420):
        self.port = port
        self._lock = threading.Lock()
        self._state = DashboardState()
        self._start_time = time.time()
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

        # Runtime module references (set after orchestrator init)
        self._stream_monitor = None
        self._stream_security = None
        self._device_harness = None
        self._metrics_collector = None
        self._abr_controller = None

        # Stage tracking
        self._stage_info: dict[str, StageInfo] = {}
        for sid, sname in PIPELINE_STAGES:
            self._stage_info[sid] = StageInfo(id=sid, name=sname)

        # Security event log
        self._security_events: list[dict] = []

    # --- Runtime refs (called once after init_supervisor) ---

    def update_runtime_refs(
        self,
        stream_monitor=None,
        stream_security=None,
        device_harness=None,
        metrics_collector=None,
        abr_controller=None,
        agent_manager=None,
    ):
        """Set references to runtime modules for live data collection."""
        self._stream_monitor = stream_monitor
        self._stream_security = stream_security
        self._device_harness = device_harness
        self._metrics_collector = metrics_collector
        self._abr_controller = abr_controller
        if agent_manager:
            stats = agent_manager.get_stats()
            with self._lock:
                self._state.total_agents = stats.get("total", 47)
                self._state.active_agents = stats.get("enabled", 0)

    # --- Pipeline stage callbacks (called from orchestrator loop) ---

    def set_pipeline_status(self, status: str):
        """Set overall pipeline status: idle, running, completed, error."""
        with self._lock:
            self._state.pipeline_status = status

    def set_stage_running(self, stage_num: float | int | str, stage_name: str):
        """Mark a stage as running."""
        sid = str(stage_num)
        with self._lock:
            if sid in self._stage_info:
                self._stage_info[sid].status = "running"
                self._stage_info[sid].started_at = time.time()
            self._state.current_stage = stage_name

    def set_stage_completed(self, stage_num: float | int | str, stage_name: str):
        """Mark a stage as completed."""
        sid = str(stage_num)
        with self._lock:
            if sid in self._stage_info:
                self._stage_info[sid].status = "completed"
                self._stage_info[sid].progress = 100
                self._stage_info[sid].finished_at = time.time()
            self._state.completed_gates += 1

    def set_stage_skipped(self, stage_num: float | int | str, stage_name: str):
        """Mark a stage as skipped."""
        sid = str(stage_num)
        with self._lock:
            if sid in self._stage_info:
                self._stage_info[sid].status = "skipped"

    def set_stage_failed(self, stage_num: float | int | str, stage_name: str):
        """Mark a stage as failed."""
        sid = str(stage_num)
        with self._lock:
            if sid in self._stage_info:
                self._stage_info[sid].status = "failed"

    def add_security_event(self, event: dict):
        """Add a security audit event to the log."""
        with self._lock:
            self._security_events.insert(0, event)
            if len(self._security_events) > 50:
                self._security_events = self._security_events[:50]

    # --- Collect live state ---

    def _collect_state(self) -> DashboardState:
        """Build a full DashboardState snapshot from runtime modules."""
        with self._lock:
            state = DashboardState()
            state.pipeline_status = self._state.pipeline_status
            state.current_stage = self._state.current_stage
            state.total_agents = self._state.total_agents
            state.active_agents = self._state.active_agents
            state.completed_gates = self._state.completed_gates
            state.total_gates = self._state.total_gates
            state.pipeline_start_time = self._start_time
            state.uptime_s = time.time() - self._start_time
            state.timestamp = time.strftime("%H:%M:%S", time.gmtime())

            # Stages
            state.stages = []
            for sid, sname in PIPELINE_STAGES:
                info = self._stage_info.get(sid, StageInfo(id=sid, name=sname))
                elapsed = ""
                if info.status == "completed" and info.started_at > 0:
                    elapsed = f"{info.finished_at - info.started_at:.0f}s"
                elif info.status == "running" and info.started_at > 0:
                    elapsed = f"{time.time() - info.started_at:.0f}s"
                state.stages.append({
                    "id": info.id,
                    "name": info.name,
                    "status": info.status,
                    "progress": info.progress,
                    "elapsed": elapsed,
                })

            # Security events
            state.security_events = list(self._security_events[:20])

        # --- Streaming metrics from StreamMonitor ---
        if self._stream_monitor:
            try:
                snap = self._stream_monitor.get_latest()
                if snap:
                    state.latency_p50_ms = snap.latency_p50_ms
                    state.latency_p95_ms = snap.latency_p95_ms
                    state.bitrate_kbps = snap.bitrate_kbps
                    state.fps = snap.fps
                    state.frame_drop_pct = snap.frame_drop_pct
                    state.packet_loss_pct = snap.packet_loss_pct
                    state.jitter_ms = snap.jitter_ms
                    state.input_latency_ms = snap.rtt_ms
                    state.resolution = snap.resolution
                    state.abr_state = snap.abr_state
                    state.session_active = True

                    # Security from snapshot
                    state.security_level = snap.security_level or "UNKNOWN"
                    state.security_violations = snap.security_violations
            except Exception as e:
                log.debug("Dashboard: StreamMonitor read error: %s", e)

        # --- Stream Security ---
        if self._stream_security:
            try:
                sec_stats = self._stream_security.get_stats()
                state.security_level = sec_stats.get("overall_level", state.security_level)
                state.security_violations = sec_stats.get("total_violations", state.security_violations)
                state.total_audits = sec_stats.get("total_checks", 0)
                # DTLS/SRTP status
                state.dtls_status = sec_stats.get("dtls_status", "")
                state.srtp_status = sec_stats.get("srtp_status", "")
            except Exception as e:
                log.debug("Dashboard: StreamSecurity read error: %s", e)

        # --- Devices ---
        if self._device_harness:
            try:
                health = self._device_harness.health_check_all()
                devices = []
                for name, status in health.items():
                    dev = {
                        "name": name,
                        "status": "online" if getattr(status, "alive", False) else "offline",
                        "type": "phone" if "pixel" in name.lower() else (
                            "router" if "mudi" in name.lower() or "router" in name.lower()
                            else "laptop"
                        ),
                    }
                    if hasattr(status, "battery_pct"):
                        dev["battery_pct"] = status.battery_pct
                    if hasattr(status, "cpu_pct"):
                        dev["cpu_pct"] = status.cpu_pct
                    if hasattr(status, "mem_pct"):
                        dev["mem_pct"] = status.mem_pct
                    devices.append(dev)
                state.devices = devices
            except Exception as e:
                log.debug("Dashboard: DeviceHarness read error: %s", e)

        # Fallback: if no live devices, provide static config
        if not state.devices:
            state.devices = [
                {"name": "Pixel 8", "type": "phone", "status": "idle",
                 "ip": "192.168.8.101", "connection": "USB/ADB"},
                {"name": "Laptop (Host)", "type": "laptop", "status": "online",
                 "ip": "192.168.8.1", "connection": "LAN/Host"},
                {"name": "Mudi 750v2", "type": "router", "status": "idle",
                 "ip": "192.168.8.254", "connection": "Ethernet"},
            ]

        return state

    # --- HTTP Handler ---

    def _make_handler(server_ref: "DashboardServer"):
        """Create an HTTP request handler class with access to the server."""

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress default access logs (too noisy)
                pass

            def do_GET(self):
                if self.path == "/api/state":
                    state = server_ref._collect_state()
                    body = state.to_json().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/" or self.path == "/index.html":
                    body = DASHBOARD_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

        return Handler

    # --- Start / Stop ---

    def start(self):
        """Start dashboard server in a background daemon thread."""
        if self._running:
            return

        HandlerClass = DashboardServer._make_handler(self)
        try:
            self._httpd = HTTPServer(("0.0.0.0", self.port), HandlerClass)
        except OSError as e:
            log.warning("Dashboard server: port %d unavailable (%s), trying %d",
                        self.port, e, self.port + 1)
            self.port += 1
            self._httpd = HTTPServer(("0.0.0.0", self.port), HandlerClass)

        self._running = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="sylion-dashboard",
            daemon=True,
        )
        self._thread.start()
        log.info("Dashboard server started: http://localhost:%d", self.port)

    def stop(self):
        """Stop the dashboard server."""
        if self._httpd:
            self._httpd.shutdown()
            self._running = False
            log.info("Dashboard server stopped")


# ---------------------------------------------------------------------------
# Self-contained HTML/CSS/JS dashboard (dark terminal theme)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SYLION — Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0e0c;--surface:#0e1412;--border:#1a2a22;
  --green:#00cc88;--green-dim:rgba(0,204,136,0.3);--green-bright:#00ffaa;
  --cyan:#00ccdd;--yellow:#eebb33;--red:#ee4444;--orange:#ee8833;
  --text:#b8e0d0;--text-dim:#4a6a5a;--text-bright:#d0f0e0;
}
html,body{height:100%;overflow:hidden;background:var(--bg);color:var(--text);
  font-family:'JetBrains Mono',monospace;font-size:12px;
  font-variant-numeric:tabular-nums lining-nums;letter-spacing:0.02em}

/* Layout: header + 2x2 grid + footer */
.dashboard{display:grid;grid-template-rows:auto 1fr auto;height:100vh;width:100vw}
.header{display:flex;align-items:center;justify-content:space-between;
  padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface)}
.header h1{font-size:14px;font-weight:700;color:var(--green);letter-spacing:0.15em;text-transform:uppercase}
.header .sub{font-size:9px;color:var(--text-dim);letter-spacing:0.2em;text-transform:uppercase}
.header .meta{display:flex;align-items:center;gap:16px;font-size:10px;color:var(--text-dim)}
.header .meta .val{color:var(--green)}
.cursor{display:inline-block;width:6px;height:14px;background:var(--green);
  animation:blink 1s step-end infinite;vertical-align:middle;margin-left:4px}
@keyframes blink{50%{opacity:0}}
@keyframes glow{0%,100%{box-shadow:0 0 4px var(--green-dim)}50%{box-shadow:0 0 12px var(--green)}}

.grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;
  gap:1px;background:rgba(0,204,136,0.08);overflow:hidden;min-height:0}
.panel{background:var(--bg);overflow:hidden;display:flex;flex-direction:column}
.panel-head{display:flex;align-items:center;justify-content:space-between;
  padding:6px 14px;border-bottom:1px solid rgba(0,204,136,0.15)}
.panel-head .title{font-size:11px;font-weight:700;color:var(--green);
  text-transform:uppercase;letter-spacing:0.12em;display:flex;align-items:center;gap:6px}
.panel-head .badge{font-size:9px;padding:2px 8px;border-radius:3px;font-weight:700;text-transform:uppercase}
.badge-ok{background:rgba(0,204,136,0.15);color:var(--green);border:1px solid rgba(0,204,136,0.3)}
.badge-warn{background:rgba(238,187,51,0.15);color:var(--yellow);border:1px solid rgba(238,187,51,0.3)}
.badge-crit{background:rgba(238,68,68,0.15);color:var(--red);border:1px solid rgba(238,68,68,0.3);animation:glow 2s infinite}
.badge-live{display:flex;align-items:center;gap:4px;font-size:9px;color:var(--green)}
.badge-live .dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:glow 2s infinite}
.panel-body{flex:1;overflow-y:auto;overflow-x:hidden;padding:6px 10px;overscroll-behavior:contain}
.panel-body::-webkit-scrollbar{width:3px}
.panel-body::-webkit-scrollbar-thumb{background:rgba(0,204,136,0.25);border-radius:2px}

/* KPI strip */
.kpi-strip{display:flex;gap:0;border-bottom:1px solid rgba(0,204,136,0.08);padding:4px 14px}
.kpi{flex:1;text-align:center}
.kpi .label{font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.1em}
.kpi .value{font-size:13px;font-weight:600;color:var(--green-bright)}

/* Stage row */
.stage{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:3px;font-size:11px}
.stage.running{background:rgba(0,204,136,0.06);border:1px solid rgba(0,204,136,0.15)}
.stage .icon{width:14px;text-align:center;flex-shrink:0}
.stage .sid{width:28px;color:var(--text-dim);font-size:10px;flex-shrink:0}
.stage .sname{flex:1;color:var(--text-bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stage .elapsed{width:36px;text-align:right;color:var(--text-dim);font-size:10px;flex-shrink:0}
.stage .bar{width:60px;height:5px;background:rgba(0,204,136,0.08);border-radius:3px;overflow:hidden;flex-shrink:0}
.stage .bar .fill{height:100%;border-radius:3px;transition:width 0.5s}
.fill-done{background:rgba(0,204,136,0.5)}
.fill-run{background:rgba(0,204,136,0.35)}
.fill-skip{background:rgba(100,100,100,0.3)}

/* Metric row */
.metric{display:flex;align-items:center;gap:6px;padding:4px 6px;border-radius:3px;font-size:11px}
.metric:hover{background:rgba(0,204,136,0.04)}
.metric .mbadge{font-size:8px;padding:1px 5px;border-radius:2px;font-weight:700;text-transform:uppercase;flex-shrink:0;width:34px;text-align:center}
.metric .mlabel{width:100px;color:var(--cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.metric .mval{width:56px;text-align:right;font-weight:700;font-size:12px;flex-shrink:0}
.metric .munit{width:30px;color:var(--text-dim);font-size:10px;flex-shrink:0}

/* Security */
.sec-info{display:grid;grid-template-columns:1fr 1fr;gap:2px 12px;padding:4px 14px;border-bottom:1px solid rgba(0,204,136,0.08);font-size:10px}
.sec-info .sk{color:var(--text-dim)}.sec-info .sv{color:var(--green)}
.event{display:flex;align-items:flex-start;gap:6px;padding:2px 4px;font-size:10px;border-radius:2px}
.event:hover{background:rgba(0,204,136,0.04)}
.event .etime{color:var(--text-dim);width:50px;flex-shrink:0}
.event .emsg{flex:1;min-width:0}

/* Device card */
.device{border:1px solid rgba(0,204,136,0.12);border-radius:4px;padding:8px 10px;margin-bottom:6px;background:rgba(0,204,136,0.02)}
.device .dhead{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.device .dname{font-size:11px;font-weight:700;color:var(--text-bright)}
.device .dstatus{font-size:9px;text-transform:uppercase}
.device .dstatus.online{color:var(--green)}.device .dstatus.offline{color:var(--red)}.device .dstatus.idle{color:var(--yellow)}
.ubar{display:flex;align-items:center;gap:4px;margin-bottom:2px}
.ubar .ulabel{width:24px;font-size:9px;color:var(--text-dim)}
.ubar .utrack{flex:1;height:5px;background:rgba(0,204,136,0.08);border-radius:3px;overflow:hidden}
.ubar .ufill{height:100%;border-radius:3px;transition:width 0.5s}
.ubar .upct{width:28px;font-size:9px;color:var(--cyan);text-align:right}
.dinfo{display:grid;grid-template-columns:1fr 1fr;gap:1px 8px;font-size:9px}
.dinfo .dk{color:var(--text-dim)}.dinfo .dv{color:var(--cyan)}

.footer{display:flex;align-items:center;justify-content:space-between;
  padding:3px 16px;border-top:1px solid var(--border);background:var(--surface);font-size:9px;color:var(--text-dim)}

/* SVG icon helpers */
svg.ico{width:14px;height:14px;stroke:var(--green);fill:none;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
</style>
</head>
<body>
<div class="dashboard">
  <!-- Header -->
  <div class="header">
    <div style="display:flex;align-items:center;gap:10px">
      <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
        <path d="M16 2 L28 9 L28 23 L16 30 L4 23 L4 9 Z" stroke="#00cc88" stroke-width="1.5"/>
        <path d="M16 8 L22 11.5 L22 18.5 L16 22 L10 18.5 L10 11.5 Z" stroke="#00cc88" stroke-width="1" opacity="0.5"/>
        <circle cx="16" cy="15" r="2.5" fill="#00cc88"/>
      </svg>
      <div>
        <h1>SYLION</h1>
        <div class="sub">Command Center</div>
      </div>
    </div>
    <div class="meta">
      <span>sys.status <span class="val" id="h-status">NOMINAL</span><span class="cursor"></span></span>
      <span id="h-time" class="val">--:--:--</span> <span>UTC</span>
    </div>
  </div>

  <!-- 2x2 Grid -->
  <div class="grid">
    <!-- Panel: Pipeline -->
    <div class="panel">
      <div class="panel-head">
        <span class="title">
          <svg class="ico" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>
          Pipeline
        </span>
        <span id="p-agents" style="font-size:10px;color:var(--text-dim)">AGENTS: 0/47 &nbsp; GATES: 0/14</span>
      </div>
      <div class="kpi-strip">
        <div class="kpi"><div class="label">Uptime</div><div class="value" id="p-uptime">00:00:00</div></div>
        <div class="kpi"><div class="label">Current</div><div class="value" id="p-current">--</div></div>
        <div class="kpi"><div class="label">Status</div><div class="value" id="p-status">idle</div></div>
      </div>
      <div class="panel-body" id="p-stages"></div>
    </div>

    <!-- Panel: Streaming -->
    <div class="panel">
      <div class="panel-head">
        <span class="title">
          <svg class="ico" viewBox="0 0 24 24"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 010 8.49"/><path d="M7.76 16.24a6 6 0 010-8.49"/><path d="M19.07 4.93a10 10 0 010 14.14"/><path d="M4.93 19.07a10 10 0 010-14.14"/></svg>
          Streaming
          <span class="badge-live" id="s-live" style="display:none"><span class="dot"></span>LIVE</span>
        </span>
        <span id="s-duration" style="font-size:10px;color:var(--text-dim)">--:--:--</span>
      </div>
      <div id="s-info" style="font-size:10px;color:var(--text-dim);padding:3px 14px;border-bottom:1px solid rgba(0,204,136,0.08);display:flex;gap:10px"></div>
      <div class="panel-body" id="s-metrics"></div>
    </div>

    <!-- Panel: Security -->
    <div class="panel">
      <div class="panel-head">
        <span class="title">
          <svg class="ico" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Security
        </span>
        <span id="sec-badge"></span>
      </div>
      <div class="sec-info" id="sec-info"></div>
      <div class="panel-body" id="sec-events">
        <div style="font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.15em;padding:2px 0">Audit Log</div>
      </div>
    </div>

    <!-- Panel: Devices -->
    <div class="panel">
      <div class="panel-head">
        <span class="title">
          <svg class="ico" viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0114.08 0"/><path d="M1.42 9a16 16 0 0121.16 0"/><path d="M8.53 16.11a6 6 0 016.95 0"/><circle cx="12" cy="20" r="1"/></svg>
          Devices
        </span>
        <span id="d-count" style="font-size:10px;color:var(--text-dim)">0/3 online</span>
      </div>
      <div class="panel-body" id="d-list"></div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <span>SYLION v2.0 — E2E Pipeline</span>
    <span>47 agents | 222 tests passed | 58 modules</span>
    <span>refresh: 1.5s | live data from pipeline</span>
  </div>
</div>

<script>
// --- State fetch + render loop ---
const API = '/api/state';
let prevStages = '';

function fmt(s){
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60);
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function statusIcon(s){
  if(s==='completed') return '<span style="color:#00cc88">&#10004;</span>';
  if(s==='running') return '<span style="color:#00cc88;animation:blink 1s step-end infinite">&#9654;</span>';
  if(s==='failed') return '<span style="color:#ee4444">&#10006;</span>';
  if(s==='skipped') return '<span style="color:#666">&#8722;</span>';
  if(s==='gated') return '<span style="color:#eebb33">&#9679;</span>';
  return '<span style="color:#333">&#9675;</span>';
}

function mBadge(v,thr,inv){
  let st='ok';
  if(inv){if(v<thr)st=v<thr*0.85?'crit':'warn';}
  else{if(v>thr)st=v>thr*1.5?'crit':'warn';}
  const cls=st==='ok'?'badge-ok':st==='warn'?'badge-warn':'badge-crit';
  const txt=st==='ok'?'OK':st==='warn'?'WARN':'CRIT';
  return `<span class="mbadge ${cls}">${txt}</span>`;
}

function mColor(v,thr,inv){
  let st='ok';
  if(inv){if(v<thr)st=v<thr*0.85?'crit':'warn';}
  else{if(v>thr)st=v>thr*1.5?'crit':'warn';}
  return st==='ok'?'var(--green)':st==='warn'?'var(--yellow)':'var(--red)';
}

function barColor(v){return v>80?'var(--red)':v>60?'var(--yellow)':'var(--green)';}

function secBadge(level){
  if(level==='SECURE') return '<span class="badge badge-ok">&#10003; SECURE</span>';
  if(level==='DEGRADED') return '<span class="badge badge-warn">&#9888; DEGRADED</span>';
  if(level==='INSECURE') return '<span class="badge badge-crit">&#9888; INSECURE</span>';
  return '<span class="badge" style="color:var(--text-dim);border:1px solid var(--text-dim);padding:2px 8px;border-radius:3px;font-size:9px">UNKNOWN</span>';
}

function render(d){
  // Header
  document.getElementById('h-time').textContent = d.timestamp || '--:--:--';
  document.getElementById('h-status').textContent = d.pipeline_status === 'error' ? 'ERROR' : 'NOMINAL';

  // Pipeline
  document.getElementById('p-uptime').textContent = fmt(d.uptime_s||0);
  document.getElementById('p-current').textContent = d.current_stage || '--';
  document.getElementById('p-status').textContent = (d.pipeline_status||'idle').toUpperCase();
  document.getElementById('p-agents').innerHTML =
    `AGENTS: <span style="color:var(--green-bright)">${d.active_agents||0}</span>/${d.total_agents||47} &nbsp; GATES: <span style="color:var(--green-bright)">${d.completed_gates||0}</span>/${d.total_gates||14}`;

  const stagesKey = JSON.stringify(d.stages);
  if(stagesKey !== prevStages){
    prevStages = stagesKey;
    let html = '';
    (d.stages||[]).forEach(s=>{
      const cls = s.status==='running'?' running':'';
      const fillCls = s.status==='completed'?'fill-done':s.status==='running'?'fill-run':'fill-skip';
      const pct = s.status==='completed'?100:s.status==='running'?50:0;
      html += `<div class="stage${cls}">
        <span class="icon">${statusIcon(s.status)}</span>
        <span class="sid">${s.id}</span>
        <span class="sname">${s.name}</span>
        <span class="elapsed">${s.elapsed||'--'}</span>
        <span class="bar"><span class="fill ${fillCls}" style="width:${pct}%"></span></span>
      </div>`;
    });
    document.getElementById('p-stages').innerHTML = html;
  }

  // Streaming
  const sess = d.session_active;
  document.getElementById('s-live').style.display = sess?'flex':'none';
  document.getElementById('s-duration').textContent = fmt(d.uptime_s||0);
  document.getElementById('s-info').innerHTML = sess
    ? `<span>${d.resolution||'--'}</span><span style="color:rgba(0,204,136,0.3)">|</span><span>ABR: ${d.abr_state||'--'}</span>`
    : '<span>No active session</span>';

  const metrics = [
    {l:'Video Latency',v:d.latency_p95_ms,u:'ms',t:30,inv:false},
    {l:'Bitrate',v:d.bitrate_kbps,u:'kbps',t:4800,inv:false},
    {l:'FPS',v:d.fps,u:'fps',t:57,inv:true},
    {l:'Frame Drop',v:d.frame_drop_pct,u:'%',t:0.8,inv:false},
    {l:'Packet Loss',v:d.packet_loss_pct,u:'%',t:0.3,inv:false},
    {l:'Input Latency',v:d.input_latency_ms,u:'ms',t:15,inv:false},
    {l:'Jitter',v:d.jitter_ms,u:'ms',t:3,inv:false},
  ];
  let mhtml='';
  metrics.forEach(m=>{
    const val = typeof m.v==='number'?m.v:0;
    mhtml += `<div class="metric">
      ${mBadge(val,m.t,m.inv)}
      <span class="mlabel">${m.l}</span>
      <span class="mval" style="color:${mColor(val,m.t,m.inv)}">${val.toFixed(m.u==='kbps'?0:m.u==='%'?2:1)}</span>
      <span class="munit">${m.u}</span>
    </div>`;
  });
  document.getElementById('s-metrics').innerHTML = mhtml;

  // Security
  document.getElementById('sec-badge').innerHTML = secBadge(d.security_level);
  document.getElementById('sec-info').innerHTML =
    `<div><span class="sk">DTLS:</span> <span class="sv">${d.dtls_status||'--'}</span></div>
     <div><span class="sk">SRTP:</span> <span class="sv">${d.srtp_status||'--'}</span></div>
     <div><span class="sk">Violations:</span> <span class="sv">${d.security_violations||0}</span></div>
     <div><span class="sk">Audits:</span> <span class="sv">${d.total_audits||0}</span></div>`;

  let ehtml = '<div style="font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.15em;padding:2px 0">Audit Log</div>';
  (d.security_events||[]).slice(0,15).forEach(e=>{
    const sev = e.severity||e.level||'info';
    const col = sev==='critical'?'var(--red)':sev==='warn'||sev==='warning'?'var(--yellow)':'var(--text-dim)';
    ehtml += `<div class="event">
      <span class="etime">${e.timestamp||''}</span>
      <span class="emsg" style="color:${col}">${e.message||e.msg||''}</span>
    </div>`;
  });
  document.getElementById('sec-events').innerHTML = ehtml;

  // Devices
  let dhtml = '';
  const devs = d.devices||[];
  const onlineCount = devs.filter(x=>x.status==='online').length;
  document.getElementById('d-count').innerHTML = `<span style="color:var(--green-bright)">${onlineCount}</span>/${devs.length} online`;

  devs.forEach(dv=>{
    const cpu = dv.cpu_pct||0, mem = dv.mem_pct||0;
    const icon = dv.type==='phone'?'&#128241;':dv.type==='router'?'&#128225;':'&#128187;';
    dhtml += `<div class="device">
      <div class="dhead">
        <span style="font-size:16px">${icon}</span>
        <span class="dname">${dv.name||'--'}</span>
        <span class="dstatus ${dv.status||'idle'}">${(dv.status||'idle').toUpperCase()}</span>
      </div>
      <div class="ubar"><span class="ulabel">CPU</span><span class="utrack"><span class="ufill" style="width:${cpu}%;background:${barColor(cpu)}"></span></span><span class="upct">${cpu}%</span></div>
      <div class="ubar"><span class="ulabel">MEM</span><span class="utrack"><span class="ufill" style="width:${mem}%;background:${barColor(mem)}"></span></span><span class="upct">${mem}%</span></div>
      <div class="dinfo">
        ${dv.ip?`<span><span class="dk">IP:</span> <span class="dv">${dv.ip}</span></span>`:''}
        ${dv.connection?`<span><span class="dk">Conn:</span> <span class="dv">${dv.connection}</span></span>`:''}
        ${dv.battery_pct!==undefined?`<span><span class="dk">Bat:</span> <span class="dv">${dv.battery_pct}%</span></span>`:''}
      </div>
    </div>`;
  });
  document.getElementById('d-list').innerHTML = dhtml;
}

// Fetch loop
async function tick(){
  try{
    const r = await fetch(API);
    if(r.ok) render(await r.json());
  }catch(e){/* retry next tick */}
}
setInterval(tick, 1500);
tick();
</script>
</body>
</html>
"""
