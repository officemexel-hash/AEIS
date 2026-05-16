#!/usr/bin/env python3
"""
SYLION Supervisor Agent + Human Gate + Deterministic Runner

Three-layer safety architecture:

  1. SUPERVISOR AGENT — watches all agents, maintains checklist,
     enforces plans, ensures nothing happens without approval
  
  2. HUMAN GATE — every action plan, command, and critical decision
     goes through the human administrator for approval
  
  3. DETERMINISTIC RUNNER — pre-approved command scenarios only,
     whitelisted ADB/SSH/HTTP commands, no raw shell execution

Architecture:
  LLM generates plan → Human Gate → Approved → Safe Runner → Output → LLM analysis

  ⚠️  LLM NEVER executes raw commands. It generates parameters for
      pre-approved scenarios. Period. Unless human explicitly grants permission.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("supervisor")

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


# ═══════════════════════════════════════════════════════════════════════════
# PART 1: HUMAN GATE — approval system
# ═══════════════════════════════════════════════════════════════════════════

class GateDecision(str, enum.Enum):
    APPROVED      = "approved"       # Go ahead
    REJECTED      = "rejected"       # Do NOT execute
    MODIFIED      = "modified"       # Human modified the plan
    DEFERRED      = "deferred"       # Decide later
    ESCALATED     = "escalated"      # Needs more investigation


class GateLevel(str, enum.Enum):
    """Security level determining what needs human approval."""
    INFO          = "info"           # Informational — auto-approve
    REVIEW        = "review"         # Review recommended but not required
    REQUIRED      = "required"       # MUST have human approval
    CRITICAL      = "critical"       # Critical — requires explicit confirmation


@dataclass
class GateRequest:
    """A request for human approval."""
    id: str
    agent_name: str
    stage: str
    level: GateLevel
    title: str
    description: str
    action_plan: list[dict]          # What will be done
    risk_assessment: str             # Why this needs approval
    proposed_commands: list[str]     # Exact commands to execute (from whitelist)
    requires_device_access: bool = False
    requires_network: bool = False
    requires_rf: bool = False        # SDR transmission
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Response
    decision: GateDecision | None = None
    human_notes: str = ""
    decided_at: str = ""
    modified_plan: list[dict] | None = None  # If human modifies the plan


@dataclass
class GateLog:
    """Audit log of all gate decisions."""
    entries: list[dict] = field(default_factory=list)

    def add(self, request: GateRequest):
        self.entries.append({
            "id": request.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": request.agent_name,
            "stage": request.stage,
            "level": request.level.value,
            "title": request.title,
            "decision": request.decision.value if request.decision else "pending",
            "human_notes": request.human_notes,
            "commands": request.proposed_commands,
        })

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"gate_log": self.entries}, f, indent=2, ensure_ascii=False)


class HumanGate:
    """Interactive human approval system.
    
    Every action plan goes through this gate. The human administrator
    sees exactly what will happen and approves/rejects/modifies it.
    
    Gate levels:
    - INFO: Auto-approved, just logged
    - REVIEW: Shown to human, auto-approved after timeout
    - REQUIRED: MUST be approved by human before proceeding
    - CRITICAL: Requires explicit "YES" confirmation
    """

    def __init__(self, log_path: Path | None = None,
                 auto_approve_info: bool = True,
                 timeout_seconds: int = 0):
        """
        Args:
            log_path: Path to save gate decision log
            auto_approve_info: Auto-approve INFO level requests
            timeout_seconds: 0 = wait forever for REQUIRED/CRITICAL
        """
        self.gate_log = GateLog()
        self.log_path = log_path or Path("results/gate_log.json")
        self.auto_approve_info = auto_approve_info
        self.timeout = timeout_seconds
        self.pending: dict[str, GateRequest] = {}
        self.history: list[GateRequest] = []

    def request_approval(self, request: GateRequest) -> GateRequest:
        """Submit a request for human approval. Blocks until decided."""
        
        # Auto-approve INFO level
        if request.level == GateLevel.INFO and self.auto_approve_info:
            request.decision = GateDecision.APPROVED
            request.decided_at = datetime.now(timezone.utc).isoformat()
            request.human_notes = "(auto-approved: info level)"
            self.gate_log.add(request)
            self.gate_log.save(self.log_path)
            return request

        # Display request to human
        self._display_request(request)
        
        # Get human decision
        request = self._get_decision(request)
        
        # Log and save
        self.gate_log.add(request)
        self.gate_log.save(self.log_path)
        self.history.append(request)
        
        return request

    def _display_request(self, req: GateRequest):
        """Display a gate request in the terminal."""
        level_colors = {
            GateLevel.INFO:     C.BLUE,
            GateLevel.REVIEW:   C.YELLOW,
            GateLevel.REQUIRED: f"{C.BOLD}{C.YELLOW}",
            GateLevel.CRITICAL: f"{C.BOLD}{C.RED}",
        }
        level_icons = {
            GateLevel.INFO:     "ℹ️ ",
            GateLevel.REVIEW:   "👁️ ",
            GateLevel.REQUIRED: "🔒",
            GateLevel.CRITICAL: "🚨",
        }
        lc = level_colors.get(req.level, C.WHITE)
        li = level_icons.get(req.level, "?")
        
        print()
        print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
        print(f"  {li} {lc}HUMAN GATE — {req.level.value.upper()}{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
        print()
        print(f"  {C.BOLD}Identyfikator:{C.RESET}  {req.id}")
        print(f"  {C.BOLD}Agent:{C.RESET}           {req.agent_name}")
        print(f"  {C.BOLD}Etap:{C.RESET}            {req.stage}")
        print(f"  {C.BOLD}Tytuł:{C.RESET}           {req.title}")
        print()
        print(f"  {C.BOLD}Opis:{C.RESET}")
        for line in textwrap.wrap(req.description, width=66):
            print(f"    {line}")
        print()
        
        # Risk assessment
        if req.risk_assessment:
            print(f"  {C.YELLOW}{C.BOLD}Ocena ryzyka:{C.RESET}")
            for line in textwrap.wrap(req.risk_assessment, width=66):
                print(f"    {C.YELLOW}{line}{C.RESET}")
            print()
        
        # Flags
        flags = []
        if req.requires_device_access:
            flags.append(f"{C.MAGENTA}📱 DEVICE ACCESS{C.RESET}")
        if req.requires_network:
            flags.append(f"{C.MAGENTA}🌐 NETWORK{C.RESET}")
        if req.requires_rf:
            flags.append(f"{C.RED}📡 RF TRANSMISSION{C.RESET}")
        if flags:
            print(f"  {C.BOLD}Flagi:{C.RESET}  {' | '.join(flags)}")
            print()
        
        # Action plan
        if req.action_plan:
            print(f"  {C.BOLD}Plan działania:{C.RESET}")
            for i, step in enumerate(req.action_plan, 1):
                status = step.get("status", "pending")
                desc = step.get("description", str(step))
                print(f"    {C.CYAN}{i}.{C.RESET} {desc}")
            print()
        
        # Proposed commands
        if req.proposed_commands:
            print(f"  {C.BOLD}Komendy do wykonania:{C.RESET}")
            for cmd in req.proposed_commands:
                # Highlight command type
                if cmd.startswith("adb"):
                    color = C.GREEN
                elif cmd.startswith("ssh") or cmd.startswith("scp"):
                    color = C.YELLOW
                elif cmd.startswith("http"):
                    color = C.BLUE
                else:
                    color = C.RED  # Unknown — extra caution
                print(f"    {color}$ {cmd}{C.RESET}")
            print()
        
        print(f"{C.BOLD}{C.CYAN}{'─' * 72}{C.RESET}")

    def _get_decision(self, req: GateRequest) -> GateRequest:
        """Get human decision from terminal input."""
        
        if req.level == GateLevel.CRITICAL:
            prompt = (f"  {C.RED}{C.BOLD}CRITICAL:{C.RESET} "
                     f"Wpisz {C.BOLD}YES{C.RESET} aby zatwierdzić, "
                     f"{C.BOLD}NO{C.RESET} aby odrzucić: ")
        else:
            prompt = (f"  [{C.GREEN}a{C.RESET}]pprove  "
                     f"[{C.RED}r{C.RESET}]eject  "
                     f"[{C.YELLOW}m{C.RESET}]odify  "
                     f"[{C.BLUE}d{C.RESET}]efer  "
                     f"[{C.MAGENTA}e{C.RESET}]scalate  "
                     f"[{C.CYAN}?{C.RESET}]help\n"
                     f"  {C.BOLD}> {C.RESET}")

        while True:
            try:
                choice = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {C.RED}Przerwane — odrzucam request{C.RESET}")
                req.decision = GateDecision.REJECTED
                req.human_notes = "Keyboard interrupt"
                break

            if req.level == GateLevel.CRITICAL:
                if choice == "yes":
                    req.decision = GateDecision.APPROVED
                    req.human_notes = self._get_notes("Notatka (opcjonalna): ")
                    break
                elif choice == "no":
                    req.decision = GateDecision.REJECTED
                    req.human_notes = self._get_notes("Powód odrzucenia: ")
                    break
                else:
                    print(f"  {C.RED}Wpisz dokładnie YES lub NO{C.RESET}")
                    continue

            if choice in ("a", "approve", "y", "yes", "tak"):
                req.decision = GateDecision.APPROVED
                req.human_notes = self._get_notes("Notatka (opcjonalna): ")
                break
            elif choice in ("r", "reject", "n", "no", "nie"):
                req.decision = GateDecision.REJECTED
                req.human_notes = self._get_notes("Powód odrzucenia: ")
                break
            elif choice in ("m", "modify"):
                req.decision = GateDecision.MODIFIED
                req.human_notes = self._get_notes("Opisz zmiany: ")
                modified = self._get_modified_plan(req)
                if modified:
                    req.modified_plan = modified
                break
            elif choice in ("d", "defer"):
                req.decision = GateDecision.DEFERRED
                req.human_notes = self._get_notes("Notatka: ")
                break
            elif choice in ("e", "escalate"):
                req.decision = GateDecision.ESCALATED
                req.human_notes = self._get_notes("Co wymaga dalszej analizy: ")
                break
            elif choice == "?":
                self._show_help()
            else:
                print(f"  {C.DIM}Nieznana opcja. Wpisz ? aby zobaczyć pomoc.{C.RESET}")

        req.decided_at = datetime.now(timezone.utc).isoformat()
        
        # Show decision
        decision_colors = {
            GateDecision.APPROVED: C.GREEN,
            GateDecision.REJECTED: C.RED,
            GateDecision.MODIFIED: C.YELLOW,
            GateDecision.DEFERRED: C.BLUE,
            GateDecision.ESCALATED: C.MAGENTA,
        }
        dc = decision_colors.get(req.decision, C.WHITE)
        print(f"\n  {dc}→ Decyzja: {req.decision.value.upper()}{C.RESET}")
        if req.human_notes:
            print(f"  {C.DIM}  Notatka: {req.human_notes}{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")
        
        return req

    @staticmethod
    def _get_notes(prompt: str) -> str:
        try:
            return input(f"  {C.DIM}{prompt}{C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    @staticmethod
    def _get_modified_plan(req: GateRequest) -> list[dict] | None:
        """Let human modify the action plan."""
        print(f"\n  {C.YELLOW}Edycja planu (wpisz nowe kroki, pusta linia = koniec):{C.RESET}")
        steps = []
        i = 1
        while True:
            try:
                step = input(f"  {C.CYAN}{i}.{C.RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not step:
                break
            steps.append({"description": step, "status": "pending"})
            i += 1
        return steps if steps else None

    @staticmethod
    def _show_help():
        print(f"""
  {C.BOLD}Human Gate — Pomoc{C.RESET}

  {C.GREEN}a/approve{C.RESET}  — Zatwierdź plan. Komendy zostaną wykonane.
  {C.RED}r/reject{C.RESET}   — Odrzuć plan. Nic nie zostanie wykonane.
  {C.YELLOW}m/modify{C.RESET}   — Zmodyfikuj plan przed wykonaniem.
  {C.BLUE}d/defer{C.RESET}    — Odłóż decyzję na później.
  {C.MAGENTA}e/escalate{C.RESET} — Wymaga dalszej analizy.
  
  {C.BOLD}Poziomy bezpieczeństwa:{C.RESET}
  {C.BLUE}INFO{C.RESET}      — Automatycznie zatwierdzane (tylko log)
  {C.YELLOW}REVIEW{C.RESET}    — Przegląd zalecany
  {C.BOLD}{C.YELLOW}REQUIRED{C.RESET}  — Zatwierdzenie WYMAGANE
  {C.RED}CRITICAL{C.RESET}  — Wymaga wpisania YES
