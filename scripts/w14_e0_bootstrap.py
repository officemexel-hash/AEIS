"""W14 E0 Bootstrap: Council session + Evidence Pack + HG ticket.

Usage:
    python scripts/w14_e0_bootstrap.py

Wykonuje:
1. Otwiera Council session (CouncilHybrid) z 4 modelami symulujacymi 9 rol
2. Dodaje 9 uczestnikow z rolami/rangami/wagami (canonical taxonomy)
3. Tworzy Evidence Pack D4 z artefactami (RFC kanon + briefy + integration contracts)
4. Tworzy HumanGate request (production gate, P2 priority)
5. Drukuje IDs
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

# Path setup - dolacz src/sylion-pipeline do PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "src" / "sylion-pipeline"
sys.path.insert(0, str(PIPELINE))

# DB path (must match backend)
DB_PATH = str(ROOT / "src" / "sylion-pipeline" / "sylion_aeis.db")
if not Path(DB_PATH).exists():
    # Fallback - moze byc w innym miejscu
    alt = ROOT / "sylion_aeis.db"
    if alt.exists():
        DB_PATH = str(alt)
    else:
        # Search
        candidates = list(ROOT.rglob("sylion_aeis.db"))
        if candidates:
            DB_PATH = str(candidates[0])

print(f"[w14-e0] Using DB: {DB_PATH}")

from sylion.governance.council_hybrid import CouncilHybrid
from sylion.governance.evidence_packs import EvidencePackManager
from sylion.governance.human_gate import HumanGate

# ============================================================
# 1. Council Session
# ============================================================
print("\n[w14-e0] Opening Council session...")

council = CouncilHybrid(db_path=DB_PATH)
session = council.open_session(
    topic="W14 RFC v2.1 -> Frozen Canon promotion",
    models=["claude-opus-4-7", "gpt-5", "claude-sonnet-4-6", "kimi-k2"],
    context=(
        "Council session for promoting W14 (Testing/Simulation/Repair/Release "
        "Governance) RFC v2.1 to Frozen Canon. Pre-implementation gate for "
        "E1-E12. Scope: 24 ontology objects, 19 actions MVP, 13 guardians, "
        "Sim L0-L4, 4 starter personas, 7 starter human errors, Loop Governor "
        "with hard limits, Merge Guard with 8 structural rejections, Release "
        "Rail with 10 statuses, plus 6 demo projects (E11) and Agent Team "
        "Theater dashboard (E12). Full canon: docs/CLAUDE_AEIS_W14_TESTING.md "
        "(37 sections). Briefs: docs/w14_workplan/ (16 files)."
    ),
    moderator_model="claude-opus-4-7",
)
session_id = session["session_id"]
print(f"[w14-e0] Council session: {session_id}")
print(f"        topic: {session['topic']}")
print(f"        models: {session['models']}")
print(f"        phase: {session['phase']}")

# ============================================================
# 2. Add 9 canonical participants
# ============================================================
print("\n[w14-e0] Adding 9 canonical participants...")

participants = [
    ("claude-opus-4-7",  "planner",            "primary"),
    ("gpt-5",            "architect",          "primary"),
    ("claude-sonnet-4-6","critic",             "primary"),    # CRITIC SIGNATURE REQUIRED
    ("kimi-k2",          "verifier",           "senior"),
    ("claude-opus-4-7",  "governance",         "primary"),
    ("gpt-5",            "cost_sentinel",      "support"),    # SENTINEL BLOCK
    ("claude-sonnet-4-6","security_sentinel",  "support"),    # SENTINEL BLOCK
    ("claude-opus-4-7",  "domain_specialist",  "senior"),
    ("gpt-5",            "funding_specialist", "review_only"),
]

added = []
for model_id, role, rank in participants:
    try:
        result = council.add_participant(
            session_id=session_id,
            model_id=model_id,
            role=role,
            rank=rank,
        )
        added.append((model_id, role, rank, result.get("participant_id", "?")))
        print(f"        +{role:20s} ({rank:14s}) <- {model_id}")
    except Exception as e:
        print(f"        FAIL {role}: {e}")

print(f"[w14-e0] Added {len(added)}/9 participants")

# ============================================================
# 3. Evidence Pack D4
# ============================================================
print("\n[w14-e0] Creating Evidence Pack D4...")

ep_mgr = EvidencePackManager(db_path=DB_PATH)
proposal_id = f"w14_rfc_v2.1_{int(time.time())}"
pack = ep_mgr.create_pack(proposal_id=proposal_id, decision_class="D4")
pack_id = pack.pack_id
print(f"[w14-e0] Evidence Pack: {pack_id}")
print(f"        proposal_id: {proposal_id}")
print(f"        decision_class: D4")

# Add artefacts (hashes of W14 documents)
artefacts_to_add = [
    ("docs/CLAUDE_AEIS_W14_TESTING.md", "decision_record",
     "W14 RFC v2.1 canonical document (37 sections, ~1300 lines)"),
    ("docs/w14_workplan/W14_OVERVIEW.md", "decision_record",
     "Master workplan E0-E12 with multi-model task split"),
    ("docs/w14_workplan/W14_INTEGRATION_CONTRACTS.md", "contract_snapshot",
     "Interface contracts C1-C14 for inter-stage integration"),
    ("docs/w14_workplan/W14_COORDINATION.md", "decision_record",
     "Workflow handoff + commit conventions + file ownership matrix"),
    ("docs/w14_workplan/W14_PROMPT_CODEX_E1_IMPL.md", "decision_record",
     "Codex E1 brief: Ontology implementation"),
    ("docs/w14_workplan/W14_PROMPT_KIMI_E11_DEMO.md", "decision_record",
     "Kimi E11 brief: 6 demo projects"),
    ("docs/w14_workplan/W14_PROMPT_CODEX_E12_THEATER.md", "decision_record",
     "Agent Team Theater dashboard brief"),
]

added_art = 0
for rel_path, atype, desc in artefacts_to_add:
    abs_path = ROOT / rel_path
    if not abs_path.exists():
        print(f"        SKIP (missing): {rel_path}")
        continue
    content = abs_path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    try:
        artefact = ep_mgr.add_artefact(
            pack_id=pack_id,
            name=rel_path,
            type=atype,
            content_hash=content_hash,
            metadata={
                "description": desc,
                "size_bytes": len(content),
                "abs_path": str(abs_path),
            },
        )
        added_art += 1
        print(f"        +artefact: {rel_path} ({atype}, {len(content)} bytes)")
    except Exception as e:
        print(f"        FAIL artefact {rel_path}: {e}")

print(f"[w14-e0] Added {added_art}/{len(artefacts_to_add)} artefacts")

# Submit pack (draft -> submitted)
try:
    submit_result = ep_mgr.submit_pack(pack_id)
    print(f"[w14-e0] Pack submitted. fidelity_score: {submit_result.get('fidelity_score', '?')}")
except Exception as e:
    print(f"[w14-e0] Submit FAIL (likely insufficient artefacts for D4 = need 5): {e}")

# ============================================================
# 4. Human Gate request
# ============================================================
print("\n[w14-e0] Creating Human Gate request...")

hg = HumanGate(db_path=DB_PATH)
hg_request = hg.create_request(
    gate_id="w14_e0_promotion_gate",
    title="W14 RFC v2.1 -> Frozen Canon (production)",
    description=(
        f"Council session: {session_id}\n"
        f"Evidence Pack: {pack_id} (D4)\n"
        f"Proposal: {proposal_id}\n\n"
        f"Scope: Promotion of W14 (Testing/Simulation/Repair/Release "
        f"Governance) from RFC v2.1 to Frozen Canon. Approving this gate "
        f"unblocks E1-E12 implementation (24 ontology objects, 19 actions, "
        f"13 guardians, 6 demo projects, Agent Team Theater).\n\n"
        f"Rollback plan: If approved and implementation reveals fundamental "
        f"problem, revert package aeis/testing/ontology/ (clean catalog, no "
        f"deps from other modules in E1). W14 status reverts to RFC.\n\n"
        f"Fidelity test: After Frozen, repeat Council session with different "
        f"models within 24h, verify consistent consolidation.\n\n"
        f"Files: docs/CLAUDE_AEIS_W14_TESTING.md + docs/w14_workplan/ (16 briefs)"
    ),
    requested_by="claude-opus-4-7",
    context_json={
        "council_session_id": session_id,
        "evidence_pack_id": pack_id,
        "proposal_id": proposal_id,
        "decision_class": "D4",
        "gate_type": "production",
        "priority": "high",
        "rfc_version": "v2.1",
        "next_etap_after_approve": "E1",
    },
)
request_id = hg_request["request_id"]
print(f"[w14-e0] HG request: {request_id}")
print(f"        title: {hg_request['title']}")
print(f"        priority: {hg_request['priority']}")
print(f"        status: {hg_request['status']}")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("W14 E0 BOOTSTRAP COMPLETE")
print("=" * 60)
print(f"Council session ID: {session_id}")
print(f"Evidence Pack ID:   {pack_id}")
print(f"HG request ID:      {request_id}")
print()
print("Next steps:")
print(f"  1. Operator reviews HG request {request_id}")
print(f"  2. After approve: start E1 (Ontology design + Codex impl)")
print(f"  3. Council deliberation can run in parallel (consolidation gated)")
print()
print("View in UI:")
print(f"  http://localhost:8000/api/v1/governance/council/sessions")
print(f"  http://localhost:8000/api/v1/governance/evidence-packs/{pack_id}")
print(f"  http://localhost:8000/api/v1/human-gate (frontend page)")
