"""
SYLION Contracts -- Compatibility Checker

Checks compatibility between contract versions and module implementations.
Validates .proto breaking changes, event compatibility, and lifecycle transitions.

Proto breaking rules:
  - Removed field   -> breaking
  - Changed type    -> breaking
  - Changed number  -> breaking
  - Added field     -> non-breaking
  - Removed RPC     -> breaking
  - Added RPC       -> non-breaking
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.contract_registry import ContractRegistry

log = logging.getLogger("sylion.contracts.compatibility_checker")


# ---------------------------------------------------------------------------
# Proto AST parsing helpers
# ---------------------------------------------------------------------------

class ProtoElementType(str, Enum):
    MESSAGE = "message"
    SERVICE = "service"
    ENUM    = "enum"


@dataclass
class ProtoField:
    """Represents a single field inside a protobuf message."""
    label: str          # optional, repeated, required, or ""
    type_name: str      # string, int32, ModuleManifest, etc.
    name: str
    number: int


@dataclass
class ProtoRpc:
    """Represents an RPC inside a protobuf service."""
    name: str
    input_type: str
    output_type: str


@dataclass
class ProtoMessage:
    name: str
    fields: dict[int, ProtoField] = field(default_factory=dict)   # number -> field


@dataclass
class ProtoService:
    name: str
    rpcs: dict[str, ProtoRpc] = field(default_factory=dict)       # name -> rpc


def parse_proto(text: str) -> dict[str, Any]:
    """Parse a .proto file into structured message/service definitions.

    Returns ``{"messages": {name: ProtoMessage}, "services": {name: ProtoService}}``.
    This is a simplified parser -- it handles the constructs used across the SYLION
    proto corpus (fields, repeated fields, rpcs, maps) without requiring protoc.
    """
    messages: dict[str, ProtoMessage] = {}
    services: dict[str, ProtoService] = {}

    # Strip single-line comments
    lines = []
    for raw_line in text.splitlines():
        # Remove // comments but preserve strings (naive -- good enough for our protos)
        ci = raw_line.find("//")
        if ci >= 0:
            raw_line = raw_line[:ci]
        lines.append(raw_line)

    source = "\n".join(lines)

    # --- Parse messages ---
    for m_match in re.finditer(r"message\s+(\w+)\s*\{", source):
        msg_name = m_match.group(1)
        msg = ProtoMessage(name=msg_name)
        # Extract body between braces
        body = _extract_braced_body(source, m_match.end() - 1)
        if body is not None:
            _parse_message_fields(body, msg)
        messages[msg_name] = msg

    # --- Parse services ---
    for s_match in re.finditer(r"service\s+(\w+)\s*\{", source):
        svc_name = s_match.group(1)
        svc = ProtoService(name=svc_name)
        body = _extract_braced_body(source, s_match.end() - 1)
        if body is not None:
            _parse_service_rpcs(body, svc)
        services[svc_name] = svc

    return {"messages": messages, "services": services}


def _extract_braced_body(text: str, open_brace_pos: int) -> str | None:
    """Return the text between the matching closing brace, starting from open_brace_pos."""
    if open_brace_pos >= len(text) or text[open_brace_pos] != "{":
        return None
    depth = 0
    start = open_brace_pos + 1
    for i in range(open_brace_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
    return None


_FIELD_RE = re.compile(
    r"^\s*"
    r"(?P<label>repeated|map|optional|required)\s+"
    r"|"
    r"(?P<simple>)"
    r"(?P<type>[A-Za-z_][\w.]*(?:<[^>]+>)?)\s+"
    r"(?P<name>\w+)\s*=\s*(?P<number>\d+)"
)

_MAP_RE = re.compile(
    r"^\s*map\s*<\s*(?P<key_type>[\w.]+)\s*,\s*(?P<value_type>[\w.]+)\s*>\s+"
    r"(?P<name>\w+)\s*=\s*(?P<number>\d+)"
)


def _parse_message_fields(body: str, msg: ProtoMessage) -> None:
    for line in body.split(";"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        # Try map<K, V> first
        m = _MAP_RE.match(line)
        if m:
            f = ProtoField(
                label="map",
                type_name=f"map<{m.group('key_type')},{m.group('value_type')}>",
                name=m.group("name"),
                number=int(m.group("number")),
            )
            msg.fields[f.number] = f
            continue

        # Regular / repeated / optional field
        m = re.match(
            r"^\s*(?P<label>repeated|optional|required)\s+"
            r"(?P<type>[A-Za-z_][\w.]*(?:<[^>]+>)?)\s+"
            r"(?P<name>\w+)\s*=\s*(?P<number>\d+)",
            line,
        )
        if not m:
            # bare field (proto3 default)
            m = re.match(
                r"^\s*(?P<type>[A-Za-z_][\w.]*(?:<[^>]+>)?)\s+"
                r"(?P<name>\w+)\s*=\s*(?P<number>\d+)",
                line,
            )
            if not m:
                continue
            f = ProtoField(
                label="",
                type_name=m.group("type"),
                name=m.group("name"),
                number=int(m.group("number")),
            )
        else:
            f = ProtoField(
                label=m.group("label"),
                type_name=m.group("type"),
                name=m.group("name"),
                number=int(m.group("number")),
            )
        msg.fields[f.number] = f


_RPC_RE = re.compile(
    r"rpc\s+(?P<name>\w+)\s*\(\s*(?:stream\s+)?(?P<in>[\w.]+)\s*\)"
    r"\s*returns\s*\(\s*(?:stream\s+)?(?P<out>[\w.]+)\s*\)"
)


def _parse_service_rpcs(body: str, svc: ProtoService) -> None:
    for m in _RPC_RE.finditer(body):
        rpc = ProtoRpc(
            name=m.group("name"),
            input_type=m.group("in"),
            output_type=m.group("out"),
        )
        svc.rpcs[rpc.name] = rpc


# ---------------------------------------------------------------------------
# Proto diff engine
# ---------------------------------------------------------------------------

@dataclass
class ProtoChange:
    """A single detected change between two proto definitions."""
    kind: str           # "field_removed", "field_type_changed", "field_number_changed",
                        # "field_added", "rpc_removed", "rpc_added"
    breaking: bool
    detail: str


def diff_protos(
    old_defs: dict[str, Any],
    new_defs: dict[str, Any],
) -> list[ProtoChange]:
    """Compare two proto definition dicts and return a list of changes."""
    changes: list[ProtoChange] = []

    old_msgs: dict[str, ProtoMessage] = old_defs.get("messages", {})
    new_msgs: dict[str, ProtoMessage] = new_defs.get("messages", {})
    old_svcs: dict[str, ProtoService] = old_defs.get("services", {})
    new_svcs: dict[str, ProtoService] = new_defs.get("services", {})

    # --- Message diffs ---
    for msg_name, old_msg in old_msgs.items():
        new_msg = new_msgs.get(msg_name)
        if new_msg is None:
            # Entire message removed -- every field is breaking
            for num, f in old_msg.fields.items():
                changes.append(ProtoChange(
                    kind="field_removed",
                    breaking=True,
                    detail=f"message {msg_name}: field '{f.name}' (#{num}) removed (message removed)",
                ))
            continue

        # Compare fields
        _diff_message_fields(msg_name, old_msg, new_msg, changes)

    # New messages (non-breaking)
    for msg_name in new_msgs:
        if msg_name not in old_msgs:
            for num, f in new_msgs[msg_name].fields.items():
                changes.append(ProtoChange(
                    kind="field_added",
                    breaking=False,
                    detail=f"message {msg_name}: field '{f.name}' (#{num}) added (new message)",
                ))

    # --- Service diffs ---
    for svc_name, old_svc in old_svcs.items():
        new_svc = new_svcs.get(svc_name)
        if new_svc is None:
            for rpc_name in old_svc.rpcs:
                changes.append(ProtoChange(
                    kind="rpc_removed",
                    breaking=True,
                    detail=f"service {svc_name}: rpc '{rpc_name}' removed (service removed)",
                ))
            continue

        _diff_service_rpcs(svc_name, old_svc, new_svc, changes)

    for svc_name in new_svcs:
        if svc_name not in old_svcs:
            for rpc_name in new_svcs[svc_name].rpcs:
                changes.append(ProtoChange(
                    kind="rpc_added",
                    breaking=False,
                    detail=f"service {svc_name}: rpc '{rpc_name}' added (new service)",
                ))

    return changes


def _diff_message_fields(
    msg_name: str,
    old_msg: ProtoMessage,
    new_msg: ProtoMessage,
    changes: list[ProtoChange],
) -> None:
    # Check by field number
    for num, old_f in old_msg.fields.items():
        new_f = new_msg.fields.get(num)
        if new_f is None:
            # Field number removed
            changes.append(ProtoChange(
                kind="field_removed",
                breaking=True,
                detail=f"message {msg_name}: field '{old_f.name}' (#{num}) removed",
            ))
            continue

        # Same number -- check type
        if _normalize_type(old_f.type_name) != _normalize_type(new_f.type_name):
            changes.append(ProtoChange(
                kind="field_type_changed",
                breaking=True,
                detail=(
                    f"message {msg_name}: field #{num} type changed "
                    f"from '{old_f.type_name}' to '{new_f.type_name}'"
                ),
            ))

        # Check if name changed (number same, name different -> confusing but not breaking per se)
        # We track it as a note but not breaking

    # Check if any old field numbers were reused with different names (number swap)
    old_name_to_num = {f.name: n for n, f in old_msg.fields.items()}
    new_name_to_num = {f.name: n for n, f in new_msg.fields.items()}

    for name, old_num in old_name_to_num.items():
        new_num = new_name_to_num.get(name)
        if new_num is not None and new_num != old_num:
            changes.append(ProtoChange(
                kind="field_number_changed",
                breaking=True,
                detail=(
                    f"message {msg_name}: field '{name}' number changed "
                    f"from #{old_num} to #{new_num}"
                ),
            ))

    # New fields (non-breaking)
    for num, new_f in new_msg.fields.items():
        if num not in old_msg.fields:
            changes.append(ProtoChange(
                kind="field_added",
                breaking=False,
                detail=f"message {msg_name}: field '{new_f.name}' (#{num}) added",
            ))


def _diff_service_rpcs(
    svc_name: str,
    old_svc: ProtoService,
    new_svc: ProtoService,
    changes: list[ProtoChange],
) -> None:
    for rpc_name in old_svc.rpcs:
        if rpc_name not in new_svc.rpcs:
            changes.append(ProtoChange(
                kind="rpc_removed",
                breaking=True,
                detail=f"service {svc_name}: rpc '{rpc_name}' removed",
            ))

    for rpc_name in new_svc.rpcs:
        if rpc_name not in old_svc.rpcs:
            changes.append(ProtoChange(
                kind="rpc_added",
                breaking=False,
                detail=f"service {svc_name}: rpc '{rpc_name}' added",
            ))


def _normalize_type(t: str) -> str:
    """Normalize a proto type name for comparison."""
    return t.strip().lower().replace(" ", "")


# ---------------------------------------------------------------------------
# Compatibility Checker
# ---------------------------------------------------------------------------

class CompatibilityChecker:
    """Checks compatibility between contract versions and module implementations.

    Parameters
    ----------
    contract_registry:
        A :class:`ContractRegistry` instance.
    module_registry:
        A :class:`ModuleRegistry` instance.
    """

    def __init__(self, contract_registry: Any, module_registry: Any) -> None:
        self._contracts = contract_registry
        self._modules = module_registry

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _major(version: str) -> int:
        """Extract major version number from a semver string."""
        try:
            return int(version.split(".")[0])
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def _parse_consumers(raw: Any) -> list[str]:
        """Parse consumer_modules field into a list."""
        import json as _json
        if isinstance(raw, str):
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError:
                return []
        if isinstance(raw, list):
            return raw
        return []

    def _is_contract_breaking(self, contract: dict) -> bool:
        """Check if the latest version of a contract was a breaking change.

        Compares the latest (current) version against the second-latest version.
        """
        name = contract.get("name", "")
        versions = self._contracts.list_versions(name)
        if len(versions) < 2:
            return False
        # versions[0] is latest, versions[1] is previous
        old_ver = versions[1].get("version", "0.0.0")
        new_ver = versions[0].get("version", "0.0.0")
        old_major = self._major(old_ver)
        new_major = self._major(new_ver)
        return old_major != new_major

    def _is_contract_breaking_for_module(self, contract: dict) -> bool:
        """Same as _is_contract_breaking -- checks latest vs previous version."""
        return self._is_contract_breaking(contract)

    # ------------------------------------------------------------------
    # Module-level contract check
    # ------------------------------------------------------------------

    def check_module_contracts(self, module_id: str) -> dict:
        """Check all contracts for a module are compatible.

        Returns ``{"compatible": bool, "issues": list[str]}``.
        """
        issues: list[str] = []

        # 1. Contracts where module is the producer
        all_contracts = self._contracts.list_all()
        produced = [c for c in all_contracts if c.get("producer_module") == module_id]

        for contract in produced:
            if self._is_contract_breaking(contract):
                name = contract.get("name", "")
                versions = self._contracts.list_versions(name)
                old_ver = versions[1]["version"] if len(versions) > 1 else "?"
                new_ver = contract.get("version", "?")
                issues.append(
                    f"Produced contract '{name}' has breaking version change: "
                    f"{old_ver} -> {new_ver}"
                )

        # 2. Contracts where module is a consumer
        for contract in all_contracts:
            consumers = self._parse_consumers(contract.get("consumer_modules", "[]"))

            if module_id in consumers:
                if self._is_contract_breaking(contract):
                    name = contract.get("name", "")
                    versions = self._contracts.list_versions(name)
                    old_ver = versions[1]["version"] if len(versions) > 1 else "?"
                    new_ver = contract.get("version", "?")
                    issues.append(
                        f"Consumed contract '{name}' has breaking version change: "
                        f"{old_ver} -> {new_ver}"
                    )

        # 3. Check module exists
        mod = self._modules.get(module_id)
        if mod is None:
            issues.append(f"Module '{module_id}' not found in registry")

        compatible = len(issues) == 0
        return {"compatible": compatible, "issues": issues}

    # ------------------------------------------------------------------
    # Proto breaking change detection
    # ------------------------------------------------------------------

    def check_proto_breaking(
        self,
        proto_path_old: str | Path,
        proto_path_new: str | Path,
    ) -> dict:
        """Compare two .proto files for breaking changes.

        Returns ``{"breaking": bool, "changes": list[dict]}``.
        """
        old_text = Path(proto_path_old).read_text(encoding="utf-8")
        new_text = Path(proto_path_new).read_text(encoding="utf-8")
        return self.check_proto_breaking_from_text(old_text, new_text)

    def check_proto_breaking_from_text(self, old_text: str, new_text: str) -> dict:
        """Compare two .proto source strings for breaking changes.

        Returns ``{"breaking": bool, "changes": list[dict]}``.
        """
        old_defs = parse_proto(old_text)
        new_defs = parse_proto(new_text)
        proto_changes = diff_protos(old_defs, new_defs)

        changes = [
            {"kind": c.kind, "breaking": c.breaking, "detail": c.detail}
            for c in proto_changes
        ]

        breaking = any(c["breaking"] for c in changes)
        return {"breaking": breaking, "changes": changes}

    # ------------------------------------------------------------------
    # Event compatibility
    # ------------------------------------------------------------------

    def check_event_compatibility(
        self,
        producer_events: list[str],
        consumer_events: list[str],
    ) -> dict:
        """Check that consumed events match produced events.

        Returns ``{"compatible": bool, "missing": list[str], "extra": list[str]}``
        where *missing* are events the consumer expects but the producer does not
        emit, and *extra* are events the producer emits that the consumer does not
        consume (non-breaking informational).
        """
        prod_set = set(producer_events)
        cons_set = set(consumer_events)

        missing = sorted(cons_set - prod_set)
        extra = sorted(prod_set - cons_set)

        compatible = len(missing) == 0
        return {
            "compatible": compatible,
            "missing": missing,
            "extra": extra,
        }

    # ------------------------------------------------------------------
    # Full system report
    # ------------------------------------------------------------------

    def generate_compatibility_report(self) -> dict:
        """Full system compatibility report across all modules and contracts.

        Returns ``{"modules_checked": int, "modules_compatible": int,
        "total_issues": int, "module_reports": dict, "summary": str}``.
        """
        modules = self._modules.list_modules()
        module_reports: dict[str, dict] = {}
        total_issues = 0
        modules_compatible = 0

        for mod in modules:
            mid = mod.get("module_id", "")
            report = self.check_module_contracts(mid)
            module_reports[mid] = report
            total_issues += len(report.get("issues", []))
            if report.get("compatible"):
                modules_compatible += 1

        modules_checked = len(modules)
        breaking = modules_checked - modules_compatible

        summary = (
            f"Checked {modules_checked} modules, "
            f"{modules_compatible} compatible, "
            f"{breaking} with issues, "
            f"{total_issues} total issues"
        )

        return {
            "modules_checked": modules_checked,
            "modules_compatible": modules_compatible,
            "total_issues": total_issues,
            "module_reports": module_reports,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Lifecycle transition validation
    # ------------------------------------------------------------------

    def validate_transition(self, module_id: str, target_stage: str) -> dict:
        """Validate that a lifecycle transition will not break contracts.

        Checks:
        1. Module contracts are currently compatible.
        2. All dependent modules have compatible contracts.
        3. For transitions to ``stable``/``cutover``, all consumed contracts
           must be in compatible state.

        Returns ``{"valid": bool, "issues": list[str]}``.
        """
        issues: list[str] = []

        # Module must exist
        mod = self._modules.get(module_id)
        if mod is None:
            return {"valid": False, "issues": [f"Module '{module_id}' not found"]}

        # 1. Check module's own contracts
        mod_check = self.check_module_contracts(module_id)
        if not mod_check.get("compatible"):
            for issue in mod_check.get("issues", []):
                issues.append(f"[{module_id}] {issue}")

        # 2. Check dependent modules (modules that depend on this one)
        all_modules = self._modules.list_modules()

        for other in all_modules:
            other_id = other.get("module_id", "")
            if other_id == module_id:
                continue
            depends = self._parse_consumers(other.get("depends_on", "[]"))

            if module_id in depends:
                dep_check = self.check_module_contracts(other_id)
                if not dep_check.get("compatible"):
                    for issue in dep_check.get("issues", []):
                        issues.append(f"[dependent {other_id}] {issue}")

        # 3. Extra checks for critical stages
        if target_stage in ("stable", "cutover"):
            all_contracts = self._contracts.list_all()
            for contract in all_contracts:
                consumers = self._parse_consumers(contract.get("consumer_modules", "[]"))

                if module_id in consumers:
                    if self._is_contract_breaking(contract):
                        name = contract.get("name", "")
                        issues.append(
                            f"Cannot transition to '{target_stage}': consumed contract "
                            f"'{name}' has breaking changes"
                        )

        # 4. Check that the module has no breaking produced contracts when
        #    transitioning beyond validate
        critical_stages = {"shadow", "dual", "cutover", "stable"}
        if target_stage in critical_stages:
            all_contracts = self._contracts.list_all()
            for contract in all_contracts:
                if contract.get("producer_module") == module_id:
                    if self._is_contract_breaking(contract):
                        name = contract.get("name", "")
                        issues.append(
                            f"Cannot transition to '{target_stage}': produced contract "
                            f"'{name}' has breaking changes that affect consumers"
                        )

        valid = len(issues) == 0
        return {"valid": valid, "issues": issues}