""")


# ═══════════════════════════════════════════════════════════════════════════
# Patch D: DbPollingHumanGate — SQLite polling bridge CLI ↔ dashboard UI
# ═══════════════════════════════════════════════════════════════════════════

class DbPollingHumanGate(HumanGate):
    """HumanGate z polling SQLite — bridge CLI ↔ dashboard UI.
    Zapisuje GateRequest do human_gate i polluje decyzję. Fallback TTY gdy DB fail.
    """
    POLL_INTERVAL: float = 2.0

    def __init__(self, log_path=None, auto_approve_info=True,
                 timeout_seconds=3600, db_path=None, run_id=""):
        super().__init__(log_path=log_path, auto_approve_info=auto_approve_info,
                         timeout_seconds=timeout_seconds)
        if db_path is None:
            import os as _os
            from pathlib import Path as _P
            db_path = _P(_os.getenv("SYLION_DB_PATH",
                str(_P(__file__).parent / "sylion_aeis.db")))
        self.db_path = db_path
        self.run_id = run_id

    _SEV = {GateLevel.INFO: "INFO", GateLevel.REVIEW: "REVIEW",
            GateLevel.REQUIRED: "REQUIRED", GateLevel.CRITICAL: "CRITICAL"}
    _DEC = {"approved": GateDecision.APPROVED, "rejected": GateDecision.REJECTED,
            "modified": GateDecision.MODIFIED, "deferred": GateDecision.DEFERRED,
            "escalated": GateDecision.ESCALATED}

    def _get_decision(self, req):
        import sqlite3 as _sq, time as _t, json as _j
        try:
            conn = _sq.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = _sq.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "INSERT INTO human_gate "
                "(id,run_id,action_type,severity,title,description,"
                " context_json,options_json,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,'pending',?)",
                (req.id, self.run_id, req.agent_name or "orchestrator",
                 self._SEV.get(req.level, "REQUIRED"), req.title, req.description,
                 _j.dumps({"stage": req.stage, "plan": req.action_plan}),
                 _j.dumps([{"value": "approved", "label": "Zatwierdź"},
                            {"value": "rejected", "label": "Odrzuć"}]),
                 _t.time()),
            )
            conn.commit()
        except Exception as exc:
            import logging as _L
            _L.getLogger(__name__).warning("DbPollingHumanGate insert failed (%s) → TTY", exc)
            return super()._get_decision(req)
        deadline = (_t.time() + self.timeout) if self.timeout else float("inf")
        try:
            while _t.time() < deadline:
                row = conn.execute(
                    "SELECT decision,decided_at,decided_by FROM human_gate "
                    "WHERE id=? AND status IN ('decided','approved','rejected',"
                    "'modified','deferred','escalated')", (req.id,),
                ).fetchone()
                if row and row["decision"]:
                    req.decision = self._DEC.get(row["decision"].lower(), GateDecision.REJECTED)
                    req.human_notes = f"decided_by={row['decided_by'] or 'dashboard'}"
                    return req
                _t.sleep(self.POLL_INTERVAL)
            conn.execute("UPDATE human_gate SET status='timeout',decision='rejected',"
                         "decided_at=? WHERE id=?", (_t.time(), req.id))
            conn.commit()
            req.decision = GateDecision.REJECTED
            req.human_notes = "timeout"
            return req
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# PART 2: DETERMINISTIC RUNNER — whitelist-only command execution
# ═══════════════════════════════════════════════════════════════════════════

class CommandType(str, enum.Enum):
    ADB     = "adb"          # Android Debug Bridge
    SSH     = "ssh"          # SSH to router
    SCP     = "scp"          # Secure copy to router
    HTTP    = "http"         # HTTP request to management API
    LOCAL   = "local"        # Local command (go build, go test, etc.)
    SDR     = "sdr"          # SDR commands (hackrf_*, srsenb, etc.)


# Whitelisted command patterns — ONLY these can be executed
# Each pattern: (regex, description, gate_level)
COMMAND_WHITELIST: list[tuple[str, str, GateLevel]] = [
    # === ADB (Pixel / GrapheneOS) ===
    # NOTE: All patterns anchored with \Z (absolute end) to prevent injection via
    # appended shell metacharacters (;, &&, ||, $(), etc.).  See P0-A audit.
    (r"^adb devices\Z",
     "List connected ADB devices", GateLevel.INFO),
    (r"^adb shell getprop ro\.\w+\Z",
     "Get device property", GateLevel.INFO),
    (r"^adb shell /data/local/tmp/sylion-relay --version\Z",
     "Check SYLION relay version", GateLevel.INFO),
    (r"^adb shell /data/local/tmp/sylion-relay health\Z",
     "SYLION relay health check", GateLevel.INFO),
    (r"^adb shell ps \| grep sylion\Z",
     "Check SYLION processes", GateLevel.INFO),
    (r"^adb shell netstat -tlnp\Z",
     "List open ports on Pixel", GateLevel.REVIEW),
    (r"^adb push [\w./-]+/build/arm64/[\w.-]+ /data/local/tmp/\Z",
     "Push binary to Pixel", GateLevel.REQUIRED),
    (r"^adb shell chmod \+x /data/local/tmp/sylion-relay\Z",
     "Make relay executable", GateLevel.REQUIRED),
    (r"^adb install [\w./-]+\.apk\Z",
     "Install APK on Pixel", GateLevel.REQUIRED),
    (r"^adb shell am start [\w./=-]+\Z",
     "Start activity on Pixel", GateLevel.REQUIRED),
    (r"^adb logcat -s SYLION:\* -d\Z",
     "Dump SYLION logs from Pixel", GateLevel.INFO),
    (r"^adb logcat -s SYLION:\* -t \d+\Z",
     "Recent SYLION logs from Pixel", GateLevel.INFO),
    (r"^adb reboot recovery\Z",
     "Reboot Pixel to recovery", GateLevel.CRITICAL),
    (r"^adb sideload [\w./-]+\.zip\Z",
     "Sideload OTA to Pixel", GateLevel.CRITICAL),

    # === SSH (Router / OpenWrt) ===
    (r"^ssh root@[\d.]+ 'cat /etc/openwrt_release'\Z",
     "Check OpenWrt version", GateLevel.INFO),
    (r"^ssh root@[\d.]+ 'uptime'\Z",
     "Check router uptime", GateLevel.INFO),
    (r"^ssh root@[\d.]+ '/usr/local/bin/sylion-relay --version'\Z",
     "Check relay version on router", GateLevel.INFO),
    (r"^ssh root@[\d.]+ '/usr/local/bin/sylion-relay health'\Z",
     "SYLION relay health check on router", GateLevel.INFO),
    (r"^ssh root@[\d.]+ 'logread \| grep -i sylion \| tail -\d+'\Z",
     "Recent SYLION logs from router", GateLevel.INFO),
    (r"^ssh root@[\d.]+ 'netstat -tlnp'\Z",
     "List open ports on router", GateLevel.REVIEW),
    (r"^ssh root@[\d.]+ 'uci show sylion'\Z",
     "Show SYLION config on router", GateLevel.REVIEW),
    (r"^ssh root@[\d.]+ 'uqmi -d /dev/cdc-wdm0 --get-serving-system'\Z",
     "Check cellular connection status", GateLevel.INFO),
    (r"^scp [\w./-]+/build/amd64/sylion-relay root@[\d.]+:/usr/local/bin/\Z",
     "Deploy relay binary to router", GateLevel.REQUIRED),
    (r"^scp [\w./-]+/configs/[\w.-]+ root@[\d.]+:/etc/config/sylion\Z",
     "Deploy config to router", GateLevel.REQUIRED),
    (r"^ssh root@[\d.]+ '/etc/init.d/sylion restart'\Z",
     "Restart SYLION on router", GateLevel.REQUIRED),
    (r"^ssh root@[\d.]+ '/etc/init.d/sylion stop'\Z",
     "Stop SYLION on router", GateLevel.REQUIRED),
    (r"^ssh root@[\d.]+ 'sysupgrade [\w./-]+'\Z",
     "Firmware upgrade on router", GateLevel.CRITICAL),
    (r"^ssh root@[\d.]+ 'reboot'\Z",
     "Reboot router", GateLevel.CRITICAL),

    # === HTTP (Management API) ===
    (r"^curl -s http://localhost:\d+/health\Z",
     "Health check endpoint", GateLevel.INFO),
    (r"^curl -s http://localhost:\d+/api/v1/version\Z",
     "Version endpoint", GateLevel.INFO),
    (r"^curl -s http://localhost:\d+/metrics\Z",
     "Metrics endpoint", GateLevel.REVIEW),
    (r"^curl -s -X GET http://localhost:\d+/api/v1/[\w/.-]+\Z",
     "GET API request", GateLevel.REVIEW),
    (r"^curl -s -X POST http://localhost:\d+/api/v1/[\w/.-]+ -H '[\w :/-]+' -d '\{[^']*\}'\Z",
     "POST API request", GateLevel.REQUIRED),

    # === Local (build, test) ===
    (r"^go build -ldflags '[\w .=-]+' -o [\w./-]+ \./cmd/[\w.-]+\Z",
     "Build Go binary", GateLevel.REVIEW),
    (r"^go test \./\.\.\. [\w =-]+\Z",
     "Run Go tests", GateLevel.INFO),
    (r"^go vet \./\.\.\.\Z",
     "Run Go vet", GateLevel.INFO),
    (r"^go test -bench [\w./-]+ \./\.\.\.\Z",
     "Run Go benchmarks", GateLevel.INFO),

    # === SDR ===
    (r"^hackrf_info\Z",
     "HackRF device info", GateLevel.INFO),
    (r"^SoapySDRUtil --find\Z",
     "Find SDR devices", GateLevel.INFO),
    (r"^bash sdr/passive_monitor\.sh (?:check|scan)\Z",
     "SDR passive scan (no transmission)", GateLevel.REVIEW),
    (r"^bash sdr/passive_monitor\.sh full (?:baseline|compare)\Z",
     "SDR full passive capture", GateLevel.REQUIRED),
    (r"^SYLION_BTS_MODE=zmq bash sdr/rogue_bts\.sh [\w =-]+\Z",
     "SDR rogue BTS in ZeroMQ mode (simulation)", GateLevel.REQUIRED),
    (r"^SYLION_BTS_MODE=rf [\w ./=-]+\Z",
     "SDR RF TRANSMISSION (requires Faraday cage)", GateLevel.CRITICAL),
]


@dataclass
class CommandResult:
    """Result of executing a whitelisted command."""
    command: str
    command_type: CommandType
    whitelisted: bool
    gate_level: GateLevel
    description: str
    approved: bool = False
    executed: bool = False
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: int = 0
    error: str = ""


class DeterministicRunner:
    """Safe command execution with whitelist enforcement.
    
    RULES:
    1. ONLY whitelisted commands can be executed
    2. Every command is matched against regex patterns
    3. Gate level determines approval requirement
    4. All commands are logged with full audit trail
    5. LLM generates parameters, NOT raw commands
    """

    def __init__(self, gate: HumanGate, dry_run: bool = False):
        self.gate = gate
        self.dry_run = dry_run
        self.execution_log: list[CommandResult] = []
        self.whitelist = COMMAND_WHITELIST

    def validate_command(self, cmd: str) -> tuple[bool, str, GateLevel]:
        """Check if a command matches the whitelist.
        
        Returns: (is_whitelisted, description, gate_level)
        """
        for pattern, description, level in self.whitelist:
            if re.match(pattern, cmd):
                return True, description, level
        return False, "UNKNOWN COMMAND — NOT IN WHITELIST", GateLevel.CRITICAL

    def execute(self, commands: list[str], agent_name: str,
                stage: str, context: str = "") -> list[CommandResult]:
        """Execute a list of commands through the safety pipeline.
        
        Flow:
        1. Validate each command against whitelist
        2. Group by gate level
        3. Request human approval for each group
        4. Execute approved commands
        5. Return results
        """
        results = []

        # Validate all commands first
        validated = []
        for cmd in commands:
            is_ok, desc, level = self.validate_command(cmd)
            cr = CommandResult(
                command=cmd,
                command_type=self._detect_type(cmd),
                whitelisted=is_ok,
                gate_level=level,
                description=desc,
            )
            validated.append(cr)

        # Reject non-whitelisted commands immediately
        rejected = [v for v in validated if not v.whitelisted]
        for r in rejected:
            r.error = "REJECTED: Command not in whitelist"
            log.warning(f"  ✗ BLOCKED: {r.command} — not whitelisted")
            results.append(r)

        # Group approved commands by gate level
        approved_cmds = [v for v in validated if v.whitelisted]
        if not approved_cmds:
            return results

        # Build gate request
        gate_request = GateRequest(
            id=f"gate-{uuid.uuid4().hex[:8]}",
            agent_name=agent_name,
            stage=stage,
            level=max((c.gate_level for c in approved_cmds),
                      key=lambda l: list(GateLevel).index(l)),
            title=f"Wykonanie {len(approved_cmds)} komend",
            description=context or f"Agent {agent_name} chce wykonać komendy w etapie {stage}",
            action_plan=[
                {"description": f"[{c.gate_level.value}] {c.description}",
                 "command": c.command, "status": "pending"}
                for c in approved_cmds
            ],
            risk_assessment=self._assess_risk(approved_cmds),
            proposed_commands=[c.command for c in approved_cmds],
            requires_device_access=any(
                c.command_type in (CommandType.ADB, CommandType.SSH, CommandType.SCP)
                for c in approved_cmds
            ),
            requires_network=any(
                c.command_type in (CommandType.SSH, CommandType.SCP, CommandType.HTTP)
                for c in approved_cmds
            ),
            requires_rf=any(
                c.command_type == CommandType.SDR and "rf" in c.command.lower()
                for c in approved_cmds
            ),
        )

        # Send through Human Gate
        gate_result = self.gate.request_approval(gate_request)

        if gate_result.decision == GateDecision.APPROVED:
            # Execute each command
            for cr in approved_cmds:
                cr.approved = True
                if self.dry_run:
                    cr.stdout = f"[DRY-RUN] Would execute: {cr.command}"
                    cr.executed = False
                    log.info(f"  (dry-run) {cr.command}")
                else:
                    self._run_command(cr)
                results.append(cr)

        elif gate_result.decision == GateDecision.MODIFIED:
            # Execute modified plan
            if gate_result.modified_plan:
                log.info(f"  Human modified plan: {len(gate_result.modified_plan)} steps")
                for step in gate_result.modified_plan:
                    cmd = step.get("command", step.get("description", ""))
                    is_ok, desc, level = self.validate_command(cmd)
                    cr = CommandResult(
                        command=cmd, command_type=self._detect_type(cmd),
                        whitelisted=is_ok, gate_level=level,
                        description=desc, approved=is_ok,
                    )
                    if is_ok and not self.dry_run:
                        self._run_command(cr)
                    results.append(cr)
        else:
            # Rejected/deferred/escalated
            for cr in approved_cmds:
                cr.approved = False
                cr.error = f"Gate decision: {gate_result.decision.value}"
                results.append(cr)

        self.execution_log.extend(results)
        return results

    def _run_command(self, cr: CommandResult):
        """Actually execute a command (after all safety checks passed)."""
        log.info(f"  ▶ Executing: {cr.command}")
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                shlex.split(cr.command), shell=False, capture_output=True,
                text=True, timeout=120,
            )
            cr.return_code = result.returncode
            cr.stdout = result.stdout
            cr.stderr = result.stderr
            cr.executed = True
        except subprocess.TimeoutExpired:
            cr.error = "Command timed out (120s)"
            cr.return_code = -1
        except Exception as e:
            cr.error = str(e)
            cr.return_code = -1
        cr.elapsed_ms = int((time.monotonic() - t0) * 1000)

    @staticmethod
    def _detect_type(cmd: str) -> CommandType:
        if cmd.startswith("adb"):
            return CommandType.ADB
        elif cmd.startswith("ssh"):
            return CommandType.SSH
        elif cmd.startswith("scp"):
            return CommandType.SCP
        elif cmd.startswith("curl") or cmd.startswith("http"):
            return CommandType.HTTP
        elif any(cmd.startswith(s) for s in ("hackrf", "SoapySDR", "SYLION_BTS", "bash sdr/")):
            return CommandType.SDR
        return CommandType.LOCAL

    @staticmethod
    def _assess_risk(commands: list[CommandResult]) -> str:
        """Generate risk assessment for a set of commands."""
        risks = []
        has_device = any(c.command_type in (CommandType.ADB, CommandType.SSH) for c in commands)
        has_deploy = any("push" in c.command or "scp" in c.command for c in commands)
        has_reboot = any("reboot" in c.command or "sysupgrade" in c.command for c in commands)
        has_rf = any(c.command_type == CommandType.SDR for c in commands)

        if has_reboot:
            risks.append("⚠️  REBOOT/UPGRADE — urządzenie może być niedostępne po wykonaniu")
        if has_deploy:
            risks.append("📦 DEPLOY — wgrywanie nowych plików na urządzenie")
        if has_device:
            risks.append("📱 DEVICE ACCESS — bezpośredni dostęp do urządzenia fizycznego")
        if has_rf:
            risks.append("📡 SDR — operacje na sprzęcie radiowym")
        if not risks:
            risks.append("ℹ️  Niskie ryzyko — operacje tylko do odczytu")

        return "\n".join(risks)

    def save_log(self, path: Path):
        """Save execution log."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "execution_log": [
                {
                    "command": cr.command,
                    "type": cr.command_type.value,
                    "whitelisted": cr.whitelisted,
                    "gate_level": cr.gate_level.value,
                    "description": cr.description,
                    "approved": cr.approved,
                    "executed": cr.executed,
                    "return_code": cr.return_code,
                    "stdout_length": len(cr.stdout),
                    "stderr_length": len(cr.stderr),
                    "elapsed_ms": cr.elapsed_ms,
                    "error": cr.error,
                }
                for cr in self.execution_log
            ]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# PART 3: SUPERVISOR AGENT — oversees all agents
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ChecklistItem:
    """Single item in the supervisor's checklist."""
    id: str
    stage: str
    description: str
    status: str = "pending"       # pending, in_progress, completed, failed, blocked
    assigned_agent: str = ""
    gate_required: bool = False
    gate_decision: str = ""
    depends_on: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


class SupervisorAgent:
    """The all-seeing eye of the pipeline.
    
    Responsibilities:
    1. Watches all agents — status, progress, errors
    2. Maintains a CHECKLIST of what needs to be done
    3. After each stage completion, creates a SUMMARY + updated plan
    4. Enforces HUMAN GATE for all critical decisions
    5. Ensures LLM never executes raw commands — only Safe Runner
    6. Tracks the full audit trail
    
    The Supervisor is the ONLY agent that can:
    - Create and modify the master checklist
    - Trigger Human Gate requests
    - Invoke the Deterministic Runner
    - Make GO/NO-GO decisions (with human approval)
    """

    CHECKLIST_PATH = Path("results/supervisor_checklist.json")
    SUMMARY_PATH = Path("results/supervisor_summaries.json")

    def __init__(self, gate: HumanGate, runner: DeterministicRunner):
        self.gate = gate
        self.runner = runner
        self.checklist: list[ChecklistItem] = []
        self.summaries: list[dict] = []
        self.stage_results: dict[str, dict] = {}

    # --- Checklist Management ---

    def create_checklist(self, items: list[dict]) -> list[ChecklistItem]:
        """Create the master checklist from LLM-generated plan.
        
        The LLM proposes the checklist, but it goes through Human Gate
        before becoming the active plan.
        """
        proposed = []
        for item in items:
            ci = ChecklistItem(
                id=f"check-{uuid.uuid4().hex[:6]}",
                stage=item.get("stage", ""),
                description=item.get("description", ""),
                assigned_agent=item.get("agent", ""),
                gate_required=item.get("gate_required", False),
                depends_on=item.get("depends_on", []),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            proposed.append(ci)

        # Human Gate for the checklist itself
        gate_req = GateRequest(
            id=f"gate-checklist-{uuid.uuid4().hex[:6]}",
            agent_name="supervisor",
            stage="planning",
            level=GateLevel.REQUIRED,
            title="Zatwierdzenie planu pipeline'u",
            description="LLM wygenerował plan działania. Przejrzyj i zatwierdź.",
            action_plan=[
                {"description": f"[{ci.stage}] {ci.description} "
                               f"({'🔒 GATE' if ci.gate_required else ''})",
                 "status": "pending"}
                for ci in proposed
            ],
            risk_assessment="Plan pipeline'u — definiuje co będzie wykonywane",
            proposed_commands=[],
        )

        result = self.gate.request_approval(gate_req)
        
        if result.decision == GateDecision.APPROVED:
            self.checklist = proposed
            self._save_checklist()
            return proposed
        elif result.decision == GateDecision.MODIFIED and result.modified_plan:
            # Rebuild checklist from modified plan
            modified_items = []
            for step in result.modified_plan:
                ci = ChecklistItem(
                    id=f"check-{uuid.uuid4().hex[:6]}",
                    stage="modified",
                    description=step.get("description", str(step)),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                modified_items.append(ci)
            self.checklist = modified_items
            self._save_checklist()
            return modified_items
        else:
            log.warning("Checklist rejected by human — pipeline cannot proceed")
            return []

    def update_item(self, item_id: str, status: str, notes: str = ""):
        """Update a checklist item's status."""
        for item in self.checklist:
            if item.id == item_id:
                item.status = status
                if notes:
                    item.notes = notes
                item.updated_at = datetime.now(timezone.utc).isoformat()
                break
        self._save_checklist()

    def get_pending_items(self) -> list[ChecklistItem]:
        """Get items that are ready to be executed."""
        pending = []
        completed_ids = {i.id for i in self.checklist if i.status == "completed"}
        for item in self.checklist:
            if item.status == "pending":
                # Check dependencies
                deps_met = all(d in completed_ids for d in item.depends_on)
                if deps_met:
                    pending.append(item)
        return pending

    def get_blocked_items(self) -> list[ChecklistItem]:
        """Get items blocked by unmet dependencies."""
        completed_ids = {i.id for i in self.checklist if i.status == "completed"}
        blocked = []
        for item in self.checklist:
            if item.status == "pending" and item.depends_on:
                if not all(d in completed_ids for d in item.depends_on):
                    blocked.append(item)
        return blocked

    # --- Stage Summaries ---

    def create_stage_summary(self, stage: str, results: dict) -> dict:
        """Create a summary after each stage and update the plan.
        
        This goes through Human Gate so the administrator
        sees what happened and what's planned next.
        """
        completed = sum(1 for i in self.checklist
                       if i.stage == stage and i.status == "completed")
        failed = sum(1 for i in self.checklist
                    if i.stage == stage and i.status == "failed")
        total = sum(1 for i in self.checklist if i.stage == stage)
        pending_all = self.get_pending_items()

        summary = {
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "checklist_status": {
                "stage_completed": completed,
                "stage_failed": failed,
                "stage_total": total,
                "pipeline_pending": len(pending_all),
                "pipeline_blocked": len(self.get_blocked_items()),
            },
            "next_steps": [
                {"description": i.description, "agent": i.assigned_agent,
                 "gate": i.gate_required}
                for i in pending_all[:10]
            ],
        }

        # Human Gate for stage summary
        gate_req = GateRequest(
            id=f"gate-summary-{stage}-{uuid.uuid4().hex[:6]}",
            agent_name="supervisor",
            stage=stage,
            level=GateLevel.REQUIRED,
            title=f"Podsumowanie Stage {stage}",
            description=(
                f"Stage {stage} zakończony.\n"
                f"Ukończone: {completed}/{total}, Błędy: {failed}\n"
                f"Pozostało do zrobienia: {len(pending_all)} zadań"
            ),
            action_plan=[
                {"description": f"NEXT: {s['description']} "
                               f"[{s['agent']}] "
                               f"{'🔒 GATE' if s['gate'] else ''}",
                 "status": "pending"}
                for s in summary["next_steps"]
            ],
            risk_assessment=(
                "Kontynuacja pipeline'u — sprawdź wyniki i zdecyduj "
                "czy idziemy dalej"
            ),
            proposed_commands=[],
        )

        gate_result = self.gate.request_approval(gate_req)
        summary["human_decision"] = gate_result.decision.value if gate_result.decision else "pending"
        summary["human_notes"] = gate_result.human_notes

        self.summaries.append(summary)
        self._save_summaries()

        return summary

    # --- Safe Command Execution ---

    def execute_commands(self, commands: list[str], agent_name: str,
                        stage: str, context: str = "") -> list[CommandResult]:
        """Execute commands through the Deterministic Runner.
        
        THIS is the only way agents can execute commands.
        Direct shell access is NEVER available to LLMs.
        """
        return self.runner.execute(commands, agent_name, stage, context)

    # --- Checklist Display ---

    def print_checklist(self):
        """Display the current checklist in the terminal."""
        status_icons = {
            "pending":     f"{C.DIM}○{C.RESET}",
            "in_progress": f"{C.YELLOW}▶{C.RESET}",
            "completed":   f"{C.GREEN}✓{C.RESET}",
            "failed":      f"{C.RED}✗{C.RESET}",
            "blocked":     f"{C.MAGENTA}⊘{C.RESET}",
        }

        print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
        print(f"  {C.BOLD}SUPERVISOR CHECKLIST{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

        current_stage = ""
        for item in self.checklist:
            if item.stage != current_stage:
                current_stage = item.stage
                print(f"  {C.BOLD}{C.BLUE}── {current_stage} ──{C.RESET}")
            
            icon = status_icons.get(item.status, "?")
            gate = f" {C.YELLOW}🔒{C.RESET}" if item.gate_required else ""
            agent = f" {C.DIM}[{item.assigned_agent}]{C.RESET}" if item.assigned_agent else ""
            
            print(f"    {icon} {item.description}{gate}{agent}")
            if item.notes:
                print(f"      {C.DIM}↳ {item.notes}{C.RESET}")

        # Stats
        total = len(self.checklist)
        done = sum(1 for i in self.checklist if i.status == "completed")
        failed = sum(1 for i in self.checklist if i.status == "failed")
        pending = sum(1 for i in self.checklist if i.status == "pending")
        
        print(f"\n  {C.GREEN}✓ {done}{C.RESET} ukończonych  "
              f"{C.RED}✗ {failed}{C.RESET} błędów  "
              f"{C.DIM}○ {pending}{C.RESET} oczekujących  "
              f"{C.BOLD}Total: {total}{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

    # --- Orchestrator Integration (called by orchestrator.py) ---

    @property
    def checklist_path(self) -> Path:
        return self.CHECKLIST_PATH

    def on_agent_start(self, agent_id: str, stage: str, task: str):
        """Record that an agent has started executing."""
        log.info(f"  Supervisor: agent '{agent_id}' starting in stage '{stage}'")
        for item in self.checklist:
            if item.assigned_agent == agent_id or item.description.startswith(stage):
                if item.status == "pending":
                    item.status = "in_progress"
                    item.updated_at = datetime.now(timezone.utc).isoformat()
                    break
        self.stage_results.setdefault(stage, {})[agent_id] = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    def on_agent_complete(self, agent_id: str, *,
                          status: str = "completed",
                          elapsed: float = 0.0,
                          cost: float = 0.0,
                          error: str = ""):
        """Record agent completion (success or failure)."""
        log.info(f"  Supervisor: agent '{agent_id}' → {status} ({elapsed:.0f}s, ${cost:.4f})")
        for item in self.checklist:
            if item.assigned_agent == agent_id and item.status == "in_progress":
                item.status = status
                item.notes = error or f"elapsed={elapsed:.0f}s, cost=${cost:.4f}"
                item.updated_at = datetime.now(timezone.utc).isoformat()
                break
        if agent_id in self.stage_results.get("", {}):
            pass  # stage unknown
        for stage_data in self.stage_results.values():
            if agent_id in stage_data:
                stage_data[agent_id].update({
                    "status": status,
                    "elapsed": elapsed,
                    "cost": cost,
                    "error": error,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
        self._save_checklist()

    def on_agent_rejected(self, agent_id: str, reason: str):
        """Record that an agent was rejected by Human Gate."""
        log.warning(f"  Supervisor: agent '{agent_id}' REJECTED — {reason}")
        for item in self.checklist:
            if item.assigned_agent == agent_id and item.status in ("pending", "in_progress"):
                item.status = "blocked"
                item.gate_decision = "rejected"
                item.notes = reason
                item.updated_at = datetime.now(timezone.utc).isoformat()
                break
        self._save_checklist()

    def on_failure_decision(self, agent_id: str, error: str,
                            elapsed: float) -> str:
        """Decide what to do when an agent fails: 'retry' or 'escalate'.
        
        Simple heuristic: if agent ran less than 10s, likely a config error
        → escalate. Otherwise retry once.
        """
        key = f"{agent_id}_retries"
        retries = self.stage_results.get("_meta", {}).get(key, 0)
        self.stage_results.setdefault("_meta", {})[key] = retries + 1

        if retries >= 1 or elapsed < 10:
            return "escalate"
        return "retry"

    def generate_checklist(self, active_stages: list, mgr) -> list[ChecklistItem]:
        """Generate a checklist from active stages and agent manager."""
        items = []
        for stage_num in active_stages:
            stage_agents = mgr.get_stage_agents(stage_num)
            for ag in stage_agents:
                items.append({
                    "stage": str(stage_num),
                    "description": f"Run {ag.name} ({ag.role})",
                    "agent": ag.name,
                    "gate_required": stage_num in (5, 6, 8, 8.5),
                })
        return self.create_checklist(items)

    def on_stage_start(self, stage_num: float, stage_name: str):
        """Notify that a pipeline stage is starting."""
        log.info(f"  Supervisor: Stage {stage_num} ({stage_name}) STARTED")
        for item in self.checklist:
            if item.stage == str(stage_num) and item.status == "pending":
                item.status = "in_progress"
                item.updated_at = datetime.now(timezone.utc).isoformat()

    def on_stage_complete(self, stage_num: float, stage_name: str):
        """Notify that a pipeline stage has completed."""
        log.info(f"  Supervisor: Stage {stage_num} ({stage_name}) COMPLETED")
        for item in self.checklist:
            if item.stage == str(stage_num) and item.status == "in_progress":
                item.status = "completed"
                item.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_checklist()

    def on_stage_skipped(self, stage_num: float, stage_name: str):
        """Notify that a stage was skipped."""
        log.info(f"  Supervisor: Stage {stage_num} ({stage_name}) SKIPPED")
        for item in self.checklist:
            if item.stage == str(stage_num):
                item.status = "blocked"
                item.notes = "Stage skipped — agents disabled"
                item.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_checklist()

    def get_remaining_tasks(self) -> list[ChecklistItem]:
        """Get tasks that are not yet completed."""
        return [i for i in self.checklist if i.status in ("pending", "in_progress")]

    def on_pipeline_error(self, error: str):
        """Handle pipeline-level error."""
        log.error(f"  Supervisor: PIPELINE ERROR — {error}")
        summary = {
            "stage": "PIPELINE_ERROR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": {"error": error},
            "checklist_status": {
                "pending": len(self.get_remaining_tasks()),
            },
        }
        self.summaries.append(summary)
        self._save_summaries()
        self._save_checklist()

    def on_pipeline_complete(self, *, elapsed: float, stats: dict,
                             results_dir: Path):
        """Handle pipeline completion."""
        log.info("  Supervisor: PIPELINE COMPLETED")
        summary = {
            "stage": "PIPELINE_COMPLETE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": {
                "elapsed": elapsed,
                "stats": stats,
                "results_dir": str(results_dir),
            },
        }
        self.summaries.append(summary)
        self._save_summaries()
        self._save_checklist()

    def save_checklist(self):
        """Public method to persist checklist."""
        self._save_checklist()

    # --- Persistence ---

    def _save_checklist(self):
        self.CHECKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "checklist": [
                {
                    "id": i.id, "stage": i.stage,
                    "description": i.description, "status": i.status,
                    "assigned_agent": i.assigned_agent,
                    "gate_required": i.gate_required,
                    "gate_decision": i.gate_decision,
                    "depends_on": i.depends_on,
                    "notes": i.notes,
                    "created_at": i.created_at,
                    "updated_at": i.updated_at,
                }
                for i in self.checklist
            ]
        }
        with open(self.CHECKLIST_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_summaries(self):
        self.SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.SUMMARY_PATH, "w") as f:
            json.dump({"summaries": self.summaries}, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# Factory — create the full safety stack
# ═══════════════════════════════════════════════════════════════════════════

def create_safety_stack(dry_run: bool = False,
                        log_path: Path | None = None) -> tuple[SupervisorAgent, HumanGate, DeterministicRunner]:
    """Create the complete Supervisor + Human Gate + Runner stack.
    
    Usage:
        supervisor, gate, runner = create_safety_stack()
        
        # LLM generates plan
        plan = llm_generate_plan(...)
        
        # Supervisor creates checklist (goes through human gate)
        supervisor.create_checklist(plan)
        
        # Execute commands safely
        results = supervisor.execute_commands(
            commands=["adb devices", "adb shell getprop ro.build.version"],
            agent_name="pixel_deployer",
            stage="deploy",
        )
    """
    gate = HumanGate(log_path=log_path or Path("results/gate_log.json"))
    runner = DeterministicRunner(gate=gate, dry_run=dry_run)
    supervisor = SupervisorAgent(gate=gate, runner=runner)
    return supervisor, gate, runner
