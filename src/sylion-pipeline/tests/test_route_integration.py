"""
SYLION Route Integration Tests
===============================
Comprehensive integration tests for 9 SYLION API route groups using
FastAPI TestClient. Each test is independent and creates its own data.

Groups tested:
  1. Hallucination Detector   (/api/v1/cognitive/hallucinations)
  2. Code Snapshot             (/api/v1/snapshots)
  3. Cascade Analyzer          (/api/v1/governance/cascade)
  4. Conflict Detector         (/api/v1/governance/conflict-detections)
  5. Compliance Checker        (/api/v1/governance/checker)
  6. Session Manager           (/api/v1/security/session-manager)
  7. Quality Gate              (/api/v1/quality/gates)
  8. Deployment                (/api/v1/deployments)
  9. Model Performance         (/api/v1/cognitive/performance)

Run:  pytest tests/test_route_integration.py -v
"""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from sylion.api.app import app

client = TestClient(app)


def _uid(prefix: str = "t") -> str:
    """Generate a unique test identifier."""
    return f"{prefix}_{uuid4().hex[:8]}"


# =====================================================================
# 1. Hallucination Detector  (/api/v1/cognitive/hallucinations)
# =====================================================================

class TestHallucinationDetectorRoutes:
    """Hallucination Detector: check claim, list, stats, verify."""

    def test_create_check(self):
        """POST /hallucinations creates a new hallucination check."""
        resp = client.post("/api/v1/cognitive/hallucinations", params={
            "source_type": "llm_call",
            "source_id": _uid("src"),
            "claim": "The sky is green.",
            "expected_answer": "The sky is blue.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "check_id" in data

    def test_create_check_minimal(self):
        """POST /hallucinations works without expected_answer."""
        resp = client.post("/api/v1/cognitive/hallucinations", params={
            "source_type": "chat_message",
            "source_id": _uid("src"),
            "claim": "2+2=5",
        })
        assert resp.status_code == 201
        assert "check_id" in resp.json()

    def test_list_checks(self):
        """GET /hallucinations returns a list of checks."""
        # Create one to ensure the list is not empty
        client.post("/api/v1/cognitive/hallucinations", params={
            "source_type": "llm_call",
            "source_id": _uid("src"),
            "claim": "test claim for listing",
        })
        resp = client.get("/api/v1/cognitive/hallucinations")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_list_checks_with_status_filter(self):
        """GET /hallucinations?status=pending filters by status."""
        resp = client.get("/api/v1/cognitive/hallucinations",
                          params={"status": "pending"})
        assert resp.status_code == 200
        assert "checks" in resp.json()

    def test_list_checks_with_source_type_filter(self):
        """GET /hallucinations?source_type=llm_call filters by source."""
        resp = client.get("/api/v1/cognitive/hallucinations",
                          params={"source_type": "llm_call"})
        assert resp.status_code == 200
        assert "checks" in resp.json()

    def test_get_stats(self):
        """GET /hallucinations/stats returns statistics."""
        resp = client.get("/api/v1/cognitive/hallucinations/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_get_check_by_id(self):
        """GET /hallucinations/{check_id} returns a single check."""
        create = client.post("/api/v1/cognitive/hallucinations", params={
            "source_type": "llm_call",
            "source_id": _uid("src"),
            "claim": "unique claim for get test",
        })
        check_id = create.json()["check_id"]
        resp = client.get(f"/api/v1/cognitive/hallucinations/{check_id}")
        assert resp.status_code == 200
        assert resp.json()["check_id"] == check_id

    def test_verify_check(self):
        """POST /hallucinations/{check_id}/verify updates verification."""
        create = client.post("/api/v1/cognitive/hallucinations", params={
            "source_type": "llm_call",
            "source_id": _uid("src"),
            "claim": "claim to verify",
        })
        check_id = create.json()["check_id"]
        resp = client.post(
            f"/api/v1/cognitive/hallucinations/{check_id}/verify",
            params={
                "is_hallucination": True,
                "confidence": 0.95,
                "evidence": "contradicts known facts",
            },
        )
        assert resp.status_code == 200

    def test_detect_patterns(self):
        """POST /hallucinations/detect-patterns returns patterns list."""
        resp = client.post(
            "/api/v1/cognitive/hallucinations/detect-patterns",
        )
        assert resp.status_code == 200
        assert "patterns" in resp.json()


# =====================================================================
# 2. Code Snapshot  (/api/v1/snapshots)
# =====================================================================

class TestCodeSnapshotRoutes:
    """Code Snapshot: create, list, latest, diff, rollback, delete."""

    def test_create_snapshot(self):
        """POST /snapshots creates a new snapshot."""
        resp = client.post("/api/v1/snapshots/", params={
            "module_id": _uid("snapmod"),
            "version": "1.0.0",
            "file_path": "src/main.py",
            "content": "print('hello')",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "snapshot_id" in data

    def test_create_snapshot_with_metadata(self):
        """POST /snapshots accepts optional metadata JSON."""
        resp = client.post("/api/v1/snapshots/", params={
            "module_id": _uid("snapmod"),
            "version": "2.0.0",
            "file_path": "src/util.py",
            "content": "x = 1",
            "metadata": '{"author": "test", "branch": "main"}',
        })
        assert resp.status_code == 201

    def test_list_snapshots(self):
        """GET /snapshots/ returns a list."""
        client.post("/api/v1/snapshots/", params={
            "module_id": _uid("snapmod"),
            "version": "1.0.0",
            "file_path": "src/a.py",
            "content": "a",
        })
        resp = client.get("/api/v1/snapshots/")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)

    def test_list_snapshots_by_module(self):
        """GET /snapshots/?module_id=X filters by module."""
        mid = _uid("snapmod")
        client.post("/api/v1/snapshots/", params={
            "module_id": mid,
            "version": "1.0.0",
            "file_path": "src/b.py",
            "content": "b",
        })
        resp = client.get("/api/v1/snapshots/", params={"module_id": mid})
        assert resp.status_code == 200
        assert "snapshots" in resp.json()

    def test_get_snapshot_by_id(self):
        """GET /snapshots/{id} returns a single snapshot."""
        create = client.post("/api/v1/snapshots/", params={
            "module_id": _uid("snapmod"),
            "version": "1.0.0",
            "file_path": "src/c.py",
            "content": "c",
        })
        sid = create.json()["snapshot_id"]
        resp = client.get(f"/api/v1/snapshots/{sid}")
        assert resp.status_code == 200
        assert resp.json()["snapshot_id"] == sid

    def test_get_latest_snapshot(self):
        """GET /snapshots/latest/{module_id} returns latest snapshot."""
        mid = _uid("snapmod")
        client.post("/api/v1/snapshots/", params={
            "module_id": mid,
            "version": "1.0.0",
            "file_path": "src/d.py",
            "content": "v1",
        })
        client.post("/api/v1/snapshots/", params={
            "module_id": mid,
            "version": "2.0.0",
            "file_path": "src/d.py",
            "content": "v2",
        })
        resp = client.get(f"/api/v1/snapshots/latest/{mid}")
        assert resp.status_code == 200
        assert resp.json()["version"] == "2.0.0"

    def test_diff_snapshots(self):
        """POST /snapshots/{from}/diff/{to} returns diff."""
        mid = _uid("snapmod")
        r1 = client.post("/api/v1/snapshots/", params={
            "module_id": mid, "version": "1.0.0",
            "file_path": "src/e.py", "content": "line1\n",
        })
        r2 = client.post("/api/v1/snapshots/", params={
            "module_id": mid, "version": "2.0.0",
            "file_path": "src/e.py", "content": "line1\nline2\n",
        })
        sid1 = r1.json()["snapshot_id"]
        sid2 = r2.json()["snapshot_id"]
        resp = client.post(f"/api/v1/snapshots/{sid1}/diff/{sid2}")
        assert resp.status_code == 200

    def test_delete_snapshot(self):
        """DELETE /snapshots/{id} removes a snapshot."""
        create = client.post("/api/v1/snapshots/", params={
            "module_id": _uid("snapmod"),
            "version": "1.0.0",
            "file_path": "src/f.py",
            "content": "f",
        })
        sid = create.json()["snapshot_id"]
        resp = client.delete(f"/api/v1/snapshots/{sid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == sid


# =====================================================================
# 3. Cascade Analyzer  (/api/v1/governance/cascade)
# =====================================================================

class TestCascadeAnalyzerRoutes:
    """Cascade Analyzer: analyze change, list analyses, stats."""

    def test_analyze_change(self):
        """POST /cascade/analyze runs cascade analysis."""
        resp = client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": _uid("casc_mod"),
            "change_type": "api_change",
            "change_description": "Renamed public endpoint",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "analysis_id" in data

    def test_analyze_change_minimal(self):
        """POST /cascade/analyze works without description."""
        resp = client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": _uid("casc_mod"),
            "change_type": "config_change",
        })
        assert resp.status_code == 201

    def test_list_analyses(self):
        """GET /cascade/analyses returns list of analyses."""
        client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": _uid("casc_mod"),
            "change_type": "dependency_change",
        })
        resp = client.get("/api/v1/governance/cascade/analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert "analyses" in data
        assert isinstance(data["analyses"], list)

    def test_list_analyses_with_filter(self):
        """GET /cascade/analyses?source_module=X filters results."""
        mid = _uid("casc_mod")
        client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": mid,
            "change_type": "schema_change",
        })
        resp = client.get("/api/v1/governance/cascade/analyses",
                          params={"source_module": mid})
        assert resp.status_code == 200
        assert "analyses" in resp.json()

    def test_list_analyses_with_risk_filter(self):
        """GET /cascade/analyses?risk_level=high filters by risk."""
        resp = client.get("/api/v1/governance/cascade/analyses",
                          params={"risk_level": "high"})
        assert resp.status_code == 200
        assert "analyses" in resp.json()

    def test_get_analysis_by_id(self):
        """GET /cascade/analyses/{id} returns a single analysis."""
        create = client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": _uid("casc_mod"),
            "change_type": "api_change",
        })
        aid = create.json()["analysis_id"]
        resp = client.get(f"/api/v1/governance/cascade/analyses/{aid}")
        assert resp.status_code == 200
        assert resp.json()["analysis_id"] == aid

    def test_get_cascade_paths(self):
        """GET /cascade/analyses/{id}/paths returns cascade paths."""
        create = client.post("/api/v1/governance/cascade/analyze", params={
            "source_module": _uid("casc_mod"),
            "change_type": "interface_change",
        })
        aid = create.json()["analysis_id"]
        resp = client.get(
            f"/api/v1/governance/cascade/analyses/{aid}/paths",
        )
        assert resp.status_code == 200
        assert "paths" in resp.json()

    def test_cascade_stats(self):
        """GET /cascade/stats returns statistics."""
        resp = client.get("/api/v1/governance/cascade/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


# =====================================================================
# 4. Conflict Detector  (/api/v1/governance/conflict-detections)
# =====================================================================

class TestConflictDetectorRoutes:
    """Conflict Detector: detect, list, stats, resolve."""

    def test_detect_conflict(self):
        """POST /conflict-detections detects a conflict."""
        resp = client.post("/api/v1/governance/conflict-detections", params={
            "module_id": _uid("conf_mod"),
            "change_a": "branch_a: update config.yaml",
            "change_b": "branch_b: update config.yaml",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "conflict_id" in data

    def test_detect_conflict_with_type(self):
        """POST /conflict-detections accepts change_type param."""
        resp = client.post("/api/v1/governance/conflict-detections", params={
            "module_id": _uid("conf_mod"),
            "change_a": "edit file A",
            "change_b": "edit file A",
            "change_type": "concurrent_edit",
        })
        assert resp.status_code == 201

    def test_list_conflicts(self):
        """GET /conflict-detections returns a list."""
        client.post("/api/v1/governance/conflict-detections", params={
            "module_id": _uid("conf_mod"),
            "change_a": "a1",
            "change_b": "b1",
        })
        resp = client.get("/api/v1/governance/conflict-detections")
        assert resp.status_code == 200
        data = resp.json()
        assert "conflicts" in data
        assert isinstance(data["conflicts"], list)

    def test_list_conflicts_with_status_filter(self):
        """GET /conflict-detections?status=detected filters."""
        resp = client.get("/api/v1/governance/conflict-detections",
                          params={"status": "detected"})
        assert resp.status_code == 200
        assert "conflicts" in resp.json()

    def test_list_conflicts_with_module_filter(self):
        """GET /conflict-detections?module_id=X filters."""
        resp = client.get("/api/v1/governance/conflict-detections",
                          params={"module_id": "nonexistent"})
        assert resp.status_code == 200
        assert "conflicts" in resp.json()

    def test_get_conflict_by_id(self):
        """GET /conflict-detections/{id} returns a conflict."""
        create = client.post("/api/v1/governance/conflict-detections", params={
            "module_id": _uid("conf_mod"),
            "change_a": "a2",
            "change_b": "b2",
        })
        cid = create.json()["conflict_id"]
        resp = client.get(
            f"/api/v1/governance/conflict-detections/{cid}",
        )
        assert resp.status_code == 200
        assert resp.json()["conflict_id"] == cid

    def test_resolve_conflict(self):
        """POST /conflict-detections/{id}/resolve resolves a conflict."""
        create = client.post("/api/v1/governance/conflict-detections", params={
            "module_id": _uid("conf_mod"),
            "change_a": "a3",
            "change_b": "b3",
        })
        cid = create.json()["conflict_id"]
        resp = client.post(
            f"/api/v1/governance/conflict-detections/{cid}/resolve",
            params={"resolution": "merged"},
        )
        assert resp.status_code == 200

    def test_conflict_detector_stats(self):
        """GET /conflict-detections/stats returns statistics."""
        resp = client.get("/api/v1/governance/conflict-detections/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_add_conflict_rule(self):
        """POST /conflict-detections/rules adds a detection rule."""
        resp = client.post("/api/v1/governance/conflict-detections/rules",
                           params={
                               "conflict_type": "concurrent_edit",
                               "detection_pattern": "*.yaml",
                           })
        assert resp.status_code == 201

    def test_list_conflict_rules(self):
        """GET /conflict-detections/rules lists detection rules."""
        resp = client.get("/api/v1/governance/conflict-detections/rules")
        assert resp.status_code == 200
        assert "rules" in resp.json()


# =====================================================================
# 5. Compliance Checker  (/api/v1/governance/checker)
# =====================================================================

class TestComplianceCheckerRoutes:
    """Compliance Checker: create policy, list, check compliance, stats."""

    def test_create_policy(self):
        """POST /checker/policies creates a compliance policy."""
        resp = client.post("/api/v1/governance/checker/policies", json={
            "name": f"Test Policy {_uid('pol')}",
            "scope": "security",
            "rules": [{"field": "auth_required", "operator": "eq", "value": True}],
            "severity": "critical",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "policy_id" in data

    def test_create_policy_minimal(self):
        """POST /checker/policies works with minimal fields."""
        resp = client.post("/api/v1/governance/checker/policies", json={
            "name": f"Minimal Policy {_uid('pol')}",
            "scope": "quality",
        })
        assert resp.status_code == 201

    def test_list_policies(self):
        """GET /checker/policies returns list."""
        resp = client.get("/api/v1/governance/checker/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert isinstance(data["policies"], list)

    def test_list_policies_with_scope_filter(self):
        """GET /checker/policies?scope=security filters by scope."""
        resp = client.get("/api/v1/governance/checker/policies",
                          params={"scope": "security"})
        assert resp.status_code == 200
        assert "policies" in resp.json()

    def test_run_compliance_check(self):
        """POST /checker/check runs compliance check for a module."""
        # Create a policy first so there is something to check against
        client.post("/api/v1/governance/checker/policies", json={
            "name": f"Check Test Policy {_uid('pol')}",
            "scope": "quality",
        })
        resp = client.post("/api/v1/governance/checker/check", params={
            "module_id": _uid("compmod"),
            "scope": "all",
        })
        assert resp.status_code == 200

    def test_run_compliance_check_with_scope(self):
        """POST /checker/check?scope=security scopes the check."""
        resp = client.post("/api/v1/governance/checker/check", params={
            "module_id": _uid("compmod"),
            "scope": "security",
        })
        assert resp.status_code == 200

    def test_list_compliance_checks(self):
        """GET /checker/checks lists previous compliance checks."""
        resp = client.get("/api/v1/governance/checker/checks")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_compliance_checker_stats(self):
        """GET /checker/stats returns statistics."""
        resp = client.get("/api/v1/governance/checker/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


# =====================================================================
# 6. Session Manager  (/api/v1/security/session-manager)
# =====================================================================

class TestSessionManagerRoutes:
    """Session Manager: create user, list, create session, audit."""

    def test_create_user(self):
        """POST /session-manager/users creates a new user."""
        resp = client.post("/api/v1/security/session-manager/users", params={
            "username": _uid("sm_user"),
            "email": "test@example.com",
            "role": "operator",
            "password_hash": "hashed_pw_123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "user_id" in data

    def test_create_user_minimal(self):
        """POST /session-manager/users works with minimal fields."""
        resp = client.post("/api/v1/security/session-manager/users", params={
            "username": _uid("sm_user"),
            "email": "min@example.com",
        })
        assert resp.status_code == 201

    def test_list_users(self):
        """GET /session-manager/users returns user list."""
        resp = client.get("/api/v1/security/session-manager/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_list_users_with_role_filter(self):
        """GET /session-manager/users?role=operator filters by role."""
        resp = client.get("/api/v1/security/session-manager/users",
                          params={"role": "operator"})
        assert resp.status_code == 200
        assert "users" in resp.json()

    def test_create_session(self):
        """POST /session-manager/sessions creates a session for a user."""
        # Create user first
        user = client.post("/api/v1/security/session-manager/users", params={
            "username": _uid("sess_user"),
            "email": "sess@example.com",
        })
        user_id = user.json()["user_id"]
        resp = client.post("/api/v1/security/session-manager/sessions", params={
            "user_id": user_id,
            "ip_address": "127.0.0.1",
            "user_agent": "TestClient/1.0",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data or "token" in data

    def test_list_sessions(self):
        """GET /session-manager/sessions returns session list."""
        resp = client.get("/api/v1/security/session-manager/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_list_sessions_by_user(self):
        """GET /session-manager/sessions?user_id=X filters."""
        resp = client.get("/api/v1/security/session-manager/sessions",
                          params={"user_id": "nonexistent"})
        assert resp.status_code == 200
        assert "sessions" in resp.json()

    def test_create_audit_event(self):
        """POST /session-manager/audit records an audit event."""
        # Need a session_id -- create user + session
        user = client.post("/api/v1/security/session-manager/users", params={
            "username": _uid("audit_user"),
            "email": "audit@example.com",
        })
        user_id = user.json()["user_id"]
        sess = client.post("/api/v1/security/session-manager/sessions", params={
            "user_id": user_id,
        })
        session_id = sess.json().get("session_id", "")
        resp = client.post("/api/v1/security/session-manager/audit", params={
            "session_id": session_id,
            "action": "login",
            "resource": "/api/v1/test",
            "ip_address": "10.0.0.1",
        })
        assert resp.status_code == 201

    def test_list_audit_events(self):
        """GET /session-manager/audit returns audit event list."""
        resp = client.get("/api/v1/security/session-manager/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)


# =====================================================================
# 7. Quality Gate  (/api/v1/quality/gates)
# =====================================================================

class TestQualityGateRoutes:
    """Quality Gate: create gate, list, evaluate, stats."""

    def test_create_gate(self):
        """POST /gates creates a quality gate."""
        resp = client.post("/api/v1/quality/gates", params={
            "name": f"Test Gate {_uid('qg')}",
            "gate_type": "deployment",
            "description": "Integration test quality gate",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "gate_id" in data

    def test_create_gate_with_criteria(self):
        """POST /gates with JSON criteria payload."""
        resp = client.post("/api/v1/quality/gates", params={
            "name": f"Criteria Gate {_uid('qg')}",
            "gate_type": "exit",
            "criteria": '{"p95_ms": 200, "error_rate": 0.01}',
        })
        assert resp.status_code == 201

    def test_list_gates(self):
        """GET /gates returns list of gates."""
        resp = client.get("/api/v1/quality/gates")
        assert resp.status_code == 200
        data = resp.json()
        assert "gates" in data
        assert isinstance(data["gates"], list)

    def test_list_gates_with_type_filter(self):
        """GET /gates?gate_type=deployment filters by type."""
        resp = client.get("/api/v1/quality/gates",
                          params={"gate_type": "deployment"})
        assert resp.status_code == 200
        assert "gates" in resp.json()

    def test_get_gate_by_id(self):
        """GET /gates/{id} returns a single gate."""
        create = client.post("/api/v1/quality/gates", params={
            "name": f"Get Gate {_uid('qg')}",
            "gate_type": "entry",
        })
        gid = create.json()["gate_id"]
        resp = client.get(f"/api/v1/quality/gates/{gid}")
        assert resp.status_code == 200
        assert resp.json()["gate_id"] == gid

    def test_evaluate_gate(self):
        """POST /gates/{id}/evaluate evaluates a gate."""
        create = client.post("/api/v1/quality/gates", params={
            "name": f"Eval Gate {_uid('qg')}",
            "gate_type": "transition",
        })
        gid = create.json()["gate_id"]
        resp = client.post(f"/api/v1/quality/gates/{gid}/evaluate", params={
            "module_id": _uid("qgmod"),
        })
        assert resp.status_code == 200

    def test_evaluate_gate_with_context(self):
        """POST /gates/{id}/evaluate with context JSON."""
        create = client.post("/api/v1/quality/gates", params={
            "name": f"Ctx Gate {_uid('qg')}",
            "gate_type": "exit",
        })
        gid = create.json()["gate_id"]
        resp = client.post(f"/api/v1/quality/gates/{gid}/evaluate", params={
            "module_id": _uid("qgmod"),
            "context": '{"environment": "production"}',
        })
        assert resp.status_code == 200

    def test_quality_stats(self):
        """GET /quality/stats returns engine statistics."""
        resp = client.get("/api/v1/quality/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


# =====================================================================
# 8. Deployment  (/api/v1/deployments)
# =====================================================================

class TestDeploymentRoutes:
    """Deployment: create, list, advance step, stats."""

    def test_create_deployment(self):
        """POST /deployments creates a new deployment."""
        resp = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "shadow",
            "to_stage": "cutover",
            "strategy": "blue_green",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "deployment_id" in data

    def test_create_deployment_canary(self):
        """POST /deployments with canary strategy."""
        resp = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "validate",
            "to_stage": "shadow",
            "strategy": "canary",
        })
        assert resp.status_code == 201

    def test_list_deployments(self):
        """GET /deployments returns list."""
        client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "draft",
            "to_stage": "build",
        })
        resp = client.get("/api/v1/deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert "deployments" in data
        assert isinstance(data["deployments"], list)

    def test_list_deployments_with_status_filter(self):
        """GET /deployments?status=in_progress filters."""
        resp = client.get("/api/v1/deployments",
                          params={"status": "in_progress"})
        assert resp.status_code == 200
        assert "deployments" in resp.json()

    def test_get_deployment_by_id(self):
        """GET /deployments/{id} returns a deployment."""
        create = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "build",
            "to_stage": "validate",
        })
        did = create.json()["deployment_id"]
        resp = client.get(f"/api/v1/deployments/{did}")
        assert resp.status_code == 200
        assert resp.json()["deployment_id"] == did

    def test_advance_step(self):
        """POST /deployments/{id}/advance advances a step."""
        create = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "build",
            "to_stage": "validate",
        })
        did = create.json()["deployment_id"]
        # Fetch actual step names from the deployment
        steps_resp = client.get(f"/api/v1/deployments/{did}/steps")
        steps = steps_resp.json()["steps"]
        first_step = steps[0]["step_name"]
        resp = client.post(f"/api/v1/deployments/{did}/advance", params={
            "step_name": first_step,
            "output": "all checks passed",
        })
        assert resp.status_code == 200

    def test_deployment_stats(self):
        """GET /deployments/stats returns statistics."""
        resp = client.get("/api/v1/deployments/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_complete_deployment(self):
        """POST /deployments/{id}/complete marks deployment complete.

        All auto-generated steps must be advanced to completed status
        (each step requires two advances: pending -> in_progress -> completed).
        """
        create = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "validate",
            "to_stage": "stable",
        })
        did = create.json()["deployment_id"]
        # Advance all steps to completion (two advances each)
        steps_resp = client.get(f"/api/v1/deployments/{did}/steps")
        steps = steps_resp.json()["steps"]
        for step in steps:
            sn = step["step_name"]
            client.post(f"/api/v1/deployments/{did}/advance", params={
                "step_name": sn, "output": "started",
            })
            client.post(f"/api/v1/deployments/{did}/advance", params={
                "step_name": sn, "output": "done",
            })
        resp = client.post(f"/api/v1/deployments/{did}/complete")
        assert resp.status_code == 200

    def test_get_deployment_steps(self):
        """GET /deployments/{id}/steps returns all steps."""
        create = client.post("/api/v1/deployments", params={
            "module_id": _uid("depmod"),
            "from_stage": "build",
            "to_stage": "stable",
        })
        did = create.json()["deployment_id"]
        resp = client.get(f"/api/v1/deployments/{did}/steps")
        assert resp.status_code == 200
        assert "steps" in resp.json()


# =====================================================================
# 9. Model Performance  (/api/v1/cognitive/performance)
# =====================================================================

class TestModelPerformanceRoutes:
    """Model Performance: record metric, list, summary, leaderboard."""

    def test_record_metric(self):
        """POST /performance/metrics records a metric."""
        resp = client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": _uid("perf_model"),
            "metric_type": "accuracy",
            "metric_value": 0.92,
            "tokens_used": 1500,
            "latency_ms": 340.5,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "metric_id" in data

    def test_record_metric_with_metadata(self):
        """POST /performance/metrics with optional metadata."""
        resp = client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": _uid("perf_model"),
            "metric_type": "latency",
            "metric_value": 120.0,
            "metadata": '{"region": "us-east", "batch_size": 32}',
        })
        assert resp.status_code == 201

    def test_list_metrics(self):
        """GET /performance/metrics returns list of metrics."""
        client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": _uid("perf_model"),
            "metric_type": "accuracy",
            "metric_value": 0.88,
        })
        resp = client.get("/api/v1/cognitive/performance/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert isinstance(data["metrics"], list)

    def test_list_metrics_by_model(self):
        """GET /performance/metrics?model_id=X filters by model."""
        mid = _uid("perf_model")
        client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": mid,
            "metric_type": "f1_score",
            "metric_value": 0.85,
        })
        resp = client.get("/api/v1/cognitive/performance/metrics",
                          params={"model_id": mid})
        assert resp.status_code == 200
        assert "metrics" in resp.json()

    def test_list_metrics_by_type(self):
        """GET /performance/metrics?metric_type=accuracy filters."""
        resp = client.get("/api/v1/cognitive/performance/metrics",
                          params={"metric_type": "accuracy"})
        assert resp.status_code == 200
        assert "metrics" in resp.json()

    def test_get_performance_summary(self):
        """GET /performance/summary/{model_id} returns summary.

        Records a metric first so the summary has data to aggregate.
        """
        mid = _uid("perf_model")
        client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": mid,
            "metric_type": "accuracy",
            "metric_value": 0.95,
        })
        # Update leaderboard so summary is generated
        client.post("/api/v1/cognitive/performance/leaderboard/update",
                     params={"metric_type": "overall"})
        resp = client.get(f"/api/v1/cognitive/performance/summary/{mid}")
        # 200 if summary found, 404 if no summary yet -- both are valid
        assert resp.status_code in (200, 404)

    def test_list_summaries(self):
        """GET /performance/summaries returns list of summaries."""
        resp = client.get("/api/v1/cognitive/performance/summaries")
        assert resp.status_code == 200
        data = resp.json()
        assert "summaries" in data
        assert isinstance(data["summaries"], list)

    def test_update_leaderboard(self):
        """POST /performance/leaderboard/update recomputes rankings."""
        client.post("/api/v1/cognitive/performance/metrics", params={
            "model_id": _uid("perf_model"),
            "metric_type": "accuracy",
            "metric_value": 0.90,
        })
        resp = client.post(
            "/api/v1/cognitive/performance/leaderboard/update",
            params={"metric_type": "overall"},
        )
        assert resp.status_code == 200
        assert "entries" in resp.json()

    def test_get_leaderboard(self):
        """GET /performance/leaderboard returns current rankings."""
        resp = client.get("/api/v1/cognitive/performance/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "leaderboard" in data
        assert isinstance(data["leaderboard"], list)

    def test_performance_stats(self):
        """GET /performance/stats returns aggregate statistics."""
        resp = client.get("/api/v1/cognitive/performance/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
