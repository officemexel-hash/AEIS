from types import SimpleNamespace

from sylion.governance.audit_chain import reset_audit_chain
from sylion.governance.ticket import GovernanceTicket, reset_ticket_store
from sylion.governance.tickets import resolve, submit
from sylion.skills.runtime import SkillsRuntime


def setup_function():
    reset_ticket_store()
    reset_audit_chain()


def teardown_function():
    reset_ticket_store()
    reset_audit_chain()


class FakeGovernanceHooks:
    class GovernanceTicket:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.ticket_id = kwargs.get("ticket_id", "")

    def __init__(self):
        self.submitted: list[object] = []
        self.states: dict[str, str] = {}

    def submit(self, ticket):
        ticket_id = "ticket-hg-1"
        ticket.ticket_id = ticket_id
        self.submitted.append(ticket)
        self.states[ticket_id] = "approved"
        return ticket_id

    def fetch_by_id(self, ticket_id: str):
        state = self.states.get(ticket_id)
        if state is None:
            return None
        return SimpleNamespace(ticket_id=ticket_id, state=state)


def test_hg_required_skill_submits_ticket_before_execute():
    runtime = SkillsRuntime()
    runtime.bootstrap_one(
        {
            "skill_id": "gated.echo",
            "name": "gated.echo",
            "description": "Governance-gated echo",
            "requires_hg": True,
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "steps": ["Read the payload.", "Return the same text."],
        }
    )

    governance = FakeGovernanceHooks()
    order: list[str] = []

    def handler(spec, inputs):
        order.append("execute")
        return {"text": inputs["text"]}

    runtime._load_governance_hooks = lambda: governance
    original_submit = governance.submit

    def recording_submit(ticket):
        order.append("submit")
        return original_submit(ticket)

    governance.submit = recording_submit

    result = runtime.execute(
        "gated.echo",
        {"text": "hello", "project_id": "proj-1", "operator_id": "op-1"},
        handler=handler,
    )

    assert result["status"] == "completed"
    assert result["output"]["text"] == "hello"
    assert result["ticket_id"] == "ticket-hg-1"
    assert order == ["submit", "execute"]
    assert governance.submitted[0].origin == "skill"
    assert governance.submitted[0].project_id == "proj-1"
    assert governance.submitted[0].payload["skill_id"] == "gated.echo"


def test_hg_required_skill_accepts_real_approved_ticket():
    reset_audit_chain()
    reset_ticket_store()

    runtime = SkillsRuntime()
    runtime.bootstrap_one(
        {
            "skill_id": "gated.real",
            "name": "gated.real",
            "description": "Governance-gated real path",
            "requires_hg": True,
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "steps": ["Read the payload.", "Return the same text."],
        }
    )

    ticket_id = submit(
        GovernanceTicket(
            origin="skill",
            project_id="proj-2",
            title="Execute gated.real",
            payload={"skill_id": "gated.real"},
            requested_by="test-suite",
        )
    )
    assert resolve(ticket_id, "approved", reviewer="tester") is True

    result = runtime.execute(
        "gated.real",
        {"text": "approved", "project_id": "proj-2", "ticket_id": ticket_id},
        handler=lambda spec, inputs: {"text": inputs["text"]},
    )

    assert result["status"] == "completed"
    assert result["ticket_id"] == ticket_id
    assert result["output"]["text"] == "approved"

    reset_ticket_store()
    reset_audit_chain()
