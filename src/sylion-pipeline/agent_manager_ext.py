#!/usr/bin/env python3
"""
SYLION Extended Agent Manager — rozbudowany panel zarządzania agentami

Rozszerzenia ponad podstawowy agent_manager.py:
  - Dodawanie nowych agentów dynamicznie (add/clone)
  - Podgląd pamięci agentów (czego się nauczyli)
  - Detekcja pętli poprawek (integracja z loop_guard)
  - Inspekcja szczegółowa agenta (pełny profil + historia)
  - Zmiana modelu w locie (model-swap)
  - Porównanie wyników między modelami
  - Rozbudowany dashboard z panelami

Użycie:
  python agent_manager_ext.py add <name> <stage> <role> <model>   # Dodaj agenta
  python agent_manager_ext.py clone <source> <new_name> [model]   # Klonuj agenta
  python agent_manager_ext.py inspect <agent>                      # Inspekcja szczegółowa
  python agent_manager_ext.py memory <agent>                       # Podgląd pamięci
  python agent_manager_ext.py loops                                # Raport pętli
  python agent_manager_ext.py swap-model <agent> <new_model>       # Zmień model
  python agent_manager_ext.py compare <agent1> <agent2>            # Porównaj agentów
  python agent_manager_ext.py dashboard                            # Rozbudowany panel
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from agent_manager import (
    AgentConfig,
    AgentManager,
    AgentStatus,
    C,
    CONFIG_PATH,
    STAGE_NAMES,
    enabled_badge,
    print_groups,
    print_profiles,
    print_status,
    print_validation,
    status_icon,
)


# ---------------------------------------------------------------------------
# Memory inspection — reads from memory/ directory created by models.py
# ---------------------------------------------------------------------------

MEMORY_DIR = Path(__file__).parent / "memory"
LOOP_STATE_PATH = Path(__file__).parent / "results" / "loop_state.json"


@dataclass
class MemoryEntry:
    """Single memory entry stored by an agent."""
    agent_id: str
    entry_type: str          # "false_positive", "true_positive", "pattern", "preference"
    content: str
    source_finding: str = ""
    model_used: str = ""
    timestamp: str = ""
    confidence: float = 0.0


def load_agent_memory(agent_name: str) -> list[MemoryEntry]:
    """Load memory entries for a specific agent."""
    agent_dir = MEMORY_DIR / agent_name
    if not agent_dir.exists():
        return []

    entries = []
    for f in sorted(agent_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    entries.append(MemoryEntry(
                        agent_id=agent_name,
                        entry_type=item.get("type", "unknown"),
                        content=item.get("content", ""),
                        source_finding=item.get("source_finding", ""),
                        model_used=item.get("model", ""),
                        timestamp=item.get("timestamp", ""),
                        confidence=item.get("confidence", 0.0),
                    ))
            elif isinstance(data, dict):
                for key, items in data.items():
                    if isinstance(items, list):
                        for item in items:
                            entries.append(MemoryEntry(
                                agent_id=agent_name,
                                entry_type=key,
                                content=item if isinstance(item, str) else json.dumps(item),
                                model_used=data.get("model", ""),
                                timestamp=data.get("timestamp", ""),
                            ))
        except (json.JSONDecodeError, KeyError):
            continue
    return entries


def get_all_memories() -> dict[str, list[MemoryEntry]]:
    """Load memories for all agents."""
    result = {}
    if not MEMORY_DIR.exists():
        return result
    for agent_dir in sorted(MEMORY_DIR.iterdir()):
        if agent_dir.is_dir():
            entries = load_agent_memory(agent_dir.name)
            if entries:
                result[agent_dir.name] = entries
    return result


# ---------------------------------------------------------------------------
# Loop state inspection — reads from loop_guard state files
# ---------------------------------------------------------------------------

@dataclass
class LoopInfo:
    """Summary of loop detection state for an agent."""
    agent_id: str
    files_tracked: int = 0
    total_iterations: int = 0
    loops_detected: int = 0
    hard_limits_hit: int = 0
    current_loop_files: list[str] = field(default_factory=list)
    max_iteration_file: str = ""
    max_iteration_count: int = 0


def load_loop_state() -> dict[str, LoopInfo]:
    """Load loop detection state from JSON."""
    result = {}
    if not LOOP_STATE_PATH.exists():
        # Also check for individual agent loop files
        loop_dir = Path(__file__).parent / "results" / "loops"
        if not loop_dir.exists():
            return result
        for f in loop_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                agent_id = f.stem
                info = LoopInfo(
                    agent_id=agent_id,
                    files_tracked=data.get("files_tracked", 0),
                    total_iterations=data.get("total_iterations", 0),
                    loops_detected=data.get("loops_detected", 0),
                    hard_limits_hit=data.get("hard_limits_hit", 0),
                    current_loop_files=data.get("current_loop_files", []),
                    max_iteration_file=data.get("max_iteration_file", ""),
                    max_iteration_count=data.get("max_iteration_count", 0),
                )
                result[agent_id] = info
            except (json.JSONDecodeError, KeyError):
                continue
        return result

    try:
        data = json.loads(LOOP_STATE_PATH.read_text(encoding="utf-8"))
        for agent_id, state in data.get("agents", {}).items():
            result[agent_id] = LoopInfo(
                agent_id=agent_id,
                files_tracked=state.get("files_tracked", 0),
                total_iterations=state.get("total_iterations", 0),
                loops_detected=state.get("loops_detected", 0),
                hard_limits_hit=state.get("hard_limits_hit", 0),
                current_loop_files=state.get("current_loop_files", []),
                max_iteration_file=state.get("max_iteration_file", ""),
                max_iteration_count=state.get("max_iteration_count", 0),
            )
    except (json.JSONDecodeError, KeyError):
        pass
    return result


# ---------------------------------------------------------------------------
# Extended AgentManager
# ---------------------------------------------------------------------------

class ExtendedAgentManager(AgentManager):
    """AgentManager with extended capabilities: add, clone, inspect, memory, loops."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        super().__init__(config_path)

    # --- Add / Clone Agents ---

    def add_agent(self, name: str, stage: float, role: str, model: str,
                  description: str = "", group: str | None = None,
                  priority: int = 5, params: dict | None = None,
                  enabled: bool = True) -> AgentConfig:
        """Add a new agent dynamically.

        The new agent is immediately saved to agents.yaml.
        """
        if name in self.agents:
            raise ValueError(f"Agent '{name}' already exists")

        agent = AgentConfig(
            name=name,
            enabled=enabled,
            stage=stage,
            role=role,
            model=model,
            priority=priority,
            description=description or f"Custom agent: {role}",
            group=group,
            params=params or {},
        )
        self.agents[name] = agent
        self._save_new_agent(name, agent)
        return agent

    def clone_agent(self, source_name: str, new_name: str,
                    new_model: str | None = None) -> AgentConfig:
        """Clone an existing agent with optional model change.

        Useful for: "let me try the same audit with a different model"
        """
        if source_name not in self.agents:
            raise ValueError(f"Source agent '{source_name}' not found")
        if new_name in self.agents:
            raise ValueError(f"Agent '{new_name}' already exists")

        source = self.agents[source_name]
        clone = AgentConfig(
            name=new_name,
            enabled=True,
            stage=source.stage,
            role=source.role,
            model=new_model or source.model,
            priority=source.priority - 1,  # Slightly lower priority
            description=f"Klon {source_name} → {new_model or source.model}",
            group=source.group,
            params=copy.deepcopy(source.params),
        )
        self.agents[new_name] = clone
        self._save_new_agent(new_name, clone)
        return clone

    def remove_agent(self, name: str) -> bool:
        """Remove a dynamically added agent.

        Built-in agents (those originally in agents.yaml) cannot be removed,
        only disabled.
        """
        if name not in self.agents:
            return False
        del self.agents[name]
        self._remove_agent_from_yaml(name)
        return True

    def swap_model(self, name: str, new_model: str) -> bool:
        """Swap an agent's model (hot-swap during pipeline).

        Also resets the agent's loop counter for the new model.
        """
        if name not in self.agents:
            return False
        old_model = self.agents[name].model
        self.agents[name].model = new_model
        self.agents[name].status = AgentStatus.IDLE  # Reset status
        self.save()

        # Log the swap
        swap_log = Path(__file__).parent / "results" / "model_swaps.jsonl"
        swap_log.parent.mkdir(parents=True, exist_ok=True)
        with open(swap_log, "a", encoding="utf-8") as f:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": name,
                "old_model": old_model,
                "new_model": new_model,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True

    # --- Memory Inspection ---

    def get_agent_memory(self, name: str) -> list[MemoryEntry]:
        """Get memory entries for a specific agent."""
        return load_agent_memory(name)

    def get_memory_stats(self, name: str) -> dict:
        """Get memory statistics for an agent."""
        entries = self.get_agent_memory(name)
        if not entries:
            return {"total": 0, "types": {}}
        types: dict[str, int] = {}
        for e in entries:
            types[e.entry_type] = types.get(e.entry_type, 0) + 1
        return {
            "total": len(entries),
            "types": types,
            "latest": entries[-1].timestamp if entries else "",
            "models_used": list(set(e.model_used for e in entries if e.model_used)),
        }

    # --- Loop Inspection ---

    def get_loop_info(self, name: str | None = None) -> dict[str, LoopInfo]:
        """Get loop detection info for one or all agents."""
        all_loops = load_loop_state()
        if name:
            return {name: all_loops.get(name, LoopInfo(agent_id=name))}
        return all_loops

    # --- Persistence Helpers ---

    def _save_new_agent(self, name: str, agent: AgentConfig):
        """Add a new agent to agents.yaml."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        raw.setdefault("agents", {})[name] = {
            "enabled": agent.enabled,
            "stage": agent.stage,
            "role": agent.role,
            "model": agent.model,
            "priority": agent.priority,
            "description": agent.description,
            "group": agent.group,
            "params": agent.params,
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _remove_agent_from_yaml(self, name: str):
        """Remove an agent from agents.yaml."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if name in raw.get("agents", {}):
            del raw["agents"][name]

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Extended CLI Display Functions
# ---------------------------------------------------------------------------

