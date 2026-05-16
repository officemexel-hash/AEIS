"""Obsidian-compatible long-horizon project memory.

The connector is intentionally local-first: AEIS writes Markdown notes into a
real vault directory and keeps a small JSON index for status and graph reads.
That gives the runtime a durable artefact without depending on the Obsidian
desktop app or an external plugin during tests and local deployments.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_VAULT_ROOT = Path("output") / "obsidian_vault"
INDEX_RELATIVE_PATH = Path(".aeis") / "obsidian_sync_index.json"


def resolve_obsidian_vault_root(vault_root: str | Path | None = None) -> Path:
    value = vault_root or os.environ.get("SYLION_OBSIDIAN_VAULT_ROOT") or DEFAULT_VAULT_ROOT
    return Path(value).expanduser()


def _safe_note_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return slug or "project"


def _project_id(project: dict[str, Any]) -> str:
    value = str(project.get("project_id") or project.get("id") or "").strip()
    if not value:
        raise ValueError("project_id is required for Obsidian sync")
    return value


def _project_title(project: dict[str, Any]) -> str:
    return str(project.get("name") or project.get("title") or _project_id(project)).strip()


def _classification(project: dict[str, Any]) -> dict[str, Any]:
    value = project.get("classification") or {}
    return value if isinstance(value, dict) else {}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _tag_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").lower()).strip("-")
    return token[:64]


def auto_tags_for_project(project: dict[str, Any]) -> list[str]:
    cls = _classification(project)
    tags = [
        "aeis",
        "project",
        f"state-{_tag_token(str(project.get('state') or 'unknown'))}",
    ]
    if cls.get("domain"):
        tags.append(f"domain-{_tag_token(str(cls['domain']))}")
    if cls.get("project_type"):
        tags.append(f"type-{_tag_token(str(cls['project_type']))}")
    if cls.get("d_level_label"):
        tags.append(f"d-level-{_tag_token(str(cls['d_level_label']))}")
    for signal in cls.get("detected_signals") or []:
        token = _tag_token(str(signal))
        if token:
            tags.append(f"signal-{token}")
    if project.get("state") == "CLOSED":
        tags.append("closed")
    if ((project.get("execution") or {}).get("project_closure") or {}).get("cost_reconciliation", {}).get("local_only"):
        tags.append("local-only")
    return _unique(tags)


def _link(project_id: str, title: str | None = None) -> str:
    note_name = _safe_note_name(project_id)
    label = str(title or project_id).strip()
    if label and label != project_id:
        return f"[[{note_name}|{label}]]"
    return f"[[{note_name}]]"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> float:
    return time.time()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        Path(tmp_name).replace(path)
    except Exception:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        finally:
            raise


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


@dataclass
class ObsidianMemorySync:
    vault_root: Path | str | None = None

    def __post_init__(self) -> None:
        self.vault_root = resolve_obsidian_vault_root(self.vault_root)

    @property
    def projects_dir(self) -> Path:
        return Path(self.vault_root) / "Projects"

    @property
    def evidence_dir(self) -> Path:
        return Path(self.vault_root) / "Evidence"

    @property
    def index_path(self) -> Path:
        return Path(self.vault_root) / INDEX_RELATIVE_PATH

    def connector_status(self) -> dict[str, Any]:
        return {
            "connector": "obsidian-local-vault",
            "mode": "local_markdown",
            "vault_root": str(self.vault_root),
            "selective_sync": True,
            "index_path": str(self.index_path),
        }

    def _load_index(self) -> dict[str, Any]:
        index = _read_json(
            self.index_path,
            {
                "schema": "aeis.obsidian_sync_index.v1",
                "vault_root": str(self.vault_root),
                "updated_at": 0.0,
                "projects": {},
            },
        )
        if not isinstance(index, dict):
            index = {}
        index.setdefault("schema", "aeis.obsidian_sync_index.v1")
        index["vault_root"] = str(self.vault_root)
        index.setdefault("projects", {})
        return index

    def _save_index(self, index: dict[str, Any]) -> None:
        index["updated_at"] = _now()
        _write_json(self.index_path, index)

    def _project_note_path(self, project_id: str) -> Path:
        return self.projects_dir / f"{_safe_note_name(project_id)}.md"

    def _evidence_path(self, project_id: str) -> Path:
        return self.evidence_dir / f"{_safe_note_name(project_id)}.json"

    def _related_from_index(self, project: dict[str, Any], tags: list[str], limit: int = 8) -> list[dict[str, str]]:
        index = self._load_index()
        project_id = _project_id(project)
        domain_tags = {tag for tag in tags if tag.startswith(("domain-", "d-level-", "type-"))}
        related: list[dict[str, str]] = []
        for other_id, item in (index.get("projects") or {}).items():
            if other_id == project_id or not isinstance(item, dict):
                continue
            other_tags = set(item.get("tags") or [])
            if domain_tags.intersection(other_tags):
                related.append({"project_id": other_id, "title": str(item.get("title") or other_id)})
            if len(related) >= limit:
                break
        return related

    def _normalize_related(
        self,
        related_projects: list[dict[str, Any]] | list[str] | None,
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in related_projects or []:
            if isinstance(item, str):
                pid = item
                title = item
            elif isinstance(item, dict):
                pid = str(item.get("project_id") or item.get("id") or "").strip()
                title = str(item.get("name") or item.get("title") or pid).strip()
            else:
                continue
            if pid:
                normalized.append({"project_id": pid, "title": title or pid})
        dedup: dict[str, dict[str, str]] = {}
        for item in normalized:
            dedup[item["project_id"]] = item
        return list(dedup.values())

    def _note_markdown(
        self,
        project: dict[str, Any],
        *,
        tags: list[str],
        related_projects: list[dict[str, str]],
        closure: dict[str, Any] | None,
        evidence_hash: str,
        synced_at: float,
        source: str,
    ) -> str:
        project_id = _project_id(project)
        cls = _classification(project)
        title = _project_title(project)
        closure = closure or ((project.get("execution") or {}).get("project_closure") or {})
        artifacts = closure.get("artifacts") or {}
        goals = project.get("goals") or {}
        scope = project.get("scope") or {}
        planning = project.get("planning") or {}
        related_lines = [
            f"- {_link(item['project_id'], item.get('title'))}"
            for item in related_projects
            if item.get("project_id") != project_id
        ]
        if not related_lines:
            related_lines = ["- No related projects indexed yet."]

        artifact_lines = []
        for key, value in sorted(artifacts.items()):
            if isinstance(value, dict) and value.get("path"):
                artifact_lines.append(f"- {key}: `{value.get('path')}` ({value.get('sha256', 'no-sha')})")
        if not artifact_lines:
            artifact_lines = ["- No closure artifacts recorded."]

        lessons = ((closure.get("calibration") or {}).get("learnings") or [])[:8]
        lesson_lines = [f"- {item}" for item in lessons] or ["- No lessons recorded."]
        tag_lines = "\n".join(f"  - {tag}" for tag in tags)
        related_yaml = "\n".join(f"  - {item['project_id']}" for item in related_projects if item.get("project_id") != project_id) or "  []"

        summary = str(goals.get("summary") or project.get("idea_text") or project.get("description") or "").strip()
        if len(summary) > 900:
            summary = f"{summary[:900].rstrip()}..."

        return "\n".join(
            [
                "---",
                f'project_id: "{project_id}"',
                f'title: "{title.replace(chr(34), chr(39))}"',
                f'state: "{project.get("state", "")}"',
                f'domain: "{cls.get("domain", "")}"',
                f'd_level: "{cls.get("d_level_label", "")}"',
                f'project_type: "{cls.get("project_type", "")}"',
                f"synced_at: {synced_at:.6f}",
                f'source: "{source}"',
                f'evidence_hash: "{evidence_hash}"',
                "tags:",
                tag_lines,
                "related_projects:",
                related_yaml,
                "---",
                "",
                f"# {title}",
                "",
                "## Runtime Status",
                f"- Project ID: `{project_id}`",
                f"- State: `{project.get('state', '')}`",
                f"- Domain: `{cls.get('domain', '')}`",
                f"- Decision level: `{cls.get('d_level_label', '')}`",
                f"- Source: `{source}`",
                "",
                "## Project Summary",
                summary or "No project summary recorded.",
                "",
                "## Scope Snapshot",
                f"- In scope: {str(scope.get('in_scope') or [])[:1200]}",
                f"- Constraints: {str(scope.get('constraints') or [])[:1200]}",
                f"- Planning state: {str(planning.get('status') or planning.get('phase') or '')}",
                "",
                "## Closure Lessons",
                *lesson_lines,
                "",
                "## Related Projects",
                *related_lines,
                "",
                "## Evidence Trail",
                f"- Evidence hash: `{evidence_hash}`",
                f"- Obsidian evidence JSON: `{self._evidence_path(project_id)}`",
                *artifact_lines,
                "",
                "## Auto Tags",
                " ".join(f"#{tag}" for tag in tags),
                "",
            ]
        )

    def sync_project(
        self,
        project: dict[str, Any],
        *,
        related_projects: list[dict[str, Any]] | list[str] | None = None,
        closure: dict[str, Any] | None = None,
        source: str = "manual",
        require_closed: bool = True,
    ) -> dict[str, Any]:
        project_id = _project_id(project)
        if require_closed and str(project.get("state") or "").upper() != "CLOSED":
            raise ValueError("only CLOSED projects can be synced to long-horizon Obsidian memory")

        synced_at = _now()
        tags = auto_tags_for_project(project)
        explicit_related = self._normalize_related(related_projects)
        inferred_related = self._related_from_index(project, tags)
        related_map = {item["project_id"]: item for item in inferred_related}
        related_map.update({item["project_id"]: item for item in explicit_related})
        related_map.pop(project_id, None)
        related = list(related_map.values())

        closure_payload = closure or ((project.get("execution") or {}).get("project_closure") or {})
        evidence_source = {
            "project_id": project_id,
            "state": project.get("state"),
            "title": _project_title(project),
            "classification": _classification(project),
            "closure_artifacts": (closure_payload.get("artifacts") or {}),
            "related_project_ids": [item["project_id"] for item in related],
            "tags": tags,
            "source": source,
            "synced_at": synced_at,
        }
        evidence_hash = _sha256_text(json.dumps(evidence_source, ensure_ascii=False, sort_keys=True, default=str))
        note = self._note_markdown(
            project,
            tags=tags,
            related_projects=related,
            closure=closure_payload,
            evidence_hash=evidence_hash,
            synced_at=synced_at,
            source=source,
        )
        note_path = self._project_note_path(project_id)
        evidence_path = self._evidence_path(project_id)
        _atomic_write_text(note_path, note)
        note_sha = _sha256_file(note_path)
        evidence_payload = {
            **evidence_source,
            "evidence_hash": evidence_hash,
            "note_path": str(note_path),
            "note_sha256": note_sha,
            "vault_root": str(self.vault_root),
            "connector": self.connector_status(),
        }
        _write_json(evidence_path, evidence_payload)

        index = self._load_index()
        index["projects"][project_id] = {
            "project_id": project_id,
            "title": _project_title(project),
            "state": project.get("state"),
            "domain": _classification(project).get("domain", ""),
            "d_level": _classification(project).get("d_level_label", ""),
            "tags": tags,
            "related_project_ids": [item["project_id"] for item in related],
            "note_path": str(note_path),
            "evidence_path": str(evidence_path),
            "evidence_hash": evidence_hash,
            "note_sha256": note_sha,
            "synced_at": synced_at,
            "source": source,
        }
        self._save_index(index)

        return {
            "status": "synced",
            "project_id": project_id,
            "vault_root": str(self.vault_root),
            "note_path": str(note_path),
            "evidence_path": str(evidence_path),
            "evidence_hash": evidence_hash,
            "note_sha256": note_sha,
            "tags": tags,
            "related_project_ids": [item["project_id"] for item in related],
            "graph_node_id": project_id,
            "selective_sync": True,
            "synced_at": synced_at,
        }

    def status(self, project_id: str) -> dict[str, Any]:
        project_id = str(project_id or "").strip()
        index = self._load_index()
        item = (index.get("projects") or {}).get(project_id)
        note_path = self._project_note_path(project_id)
        if not isinstance(item, dict):
            return {
                "project_id": project_id,
                "status": "not_synced",
                "synced": False,
                "vault_root": str(self.vault_root),
                "note_path": str(note_path),
                "note_exists": note_path.exists(),
            }
        return {
            **item,
            "status": "synced" if note_path.exists() else "index_only_missing_note",
            "synced": note_path.exists(),
            "vault_root": str(self.vault_root),
            "note_exists": note_path.exists(),
        }

    def graph(self) -> dict[str, Any]:
        index = self._load_index()
        projects = index.get("projects") or {}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for project_id, item in projects.items():
            if not isinstance(item, dict):
                continue
            nodes.append(
                {
                    "id": project_id,
                    "label": item.get("title") or project_id,
                    "state": item.get("state"),
                    "domain": item.get("domain"),
                    "d_level": item.get("d_level"),
                    "tags": item.get("tags") or [],
                    "note_path": item.get("note_path"),
                }
            )
            for target in item.get("related_project_ids") or []:
                if target:
                    edges.append({"source": project_id, "target": target, "type": "obsidian_backlink"})
        return {
            "vault_root": str(self.vault_root),
            "nodes": nodes,
            "edges": edges,
            "counts": {"nodes": len(nodes), "edges": len(edges)},
            "updated_at": index.get("updated_at", 0.0),
            "source": "obsidian_sync_index",
        }

    def read_note(self, project_id: str) -> dict[str, Any]:
        note_path = self._project_note_path(project_id)
        if not note_path.exists():
            raise FileNotFoundError(str(note_path))
        content = note_path.read_text(encoding="utf-8")
        return {
            "project_id": project_id,
            "note_path": str(note_path),
            "sha256": _sha256_file(note_path),
            "bytes": note_path.stat().st_size,
            "content": content,
        }


def sync_project_to_obsidian(
    project: dict[str, Any],
    *,
    related_projects: list[dict[str, Any]] | list[str] | None = None,
    closure: dict[str, Any] | None = None,
    source: str = "manual",
    require_closed: bool = True,
    vault_root: str | Path | None = None,
) -> dict[str, Any]:
    return ObsidianMemorySync(vault_root=vault_root).sync_project(
        project,
        related_projects=related_projects,
        closure=closure,
        source=source,
        require_closed=require_closed,
    )


def obsidian_status(project_id: str, *, vault_root: str | Path | None = None) -> dict[str, Any]:
    return ObsidianMemorySync(vault_root=vault_root).status(project_id)


def obsidian_graph(*, vault_root: str | Path | None = None) -> dict[str, Any]:
    return ObsidianMemorySync(vault_root=vault_root).graph()
