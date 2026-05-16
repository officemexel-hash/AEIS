"""AR-6.3 — W18 Phase 1 real-output command tests.

The seven W18 slash-commands flagged in F-W18-1 (P3) used to return
hard-coded "skeleton" / "not_implemented" placeholders. AR-6.2 wires
each of them to real data sources (health/v2, cost ledger, council
roles, DecisionGateEngine, SecurityAuditor, ProjectModeStore). These
tests pin the contract:

  test_status_real_output         — services + sessions + tickets, no "skeleton"
  test_cost_real_output           — total_usd + breakdown, not placeholder
  test_agents_real_output         — exactly 9 canonical roles + 2 sentinels
  test_explain_real_output        — most-recent decision rationale
  test_findings_real_output       — open security findings
  test_budget_real_output         — projects with cost_cap + spent
  test_report_current_run_real_output — newest project (max updated_at)

The tests do NOT require a fully-running app; they call ``parse_command``
directly and assert on shape + content of ``CommandResult``.
"""
from __future__ import annotations

import time
import warnings
import json
import sqlite3

import pytest

from sylion.aeis_v2.terminal.commands import CommandResult, parse_command
from sylion.governance.council_hybrid import (
    SENTINEL_ROLES,
    VALID_ROLES,
)


def _patch_terminal_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> sqlite3.Connection:
    import sylion.aeis_v2.terminal.commands as commands

    db_path = tmp_path / "w18_terminal.db"

    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(commands, "_audit_db_connect", connect)
    conn = connect()
    return conn


# --------------------------------------------------------------------------
# /status — real services + sessions + HG tickets + project counts
# --------------------------------------------------------------------------


def test_status_real_output() -> None:
    """/status must return real metrics, not the Phase 0 'skeleton' string."""
    result = parse_command("/status")

    assert isinstance(result, CommandResult)
    assert result.kind == "text"
    assert result.text, "status text must not be empty"
    # Phase 0 had the literal 'skeleton (W18 — Phase 0 active)' line.
    # Phase 1 must not regress to that.
    assert "skeleton (W18" not in result.text
    assert "Phase 0 active" not in result.text

    # Phase 1 contract: the real-output meta carries structured counts.
    meta = result.meta or {}
    assert "active_sessions" in meta
    assert "total_sessions" in meta
    assert "pending_hg_tickets" in meta
    assert "projects_total" in meta

    # All four counts must be non-negative ints (real types, not None/str).
    for k in ("active_sessions", "total_sessions",
              "pending_hg_tickets", "projects_total"):
        v = meta[k]
        assert isinstance(v, int), f"{k} must be int, got {type(v).__name__}"
        assert v >= 0, f"{k} must be >= 0, got {v}"

    # The text body must reference the four canonical surfaces.
    text_lower = result.text.lower()
    assert "services" in text_lower
    assert "sessions" in text_lower
    assert "hg_tickets" in text_lower or "tickets" in text_lower
    assert "projects" in text_lower


def test_status_treats_idle_audit_chains_as_non_alarm() -> None:
    result = parse_command("/status")
    assert result.kind == "text"
    assert "audit_chain" in result.text
    assert "0/4 clean" not in result.text
    assert "bad=0" in result.text or "audit_chain : unavailable" in result.text


