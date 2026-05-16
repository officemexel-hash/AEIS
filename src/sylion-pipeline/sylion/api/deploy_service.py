from __future__ import annotations

from pathlib import Path
from typing import Any

from sylion.execution.deployment_orchestrator import get_deployment_orchestrator
from sylion.project_mode import get_project_mode_store


_BUNDLE_FILE_LABELS = {
    "docker_compose": "docker-compose.yml",
    "deploy_ps1": "deploy.local.ps1",
    "deploy_sh": "deploy.local.sh",
    "terraform_tfvars": "terraform.tfvars.json",
    "ansible_inventory": "ansible_inventory.ini",
    "plan_md": "PLAN.md",
}

_READY_PROJECT_STATUSES = {"completed", "merged"}
_ACTIVE_DEPLOYMENT_STATUSES = {"pending", "in_progress", "failed"}


def _normalize_path(raw_path: Any) -> str:
    path_value = str(raw_path or "").strip()
    if not path_value:
        return ""
    try:
        path = Path(path_value)
        return str(path.resolve()) if path.exists() else str(path)
    except OSError:
        return path_value


def _file_ref(key: str, label: str, raw_path: Any) -> dict[str, Any]:
    path_value = _normalize_path(raw_path)
    exists = bool(path_value) and Path(path_value).is_file()
    size_bytes = Path(path_value).stat().st_size if exists else 0
    return {
        "key": key,
        "label": label,
        "path": path_value,
        "exists": exists,
        "size_bytes": size_bytes,
    }


def _artifact_ref(launch: dict[str, Any]) -> dict[str, Any]:
    artifact_path = _file_ref("artifact", "artifact", launch.get("artifact_path"))
    artifact_path["sha256"] = str(launch.get("artifact_sha256") or "")
    artifact_path["format"] = str(launch.get("artifact_format") or "")
    return artifact_path


def _bundle_ref(launch: dict[str, Any]) -> dict[str, Any]:
    deployment = launch.get("deployment") if isinstance(launch.get("deployment"), dict) else {}
    files = [
        _file_ref(key, label, deployment.get(key))
        for key, label in _BUNDLE_FILE_LABELS.items()
    ]
    existing = sum(1 for item in files if item["exists"])
    if existing == len(files) and files:
        status = "ready"
    elif existing > 0:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "files": files,
    }


def _launch_reason(project: dict[str, Any], launch: dict[str, Any], artifact: dict[str, Any], bundle: dict[str, Any]) -> str:
    project_status = str(project.get("status") or "").strip().lower()
    launch_status = str(launch.get("status") or project_status or "").strip().lower()
    launch_error = str(launch.get("error") or "").strip()
    validation = launch.get("validation") if isinstance(launch.get("validation"), dict) else {}

    if not launch:
        return "Project has not been launched into the pipeline yet."
    if launch_status == "failed":
        return f"Pipeline launch failed: {launch_error}" if launch_error else "Pipeline launch failed before a deployable artifact was recorded."
    if launch_status in {"running", "pending", "in_progress"} and not artifact["path"]:
        return "Pipeline execution is still running and has not recorded an artifact yet."
    if not artifact["path"]:
        return "Launch metadata does not include an artifact path."
    if not artifact["exists"]:
        return "Recorded artifact path does not exist on this backend host."
    if not bool(validation.get("success")):
        return "Validation has not passed for the recorded artifact."
    if bundle["status"] != "ready":
        return "Deployment bundle is incomplete."
    if project_status not in _READY_PROJECT_STATUSES:
        return f"Project status is '{project.get('status', 'unknown')}', so the artifact is not operator-ready."
    return ""


def _launch_action(launch: dict[str, Any], reason: str) -> str:
    launch_status = str(launch.get("status") or "").strip().lower()
    if not launch:
        return "Launch the project with auto_execute enabled and wait for completion."
    if launch_status in {"running", "pending", "in_progress"}:
        return "Wait for the pipeline run to finish before attempting deployment."
    if launch_status == "failed":
        return "Inspect the launch error and re-run the project build before deploying."
    if "Validation has not passed" in reason:
        return "Fix the build or validation failure and re-run the project launch."
    if "Deployment bundle is incomplete" in reason:
        return "Re-run the launch to regenerate docker, Terraform, and inventory files."
    if "artifact path" in reason.lower():
        return "Re-run the project launch so the backend can record a real artifact path."
    return "Review the project launch record before attempting deployment."


