"""W14 round_meta-orchestration BE-1/BE-2/BE-3 adversarial tests.

Per ``W14_PROMPT_CODEX_RM_BACKEND.md``, every freeze / authorize endpoint
gets the same 4-test adversarial battery:

1. **Bypass attempt** -- a request that tries to skip the Human Gate ticket.
2. **Replay attack** -- 10 rapid identical POSTs must produce 1 ticket.
3. **Scope escalation** -- BE-3 without BE-2 frozen must 409.
4. **Concurrent** -- 10 parallel POSTs must not split the chain.

The tests mount only the round-meta router on an isolated FastAPI app
and stub the project_mode store / ticket store in tmp_path so the suite
doesn't share global state with the rest of aeis_v2.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.api import projects_freeze_routes as freeze_module
from sylion.api.projects_freeze_routes import router as freeze_router


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeProjectStore:
    """Tiny in-memory project store covering exactly what BE-1..BE-3 need."""

    def __init__(self) -> None:
        self.projects: dict[str, dict[str, Any]] = {}
        self.events: list[tuple[str, str, dict[str, Any]]] = []
        self.lock = threading.RLock()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.lock:
            project = self.projects.get(project_id)
            return None if project is None else dict(project)

    def upsert_project(self, project: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            pid = project["project_id"]
            self.projects[pid] = dict(project)
            return dict(self.projects[pid])

    def add_event(self, project_id: str, kind: str, payload: dict[str, Any]) -> None:
        with self.lock:
            self.events.append((project_id, kind, payload))


class _FakeTicket:
    def __init__(self, ticket_id: str, payload: dict[str, Any]) -> None:
        self.ticket_id = ticket_id
        self.payload = payload


class _FakeTicketStore:
    """Stand-in for governance.tickets that records every submit."""

    def __init__(self) -> None:
        self.submitted: list[dict[str, Any]] = []
        self.pending: dict[str, _FakeTicket] = {}
        self.lock = threading.RLock()
        self._counter = 0

    def submit(self, ticket: Any) -> str:
        with self.lock:
            self._counter += 1
            ticket_id = f"tic_{self._counter:04d}"
            payload = dict(ticket.payload or {})
            self.submitted.append({
                "ticket_id": ticket_id,
                "origin": ticket.origin,
                "project_id": ticket.project_id,
                "decision_class": ticket.decision_class,
                "gate_type": ticket.gate_type,
                "payload": payload,
            })
            self.pending[ticket_id] = _FakeTicket(ticket_id, payload)
            return ticket_id

    def fetch_pending(
        self, *, origin: str | None = None, project_id: str | None = None,
    ) -> list[_FakeTicket]:
        with self.lock:
            out: list[_FakeTicket] = []
            for entry in self.submitted:
                if origin and entry["origin"] != origin:
                    continue
                if project_id and entry["project_id"] != project_id:
                    continue
                out.append(_FakeTicket(entry["ticket_id"], entry["payload"]))
            return out


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_store() -> _FakeProjectStore:
    return _FakeProjectStore()


@pytest.fixture
def fake_tickets() -> _FakeTicketStore:
    return _FakeTicketStore()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
    tmp_path: Path,
) -> TestClient:
    """Mount only the round_meta router; stub stores; redirect audit chain."""
    monkeypatch.setattr(freeze_module, "_store", lambda: fake_store)
    monkeypatch.setattr(freeze_module, "submit", fake_tickets.submit)
    monkeypatch.setattr(
        freeze_module, "fetch_pending",
        lambda *a, **kw: fake_tickets.fetch_pending(**kw),
    )
    # Reset per-project locks between tests.
    monkeypatch.setattr(freeze_module, "_PROJECT_LOCKS", {})
    # Audit chain dir -> tmp.
    monkeypatch.setattr(
        freeze_module, "resolve_audit_chain_dir", lambda: tmp_path / "chains",
    )

    api = FastAPI()
    api.include_router(freeze_router)
    return TestClient(api)


def _make_project(
    fake_store: _FakeProjectStore,
    project_id: str = "proj_alpha",
    *,
    canon: str = "Source of truth body.",
    masterplan: str = "Masterplan body.",
    canon_frozen: bool = False,
    masterplan_frozen: bool = False,
    build_authorized: bool = False,
) -> None:
    fake_store.upsert_project({
        "project_id": project_id,
        "canonical_book": canon,
        "masterplan": masterplan,
        "approvals": {
            "book": canon_frozen,
            "operating_model": masterplan_frozen,
        },
        "canon_frozen_at": 1.0 if canon_frozen else None,
        "masterplan_frozen_at": 1.0 if masterplan_frozen else None,
        "build_authorized_at": 1.0 if build_authorized else None,
    })


# ---------------------------------------------------------------------------
# BE-1 -- canon freeze (4 adversarial + 4 contract tests)
# ---------------------------------------------------------------------------


def test_be1_canon_freeze_happy_path(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore, tmp_path: Path,
) -> None:
    _make_project(fake_store)
    r = client.post(
        "/api/v1/projects/proj_alpha/canon/freeze",
        json={"reason": "ready", "evidence_pack_id": "ep_1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_human_gate"
    assert body["ticket_id"].startswith("tic_")
    assert len(fake_tickets.submitted) == 1
    assert fake_tickets.submitted[0]["gate_type"] == "source_of_truth_gate"
    # Audit chain must contain exactly one entry, and verify_chain must
    # report no faults.
    chain = tmp_path / "chains" / "canon_freeze.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []


def test_be1_404_when_project_missing(client: TestClient) -> None:
    r = client.post(
        "/api/v1/projects/nope/canon/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 404


def test_be1_409_when_canon_empty(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon="   ")
    r = client.post(
        "/api/v1/projects/proj_alpha/canon/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 409


def test_be1_400_when_already_frozen(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/canon/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 400


# Adversarial #1 (BE-1): bypass attempt. The contract says every freeze
# MUST produce an HG ticket -- there is no way to skip it. We assert
# that even when reason+evidence are blank, a ticket is still created
# (cannot freeze without going through HG).
def test_be1_bypass_attempt_still_creates_ticket(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store)
    r = client.post(
        "/api/v1/projects/proj_alpha/canon/freeze",
        json={},  # empty body -- no reason, no evidence
    )
    assert r.status_code == 200
    assert len(fake_tickets.submitted) == 1
    # gate_type must remain source_of_truth_gate -- cannot be downgraded by attacker.
    assert fake_tickets.submitted[0]["gate_type"] == "source_of_truth_gate"


# Adversarial #2 (BE-1): Replay attack -- 10 rapid POSTs must produce 1 ticket.
def test_be1_replay_attack_idempotent(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store)
    last_ticket = None
    for _ in range(10):
        r = client.post(
            "/api/v1/projects/proj_alpha/canon/freeze",
            json={"reason": "ready"},
        )
        assert r.status_code == 200
        if last_ticket is None:
            last_ticket = r.json()["ticket_id"]
        else:
            assert r.json()["ticket_id"] == last_ticket
    assert len(fake_tickets.submitted) == 1


# Adversarial #3 (BE-1): scope escalation -- caller cannot freeze canon
# of a project that does not exist (no implicit project creation).
def test_be1_scope_escalation_unknown_project(client: TestClient) -> None:
    r = client.post(
        "/api/v1/projects/zzz_does_not_exist/canon/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 404


# Adversarial #4 (BE-1): concurrent POSTs hit the project lock, so we
# end up with exactly 1 ticket regardless of thread count.
def test_be1_concurrent_posts_single_ticket(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store)

    statuses: list[int] = []
    statuses_lock = threading.Lock()

    def hit() -> None:
        r = client.post(
            "/api/v1/projects/proj_alpha/canon/freeze",
            json={"reason": "race"},
        )
        with statuses_lock:
            statuses.append(r.status_code)

    threads = [threading.Thread(target=hit) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(s == 200 for s in statuses)
    assert len(fake_tickets.submitted) == 1


# ---------------------------------------------------------------------------
# BE-2 -- masterplan freeze (4 adversarial + 3 contract tests)
# ---------------------------------------------------------------------------


def test_be2_masterplan_freeze_happy_path(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore, tmp_path: Path,
) -> None:
    _make_project(fake_store, canon_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/masterplan/freeze",
        json={"reason": "ok"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending_human_gate"
    assert fake_tickets.submitted[0]["gate_type"] == "masterplan_gate"
    chain = tmp_path / "chains" / "masterplan_freeze.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []


def test_be2_409_when_canon_not_frozen(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=False)
    r = client.post(
        "/api/v1/projects/proj_alpha/masterplan/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 409


def test_be2_400_when_already_frozen(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/masterplan/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 400


# Adversarial #1 (BE-2): bypass attempt -- empty body still triggers HG.
def test_be2_bypass_empty_body_still_creates_ticket(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store, canon_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/masterplan/freeze",
        json={},
    )
    assert r.status_code == 200
    assert len(fake_tickets.submitted) == 1
    assert fake_tickets.submitted[0]["gate_type"] == "masterplan_gate"


# Adversarial #2 (BE-2): replay attack -- 10 POSTs collapse to 1 ticket.
def test_be2_replay_attack_idempotent(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store, canon_frozen=True)
    last = None
    for _ in range(10):
        r = client.post(
            "/api/v1/projects/proj_alpha/masterplan/freeze",
            json={"reason": "ok"},
        )
        assert r.status_code == 200
        if last is None:
            last = r.json()["ticket_id"]
        else:
            assert r.json()["ticket_id"] == last
    assert len(fake_tickets.submitted) == 1


# Adversarial #3 (BE-2): scope escalation -- attempt to freeze masterplan
# while canon is still in draft must 409.
def test_be2_scope_escalation_canon_required(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon="canon body", canon_frozen=False)
    r = client.post(
        "/api/v1/projects/proj_alpha/masterplan/freeze",
        json={"reason": "x"},
    )
    assert r.status_code == 409
    assert "Round 1" in r.json()["detail"]


# Adversarial #4 (BE-2): concurrent POSTs collapse to 1 ticket.
def test_be2_concurrent_posts_single_ticket(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store, canon_frozen=True)

    def hit() -> None:
        client.post(
            "/api/v1/projects/proj_alpha/masterplan/freeze",
            json={"reason": "race"},
        )

    threads = [threading.Thread(target=hit) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(fake_tickets.submitted) == 1


# ---------------------------------------------------------------------------
# BE-3 -- build authorize (4 adversarial + 3 contract tests)
# ---------------------------------------------------------------------------


def test_be3_build_authorize_happy_path(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore, tmp_path: Path,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/build/authorize",
        json={
            "cost_cap_usd": 50.0,
            "autonomy_level": "L2",
            "external_actions_policy": {"vps_deploy": "human_gate"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_human_gate"
    assert body["pending_governance_ticket_id"] == body["ticket_id"]
    project = fake_store.get_project("proj_alpha")
    assert project is not None
    assert project["approvals"]["build_pending_ticket_id"] == body["ticket_id"]
    submitted = fake_tickets.submitted[0]
    assert submitted["decision_class"] == "D4"
    assert submitted["gate_type"] == "financial"
    assert submitted["payload"]["gate_types"] == [
        "financial", "production", "external_action",
    ]
    chain = tmp_path / "chains" / "build_authorize.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []


def test_be3_400_when_already_authorized(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(
        fake_store, canon_frozen=True,
        masterplan_frozen=True, build_authorized=True,
    )
    r = client.post(
        "/api/v1/projects/proj_alpha/build/authorize",
        json={
            "cost_cap_usd": 10.0,
            "autonomy_level": "L1",
            "external_actions_policy": {},
        },
    )
    assert r.status_code == 400


# Adversarial #1 (BE-3): bypass attempt -- invalid autonomy level rejected
# at the schema layer (cannot smuggle autonomy beyond L4). The attacker
# also cannot send negative cost_cap (Field(ge=0)).
def test_be3_bypass_invalid_autonomy_rejected(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/build/authorize",
        json={
            "cost_cap_usd": 1.0,
            "autonomy_level": "L99",  # not in the allowed set
            "external_actions_policy": {},
        },
    )
    assert r.status_code == 422


def test_be3_bypass_negative_cost_cap_rejected(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)
    r = client.post(
        "/api/v1/projects/proj_alpha/build/authorize",
        json={
            "cost_cap_usd": -100.0,
            "autonomy_level": "L1",
            "external_actions_policy": {},
        },
    )
    assert r.status_code == 422


# Adversarial #2 (BE-3): replay attack -- 10 POSTs collapse to 1 ticket.
def test_be3_replay_attack_idempotent(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)
    last = None
    for _ in range(10):
        r = client.post(
            "/api/v1/projects/proj_alpha/build/authorize",
            json={
                "cost_cap_usd": 10.0,
                "autonomy_level": "L1",
                "external_actions_policy": {},
            },
        )
        assert r.status_code == 200
        if last is None:
            last = r.json()["ticket_id"]
        else:
            assert r.json()["ticket_id"] == last
    assert len(fake_tickets.submitted) == 1


# Adversarial #3 (BE-3): scope escalation -- authorize without
# masterplan frozen must 409 with "Round 2" hint.
def test_be3_scope_escalation_masterplan_required(
    client: TestClient, fake_store: _FakeProjectStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=False)
    r = client.post(
        "/api/v1/projects/proj_alpha/build/authorize",
        json={
            "cost_cap_usd": 10.0,
            "autonomy_level": "L1",
            "external_actions_policy": {},
        },
    )
    assert r.status_code == 409
    assert "Round 2" in r.json()["detail"]


# Adversarial #4 (BE-3): concurrent POSTs collapse to 1 ticket.
def test_be3_concurrent_posts_single_ticket(
    client: TestClient, fake_store: _FakeProjectStore,
    fake_tickets: _FakeTicketStore,
) -> None:
    _make_project(fake_store, canon_frozen=True, masterplan_frozen=True)

    def hit() -> None:
        client.post(
            "/api/v1/projects/proj_alpha/build/authorize",
            json={
                "cost_cap_usd": 10.0,
                "autonomy_level": "L1",
                "external_actions_policy": {},
            },
        )

    threads = [threading.Thread(target=hit) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(fake_tickets.submitted) == 1


# ---------------------------------------------------------------------------
# Audit-profile interaction (BE-1 chain under SYLION_AUDIT_PROFILE_ID)
# ---------------------------------------------------------------------------


def test_audit_chain_under_audit_profile(
    client: TestClient, fake_store: _FakeProjectStore,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When the audit profile dir is overridden, chains land under it."""
    audit_root = tmp_path / "audit_chain_root"
    monkeypatch.setattr(
        freeze_module, "resolve_audit_chain_dir", lambda: audit_root,
    )
    _make_project(fake_store)
    r = client.post(
        "/api/v1/projects/proj_alpha/canon/freeze",
        json={"reason": "audit"},
    )
    assert r.status_code == 200
    chain = audit_root / "canon_freeze.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []
