"""SYLION AEIS FastAPI application entry point."""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from sylion.api.rate_limit import RateLimitMiddleware
from sylion.api.rbac_enforcement import RBACEnforcementMiddleware
from sylion.api.faq_routes import router as faq_router
from sylion.api.testing_routes import router as testing_router
from sylion.api.test_center_routes import router as test_center_router
# SYLION AEIS v2 — W7 Skills Registry extension: Role Catalog (PDF §8.2).
from sylion.api.role_catalog_routes import router as role_catalog_router
# SYLION AEIS v2 — W15 Ontology Runtime Plane (Phase 0 read-only).
from sylion.api.ontology_routes import router as ontology_v2_router
# SYLION AEIS v2 — W18 Operator Terminal Plane (Phase 0 SSE + commands).
from sylion.api.terminal_routes import router as terminal_v2_router
# SYLION AEIS v2 — W17 Deployment Plane (Phase 0 Compute Provider Federation).
from sylion.api.federation_routes import router as federation_v2_router
# SYLION AEIS v2 — W16 Apps Builder Plane (Phase 0 read-only demo list).
from sylion.api.apps_routes import router as apps_v2_router
# SYLION AEIS v2 — W19 Policy / Security Plane (Phase 0 read-only catalogue).
from sylion.api.policy_routes import router as policy_v2_router
# SYLION AEIS v2 — GDPR DSR (Articles 15/16/17/20) handler.
from sylion.api.gdpr_routes import router as gdpr_v2_router
# SYLION AEIS v2 — Prometheus metrics endpoint.
from sylion.api.metrics_v2_routes import router as metrics_v2_router
# SYLION AEIS v2 — health probe (k8s liveness/readiness, no RBAC).
from sylion.api.health_v2_routes import router as health_v2_router
# SYLION AEIS v2 — Council Hybrid ADR sign-off endpoint (sprint 3 A1).
from sylion.api.council_signoff_routes import router as council_signoff_router
# SYLION AEIS v2 — replay-as-fork REST endpoints (sprint 3 B-replay).
from sylion.api.replay_routes import router as replay_v2_router
from sylion.api.agent_theater_routes import (
    router as agent_theater_router,
    ws_router as agent_theater_ws_router,
)
from sylion.api.demo_mobile_inspector_routes import (
    router as demo_mobile_inspector_router,
)
from sylion.api.demo_portal_routes import router as demo_portal_router
from sylion.api.demo_factory_routes import router as demo_factory_router
from sylion.api.demo_crm_routes import router as demo_crm_router
from sylion.api.demo_funding_routes import router as demo_funding_router
from sylion.api.demo_marketplace_routes import (
    router as demo_marketplace_router,
)
from sylion.api.router import router
from sylion.core.auto_register import auto_register_modules
from sylion.core.contract_registry import get_contract_registry
from sylion.core.event_bus import get_event_bus
from sylion.core.module_registry import get_registry
from sylion.security.bootstrap_flow import BootstrapFlow
from sylion.security.startup_check import assert_safe_to_serve

log = logging.getLogger("sylion.api.app")


_DEV_OPERATOR_ID = "00000000-0000-0000-0000-000000000001"
_DEV_AUTH_PATH_PREFIXES = (
    # F-bug-401: in SYLION_AUTH_MODE=dev (default), the AuthMiddleware auto-
    # populates request.state.user with _DEV_OPERATOR_ID for these prefixes
    # so the operator dashboard works without a login flow. Previously only
    # /advisor and /orchestration were covered, which left every other
    # /api/v1/* mutation (ideas/projects/workspace/...) returning 401.
    # In dev mode we intentionally cover the whole /api/v1 surface. Production
    # and staging default to strict auth unless SYLION_AUTH_MODE is explicit.
    "/api/v1",
)


_TERMINAL_ACTIVITY_SKIP_PREFIXES = (
    "/api/v1/terminal/stream",
    "/api/v1/terminal/replay",
    "/api/v1/metrics",
    "/api/v1/health",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _terminal_layer_for_path(path: str) -> str:
    if "/ontology" in path:
        return "W15"
    if "/role-catalog" in path:
        return "W7"
    if "/terminal" in path:
        return "W18"
    if "/policy" in path:
        return "W19"
    if "/council" in path or "/ksiega" in path:
        return "COUNCIL"
    if "/planning" in path or "/project-start" in path:
        return "AEIS"
    if "/execution-start" in path or "/build" in path:
        return "W6"
    if "/funding" in path:
        return "FUNDING"
    if "/human" in path or "/gate" in path:
        return "HUMANGATE"
    if "/ai-providers" in path or "/models" in path:
        return "MODELS"
    if "/environment" in path or "/federation" in path:
        return "ENV"
    return "API"


def _terminal_project_id_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    for part in parts:
        if part.startswith(("proj_", "project_")):
            return part
    try:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if candidate and candidate not in {"active", "create"}:
                return candidate
    except ValueError:
        pass
    return ""


def _terminal_activity_message(method: str, path: str, status_code: int, elapsed_ms: int) -> str:
    action = "odczyt"
    if method in {"POST", "PUT", "PATCH"}:
        action = "akcja"
    elif method == "DELETE":
        action = "usuniecie"
    return f"{action} dashboardu: {method} {path} -> {status_code} ({elapsed_ms} ms)"


def _bootstrap_advisor_audit_subscriber(event_backbone) -> None:
    """Start the advisor audit subscriber once during app boot."""
    try:
        from sylion.aeis.advisor.events import get_or_create_advisor_audit_subscriber

        get_or_create_advisor_audit_subscriber(event_backbone=event_backbone)
        log.info("advisor audit subscriber initialized")
    except Exception:
        log.warning("advisor audit subscriber initialization failed", exc_info=True)


def _load_dotenv() -> None:
    """Load .env file from project root into os.environ (no python-dotenv needed)."""
    # Walk up from app.py to find .env: api/ -> sylion/ -> sylion-pipeline/ -> src/ -> project_root
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    # F-006 fix: treat empty-string env value as "missing"
                    # so .env can override empty placeholders (e.g. shell that
                    # passes ANTHROPIC_API_KEY="" via parent process).
                    if key and not os.environ.get(key):
                        os.environ[key] = value
            return


def _prime_secrets_from_sops() -> None:
    """Phase 3 W2.2 (scope-fill): if a SOPS-encrypted secrets file exists
    for the current environment, decrypt it and materialise its values
    into ``os.environ`` *and* the unified key store. No-op when:

      * ``secrets/{env}.yaml`` doesn't exist (legacy env-var deployment)
      * No ``SYLION_AGE_IDENTITY[_FILE]`` configured (dev workstation)

    Existing env-vars take precedence over SOPS values so an operator
    can override a single secret without editing the encrypted file.
    """
    try:
        from sylion.security.sops_provider import (
            SopsAgeProvider,
            DecryptionUnavailable,
            SopsFileError,
        )
    except Exception:
        log.warning("sops_provider unavailable — skipping prime", exc_info=True)
        return

    env = os.environ.get("SYLION_AEIS_ENV", "dev").strip().lower()
    secrets_dir = Path(os.environ.get(
        "SYLION_SECRETS_DIR",
        Path(__file__).resolve().parent.parent.parent / "secrets",
    ))
    path = secrets_dir / f"{env}.yaml"
    if not path.exists():
        return

    provider = SopsAgeProvider()
    if not provider.has_identity():
        log.warning(
            "sops: %s exists but no SYLION_AGE_IDENTITY configured — "
            "secrets will fall back to env-vars",
            path,
        )
        return

    try:
        decoded = provider.decrypt_file(path)
    except (SopsFileError, DecryptionUnavailable):
        log.error("sops: failed to decrypt %s", path, exc_info=True)
        return

    primed = 0
    for name, value in decoded.items():
        if name not in os.environ:
            os.environ[name] = value
            primed += 1
    log.info("sops: primed %d secrets from %s into env", primed, path)


def _seed_key_vault() -> None:
    """Seed KeyVault with API keys from environment if not already stored."""
    from sylion.security.key_vault import get_key_vault

    vault = get_key_vault()
    provider_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    existing = {k["provider"] for k in vault.list_keys()}
    for provider, env_var in provider_map.items():
        key_value = os.environ.get(env_var, "").strip()
        if key_value and provider not in existing:
            try:
                rec = vault.store_key(provider, key_value, display_name=f"{provider} (from .env)")
                vault.activate_key(rec["key_id"])
                log.info("seeded %s key into vault", provider)
            except Exception:
                log.warning("failed to seed %s key", provider, exc_info=True)

    # Set default LLM provider based on available keys
    if not os.environ.get("SYLION_LLM_PROVIDER"):
        # Prefer openai (cheapest), fall back to whatever is available
        for pref in ("openai", "anthropic", "perplexity", "google"):
            if any(k["provider"] == pref and k["is_active"] for k in vault.list_keys()):
                os.environ["SYLION_LLM_PROVIDER"] = pref
                if not os.environ.get("SYLION_LLM_MODEL"):
                    defaults = {"openai": "gpt-4o-mini", "anthropic": "claude-haiku-4-5-20251001", "perplexity": "sonar", "google": "gemini-2.0-flash"}
                    os.environ["SYLION_LLM_MODEL"] = defaults.get(pref, "")
                log.info("set default LLM provider: %s (%s)", pref, os.environ.get("SYLION_LLM_MODEL", ""))
                break


def _seed_auth_data() -> None:
    """Seed default auth provider, RBAC roles, and admin user.

    Defensive: skips any step that fails because AuthProvider surface evolved
    (e.g. seed_roles/assign_role no longer exist). Phase 2 D-INTEGRATE
    relaxation — startup must not crash on optional seeding.
    """
    from sylion.security.auth_provider import get_auth_provider

    ap = get_auth_provider()

    try:
        providers = ap.list_providers(provider_type="local")
        if not providers:
            ap.register_provider("local", provider_type="local", config_json={})
            log.info("seeded local auth provider")
            providers = ap.list_providers(provider_type="local")
        provider_id = providers[0]["provider_id"]
    except Exception:
        log.warning("auth provider bootstrap skipped", exc_info=True)
        return

    roles = [
        {"code": "R-00", "name": "Root",          "permissions": ["*"], "mfa_required": True,  "requires_2pr": True,  "hierarchy_level": 7},
        {"code": "R-01", "name": "SecOfficer",    "permissions": ["security.*", "audit.*", "vault.*"], "mfa_required": True,  "requires_2pr": True,  "hierarchy_level": 6},
        {"code": "R-02", "name": "PipelineOp",    "permissions": ["pipeline.*", "execution.*", "modules.*"], "mfa_required": False, "requires_2pr": False, "hierarchy_level": 5},
        {"code": "R-03", "name": "CanonCust",     "permissions": ["governance.*", "proposals.*"], "mfa_required": False, "requires_2pr": False, "hierarchy_level": 4},
        {"code": "R-04", "name": "CostCtrl",      "permissions": ["budget.*", "cost.*", "monitoring.*"], "mfa_required": False, "requires_2pr": False, "hierarchy_level": 3},
        {"code": "R-05", "name": "Auditor",       "permissions": ["audit.read", "report.read"], "mfa_required": False, "requires_2pr": False, "hierarchy_level": 2},
        {"code": "R-06", "name": "ReadOnly",      "permissions": ["*.read"], "mfa_required": False, "requires_2pr": False, "hierarchy_level": 1},
    ]
    if hasattr(ap, "seed_roles"):
        try:
            ap.seed_roles(roles)
            log.info("seeded %d RBAC roles", len(roles))
        except Exception:
            log.warning("seed_roles failed", exc_info=True)
    else:
        log.info("auth provider has no seed_roles — skipping RBAC seed")

    admin_user = "admin"
    admin_password = (
        os.environ.get("SYLION_BOOTSTRAP_ADMIN_PASSWORD")
        or os.environ.get("SYLION_ADMIN_PASSWORD")
        or "admin"
    )
    try:
        sessions = ap.list_sessions(user_id=admin_user)
    except Exception:
        log.warning("list_sessions skipped", exc_info=True)
        return
    try:
        ap.create_user(
            admin_user,
            "admin",
            admin_password,
            role="owner",
            metadata={"source": "bootstrap"},
        )
        log.info("seeded local admin auth user")
    except ValueError:
        pass
    except Exception:
        log.warning("admin local auth user seed failed", exc_info=True)
    if not sessions:
        try:
            result = ap.authenticate(
                provider_id,
                {"user_id": admin_user, "password": admin_password},
            )
            if hasattr(ap, "assign_role"):
                ap.assign_role(admin_user, "R-00", assigned_by="system")
            log.info("seeded default admin user (token_id=%s)", result["token_id"][:12])
        except Exception:
            log.warning("admin user seed failed", exc_info=True)
    if sessions and admin_password != "admin":
        try:
            if ap.authenticate(admin_user, admin_password) is None and ap.authenticate(admin_user, "admin"):
                with ap._lock:  # Existing audit profiles may have been bootstrapped before the env alias existed.
                    ap._conn.execute(
                        "UPDATE auth_users SET password_hash = ? WHERE username = ? AND password_hash = ?",
                        (admin_password, admin_user, "admin"),
                    )
                    ap._conn.commit()
                log.info("updated bootstrap admin password from legacy default")
        except Exception:
            log.warning("admin password alias reconciliation skipped", exc_info=True)
    if sessions and hasattr(ap, "get_user_roles") and hasattr(ap, "assign_role"):
        try:
            user_roles = ap.get_user_roles(admin_user)
            if not user_roles:
                ap.assign_role(admin_user, "R-00", assigned_by="system")
                log.info("assigned Root role to existing admin")
        except Exception:
            log.warning("admin role check skipped", exc_info=True)


def _seed_dev_rbac_roles(db_path: str, event_bus) -> None:
    """Ensure the dev operator exists for anonymous advisor/orchestration calls."""
    from sylion.governance.roles import get_roles_manager

    roles = get_roles_manager(db_path=db_path, event_bus=event_bus)

    existing_roles = {role["name"]: role for role in roles.list_roles()}
    if "operator" not in existing_roles:
        existing_roles["operator"] = roles.create_role(
            "operator",
            description="Default operator role for API mutations",
            permissions_list=["*"],
        )
    if "owner" not in existing_roles:
        existing_roles["owner"] = roles.create_role(
            "owner",
            description="Default owner role for API mutations",
            permissions_list=["*"],
        )
    if "security" not in existing_roles:
        existing_roles["security"] = roles.create_role(
            "security",
            description="Security role: vault, secrets, RBAC, phantom",
            permissions_list=["*"],
        )
    if "compliance" not in existing_roles:
        existing_roles["compliance"] = roles.create_role(
            "compliance",
            description="Compliance role: policy, DPO, GDPR",
            permissions_list=["*"],
        )

    assigned_names = {role["name"] for role in roles.get_user_roles(_DEV_OPERATOR_ID)}
    if "operator" not in assigned_names:
        roles.assign_role(
            existing_roles["operator"]["role_id"],
            _DEV_OPERATOR_ID,
            assigned_by="system",
        )
    if "security" not in assigned_names:
        roles.assign_role(
            existing_roles["security"]["role_id"],
            _DEV_OPERATOR_ID,
            assigned_by="system",
        )

    # In audit mode the dev operator drives the dashboard end-to-end and must
    # be able to write secrets, vault keys, and hit security-gated endpoints
    # (Phase C, A3, Funding live discovery, deploy plane). Grant owner so the
    # audit can actually exercise these surfaces. Outside audit mode the
    # dev operator stays restricted to "operator".
    try:
        from sylion.aeis_v2.audit_profile import is_audit_mode

        audit_mode_active = is_audit_mode()
    except Exception:
        audit_mode_active = False
    if audit_mode_active and "owner" not in assigned_names:
        roles.assign_role(
            existing_roles["owner"]["role_id"],
            _DEV_OPERATOR_ID,
            assigned_by="audit-bootstrap",
        )

    admin_assigned = {role["name"] for role in roles.get_user_roles("admin")}
    if "owner" not in admin_assigned:
        roles.assign_role(
            existing_roles["owner"]["role_id"],
            "admin",
            assigned_by="system",
        )


def _seed_system_agents(event_bus) -> None:
    """Ensure the operator has a live baseline council/runtime roster."""
    try:
        from sylion.cognitive.agent_runtime import get_agent_runtime

        runtime = get_agent_runtime(event_bus=event_bus)
        existing_names = {
            str(agent.get("name") or "").strip().lower()
            for agent in runtime.list_agents()
        }
        baseline_agents = [
            {
                "name": "Chair",
                "agent_type": "council_chair",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "capabilities": ["council", "decision_ladder", "human_gate"],
                "system_prompt": "Coordinate council rounds, quorum, decision class and Human Gate handoff.",
            },
            {
                "name": "Planner",
                "agent_type": "planner",
                "provider": "anthropic",
                "model_id": "claude-haiku-4-5",
                "capabilities": ["planning", "scope_split", "risk_mapping"],
                "system_prompt": "Split project work into executable stages with explicit dependencies and risks.",
            },
            {
                "name": "Critic",
                "agent_type": "critic",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "capabilities": ["critique", "mock_detection", "regression_review"],
                "system_prompt": "Find weak assumptions, stubs, mocks, missing evidence and product-quality gaps.",
            },
            {
                "name": "Security",
                "agent_type": "security",
                "provider": "anthropic",
                "model_id": "claude-haiku-4-5",
                "capabilities": ["security", "secret_hygiene", "policy_guard"],
                "system_prompt": "Check secrets, policies, unsafe actions and security guard findings.",
            },
            {
                "name": "QA",
                "agent_type": "qa",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "capabilities": ["testing", "w14", "dashboard_clickthrough"],
                "system_prompt": "Design and execute acceptance tests, W14 release gates and dashboard click-through checks.",
            },
            {
                "name": "Funding Specialist",
                "agent_type": "funding",
                "provider": "perplexity",
                "model_id": "sonar",
                "capabilities": ["funding", "grant_readiness", "financial_gate"],
                "system_prompt": "Evaluate grants, budgets, financial commitments and funding governance gates.",
            },
            {
                "name": "Runtime Operator",
                "agent_type": "runtime_operator",
                "provider": "ollama",
                "model_id": "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M",
                "capabilities": ["runtime", "terminal", "local_verification"],
                "system_prompt": "Observe local runtime, terminal events, workers, environments and execution telemetry.",
            },
        ]
        seeded = 0
        for spec in baseline_agents:
            if spec["name"].lower() in existing_names:
                continue
            runtime.register_agent(
                name=spec["name"],
                agent_type=spec["agent_type"],
                provider=spec["provider"],
                model_id=spec["model_id"],
                system_prompt=spec["system_prompt"],
                capabilities=spec["capabilities"],
                tools=["dashboard", "api", "terminal"],
                config={"source": "system_startup_seed", "required_for_dashboard": True},
            )
            seeded += 1
        if seeded:
            log.info("seeded %d baseline system agents", seeded)
    except Exception:
        log.warning("system agent seed failed", exc_info=True)


def _seed_demo_data(db_path: str, event_bus) -> None:
    """Seed sample data so the UI is not empty on first run."""
    try:
        from sylion.aeis_v2.audit_profile import is_audit_mode

        if is_audit_mode():
            log.info("audit profile active; skipping demo seed data for clean first-run state")
            return
    except Exception:
        pass

    try:
        # Seed worker for fleet visibility
        from sylion.worker.registry import get_worker_registry
        wr = get_worker_registry(event_bus=event_bus)
        if len(wr.list_workers()) == 0:
            wr.register_worker("Demo-Worker", host="localhost", capacity=3,
                               tags=["demo", "seed"])
            log.info("seeded 1 demo worker")

        # Seed skill for registry visibility
        from sylion.skills.registry import get_skills_registry
        sr = get_skills_registry()
        if len(sr.list_skills(limit=1)) == 0:
            sr.register("seed_skill_001", "Demo Skill",
                        domain="core", description="Seeded demo skill")
            log.info("seeded 1 demo skill")

        # Seed improvements for autonomy page
        from sylion.aeis.improvement_queue import get_improvement_queue
        q = get_improvement_queue(db_path=db_path, event_bus=event_bus)
        if len(q.list_improvements(limit=1)) == 0:
            q.submit("Reduce event bus latency by 20%",
                     description="Batch event processing to reduce per-event overhead",
                     category="performance", priority=3, source="aeis.self_observation")
            q.submit("Auto-scale model router connections",
                     description="Dynamic connection pool scaling based on throughput",
                     category="performance", priority=5, source="cognitive.model_router")
            q.submit("Implement circuit breaker for external APIs",
                     description="Half-open circuit breaker pattern with adaptive thresholds",
                     category="security", priority=4, source="aeis.self_preservation")
            log.info("seeded 3 sample improvements")

        # Seed self-observation metrics
        from sylion.aeis.self_observation import get_self_observation
        obs = get_self_observation(db_path=db_path, event_bus=event_bus)
        if len(obs.get_dashboard()) == 0:
            obs.record("cpu", 35.0, unit="percent")
            obs.record("memory", 58.0, unit="percent")
            obs.record("events", 42.0, unit="per_min")
            log.info("seeded sample self-observation metrics")

        # Seed observability logs
        from sylion.observability.hub import ObservabilityHub
        from sylion.observability.log_aggregator import LogAggregator
        hub = ObservabilityHub(log_aggregator=LogAggregator())
        hub.log("sylion.api", "info", "System initialized with demo data")
        hub.log("sylion.worker", "info", "Worker fleet registered")
        log.info("seeded sample observability logs")

        # Seed governance proposals
        from sylion.governance.decision_ladder import get_decision_ladder, DecisionProposal
        ladder = get_decision_ladder()
        if len(ladder.list_proposals()) == 0:
            ladder.propose(DecisionProposal(
                title="Enable auto-scaling for model router",
                description="Automatically scale model router connections based on throughput metrics",
                source_plan="cognitive.model_router", change_type="config", blast_radius="medium"
            ))
            ladder.propose(DecisionProposal(
                title="Add circuit breaker for external APIs",
                description="Implement half-open circuit breaker with adaptive thresholds",
                source_plan="security.hardening", change_type="module", blast_radius="high"
            ))
            log.info("seeded 2 sample proposals")

        # Seed governance policies
        from sylion.governance.policy_registry import get_policy_registry
        pr = get_policy_registry(db_path=db_path)
        if len(pr.list_policies()) == 0:
            pr.register("policy_api_rate_limit", "API Rate Limit",
                        category="security", description="Max 100 req/min per API key",
                        enforcement="mandatory")
            pr.register("policy_cost_alert", "Cost Alert Threshold",
                        category="budget", description="Alert when daily spend exceeds $50",
                        enforcement="advisory")
            log.info("seeded 2 sample policies")

        # Seed governance gates
        from sylion.governance.gates_registry import get_gates_registry
        gr = get_gates_registry(db_path=db_path, event_bus=event_bus)
        if len(gr.list_gates()) == 0:
            gr.create_gate("D3 Council Review", gate_type="approval",
                           criteria_json={"min_votes": 3, "quorum": "majority"},
                           scope="governance")
            gr.create_gate("D4 Human Gate", gate_type="human_approval",
                           criteria_json={"requires_human": True, "timeout_hours": 48},
                           scope="governance")
            log.info("seeded 2 sample gates")

        # Seed decision snapshots for timeline
        from sylion.governance.decision_snapshot import get_decision_snapshot_manager
        dsm = get_decision_snapshot_manager(db_path=db_path, event_bus=event_bus)
        if len(dsm.list_snapshots(limit=1)) == 0:
            dsm.create_snapshot("decision-001",
                                context_json={"module": "governance", "topic": "auto_scaling"},
                                outcome="approved", confidence=0.92,
                                factors_list=[{"name": "risk_score", "value": 0.15, "weight": 0.4}])
            dsm.create_snapshot("decision-002",
                                context_json={"module": "security", "topic": "circuit_breaker"},
                                outcome="approved", confidence=0.88,
                                factors_list=[{"name": "blast_radius", "value": 0.3, "weight": 0.5}])
            log.info("seeded 2 sample decision snapshots")

        # Seed security findings and scans
        from sylion.security.security_audit import get_security_auditor
        sa = get_security_auditor(db_path=db_path, event_bus=event_bus)
        if len(sa.list_findings()) == 0:
            scan = sa.start_scan(scope="sylion.core", scan_type="full")
            sa.create_finding(
                title="Hardcoded API key in module registry",
                severity="high",
                description="API key found in source code of module_registry.py",
                module="core.module_registry",
                recommendation="Rotate key and move to KeyVault")
            sa.create_finding(
                title="Missing input validation on event bus",
                severity="medium",
                description="Event payload not validated before processing",
                module="core.event_bus",
                recommendation="Add schema validation to event handlers")
            sa.create_finding(
                title="Unauthenticated health endpoint exposes version",
                severity="low",
                description="/health returns version string without auth",
                module="api.health",
                recommendation="Consider removing version from public health")
            sa.complete_scan(scan["scan_id"], findings_count=3)
            log.info("seeded 3 security findings and 1 scan")

    except Exception as e:
        log.warning("demo data seeding failed (non-critical): %s", e)


# ---------------------------------------------------------------------------
# Database mode detection
# ---------------------------------------------------------------------------
# SYLION_DB_MODE=postgres  +  SYLION_DB_URL set  ->  PostgreSQL (asyncpg)
# Otherwise                                      ->  SQLite (default)
# ---------------------------------------------------------------------------

_PG_ENGINE = None  # lazily initialised async engine

# Bootstrap flow instance (lives across the app lifecycle)
_bootstrap_flow: BootstrapFlow | None = None


def _is_pg_mode() -> bool:
    from sylion.db import get_db_mode, get_db_url

    return get_db_mode() == "postgres" and bool(get_db_url())


def _db_url() -> str:
    from sylion.db import get_db_url

    return get_db_url()


def _event_mode() -> str:
    return os.environ.get("SYLION_EVENT_MODE", "sqlite").strip().lower()


def _nats_url() -> str:
    return os.environ.get("NATS_URL", "nats://localhost:4222")


def get_bootstrap_flow() -> BootstrapFlow | None:
    return _bootstrap_flow


def _get_runtime_module_count() -> int:
    registry = get_registry()
    get_all = getattr(registry, "get_all", None)
    if callable(get_all):
        return len(get_all())
    return len(registry.list_modules())


def _get_runtime_endpoint_count(api_app: FastAPI) -> int:
    return sum(1 for route in api_app.routes if hasattr(route, "endpoint"))


def _get_runtime_openapi_description(api_app: FastAPI) -> str:
    module_count = _get_runtime_module_count()
    endpoint_count = _get_runtime_endpoint_count(api_app)
    return (
        f"Autonomous Engineering Intelligence System - "
        f"{module_count} modules / {endpoint_count} endpoints (runtime)"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _PG_ENGINE, _bootstrap_flow

    _load_dotenv()
    # Phase 3 W2.2 (scope-fill): pull encrypted env secrets *before* the
    # production fail-fast check so an env-less operator who configured
    # secrets/{env}.yaml + SYLION_AGE_IDENTITY does not get blocked.
    _prime_secrets_from_sops()
    # Phase 3 W2.2: production fail-fast on dev-default secrets. No-op in
    # dev/test where SYLION_AEIS_ENV != "production".
    assert_safe_to_serve()
    _seed_auth_data()

    registry = get_registry()
    event_bus = get_event_bus()
    contract_registry = get_contract_registry(event_bus=event_bus)
    manifest_dir = Path(__file__).parent.parent / "contracts" / "manifests"

    # Auto-register modules from manifests in dependency order
    auto_register_modules(registry, manifest_dir, event_bus)
    _bootstrap_advisor_audit_subscriber(event_bus)

    if _is_pg_mode():
        from sylion.db.pg_migration import create_pg_engine, run_pg_migration
        _PG_ENGINE = create_pg_engine(_db_url())
        await run_pg_migration(_PG_ENGINE)
        db_path = ":memory:"
    else:
        from sylion.aeis_v2.audit_profile import resolve_db_path

        db_path = str(resolve_db_path("sylion_aeis.db"))

    # Initialize data singletons with persistent DB path so data survives restarts
    from sylion.cognitive.idea_vault import get_idea_vault
    from sylion.cognitive.llm_adapter import get_llm_adapter
    from sylion.cognitive.agent_runtime import reset_agent_runtime
    from sylion.cognitive.model_registry import reset_model_registry
    from sylion.cognitive.model_router import get_model_router
    from sylion.worker.registry import get_worker_registry
    from sylion.skills.bootstrap import bootstrap_truth_plane as bootstrap_skills_truth_plane
    from sylion.governance.human_gate import get_human_gate
    from sylion.monitoring.model_budget import reset_model_budget
    from sylion.security.key_vault import reset_key_vault
    from sylion.security.cloud_connectors import get_cloud_connector_store

    # Phase 2 D-INTEGRATE: governance unified plane MUST land before HumanGate
    # mirror so legacy submit_review() finds a configured TicketStore.
    # Order: audit_chain -> ticket_store -> human_gate.
    from sylion.governance.audit_chain import reset_audit_chain
    from sylion.governance.ticket import reset_ticket_store
    from sylion.security.audit_trail_aggregator import reset_audit_trail_aggregator
    from sylion.security.execution_guard import reset_execution_guard
    from sylion.funding_autopilot.routes import reset_funding_route_service

    reset_audit_trail_aggregator(db_path=db_path, event_bus=event_bus)
    reset_audit_chain(db_path=db_path, event_bus=event_bus)
    reset_ticket_store(db_path=db_path, event_bus=event_bus)
    reset_execution_guard(db_path=db_path, event_bus=event_bus)
    reset_funding_route_service(db_path=db_path)

    get_idea_vault(db_path=db_path, event_bus=event_bus)
    reset_model_registry(db_path=db_path, event_bus=event_bus)
    model_router = get_model_router(db_path=db_path, event_bus=event_bus)
    get_llm_adapter(model_router=model_router, db_path=db_path, event_bus=event_bus)
    reset_agent_runtime(db_path=db_path, event_bus=event_bus)
    _seed_system_agents(event_bus)
    get_worker_registry(db_path=db_path, event_bus=event_bus)
    get_human_gate(db_path=db_path, event_bus=event_bus)
    reset_key_vault(db_path=db_path, event_bus=event_bus)
    _seed_key_vault()
    # F-V10-006 fix: SecretProvider used `:memory:` by default, so /secrets/create
    # entries vanished after every uvicorn restart. Wire it to the audit-profile
    # DB path so secrets survive restarts in audit mode and dev mode alike.
    from sylion.security.secret_provider import reset_secret_provider as _reset_sp
    _reset_sp(db_path=db_path, event_bus=event_bus)
    get_cloud_connector_store(db_path=db_path, event_bus=event_bus)
    reset_model_budget(db_path=db_path, event_bus=event_bus)

    # W14 E2 wire-up: register 20 Testing Actions with the global registry.
    # Per docs/CLAUDE_AEIS_W14_TESTING.md sec 18 + W14_INTEGRATION_CONTRACTS C2.
    try:
        from sylion.aeis.testing.actions import register_testing_actions
        from sylion.aeis.testing.ontology import OntologyStore
        from sylion.governance.ticket import get_ticket_store
        from sylion.surface.command_bus import get_command_bus
        w14_ontology = OntologyStore(db_path=db_path, event_bus=event_bus)
        w14_tickets = get_ticket_store()
        w14_command_bus = get_command_bus(db_path=db_path, event_bus=event_bus)
        w14_handlers = register_testing_actions(
            bus=w14_command_bus,
            ontology=w14_ontology,
            tickets=w14_tickets,
            event_bus=event_bus,
        )
        log.info(
            "W14: registered %d testing action handlers (bus + tickets wired)",
            len(w14_handlers),
        )
    except Exception:
        log.warning("W14 actions registration failed (non-fatal)", exc_info=True)

    # Phase 2 D-INTEGRATE: shared memory plane (B3-B4 RB-003 / RB-016)
    from sylion.memory import bootstrap as memory_bootstrap
    memory_bootstrap({
        "db_path": db_path,
        "event_bus": event_bus,
    })

    # Phase 2 D-INTEGRATE: skills truth plane (B1 RB-015).
    # Registry, runtime and executor must share one db_path, and manifest seed
    # skills must be visible through both runtime and registry/UI surfaces.
    skills_dir = (
        os.environ.get("SYLION_SKILLS_DIR")
        or str(Path(__file__).parent.parent.parent.parent.parent / "manifests" / "skills")
    )
    try:
        skills_bootstrap = bootstrap_skills_truth_plane(
            db_path=db_path,
            skills_dir=skills_dir,
            event_bus=event_bus,
            reset=True,
        )
        if skills_bootstrap.get("skills_dir_exists"):
            log.info("skills truth plane initialized: %s", skills_bootstrap)
        else:
            log.warning("SYLION_SKILLS_DIR not found: %s", skills_dir)
    except Exception:
        log.warning("skills truth-plane bootstrap failed", exc_info=True)

    # Phase 2 D-INTEGRATE: operator mobile bridge (B5)
    from sylion.operator_mobile import (
        reset_operator_mobile_bridge,
        reset_operator_mobile_store,
    )
    mobile_db = db_path if db_path != ":memory:" else "operator_mobile.db"
    reset_operator_mobile_store(db_path=mobile_db)
    reset_operator_mobile_bridge(
        db_path=mobile_db,
        signing_secret=os.environ.get("SYLION_MOBILE_SIGNING_SECRET", "operator-mobile-dev-secret"),
    )
    log.info("operator_mobile bridge initialized")

    # Phase 2 D-INTEGRATE: autonomy stage machine (A5 RB-013) — eager init so
    # the singleton uses the configured db_path, not :memory:.
    from sylion.autonomy import get_autonomy_machine
    try:
        get_autonomy_machine(db_path=mobile_db)
        log.info("autonomy stage machine initialized")
    except TypeError:
        # Older signature without db_path arg — fall back to default
        get_autonomy_machine()

    from sylion.governance.decision_ladder import reset_decision_ladder
    from sylion.governance.policy_registry import get_policy_registry
    from sylion.governance.gates_registry import get_gates_registry
    from sylion.governance.decision_snapshot import get_decision_snapshot_manager
    _seed_dev_rbac_roles(db_path, event_bus)
    reset_decision_ladder(db_path=db_path, event_bus=event_bus)
    get_policy_registry(db_path=db_path)
    get_gates_registry(db_path=db_path, event_bus=event_bus)
    get_decision_snapshot_manager(db_path=db_path, event_bus=event_bus)

    from sylion.security.security_audit import reset_security_auditor
    reset_security_auditor(db_path=db_path, event_bus=event_bus)

    _bootstrap_flow = BootstrapFlow(
        db_path=db_path,
        event_bus=event_bus,
    )
    log.info("bootstrap flow initialized")

    # Seed demo data for autonomy / rebuild / governance visibility
    _seed_demo_data(db_path, event_bus)

    from sylion.api.ws_routes import start_event_bridge
    await start_event_bridge()

    yield

    if _PG_ENGINE is not None:
        await _PG_ENGINE.dispose()
        _PG_ENGINE = None


app = FastAPI(
    title="SYLION AEIS",
    version="3.5.0",
    description="Autonomous Engineering Intelligence System",
    lifespan=lifespan,
)


def custom_openapi():
    # F-002 follow-up (Kimi review): description references runtime endpoint
    # count, so we must regenerate the schema when route count changes — not
    # just patch the cached description. Cache key: (len(routes),).
    runtime_description = _get_runtime_openapi_description(app)
    cached = getattr(app, "openapi_schema", None)
    cached_route_count = getattr(app, "_openapi_route_count", None)
    current_route_count = len(app.routes)
    if cached and cached_route_count == current_route_count:
        # Schema still matches current route topology; just refresh description.
        cached["info"]["description"] = runtime_description
        return cached

    app.openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=runtime_description,
        routes=app.routes,
    )
    app._openapi_route_count = current_route_count
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    # Bug fixed 2026-04-28: hardcoded 3000/3001 broke when dev server
    # picked port 3002 after a restart. Use a regex allow-list for any
    # localhost dev port instead — keeps allow_credentials=True valid
    # (regex match, not wildcard).
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 3 W3.3: OTel tracing wiring. No-op unless SYLION_TRACING_ENABLED=1.
from sylion.observability.tracing import setup_tracing as _setup_tracing
_setup_tracing(app)


class AuthMiddleware(BaseHTTPMiddleware):
    """Attach user context from bearer token if present.

    v3.5 permissive mode: token is validated when provided, but not required.
    Endpoints that need enforcement should check request.state.user themselves.
    """

    PUBLIC_PATHS = {
        "/favicon.ico",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
    PUBLIC_PREFIXES = (
        "/api/v1/auth/",
    )

    @staticmethod
    def _auth_mode() -> str:
        configured = os.environ.get("SYLION_AUTH_MODE")
        if configured:
            return configured.strip().lower()
        runtime_env = os.environ.get("SYLION_AEIS_ENV", "").strip().lower()
        if runtime_env in {"production", "staging"}:
            return "strict"
        return "dev"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Allow CORS preflight
        if method == "OPTIONS":
            return await call_next(request)

        # Allow public paths without token check
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES):
            return await call_next(request)

        # Try to validate token if present
        auth_header = request.headers.get("Authorization", "")
        request.state.user = None
        request.state.token = None

        dev_api_path = (
            self._auth_mode() == "dev"
            and any(path == prefix or path.startswith(prefix + "/") for prefix in _DEV_AUTH_PATH_PREFIXES)
        )

        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            from sylion.security.auth_provider import get_auth_provider
            ap = get_auth_provider()
            result = ap.validate_token(token)
            if result:
                request.state.user = result["session"].get("user_id")
                request.state.token = token
            elif dev_api_path:
                # Browser sessions can keep a token_id from before a backend
                # restart. In dev/operator audit mode this stale bearer must
                # not turn the whole dashboard into 401s; strict/prod mode
                # still leaves request.state.user unset.
                request.state.user = _DEV_OPERATOR_ID
                request.state.token = "dev-bypass"
        elif dev_api_path:
            request.state.user = _DEV_OPERATOR_ID
            request.state.token = "dev-bypass"

        return await call_next(request)


class TerminalActivityMiddleware(BaseHTTPMiddleware):
    """Mirror operator-facing API activity into the W18 Terminal stream."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        should_emit = (
            path.startswith("/api/v1/")
            and method != "OPTIONS"
            and not any(path == prefix or path.startswith(prefix + "/") for prefix in _TERMINAL_ACTIVITY_SKIP_PREFIXES)
        )
        started = time.perf_counter()
        response = await call_next(request)
        if not should_emit:
            return response

        try:
            from sylion.aeis_v2.terminal.stream import TerminalEvent, get_broadcaster

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status_code", 0) or 0)
            severity = "error" if status_code >= 500 else "warn" if status_code >= 400 else "debug" if method == "GET" else "info"
            project_id = _terminal_project_id_from_path(path)
            get_broadcaster()._offer_without_loop(  # noqa: SLF001 - middleware bridges sync API activity to W18.
                TerminalEvent(
                    ts=time.time(),
                    layer=_terminal_layer_for_path(path),
                    module="api.dashboard",
                    host="local",
                    message=_terminal_activity_message(method, path, status_code, elapsed_ms),
                    severity=severity,
                    session_id=str(getattr(request.state, "terminal_session_id", "") or ""),
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "elapsed_ms": elapsed_ms,
                        "project_id": project_id,
                        "operator_id": str(getattr(request.state, "user", "") or ""),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("terminal activity emit failed for %s %s: %s", method, path, exc)
        return response


# Phase 3 W2.3 + W2.4: middleware stack ordering.
# Starlette wraps middleware so the LAST add_middleware is the OUTERMOST
# (sees the request first). We need:
#   request → AuthMiddleware → RBACEnforcement → RateLimit → route
# so AuthMiddleware can populate request.state.user before RBAC reads it,
# and RBAC can deny before rate-limit accounting fires.
# Source order therefore: RateLimit (innermost), RBAC, Auth (outermost).
app.add_middleware(TerminalActivityMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RBACEnforcementMiddleware)
app.add_middleware(AuthMiddleware)

app.include_router(router)
app.include_router(faq_router)
app.include_router(testing_router)
app.include_router(test_center_router)
app.include_router(role_catalog_router)
app.include_router(agent_theater_router)
app.include_router(agent_theater_ws_router)
app.include_router(demo_mobile_inspector_router)
app.include_router(demo_portal_router)
app.include_router(demo_factory_router)
app.include_router(demo_crm_router)
app.include_router(demo_funding_router)
app.include_router(demo_marketplace_router)
# v2 routers
app.include_router(ontology_v2_router)
app.include_router(terminal_v2_router)
app.include_router(federation_v2_router)
app.include_router(apps_v2_router)
app.include_router(policy_v2_router)
app.include_router(gdpr_v2_router)
app.include_router(metrics_v2_router)
app.include_router(health_v2_router)
app.include_router(council_signoff_router)
app.include_router(replay_v2_router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/api/v1/health")
@app.get("/health")
async def health():
    from sylion.core.module_registry import get_registry
    registry = get_registry()
    module_count = len(registry.list_modules())
    endpoint_count = sum(1 for r in app.routes if hasattr(r, "endpoint"))
    info = {
        "status": "ok",
        "version": "3.5.0",
        "modules": module_count,
        "endpoints": endpoint_count,
        "db_mode": "postgres" if _is_pg_mode() else "sqlite",
        "event_mode": _event_mode(),
    }

    if _is_pg_mode() and _PG_ENGINE is not None:
        from sylion.db.pg_migration import check_pg_health
        pg_info = await check_pg_health(_PG_ENGINE)
        info["db_health"] = pg_info

    if _event_mode() == "nats":
        from sylion.core.nats_health import check_nats_health
        nats_info = check_nats_health(_nats_url())
        info["nats_health"] = nats_info

    return info