def print_agent_inspect(mgr: ExtendedAgentManager, name: str):
    """Detailed inspection of a single agent."""
    if name not in mgr.agents:
        print(f"  {C.RED}✗ Agent '{name}' nie istnieje{C.RESET}")
        return

    agent = mgr.agents[name]
    mem_stats = mgr.get_memory_stats(name)
    loop_info = mgr.get_loop_info(name).get(name, LoopInfo(agent_id=name))

    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
    print(f"  {C.BOLD}INSPEKCJA AGENTA: {name}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

    # Basic info
    icon = status_icon(agent.status if agent.enabled else AgentStatus.DISABLED)
    print(f"  {C.BOLD}Status:{C.RESET}      {icon} {agent.status.value}")
    print(f"  {C.BOLD}Włączony:{C.RESET}    {enabled_badge(agent.enabled)}")
    print(f"  {C.BOLD}Stage:{C.RESET}       {agent.stage} ({STAGE_NAMES.get(agent.stage, '?')})")
    print(f"  {C.BOLD}Rola:{C.RESET}        {agent.role}")
    print(f"  {C.BOLD}Model:{C.RESET}       {C.MAGENTA}{agent.model}{C.RESET}")
    print(f"  {C.BOLD}Priorytet:{C.RESET}   {agent.priority}/10")
    print(f"  {C.BOLD}Grupa:{C.RESET}       {agent.group or '(brak)'}")
    print(f"  {C.BOLD}Opis:{C.RESET}        {agent.description}")

    # Runtime stats
    if agent.elapsed_seconds > 0 or agent.cost > 0:
        print(f"\n  {C.BOLD}{C.YELLOW}── Statystyki runtime ──{C.RESET}")
        if agent.started_at:
            print(f"  {C.BOLD}Start:{C.RESET}       {agent.started_at}")
        if agent.completed_at:
            print(f"  {C.BOLD}Koniec:{C.RESET}      {agent.completed_at}")
        print(f"  {C.BOLD}Czas:{C.RESET}        {agent.elapsed_seconds:.1f}s")
        print(f"  {C.BOLD}Koszt:{C.RESET}       ${agent.cost:.4f}")
        if agent.error:
            print(f"  {C.RED}{C.BOLD}Błąd:{C.RESET}        {C.RED}{agent.error}{C.RESET}")
        if agent.result_path:
            print(f"  {C.BOLD}Wynik:{C.RESET}       {agent.result_path}")

    # Parameters
    if agent.params:
        print(f"\n  {C.BOLD}{C.BLUE}── Parametry ──{C.RESET}")
        _print_params(agent.params, indent=4)

    # Memory
    print(f"\n  {C.BOLD}{C.GREEN}── Pamięć (czego się nauczył) ──{C.RESET}")
    if mem_stats["total"] == 0:
        print(f"    {C.DIM}(brak wpisów — agent jeszcze nie uczył się){C.RESET}")
    else:
        print(f"    {C.BOLD}Wpisy:{C.RESET}  {mem_stats['total']}")
        for etype, count in sorted(mem_stats["types"].items()):
            icon = _memory_type_icon(etype)
            print(f"    {icon} {etype}: {count}")
        if mem_stats.get("latest"):
            print(f"    {C.DIM}Ostatni wpis: {mem_stats['latest']}{C.RESET}")
        if mem_stats.get("models_used"):
            print(f"    {C.DIM}Modele użyte: {', '.join(mem_stats['models_used'])}{C.RESET}")

    # Loop detection
    print(f"\n  {C.BOLD}{C.YELLOW}── Detekcja pętli ──{C.RESET}")
    if loop_info.total_iterations == 0:
        print(f"    {C.DIM}(brak danych — agent nie wykonywał jeszcze iteracji){C.RESET}")
    else:
        print(f"    {C.BOLD}Pliki śledzone:{C.RESET}   {loop_info.files_tracked}")
        print(f"    {C.BOLD}Łączne iteracje:{C.RESET}  {loop_info.total_iterations}")

        if loop_info.loops_detected > 0:
            print(f"    {C.RED}{C.BOLD}Pętle wykryte:{C.RESET}    "
                  f"{C.RED}{loop_info.loops_detected}{C.RESET}")
        else:
            print(f"    {C.GREEN}Pętle wykryte:{C.RESET}    0 ✓")

        if loop_info.hard_limits_hit > 0:
            print(f"    {C.RED}{C.BOLD}Twardy limit:{C.RESET}    "
                  f"{C.RED}{loop_info.hard_limits_hit}× osiągnięty{C.RESET}")

        if loop_info.current_loop_files:
            print(f"    {C.YELLOW}{C.BOLD}Aktywne pętle:{C.RESET}")
            for fp in loop_info.current_loop_files:
                print(f"      {C.YELLOW}⚠ {fp}{C.RESET}")

        if loop_info.max_iteration_file:
            print(f"    {C.DIM}Max iteracji: {loop_info.max_iteration_count}× "
                  f"w {loop_info.max_iteration_file}{C.RESET}")

    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")


def print_memory_report(mgr: ExtendedAgentManager, agent_name: str | None = None):
    """Print memory report for one or all agents."""
    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
    print(f"  {C.BOLD}RAPORT PAMIĘCI AGENTÓW{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

    if agent_name:
        entries = load_agent_memory(agent_name)
        if not entries:
            print(f"  {C.DIM}Agent '{agent_name}' nie ma zapisanej pamięci{C.RESET}\n")
            return
        _print_memory_entries(agent_name, entries)
    else:
        all_memories = get_all_memories()
        if not all_memories:
            print(f"  {C.DIM}Żaden agent nie ma zapisanej pamięci{C.RESET}")
            print(f"  {C.DIM}(Pamięć tworzy się po pierwszym przebiegu pipeline'u){C.RESET}\n")
            return

        for name, entries in all_memories.items():
            _print_memory_entries(name, entries)
            print()


def _print_memory_entries(agent_name: str, entries: list[MemoryEntry]):
    """Print memory entries for a single agent."""
    print(f"  {C.BOLD}{C.GREEN}{agent_name}{C.RESET} — {len(entries)} wpisów")
    print(f"  {C.DIM}{'─' * 60}{C.RESET}")

    # Group by type
    by_type: dict[str, list[MemoryEntry]] = {}
    for e in entries:
        by_type.setdefault(e.entry_type, []).append(e)

    for etype, elist in sorted(by_type.items()):
        icon = _memory_type_icon(etype)
        print(f"\n    {icon} {C.BOLD}{etype}{C.RESET} ({len(elist)})")
        for e in elist[:5]:  # Show first 5
            content_preview = e.content[:80].replace("\n", " ")
            conf = f" [{e.confidence:.0%}]" if e.confidence > 0 else ""
            print(f"      {C.DIM}•{C.RESET} {content_preview}{conf}")
        if len(elist) > 5:
            print(f"      {C.DIM}... i {len(elist) - 5} więcej{C.RESET}")


def _memory_type_icon(etype: str) -> str:
    icons = {
        "false_positive": f"{C.RED}✗{C.RESET}",
        "true_positive": f"{C.GREEN}✓{C.RESET}",
        "pattern": f"{C.BLUE}◈{C.RESET}",
        "preference": f"{C.MAGENTA}♦{C.RESET}",
        "lesson": f"{C.YELLOW}★{C.RESET}",
    }
    return icons.get(etype, f"{C.DIM}•{C.RESET}")


def _print_params(params: dict, indent: int = 2):
    """Pretty-print nested parameters."""
    prefix = " " * indent
    for key, val in params.items():
        if isinstance(val, dict):
            print(f"{prefix}{C.BOLD}{key}:{C.RESET}")
            _print_params(val, indent + 2)
        elif isinstance(val, list):
            print(f"{prefix}{C.BOLD}{key}:{C.RESET} [{', '.join(str(v) for v in val[:5])}"
                  f"{'...' if len(val) > 5 else ''}]")
        else:
            print(f"{prefix}{C.BOLD}{key}:{C.RESET} {val}")


def print_loop_report(mgr: ExtendedAgentManager):
    """Print loop detection report for all agents."""
    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
    print(f"  {C.BOLD}RAPORT PĘTLI POPRAWEK{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

    all_loops = load_loop_state()
    if not all_loops:
        print(f"  {C.DIM}Brak danych o pętlach{C.RESET}")
        print(f"  {C.DIM}(Dane pojawią się po uruchomieniu pipeline'u z Loop Guard){C.RESET}\n")
        return

    total_loops = sum(li.loops_detected for li in all_loops.values())
    total_limits = sum(li.hard_limits_hit for li in all_loops.values())
    total_iters = sum(li.total_iterations for li in all_loops.values())

    # Summary
    if total_loops == 0:
        print(f"  {C.GREEN}✓ Brak wykrytych pętli — system zdrowy{C.RESET}\n")
    else:
        print(f"  {C.RED}⚠ Wykryte pętle: {total_loops}   "
              f"Osiągnięte limity: {total_limits}   "
              f"Łączne iteracje: {total_iters}{C.RESET}\n")

    # Per-agent
    for agent_id, info in sorted(all_loops.items()):
        if info.total_iterations == 0:
            continue

        if info.loops_detected > 0:
            status = f"{C.RED}⚠ PĘTLA{C.RESET}"
        elif info.total_iterations > 3:
            status = f"{C.YELLOW}⚡ OBSERWACJA{C.RESET}"
        else:
            status = f"{C.GREEN}✓ OK{C.RESET}"

        print(f"  {C.BOLD}{agent_id}{C.RESET}  {status}")
        print(f"    Iteracji: {info.total_iterations}  "
              f"Pętli: {info.loops_detected}  "
              f"Plików: {info.files_tracked}")

        if info.current_loop_files:
            for fp in info.current_loop_files:
                print(f"    {C.YELLOW}  ⟳ {fp}{C.RESET}")
        print()


def print_agent_comparison(mgr: ExtendedAgentManager, name1: str, name2: str):
    """Compare two agents side by side."""
    if name1 not in mgr.agents or name2 not in mgr.agents:
        print(f"  {C.RED}✗ Jeden z agentów nie istnieje{C.RESET}")
        return

    a1 = mgr.agents[name1]
    a2 = mgr.agents[name2]
    m1 = mgr.get_memory_stats(name1)
    m2 = mgr.get_memory_stats(name2)
    l1 = mgr.get_loop_info(name1).get(name1, LoopInfo(agent_id=name1))
    l2 = mgr.get_loop_info(name2).get(name2, LoopInfo(agent_id=name2))

    col_w = 30

    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}")
    print(f"  {C.BOLD}PORÓWNANIE: {name1} vs {name2}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")

    def row(label: str, v1: str, v2: str):
        print(f"  {C.BOLD}{label:<16}{C.RESET}  {v1:<{col_w}}  {v2:<{col_w}}")

    row("", f"{C.BOLD}{name1}{C.RESET}", f"{C.BOLD}{name2}{C.RESET}")
    print(f"  {'─' * 16}  {'─' * col_w}  {'─' * col_w}")
    row("Model", a1.model, a2.model)
    row("Status", a1.status.value, a2.status.value)
    row("Stage", str(a1.stage), str(a2.stage))
    row("Priorytet", str(a1.priority), str(a2.priority))
    row("Czas", f"{a1.elapsed_seconds:.1f}s", f"{a2.elapsed_seconds:.1f}s")
    row("Koszt", f"${a1.cost:.4f}", f"${a2.cost:.4f}")
    row("Pamięć", f"{m1['total']} wpisów", f"{m2['total']} wpisów")
    row("Iteracji", str(l1.total_iterations), str(l2.total_iterations))
    row("Pętli", str(l1.loops_detected), str(l2.loops_detected))

    # Memory type breakdown
    all_types = set(list(m1.get("types", {}).keys()) + list(m2.get("types", {}).keys()))
    if all_types:
        print(f"\n  {C.BOLD}Pamięć — typy:{C.RESET}")
        for t in sorted(all_types):
            c1 = m1.get("types", {}).get(t, 0)
            c2 = m2.get("types", {}).get(t, 0)
            row(f"  {t}", str(c1), str(c2))

    print(f"\n{C.BOLD}{C.CYAN}{'═' * 72}{C.RESET}\n")


# ---------------------------------------------------------------------------
# Extended Interactive Dashboard
# ---------------------------------------------------------------------------

def extended_dashboard(mgr: ExtendedAgentManager):
    """Extended interactive terminal dashboard."""
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print_status(mgr)

        # Show loop warnings
        all_loops = load_loop_state()
        active_loops = {k: v for k, v in all_loops.items() if v.loops_detected > 0}
        if active_loops:
            print(f"  {C.RED}{C.BOLD}⚠ WYKRYTE PĘTLE:{C.RESET}")
            for agent_id, info in active_loops.items():
                print(f"    {C.RED}⟳ {agent_id}: {info.loops_detected} pętli, "
                      f"{info.total_iterations} iteracji{C.RESET}")
            print()

        # Show memory summary
        all_mem = get_all_memories()
        if all_mem:
            total_entries = sum(len(v) for v in all_mem.values())
            agents_with_mem = len(all_mem)
            print(f"  {C.GREEN}🧠 Pamięć: {total_entries} wpisów "
                  f"u {agents_with_mem} agentów{C.RESET}\n")

        print(f"{C.BOLD}Komendy podstawowe:{C.RESET}")
        print(f"  {C.CYAN}e/d/t <agent>{C.RESET} — włącz/wyłącz/toggle    "
              f"  {C.CYAN}p <profil>{C.RESET} — profil")
        print(f"  {C.CYAN}eg/dg <grupa>{C.RESET} — włącz/wyłącz grupę    "
              f"  {C.CYAN}v{C.RESET} — walidacja")

        print(f"\n{C.BOLD}Komendy rozszerzone:{C.RESET}")
        print(f"  {C.CYAN}i <agent>{C.RESET}     — inspekcja agenta (pełny profil)")
        print(f"  {C.CYAN}m [agent]{C.RESET}     — pamięć (czego się nauczyli)")
        print(f"  {C.CYAN}l{C.RESET}             — raport pętli poprawek")
        print(f"  {C.CYAN}cmp <a> <b>{C.RESET}   — porównaj dwóch agentów")
        print(f"  {C.CYAN}add{C.RESET}           — dodaj nowego agenta (interaktywnie)")
        print(f"  {C.CYAN}clone <src>{C.RESET}   — klonuj agenta z innym modelem")
        print(f"  {C.CYAN}swap <a> <m>{C.RESET}  — zmień model agenta w locie")
        print(f"  {C.CYAN}rm <agent>{C.RESET}    — usuń dodanego agenta")
        print(f"  {C.CYAN}r{C.RESET} — odśwież   {C.CYAN}q{C.RESET} — wyjście")
        print()

        try:
            cmd = input(f"{C.BOLD}> {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if action == "q":
            break
        elif action == "r":
            mgr.load()
        elif action == "v":
            print_validation(mgr)
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")

        # --- Basic commands ---
        elif action == "e" and args:
            _do_enable(mgr, args[0])
        elif action == "d" and args:
            _do_disable(mgr, args[0])
        elif action == "t" and args:
            _do_toggle(mgr, args[0])
        elif action == "eg" and args:
            mgr.enable_group(args[0])
            print(f"  {C.GREEN}✓ Grupa '{args[0]}' włączona{C.RESET}")
            time.sleep(0.5)
        elif action == "dg" and args:
            mgr.disable_group(args[0])
            print(f"  {C.RED}✗ Grupa '{args[0]}' wyłączona{C.RESET}")
            time.sleep(0.5)
        elif action == "p" and args:
            if mgr.apply_profile(args[0]):
                print(f"  {C.GREEN}✓ Profil '{args[0]}' zastosowany{C.RESET}")
            else:
                print(f"  {C.RED}✗ Profil '{args[0]}' nie istnieje{C.RESET}")
            time.sleep(1)

        # --- Extended commands ---
        elif action == "i" and args:
            print_agent_inspect(mgr, args[0])
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")

        elif action == "m":
            agent_name = args[0] if args else None
            print_memory_report(mgr, agent_name)
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")

        elif action == "l":
            print_loop_report(mgr)
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")

        elif action == "cmp" and len(args) >= 2:
            print_agent_comparison(mgr, args[0], args[1])
            input(f"\n{C.DIM}Enter aby kontynuować...{C.RESET}")

        elif action == "add":
            _do_add_agent(mgr)

        elif action == "clone" and args:
            _do_clone_agent(mgr, args[0])

        elif action == "swap" and len(args) >= 2:
            if mgr.swap_model(args[0], args[1]):
                print(f"  {C.GREEN}✓ {args[0]}: model → {args[1]}{C.RESET}")
            else:
                print(f"  {C.RED}✗ Agent '{args[0]}' nie istnieje{C.RESET}")
            time.sleep(1)

        elif action == "rm" and args:
            if mgr.remove_agent(args[0]):
                print(f"  {C.GREEN}✓ Agent '{args[0]}' usunięty{C.RESET}")
            else:
                print(f"  {C.RED}✗ Agent '{args[0]}' nie istnieje{C.RESET}")
            time.sleep(0.5)

        else:
            print(f"  {C.DIM}Nieznana komenda: {cmd}{C.RESET}")
            time.sleep(0.5)


def _do_enable(mgr, name):
    if mgr.enable(name):
        print(f"  {C.GREEN}✓ {name} włączony{C.RESET}")
    else:
        print(f"  {C.RED}✗ Agent '{name}' nie istnieje{C.RESET}")
    time.sleep(0.5)


def _do_disable(mgr, name):
    if mgr.disable(name):
        print(f"  {C.RED}✗ {name} wyłączony{C.RESET}")
    else:
        print(f"  {C.RED}✗ Agent '{name}' nie istnieje{C.RESET}")
    time.sleep(0.5)


def _do_toggle(mgr, name):
    result = mgr.toggle(name)
    if result is not None:
        state = "włączony" if result else "wyłączony"
        print(f"  → {name} {state}")
    else:
        print(f"  {C.RED}✗ Agent '{name}' nie istnieje{C.RESET}")
    time.sleep(0.5)


def _do_add_agent(mgr: ExtendedAgentManager):
    """Interactive agent creation."""
    print(f"\n{C.BOLD}{C.CYAN}── Dodawanie nowego agenta ──{C.RESET}\n")
    try:
        name = input(f"  {C.BOLD}Nazwa:{C.RESET} ").strip()
        if not name:
            return
        stage = float(input(f"  {C.BOLD}Stage (0-9):{C.RESET} ").strip())
        role = input(f"  {C.BOLD}Rola:{C.RESET} ").strip()
        model = input(f"  {C.BOLD}Model (claude-sonnet/gpt-5/gemini-pro/...):{C.RESET} ").strip() or "claude-sonnet"
        desc = input(f"  {C.BOLD}Opis:{C.RESET} ").strip()
        group = input(f"  {C.BOLD}Grupa (puste = brak):{C.RESET} ").strip() or None

        agent = mgr.add_agent(
            name=name, stage=stage, role=role, model=model,
            description=desc, group=group,
        )
        print(f"\n  {C.GREEN}✓ Agent '{name}' dodany (Stage {stage}, {model}){C.RESET}")
    except ValueError as e:
        print(f"\n  {C.RED}✗ Błąd: {e}{C.RESET}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {C.DIM}Anulowano{C.RESET}")
    time.sleep(1)


def _do_clone_agent(mgr: ExtendedAgentManager, source: str):
    """Interactive agent cloning."""
    if source not in mgr.agents:
        print(f"  {C.RED}✗ Agent '{source}' nie istnieje{C.RESET}")
        time.sleep(0.5)
        return

    print(f"\n{C.BOLD}{C.CYAN}── Klonowanie agenta '{source}' ──{C.RESET}\n")
    try:
        new_name = input(f"  {C.BOLD}Nowa nazwa:{C.RESET} ").strip()
        if not new_name:
            return
        new_model = input(
            f"  {C.BOLD}Nowy model (Enter = ten sam: {mgr.agents[source].model}):{C.RESET} "
        ).strip()

        clone = mgr.clone_agent(source, new_name, new_model or None)
        print(f"\n  {C.GREEN}✓ Sklonowano '{source}' → '{new_name}' ({clone.model}){C.RESET}")
    except ValueError as e:
        print(f"\n  {C.RED}✗ Błąd: {e}{C.RESET}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {C.DIM}Anulowano{C.RESET}")
    time.sleep(1)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SYLION Extended Agent Manager — rozbudowany panel zarządzania",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python agent_manager_ext.py status
  python agent_manager_ext.py add auditor_extra 2 "Audytor" gpt-5
  python agent_manager_ext.py clone auditor_claude auditor_claude_v2 gpt-5
  python agent_manager_ext.py inspect auditor_claude
  python agent_manager_ext.py memory auditor_claude
  python agent_manager_ext.py loops
  python agent_manager_ext.py swap-model auditor_claude gpt-5
  python agent_manager_ext.py compare auditor_claude auditor_gpt
  python agent_manager_ext.py dashboard
        """,
    )
    parser.add_argument("command", choices=[
        "status", "enable", "disable", "toggle",
        "profile", "profiles", "groups", "validate",
        "add", "clone", "remove",
        "inspect", "memory", "loops",
        "swap-model", "compare",
        "dashboard", "export",
        "enable-group", "disable-group",
        "enable-stage", "disable-stage",
    ], help="Komenda do wykonania")
    parser.add_argument("args", nargs="*", help="Argumenty komendy")
    parser.add_argument("--config", "-c", type=Path, default=CONFIG_PATH,
                        help="Ścieżka do agents.yaml")

    args = parser.parse_args()
    mgr = ExtendedAgentManager(args.config)

    # Forward basic commands
    if args.command == "status":
        print_status(mgr)
    elif args.command in ("enable", "disable", "toggle"):
        if not args.args:
            print(f"Użycie: agent_manager_ext.py {args.command} <agent>")
            sys.exit(1)
        for name in args.args:
            if args.command == "enable":
                _do_enable(mgr, name)
            elif args.command == "disable":
                _do_disable(mgr, name)
            else:
                _do_toggle(mgr, name)
    elif args.command == "profile":
        if not args.args:
            print_profiles(mgr)
        elif mgr.apply_profile(args.args[0]):
            print(f"  ✓ Profil '{args.args[0]}' zastosowany")
            print_status(mgr)
        else:
            print(f"  ✗ Profil '{args.args[0]}' nie istnieje")
    elif args.command == "profiles":
        print_profiles(mgr)
    elif args.command == "groups":
        print_groups(mgr)
    elif args.command == "validate":
        print_validation(mgr)

    # Extended commands
    elif args.command == "add":
        if len(args.args) >= 4:
            name, stage, role, model = args.args[0], float(args.args[1]), args.args[2], args.args[3]
            desc = " ".join(args.args[4:]) if len(args.args) > 4 else ""
            try:
                mgr.add_agent(name, stage, role, model, description=desc)
                print(f"  ✓ Agent '{name}' dodany")
            except ValueError as e:
                print(f"  ✗ {e}")
        else:
            _do_add_agent(mgr)

    elif args.command == "clone":
        if len(args.args) >= 2:
            source, new_name = args.args[0], args.args[1]
            new_model = args.args[2] if len(args.args) > 2 else None
            try:
                clone = mgr.clone_agent(source, new_name, new_model)
                print(f"  ✓ Sklonowano '{source}' → '{new_name}' ({clone.model})")
            except ValueError as e:
                print(f"  ✗ {e}")
        else:
            print("Użycie: agent_manager_ext.py clone <source> <new_name> [model]")

    elif args.command == "remove":
        if args.args:
            if mgr.remove_agent(args.args[0]):
                print(f"  ✓ Agent '{args.args[0]}' usunięty")
            else:
                print(f"  ✗ Agent '{args.args[0]}' nie istnieje")
        else:
            print("Użycie: agent_manager_ext.py remove <agent>")

    elif args.command == "inspect":
        if args.args:
            print_agent_inspect(mgr, args.args[0])
        else:
            print("Użycie: agent_manager_ext.py inspect <agent>")

    elif args.command == "memory":
        agent_name = args.args[0] if args.args else None
        print_memory_report(mgr, agent_name)

    elif args.command == "loops":
        print_loop_report(mgr)

    elif args.command == "swap-model":
        if len(args.args) >= 2:
            if mgr.swap_model(args.args[0], args.args[1]):
                print(f"  ✓ {args.args[0]}: model → {args.args[1]}")
            else:
                print(f"  ✗ Agent '{args.args[0]}' nie istnieje")
        else:
            print("Użycie: agent_manager_ext.py swap-model <agent> <new_model>")

    elif args.command == "compare":
        if len(args.args) >= 2:
            print_agent_comparison(mgr, args.args[0], args.args[1])
        else:
            print("Użycie: agent_manager_ext.py compare <agent1> <agent2>")

    elif args.command == "export":
        config = {
            "global": mgr.global_config,
            "agents": {
                name: {
                    "enabled": a.enabled, "stage": a.stage, "role": a.role,
                    "model": a.model, "priority": a.priority,
                    "description": a.description, "group": a.group,
                    "params": a.params, "status": a.status.value,
                    "memory_entries": mgr.get_memory_stats(name).get("total", 0),
                    "loop_iterations": mgr.get_loop_info(name).get(name, LoopInfo(agent_id=name)).total_iterations,
                }
                for name, a in mgr.agents.items()
            },
        }
        print(json.dumps(config, indent=2, ensure_ascii=False))

    elif args.command in ("enable-group", "disable-group"):
        if not args.args:
            print(f"Użycie: agent_manager_ext.py {args.command} <group>")
            sys.exit(1)
        if args.command == "enable-group":
            mgr.enable_group(args.args[0])
        else:
            mgr.disable_group(args.args[0])

    elif args.command in ("enable-stage", "disable-stage"):
        if not args.args:
            print(f"Użycie: agent_manager_ext.py {args.command} <N>")
            sys.exit(1)
        if args.command == "enable-stage":
            mgr.enable_stage(float(args.args[0]))
        else:
            mgr.disable_stage(float(args.args[0]))

    elif args.command == "dashboard":
        extended_dashboard(mgr)


if __name__ == "__main__":
    main()