def test_show_audit_tail_unwraps_hash_chain_content(tmp_path, monkeypatch) -> None:
    from sylion.aeis_v2 import audit_profile

    chain = tmp_path / "advisor_events.jsonl"
    chain.write_text(
        '{"content":{"kind":"advisor.test","payload":{"project_id":"project_x"},'
        '"event_id":"evt_1"},"content_hash":"hash_1","prev_hash":"GENESIS"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(audit_profile, "resolve_audit_chain_dir", lambda *_args, **_kw: tmp_path)

    result = parse_command("/show audit-tail 1")

    assert result.kind == "table"
    assert result.rows
    assert result.rows[0]["kind"] == "advisor.test"
    assert result.rows[0]["project_id"] == "project_x"
    assert result.rows[0]["ref"] == "hash_1"


# --------------------------------------------------------------------------
# /cost — real spend numbers, not a placeholder string
# --------------------------------------------------------------------------


def test_cost_real_output() -> None:
    """/cost must return today + month totals from cost_ledger, not 'G2:' stub."""
    result = parse_command("/cost")

    assert result.kind == "text", (
        f"expected text kind, got {result.kind!r} (text={result.text!r})"
    )
    # Phase 0 stub had this exact phrase.
    assert "Phase 0: uzyj GET /api/v1/monitoring/budget" not in result.text

    meta = result.meta or {}
    assert "today_total_usd" in meta
    assert "month_total_usd" in meta
    assert "today_call_count" in meta

    # Numeric types — not None, not string.
    assert isinstance(meta["today_total_usd"], (int, float))
    assert isinstance(meta["month_total_usd"], (int, float))
    assert meta["today_total_usd"] >= 0.0
    assert meta["month_total_usd"] >= 0.0

    # Body must mention dollar sign + 'dzisiaj' / 'miesiac'
    assert "$" in result.text
    text_lower = result.text.lower()
    assert "dzisiaj" in text_lower or "today" in text_lower
    assert "miesiac" in text_lower or "month" in text_lower


# --------------------------------------------------------------------------
# /agents — 9 canonical council roles
# --------------------------------------------------------------------------


def test_agents_real_output() -> None:
    """/agents must enumerate the 9 canonical council roles (not just providers)."""
    result = parse_command("/agents")

    assert result.kind == "table", f"expected table, got {result.kind}"
    assert result.headers is not None
    assert "role" in result.headers
    assert "default_weight" in result.headers
    assert "is_sentinel" in result.headers

    rows = result.rows or []
    # Exactly the 9 canonical roles, no more no less.
    assert len(rows) == len(VALID_ROLES) == 9
    role_names = {r["role"] for r in rows}
    assert role_names == set(VALID_ROLES)

    # Sentinel rows are flagged.
    sentinel_rows = [r for r in rows if r["is_sentinel"] == "yes"]
    assert {r["role"] for r in sentinel_rows} == set(SENTINEL_ROLES)
    assert len(sentinel_rows) == 2  # cost_sentinel + security_sentinel

    # Meta carries structured summary.
    meta = result.meta or {}
    assert set(meta.get("roles", [])) == set(VALID_ROLES)
    assert set(meta.get("sentinel_roles", [])) == set(SENTINEL_ROLES)


# --------------------------------------------------------------------------
# /explain — rationale of most-recent decision
# --------------------------------------------------------------------------


def test_explain_real_output() -> None:
    """/explain must return rationale of newest decision (or 'no decisions' fallback)."""
    # Seed one decision so the engine has something to surface.
    from sylion.core.decision_gate_engine import (
        DecisionRequest,
        get_decision_engine,
    )

    engine = get_decision_engine()
    req = DecisionRequest(
        description="AR-6.3 test decision — pin /explain rationale shape",
        source_plan="ar6_test_plan",
        change_type="config",
        blast_radius="low",
        reversible=True,
    )
    decision = engine.classify(req)
    assert decision is not None

    result = parse_command("/explain")

    assert result.kind == "text"
    # Phase 0 had this exact stub:
    assert "G3: WHY-trace ostatniej decyzji" not in result.text

    meta = result.meta or {}
    assert "decision_id" in meta
    assert meta.get("decision_count", 0) >= 1
    # Rationale text round-trips through the body.
    assert meta.get("rationale", ""), "rationale must not be empty"
    assert meta["rationale"] in result.text or "AR-6.3 test decision" in result.text


# --------------------------------------------------------------------------
# /findings — open security findings (table)
# --------------------------------------------------------------------------


def test_findings_real_output() -> None:
    """/findings must return a real findings table from SecurityAuditor."""
    # Seed at least one open finding so the table has shape.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from sylion.security.security_audit import get_security_auditor

    auditor = get_security_auditor()
    auditor.create_finding(
        title="AR-6.3 test finding",
        severity="high",
        description="Pin /findings real output shape.",
        module="ar6.test",
        recommendation="No-op; this is a fixture.",
    )

    result = parse_command("/findings")

    assert result.kind == "table"
    # Phase 0 had this exact stub:
    assert "G2: lista F-### z biezacej sesji" not in result.text

    headers = result.headers or []
    assert "finding_id" in headers
    assert "severity" in headers
    assert "title" in headers

    rows = result.rows or []
    # At least the seeded one is present.
    assert len(rows) >= 1
    # All rows have a non-empty finding_id.
    for r in rows:
        assert r.get("finding_id"), f"row missing finding_id: {r}"


# --------------------------------------------------------------------------
# /budget — project cost-caps + spend
# --------------------------------------------------------------------------


def test_budget_real_output() -> None:
    """/budget must return a project table with cost_cap + spent_usd."""
    # Seed at least one project so the table has shape. ProjectModeStore
    # uses upsert_project (no dedicated create_project) — pass a minimal
    # dict and the store fills defaults.
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    project_id = f"ar6-budget-{int(time.time()*1000)}"
    project = store.upsert_project({
        "project_id": project_id,
        "title": f"AR-6.3 budget test project {project_id}",
        "idea": "Pin /budget real output shape.",
        "owner_id": "ar6_tester",
        "phase": "canon",
        "status": "definition_in_progress",
        "cost_cap_usd": 10.0,
    })
    assert project["project_id"] == project_id

    result = parse_command("/budget")

    assert result.kind == "table"
    # Phase 0 had this exact stub:
    assert "G2: aktualny budzet vs zuzycie" not in result.text

    headers = result.headers or []
    assert "project_id" in headers
    assert "cost_cap" in headers
    assert "spent_usd" in headers
    assert "phase" in headers

    rows = result.rows or []
    assert len(rows) >= 1, "at least the seeded project must surface"

    meta = result.meta or {}
    assert meta.get("project_count", 0) == len(rows)


# --------------------------------------------------------------------------
# /report current-run — newest project
# --------------------------------------------------------------------------


def test_report_current_run_real_output() -> None:
    """/report current-run must return the most-recently-updated project."""
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    # Seed a fresh project — guaranteed-newest by injecting future updated_at.
    project_id = f"ar6-report-{int(time.time()*1000)}"
    future_ts = time.time() + 3600.0  # +1h ensures we beat any existing rows
    fresh = store.upsert_project({
        "project_id": project_id,
        "title": f"AR-6.3 report freshest {project_id}",
        "idea": "Pin /report current-run real output shape.",
        "owner_id": "ar6_tester",
        "phase": "canon",
        "status": "definition_in_progress",
        "created_at": future_ts,
        "updated_at": future_ts,
    })
    assert fresh["project_id"] == project_id

    result = parse_command("/report current-run")

    assert result.kind == "text"
    # Phase 0 had this exact stub:
    assert "G3: dzienny / tygodniowy raport sesji" not in result.text

    meta = result.meta or {}
    assert meta.get("project_id") == fresh["project_id"]
    # Body must surface the project_id text.
    assert fresh["project_id"] in result.text
    # Body must mention phase + status + module count.
    text_lower = result.text.lower()
    assert "phase" in text_lower
    assert "status" in text_lower
    assert "modules" in text_lower


def test_host_drilldown_returns_real_runtime_rows(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """/host must drill into worker/masterplan runtime data, not return G2/G3 stub."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE project_worker_pool (
            worker_entry_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            worker_type TEXT NOT NULL,
            endpoint TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            cost_per_1k REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            config_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE project_masterplans (
            project_id TEXT PRIMARY KEY,
            status TEXT,
            deployment_topology_json TEXT,
            frozen_at REAL,
            updated_at REAL
        );
        """
    )
    conn.execute(
        "INSERT INTO project_worker_pool "
        "(worker_entry_id, project_id, name, worker_type, endpoint, model_id, role, active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("w1", "project_host", "local-docker-1", "docker", "localhost", "bielik", "qa", 1),
    )
    conn.execute(
        "INSERT INTO project_masterplans VALUES (?, ?, ?, ?, ?)",
        (
            "project_host",
            "frozen",
            json.dumps({"deployment_mode": "local_docker", "provisioning_mode": "local-only", "vps_workers": 0, "local_docker_workers": 3}),
            time.time(),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()

    result = parse_command("/host local")

    assert result.kind == "table"
    assert "G4" not in result.text
    assert result.meta and result.meta["count"] >= 2
    assert {row["source"] for row in result.rows or []} >= {"worker", "masterplan"}


def test_report_skills_filters_by_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """/report skills <project_id> must show skill bindings for that project, not a global table."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE project_skill_reuse_log (
            project_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            reused_skill_id TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            adaptation_notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO project_skill_reuse_log VALUES (?, ?, ?, ?, ?, ?)",
        ("project_target", "project_target::module::0", "aeis.offline-checklist-builder", 0.91, "target skill", time.time()),
    )
    conn.execute(
        "INSERT INTO project_skill_reuse_log VALUES (?, ?, ?, ?, ?, ?)",
        ("project_other", "project_other::module::0", "aeis.auth-flow-builder", 0.88, "other skill", time.time() + 1),
    )
    conn.commit()
    conn.close()

    result = parse_command("/report skills project_target")

    assert result.kind == "table"
    assert result.meta and result.meta["project_id"] == "project_target"
    assert result.meta["count"] == 1
    assert result.rows == [
        {
            "project_id": "project_target",
            "module": "project_target::module::0",
            "skill": "aeis.offline-checklist-builder",
            "score": "0.910",
            "notes": "target skill",
        }
    ]


def test_model_drilldown_returns_real_council_and_cost_rows(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """/model must surface model assignments/usage, not return G2/G3 placeholder."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE project_worker_pool (
            worker_entry_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            worker_type TEXT NOT NULL,
            endpoint TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            cost_per_1k REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            config_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE project_council_members (
            council_member_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            member_role TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            voting_weight REAL NOT NULL DEFAULT 1.0,
            config_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE project_cost_ledger (
            cost_entry_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            tokens_in INTEGER NOT NULL DEFAULT 0,
            tokens_out INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0,
            running_total REAL NOT NULL DEFAULT 0
        );
        """
    )
    model = "PRIHLOP/PLLuM:12B-chat-Q8_0"
    conn.execute(
        "INSERT INTO project_council_members "
        "(council_member_id, project_id, member_role, provider, model_id, voting_weight, active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("c1", "project_model", "planner", "ollama", model, 1.0, 1),
    )
    conn.execute(
        "INSERT INTO project_cost_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("cost1", "project_model", time.time(), "ollama", model, 1200, 300, 0.0, 0.0),
    )
    conn.commit()
    conn.close()

    result = parse_command(f"/model {model}")

    assert result.kind == "table"
    assert "G3" not in result.text
    assert result.meta and result.meta["count"] >= 2
    sources = {row["source"] for row in result.rows or []}
    assert {"council", "cost_ledger"} <= sources


def test_v9_report_council_sync_and_pending_models(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """/report council-sync and /show pending-models must expose wait-barrier state."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE hybrid_council_sessions (
            session_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            models TEXT NOT NULL DEFAULT '[]',
            context TEXT NOT NULL DEFAULT '',
            moderator_model TEXT NOT NULL DEFAULT '',
            phase TEXT NOT NULL DEFAULT 'parallel_analysis',
            status TEXT NOT NULL DEFAULT 'open',
            consolidated_text TEXT NOT NULL DEFAULT '',
            consensus_level REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            closed_at REAL
        );
        CREATE TABLE council_participants (
            participant_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            role TEXT NOT NULL,
            rank TEXT NOT NULL DEFAULT 'primary',
            weight REAL NOT NULL DEFAULT 1,
            joined_at REAL NOT NULL
        );
        CREATE TABLE model_analyses (
            analysis_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            analysis_text TEXT NOT NULL DEFAULT '',
            verdict TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            rationale TEXT NOT NULL DEFAULT '',
            rating REAL,
            created_at REAL NOT NULL
        );
        CREATE TABLE council_critic_signatures (
            signature_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            signed_decision TEXT NOT NULL,
            signature_hash TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            signed_at REAL NOT NULL
        );
        CREATE TABLE council_sentinel_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            sentinel_role TEXT NOT NULL,
            model_id TEXT NOT NULL,
            verdict TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            details TEXT NOT NULL DEFAULT '',
            evaluated_at REAL NOT NULL
        );
        """
    )
    now = time.time()
    conn.execute(
        "INSERT INTO hybrid_council_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sess_v9", "project_v9 :: build", '["m1","m2"]', "project_v9", "chair", "verdicts", "open", "", 0, now, None),
    )
    conn.execute(
        "INSERT INTO council_participants VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("p1", "sess_v9", "m1", "critic", "primary", 1.0, now),
    )
    conn.execute(
        "INSERT INTO council_participants VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("p2", "sess_v9", "m2", "security_sentinel", "support", 0.5, now),
    )
    conn.execute(
        "INSERT INTO model_analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("a1", "sess_v9", "m1", "ok", "approve", 0.9, "critic ok", None, now),
    )
    conn.commit()
    conn.close()

    sync = parse_command("/report council-sync sess_v9")
    assert sync.kind == "table"
    assert sync.meta and sync.meta["barrier_status"] == "blocked"
    assert sync.meta["missing_blocking_models"] == ["m2"]
    assert "m2" in sync.rows[0]["missing"]

    pending = parse_command("/show pending-models sess_v9")
    assert pending.kind == "table"
    assert pending.rows == [
        {
            "session_id": "sess_v9",
            "model": "m2",
            "role": "security_sentinel",
            "status": "pending",
            "reason": "mandatory participant has no analysis row",
        }
    ]

    barrier_alias = parse_command("/report model-barriers sess_v9")
    assert barrier_alias.kind == "table"
    assert barrier_alias.rows == pending.rows


def test_v9_council_sync_uses_latest_sentinel_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A newer pass clears an older sentinel fail; a newer fail blocks."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE hybrid_council_sessions (
            session_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            models TEXT NOT NULL DEFAULT '[]',
            context TEXT NOT NULL DEFAULT '',
            moderator_model TEXT NOT NULL DEFAULT '',
            phase TEXT NOT NULL DEFAULT 'parallel_analysis',
            status TEXT NOT NULL DEFAULT 'open',
            consolidated_text TEXT NOT NULL DEFAULT '',
            consensus_level REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            closed_at REAL
        );
        CREATE TABLE council_participants (
            participant_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            role TEXT NOT NULL,
            rank TEXT NOT NULL DEFAULT 'primary',
            weight REAL NOT NULL DEFAULT 1,
            joined_at REAL NOT NULL
        );
        CREATE TABLE model_analyses (
            analysis_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            analysis_text TEXT NOT NULL DEFAULT '',
            verdict TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            rationale TEXT NOT NULL DEFAULT '',
            rating REAL,
            created_at REAL NOT NULL
        );
        CREATE TABLE council_critic_signatures (
            signature_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            signed_decision TEXT NOT NULL,
            signature_hash TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            signed_at REAL NOT NULL
        );
        CREATE TABLE council_sentinel_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            sentinel_role TEXT NOT NULL,
            model_id TEXT NOT NULL,
            verdict TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            details TEXT NOT NULL DEFAULT '',
            evaluated_at REAL NOT NULL
        );
        """
    )
    now = time.time()
    sessions = [
        ("sess_latest_pass", "consolidated", now),
        ("sess_latest_fail", "verdicts", now + 10),
    ]
    for session_id, phase, created_at in sessions:
        conn.execute(
            "INSERT INTO hybrid_council_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                f"project_v9 :: {session_id}",
                '["critic-model","cost-model"]',
                "project_v9",
                "chair",
                phase,
                "open",
                "",
                0,
                created_at,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO council_participants VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{session_id}-p1", session_id, "critic-model", "critic", "primary", 1.0, created_at),
        )
        conn.execute(
            "INSERT INTO council_participants VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{session_id}-p2", session_id, "cost-model", "cost_sentinel", "support", 0.5, created_at),
        )
        conn.execute(
            "INSERT INTO model_analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{session_id}-a1", session_id, "critic-model", "ok", "approve", 0.9, "critic ok", None, created_at),
        )
        conn.execute(
            "INSERT INTO model_analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{session_id}-a2", session_id, "cost-model", "ok", "approve", 0.9, "cost ok", None, created_at),
        )
        conn.execute(
            "INSERT INTO council_critic_signatures VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{session_id}-sig", session_id, "critic-model", "approve", "hash", "signed", created_at),
        )

    conn.execute(
        "INSERT INTO council_sentinel_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("e-pass-1", "sess_latest_pass", "cost_sentinel", "cost-model", "fail", 0.2, "old fail", now + 1),
    )
    conn.execute(
        "INSERT INTO council_sentinel_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("e-pass-2", "sess_latest_pass", "cost_sentinel", "cost-model", "pass", 0.9, "new pass", now + 2),
    )
    conn.execute(
        "INSERT INTO council_sentinel_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("e-fail-1", "sess_latest_fail", "cost_sentinel", "cost-model", "pass", 0.9, "old pass", now + 11),
    )
    conn.execute(
        "INSERT INTO council_sentinel_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("e-fail-2", "sess_latest_fail", "cost_sentinel", "cost-model", "fail", 0.2, "new fail", now + 12),
    )
    conn.commit()
    conn.close()

    latest_pass = parse_command("/report council-sync sess_latest_pass")
    assert latest_pass.kind == "table"
    assert latest_pass.rows and latest_pass.rows[0]["sentinel_blocks"] == "-"
    assert latest_pass.rows[0]["barrier_status"] == "satisfied"
    assert latest_pass.rows[0]["next_stage_enabled"] == "yes"

    latest_fail = parse_command("/report council-sync sess_latest_fail")
    assert latest_fail.kind == "table"
    assert latest_fail.rows and latest_fail.rows[0]["sentinel_blocks"] == "cost_sentinel"
    assert latest_fail.rows[0]["barrier_status"] == "guard_blocked"
    assert latest_fail.rows[0]["next_stage_enabled"] == "no"


