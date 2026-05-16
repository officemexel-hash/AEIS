#!/usr/bin/env python3
"""
SYLION Agent Manager — panel zarządzania agentami

Ładuje konfigurację z agents.yaml, umożliwia włączanie/wyłączanie
agentów, stosowanie profili, monitoring statusu w runtime.

Użycie:
  python agent_manager.py status                    # Status wszystkich agentów
  python agent_manager.py enable <agent>            # Włącz agenta
  python agent_manager.py disable <agent>           # Wyłącz agenta
  python agent_manager.py toggle <agent>            # Przełącz agenta
  python agent_manager.py profile <nazwa>           # Zastosuj profil
  python agent_manager.py profiles                  # Lista profili
  python agent_manager.py groups                    # Pokaż grupy agentów
  python agent_manager.py set <agent> <klucz> <val> # Zmień parametr
  python agent_manager.py dashboard                 # Interaktywny panel
  python agent_manager.py export                    # Eksport aktualnej konfiguracji
  python agent_manager.py validate                  # Walidacja konfiguracji
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "agents.yaml"
STATE_PATH = Path(__file__).parent / "results" / "agent_state.json"

STAGE_NAMES = {
    0: "META",
    1: "PREPARE",
    2: "AUDIT",
    3: "CROSS-VERIFY",
    4: "MERGE",
    5: "PATCH",
    6: "DEPLOY",
    6.5: "STREAMING",
    7: "TEST",
    7.5: "STREAM-TEST",
    8: "SECURITY",
    8.5: "SDR",
    9: "REPORT",
}

# ANSI color codes
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
    BG_BLUE = "\033[44m"


# ---------------------------------------------------------------------------
# Agent status enum
# ---------------------------------------------------------------------------

class AgentStatus(str, Enum):
    IDLE       = "idle"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    SKIPPED    = "skipped"
    DISABLED   = "disabled"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    enabled: bool = True
    stage: float = 0
    role: str = ""
    model: str = "claude"
    priority: int = 5
    description: str = ""
    group: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    # --- Agent metadata (Single Source of Truth — §9.5) ---
    book_refs: list[str] = field(default_factory=list)          # Księga requirement IDs this agent references
    allowed_actions: list[str] = field(default_factory=list)    # Whitelisted Safe Runner scenarios
    forbidden_actions: list[str] = field(default_factory=list)  # Explicitly blocked actions
    requires_human_gate: bool = True                            # Requires Human Gate before execution
    tier_scope: list[str] = field(default_factory=list)         # SYLION tiers: G1, G2, VPS, etc.
    security_impact: str = "medium"                             # critical / high / medium / low
    produces_artifacts: list[str] = field(default_factory=list) # Expected output files
    acceptance_tests: list[str] = field(default_factory=list)   # Criteria for success
    declared_files: list[str] | None = None                    # Files agent may modify (anti-hallucination)
    fallback_model: str | None = None                          # Fallback model on primary failure
    learning: bool = False                                     # Remembers results between sessions
    multi_verify: dict[str, Any] | None = None                 # Multi-model verification config
    online_search: dict[str, Any] | None = None                # Online search config

    # Runtime state (not saved to YAML)
    status: AgentStatus = AgentStatus.IDLE
    started_at: str | None = None
    completed_at: str | None = None
    elapsed_seconds: float = 0
    cost: float = 0
    error: str | None = None
    result_path: str | None = None


@dataclass
class PipelineProfile:
    """Predefined configuration profile."""
    name: str
    description: str
    overrides: dict[str, Any]


# ---------------------------------------------------------------------------
# AgentManager — core logic
# ---------------------------------------------------------------------------

class AgentManager:
    """Manages agent configuration, lifecycle, and monitoring."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.agents: dict[str, AgentConfig] = {}
        self.profiles: dict[str, PipelineProfile] = {}
        self.global_config: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._callbacks: list = []
        self.load()

    # --- Loading / Saving ---

    def load(self):
        """Load agent configuration from YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self.global_config = raw.get("global", {})

        # Load agents
        self.agents = {}
        for name, cfg in raw.get("agents", {}).items():
            self.agents[name] = AgentConfig(
                name=name,
                enabled=cfg.get("enabled", True),
                stage=cfg.get("stage", 0),
                role=cfg.get("role", ""),
                model=cfg.get("model", "claude") or "claude",
                priority=cfg.get("priority", 5),
                description=cfg.get("description", ""),
                group=cfg.get("group"),
                params=cfg.get("params", {}),
                # --- Metadata (§9.5 Single Source of Truth) ---
                book_refs=cfg.get("book_refs", []),
                allowed_actions=cfg.get("allowed_actions", []),
                forbidden_actions=cfg.get("forbidden_actions", []),
                requires_human_gate=cfg.get("requires_human_gate", True),
                tier_scope=cfg.get("tier_scope", []),
                security_impact=cfg.get("security_impact", "medium"),
                produces_artifacts=cfg.get("produces_artifacts", []),
                acceptance_tests=cfg.get("acceptance_tests", []),
                declared_files=cfg.get("declared_files"),
                fallback_model=cfg.get("fallback_model"),
                learning=cfg.get("learning", False),
                multi_verify=cfg.get("multi_verify"),
                online_search=cfg.get("online_search"),
            )

        # Load profiles
        self.profiles = {}
        for name, prof in raw.get("profiles", {}).items():
            self.profiles[name] = PipelineProfile(
                name=name,
                description=prof.get("description", ""),
                overrides=prof.get("overrides", {}),
            )

        # Restore runtime state if available
        self._load_state()

    def save(self):
        """Save current configuration back to YAML."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        # Update agent enabled/model/params
        for name, agent in self.agents.items():
            if name in raw.get("agents", {}):
                raw["agents"][name]["enabled"] = agent.enabled
                raw["agents"][name]["model"] = agent.model
                raw["agents"][name]["params"] = agent.params

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _load_state(self):
        """Load runtime state from JSON (if pipeline is running)."""
        if not STATE_PATH.exists():
            return
        try:
            with open(STATE_PATH, "r") as f:
                state = json.load(f)
            for name, s in state.get("agents", {}).items():
                if name in self.agents:
                    self.agents[name].status = AgentStatus(s.get("status", "idle"))
                    self.agents[name].started_at = s.get("started_at")
                    self.agents[name].completed_at = s.get("completed_at")
                    # PIPELINE-003 fix: coerce to float, reject non-numeric
                    # (e.g. legacy state files where elapsed_seconds='done')
                    def _num(v, default=0.0):
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            return default
                    self.agents[name].elapsed_seconds = _num(s.get("elapsed_seconds", 0))
                    self.agents[name].cost = _num(s.get("cost", 0))
                    self.agents[name].error = s.get("error")
                    self.agents[name].result_path = s.get("result_path")
        except (json.JSONDecodeError, KeyError) as exc:
            # v5.8.8 (Fix 2): surface corrupted state instead of silent pass.
            # Root cause: silent pass hid state file corruption from operator.
            print(
                f"[agent_manager] WARNING: uszkodzony stan w {STATE_PATH}: {exc} — start z czystą listą",
                file=sys.stderr,
            )

    def save_state(self):
        """Save runtime state to JSON (atomically, under self._lock).

        v5.8.8 (Fix 3): atomic tmp+rename under self._lock with fsync.
        Root cause: concurrent writers could corrupt JSON mid-write.
        Callers already release self._lock before calling save_state()
        (see mark_running/mark_completed/mark_failed/mark_skipped),
        so re-acquiring here is safe (no reentrant deadlock).
        """
        with self._lock:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            state = {"timestamp": datetime.now(timezone.utc).isoformat(), "agents": {}}
            for name, agent in self.agents.items():
                state["agents"][name] = {
                    "status": agent.status.value,
                    "enabled": agent.enabled,
                    "started_at": agent.started_at,
                    "completed_at": agent.completed_at,
                    "elapsed_seconds": agent.elapsed_seconds,
                    "cost": agent.cost,
                    "error": agent.error,
                    "result_path": agent.result_path,
                }
            tmp_path = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, STATE_PATH)

    # --- Agent Control ---

    def enable(self, name: str) -> bool:
        """Enable an agent."""
        if name not in self.agents:
            return False
        with self._lock:
            self.agents[name].enabled = True
            self.agents[name].status = AgentStatus.IDLE
        self.save()
        return True

    def disable(self, name: str) -> bool:
        """Disable an agent."""
        if name not in self.agents:
            return False
        with self._lock:
            self.agents[name].enabled = False
            self.agents[name].status = AgentStatus.DISABLED
        self.save()
        return True

    def toggle(self, name: str) -> bool | None:
        """Toggle an agent's enabled state. Returns new state."""
        if name not in self.agents:
            return None
        new_state = not self.agents[name].enabled
        if new_state:
            self.enable(name)
        else:
            self.disable(name)
        return new_state

    def enable_group(self, group: str):
        """Enable all agents in a group."""
        for agent in self.agents.values():
            if agent.group == group:
                self.enable(agent.name)

    def disable_group(self, group: str):
        """Disable all agents in a group."""
        for agent in self.agents.values():
            if agent.group == group:
                self.disable(agent.name)

    def enable_stage(self, stage: float):
        """Enable all agents in a stage."""
        for agent in self.agents.values():
            if agent.stage == stage:
                self.enable(agent.name)

    def disable_stage(self, stage: float):
        """Disable all agents in a stage."""
        for agent in self.agents.values():
            if agent.stage == stage:
                self.disable(agent.name)

    def set_model(self, name: str, model: str) -> bool:
        """Change an agent's model."""
        if name not in self.agents:
            return False
        self.agents[name].model = model
        self.save()
        return True

    def set_param(self, name: str, key: str, value: Any) -> bool:
        """Set a parameter for an agent."""
        if name not in self.agents:
            return False
        self.agents[name].params[key] = value
        self.save()
        return True

    # --- Profiles ---

    def apply_profile(self, profile_name: str) -> bool:
        """Apply a predefined profile."""
        if profile_name not in self.profiles:
            return False

        profile = self.profiles[profile_name]
        for key, value in profile.overrides.items():
            parts = key.split(".")
            if len(parts) == 2:
                agent_name, attr = parts
                if agent_name in self.agents and attr == "enabled":
                    if value:
                        self.enable(agent_name)
                    else:
                        self.disable(agent_name)
                elif agent_name == "global":
                    # Handle global overrides
                    self._set_nested(self.global_config, parts[1:] + [attr], value)
            elif len(parts) == 3 and parts[0] == "global":
                self._set_nested(self.global_config, parts[1:], value)
        return True

    @staticmethod
    def _set_nested(d: dict, keys: list[str], value: Any):
        """Set a nested dict value by key path."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    # --- Runtime Status ---

    def mark_running(self, name: str):
        """Mark agent as running."""
        if name in self.agents:
            with self._lock:
                self.agents[name].status = AgentStatus.RUNNING
                self.agents[name].started_at = datetime.now(timezone.utc).isoformat()
            self.save_state()

    def mark_completed(self, name: str, elapsed: float = 0, cost: float = 0,
                       result_path: str | None = None):
        """Mark agent as completed."""
        if name in self.agents:
            with self._lock:
                self.agents[name].status = AgentStatus.COMPLETED
                self.agents[name].completed_at = datetime.now(timezone.utc).isoformat()
                self.agents[name].elapsed_seconds = elapsed
                self.agents[name].cost = cost
                self.agents[name].result_path = result_path
            self.save_state()

    def mark_failed(self, name: str, error: str):
        """Mark agent as failed."""
        if name in self.agents:
            with self._lock:
                self.agents[name].status = AgentStatus.FAILED
                self.agents[name].error = error
                self.agents[name].completed_at = datetime.now(timezone.utc).isoformat()
            self.save_state()

    def mark_skipped(self, name: str):
        """Mark agent as skipped."""
        if name in self.agents:
            with self._lock:
                self.agents[name].status = AgentStatus.SKIPPED
            self.save_state()

    # --- Queries ---

    def get_enabled_agents(self) -> list[AgentConfig]:
        """Get all enabled agents sorted by stage then priority."""
        return sorted(
            [a for a in self.agents.values() if a.enabled],
            key=lambda a: (a.stage, -a.priority),
        )

    def get_stage_agents(self, stage: float) -> list[AgentConfig]:
        """Get enabled agents for a specific stage."""
        return [a for a in self.get_enabled_agents() if a.stage == stage]

    def get_groups(self) -> dict[str, list[AgentConfig]]:
        """Get agents organized by group."""
        groups: dict[str, list[AgentConfig]] = {}
        for agent in self.agents.values():
            if agent.group:
                groups.setdefault(agent.group, []).append(agent)
        return groups

    def get_active_stages(self) -> list[float]:
        """Get stages that have at least one enabled agent."""
        stages = set()
        for agent in self.agents.values():
            if agent.enabled:
                stages.add(agent.stage)
        return sorted(stages)

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        total = len(self.agents)
        enabled = sum(1 for a in self.agents.values() if a.enabled)
        running = sum(1 for a in self.agents.values() if a.status == AgentStatus.RUNNING)
        completed = sum(1 for a in self.agents.values() if a.status == AgentStatus.COMPLETED)
        failed = sum(1 for a in self.agents.values() if a.status == AgentStatus.FAILED)
        total_cost = sum(a.cost for a in self.agents.values())
        total_time = sum(a.elapsed_seconds for a in self.agents.values())
        return {
            "total": total, "enabled": enabled, "disabled": total - enabled,
            "running": running, "completed": completed, "failed": failed,
            "total_cost": total_cost, "total_time": total_time,
        }

    # --- Validation ---

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of warnings/errors."""
        issues = []
        enabled = self.get_enabled_agents()
        enabled_names = {a.name for a in enabled}

        # Check minimum agents for pipeline
        if not any(a.stage == 1 for a in enabled):
            issues.append("ERROR: Brak włączonych agentów w Stage 1 (PREPARE)")

        if not any(a.stage == 2 for a in enabled):
            issues.append("ERROR: Brak włączonych audytorów w Stage 2 (AUDIT)")

        # Check auditor count vs consensus threshold
        auditor_count = sum(1 for a in enabled if a.stage == 2)
        threshold = self.global_config.get("consensus_threshold", 3)
        if auditor_count < threshold:
            issues.append(
                f"WARN: Tylko {auditor_count} audytorów włączonych, "
                f"próg konsensusu = {threshold} (nieosiągalny)"
            )

        # Check verifier parity with auditors
        verifier_count = sum(1 for a in enabled if a.stage == 3)
        if verifier_count > 0 and verifier_count != auditor_count:
            issues.append(
                f"WARN: {verifier_count} weryfikatorów vs {auditor_count} audytorów "
                f"(powinny być równe)"
            )

        # SDR checks
        sdr_agents = [a for a in self.agents.values() if a.group == "sdr"]
        sdr_enabled = [a for a in sdr_agents if a.enabled]
        if sdr_enabled:
            rf_red = self.agents.get("rf_red_team")
            if rf_red and rf_red.enabled:
                bts_mode = rf_red.params.get("bts_mode", "zmq")
                if bts_mode == "rf":
                    faraday = rf_red.params.get("faraday_required", True)
                    if faraday:
                        issues.append(
                            "WARN: RF Red Team w trybie RF — upewnij się, "
                            "że klatka Faradaya jest gotowa"
                        )

        # Check reporter
        if "reporter" not in enabled_names:
            issues.append("WARN: Reporter wyłączony — nie wygeneruje raportu końcowego")

        # Check merger
        if "merger" not in enabled_names and auditor_count > 0:
            issues.append("ERROR: Merger wyłączony ale audytorzy włączeni — brak scalania")

        # --- Metadata validation (§9.5 Single Source of Truth) ---
        issues.extend(self.validate_metadata())

        return issues

    def validate_metadata(self) -> list[str]:
        """Validate agent metadata completeness and consistency (§9.5).

        Checks:
          - security_impact is valid enum value
          - high/critical security agents have requires_human_gate
          - allowed_actions and forbidden_actions don't overlap
          - streaming agents (Pion D) have book_refs
          - agents with produces_artifacts have acceptance_tests
        """
        issues: list[str] = []
        valid_impacts = {"critical", "high", "medium", "low"}

        for name, agent in self.agents.items():
            if not agent.enabled:
                continue

            # security_impact must be valid
            if agent.security_impact not in valid_impacts:
                issues.append(
                    f"ERROR: {name}.security_impact='{agent.security_impact}' "
                    f"(— dozwolone: {valid_impacts})"
                )

            # High/critical impact agents should require Human Gate
            if agent.security_impact in ("critical", "high") and not agent.requires_human_gate:
                # book_guardian/budget_guard/file_verifier are exempt (auto-escalate)
                # Read-only agents (auditors, verifiers, monitors) are exempt
                read_only_roles = {"Audytor", "Weryfikator krzyżowy", "Blue Team", "RF Blue Team", "Analiza Księgi"}
                if name not in ("book_guardian", "budget_guard", "file_verifier") \
                   and agent.role not in read_only_roles:
                    issues.append(
                        f"WARN: {name} ma security_impact='{agent.security_impact}' "
                        f"ale requires_human_gate=False"
                    )

            # allowed_actions and forbidden_actions must not overlap
            if agent.allowed_actions and agent.forbidden_actions:
                overlap = set(agent.allowed_actions) & set(agent.forbidden_actions)
                if overlap:
                    issues.append(
                        f"ERROR: {name} has overlapping allowed/forbidden actions: "
                        f"{overlap}"
                    )

            # Agents with produces_artifacts should have acceptance_tests
            if agent.produces_artifacts and not agent.acceptance_tests:
                issues.append(
                    f"WARN: {name} produces artifacts but has no acceptance_tests"
                )

            # Streaming agents must have book_refs
            if agent.group == "streaming" and not agent.book_refs:
                issues.append(
                    f"WARN: {name} (Pion D streaming) has no book_refs — "
                    f"should reference Księga requirements"
                )

        return issues


