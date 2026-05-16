"""SYLION Governance — D0–D5, Council 4/4, Evidence, Gates, Unified Tickets, Audit Chain.

Convenience re-exports (Wave A-Cleanup): the public Hook v1.0 API from
`sylion.governance.tickets` is available directly on this package so
callers can write::

    from sylion.governance import submit, GovernanceTicket

instead of reaching into the submodule.
"""

from sylion.governance.audit_chain import (
    GovernanceAuditChain, get_audit_chain, reset_audit_chain,
)
from sylion.governance.adr_status_enum import AdrStatusEnum
from sylion.governance.evidence_timeline import (
    EvidenceTimeline, get_evidence_timeline, reset_evidence_timeline,
)
from sylion.governance.gates_registry import (
    GatesRegistry, get_gates_registry, reset_gates_registry,
)
from sylion.governance.human_gate import (
    HumanGate, get_human_gate, reset_human_gate,
)
from sylion.governance.ticket import (
    GovernanceTicket, TicketStore,
    VALID_DECISION_CLASSES, VALID_GATE_TYPES, VALID_ORIGINS,
    VALID_PRIORITIES, VALID_STATES,
    get_ticket_store, reset_ticket_store,
)
from sylion.governance.tickets import (
    escalate, fetch_by_id, fetch_pending, resolve, stats, submit, withdraw,
)

__all__ = [
    "EvidenceTimeline",
    "get_evidence_timeline",
    "reset_evidence_timeline",
    "GatesRegistry",
    "get_gates_registry",
    "reset_gates_registry",
    "HumanGate",
    "get_human_gate",
    "reset_human_gate",
    "GovernanceTicket",
    "TicketStore",
    "VALID_DECISION_CLASSES",
    "VALID_GATE_TYPES",
    "VALID_ORIGINS",
    "VALID_PRIORITIES",
    "VALID_STATES",
    "get_ticket_store",
    "reset_ticket_store",
    "GovernanceAuditChain",
    "get_audit_chain",
    "reset_audit_chain",
    # Hook v1.0 unified API
    "submit",
    "fetch_pending",
    "fetch_by_id",
    "resolve",
    "withdraw",
    "escalate",
    "stats",
    "AdrStatusEnum",
]
