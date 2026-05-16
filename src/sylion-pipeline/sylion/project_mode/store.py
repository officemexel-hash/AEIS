from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.project_mode.store")


def _invalidate_project_caches(project_id: str | None = None) -> None:
    """Phase 3 W1.3 — drop workspace.project + council.decision caches.

    Called from every project-state mutation (upsert_project, add_event,
    set_council_enabled, reconcile_council). Failures here must not block
    the write — a stale cache only ever produces a slow read, never a
    wrong read, and the next miss will rebuild from canonical state.

    When ``project_id`` is given we drop only entries for that project.
    """
    try:
        from sylion.infra.cache import get_cache
        cache = get_cache()
        if project_id:
            cache.invalidate(f"sylion:workspace.project:*")
            cache.invalidate(f"sylion:council.decision:*")
        else:
            cache.invalidate("sylion:workspace.project:*")
            cache.invalidate("sylion:council.decision:*")
    except Exception:                              # noqa: BLE001
        log.warning("project cache invalidation failed", exc_info=True)


PROJECT_STAGE_ORDER = [
    "ingest",
    "canon",
    "decomposition",
    "contract_freeze",
    "assignment",
    "build",
    "validate",
    "governance",
    "merge",
    "broadcast",
]

VALID_NOTIFICATION_STATUSES = ("unread", "read", "acknowledged")

DEFAULT_BRAIN_PROMPTS = [
    {
        "prompt_id": "brain_prompt_canon_council",
        "category": "canon",
        "role_name": "canon_council",
        "template": "Review the idea, canon, and prior evidence. Produce a shortlist with tradeoffs and blocking risks.",
    },
    {
        "prompt_id": "brain_prompt_masterplan_architect",
        "category": "masterplan",
        "role_name": "masterplan_architect",
        "template": "Turn the accepted canon into modules, contracts, deployment topology, and worker assignments.",
    },
    {
        "prompt_id": "brain_prompt_audit_security",
        "category": "audit",
        "role_name": "security_officer",
        "template": "Review the diff, contracts, and deployment plan for secrets exposure, auth flaws, injection, and unsafe defaults.",
    },
]


DEFAULT_PROJECT_SKILL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "aeis.intent-classifier": {
        "name": "Intent Classifier",
        "domain": "planning",
        "owner_role": "planner",
        "description": "Classify project intent, domain, size and risk before execution.",
    },
    "aeis.source-of-truth-builder": {
        "name": "Source Of Truth Builder",
        "domain": "canon",
        "owner_role": "planner",
        "description": "Build a canonical source of truth from accepted direction and constraints.",
    },
    "aeis.masterplan-builder": {
        "name": "Masterplan Builder",
        "domain": "planning",
        "owner_role": "architect",
        "description": "Turn source of truth into modules, dependencies, workers, tests and gates.",
    },
    "aeis.local-build-validator": {
        "name": "Local Build Validator",
        "domain": "quality",
        "owner_role": "verifier",
        "description": "Validate local-only builds without external or production side effects.",
    },
    "aeis.audit-trail-writer": {
        "name": "Audit Trail Writer",
        "domain": "governance",
        "owner_role": "governance",
        "description": "Record important project, council, approval and runtime events.",
    },
    "aeis.human-gate-policy": {
        "name": "Human Gate Policy",
        "domain": "governance",
        "owner_role": "governance",
        "description": "Classify actions that require operator approval.",
    },
    "aeis.auth-flow-builder": {
        "name": "Auth Flow Builder",
        "domain": "application",
        "owner_role": "backend_builder",
        "description": "Build registration, login, session and role scaffolds.",
    },
    "aeis.realtime-messaging-builder": {
        "name": "Realtime Messaging Builder",
        "domain": "application",
        "owner_role": "backend_builder",
        "description": "Build room/message workflow scaffolds.",
    },
    "aeis.e2e-test-writer": {
        "name": "E2E Test Writer",
        "domain": "quality",
        "owner_role": "qa_validator",
        "description": "Generate end-to-end and human-like validation checks.",
    },
    "aeis.canvas-ui-builder": {
        "name": "Canvas UI Builder",
        "domain": "frontend",
        "owner_role": "ui_builder",
        "description": "Build interactive canvas and design-tool UI scaffolds.",
    },
    "aeis.funding-program-scorer": {
        "name": "Funding Program Scorer",
        "domain": "funding",
        "owner_role": "funding_analyst",
        "description": "Score grant programs and match them to project profiles.",
    },
    "aeis.funding-document-packager": {
        "name": "Funding Document Packager",
        "domain": "funding",
        "owner_role": "document_builder",
        "description": "Prepare draft funding document packages without final submission.",
    },
    "aeis.mobile-approval-security": {
        "name": "Mobile Approval Security",
        "domain": "operator_mobile",
        "owner_role": "security_reviewer",
        "description": "Check mobile approval token, device binding and deep-link governance.",
    },
    "aeis.offline-checklist-builder": {
        "name": "Offline Checklist Builder",
        "domain": "operator_mobile",
        "owner_role": "offline_state_engineer",
        "description": "Build technician checklists that survive offline mode and replay into the sync queue.",
    },
    "aeis.firmware-attachment-guard": {
        "name": "Firmware Attachment Guard",
        "domain": "operator_mobile",
        "owner_role": "firmware_security_reviewer",
        "description": "Validate firmware attachments, record hashes and require HumanGate before upload or sync.",
    },
    "aeis.photo-evidence-redactor": {
        "name": "Photo Evidence Redactor",
        "domain": "operator_mobile",
        "owner_role": "security_reviewer",
        "description": "Detect and redact possible PII in field photos before evidence synchronization.",
    },
    "aeis.sync-queue-governance": {
        "name": "Sync Queue Governance",
        "domain": "operator_mobile",
        "owner_role": "sync_integrator",
        "description": "Govern offline queue replay, conflict checks, external sync gates and audit evidence.",
    },
    "aeis.operator-console-surface": {
        "name": "Operator Console Surface",
        "domain": "operator",
        "owner_role": "frontend_builder",
        "description": "Build operator dashboard surfaces that explain state, blockers and decisions.",
    },
    "aeis.hr-document-workflow": {
        "name": "HR Document Workflow",
        "domain": "employee_portal",
        "owner_role": "workflow_builder",
        "description": "Build employee document lifecycle, leave requests and role-based HR workflows.",
    },
    "aeis.gdpr-dsr-governance": {
        "name": "GDPR DSR Governance",
        "domain": "compliance",
        "owner_role": "gdpr_security_reviewer",
        "description": "Enforce DPIA, DSR export/erasure HumanGate and retention evidence for PII-heavy portals.",
    },
    "aeis.security-session-policy": {
        "name": "Security Session Policy",
        "domain": "security",
        "owner_role": "identity_builder",
        "description": "Bind SSO/LDAP, session timeout, rate limits, lockout and password policy checks.",
    },
    "aeis.project-management-workflow": {
        "name": "Project Management Workflow",
        "domain": "project_management",
        "owner_role": "workflow_architect",
        "description": "Build portfolio, backlog, sprint, dependency and milestone workflows.",
    },
    "aeis.kanban-gantt-builder": {
        "name": "Kanban Gantt Builder",
        "domain": "project_management",
        "owner_role": "frontend_builder",
        "description": "Build Kanban, roadmap and Gantt-style planning controls.",
    },
    "aeis.budget-risk-control": {
        "name": "Budget Risk Control",
        "domain": "project_management",
        "owner_role": "finance_risk_reviewer",
        "description": "Track project budgets, risk registers, blockers and escalation gates.",
    },
    "aeis.rbac-audit-governance": {
        "name": "RBAC Audit Governance",
        "domain": "governance",
        "owner_role": "security_reviewer",
        "description": "Enforce roles, audit trails and approval boundaries for multi-tenant project systems.",
    },
    "aeis.release-deploy-governance": {
        "name": "Release Deploy Governance",
        "domain": "deployment",
        "owner_role": "release_manager",
        "description": "Control release gates, canary deployment, rollback and external production actions.",
    },
}


BASE_PROJECT_SKILLS = [
    "aeis.intent-classifier",
    "aeis.source-of-truth-builder",
    "aeis.masterplan-builder",
    "aeis.local-build-validator",
    "aeis.audit-trail-writer",
    "aeis.human-gate-policy",
]


PROJECT_KIND_SKILLS: dict[str, list[str]] = {
    "chat_app": ["aeis.auth-flow-builder", "aeis.realtime-messaging-builder", "aeis.e2e-test-writer"],
    "design_tool": ["aeis.canvas-ui-builder", "aeis.e2e-test-writer"],
    "funding": ["aeis.funding-program-scorer", "aeis.funding-document-packager", "aeis.human-gate-policy"],
    "employee_portal": ["aeis.auth-flow-builder", "aeis.hr-document-workflow", "aeis.gdpr-dsr-governance", "aeis.security-session-policy", "aeis.e2e-test-writer"],
    "operator_mobile": [
        "aeis.offline-checklist-builder",
        "aeis.firmware-attachment-guard",
        "aeis.photo-evidence-redactor",
        "aeis.sync-queue-governance",
        "aeis.mobile-approval-security",
        "aeis.human-gate-policy",
        "aeis.e2e-test-writer",
    ],
    "project_management_system": [
        "aeis.project-management-workflow",
        "aeis.kanban-gantt-builder",
        "aeis.budget-risk-control",
        "aeis.rbac-audit-governance",
        "aeis.release-deploy-governance",
        "aeis.human-gate-policy",
        "aeis.e2e-test-writer",
    ],
    "dashboard": ["aeis.operator-console-surface", "aeis.e2e-test-writer"],
    "application": ["aeis.e2e-test-writer"],
}


MODULE_SKILLS: dict[str, list[str]] = {
    "auth-and-rooms": ["aeis.auth-flow-builder"],
    "messaging-realtime": ["aeis.realtime-messaging-builder"],
    "integration_validation": ["aeis.e2e-test-writer", "aeis.local-build-validator"],
    "canvas_kernel": ["aeis.canvas-ui-builder"],
    "operator_console": ["aeis.operator-console-surface"],
    "funding_intake": ["aeis.funding-program-scorer"],
    "program_scoring": ["aeis.funding-program-scorer"],
    "document_package": ["aeis.funding-document-packager"],
    "submission_governance": ["aeis.human-gate-policy", "aeis.funding-document-packager"],
    "auth_users": ["aeis.auth-flow-builder", "aeis.security-session-policy"],
    "role_assignment": ["aeis.auth-flow-builder", "aeis.hr-document-workflow"],
    "document_workflow": ["aeis.hr-document-workflow", "aeis.gdpr-dsr-governance"],
    "leave_request_workflow": ["aeis.hr-document-workflow"],
    "gdpr_dsr": ["aeis.gdpr-dsr-governance", "aeis.human-gate-policy"],
    "security_session_policy": ["aeis.security-session-policy", "aeis.human-gate-policy"],
    "audit_evidence_pack": ["aeis.audit-trail-writer", "aeis.gdpr-dsr-governance"],
    "mobile_shell": ["aeis.offline-checklist-builder", "aeis.mobile-approval-security"],
    "offline_checklists": ["aeis.offline-checklist-builder"],
    "firmware_attachment_guard": ["aeis.firmware-attachment-guard", "aeis.human-gate-policy"],
    "photo_evidence_redaction": ["aeis.photo-evidence-redactor", "aeis.human-gate-policy"],
    "sync_queue": ["aeis.sync-queue-governance", "aeis.human-gate-policy"],
    "device_binding": ["aeis.mobile-approval-security"],
    "secure_approval": ["aeis.mobile-approval-security", "aeis.human-gate-policy"],
    "tenant_workspace": ["aeis.project-management-workflow", "aeis.rbac-audit-governance"],
    "portfolio_dashboard": ["aeis.project-management-workflow", "aeis.kanban-gantt-builder"],
    "kanban_backlog": ["aeis.project-management-workflow", "aeis.kanban-gantt-builder"],
    "gantt_roadmap": ["aeis.kanban-gantt-builder"],
    "resource_capacity": ["aeis.project-management-workflow", "aeis.budget-risk-control"],
    "risk_register": ["aeis.budget-risk-control", "aeis.human-gate-policy"],
    "budget_tracking": ["aeis.budget-risk-control"],
    "notification_center": ["aeis.operator-console-surface"],
    "api_integrations": ["aeis.release-deploy-governance", "aeis.human-gate-policy"],
    "rbac_audit": ["aeis.rbac-audit-governance", "aeis.human-gate-policy"],
    "release_governance": ["aeis.release-deploy-governance", "aeis.human-gate-policy"],
}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _db_path() -> str:
    path = os.environ.get("SYLION_DB_PATH", "sylion_aeis.db")
    if path == ":memory:":
        return path
    # W14 BE-7: redirect onto audit-isolated DB when audit profile active.
    # is_audit_mode() returns False when env unset -> legacy behavior.
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if is_audit_mode():
        return str(resolve_db_path(Path(path)))
    return str(Path(path))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", str(value or "").lower())
        if len(token) >= 3
    }


