"""AgentTheaterAggregator tests — read-only contract."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sylion.aeis.testing.agent_theater import AgentTheaterAggregator
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Finding, RepairAttempt


class FakeModelRegistry:
    def get_active_members(self, project_id=None):
        return [
            SimpleNamespace(
                member_id="gpt-5-codex",
                project_id=project_id,
                member_role="repair_controller",
                provider="openai",
                model_id="gpt-5-codex",
                voting_weight=1.0,
                active=True,
            ),
            SimpleNamespace(
                member_id="qwen3.5:latest",
                project_id=project_id,
                member_role="critic",
                provider="ollama",
                model_id="qwen3.5:latest",
                voting_weight=0.8,
                active=True,
            ),
        ]

    def list_models(self):
        return [
            {
                "model_id": "qwen3.5:latest",
                "provider": "ollama",
                "display_name": "qwen3.5",
                "model_family": "local",
                "latest_health": {"status": "registered", "tasks_today": 2},
            },
            {
                "model_id": "gpt-5.2",
                "provider": "openai",
                "display_name": "GPT-5.2",
                "model_family": "remote",
                "latest_health": None,
            },
        ]


class EmptyModelRegistry:
    def get_active_members(self, project_id=None):
        return []

    def list_models(self):
        return []


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def agg(store):
    return AgentTheaterAggregator(ontology=store, model_registry=FakeModelRegistry())


# -------- Topology --------

def test_topology_uses_model_registry_actors(agg):
    topo = agg.get_topology()
    model_actors = [a for a in topo["actors"] if a["kind"] == "model"]
    assert len(model_actors) == 2
    names = {a["name"] for a in model_actors}
    assert "gpt-5-codex" in names
    assert "qwen3.5:latest" in names
    assert topo["source"]["models"] == "model_registry"


def test_topology_does_not_invent_model_actors(store):
    agg = AgentTheaterAggregator(ontology=store, model_registry=EmptyModelRegistry())
    topo = agg.get_topology()
    assert [a for a in topo["actors"] if a["kind"] == "model"] == []


def test_topology_includes_open_findings_as_tasks(store, agg):
    f = Finding(severity="P2", d_level="D2", title="open task",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    topo = agg.get_topology()
    task_actors = [a for a in topo["actors"] if a["kind"] == "task"]
    assert len(task_actors) == 1
    assert task_actors[0]["severity"] == "P2"


def test_topology_excludes_closed_findings(store, agg):
    f = Finding(severity="P3", d_level="D2", title="done",
                description="d", discovered_by="t", r_status="CLOSED")
    store.create(f)
    topo = agg.get_topology()
    task_actors = [a for a in topo["actors"] if a["kind"] == "task"]
    assert len(task_actors) == 0


def test_topology_has_edges_from_codex_to_findings(store, agg):
    f = Finding(severity="P2", d_level="D2", title="x",
                description="d", discovered_by="t", r_status="REPAIRING")
    store.create(f)
    topo = agg.get_topology()
    codex_edges = [e for e in topo["edges"] if e["source"] == "model_gpt-5-codex"]
    assert len(codex_edges) == 1
    assert codex_edges[0]["kind"] == "works_on"


# -------- Council view --------

def test_council_view_returns_structure(agg):
    ticket = SimpleNamespace(
        ticket_id="cs_test",
        origin="council",
        project_id="proj_test",
        decision_class="D4",
        gate_type="blocking",
        priority="P1",
        title="Council decision",
        summary="Approve release",
        requested_by="test",
        resolved_by="critic",
        resolved_at=123.0,
        state="approved",
        payload={
            "participants": [
                {"role": "critic", "vote": "approve", "signed": True, "weight": 1.0},
            ],
            "sentinel_status": "pass",
        },
    )
    agg = AgentTheaterAggregator(
        ontology=OntologyStore(),
        model_registry=FakeModelRegistry(),
        ticket_fetcher=lambda session_id: ticket if session_id == "cs_test" else None,
    )
    view = agg.get_council_session_view("cs_test")
    assert view["source"] == "governance_ticket"
    assert view["session_id"] == "cs_test"
    assert view["critic_status"] == "signed"
    assert view["consensus"]["state"] == "approved"


def test_council_view_unknown_session_is_not_stub(agg):
    agg = AgentTheaterAggregator(
        ontology=OntologyStore(),
        model_registry=FakeModelRegistry(),
        ticket_fetcher=lambda session_id: None,
    )
    view = agg.get_council_session_view("missing")
    assert view["error"] == "council_session_not_found"


# -------- Repair theater --------

def test_repair_theater_unknown_finding(agg):
    result = agg.get_repair_theater("find_unknown")
    assert result.get("error") == "finding_not_found"


def test_repair_theater_returns_loop_governor_metrics(store, agg):
    f = Finding(severity="P1", d_level="D3", title="x",
                description="d", discovered_by="t", r_status="REPAIRING")
    store.create(f)
    a = RepairAttempt(
        finding_id=f.finding_id, n=1, r_phase="REPAIRING",
        result="success", files_touched_count=2, diff_lines=15,
        time_in_phase_s=10.0,
    )
    store.create(a)
    rt = agg.get_repair_theater(f.finding_id)
    assert rt["attempts_used"] == 1
    assert rt["attempts_max"] == 2  # Loop Governor default
    assert rt["files_touched"] == 2
    assert rt["diff_lines"] == 15
    assert rt["loop_status"] == "CLEAR"


# -------- Guardian status --------

def test_guardian_status_returns_13_guardians(agg):
    statuses = agg.get_guardian_status()
    assert len(statuses) == 13
    for s in statuses:
        assert "name" in s
        assert "health" in s


# -------- Local models --------

def test_local_models_status_uses_registry(agg):
    locals_ = agg.get_local_models_status()
    assert len(locals_) == 1
    names = {m["name"] for m in locals_}
    assert "qwen3.5" in names
    assert locals_[0]["source"] == "model_registry"
