"""
SYLION Skills -- Runtime Engine

Loads skill definitions from filesystem manifests or skill directories and
executes them through declared handlers or a simulated default path.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.skills.runtime")


def _load_structured_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(f"PyYAML is required to parse {path}") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    raise ValueError(f"Unsupported manifest file: {path}")


def _normalise_inputs(inputs: Any) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for item in inputs or []:
        if isinstance(item, dict):
            normalised.append({
                "name": item.get("name", ""),
                "type": item.get("type", "string"),
                "required": bool(item.get("required", False)),
                **{k: v for k, v in item.items() if k not in {"name", "type", "required"}},
            })
        elif isinstance(item, str):
            normalised.append({"name": item, "type": "string", "required": False})
    return [item for item in normalised if item.get("name")]


def _normalise_outputs(outputs: Any) -> list[Any]:
    normalised: list[Any] = []
    for item in outputs or []:
        if isinstance(item, dict):
            normalised.append(dict(item))
        elif isinstance(item, str):
            normalised.append({"name": item})
    return normalised


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SkillSpec:
    """A loaded skill specification."""

    skill_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[Any] = field(default_factory=list)
    parallel_safe: bool = True
    idempotent: bool = True
    steps: list[str] = field(default_factory=list)
    safety_rules: list[str] = field(default_factory=list)
    source_path: str = ""
    manifest_path: str = ""
    entry_point: str = ""
    requires_hg: bool = False
    domain: str = ""
    owner_role: str = ""
    lifecycle: str = "PUBLISHED"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.skill_id and self.name:
            self.skill_id = self.name
        if not self.name and self.skill_id:
            self.name = self.skill_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "parallel_safe": self.parallel_safe,
            "idempotent": self.idempotent,
            "steps": list(self.steps),
            "safety_rules": list(self.safety_rules),
            "source_path": self.source_path,
            "manifest_path": self.manifest_path,
            "entry_point": self.entry_point,
            "requires_hg": self.requires_hg,
            "domain": self.domain,
            "owner_role": self.owner_role,
            "lifecycle": self.lifecycle,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


@dataclass
class RuntimeExecution:
    """A runtime skill execution record."""

    exec_id: str = ""
    skill_name: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: Any = field(default_factory=dict)
    status: str = "pending"
    step_results: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    error: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.exec_id:
            self.exec_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Skill loading helpers
# ---------------------------------------------------------------------------

def _spec_from_payload(payload: dict[str, Any], *, source_path: str = "", manifest_path: str = "") -> SkillSpec:
    name = payload.get("name") or payload.get("skill_id") or ""
    skill_id = payload.get("skill_id") or name
    metadata = {
        k: v
        for k, v in payload.items()
        if k
        not in {
            "skill_id",
            "name",
            "version",
            "description",
            "inputs",
            "outputs",
            "parallel_safe",
            "idempotent",
            "steps",
            "safety_rules",
            "entry_point",
            "requires_hg",
            "domain",
            "owner_role",
            "lifecycle",
            "tags",
        }
    }
    return SkillSpec(
        skill_id=skill_id,
        name=name or skill_id,
        version=payload.get("version", "1.0.0"),
        description=payload.get("description", ""),
        inputs=_normalise_inputs(payload.get("inputs", [])),
        outputs=_normalise_outputs(payload.get("outputs", [])),
        parallel_safe=bool(payload.get("parallel_safe", True)),
        idempotent=bool(payload.get("idempotent", True)),
        steps=[str(step) for step in payload.get("steps", []) if str(step).strip()],
        safety_rules=[str(rule) for rule in payload.get("safety_rules", []) if str(rule).strip()],
        source_path=source_path,
        manifest_path=manifest_path,
        entry_point=payload.get("entry_point", ""),
        requires_hg=bool(payload.get("requires_hg", False)),
        domain=payload.get("domain", ""),
        owner_role=payload.get("owner_role", ""),
        lifecycle=payload.get("lifecycle", "PUBLISHED"),
        tags=[str(tag) for tag in payload.get("tags", []) if str(tag).strip()],
        metadata=metadata,
    )


def load_skill_manifest(manifest_path: Path) -> SkillSpec | None:
    """Load a skill manifest from YAML or JSON."""

    if not manifest_path.exists() or not manifest_path.is_file():
        return None

    if manifest_path.suffix.lower() not in {".json", ".yaml", ".yml"}:
        return None

    payload = _load_structured_file(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Skill manifest must be a mapping: {manifest_path}")

    payload = dict(payload)
    payload.setdefault("skill_id", payload.get("name", manifest_path.stem))
    payload.setdefault("name", payload.get("skill_id", manifest_path.stem))
    return _spec_from_payload(payload, manifest_path=str(manifest_path))


def load_skill_spec(skill_dir: Path) -> SkillSpec | None:
    """Load a skill specification from a directory containing SKILL.md + skill.yaml."""

    md_file = skill_dir / "SKILL.md"
    yaml_file = skill_dir / "skill.yaml"

    if not md_file.exists():
        return None

    base_payload: dict[str, Any] = {}
    if yaml_file.exists():
        try:
            yaml_payload = _load_structured_file(yaml_file)
            if isinstance(yaml_payload, dict):
                base_payload.update(yaml_payload)
        except Exception as exc:  # pragma: no cover - defensive logging
            log.warning("failed to parse %s: %s", yaml_file, exc)

    base_payload.setdefault("name", skill_dir.name)
    base_payload.setdefault("skill_id", base_payload["name"])
    spec = _spec_from_payload(base_payload, source_path=str(skill_dir))

    try:
        content = md_file.read_text(encoding="utf-8")

        steps_match = re.search(
            r"##\s*Execution\s+steps\s*\n(.*?)(?=\n##\s|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if steps_match:
            step_text = steps_match.group(1)
            parsed_steps = re.findall(r"^\d+\.\s*\*\*(.+?)\*\*", step_text, re.MULTILINE)
            if not parsed_steps:
                parsed_steps = re.findall(r"^\d+\.\s*(.+)", step_text, re.MULTILINE)
            if parsed_steps:
                spec.steps = [step.strip() for step in parsed_steps if step.strip()]

        safety_match = re.search(
            r"##\s*Safety\s+rules\s*\n(.*?)(?=\n##\s|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if safety_match:
            safety_text = safety_match.group(1)
            parsed_rules = re.findall(r"^\d+\.\s*(.+)", safety_text, re.MULTILINE)
            if parsed_rules:
                spec.safety_rules = [rule.strip() for rule in parsed_rules if rule.strip()]

        if not spec.name:
            fm_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
            if fm_match:
                spec.name = fm_match.group(1).strip()
                spec.skill_id = spec.skill_id or spec.name

    except Exception as exc:  # pragma: no cover - defensive logging
        log.warning("failed to parse %s: %s", md_file, exc)

    return spec


# ---------------------------------------------------------------------------
# Skills Runtime
# ---------------------------------------------------------------------------

class SkillsRuntime:
    """Skills runtime engine with spec loading and execution."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        skills_dir: str | Path | None = None,
        event_bus: EventBus | None = None,
    ):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._skills_dir = Path(skills_dir) if skills_dir else None
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._specs: dict[str, SkillSpec] = {}
        self._aliases: dict[str, str] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

        if self._skills_dir:
            self.bootstrap_from(self._skills_dir)

    def _ensure_tables(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_executions (
                exec_id      TEXT PRIMARY KEY,
                skill_name   TEXT    NOT NULL,
                inputs       TEXT    NOT NULL DEFAULT '{}',
                outputs      TEXT    NOT NULL DEFAULT '{}',
                status       TEXT    NOT NULL DEFAULT 'pending',
                step_results TEXT    NOT NULL DEFAULT '[]',
                duration_ms  INTEGER NOT NULL DEFAULT 0,
                error        TEXT    NOT NULL DEFAULT '',
                timestamp    REAL    NOT NULL
            )
        """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rtexec_skill ON runtime_executions(skill_name)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rtexec_status ON runtime_executions(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rtexec_ts ON runtime_executions(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Discovery / bootstrap
    # ------------------------------------------------------------------

    def _canonical_skill_id(self, skill_name: str) -> str:
        return self._aliases.get(skill_name, skill_name)

    def _resolve_handler(self, entry_point: str) -> Callable[..., Any] | None:
        if not entry_point:
            return None

        module_name, sep, attr_name = entry_point.partition(":")
        if not sep:
            raise ValueError(f"Invalid entry_point '{entry_point}', expected module:function")
        module = import_module(module_name)
        handler = getattr(module, attr_name)
        if not callable(handler):
            raise TypeError(f"Entry point {entry_point} is not callable")
        return handler

    def _store_spec(self, spec: SkillSpec, handler: Callable[..., Any] | None = None) -> SkillSpec:
        skill_id = spec.skill_id or spec.name
        if not skill_id:
            raise ValueError("Skill spec requires skill_id or name")

        spec.skill_id = skill_id
        spec.name = spec.name or skill_id
        self._specs[skill_id] = spec
        self._aliases[skill_id] = skill_id
        self._aliases[spec.name] = skill_id
        if handler is not None:
            self._handlers[skill_id] = handler
        elif skill_id in self._handlers and not spec.entry_point:
            self._handlers.pop(skill_id, None)
        return spec

    def bootstrap_one(self, skill_source: SkillSpec | dict[str, Any] | str | Path) -> SkillSpec | None:
        if isinstance(skill_source, SkillSpec):
            spec = skill_source
        elif isinstance(skill_source, dict):
            spec = _spec_from_payload(dict(skill_source))
        else:
            path = Path(skill_source)
            if path.is_dir():
                spec = load_skill_spec(path)
            else:
                spec = load_skill_manifest(path)

        if spec is None:
            return None

        handler = None
        if spec.entry_point:
            try:
                handler = self._resolve_handler(spec.entry_point)
            except Exception as exc:  # pragma: no cover - defensive logging
                log.warning("failed to resolve handler for %s: %s", spec.skill_id or spec.name, exc)

        loaded = self._store_spec(spec, handler=handler)
        log.info("bootstrapped skill %s from %s", loaded.skill_id, loaded.manifest_path or loaded.source_path or "memory")
        return loaded

    def bootstrap_from(self, skills_dir: str | Path) -> None:
        target = Path(skills_dir)
        self._skills_dir = target
        if not target.exists():
            return

        for entry in sorted(target.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                self.bootstrap_one(entry)
            elif entry.is_file() and entry.suffix.lower() in {".json", ".yaml", ".yml"}:
                self.bootstrap_one(entry)

    def discover_skills(self, skills_dir: str | Path | None = None) -> list[str]:
        """Scan a directory for skill definitions and load specs."""

        before = set(self._specs.keys())
        target = Path(skills_dir) if skills_dir else self._skills_dir
        if not target:
            return []

        self.bootstrap_from(target)
        after = set(self._specs.keys())
        return sorted(after - before) if before else sorted(after)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_inputs(self, skill_name: str, inputs: dict[str, Any]) -> list[str]:
        """Validate inputs against skill spec. Returns list of errors."""

        errors = []
        skill_id = self._canonical_skill_id(skill_name)
        spec = self._specs.get(skill_id)
        if not spec:
            return [f"Unknown skill: {skill_name}"]

        for inp_spec in spec.inputs:
            name = inp_spec.get("name", "")
            required = bool(inp_spec.get("required", False))
            if required and name not in inputs:
                errors.append(f"Missing required input: {name}")

        return errors

    def _invoke_handler(self, handler: Callable[..., Any], spec: SkillSpec, inputs: dict[str, Any]) -> Any:
        try:
            params = list(inspect.signature(handler).parameters.values())
        except (TypeError, ValueError):  # pragma: no cover - rare callable wrappers
            params = []

        positional = [
            param
            for param in params
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params)

        if has_varargs or len(positional) >= 2:
            return handler(spec, inputs)
        if len(positional) == 1:
            return handler(inputs)
        return handler()

    def _load_governance_hooks(self):
        return import_module("sylion.governance.tickets")

    @staticmethod
    def _ticket_field(ticket: Any, field: str) -> Any:
        if ticket is None:
            return None
        if isinstance(ticket, dict):
            return ticket.get(field)
        return getattr(ticket, field, None)

    def _build_governance_ticket(self, governance: Any, spec: SkillSpec, inputs: dict[str, Any], invocation_id: str):
        payload = dict(inputs)
        payload.setdefault("skill_id", spec.skill_id)
        payload.setdefault("skill_name", spec.name)
        payload.setdefault("skill_invocation_id", invocation_id)

        return governance.GovernanceTicket(
            origin="skill",
            project_id=inputs.get("project_id"),
            decision_class=spec.metadata.get("decision_class", "D2"),
            gate_type=spec.metadata.get("gate_type", "blocking"),
            priority=spec.metadata.get("priority", "P2"),
            title=spec.metadata.get("title", f"Execute skill {spec.skill_id}"),
            summary=spec.description[:200],
            payload=payload,
            requested_by=inputs.get("operator_id", "skills.runtime"),
        )

    def _ensure_governance_approval(self, spec: SkillSpec, inputs: dict[str, Any], invocation_id: str) -> str:
        governance = self._load_governance_hooks()
        fetch_by_id = getattr(governance, "fetch_by_id", None)
        submit = getattr(governance, "submit", None)
        if fetch_by_id is None or submit is None or not hasattr(governance, "GovernanceTicket"):
            raise RuntimeError("Governance ticket hooks are unavailable for HG-required skill execution")

        ticket_id = inputs.get("ticket_id")
        if ticket_id:
            ticket = fetch_by_id(ticket_id)
            if ticket is None:
                raise RuntimeError(f"Governance ticket {ticket_id} not found")
        else:
            ticket = self._build_governance_ticket(governance, spec, inputs, invocation_id)
            ticket_id = submit(ticket)

        timeout_ms = int(inputs.get("hg_timeout_ms", spec.metadata.get("hg_timeout_ms", 0)) or 0)
        poll_interval_ms = int(inputs.get("hg_poll_interval_ms", spec.metadata.get("hg_poll_interval_ms", 250)) or 250)
        deadline = time.time() + (timeout_ms / 1000.0 if timeout_ms > 0 else 0.0)

        while True:
            current = fetch_by_id(ticket_id)
            state = self._ticket_field(current, "state")
            if state == "approved":
                return str(ticket_id)
            if state in {"rejected", "expired", "withdrawn"}:
                raise RuntimeError(f"Governance ticket {ticket_id} {state}")
            if timeout_ms <= 0 or time.time() >= deadline:
                raise RuntimeError(f"Governance ticket {ticket_id} pending approval")
            time.sleep(max(poll_interval_ms, 0) / 1000.0)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        skill_name: str,
        inputs: dict[str, Any] | None = None,
        handler: Any = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a skill by name."""

        if inputs is None:
            inputs = context or {}
        elif context:
            merged = dict(context)
            merged.update(inputs)
            inputs = merged

        skill_id = self._canonical_skill_id(skill_name)
        spec = self._specs.get(skill_id)
        if not spec:
            return self._record_failed(skill_name, inputs, f"Unknown skill: {skill_name}")

        validation_errors = self.validate_inputs(skill_id, inputs)
        if validation_errors:
            return self._record_failed(skill_id, inputs, "; ".join(validation_errors))

        start = time.time()
        step_results: list[dict[str, Any]] = []
        ticket_id = inputs.get("ticket_id")
        invocation_id = uuid.uuid4().hex

        try:
            if spec.requires_hg:
                ticket_id = self._ensure_governance_approval(spec, inputs, invocation_id)
                if ticket_id:
                    inputs = dict(inputs)
                    inputs.setdefault("ticket_id", ticket_id)

            runtime_handler = handler if callable(handler) else self._handlers.get(skill_id)
            if runtime_handler is not None:
                output_data = self._invoke_handler(runtime_handler, spec, inputs)
            else:
                output_data = {
                    "executed_steps": len(spec.steps),
                    "steps": list(spec.steps),
                    "safety_rules_count": len(spec.safety_rules),
                    "result": "completed",
                }
                for index, step in enumerate(spec.steps, start=1):
                    step_results.append({
                        "step": index,
                        "description": step,
                        "status": "simulated",
                    })

            duration_ms = int((time.time() - start) * 1000)
            result = self._record_success(skill_id, inputs, output_data, step_results, duration_ms)
            if ticket_id:
                result["ticket_id"] = ticket_id
            return result
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            result = self._record_failed(skill_id, inputs, str(exc), duration_ms)
            if ticket_id:
                result["ticket_id"] = ticket_id
            return result

    def _record_success(
        self,
        skill_name: str,
        inputs: dict[str, Any],
        output_data: Any,
        step_results: list[dict[str, Any]],
        duration_ms: int,
    ) -> dict[str, Any]:
        ex = RuntimeExecution(
            skill_name=skill_name,
            inputs=inputs,
            outputs=output_data,
            status="completed",
            step_results=step_results,
            duration_ms=duration_ms,
        )
        self._persist(ex)

        self._emit(
            "skill.runtime.executed",
            {
                "exec_id": ex.exec_id,
                "skill_name": skill_name,
                "status": "completed",
                "duration_ms": duration_ms,
            },
        )

        return {
            "ok": True,
            "exec_id": ex.exec_id,
            "skill_id": skill_name,
            "skill_name": skill_name,
            "status": "completed",
            "output": output_data,
            "steps_completed": len(step_results),
            "duration_ms": duration_ms,
        }

    def _record_failed(
        self,
        skill_name: str,
        inputs: dict[str, Any],
        error: str,
        duration_ms: int = 0,
    ) -> dict[str, Any]:
        ex = RuntimeExecution(
            skill_name=skill_name,
            inputs=inputs,
            status="failed",
            error=error,
            duration_ms=duration_ms,
        )
        self._persist(ex)

        self._emit(
            "skill.runtime.failed",
            {
                "exec_id": ex.exec_id,
                "skill_name": skill_name,
                "error": error,
            },
        )

        return {
            "ok": False,
            "exec_id": ex.exec_id,
            "skill_id": skill_name,
            "skill_name": skill_name,
            "status": "failed",
            "error": error,
        }

    def _persist(self, ex: RuntimeExecution):
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO runtime_executions
                    (exec_id, skill_name, inputs, outputs, status,
                     step_results, duration_ms, error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    ex.exec_id,
                    ex.skill_name,
                    json.dumps(ex.inputs, default=str),
                    json.dumps(ex.outputs, default=str),
                    ex.status,
                    json.dumps(ex.step_results, default=str),
                    ex.duration_ms,
                    ex.error,
                    ex.timestamp,
                ),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_spec(self, skill_name: str) -> dict[str, Any] | None:
        """Return a loaded skill specification."""

        skill_id = self._canonical_skill_id(skill_name)
        spec = self._specs.get(skill_id)
        return spec.to_dict() if spec else None

    def get_loaded_skill(self, skill_name: str) -> dict[str, Any] | None:
        skill_id = self._canonical_skill_id(skill_name)
        spec = self._specs.get(skill_id)
        if not spec:
            return None
        data = spec.to_dict()
        data["loaded"] = True
        data["has_handler"] = skill_id in self._handlers
        return data

    def list_loaded(self) -> list[dict[str, Any]]:
        return [self.get_loaded_skill(skill_id) for skill_id in sorted(self._specs.keys())]

    def list_specs(self) -> list[str]:
        """List all loaded skill names."""

        return sorted(self._specs.keys())

    def get_execution(self, exec_id: str) -> dict[str, Any] | None:
        """Return a single execution by ID."""

        row = self._conn.execute("SELECT * FROM runtime_executions WHERE exec_id = ?", (exec_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["inputs"] = json.loads(data.get("inputs", "{}"))
        data["outputs"] = json.loads(data.get("outputs", "{}"))
        data["step_results"] = json.loads(data.get("step_results", "[]"))
        return data

    def list_executions(
        self,
        skill_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List executions with optional filters."""

        query = "SELECT * FROM runtime_executions WHERE 1=1"
        params: list[Any] = []
        if skill_name:
            query += " AND skill_name = ?"
            params.append(self._canonical_skill_id(skill_name))
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data["inputs"] = json.loads(data.get("inputs", "{}"))
            data["outputs"] = json.loads(data.get("outputs", "{}"))
            data["step_results"] = json.loads(data.get("step_results", "[]"))
            results.append(data)
        return results

    def get_stats(self) -> dict[str, Any]:
        """Aggregate runtime execution statistics."""

        total = self._conn.execute("SELECT COUNT(*) as cnt FROM runtime_executions").fetchone()["cnt"]
        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM runtime_executions GROUP BY status"
        ).fetchall()
        by_status = {row["status"]: row["cnt"] for row in by_status_rows}
        by_skill_rows = self._conn.execute(
            "SELECT skill_name, COUNT(*) as cnt FROM runtime_executions GROUP BY skill_name"
        ).fetchall()
        by_skill = {row["skill_name"]: row["cnt"] for row in by_skill_rows}

        return {
            "total_executions": total,
            "loaded_skills": len(self._specs),
            "by_status": by_status,
            "by_skill": by_skill,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus:
            self._event_bus.publish(
                SylionEvent(
                    event_id="",
                    topic=topic,
                    payload=payload,
                    source_module="skills.runtime",
                )
            )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runtime: SkillsRuntime | None = None


def get_skills_runtime(
    db_path: str | Path | None = None,
    skills_dir: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> SkillsRuntime:
    global _runtime
    if _runtime is None:
        _runtime = SkillsRuntime(db_path, skills_dir, event_bus)
    else:
        if db_path is not None and str(db_path) != _runtime._db_path:
            _runtime = SkillsRuntime(db_path, skills_dir or _runtime._skills_dir, event_bus or _runtime._event_bus)
        elif skills_dir:
            _runtime.bootstrap_from(skills_dir)
    return _runtime


def reset_skills_runtime(
    db_path: str | Path | None = None,
    skills_dir: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> SkillsRuntime | None:
    global _runtime
    _runtime = None
    if db_path is not None or skills_dir is not None or event_bus is not None:
        _runtime = SkillsRuntime(db_path=db_path, skills_dir=skills_dir, event_bus=event_bus)
    return _runtime


def bootstrap_from(skills_dir: str | Path) -> None:
    """Hook v1.0 (2026-04-24): bootstrap runtime skills from a directory."""

    get_skills_runtime(skills_dir=skills_dir).bootstrap_from(skills_dir)


def list_loaded() -> list[dict[str, Any]]:
    """Hook v1.0 (2026-04-24): list loaded runtime skills."""

    return get_skills_runtime().list_loaded()


def execute(skill_id: str, context: dict[str, Any]) -> dict[str, Any]:
    """Hook v1.0 (2026-04-24): execute a runtime skill."""

    return get_skills_runtime().execute(skill_id, context=context)
