# AEIS Generated Product Test Matrix

Status: running

## Product Pass Rule

A generated product passes only when it exists locally, opens, is not a placeholder, implements its business flow, handles validation/errors, and is tied back to project evidence.

## Matrix

| Project | Artifact Path | Opens Locally | Not Placeholder | Data Present | Buttons Work | Forms Validate | Business Flow Works | No External Action Without Gate | Test Center Result | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 Mini CRM | `C:\Users\razor\.sylion\projects\proj-91014e2cad46-p1-restart2-mini-crm-lokalny-aeis\code\repo` | PASS | PASS, 218-file forbidden/placeholder scan clean | PASS | PASS by generated API test | PASS by FastAPI/Pydantic test path | PASS: contact, note, reminder, CSV, GDPR export/delete | PASS: local-only, zero external submission/spend | Generated backend pytest `1 passed` | PASS |
| P2 Funding Assistant | `C:\Users\razor\.sylion\projects\proj-7544e8bdd3ea-p2-restart4-funding-ngo-aeis\code\repo` | PASS | PASS, 218-file forbidden/placeholder scan clean | PASS | PASS by generated API test | PASS by FastAPI/Pydantic test path | PASS: grant match, deadline/source blockers, documents, legal/budget/document confirmations, HumanGate, local rehearsal | PASS: external submit blocked/local only | Generated backend pytest `1 passed` | PASS |
| P3 Mobile Approval Queue | `C:\Users\razor\.sylion\projects\proj-635af5715faf-p3-restart-mobile-approval-queue-aeis\code\repo` | PASS | PASS, 218-file forbidden/placeholder scan clean | PASS | PASS by generated API test | PASS by FastAPI/Pydantic test path | PASS: pending queue, device token binding, invalid-token block, approve and reject paths | PASS: external action false/local only | Generated backend pytest `1 passed` | PASS |
| P4 Local Automation Runtime | `C:\Users\razor\.sylion\projects\proj-f3e2a536e48c-p4-restart-local-automation-runtime-aeis\code\repo` | PASS | PASS, 230-file scan acceptable; only Hetzner terms are blocking evidence with `hetzner_provisioned=false` | PASS | PASS by generated API test | PASS by FastAPI/Pydantic test path | PASS: runtime config, queued task, retry, logs, traces, status reporting | PASS: attempted VPS config reset to local-only, external deploy false | Generated backend pytest `1 passed` | PASS |
| P5 Complex Multi-Domain | `C:\Users\razor\.sylion\projects\proj-b9c142b06eb4-p5-restart-multi-domain-aeis\code\repo` | PASS | PASS, 230-file forbidden/placeholder scan clean | PASS | PASS by generated API test | PASS by FastAPI/Pydantic test path | PASS: CRM, funding, mobile approvals, automation runtime, governance, memory reuse and guards preserved | PASS: attempted VPS config reset to local-only; external actions require HumanGate and record `external_action_blocked` | Generated backend pytest `1 passed` | PASS |
