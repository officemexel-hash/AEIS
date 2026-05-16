#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".claude",
    "results",
    "output",
    "workspace_uploads",
    "logs",
}


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def layer_hint_for_backend(first_segment: str) -> str:
    mapping = {
        "aeis": "governance_or_autonomy",
        "api": "integration",
        "cellular": "laboratory",
        "cognitive": "planning_or_reasoning",
        "container": "laboratory_runtime",
        "contracts": "canon_or_contracts",
        "core": "canon_or_kernel",
        "db": "data",
        "devices": "device_surface",
        "efficiency": "governance_or_efficiency",
        "execution": "execution",
        "funding_autopilot": "funding_domain",
        "governance": "governance",
        "grpc": "integration",
        "grpc_stubs": "integration",
        "infra": "integration_or_runtime",
        "integration": "integration",
        "memory": "memory",
        "monitoring": "observability",
        "observability": "observability",
        "pipeline": "coordination",
        "project_mode": "planning_or_workspace",
        "quality": "quality",
        "rebuild": "rebuildability",
        "sdr": "laboratory",
        "security": "security",
        "skills": "skills",
        "surface": "operator_surface",
        "vps": "runtime",
        "worker": "coordination_or_worker",
    }
    return mapping.get(first_segment, "unclassified")


def route_from_page(path: Path, app_root: Path) -> str:
    rel = path.relative_to(app_root).parent
    parts = []
    for part in rel.parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        parts.append(part)
    if not parts:
        return "/"
    return "/" + "/".join(parts)


def collect_backend(sylion_root: Path) -> tuple[list[dict], list[dict]]:
    packages: list[dict] = []
    modules: list[dict] = []

    for package_dir in sorted(p for p in sylion_root.iterdir() if p.is_dir() and p.name != "__pycache__"):
        packages.append(
            {
                "name": package_dir.name,
                "path": str(package_dir),
                "type": "backend_package",
                "layer_hint": layer_hint_for_backend(package_dir.name),
            }
        )

    for py_file in sorted(sylion_root.rglob("*.py")):
        if should_skip(py_file) or py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(sylion_root)
        dotted = "sylion." + ".".join(rel.with_suffix("").parts)
        first_segment = rel.parts[0] if rel.parts else ""
        modules.append(
            {
                "name": dotted,
                "path": str(py_file),
                "type": "backend_module",
                "layer_hint": layer_hint_for_backend(first_segment),
            }
        )

    return packages, modules


def collect_api_routes(api_root: Path) -> list[dict]:
    routes: list[dict] = []
    for py_file in sorted(api_root.rglob("*.py")):
        if should_skip(py_file) or py_file.name == "__init__.py":
            continue
        route_type = "api_route" if py_file.name.endswith("_routes.py") else "api_support"
        routes.append(
            {
                "name": py_file.stem,
                "path": str(py_file),
                "type": route_type,
                "layer_hint": "integration",
            }
        )
    return routes


def collect_frontend_routes(app_root: Path) -> list[dict]:
    routes: list[dict] = []
    for page in sorted(app_root.rglob("page.tsx")):
        if should_skip(page):
            continue
        routes.append(
            {
                "name": route_from_page(page, app_root),
                "path": str(page),
                "type": "frontend_route",
                "layer_hint": "operator_surface",
            }
        )
    return routes


def collect_proto(proto_root: Path) -> list[dict]:
    items: list[dict] = []
    if not proto_root.exists():
        return items
    for proto in sorted(proto_root.rglob("*.proto")):
        if should_skip(proto):
            continue
        items.append(
            {
                "name": proto.stem,
                "path": str(proto),
                "type": "contract_proto",
                "layer_hint": "canon_or_contracts",
            }
        )
    return items


def collect_repo_skills(skills_root: Path) -> list[dict]:
    items: list[dict] = []
    if not skills_root.exists():
        return items
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        items.append(
            {
                "name": skill_dir.name,
                "path": str(skill_md),
                "type": "repo_skill",
                "layer_hint": "skills",
            }
        )
    return items


def collect_root_prompts(root: Path) -> list[dict]:
    items: list[dict] = []
    for txt in sorted(root.glob("*.txt")):
        if "prompt" not in txt.name.lower():
            continue
        items.append(
            {
                "name": txt.stem,
                "path": str(txt),
                "type": "prompt_only",
                "layer_hint": "plan_only_or_prompt",
            }
        )
    return items


def collect_addons(root: Path) -> list[dict]:
    items: list[dict] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        if path.name in {"sylion_devices_addon", "SYLION_Dashboard_V5_ClaudeCode_Package"}:
            items.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "type": "addon",
                    "layer_hint": "device_surface" if "devices" in path.name.lower() else "legacy_or_external_surface",
                }
            )
    return items


def collect_legacy_dashboard(dashboard_root: Path) -> list[dict]:
    items: list[dict] = []
    if not dashboard_root.exists():
        return items
    for py_file in sorted(dashboard_root.rglob("*.py")):
        if should_skip(py_file) or py_file.name == "__init__.py":
            continue
        items.append(
            {
                "name": py_file.stem,
                "path": str(py_file),
                "type": "legacy_dashboard",
                "layer_hint": "operator_surface",
            }
        )
    return items


def collect_entrypoints(root: Path) -> list[dict]:
    items: list[dict] = []
    for name in [
        "start_backend.ps1",
        "start_frontend.ps1",
        "start_backend.bat",
        "start_frontend.bat",
        "start_backend.ps1",
        "HOW_TO_RUN.md",
        "API_REFERENCE.md",
        "CURRENT_STATE.md",
    ]:
        path = root / name
        if path.exists():
            items.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "type": "entrypoint",
                    "layer_hint": "runtime_or_docs",
                }
            )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect AEIS inventory candidates from repo structure.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sylion_root = root / "src" / "sylion-pipeline" / "sylion"
    api_root = sylion_root / "api"
    frontend_root = root / "src" / "sylion-frontend" / "src" / "app"
    proto_root = root / "src" / "sylion-pipeline" / "proto"
    repo_skills_root = root / ".agents" / "skills"
    legacy_dashboard_root = root / "src" / "sylion-pipeline" / "dashboard"

    backend_packages, backend_modules = collect_backend(sylion_root)
    api_routes = collect_api_routes(api_root)
    frontend_routes = collect_frontend_routes(frontend_root)
    proto_files = collect_proto(proto_root)
    repo_skills = collect_repo_skills(repo_skills_root)
    root_prompts = collect_root_prompts(root)
    addons = collect_addons(root)
    legacy_dashboard = collect_legacy_dashboard(legacy_dashboard_root)
    entrypoints = collect_entrypoints(root)

    payload = {
        "root": str(root),
        "counts": {
            "backend_packages": len(backend_packages),
            "backend_modules": len(backend_modules),
            "api_routes": len([x for x in api_routes if x["type"] == "api_route"]),
            "api_support": len([x for x in api_routes if x["type"] == "api_support"]),
            "frontend_routes": len(frontend_routes),
            "proto_files": len(proto_files),
            "repo_skills": len(repo_skills),
            "root_prompts": len(root_prompts),
            "addons": len(addons),
            "legacy_dashboard_files": len(legacy_dashboard),
            "entrypoints": len(entrypoints),
        },
        "backend_packages": backend_packages,
        "backend_modules": backend_modules,
        "api_files": api_routes,
        "frontend_routes": frontend_routes,
        "proto_files": proto_files,
        "repo_skills": repo_skills,
        "root_prompts": root_prompts,
        "addons": addons,
        "legacy_dashboard_files": legacy_dashboard,
        "entrypoints": entrypoints,
    }

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