def _token_similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return round(len(a & b) / max(len(a | b), 1), 4)


def _project_chain_event_type(event_type: str) -> str:
    if event_type == "project.created":
        return "create"
    if event_type.endswith(".transitioned"):
        return "transition"
    return "audit_recorded"


def _record_project_audit_event(event: dict[str, Any]) -> None:
    """Mirror project events into governance chain and unified audit trail."""
    project_id = str(event.get("project_id") or "")
    event_type = str(event.get("event_type") or "project.event")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    actor = str(
        payload.get("actor")
        or payload.get("owner_id")
        or payload.get("requested_by")
        or payload.get("reviewer")
        or "project-mode"
    )
    chain_entry = ""
    try:
        from sylion.governance.audit_chain import get_audit_chain

        chain_entry = get_audit_chain().append_project_event(
            project_id=project_id,
            event_type=_project_chain_event_type(event_type),
            actor=actor,
            payload={
                "project_event_id": event.get("event_id"),
                "project_event_type": event_type,
                "payload": payload,
            },
        )
    except Exception:                              # noqa: BLE001
        log.warning("project governance audit chain mirror failed", exc_info=True)

    try:
        from sylion.security.audit_trail_aggregator import get_audit_trail_aggregator

        get_audit_trail_aggregator().record(
            source="workspace",
            action=event_type,
            actor=actor,
            resource=f"project:{project_id}",
            outcome="success",
            metadata={
                "project_id": project_id,
                "project_event_id": event.get("event_id"),
                "project_event_type": event_type,
                "audit_chain_entry": chain_entry,
                "payload": payload,
            },
            entry_id=f"project.event.{event.get('event_id')}",
        )
    except Exception:                              # noqa: BLE001
        log.warning("project unified audit trail mirror failed", exc_info=True)


class ProjectModeStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _db_path()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout = 30000")
            self._conn.execute("PRAGMA foreign_keys=ON")
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._migrate(self._conn)
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
            self._conn = None

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS project_projects (
                project_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                idea TEXT NOT NULL,
                constraints TEXT NOT NULL DEFAULT '',
                canonical_book_input TEXT NOT NULL DEFAULT '',
                preferred_stack_json TEXT NOT NULL DEFAULT '[]',
                attachments_json TEXT NOT NULL DEFAULT '[]',
                owner_id TEXT NOT NULL DEFAULT 'workspace-default',
                team_id TEXT NOT NULL DEFAULT '',
                project_kind TEXT NOT NULL DEFAULT 'application',
                source_idea_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'definition_in_progress',
                phase TEXT NOT NULL DEFAULT 'canon',
                human_gate_session_id TEXT NOT NULL DEFAULT '',
                approval_book INTEGER NOT NULL DEFAULT 0,
                approval_operating_model INTEGER NOT NULL DEFAULT 0,
                canonical_book TEXT NOT NULL DEFAULT '',
                masterplan TEXT NOT NULL DEFAULT '',
                canon_snapshot_json TEXT NOT NULL DEFAULT '{}',
                memory_policy_json TEXT NOT NULL DEFAULT '{}',
                worker_plan_json TEXT NOT NULL DEFAULT '{}',
                council_plan_json TEXT NOT NULL DEFAULT '{}',
                execution_plan_json TEXT NOT NULL DEFAULT '{}',
                governance_policy_json TEXT NOT NULL DEFAULT '{}',
                audit_plan_json TEXT NOT NULL DEFAULT '{}',
                worker_pool_json TEXT NOT NULL DEFAULT '[]',
                council_members_json TEXT NOT NULL DEFAULT '[]',
                hierarchy_layers_json TEXT NOT NULL DEFAULT '[]',
                custom_inputs_json TEXT NOT NULL DEFAULT '[]',
                launch_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_project_projects_owner ON project_projects(owner_id);
            CREATE INDEX IF NOT EXISTS idx_project_projects_status ON project_projects(status);
            CREATE INDEX IF NOT EXISTS idx_project_projects_phase ON project_projects(phase);

            CREATE TABLE IF NOT EXISTS project_stages (
                stage_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                stage_order INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL NOT NULL DEFAULT 0,
                completed_at REAL NOT NULL DEFAULT 0,
                output_ref TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_stages_project ON project_stages(project_id, stage_order);

            CREATE TABLE IF NOT EXISTS project_questions (
                question_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                question_key TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                context TEXT NOT NULL,
                options_json TEXT NOT NULL DEFAULT '[]',
                free_text_allowed INTEGER NOT NULL DEFAULT 1,
                timeout_seconds INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'council',
                sort_order INTEGER NOT NULL DEFAULT 0,
                asked_at REAL NOT NULL,
                answered_at REAL NOT NULL DEFAULT 0,
                selected_choice_id TEXT NOT NULL DEFAULT '',
                selected_value TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_questions_project ON project_questions(project_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_project_questions_status ON project_questions(project_id, status);

            CREATE TABLE IF NOT EXISTS project_answers (
                answer_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                choice_id TEXT NOT NULL DEFAULT '',
                value TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'human',
                rationale TEXT NOT NULL DEFAULT '',
                answered_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES project_questions(question_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_answers_project ON project_answers(project_id, answered_at);

            CREATE TABLE IF NOT EXISTS project_decisions (
                decision_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                question_id TEXT NOT NULL DEFAULT '',
                stage_name TEXT NOT NULL,
                decision_key TEXT NOT NULL,
                decision_value TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '',
                consequences TEXT NOT NULL DEFAULT '',
                evidence_ref TEXT NOT NULL DEFAULT '',
                effects_json TEXT NOT NULL DEFAULT '{}',
                is_custom INTEGER NOT NULL DEFAULT 0,
                frozen INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_decisions_project ON project_decisions(project_id, created_at);

            CREATE TABLE IF NOT EXISTS project_canon_entries (
                canon_entry_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                entry_key TEXT NOT NULL,
                entry_value TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                supersedes_id TEXT NOT NULL DEFAULT '',
                frozen_at REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_canon_entries_project ON project_canon_entries(project_id, entry_key);

            CREATE TABLE IF NOT EXISTS project_masterplans (
                masterplan_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                plan_json TEXT NOT NULL DEFAULT '{}',
                module_graph_json TEXT NOT NULL DEFAULT '{}',
                deployment_topology_json TEXT NOT NULL DEFAULT '{}',
                team_composition_json TEXT NOT NULL DEFAULT '{}',
                hierarchy_json TEXT NOT NULL DEFAULT '[]',
                audit_json TEXT NOT NULL DEFAULT '{}',
                frozen_at REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_masterplans_project ON project_masterplans(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS project_modules (
                module_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                masterplan_id TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                spec_json TEXT NOT NULL DEFAULT '{}',
                worker_id TEXT NOT NULL DEFAULT '',
                docker_profile TEXT NOT NULL DEFAULT '',
                host_target TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'planned',
                depends_on_json TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_modules_project ON project_modules(project_id, name);

            CREATE TABLE IF NOT EXISTS project_events (
                event_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                emitted_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_events_project ON project_events(project_id, emitted_at DESC);

            CREATE TABLE IF NOT EXISTS project_worker_pool (
                worker_entry_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                worker_type TEXT NOT NULL,
                endpoint TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                cost_per_1k REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_worker_pool_project ON project_worker_pool(project_id);

            CREATE TABLE IF NOT EXISTS project_council_members (
                council_member_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                member_role TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                voting_weight REAL NOT NULL DEFAULT 1.0,
                config_json TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_council_members_project ON project_council_members(project_id);

            CREATE TABLE IF NOT EXISTS project_council_votes (
                council_vote_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                proposal TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                vote_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_council_votes_project ON project_council_votes(project_id, vote_at DESC);

            CREATE TABLE IF NOT EXISTS project_hierarchy_layers (
                layer_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                layer_name TEXT NOT NULL,
                layer_order INTEGER NOT NULL DEFAULT 0,
                model_id TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                role_prompt TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_hierarchy_layers_project ON project_hierarchy_layers(project_id, layer_order);

            CREATE TABLE IF NOT EXISTS project_autonomy_config (
                config_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                level TEXT NOT NULL,
                overrides_json TEXT NOT NULL DEFAULT '{}',
                updated_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_audit_results (
                audit_result_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                module_id TEXT NOT NULL DEFAULT '',
                audit_type TEXT NOT NULL,
                status TEXT NOT NULL,
                findings_json TEXT NOT NULL DEFAULT '[]',
                executed_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_audit_results_project ON project_audit_results(project_id, executed_at DESC);

            CREATE TABLE IF NOT EXISTS project_cost_ledger (
                cost_entry_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0,
                running_total REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_cost_ledger_project ON project_cost_ledger(project_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS project_notifications (
                notification_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL DEFAULT '',
                owner_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'info',
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                link_to TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'unread',
                created_at REAL NOT NULL,
                read_at REAL NOT NULL DEFAULT 0,
                acknowledged_at REAL NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_project_notifications_owner ON project_notifications(owner_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_project_notifications_project ON project_notifications(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS project_skill_reuse_log (
                skill_reuse_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                module_id TEXT NOT NULL DEFAULT '',
                reused_skill_id TEXT NOT NULL,
                similarity_score REAL NOT NULL DEFAULT 0,
                adaptation_notes TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS brain_memory_entries (
                memory_entry_id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                project_id TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                embedding_id TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_brain_memory_project ON brain_memory_entries(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS brain_embeddings (
                embedding_id TEXT PRIMARY KEY,
                text_hash TEXT NOT NULL,
                embedding_json TEXT NOT NULL DEFAULT '[]',
                dim INTEGER NOT NULL DEFAULT 0,
                source_table TEXT NOT NULL DEFAULT '',
                source_id TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS brain_prompt_library (
                prompt_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                role_name TEXT NOT NULL,
                template TEXT NOT NULL,
                last_used_at REAL NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0,
                usage_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS brain_lora_datasets (
                dataset_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                dataset_path TEXT NOT NULL DEFAULT '',
                sample_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_brain_lora_datasets_project ON brain_lora_datasets(project_id);

            CREATE TABLE IF NOT EXISTS brain_lora_adapters (
                adapter_id TEXT PRIMARY KEY,
                base_model TEXT NOT NULL,
                adapter_path TEXT NOT NULL DEFAULT '',
                training_project_ids_json TEXT NOT NULL DEFAULT '[]',
                eval_score REAL NOT NULL DEFAULT 0,
                promoted INTEGER NOT NULL DEFAULT 0,
                promoted_at REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            -- Phase 3 W1.2: secondary indexes for hot lookup paths.
            CREATE INDEX IF NOT EXISTS idx_project_council_votes_member   ON project_council_votes(member_id, vote_at DESC);
            CREATE INDEX IF NOT EXISTS idx_project_audit_results_module   ON project_audit_results(project_id, module_id, executed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_project_skill_reuse_log_proj   ON project_skill_reuse_log(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_project_skill_reuse_log_module ON project_skill_reuse_log(module_id);
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(project_notifications)").fetchall()
        }
        if "acknowledged_at" not in columns:
            conn.execute(
                "ALTER TABLE project_notifications "
                "ADD COLUMN acknowledged_at REAL NOT NULL DEFAULT 0"
            )
        # W14 BE-6 round_meta — additive freeze/authorize columns. Each
        # ALTER is wrapped in try/except so re-running ``_migrate`` on an
        # already-migrated DB is a no-op rather than raising
        # ``OperationalError: duplicate column name``.
        project_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(project_projects)").fetchall()
        }
        for col, ddl in (
            ("canon_frozen_at", "ALTER TABLE project_projects ADD COLUMN canon_frozen_at REAL DEFAULT NULL"),
            ("masterplan_frozen_at", "ALTER TABLE project_projects ADD COLUMN masterplan_frozen_at REAL DEFAULT NULL"),
            ("build_authorized_at", "ALTER TABLE project_projects ADD COLUMN build_authorized_at REAL DEFAULT NULL"),
            ("canon_hash", "ALTER TABLE project_projects ADD COLUMN canon_hash TEXT NOT NULL DEFAULT ''"),
            ("masterplan_hash", "ALTER TABLE project_projects ADD COLUMN masterplan_hash TEXT NOT NULL DEFAULT ''"),
            ("cost_cap_usd", "ALTER TABLE project_projects ADD COLUMN cost_cap_usd REAL DEFAULT NULL"),
            ("autonomy_level", "ALTER TABLE project_projects ADD COLUMN autonomy_level TEXT NOT NULL DEFAULT ''"),
            ("source_idea_id", "ALTER TABLE project_projects ADD COLUMN source_idea_id TEXT NOT NULL DEFAULT ''"),
        ):
            if col in project_columns:
                continue
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                # Column already exists (race or partial migration) — safe to ignore.
                log.debug("project_projects column %s already present", col, exc_info=True)
        for prompt in DEFAULT_BRAIN_PROMPTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO brain_prompt_library (
                    prompt_id, category, role_name, template, last_used_at, success_rate, usage_count, active
                ) VALUES (?, ?, ?, ?, 0, 0, 0, 1)
                """,
                (prompt["prompt_id"], prompt["category"], prompt["role_name"], prompt["template"]),
            )
        conn.commit()

    def _ensure_stage_state(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        stages = project.get("stage_state") or []
        by_name = {item.get("stage"): dict(item) for item in stages if item.get("stage")}
        now = _now()
        final = []
        for idx, stage_name in enumerate(PROJECT_STAGE_ORDER):
            item = by_name.get(stage_name, {})
            final.append(
                {
                    "stage_id": item.get("stage_id") or f"{project['project_id']}::{stage_name}",
                    "stage": stage_name,
                    "status": item.get("status") or ("completed" if stage_name == "ingest" else "pending"),
                    "updated_at": float(item.get("updated_at") or now),
                    "started_at": float(item.get("started_at") or 0),
                    "completed_at": float(item.get("completed_at") or 0),
                    "output_ref": item.get("output_ref", ""),
                    "metadata": item.get("metadata") or {},
                }
            )
        project["stage_state"] = final
        return final

    def _ensure_questions(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        now = _now()
        questions = []
        for index, question in enumerate(project.get("questions") or []):
            normalized = dict(question)
            normalized["question_id"] = normalized.get("question_id") or _uid("pq")
            normalized["status"] = normalized.get("status") or "pending"
            normalized["asked_at"] = float(normalized.get("asked_at") or now)
            normalized["answered_at"] = float(normalized.get("answered_at") or 0)
            normalized["source"] = normalized.get("source") or "council"
            normalized["sort_order"] = int(normalized.get("sort_order", index))
            normalized["free_text_allowed"] = bool(normalized.get("free_text_allowed", True))
            normalized["timeout_seconds"] = int(normalized.get("timeout_seconds", 0))
            normalized["choices"] = [
                {
                    **dict(choice),
                    "choice_id": dict(choice).get("choice_id") or _uid("pqc"),
                }
                for choice in normalized.get("choices") or []
            ]
            questions.append(normalized)
        project["questions"] = questions
        return questions

    def _ensure_answers(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        answers = []
        for answer in project.get("answers") or []:
            normalized = dict(answer)
            normalized["answer_id"] = normalized.get("answer_id") or _uid("answer")
            normalized["answered_at"] = float(normalized.get("answered_at") or _now())
            answers.append(normalized)
        project["answers"] = answers
        return answers

    def _ensure_decisions(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        decisions = []
        for decision in project.get("decisions") or []:
            normalized = dict(decision)
            normalized["decision_id"] = normalized.get("decision_id") or _uid("decision")
            normalized["selected_at"] = float(normalized.get("selected_at") or _now())
            normalized["effects"] = normalized.get("effects") or {}
            decisions.append(normalized)
        project["decisions"] = decisions
        return decisions

    def _derive_modules(self, project: dict[str, Any], masterplan_id: str) -> list[dict[str, Any]]:
        modules = project.get("modules") or []
        execution = project.get("execution_plan") or {}
        deployment_mode = str(execution.get("deployment_mode") or "")
        try:
            local_workers = int(execution.get("local_docker_workers", 0) or 0)
        except (TypeError, ValueError):
            local_workers = 0
        try:
            vps_workers = int(execution.get("vps_workers", 0) or 0)
        except (TypeError, ValueError):
            vps_workers = 0

        def _module_host_target(index: int) -> str:
            if vps_workers <= 0:
                return "local"
            return "local" if index < local_workers else "vps"

        if not modules:
            for idx, name in enumerate((project.get("worker_plan") or {}).get("modules") or []):
                modules.append(
                    {
                        "module_id": f"{project['project_id']}::module::{idx}",
                        "name": name,
                        "status": "planned",
                        "worker_id": "",
                        "docker_profile": deployment_mode,
                        "host_target": _module_host_target(idx),
                        "depends_on": [],
                        "spec": {
                            "role": "module",
                            "recommended_stack": project.get("preferred_stack") or [],
                            "project_kind": project.get("project_kind", ""),
                        },
                        "created_at": project.get("created_at") or _now(),
                        "updated_at": project.get("updated_at") or _now(),
                        "masterplan_id": masterplan_id,
                    }
                )
        else:
            for idx, module in enumerate(modules):
                module.setdefault("module_id", _uid("module"))
                module.setdefault("masterplan_id", masterplan_id)
                module.setdefault("status", "planned")
                module.setdefault("worker_id", "")
                module.setdefault("docker_profile", "")
                module.setdefault("host_target", "")
                module.setdefault("depends_on", [])
                module.setdefault("spec", {})
                module.setdefault("created_at", project.get("created_at") or _now())
                module.setdefault("updated_at", project.get("updated_at") or _now())
                desired_host_target = _module_host_target(idx)
                if module.get("docker_profile") != deployment_mode or module.get("host_target") != desired_host_target:
                    module["docker_profile"] = deployment_mode
                    module["host_target"] = desired_host_target
                    module["updated_at"] = _now()
        project["modules"] = modules
        return modules

    def _ensure_default_skills_registered(self, skill_ids: set[str]) -> None:
        if not skill_ids:
            return
        try:
            from sylion.skills.registry import get_skills_registry

            registry = get_skills_registry(db_path=self.db_path)
            for skill_id in sorted(skill_ids):
                if registry.get(skill_id):
                    continue
                definition = DEFAULT_PROJECT_SKILL_DEFINITIONS.get(skill_id, {})
                registry.register_skill(
                    {
                        "skill_id": skill_id,
                        "name": definition.get("name", skill_id),
                        "domain": definition.get("domain", "project"),
                        "owner_role": definition.get("owner_role", "aeis"),
                        "description": definition.get("description", ""),
                        "lifecycle": "PUBLISHED",
                        "runtime_spec": {
                            "skill_id": skill_id,
                            "name": definition.get("name", skill_id),
                            "domain": definition.get("domain", "project"),
                            "owner_role": definition.get("owner_role", "aeis"),
                            "lifecycle": "PUBLISHED",
                            "requires_hg": False,
                            "parallel_safe": True,
                            "idempotent": True,
                        },
                    },
                    persist=True,
                )
        except Exception:
            log.warning("default project skill registration failed", exc_info=True)

    def _default_skill_ids_for_module(self, project: dict[str, Any], module_name: str) -> list[str]:
        skill_ids: list[str] = []
        for skill_id in BASE_PROJECT_SKILLS:
            if skill_id not in skill_ids:
                skill_ids.append(skill_id)
        for skill_id in PROJECT_KIND_SKILLS.get(project.get("project_kind", "application"), PROJECT_KIND_SKILLS["application"]):
            if skill_id not in skill_ids:
                skill_ids.append(skill_id)
        normalized_name = str(module_name or "").lower().replace("-", "_")
        for key, module_skill_ids in MODULE_SKILLS.items():
            if key in normalized_name:
                for skill_id in module_skill_ids:
                    if skill_id not in skill_ids:
                        skill_ids.append(skill_id)
        return skill_ids

    def _similar_project_skill_hints(self, conn: sqlite3.Connection, project: dict[str, Any]) -> list[dict[str, Any]]:
        if not bool((project.get("memory_policy") or {}).get("similarity_search", True)):
            return []
        rows = conn.execute(
            """
            SELECT project_id, title, idea, project_kind, updated_at
            FROM project_projects
            WHERE project_id != ?
            ORDER BY updated_at DESC
            LIMIT 25
            """,
            (project["project_id"],),
        ).fetchall()
        hints: list[dict[str, Any]] = []
        current_text = f"{project.get('title', '')}\n{project.get('idea', '')}\n{project.get('project_kind', '')}"
        for row in rows:
            candidate_text = f"{row['title']}\n{row['idea']}\n{row['project_kind']}"
            score = _token_similarity(current_text, candidate_text)
            if row["project_kind"] == project.get("project_kind"):
                score = min(1.0, score + 0.18)
            if score < 0.22:
                continue
            module_rows = conn.execute(
                "SELECT module_id, name, spec_json FROM project_modules WHERE project_id = ?",
                (row["project_id"],),
            ).fetchall()
            module_skills: dict[str, list[str]] = {}
            for module_row in module_rows:
                spec = _json_loads(module_row["spec_json"], {})
                skills = list(spec.get("skills") or [])
                for binding in spec.get("skill_bindings") or []:
                    skill_id = str((binding or {}).get("skill_id", ""))
                    if skill_id and skill_id not in skills:
                        skills.append(skill_id)
                if skills:
                    module_skills[str(module_row["name"])] = skills
            if module_skills:
                hints.append(
                    {
                        "project_id": row["project_id"],
                        "title": row["title"],
                        "project_kind": row["project_kind"],
                        "similarity_score": round(score, 4),
                        "module_skills": module_skills,
                    }
                )
        return hints[:5]

    def _apply_skill_memory_bindings(self, conn: sqlite3.Connection, project: dict[str, Any]) -> None:
        hints = self._similar_project_skill_hints(conn, project)
        memory_policy = dict(project.get("memory_policy") or {})
        memory_policy["similar_projects"] = [
            {
                "project_id": hint["project_id"],
                "title": hint["title"],
                "project_kind": hint["project_kind"],
                "similarity_score": hint["similarity_score"],
            }
            for hint in hints
        ]

        all_skill_ids: set[str] = set()
        reused_skill_ids: set[str] = set()
        for module in project.get("modules") or []:
            module_name = str(module.get("name", ""))
            spec = dict(module.get("spec") or {})
            preserved = [
                dict(binding)
                for binding in spec.get("skill_bindings") or []
                if dict(binding).get("source") not in {"default", "memory"}
            ]
            bindings: list[dict[str, Any]] = preserved
            seen = {str(binding.get("skill_id")) for binding in bindings if binding.get("skill_id")}

            for skill_id in self._default_skill_ids_for_module(project, module_name):
                if skill_id in seen:
                    continue
                seen.add(skill_id)
                all_skill_ids.add(skill_id)
                bindings.append(
                    {
                        "skill_id": skill_id,
                        "source": "default",
                        "reason": f"matched project_kind={project.get('project_kind', 'application')} module={module_name}",
                    }
                )

            for hint in hints:
                candidate_skills = list((hint.get("module_skills") or {}).get(module_name) or [])
                for skill_id in candidate_skills:
                    if skill_id in seen:
                        for binding in bindings:
                            if binding.get("skill_id") != skill_id:
                                continue
                            evidence = binding.setdefault("memory_reuse", [])
                            evidence.append(
                                {
                                    "reused_from_project_id": hint["project_id"],
                                    "similarity_score": hint["similarity_score"],
                                    "module_name": module_name,
                                }
                            )
                            reused_skill_ids.add(skill_id)
                            break
                        continue
                    seen.add(skill_id)
                    all_skill_ids.add(skill_id)
                    reused_skill_ids.add(skill_id)
                    bindings.append(
                        {
                            "skill_id": skill_id,
                            "source": "memory",
                            "reused_from_project_id": hint["project_id"],
                            "similarity_score": hint["similarity_score"],
                            "reason": f"reused from similar project module={module_name}",
                        }
                    )

            spec["skill_bindings"] = bindings
            spec["skills"] = [binding["skill_id"] for binding in bindings if binding.get("skill_id")]
            module["spec"] = spec

        memory_policy["reused_skill_ids"] = sorted(reused_skill_ids)
        memory_policy["skill_binding_count"] = sum(len((module.get("spec") or {}).get("skill_bindings") or []) for module in project.get("modules") or [])
        project["memory_policy"] = memory_policy
        self._ensure_default_skills_registered(all_skill_ids)

    def _sync_skill_reuse_log(self, conn: sqlite3.Connection, project: dict[str, Any]) -> None:
        project_id = project["project_id"]
        conn.execute("DELETE FROM project_skill_reuse_log WHERE project_id = ?", (project_id,))
        for module in project.get("modules") or []:
            module_id = module.get("module_id", "")
            module_name = str(module.get("name", ""))
            for binding in (module.get("spec") or {}).get("skill_bindings") or []:
                skill_id = str(binding.get("skill_id") or "")
                if not skill_id:
                    continue
                evidence = list(binding.get("memory_reuse") or [])
                if binding.get("source") == "memory":
                    evidence.append(
                        {
                            "reused_from_project_id": binding.get("reused_from_project_id", ""),
                            "similarity_score": binding.get("similarity_score", 0),
                            "module_name": module_name,
                        }
                    )
                if binding.get("source") == "default" and not evidence:
                    evidence.append(
                        {
                            "reused_from_project_id": "",
                            "similarity_score": 1.0,
                            "module_name": module_name,
                            "match_source": "manifest",
                        }
                    )
                if not evidence:
                    continue
                for item in evidence:
                    conn.execute(
                        """
                        INSERT INTO project_skill_reuse_log (
                            skill_reuse_id, project_id, module_id, reused_skill_id,
                            similarity_score, adaptation_notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _uid("skillreuse"),
                            project_id,
                            module_id,
                            skill_id,
                            float((item or {}).get("similarity_score") or 0),
                            str(
                                binding.get("reason")
                                or (
                                    "matched by project skill manifest"
                                    if (item or {}).get("match_source") == "manifest"
                                    else f"memory confirmed by project {(item or {}).get('reused_from_project_id', '')}"
                                )
                            ),
                            float(project.get("updated_at") or _now()),
                        ),
                    )

    def _derive_worker_pool(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        """Wave A4 (RB-002): rebuild worker_pool from execution_plan every call.

        Old behaviour returned a cached pool whenever the project dict carried
        any prior `worker_pool` entries. That meant changes to
        execution_plan (e.g. scaling vps_workers from 2 to 0) never rebuilt
        the pool, leaving orphaned slots wired to a stale topology.

        New contract:
        - Canonical pool is always derived from `execution_plan` + `worker_plan.roles`.
        - Existing entries are matched by `worker_entry_id`; their mutable
          metadata (model_id, cost_per_1k, config) is preserved when the slot
          still exists in the new plan.
        - Entries whose ids are no longer in the canonical plan are dropped.
        - The dropped ids surface on `project["worker_pool_orphans"]` so callers
          (e.g. reconcile_worker_pool, worker registry) can unregister them.
        """
        existing = {
            e.get("worker_entry_id"): e
            for e in (project.get("worker_pool") or [])
            if e.get("worker_entry_id")
        }

        execution = project.get("execution_plan") or {}
        roles = (project.get("worker_plan") or {}).get("roles") or []
        local_count = int(execution.get("local_docker_workers", 0))
        vps_count = int(execution.get("vps_workers", 0))
        project_id = project["project_id"]
        derived: list[dict[str, Any]] = []
        canonical_ids: set[str] = set()

        for idx in range(max(local_count, len(roles))):
            entry_id = f"{project_id}::local::{idx}"
            canonical_ids.add(entry_id)
            base = {
                "worker_entry_id": entry_id,
                "name": f"local-docker-{idx + 1}",
                "worker_type": "docker",
                "endpoint": "localhost",
                "model_id": "",
                "role": roles[idx] if idx < len(roles) else "coder",
                "cost_per_1k": 0.0,
                "active": True,
                "config": {"lane": "local", "auto_provision": False},
            }
            prior = existing.get(entry_id)
            if prior:
                base["model_id"] = prior.get("model_id", base["model_id"])
                base["cost_per_1k"] = prior.get("cost_per_1k", base["cost_per_1k"])
                base["active"] = bool(prior.get("active", True))
                merged_cfg = dict(base["config"])
                merged_cfg.update(prior.get("config") or {})
                base["config"] = merged_cfg
            derived.append(base)

        for idx in range(vps_count):
            entry_id = f"{project_id}::vps::{idx}"
            canonical_ids.add(entry_id)
            base = {
                "worker_entry_id": entry_id,
                "name": f"vps-worker-{idx + 1}",
                "worker_type": "vps",
                "endpoint": "host_b" if idx == 0 else f"vps-{idx + 1}",
                "model_id": "",
                "role": roles[(idx + local_count) % len(roles)] if roles else "coder",
                "cost_per_1k": 0.0,
                "active": True,
                "config": {"lane": "remote", "auto_provision": bool(execution.get("auto_provision"))},
            }
            prior = existing.get(entry_id)
            if prior:
                base["model_id"] = prior.get("model_id", base["model_id"])
                base["cost_per_1k"] = prior.get("cost_per_1k", base["cost_per_1k"])
                base["active"] = bool(prior.get("active", True))
                merged_cfg = dict(base["config"])
                merged_cfg.update(prior.get("config") or {})
                base["config"] = merged_cfg
            derived.append(base)

        project["worker_pool"] = derived
        project["worker_pool_orphans"] = sorted(
            entry_id for entry_id in existing if entry_id not in canonical_ids
        )
        return derived

    def _derive_council_members(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        # Wave A3 (RB-004): if council_plan.enabled is explicitly False, all
        # members must be inactive regardless of active_size or member list.
        council_plan = project.get("council_plan") or {}
        plan_enabled = bool(council_plan.get("enabled", True))

        members = project.get("council_members") or []
        if members:
            for member in members:
                member.setdefault("council_member_id", _uid("council"))
                member.setdefault("provider", "")
                member.setdefault("model_id", "")
                member.setdefault("voting_weight", 1.0)
                member.setdefault("config", {})
                member.setdefault("active", True)
                if "rank" in member and "rank" not in member["config"]:
                    member["config"]["rank"] = member["rank"]
                if "role" in member and "member_role" not in member:
                    member["member_role"] = member["role"]
                if not plan_enabled:
                    member["active"] = False
            project["council_members"] = members
            return members
        derived = []
        active_size = int(council_plan.get(
            "active_size", council_plan.get("suggested_size", 0) or 0,
        ))
        for idx, member in enumerate(council_plan.get("members") or []):
            preferred = list(member.get("preferred_models") or [])
            model_id = member.get("model_id") or (preferred[0] if preferred else "")
            if member.get("provider"):
                provider = str(member.get("provider") or "")
            else:
                try:
                    from sylion.cognitive.llm_runtime import infer_provider_for_model

                    provider = infer_provider_for_model(str(model_id))
                except Exception:
                    provider = "ollama" if ":" in str(model_id) else ""
            weight = float(member.get("voting_weight") or member.get("weight") or 1.0)
            rank = member.get("rank", "primary")
            derived.append(
                {
                    "council_member_id": f"{project['project_id']}::council::{idx}",
                    "member_role": member.get("role", f"member_{idx + 1}"),
                    "provider": provider,
                    "model_id": model_id,
                    "voting_weight": weight,
                    "config": {
                        "rank": rank,
                        "responsibility": member.get("responsibility", ""),
                        "preferred_models": preferred,
                        "required_signature": bool(member.get("required_signature", False)),
                        "approval_scope": member.get("approval_scope", ""),
                    },
                    "active": plan_enabled and idx < active_size,
                }
            )
        project["council_members"] = derived
        return derived

    def _derive_hierarchy_layers(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        layers = project.get("hierarchy_layers") or []
        if layers:
            for idx, layer in enumerate(layers):
                layer.setdefault("layer_id", f"{project['project_id']}::layer::{idx}")
                layer.setdefault("layer_order", idx)
                layer.setdefault("model_id", "")
                layer.setdefault("provider", "")
                layer.setdefault("role_prompt", "")
                layer.setdefault("config", {})
                layer.setdefault("active", True)
            project["hierarchy_layers"] = layers
            return layers
        derived = []
        for idx, layer_name in enumerate((project.get("governance_policy") or {}).get("decision_layers") or []):
            derived.append(
                {
                    "layer_id": f"{project['project_id']}::layer::{idx}",
                    "layer_name": layer_name,
                    "layer_order": idx,
                    "model_id": "",
                    "provider": "",
                    "role_prompt": "",
                    "config": {},
                    "active": True,
                }
            )
        project["hierarchy_layers"] = derived
        return derived

    def _ensure_project_defaults(self, project: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        project.setdefault("project_id", _uid("project"))
        project.setdefault("title", project.get("idea", "Project Kickoff")[:72] or "Project Kickoff")
        project.setdefault("idea", "")
        project.setdefault("constraints", "")
        project.setdefault("canonical_book_input", "")
        project.setdefault("preferred_stack", [])
        project.setdefault("attachments", [])
        project.setdefault("owner_id", "workspace-default")
        project.setdefault("team_id", "")
        project.setdefault("project_kind", "application")
        project.setdefault("source_idea_id", "")
        project.setdefault("status", "definition_in_progress")
        project.setdefault("phase", "canon")
        project.setdefault("human_gate_session_id", "")
        project.setdefault("canon_snapshot", {})
        project.setdefault("memory_policy", {})
        project.setdefault("worker_plan", {})
        project.setdefault("council_plan", {})
        project.setdefault("execution_plan", {})
        project.setdefault("governance_policy", {})
        project.setdefault("audit_plan", {
            "masterplan_mode": "parallel",
            "module_mode": "sequential",
            "override": "configurable",
            "auditors": ["security_officer", "quality_perf_reviewer", "compliance_officer", "dependency_guardian", "ux_reviewer", "doc_officer"],
        })
        project.setdefault("approvals", {"book": False, "operating_model": False})
        project.setdefault("custom_inputs", [])
        project.setdefault("launch", {})
        project.setdefault("canonical_book", "")
        project.setdefault("masterplan", "")
        project.setdefault("created_at", now)
        project.setdefault("updated_at", now)
        self._ensure_stage_state(project)
        self._ensure_questions(project)
        self._ensure_answers(project)
        self._ensure_decisions(project)
        masterplan_id = project.get("masterplan_id") or f"{project['project_id']}::masterplan"
        project["masterplan_id"] = masterplan_id
        self._derive_modules(project, masterplan_id)
        self._derive_worker_pool(project)
        self._derive_council_members(project)
        self._derive_hierarchy_layers(project)
        return project

    def upsert_project(self, project: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._ensure_project_defaults(project)
            conn = self._get_conn()
            self._apply_skill_memory_bindings(conn, project)
            with conn:
                # W14 BE-6 round_meta freeze/authorize columns. ``None`` is
                # passed through for the timestamp fields to preserve the
                # "not yet frozen" semantic — sqlite stores it as NULL.
                _canon_frozen_at = project.get("canon_frozen_at")
                _masterplan_frozen_at = project.get("masterplan_frozen_at")
                _build_authorized_at = project.get("build_authorized_at")
                _cost_cap_usd = project.get("cost_cap_usd")
                conn.execute(
                    """
                    INSERT INTO project_projects (
                        project_id, title, idea, constraints, canonical_book_input, preferred_stack_json,
                        attachments_json, owner_id, team_id, project_kind, source_idea_id, status, phase,
                        human_gate_session_id, approval_book, approval_operating_model,
                        canonical_book, masterplan, canon_snapshot_json, memory_policy_json,
                        worker_plan_json, council_plan_json, execution_plan_json,
                        governance_policy_json, audit_plan_json, worker_pool_json,
                        council_members_json, hierarchy_layers_json, custom_inputs_json,
                        launch_json, created_at, updated_at,
                        canon_frozen_at, masterplan_frozen_at, build_authorized_at,
                        canon_hash, masterplan_hash, cost_cap_usd, autonomy_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        title=excluded.title,
                        idea=excluded.idea,
                        constraints=excluded.constraints,
                        canonical_book_input=excluded.canonical_book_input,
                        preferred_stack_json=excluded.preferred_stack_json,
                        attachments_json=excluded.attachments_json,
                        owner_id=excluded.owner_id,
                        team_id=excluded.team_id,
                        project_kind=excluded.project_kind,
                        source_idea_id=excluded.source_idea_id,
                        status=excluded.status,
                        phase=excluded.phase,
                        human_gate_session_id=excluded.human_gate_session_id,
                        approval_book=excluded.approval_book,
                        approval_operating_model=excluded.approval_operating_model,
                        canonical_book=excluded.canonical_book,
                        masterplan=excluded.masterplan,
                        canon_snapshot_json=excluded.canon_snapshot_json,
                        memory_policy_json=excluded.memory_policy_json,
                        worker_plan_json=excluded.worker_plan_json,
                        council_plan_json=excluded.council_plan_json,
                        execution_plan_json=excluded.execution_plan_json,
                        governance_policy_json=excluded.governance_policy_json,
                        audit_plan_json=excluded.audit_plan_json,
                        worker_pool_json=excluded.worker_pool_json,
                        council_members_json=excluded.council_members_json,
                        hierarchy_layers_json=excluded.hierarchy_layers_json,
                        custom_inputs_json=excluded.custom_inputs_json,
                        launch_json=excluded.launch_json,
                        updated_at=excluded.updated_at,
                        canon_frozen_at=excluded.canon_frozen_at,
                        masterplan_frozen_at=excluded.masterplan_frozen_at,
                        build_authorized_at=excluded.build_authorized_at,
                        canon_hash=excluded.canon_hash,
                        masterplan_hash=excluded.masterplan_hash,
                        cost_cap_usd=excluded.cost_cap_usd,
                        autonomy_level=excluded.autonomy_level
                    """,
                    (
                        project["project_id"],
                        project["title"],
                        project["idea"],
                        project["constraints"],
                        project.get("canonical_book_input", ""),
                        _json_dumps(project.get("preferred_stack") or []),
                        _json_dumps(project.get("attachments") or []),
                        project.get("owner_id", "workspace-default"),
                        project.get("team_id", ""),
                        project.get("project_kind", "application"),
                        project.get("source_idea_id", ""),
                        project.get("status", "definition_in_progress"),
                        project.get("phase", "canon"),
                        project.get("human_gate_session_id", ""),
                        1 if (project.get("approvals") or {}).get("book") else 0,
                        1 if (project.get("approvals") or {}).get("operating_model") else 0,
                        project.get("canonical_book", ""),
                        project.get("masterplan", ""),
                        _json_dumps(project.get("canon_snapshot") or {}),
                        _json_dumps(project.get("memory_policy") or {}),
                        _json_dumps(project.get("worker_plan") or {}),
                        _json_dumps(project.get("council_plan") or {}),
                        _json_dumps(project.get("execution_plan") or {}),
                        _json_dumps(project.get("governance_policy") or {}),
                        _json_dumps(project.get("audit_plan") or {}),
                        _json_dumps(project.get("worker_pool") or []),
                        _json_dumps(project.get("council_members") or []),
                        _json_dumps(project.get("hierarchy_layers") or []),
                        _json_dumps(project.get("custom_inputs") or []),
                        _json_dumps(project.get("launch") or {}),
                        float(project.get("created_at") or _now()),
                        float(project.get("updated_at") or _now()),
                        float(_canon_frozen_at) if _canon_frozen_at is not None else None,
                        float(_masterplan_frozen_at) if _masterplan_frozen_at is not None else None,
                        float(_build_authorized_at) if _build_authorized_at is not None else None,
                        str(project.get("canon_hash") or ""),
                        str(project.get("masterplan_hash") or ""),
                        float(_cost_cap_usd) if _cost_cap_usd is not None else None,
                        str(project.get("autonomy_level") or ""),
                    ),
                )

                self._replace_project_graph(conn, project)
                self._sync_skill_reuse_log(conn, project)
                self._sync_brain(conn, project)

            _invalidate_project_caches(project["project_id"])
            return self.get_project(project["project_id"])

    def _replace_project_graph(self, conn: sqlite3.Connection, project: dict[str, Any]) -> None:
        project_id = project["project_id"]
        masterplan_id = project["masterplan_id"]

        conn.execute("DELETE FROM project_stages WHERE project_id = ?", (project_id,))
        for idx, stage in enumerate(project.get("stage_state") or []):
            conn.execute(
                """
                INSERT INTO project_stages (
                    stage_id, project_id, stage_name, stage_order, status, updated_at,
                    started_at, completed_at, output_ref, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stage["stage_id"],
                    project_id,
                    stage["stage"],
                    idx,
                    stage["status"],
                    float(stage.get("updated_at") or _now()),
                    float(stage.get("started_at") or 0),
                    float(stage.get("completed_at") or 0),
                    stage.get("output_ref", ""),
                    _json_dumps(stage.get("metadata") or {}),
                ),
            )

        conn.execute("DELETE FROM project_questions WHERE project_id = ?", (project_id,))
        for idx, question in enumerate(project.get("questions") or []):
            conn.execute(
                """
                INSERT INTO project_questions (
                    question_id, project_id, question_key, stage_name, status, context,
                    options_json, free_text_allowed, timeout_seconds, source, sort_order,
                    asked_at, answered_at, selected_choice_id, selected_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question["question_id"],
                    project_id,
                    question.get("key", ""),
                    question.get("phase", ""),
                    question.get("status", "pending"),
                    question.get("context", ""),
                    _json_dumps(question.get("choices") or []),
                    1 if question.get("free_text_allowed", True) else 0,
                    int(question.get("timeout_seconds", 0)),
                    question.get("source", "council"),
                    int(question.get("sort_order", idx)),
                    float(question.get("asked_at") or _now()),
                    float(question.get("answered_at") or 0),
                    question.get("selected_choice_id", ""),
                    question.get("selected_value", ""),
                ),
            )

        conn.execute("DELETE FROM project_answers WHERE project_id = ?", (project_id,))
        for answer in project.get("answers") or []:
            conn.execute(
                """
                INSERT INTO project_answers (
                    answer_id, project_id, question_id, choice_id, value, source, rationale, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer["answer_id"],
                    project_id,
                    answer.get("question_id", ""),
                    answer.get("choice_id", ""),
                    answer.get("value", ""),
                    answer.get("source", "human"),
                    answer.get("rationale", ""),
                    float(answer.get("answered_at") or _now()),
                ),
            )

        conn.execute("DELETE FROM project_decisions WHERE project_id = ?", (project_id,))
        for decision in project.get("decisions") or []:
            conn.execute(
                """
                INSERT INTO project_decisions (
                    decision_id, project_id, question_id, stage_name, decision_key, decision_value,
                    rationale, consequences, evidence_ref, effects_json, is_custom, frozen, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision["decision_id"],
                    project_id,
                    decision.get("question_id", ""),
                    decision.get("phase", ""),
                    decision.get("key", ""),
                    decision.get("label", ""),
                    decision.get("description", ""),
                    decision.get("consequences", ""),
                    decision.get("evidence_ref", ""),
                    _json_dumps(decision.get("effects") or {}),
                    1 if decision.get("is_custom") else 0,
                    1 if decision.get("frozen") else 0,
                    float(decision.get("selected_at") or _now()),
                ),
            )

        conn.execute("DELETE FROM project_canon_entries WHERE project_id = ?", (project_id,))
        canon = project.get("canon_snapshot") or {}
        for idx, (entry_key, entry_value) in enumerate(canon.items()):
            conn.execute(
                """
                INSERT INTO project_canon_entries (
                    canon_entry_id, project_id, entry_key, entry_value, version, supersedes_id, frozen_at, created_at
                ) VALUES (?, ?, ?, ?, 1, '', ?, ?)
                """,
                (
                    f"{project_id}::canon::{idx}",
                    project_id,
                    entry_key,
                    _json_dumps(entry_value),
                    float(project.get("updated_at") or _now()) if (project.get("approvals") or {}).get("book") else 0,
                    float(project.get("created_at") or _now()),
                ),
            )

        conn.execute("DELETE FROM project_masterplans WHERE project_id = ?", (project_id,))
        modules = project.get("modules") or []
        conn.execute(
            """
            INSERT INTO project_masterplans (
                masterplan_id, project_id, status, plan_json, module_graph_json, deployment_topology_json,
                team_composition_json, hierarchy_json, audit_json, frozen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                masterplan_id,
                project_id,
                "frozen" if (project.get("approvals") or {}).get("operating_model") else "draft",
                _json_dumps(
                    {
                        "worker_plan": project.get("worker_plan") or {},
                        "execution_plan": project.get("execution_plan") or {},
                        "governance_policy": project.get("governance_policy") or {},
                    }
                ),
                _json_dumps(
                    {
                        "modules": [module.get("name", "") for module in modules],
                        "dependencies": {module.get("name", ""): module.get("depends_on") or [] for module in modules},
                    }
                ),
                _json_dumps(project.get("execution_plan") or {}),
                _json_dumps(
                    {
                        "worker_pool": project.get("worker_pool") or [],
                        "council_members": project.get("council_members") or [],
                    }
                ),
                _json_dumps(project.get("hierarchy_layers") or []),
                _json_dumps(project.get("audit_plan") or {}),
                float(project.get("updated_at") or _now()) if (project.get("approvals") or {}).get("operating_model") else 0,
                float(project.get("created_at") or _now()),
                float(project.get("updated_at") or _now()),
            ),
        )

        conn.execute("DELETE FROM project_modules WHERE project_id = ?", (project_id,))
        for module in modules:
            conn.execute(
                """
                INSERT INTO project_modules (
                    module_id, project_id, masterplan_id, name, spec_json, worker_id, docker_profile,
                    host_target, status, depends_on_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    module["module_id"],
                    project_id,
                    module.get("masterplan_id", masterplan_id),
                    module.get("name", ""),
                    _json_dumps(module.get("spec") or {}),
                    module.get("worker_id", ""),
                    module.get("docker_profile", ""),
                    module.get("host_target", ""),
                    module.get("status", "planned"),
                    _json_dumps(module.get("depends_on") or []),
                    float(module.get("created_at") or _now()),
                    float(module.get("updated_at") or _now()),
                ),
            )

        conn.execute("DELETE FROM project_worker_pool WHERE project_id = ?", (project_id,))
        for worker in project.get("worker_pool") or []:
            conn.execute(
                """
                INSERT INTO project_worker_pool (
                    worker_entry_id, project_id, name, worker_type, endpoint, model_id, role,
                    cost_per_1k, active, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    worker["worker_entry_id"],
                    project_id,
                    worker.get("name", ""),
                    worker.get("worker_type", ""),
                    worker.get("endpoint", ""),
                    worker.get("model_id", ""),
                    worker.get("role", ""),
                    float(worker.get("cost_per_1k") or 0),
                    1 if worker.get("active", True) else 0,
                    _json_dumps(worker.get("config") or {}),
                ),
            )

        conn.execute("DELETE FROM project_council_members WHERE project_id = ?", (project_id,))
        for member in project.get("council_members") or []:
            conn.execute(
                """
                INSERT INTO project_council_members (
                    council_member_id, project_id, member_role, provider, model_id,
                    voting_weight, config_json, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member["council_member_id"],
                    project_id,
                    member.get("member_role") or member.get("role", ""),
                    member.get("provider", ""),
                    member.get("model_id", ""),
                    float(member.get("voting_weight") or 1.0),
                    _json_dumps(member.get("config") or {}),
                    1 if member.get("active", True) else 0,
                ),
            )

        conn.execute("DELETE FROM project_hierarchy_layers WHERE project_id = ?", (project_id,))
        for layer in project.get("hierarchy_layers") or []:
            conn.execute(
                """
                INSERT INTO project_hierarchy_layers (
                    layer_id, project_id, layer_name, layer_order, model_id, provider,
                    role_prompt, active, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    layer["layer_id"],
                    project_id,
                    layer.get("layer_name", ""),
                    int(layer.get("layer_order", 0)),
                    layer.get("model_id", ""),
                    layer.get("provider", ""),
                    layer.get("role_prompt", ""),
                    1 if layer.get("active", True) else 0,
                    _json_dumps(layer.get("config") or {}),
                ),
            )

        conn.execute("DELETE FROM project_autonomy_config WHERE project_id = ?", (project_id,))
        conn.execute(
            """
            INSERT INTO project_autonomy_config (config_id, project_id, level, overrides_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"{project_id}::autonomy",
                project_id,
                (project.get("governance_policy") or {}).get("autonomy_mode", "L1_BOOK_LOCKED"),
                _json_dumps((project.get("governance_policy") or {}).get("autonomy_overrides") or {}),
                float(project.get("updated_at") or _now()),
            ),
        )

    def _sync_brain(self, conn: sqlite3.Connection, project: dict[str, Any]) -> None:
        project_id = project["project_id"]
        conn.execute("DELETE FROM brain_memory_entries WHERE project_id = ?", (project_id,))
        entries = [
            {
                "memory_entry_id": f"{project_id}::brain::canon",
                "entry_type": "canon",
                "content": project.get("canonical_book", ""),
                "metadata": {"title": project.get("title", ""), "phase": project.get("phase", "")},
            },
            {
                "memory_entry_id": f"{project_id}::brain::masterplan",
                "entry_type": "masterplan",
                "content": project.get("masterplan", ""),
                "metadata": {"status": project.get("status", "")},
            },
        ]
        for decision in project.get("decisions") or []:
            entries.append(
                {
                    "memory_entry_id": f"{project_id}::brain::decision::{decision['decision_id']}",
                    "entry_type": "decision",
                    "content": f"{decision.get('key', '')}: {decision.get('label', '')}\n{decision.get('consequences', '')}",
                    "metadata": {
                        "stage": decision.get("phase", ""),
                        "effects": decision.get("effects") or {},
                    },
                }
            )
        for module in project.get("modules") or []:
            entries.append(
                {
                    "memory_entry_id": f"{project_id}::brain::module::{module['module_id']}",
                    "entry_type": "skill",
                    "content": f"{module.get('name', '')}\n{_json_dumps(module.get('spec') or {})}",
                    "metadata": {"module_id": module["module_id"]},
                }
            )
        for entry in entries:
            if not entry["content"]:
                continue
            conn.execute(
                """
                INSERT INTO brain_memory_entries (memory_entry_id, entry_type, project_id, content, metadata_json, embedding_id, created_at)
                VALUES (?, ?, ?, ?, ?, '', ?)
                """,
                (
                    entry["memory_entry_id"],
                    entry["entry_type"],
                    project_id,
                    entry["content"],
                    _json_dumps(entry["metadata"]),
                    float(project.get("updated_at") or _now()),
                ),
            )

        dataset_id = f"{project_id}::dataset"
        sample_count = len(project.get("decisions") or []) + len(project.get("modules") or [])
        dataset_path = str(Path(self.db_path).with_name(f"{project_id}_lora_dataset.jsonl")) if self.db_path != ":memory:" else f"{project_id}_lora_dataset.jsonl"
        conn.execute(
            """
            INSERT INTO brain_lora_datasets (dataset_id, project_id, dataset_path, sample_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                dataset_path=excluded.dataset_path,
                sample_count=excluded.sample_count,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                dataset_id,
                project_id,
                dataset_path,
                sample_count,
                (project.get("memory_policy") or {}).get("training_policy", "merge_time_lora"),
                float(project.get("created_at") or _now()),
                float(project.get("updated_at") or _now()),
            ),
        )

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Return the assembled project view, or None.

        Phase 3 W1.3: cached under ``workspace.project`` namespace
        (TTL 5 min). Invalidated by every state mutation through
        ``_invalidate_project_caches``.
        """
        cache_key: str | None = None
        use_cache = True
        try:
            from sylion.aeis_v2.audit_profile import is_audit_mode

            # Audit runs often use two local API processes against one SQLite
            # DB. The fallback cache is process-local, so one process cannot
            # invalidate another process after dashboard mutations.
            use_cache = not is_audit_mode()
        except Exception:                          # noqa: BLE001
            use_cache = True
        try:
            if use_cache:
                from sylion.infra.cache import default_ttl, get_cache, make_key

                cache_key = make_key("workspace.project", "get", project_id)
                cached_payload = get_cache().get(cache_key)
                if cached_payload is not None:
                    return cached_payload
        except Exception:                          # noqa: BLE001
            log.warning("workspace.project cache get failed", exc_info=True)
            cache_key = None

        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM project_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            project = self._assemble_project(row)

        if cache_key is not None:
            try:
                from sylion.infra.cache import default_ttl, get_cache

                get_cache().set(
                    cache_key,
                    project,
                    ttl=default_ttl("workspace.project"),
                )
            except Exception:                      # noqa: BLE001
                log.warning("workspace.project cache set failed", exc_info=True)

        return project

    def _assemble_project(self, row: sqlite3.Row) -> dict[str, Any]:
        project_id = row["project_id"]
        conn = self._get_conn()
        # W14 BE-6 round_meta freeze/authorize fields. ``sqlite3.Row`` raises
        # ``IndexError`` for missing columns; guard for tests/older DBs that
        # may not have run the latest ``_migrate``.
        row_keys = set(row.keys())

        def _opt_float(name: str) -> float | None:
            if name not in row_keys:
                return None
            value = row[name]
            return None if value is None else float(value)

        def _opt_str(name: str) -> str:
            if name not in row_keys:
                return ""
            value = row[name]
            return "" if value is None else str(value)

        project = {
            "project_id": project_id,
            "title": row["title"],
            "idea": row["idea"],
            "constraints": row["constraints"],
            "canonical_book_input": row["canonical_book_input"],
            "preferred_stack": _json_loads(row["preferred_stack_json"], []),
            "attachments": _json_loads(row["attachments_json"], []),
            "owner_id": row["owner_id"],
            "team_id": row["team_id"],
            "project_kind": row["project_kind"],
            "source_idea_id": _opt_str("source_idea_id"),
            "status": row["status"],
            "phase": row["phase"],
            "human_gate_session_id": row["human_gate_session_id"],
            "approvals": {
                "book": bool(row["approval_book"]),
                "operating_model": bool(row["approval_operating_model"]),
            },
            "canonical_book": row["canonical_book"],
            "masterplan": row["masterplan"],
            "canon_snapshot": _json_loads(row["canon_snapshot_json"], {}),
            "memory_policy": _json_loads(row["memory_policy_json"], {}),
            "worker_plan": _json_loads(row["worker_plan_json"], {}),
            "council_plan": _json_loads(row["council_plan_json"], {}),
            "execution_plan": _json_loads(row["execution_plan_json"], {}),
            "governance_policy": _json_loads(row["governance_policy_json"], {}),
            "audit_plan": _json_loads(row["audit_plan_json"], {}),
            "worker_pool": _json_loads(row["worker_pool_json"], []),
            "council_members": _json_loads(row["council_members_json"], []),
            "hierarchy_layers": _json_loads(row["hierarchy_layers_json"], []),
            "custom_inputs": _json_loads(row["custom_inputs_json"], []),
            "launch": _json_loads(row["launch_json"], {}),
            "created_at": float(row["created_at"]),
            "updated_at": float(row["updated_at"]),
            "masterplan_id": f"{project_id}::masterplan",
            "canon_frozen_at": _opt_float("canon_frozen_at"),
            "masterplan_frozen_at": _opt_float("masterplan_frozen_at"),
            "build_authorized_at": _opt_float("build_authorized_at"),
            "canon_hash": _opt_str("canon_hash"),
            "masterplan_hash": _opt_str("masterplan_hash"),
            "cost_cap_usd": _opt_float("cost_cap_usd"),
            "autonomy_level": _opt_str("autonomy_level"),
        }
        project["stage_state"] = [
            {
                "stage_id": stage["stage_id"],
                "stage": stage["stage_name"],
                "status": stage["status"],
                "updated_at": float(stage["updated_at"]),
                "started_at": float(stage["started_at"]),
                "completed_at": float(stage["completed_at"]),
                "output_ref": stage["output_ref"],
                "metadata": _json_loads(stage["metadata_json"], {}),
            }
            for stage in conn.execute(
                "SELECT * FROM project_stages WHERE project_id = ? ORDER BY stage_order ASC",
                (project_id,),
            ).fetchall()
        ]
        project["questions"] = [
            {
                "question_id": question["question_id"],
                "key": question["question_key"],
                "phase": question["stage_name"],
                "status": question["status"],
                "context": question["context"],
                "choices": _json_loads(question["options_json"], []),
                "free_text_allowed": bool(question["free_text_allowed"]),
                "timeout_seconds": int(question["timeout_seconds"]),
                "source": question["source"],
                "sort_order": int(question["sort_order"]),
                "asked_at": float(question["asked_at"]),
                "answered_at": float(question["answered_at"]),
                "selected_choice_id": question["selected_choice_id"],
                "selected_value": question["selected_value"],
            }
            for question in conn.execute(
                "SELECT * FROM project_questions WHERE project_id = ? ORDER BY sort_order ASC",
                (project_id,),
            ).fetchall()
        ]
        project["answers"] = [
            {
                "answer_id": answer["answer_id"],
                "question_id": answer["question_id"],
                "choice_id": answer["choice_id"],
                "value": answer["value"],
                "source": answer["source"],
                "rationale": answer["rationale"],
                "answered_at": float(answer["answered_at"]),
            }
            for answer in conn.execute(
                "SELECT * FROM project_answers WHERE project_id = ? ORDER BY answered_at ASC",
                (project_id,),
            ).fetchall()
        ]
        project["decisions"] = [
            {
                "decision_id": decision["decision_id"],
                "question_id": decision["question_id"],
                "phase": decision["stage_name"],
                "key": decision["decision_key"],
                "label": decision["decision_value"],
                "description": decision["rationale"],
                "consequences": decision["consequences"],
                "evidence_ref": decision["evidence_ref"],
                "effects": _json_loads(decision["effects_json"], {}),
                "is_custom": bool(decision["is_custom"]),
                "frozen": bool(decision["frozen"]),
                "selected_at": float(decision["created_at"]),
            }
            for decision in conn.execute(
                "SELECT * FROM project_decisions WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,),
            ).fetchall()
        ]
        project["modules"] = [
            {
                "module_id": module["module_id"],
                "masterplan_id": module["masterplan_id"],
                "name": module["name"],
                "spec": _json_loads(module["spec_json"], {}),
                "worker_id": module["worker_id"],
                "docker_profile": module["docker_profile"],
                "host_target": module["host_target"],
                "status": module["status"],
                "depends_on": _json_loads(module["depends_on_json"], []),
                "created_at": float(module["created_at"]),
                "updated_at": float(module["updated_at"]),
            }
            for module in conn.execute(
                "SELECT * FROM project_modules WHERE project_id = ? ORDER BY name ASC",
                (project_id,),
            ).fetchall()
        ]
        project["pending_questions"] = [question for question in project["questions"] if question["status"] == "pending"]
        project["timeline"] = self.get_project_timeline(project_id)["stages"]
        project["events"] = self.list_project_events(project_id, limit=50)["events"]
        return project

    def list_projects(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            if owner_id:
                rows = conn.execute(
                    "SELECT * FROM project_projects WHERE owner_id = ? ORDER BY created_at DESC",
                    (owner_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM project_projects ORDER BY created_at DESC"
                ).fetchall()
            return [self._assemble_project(row) for row in rows]

    def get_project_by_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM project_projects WHERE human_gate_session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._assemble_project(row)

    def list_project_questions(self, project_id: str, status: str | None = None) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        questions = project["questions"]
        if status:
            questions = [question for question in questions if question["status"] == status]
        return {"questions": questions}

    def list_project_events(self, project_id: str, limit: int = 100) -> dict[str, Any]:
        rows = self._get_conn().execute(
            """
            SELECT * FROM project_events WHERE project_id = ?
            ORDER BY emitted_at DESC LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return {
            "events": [
                {
                    "event_id": row["event_id"],
                    "project_id": row["project_id"],
                    "event_type": row["event_type"],
                    "payload": _json_loads(row["payload_json"], {}),
                    "emitted_at": float(row["emitted_at"]),
                }
                for row in rows
            ]
        }

    def add_event(self, project_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_id": _uid("pevt"),
            "project_id": project_id,
            "event_type": event_type,
            "payload": payload or {},
            "emitted_at": _now(),
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_events (event_id, project_id, event_type, payload_json, emitted_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        project_id,
                        event_type,
                        _json_dumps(event["payload"]),
                        float(event["emitted_at"]),
                    ),
                )
        # Phase 3 W1.3: events that close stages or trigger workflow updates
        # mutate the assembled project view returned by ``get_project``.
        _invalidate_project_caches(project_id)
        _record_project_audit_event(event)
        return event

    def add_notification(
        self,
        owner_id: str,
        title: str,
        body: str,
        *,
        notification_type: str = "info",
        project_id: str = "",
        link_to: str = "",
        metadata: dict[str, Any] | None = None,
        status: str = "unread",
    ) -> dict[str, Any]:
        if status not in VALID_NOTIFICATION_STATUSES:
            raise ValueError(f"Invalid notification status '{status}'")
        created_at = _now()
        read_at = created_at if status in {"read", "acknowledged"} else 0.0
        acknowledged_at = created_at if status == "acknowledged" else 0.0
        notification = {
            "notification_id": _uid("notif"),
            "project_id": project_id,
            "owner_id": owner_id or "workspace-default",
            "type": notification_type,
            "title": title,
            "body": body,
            "link_to": link_to,
            "status": status,
            "created_at": created_at,
            "read_at": read_at,
            "acknowledged_at": acknowledged_at,
            "metadata": metadata or {},
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_notifications (
                        notification_id, project_id, owner_id, type, title, body, link_to,
                        status, created_at, read_at, acknowledged_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notification["notification_id"],
                        notification["project_id"],
                        notification["owner_id"],
                        notification["type"],
                        notification["title"],
                        notification["body"],
                        notification["link_to"],
                        notification["status"],
                        float(notification["created_at"]),
                        float(notification["read_at"]),
                        float(notification["acknowledged_at"]),
                        _json_dumps(notification["metadata"]),
                    ),
                )
        return notification

    @staticmethod
    def _notification_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notification_id": row["notification_id"],
            "project_id": row["project_id"],
            "owner_id": row["owner_id"],
            "type": row["type"],
            "title": row["title"],
            "message": row["body"],
            "body": row["body"],
            "link_to": row["link_to"],
            "status": row["status"],
            "created_at": float(row["created_at"]),
            "read_at": float(row["read_at"]),
            "acknowledged_at": float(row["acknowledged_at"]),
            "metadata": _json_loads(row["metadata_json"], {}),
        }

    def list_notifications(
        self,
        *,
        project_id: str | None = None,
        owner_id: str | None = None,
        limit: int = 50,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        clauses = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if unread_only:
            clauses.append("status = 'unread'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._get_conn().execute(
            f"SELECT * FROM project_notifications {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return {
            "notifications": [self._notification_from_row(row) for row in rows]
        }

    def unread_count(self, owner_id: str) -> int:
        row = self._get_conn().execute(
            """
            SELECT COUNT(*) AS count FROM project_notifications
            WHERE owner_id = ? AND status = 'unread'
            """,
            (owner_id,),
        ).fetchone()
        return int(row["count"] if row else 0)

    def mark_notification_read(self, notification_id: str) -> dict[str, Any] | None:
        now = _now()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
            if row is None or row["status"] == "read":
                return None
            with conn:
                conn.execute(
                    """
                    UPDATE project_notifications
                    SET status = 'read', read_at = ?, acknowledged_at = 0
                    WHERE notification_id = ?
                    """,
                    (now, notification_id),
                )
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        if row is None:
            return None
        return self._notification_from_row(row)

    def mark_notification_unread(self, notification_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
            if row is None or row["status"] == "unread":
                return None
            with conn:
                conn.execute(
                    """
                    UPDATE project_notifications
                    SET status = 'unread', read_at = 0, acknowledged_at = 0
                    WHERE notification_id = ?
                    """,
                    (notification_id,),
                )
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        if row is None:
            return None
        return self._notification_from_row(row)

    def acknowledge_notification(self, notification_id: str) -> dict[str, Any] | None:
        now = _now()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
            if row is None or row["status"] == "acknowledged":
                return None
            read_at = float(row["read_at"]) or now
            with conn:
                conn.execute(
                    """
                    UPDATE project_notifications
                    SET status = 'acknowledged', read_at = ?, acknowledged_at = ?
                    WHERE notification_id = ?
                    """,
                    (read_at, now, notification_id),
                )
            row = conn.execute(
                "SELECT * FROM project_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        if row is None:
            return None
        return self._notification_from_row(row)

    def get_project_timeline(self, project_id: str) -> dict[str, Any]:
        conn = self._get_conn()
        project_row = conn.execute(
            """
            SELECT status, updated_at, canon_frozen_at, masterplan_frozen_at,
                   build_authorized_at, launch_json
            FROM project_projects
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        rows = conn.execute(
            "SELECT * FROM project_stages WHERE project_id = ? ORDER BY stage_order ASC",
            (project_id,),
        ).fetchall()
        completed_stages: set[str] = set()
        completed_at: dict[str, float] = {}

        if project_row:
            launch = _json_loads(project_row["launch_json"], {})
            canon_frozen_at = float(project_row["canon_frozen_at"] or 0)
            masterplan_frozen_at = float(project_row["masterplan_frozen_at"] or 0)
            build_authorized_at = float(project_row["build_authorized_at"] or 0)

            if canon_frozen_at:
                completed_stages.add("canon")
                completed_at["canon"] = canon_frozen_at
            if masterplan_frozen_at:
                completed_stages.add("masterplan")
                completed_at["masterplan"] = masterplan_frozen_at
            if build_authorized_at:
                completed_stages.add("build_authorization")
                completed_at["build_authorization"] = build_authorized_at
            if project_row["status"] == "completed" or launch.get("status") == "completed":
                completed_stages.update(PROJECT_STAGE_ORDER)
                launched_at = float(launch.get("launched_at") or project_row["updated_at"] or _now())
                for stage_name in PROJECT_STAGE_ORDER:
                    completed_at.setdefault(stage_name, launched_at)
        return {
            "stages": [
                {
                    "stage": row["stage_name"],
                    "status": "completed" if row["stage_name"] in completed_stages else row["status"],
                    "updated_at": completed_at.get(row["stage_name"], float(row["updated_at"])),
                    "started_at": float(row["started_at"]),
                    "completed_at": completed_at.get(row["stage_name"], float(row["completed_at"])),
                    "output_ref": row["output_ref"],
                    "metadata": _json_loads(row["metadata_json"], {}),
                }
                for row in rows
            ]
        }

    def get_project_canon(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        entries = self._get_conn().execute(
            "SELECT * FROM project_canon_entries WHERE project_id = ? ORDER BY canon_entry_id ASC",
            (project_id,),
        ).fetchall()
        return {
            "project_id": project_id,
            "book": project["canonical_book"],
            "entries": [
                {
                    "entry_id": row["canon_entry_id"],
                    "key": row["entry_key"],
                    "value": _json_loads(row["entry_value"], row["entry_value"]),
                    "frozen_at": float(row["frozen_at"]),
                }
                for row in entries
            ],
            "approved": bool(project["approvals"]["book"]),
        }

    def get_project_masterplan(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        row = self._get_conn().execute(
            "SELECT * FROM project_masterplans WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if row is None:
            return {"project_id": project_id, "masterplan": project["masterplan"], "modules": project["modules"]}
        return {
            "project_id": project_id,
            "masterplan_id": row["masterplan_id"],
            "status": row["status"],
            "summary": project["masterplan"],
            "plan": _json_loads(row["plan_json"], {}),
            "module_graph": _json_loads(row["module_graph_json"], {}),
            "deployment_topology": _json_loads(row["deployment_topology_json"], {}),
            "team_composition": _json_loads(row["team_composition_json"], {}),
            "hierarchy": _json_loads(row["hierarchy_json"], []),
            "audit_plan": _json_loads(row["audit_json"], {}),
            "frozen_at": float(row["frozen_at"]),
            "modules": project["modules"],
            "approved": bool(project["approvals"]["operating_model"]),
        }

    def get_project_modules(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        return {"modules": project["modules"]}

    def get_project_skill_bindings(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        rows = self._get_conn().execute(
            """
            SELECT * FROM project_skill_reuse_log
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        ).fetchall()
        modules = []
        skill_ids: set[str] = set()
        for module in project.get("modules") or []:
            bindings = list((module.get("spec") or {}).get("skill_bindings") or [])
            for binding in bindings:
                skill_id = str((binding or {}).get("skill_id") or "")
                if skill_id:
                    skill_ids.add(skill_id)
            modules.append(
                {
                    "module_id": module.get("module_id", ""),
                    "name": module.get("name", ""),
                    "skills": list((module.get("spec") or {}).get("skills") or []),
                    "bindings": bindings,
                }
            )
        return {
            "project_id": project_id,
            "skill_ids": sorted(skill_ids),
            "modules": modules,
            "memory_policy": project.get("memory_policy") or {},
            "reuse_log": [
                {
                    "skill_reuse_id": row["skill_reuse_id"],
                    "project_id": row["project_id"],
                    "module_id": row["module_id"],
                    "reused_skill_id": row["reused_skill_id"],
                    "similarity_score": float(row["similarity_score"]),
                    "adaptation_notes": row["adaptation_notes"],
                    "created_at": float(row["created_at"]),
                }
                for row in rows
            ],
        }

    def get_project_decisions(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        return {"decisions": project["decisions"]}

    def get_project_council(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        return {
            "project_id": project_id,
            "plan": project["council_plan"],
            "members": project["council_members"],
        }

    def update_project_council(self, project_id: str, members: list[dict[str, Any]], plan_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        project["council_members"] = members
        if plan_overrides:
            project["council_plan"] = {**(project.get("council_plan") or {}), **plan_overrides}
        project["updated_at"] = _now()
        return self.upsert_project(project)

    # ------------------------------------------------------------------
    # Wave A3 (RB-004): council semantics accessors
    # ------------------------------------------------------------------

    def is_council_enabled(self, project_id: str) -> bool:
        """Whether the council plane is enabled for a project.

        Reads `council_plan.enabled` (default True if absent for legacy compat).
        """
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        plan = project.get("council_plan") or {}
        return bool(plan.get("enabled", True))

    def set_council_enabled(self, project_id: str, enabled: bool) -> dict[str, Any]:
        """Toggle council enablement and update members so active flags
        are consistent with the new state.

        F-012 fix: when re-enabling after a previous disable, members carry
        active=False from the disable step. Multiplying by m.get("active", True)
        kept them inactive forever. We now:
          - on disable: flip everyone to inactive (preserves operator deletes
            via list shape, but resets active flag to False)
          - on enable: drop the cached members so upsert/_derive_council_members
            re-derives from the council_plan (matches docstring intent and the
            reconcile_council() pattern below).
        """
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        plan = dict(project.get("council_plan") or {})
        plan["enabled"] = bool(enabled)
        project["council_plan"] = plan
        if not enabled:
            existing = project.get("council_members") or []
            for m in existing:
                m["active"] = False
            project["council_members"] = existing
        else:
            # Re-derive from plan (same path as reconcile_council).
            project["council_members"] = []
        project["updated_at"] = _now()
        return self.upsert_project(project)

    def get_decision_hierarchy(self, project_id: str) -> list[str]:
        """Return ordered decision hierarchy for a project.

        Honors RB-004: when council is disabled, hierarchy must NOT include
        `planner_council`. Falls back to operator-only.
        """
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        plan = project.get("council_plan") or {}
        if not bool(plan.get("enabled", True)):
            return ["operator_only"]
        layers = (project.get("governance_policy") or {}).get("decision_layers") or []
        if not layers:
            return ["operator", "planner_council", "engineer_council"]
        return [str(name) for name in layers]

    def reconcile_council(self, project_id: str) -> dict[str, Any]:
        """Force re-derivation of council_members from current council_plan.

        After this call, `council_members` mirrors `council_plan` deterministically:
          - count of active members == council_plan.active_size when enabled
          - all members inactive when disabled
        Returns the refreshed council view {project_id, plan, members}.
        """
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        # Drop the stored members so upsert path triggers _derive_council_members.
        project["council_members"] = []
        project["updated_at"] = _now()
        self.upsert_project(project)
        return self.get_project_council(project_id)

    def get_project_hierarchy(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        return {"project_id": project_id, "layers": project["hierarchy_layers"]}

    def update_project_hierarchy(self, project_id: str, layers: list[dict[str, Any]]) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        project["hierarchy_layers"] = layers
        project["updated_at"] = _now()
        return self.upsert_project(project)

    def get_project_workers(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        return {"project_id": project_id, "workers": project["worker_pool"]}

    def update_project_workers(self, project_id: str, workers: list[dict[str, Any]]) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        project["worker_pool"] = workers
        project["updated_at"] = _now()
        return self.upsert_project(project)

    def reconcile_worker_pool(
        self,
        project_id: str,
        execution_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Wave A4 (RB-002): rebuild worker_pool from execution_plan.

        If `execution_plan` is given, replaces the project's plan first; this
        is the "execution_plan changed" entry point. With no argument, the
        existing plan is re-applied (useful to heal external drift).

        Returns {"project_id", "workers", "orphans"} where `orphans` is the
        list of worker_entry_ids that were dropped during the rebuild.
        """
        project = self.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        prior_ids = {
            e.get("worker_entry_id")
            for e in (project.get("worker_pool") or [])
            if e.get("worker_entry_id")
        }
        if execution_plan is not None:
            project["execution_plan"] = dict(execution_plan)
        project["updated_at"] = _now()
        refreshed = self.upsert_project(project)
        new_ids = {
            e.get("worker_entry_id")
            for e in (refreshed.get("worker_pool") or [])
            if e.get("worker_entry_id")
        }
        return {
            "project_id": project_id,
            "workers": refreshed.get("worker_pool") or [],
            "orphans": sorted(prior_ids - new_ids),
        }

    def get_project_cost(self, project_id: str) -> dict[str, Any]:
        rows = self._get_conn().execute(
            "SELECT * FROM project_cost_ledger WHERE project_id = ? ORDER BY timestamp DESC",
            (project_id,),
        ).fetchall()
        records = [
            {
                "cost_entry_id": row["cost_entry_id"],
                "timestamp": float(row["timestamp"]),
                "provider": row["provider"],
                "model": row["model"],
                "tokens_in": int(row["tokens_in"]),
                "tokens_out": int(row["tokens_out"]),
                "cost_usd": float(row["cost_usd"]),
                "running_total": float(row["running_total"]),
            }
            for row in rows
        ]
        return {
            "project_id": project_id,
            "records": records,
            "running_total": records[0]["running_total"] if records else 0.0,
        }

    def record_cost(
        self,
        project_id: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> dict[str, Any]:
        current = self.get_project_cost(project_id)["running_total"]
        entry = {
            "cost_entry_id": _uid("cost"),
            "project_id": project_id,
            "timestamp": _now(),
            "provider": provider,
            "model": model,
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "cost_usd": float(cost_usd),
            "running_total": float(current + cost_usd),
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_cost_ledger (
                        cost_entry_id, project_id, timestamp, provider, model,
                        tokens_in, tokens_out, cost_usd, running_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry["cost_entry_id"],
                        project_id,
                        entry["timestamp"],
                        provider,
                        model,
                        entry["tokens_in"],
                        entry["tokens_out"],
                        entry["cost_usd"],
                        entry["running_total"],
                    ),
                )
        return entry

    def get_project_audit(self, project_id: str) -> dict[str, Any]:
        rows = self._get_conn().execute(
            "SELECT * FROM project_audit_results WHERE project_id = ? ORDER BY executed_at DESC",
            (project_id,),
        ).fetchall()
        return {
            "project_id": project_id,
            "results": [
                {
                    "audit_result_id": row["audit_result_id"],
                    "module_id": row["module_id"],
                    "audit_type": row["audit_type"],
                    "status": row["status"],
                    "findings": _json_loads(row["findings_json"], []),
                    "executed_at": float(row["executed_at"]),
                }
                for row in rows
            ],
        }

    def record_audit_result(
        self,
        project_id: str,
        audit_type: str,
        *,
        module_id: str = "",
        status: str = "pass",
        findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = {
            "audit_result_id": _uid("audit"),
            "project_id": project_id,
            "module_id": module_id,
            "audit_type": audit_type,
            "status": status,
            "findings": findings or [],
            "executed_at": _now(),
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_audit_results (
                        audit_result_id, project_id, module_id, audit_type, status, findings_json, executed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result["audit_result_id"],
                        project_id,
                        module_id,
                        audit_type,
                        status,
                        _json_dumps(result["findings"]),
                        result["executed_at"],
                    ),
                )
        return result

    def get_brain_stats(self) -> dict[str, Any]:
        conn = self._get_conn()
        stats = {}
        for table, field in [
            ("brain_memory_entries", "entries"),
            ("brain_lora_datasets", "datasets"),
            ("brain_lora_adapters", "adapters"),
            ("brain_prompt_library", "prompts"),
        ]:
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            stats[field] = int(row["count"] if row else 0)
        return stats

    def search_brain(self, query: str, top_k: int = 5) -> dict[str, Any]:
        indexed_rows: list[sqlite3.Row] = []
        try:
            from sylion.memory.indexer import Indexer

            hits = Indexer(db_path=self.db_path).search(query, limit=top_k)
            if hits:
                ids = [hit["section_id"] for hit in hits]
                placeholders = ",".join("?" for _ in ids)
                indexed_rows = self._get_conn().execute(
                    f"""
                    SELECT * FROM brain_memory_entries
                    WHERE memory_entry_id IN ({placeholders})
                    """,
                    ids,
                ).fetchall()
                by_id = {row["memory_entry_id"]: row for row in indexed_rows}
                indexed_rows = [by_id[item_id] for item_id in ids if item_id in by_id]
        except Exception:
            indexed_rows = []

        rows = indexed_rows or self._get_conn().execute(
            """
            SELECT * FROM brain_memory_entries
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", top_k),
        ).fetchall()
        return {
            "items": [
                {
                    "memory_entry_id": row["memory_entry_id"],
                    "entry_type": row["entry_type"],
                    "project_id": row["project_id"],
                    "content": row["content"],
                    "metadata": _json_loads(row["metadata_json"], {}),
                    "created_at": float(row["created_at"]),
                }
                for row in rows
            ]
        }

    def list_brain_prompts(self) -> dict[str, Any]:
        rows = self._get_conn().execute(
            "SELECT * FROM brain_prompt_library ORDER BY category ASC, role_name ASC"
        ).fetchall()
        return {
            "prompts": [
                {
                    "prompt_id": row["prompt_id"],
                    "category": row["category"],
                    "role_name": row["role_name"],
                    "template": row["template"],
                    "last_used_at": float(row["last_used_at"]),
                    "success_rate": float(row["success_rate"]),
                    "usage_count": int(row["usage_count"]),
                    "active": bool(row["active"]),
                }
                for row in rows
            ]
        }

    def record_brain_prompt_snapshot(self, category: str, role_name: str, template: str) -> dict[str, Any]:
        prompt = {
            "prompt_id": _uid("brainprompt"),
            "category": category,
            "role_name": role_name,
            "template": template,
            "last_used_at": _now(),
            "success_rate": 1.0,
            "usage_count": 1,
            "active": True,
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO brain_prompt_library (
                        prompt_id, category, role_name, template,
                        last_used_at, success_rate, usage_count, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prompt["prompt_id"],
                        prompt["category"],
                        prompt["role_name"],
                        prompt["template"],
                        prompt["last_used_at"],
                        prompt["success_rate"],
                        prompt["usage_count"],
                        1,
                    ),
                )
        return prompt

    def update_brain_prompt(self, prompt_id: str, template: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    "UPDATE brain_prompt_library SET template = ?, last_used_at = ? WHERE prompt_id = ?",
                    (template, _now(), prompt_id),
                )
            row = conn.execute(
                "SELECT * FROM brain_prompt_library WHERE prompt_id = ?",
                (prompt_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "prompt_id": row["prompt_id"],
            "category": row["category"],
            "role_name": row["role_name"],
            "template": row["template"],
        }

    def list_brain_lora_adapters(self) -> dict[str, Any]:
        rows = self._get_conn().execute(
            "SELECT * FROM brain_lora_adapters ORDER BY created_at DESC"
        ).fetchall()
        return {
            "adapters": [
                {
                    "adapter_id": row["adapter_id"],
                    "base_model": row["base_model"],
                    "adapter_path": row["adapter_path"],
                    "training_project_ids": _json_loads(row["training_project_ids_json"], []),
                    "eval_score": float(row["eval_score"]),
                    "promoted": bool(row["promoted"]),
                    "promoted_at": float(row["promoted_at"]),
                    "created_at": float(row["created_at"]),
                }
                for row in rows
            ]
        }

    def queue_lora_training(self, project_id: str, base_model: str) -> dict[str, Any]:
        safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", str(base_model or "model")).strip("._-") or "model"
        safe_project = re.sub(r"[^A-Za-z0-9._-]+", "_", str(project_id or "project")).strip("._-") or "project"
        adapter_filename = f"{safe_project}_{safe_model}.lora"
        adapter = {
            "adapter_id": _uid("lora"),
            "base_model": base_model,
            "adapter_path": str(Path(self.db_path).with_name(adapter_filename)) if self.db_path != ":memory:" else adapter_filename,
            "training_project_ids": [project_id],
            "eval_score": 0.0,
            "promoted": False,
            "promoted_at": 0.0,
            "created_at": _now(),
        }
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT INTO brain_lora_adapters (
                        adapter_id, base_model, adapter_path, training_project_ids_json,
                        eval_score, promoted, promoted_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        adapter["adapter_id"],
                        adapter["base_model"],
                        adapter["adapter_path"],
                        _json_dumps(adapter["training_project_ids"]),
                        adapter["eval_score"],
                        0,
                        adapter["promoted_at"],
                        adapter["created_at"],
                    ),
                )
        return adapter

    def list_ollama_models(self) -> list[str]:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(rows) <= 1:
            return []
        return [line.split()[0] for line in rows[1:] if line.split()]

    def get_brain_models(self) -> dict[str, Any]:
        installed = self.list_ollama_models()
        recommended = ["qwen3.5:latest", "gpt-oss:20b", "nomic-embed-text", "qwen2.5-coder:7b", "qwen2.5-coder:14b", "bge-m3"]
        return {
            "installed": installed,
            "missing": [model for model in recommended if model not in installed and model != "bge-m3"],
            "optional": [model for model in ["bge-m3"] if model not in installed],
        }


_store: ProjectModeStore | None = None
_store_lock = threading.RLock()


def get_project_mode_store() -> ProjectModeStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ProjectModeStore()
        return _store