def _project_candidate(project: dict[str, Any]) -> dict[str, Any]:
    launch = project.get("launch") if isinstance(project.get("launch"), dict) else {}
    artifact = _artifact_ref(launch)
    bundle = _bundle_ref(launch)
    validation = launch.get("validation") if isinstance(launch.get("validation"), dict) else {}
    audit = launch.get("audit") if isinstance(launch.get("audit"), dict) else {}
    execution_plan = project.get("execution_plan") if isinstance(project.get("execution_plan"), dict) else {}
    reason = _launch_reason(project, launch, artifact, bundle)

    return {
        "project_id": project.get("project_id", ""),
        "title": project.get("title", ""),
        "project_kind": project.get("project_kind", ""),
        "status": project.get("status", ""),
        "phase": project.get("phase", ""),
        "created_at": project.get("created_at"),
        "updated_at": project.get("updated_at"),
        "launch_status": launch.get("status") or project.get("status", ""),
        "launched_at": launch.get("launched_at"),
        "artifact": artifact,
        "bundle": bundle,
        "validation": {
            "success": bool(validation.get("success")),
            "stages": validation.get("stages") if isinstance(validation.get("stages"), dict) else {},
        },
        "audit": {
            "result_count": len(audit.get("results", [])) if isinstance(audit.get("results"), list) else 0,
        },
        "module_output_count": len(launch.get("module_outputs", [])) if isinstance(launch.get("module_outputs"), list) else 0,
        "deployment_mode": execution_plan.get("deployment_mode", ""),
        "provisioning_mode": execution_plan.get("provisioning_mode", ""),
        "pending_question_count": len(project.get("pending_questions", [])) if isinstance(project.get("pending_questions"), list) else 0,
        "reason": reason,
        "recommended_action": "" if not reason else _launch_action(launch, reason),
    }


def _step_summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    completed = sum(1 for step in steps if step.get("status") == "completed")
    in_progress = sum(1 for step in steps if step.get("status") == "in_progress")
    pending = sum(1 for step in steps if step.get("status") == "pending")
    failed = sum(1 for step in steps if step.get("status") == "failed")
    current_step = next((step.get("step_name") for step in steps if step.get("status") != "completed"), "")
    return {
        "total": len(steps),
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "failed": failed,
        "current_step": current_step or "",
    }


def _active_deployments() -> list[dict[str, Any]]:
    orchestrator = get_deployment_orchestrator()
    deployments = orchestrator.list_deployments(limit=100)
    queue: list[dict[str, Any]] = []
    for deployment in deployments:
        status = str(deployment.get("status") or "")
        if status not in _ACTIVE_DEPLOYMENT_STATUSES:
            continue
        steps = orchestrator.get_steps(deployment["deployment_id"])
        queue.append(
            {
                "deployment_id": deployment.get("deployment_id", ""),
                "module_id": deployment.get("module_id", ""),
                "from_stage": deployment.get("from_stage", ""),
                "to_stage": deployment.get("to_stage", ""),
                "strategy": deployment.get("strategy", ""),
                "status": status,
                "started_at": deployment.get("started_at"),
                "step_summary": _step_summary(steps),
            }
        )
    return queue


def build_deploy_summary() -> dict[str, Any]:
    projects = [
        project
        for project in get_project_mode_store().list_projects()
        if str(project.get("status") or "").strip().lower() != "deleted"
    ]
    candidates = [_project_candidate(project) for project in projects]
    ready_projects = [candidate for candidate in candidates if not candidate["reason"]]
    pending_projects = [candidate for candidate in candidates if candidate["reason"]]
    active_deployments = _active_deployments()

    ready_projects.sort(key=lambda item: float(item.get("launched_at") or item.get("updated_at") or 0), reverse=True)
    pending_projects.sort(key=lambda item: float(item.get("updated_at") or item.get("created_at") or 0), reverse=True)

    return {
        "surface_status": "live",
        "stats": {
            "tracked_projects": len(candidates),
            "ready_projects": len(ready_projects),
            "pending_projects": len(pending_projects),
            "active_deployments": len(active_deployments),
        },
        "ready_projects": ready_projects,
        "pending_projects": pending_projects,
        "active_deployments": active_deployments,
    }