# ---------------------------------------------------------------------------
# CLI Dashboard — pretty printed status
# ---------------------------------------------------------------------------

def status_icon(status: AgentStatus) -> str:
    icons = {
        AgentStatus.IDLE:      f"{C.DIM}○{C.RESET}",
        AgentStatus.RUNNING:   f"{C.YELLOW}▶{C.RESET}",
        AgentStatus.COMPLETED: f"{C.GREEN}✓{C.RESET}",
        AgentStatus.FAILED:    f"{C.RED}✗{C.RESET}",
        AgentStatus.SKIPPED:   f"{C.DIM}⊘{C.RESET}",
        AgentStatus.DISABLED:  f"{C.DIM}⊗{C.RESET}",
    }
    return icons.get(status, "?")


def enabled_badge(enabled: bool) -> str:
    if enabled:
        return f"{C.GREEN}ON {C.RESET}"
    return f"{C.RED}OFF{C.RESET}"


def print_status(mgr: AgentManager):
    """Print formatted status of all agents."""
    stats = mgr.get_stats()

    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║{C.RESET}  {C.BOLD}SYLION AGENT MANAGER — {stats['enabled']}/{stats['total']} agentów aktywnych{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════════════════╝{C.RESET}\n")

    # Global stats
    print(f"  {C.GREEN}●{C.RESET} Włączonych: {stats['enabled']}  "
          f"  {C.RED}●{C.RESET} Wyłączonych: {stats['disabled']}  "
          f"  {C.YELLOW}▶{C.RESET} Działających: {stats['running']}  "
          f"  {C.GREEN}✓{C.RESET} Zakończonych: {stats['completed']}  "
          f"  {C.RED}✗{C.RESET} Błędów: {stats['failed']}")

    if stats['total_cost'] > 0:
        print(f"  💰 Koszt: ${stats['total_cost']:.4f}  "
              f"  ⏱ Czas: {stats['total_time']:.0f}s")
    print()

    # Agents by stage
    for stage in sorted(STAGE_NAMES.keys()):
        stage_agents = [a for a in mgr.agents.values() if a.stage == stage]
        if not stage_agents:
            continue

        stage_label = STAGE_NAMES.get(stage, f"STAGE {stage}")
        stage_num = str(stage) if stage == int(stage) else f"{stage}"
        enabled_count = sum(1 for a in stage_agents if a.enabled)

        print(f"  {C.BOLD}{C.BLUE}── STAGE {stage_num}: {stage_label} "
              f"({enabled_count}/{len(stage_agents)}) ──{C.RESET}")

        for agent in sorted(stage_agents, key=lambda a: (-a.priority, a.name)):
            icon = status_icon(agent.status if agent.enabled else AgentStatus.DISABLED)
            badge = enabled_badge(agent.enabled)
            model_tag = f"{C.MAGENTA}[{agent.model}]{C.RESET}"
            name_styled = f"{C.BOLD}{agent.name}{C.RESET}" if agent.enabled else f"{C.DIM}{agent.name}{C.RESET}"

            line = f"    {icon} {badge} {name_styled:<30s} {model_tag:<20s} {C.DIM}{agent.description}{C.RESET}"

            if agent.status == AgentStatus.RUNNING:
                line += f"  {C.YELLOW}⏱{C.RESET}"
            elif agent.status == AgentStatus.COMPLETED:
                line += f"  {C.DIM}{agent.elapsed_seconds:.0f}s{C.RESET}"
                if agent.cost > 0:
                    line += f" {C.DIM}${agent.cost:.4f}{C.RESET}"
            elif agent.status == AgentStatus.FAILED:
                line += f"  {C.RED}{agent.error or 'unknown error'}{C.RESET}"

            print(line)
        print()


def print_profiles(mgr: AgentManager):
    """Print available profiles."""
    print(f"\n{C.BOLD}{C.CYAN}Dostępne profile:{C.RESET}\n")
    for name, profile in mgr.profiles.items():
        changes = len(profile.overrides)
        print(f"  {C.BOLD}{C.GREEN}{name}{C.RESET}")
        print(f"    {profile.description}")
        print(f"    {C.DIM}({changes} zmian){C.RESET}")
        print()


def print_groups(mgr: AgentManager):
    """Print agent groups."""
    print(f"\n{C.BOLD}{C.CYAN}Grupy agentów:{C.RESET}\n")
    groups = mgr.get_groups()
    for group_name, agents in sorted(groups.items()):
        enabled = sum(1 for a in agents if a.enabled)
        print(f"  {C.BOLD}{group_name}{C.RESET} ({enabled}/{len(agents)} aktywnych)")
        for a in sorted(agents, key=lambda x: x.name):
            icon = "✓" if a.enabled else "✗"
            color = C.GREEN if a.enabled else C.RED
            print(f"    {color}{icon}{C.RESET} {a.name} [{a.model}]")
        print()


def print_validation(mgr: AgentManager):
    """Print validation results."""
    issues = mgr.validate()
    if not issues:
        print(f"\n  {C.GREEN}✓ Konfiguracja poprawna — brak problemów{C.RESET}\n")
    else:
        print(f"\n{C.BOLD}Wyniki walidacji:{C.RESET}\n")
        for issue in issues:
            if issue.startswith("ERROR"):
                print(f"  {C.RED}✗ {issue}{C.RESET}")
            elif issue.startswith("WARN"):
                print(f"  {C.YELLOW}⚠ {issue}{C.RESET}")
            else:
                print(f"  {C.DIM}ℹ {issue}{C.RESET}")
        print()


# ---------------------------------------------------------------------------
# Interactive Dashboard
# ---------------------------------------------------------------------------

def dashboard(mgr: AgentManager):
    """Interactive terminal dashboard."""
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print_status(mgr)

        print(f"{C.BOLD}Komendy:{C.RESET}")
        print(f"  {C.CYAN}e <agent>{C.RESET}  — włącz    "
              f"  {C.CYAN}d <agent>{C.RESET}  — wyłącz    "
              f"  {C.CYAN}t <agent>{C.RESET}  — toggle")
        print(f"  {C.CYAN}eg <group>{C.RESET} — włącz grupę  "
              f"  {C.CYAN}dg <group>{C.RESET} — wyłącz grupę  "
              f"  {C.CYAN}es <N>{C.RESET}    — włącz stage")
        print(f"  {C.CYAN}p <profil>{C.RESET} — zastosuj profil  "
              f"  {C.CYAN}v{C.RESET} — walidacja  "
              f"  {C.CYAN}r{C.RESET} — odśwież  "
              f"  {C.CYAN}q{C.RESET} — wyjście")
        print()

        try:
            cmd = input(f"{C.BOLD}> {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "q":
            break
        elif action == "r":
            mgr.load()
        elif action == "v":
            print_validation(mgr)
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")
        elif action == "e" and arg:
            if mgr.enable(arg):
                print(f"  {C.GREEN}✓ {arg} włączony{C.RESET}")
            else:
                print(f"  {C.RED}✗ Agent '{arg}' nie istnieje{C.RESET}")
            time.sleep(0.5)
        elif action == "d" and arg:
            if mgr.disable(arg):
                print(f"  {C.RED}✗ {arg} wyłączony{C.RESET}")
            else:
                print(f"  {C.RED}✗ Agent '{arg}' nie istnieje{C.RESET}")
            time.sleep(0.5)
        elif action == "t" and arg:
            result = mgr.toggle(arg)
            if result is not None:
                state = "włączony" if result else "wyłączony"
                print(f"  → {arg} {state}")
            else:
                print(f"  {C.RED}✗ Agent '{arg}' nie istnieje{C.RESET}")
            time.sleep(0.5)
        elif action == "eg" and arg:
            mgr.enable_group(arg)
            print(f"  {C.GREEN}✓ Grupa '{arg}' włączona{C.RESET}")
            time.sleep(0.5)
        elif action == "dg" and arg:
            mgr.disable_group(arg)
            print(f"  {C.RED}✗ Grupa '{arg}' wyłączona{C.RESET}")
            time.sleep(0.5)
        elif action == "es" and arg:
            try:
                mgr.enable_stage(float(arg))
                print(f"  {C.GREEN}✓ Stage {arg} włączony{C.RESET}")
            except ValueError:
                print(f"  {C.RED}✗ Nieprawidłowy numer stage{C.RESET}")
            time.sleep(0.5)
        elif action == "ds" and arg:
            try:
                mgr.disable_stage(float(arg))
                print(f"  {C.RED}✗ Stage {arg} wyłączony{C.RESET}")
            except ValueError:
                print(f"  {C.RED}✗ Nieprawidłowy numer stage{C.RESET}")
            time.sleep(0.5)
        elif action == "p" and arg:
            if mgr.apply_profile(arg):
                print(f"  {C.GREEN}✓ Profil '{arg}' zastosowany{C.RESET}")
            else:
                print(f"  {C.RED}✗ Profil '{arg}' nie istnieje{C.RESET}")
                print_profiles(mgr)
            time.sleep(1)
        else:
            print(f"  {C.DIM}Nieznana komenda: {cmd}{C.RESET}")
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SYLION Agent Manager — zarządzanie agentami pipeline'u",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python agent_manager.py status
  python agent_manager.py enable sdr_monitor
  python agent_manager.py disable auditor_deepseek
  python agent_manager.py toggle rf_red_team
  python agent_manager.py profile quick_audit
  python agent_manager.py set rf_red_team bts_mode rf
  python agent_manager.py dashboard
        """,
    )
    parser.add_argument("command", choices=[
        "status", "enable", "disable", "toggle",
        "profile", "profiles", "groups",
        "set", "dashboard", "export", "validate",
        "enable-group", "disable-group",
        "enable-stage", "disable-stage",
    ], help="Komenda do wykonania")
    parser.add_argument("args", nargs="*", help="Argumenty komendy")
    parser.add_argument("--config", "-c", type=Path, default=CONFIG_PATH,
                        help="Ścieżka do agents.yaml")

    args = parser.parse_args()
    mgr = AgentManager(args.config)

    if args.command == "status":
        print_status(mgr)

    elif args.command == "enable":
        if not args.args:
            print("Użycie: agent_manager.py enable <agent_name>")
            sys.exit(1)
        for name in args.args:
            if mgr.enable(name):
                print(f"  ✓ {name} włączony")
            else:
                print(f"  ✗ Agent '{name}' nie istnieje")

    elif args.command == "disable":
        if not args.args:
            print("Użycie: agent_manager.py disable <agent_name>")
            sys.exit(1)
        for name in args.args:
            if mgr.disable(name):
                print(f"  ✓ {name} wyłączony")
            else:
                print(f"  ✗ Agent '{name}' nie istnieje")

    elif args.command == "toggle":
        if not args.args:
            print("Użycie: agent_manager.py toggle <agent_name>")
            sys.exit(1)
        for name in args.args:
            result = mgr.toggle(name)
            if result is not None:
                state = "włączony" if result else "wyłączony"
                print(f"  → {name} {state}")
            else:
                print(f"  ✗ Agent '{name}' nie istnieje")

    elif args.command == "enable-group":
        if not args.args:
            print("Użycie: agent_manager.py enable-group <group>")
            sys.exit(1)
        mgr.enable_group(args.args[0])
        print(f"  ✓ Grupa '{args.args[0]}' włączona")

    elif args.command == "disable-group":
        if not args.args:
            print("Użycie: agent_manager.py disable-group <group>")
            sys.exit(1)
        mgr.disable_group(args.args[0])
        print(f"  ✓ Grupa '{args.args[0]}' wyłączona")

    elif args.command == "enable-stage":
        if not args.args:
            print("Użycie: agent_manager.py enable-stage <N>")
            sys.exit(1)
        mgr.enable_stage(float(args.args[0]))
        print(f"  ✓ Stage {args.args[0]} włączony")

    elif args.command == "disable-stage":
        if not args.args:
            print("Użycie: agent_manager.py disable-stage <N>")
            sys.exit(1)
        mgr.disable_stage(float(args.args[0]))
        print(f"  ✓ Stage {args.args[0]} wyłączony")

    elif args.command == "profile":
        if not args.args:
            print_profiles(mgr)
            sys.exit(0)
        if mgr.apply_profile(args.args[0]):
            print(f"  ✓ Profil '{args.args[0]}' zastosowany")
            print_status(mgr)
        else:
            print(f"  ✗ Profil '{args.args[0]}' nie istnieje")
            print_profiles(mgr)

    elif args.command == "profiles":
        print_profiles(mgr)

    elif args.command == "groups":
        print_groups(mgr)

    elif args.command == "set":
        if len(args.args) < 3:
            print("Użycie: agent_manager.py set <agent> <key> <value>")
            sys.exit(1)
        name, key, value = args.args[0], args.args[1], args.args[2]
        # Auto-convert types
        if value.lower() in ("true", "yes"):
            value = True
        elif value.lower() in ("false", "no"):
            value = False
        elif value.isdigit():
            value = int(value)
        elif value.replace(".", "", 1).replace("-", "", 1).isdigit():
            value = float(value)

        if mgr.set_param(name, key, value):
            print(f"  ✓ {name}.params.{key} = {value}")
        else:
            print(f"  ✗ Agent '{name}' nie istnieje")

    elif args.command == "export":
        config = {
            "global": mgr.global_config,
            "agents": {
                name: {
                    "enabled": a.enabled, "stage": a.stage, "role": a.role,
                    "model": a.model, "priority": a.priority,
                    "description": a.description, "group": a.group,
                    "params": a.params, "status": a.status.value,
                }
                for name, a in mgr.agents.items()
            },
        }
        print(json.dumps(config, indent=2, ensure_ascii=False))

    elif args.command == "validate":
        print_validation(mgr)

    elif args.command == "dashboard":
        dashboard(mgr)


if __name__ == "__main__":
    main()