def test_v9_reports_model_slots_guards_and_loop_guard(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """/report V9 variants must be implemented and backed by runtime tables."""
    conn = _patch_terminal_db(monkeypatch, tmp_path)
    conn.executescript(
        """
        CREATE TABLE project_council_members (
            council_member_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            member_role TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            voting_weight REAL NOT NULL DEFAULT 1.0,
            config_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE governance_tickets (
            ticket_id TEXT PRIMARY KEY,
            origin TEXT,
            project_id TEXT,
            decision_class TEXT,
            gate_type TEXT,
            priority TEXT,
            title TEXT,
            summary TEXT,
            payload_json TEXT,
            requested_by TEXT,
            audit_chain_ref TEXT,
            created_at REAL,
            sla_deadline REAL,
            state TEXT,
            resolved_by TEXT,
            resolved_at REAL,
            resolution_reason TEXT
        );
        CREATE TABLE w14_loop_reports (
            obj_id TEXT PRIMARY KEY,
            payload TEXT,
            created_at REAL,
            updated_at REAL,
            deleted_at REAL
        );
        """
    )
    now = time.time()
    conn.execute(
        "INSERT INTO project_council_members VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "cm1",
            "project_v9",
            "critic",
            "openai",
            "gpt-4o-mini",
            1.0,
            json.dumps({"rank": "primary", "required_signature": True, "timeout_s": 45}),
            1,
        ),
    )
    conn.execute(
        "INSERT INTO governance_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "gt1",
            "council",
            "project_v9",
            "D4",
            "security",
            "P1",
            "Guard test",
            "Security guard blocks missing RBAC",
            json.dumps({"target": "build", "policy_ref": "policy/security/rbac-required"}),
            "guard",
            "hash1",
            now,
            now + 3600,
            "pending",
            "",
            None,
            "",
        ),
    )
    conn.execute(
        "INSERT INTO w14_loop_reports VALUES (?, ?, ?, ?, ?)",
        (
            "loop1",
            json.dumps({"project_id": "project_v9", "process_type": "fixer", "stage_id": "repair", "max_attempts": 3, "attempts_seen": 3, "trigger": "same root cause repeated", "loop_status": "stopped_for_humangate", "human_gate_ref": "hg1"}),
            now,
            now,
            None,
        ),
    )
    conn.execute(
        "INSERT INTO w14_loop_reports VALUES (?, ?, ?, ?, ?)",
        (
            "loop2",
            json.dumps({
                "loop_type": "no_progress",
                "attempts_n": 2,
                "required_decision": {
                    "project_id": "project_v9_nested",
                    "human_gate_ref": "hg_nested",
                    "status": "blocked_human_gate",
                    "max_attempts": 2,
                    "reason": "max_auto_fix_attempts_per_finding",
                },
            }),
            now,
            now,
            None,
        ),
    )
    conn.commit()
    conn.close()

    slots = parse_command("/report model-slots project_v9")
    assert slots.kind == "table"
    assert slots.rows and slots.rows[0]["mandatory"] == "yes"
    assert slots.rows[0]["timeout_s"] == "45"

    guards = parse_command("/report guard-decisions project_v9")
    assert guards.kind == "table"
    assert guards.rows and guards.rows[0]["decision"] == "block"
    assert guards.rows[0]["policy_ref"] == "policy/security/rbac-required"

    loop = parse_command("/report loop-guard project_v9")
    assert loop.kind == "table"
    assert loop.rows and loop.rows[0]["status"] == "stopped_for_humangate"

    nested_loop = parse_command("/report loop-guard project_v9_nested")
    assert nested_loop.kind == "table"
    assert nested_loop.rows and nested_loop.rows[0]["project_id"] == "project_v9_nested"
    assert nested_loop.rows[0]["attempts_seen"] == 2
    assert nested_loop.rows[0]["status"] == "blocked_human_gate"
    assert nested_loop.rows[0]["human_gate_ref"] == "hg_nested"
