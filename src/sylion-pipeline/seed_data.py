#!/usr/bin/env python3
"""
SYLION seed script -- populates the backend with realistic data via REST API.

Usage:
    python seed_data.py [--base-url http://localhost:8000]

All endpoints use query parameters (not JSON body). The script is idempotent:
re-running it will add more rows but won't crash on duplicates.
"""

import json
import sys
import urllib.parse
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(path: str, params: dict) -> dict | None:
    """POST to an API endpoint with query-string params. Returns JSON or None."""
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405, 500, 501):
            print(f"  SKIP {path} -> HTTP {exc.code}")
            return None
        if exc.code == 409:
            print(f"  SKIP (duplicate) {path} -> HTTP 409")
            return None
        body = exc.read().decode("utf-8", errors="replace")
        print(f"  ERR  {path} -> HTTP {exc.code}: {body[:200]}")
        return None
    except urllib.error.URLError as exc:
        print(f"  ERR  {path} -> {exc.reason}")
        return None
    except Exception as exc:
        print(f"  ERR  {path} -> {exc}")
        return None


def _ok(result: dict | None) -> bool:
    return result is not None


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

def seed_modules():
    """1. Core Modules -- 10 modules with varied kinds (A-L) and plans (P01-P10)."""
    print("\n=== Seeding 10 Core Modules ===")
    modules = [
        {"module_id": "core.kernel",       "module_kind": "A", "owner_plan": "P01",
         "description": "Central kernel orchestrating module lifecycle and events",
         "implementation_strategy": "greenfield", "decision_class_entry": "D5",
         "depends_on": ""},
        {"module_id": "core.event_bus",    "module_kind": "A", "owner_plan": "P01",
         "description": "NATS-backed event bus for inter-module communication",
         "implementation_strategy": "greenfield", "decision_class_entry": "D4",
         "depends_on": "core.kernel"},
        {"module_id": "memory.kanon",      "module_kind": "B", "owner_plan": "P02",
         "description": "Kanon knowledge access and section management",
         "implementation_strategy": "greenfield", "decision_class_entry": "D3",
         "depends_on": "core.kernel"},
        {"module_id": "memory.retrieval",  "module_kind": "B", "owner_plan": "P02",
         "description": "Vector-based memory retrieval and indexing",
         "implementation_strategy": "greenfield", "decision_class_entry": "D3",
         "depends_on": "memory.kanon"},
        {"module_id": "cognitive.planner","module_kind": "C", "owner_plan": "P03",
         "description": "Hierarchical task planner with dependency resolution",
         "implementation_strategy": "greenfield", "decision_class_entry": "D4",
         "depends_on": "core.kernel"},
        {"module_id": "cognitive.router",  "module_kind": "C", "owner_plan": "P03",
         "description": "LLM model router with cost-aware selection",
         "implementation_strategy": "greenfield", "decision_class_entry": "D3",
         "depends_on": "cognitive.planner"},
        {"module_id": "governance.decision","module_kind": "D", "owner_plan": "P04",
         "description": "Decision ladder with D0-D5 classification engine",
         "implementation_strategy": "greenfield", "decision_class_entry": "D5",
         "depends_on": "core.kernel"},
        {"module_id": "skills.registry",   "module_kind": "E", "owner_plan": "P05",
         "description": "Skills registry with lifecycle management",
         "implementation_strategy": "greenfield", "decision_class_entry": "D3",
         "depends_on": "core.kernel"},
        {"module_id": "efficiency.perf",   "module_kind": "H", "owner_plan": "P08",
         "description": "Runtime performance tracker and SLO management",
         "implementation_strategy": "greenfield", "decision_class_entry": "D3",
         "depends_on": "core.kernel"},
        {"module_id": "aeis.improvement",  "module_kind": "I", "owner_plan": "P09",
         "description": "Self-improvement queue with prioritization",
         "implementation_strategy": "greenfield", "decision_class_entry": "D4",
         "depends_on": "core.kernel"},
    ]
    ok = 0
    for m in modules:
        result = _post("/api/v1/core/modules", m)
        if _ok(result):
            ok += 1
            print(f"  OK   module {m['module_id']} ({m['module_kind']})")
    print(f"  --> {ok}/{len(modules)} modules registered")


def seed_contracts():
    """2. Contracts -- 5 inter-module contracts."""
    print("\n=== Seeding 5 Contracts ===")
    contracts = [
        {"name": "EventBus.v1", "contract_type": "grpc_service", "version": "1.0.0",
         "schema_def": "message Envelope { string event_id; string topic; bytes payload; }",
         "producer_module": "core.event_bus",
         "consumer_modules": "memory.kanon,cognitive.planner,governance.decision",
         "description": "NATS event bus publish/subscribe contract"},
        {"name": "KanonAccess.v1", "contract_type": "grpc_service", "version": "1.0.0",
         "schema_def": "message SectionRequest { string section_id; }",
         "producer_module": "memory.kanon",
         "consumer_modules": "memory.retrieval,cognitive.planner",
         "description": "Kanon section read/write contract"},
        {"name": "ModelRouting.v1", "contract_type": "grpc_service", "version": "1.1.0",
         "schema_def": "message RouteRequest { string task_type; string tier; }",
         "producer_module": "cognitive.router",
         "consumer_modules": "cognitive.planner,skills.registry",
         "description": "LLM model routing and selection contract"},
        {"name": "DecisionGate.v1", "contract_type": "grpc_service", "version": "1.0.0",
         "schema_def": "message GateRequest { string decision_class; string proposal_id; }",
         "producer_module": "governance.decision",
         "consumer_modules": "core.kernel,aeis.improvement",
         "description": "Decision gate evaluation contract"},
        {"name": "PerfSLO.v1", "contract_type": "rest_api", "version": "1.0.0",
         "schema_def": "GET /api/v1/efficiency/perf/slos/{endpoint}",
         "producer_module": "efficiency.perf",
         "consumer_modules": "core.kernel,governance.decision",
         "description": "Performance SLO monitoring contract"},
    ]
    ok = 0
    for c in contracts:
        result = _post("/api/v1/contracts", c)
        if _ok(result):
            ok += 1
            print(f"  OK   contract {c['name']} v{c['version']}")
    print(f"  --> {ok}/{len(contracts)} contracts published")


def seed_skills():
    """3. Skills -- 5 skills, plus executions and demand signals."""
    print("\n=== Seeding 5 Skills (+ executions + demand signals) ===")
    skills = [
        {"skill_id": "skill.adaptive-reasoning", "name": "Adaptive Reasoning",
         "domain": "cognitive", "owner_role": "planner",
         "description": "Dynamically selects reasoning strategy based on task type"},
        {"skill_id": "skill.context-retrieval", "name": "Context Retrieval",
         "domain": "memory", "owner_role": "retriever",
         "description": "Retrieves relevant context from Kanon and evidence store"},
        {"skill_id": "skill.circuit-monitor", "name": "Circuit Monitor",
         "domain": "efficiency", "owner_role": "watchdog",
         "description": "Monitors circuit breaker states and triggers alerts"},
        {"skill_id": "skill.governance-review", "name": "Governance Review",
         "domain": "governance", "owner_role": "auditor",
         "description": "Reviews decision proposals against governance gates"},
        {"skill_id": "skill.improvement-suggest", "name": "Improvement Suggest",
         "domain": "aeis", "owner_role": "optimizer",
         "description": "Analyzes system telemetry and proposes improvements"},
    ]
    ok = 0
    skill_ids = []
    for s in skills:
        result = _post("/api/v1/skills/skills", s)
        if _ok(result):
            ok += 1
            sid = s["skill_id"]
            skill_ids.append(sid)
            print(f"  OK   skill {sid}")

            # Publish the skill
            _post(f"/api/v1/skills/skills/{urllib.parse.quote(sid, safe='')}/publish", {})

    # Executions for each skill
    exec_ok = 0
    for sid in skill_ids:
        result = _post("/api/v1/skills/executions", {
            "skill_id": sid,
            "input_data": json.dumps({"trigger": "seed", "auto": True}),
        })
        if _ok(result):
            exec_ok += 1

    # Demand signals
    demand_ok = 0
    signals = [
        {"signal_type": "frequency", "source": "pipeline-cron", "skill_id": "skill.adaptive-reasoning",
         "confidence": 0.92, "details": json.dumps({"hourly_calls": 47})},
        {"signal_type": "latency_demand", "source": "slo-monitor", "skill_id": "skill.context-retrieval",
         "confidence": 0.85, "details": json.dumps({"p95_ms": 120})},
        {"signal_type": "error_spike", "source": "circuit-breaker", "skill_id": "skill.circuit-monitor",
         "confidence": 0.78, "details": json.dumps({"errors_last_hour": 3})},
        {"signal_type": "frequency", "source": "governance-cron", "skill_id": "skill.governance-review",
         "confidence": 0.67, "details": json.dumps({"pending_reviews": 2})},
        {"signal_type": "usage_trend", "source": "telemetry-agent", "skill_id": "skill.improvement-suggest",
         "confidence": 0.88, "details": json.dumps({"weekly_trend": "up_12pct"})},
    ]
    for sig in signals:
        result = _post("/api/v1/skills/demand/signals", sig)
        if _ok(result):
            demand_ok += 1

    print(f"  --> {ok}/{len(skills)} skills, {exec_ok}/{len(skill_ids)} executions, {demand_ok}/{len(signals)} demand signals")


def seed_governance():
    """4. Governance proposals -- 3 proposals at different decision classes."""
    print("\n=== Seeding 3 Governance Proposals ===")
    proposals = [
        {"title": "Upgrade model router to cost-tier routing",
         "description": "Switch from round-robin model selection to cost-aware tier routing. "
                        "Affects all modules using cognitive.router. Estimated 40% cost reduction.",
         "source_plan": "P03", "module_id": "cognitive.router",
         "change_type": "architectural", "blast_radius": "medium",
         "reversible": True, "affects_contracts": True, "affects_kernel": False,
         "proposed_by": "aeis.improvement", "rollback_plan": "Revert to round-robin routing table"},
        {"title": "Enable memory compaction for Kanon sections",
         "description": "Activate compact layer to reduce Kanon storage by 30%. "
                        "Sections older than 7 days will be compressed in-place.",
         "source_plan": "P02", "module_id": "memory.kanon",
         "change_type": "optimization", "blast_radius": "low",
         "reversible": True, "affects_contracts": False, "affects_kernel": False,
         "proposed_by": "aeis.improvement", "rollback_plan": "Disable compaction, rehydrate from backup"},
        {"title": "Migrate event bus from NATS JetStream to PostgreSQL-backed queue",
         "description": "Replace NATS with PostgreSQL LISTEN/NOTIFY for event distribution. "
                        "Reduces infrastructure dependencies but increases DB load by ~15%.",
         "source_plan": "P01", "module_id": "core.event_bus",
         "change_type": "infra", "blast_radius": "high",
         "reversible": False, "affects_contracts": True, "affects_kernel": True,
         "proposed_by": "governance.decision", "rollback_plan": "N/A -- irreversible infrastructure change"},
    ]
    ok = 0
    for p in proposals:
        result = _post("/api/v1/governance/proposals", p)
        if _ok(result):
            ok += 1
            print(f"  OK   proposal: {p['title'][:50]}...")
    print(f"  --> {ok}/{len(proposals)} proposals submitted")


def seed_models():
    """5. Cognitive models -- 4 LLM models with realistic costs."""
    print("\n=== Seeding 4 Cognitive Models ===")
    models = [
        {"model_id": "gpt-4.1-mini", "provider": "openai", "name": "GPT-4.1 Mini",
         "tier": "standard", "cost_per_1k_input": 0.0004, "cost_per_1k_output": 0.0016,
         "max_context": 1047576, "capabilities": "chat,code,analysis"},
        {"model_id": "claude-sonnet-4-20250514", "provider": "anthropic", "name": "Claude Sonnet 4",
         "tier": "standard", "cost_per_1k_input": 0.003, "cost_per_1k_output": 0.015,
         "max_context": 200000, "capabilities": "chat,code,analysis,vision"},
        {"model_id": "gemini-2.5-pro", "provider": "google", "name": "Gemini 2.5 Pro",
         "tier": "premium", "cost_per_1k_input": 0.00125, "cost_per_1k_output": 0.005,
         "max_context": 1048576, "capabilities": "chat,code,analysis,vision,audio"},
        {"model_id": "glm-4-flash", "provider": "zhipu", "name": "GLM-4 Flash",
         "tier": "economy", "cost_per_1k_input": 0.0001, "cost_per_1k_output": 0.0001,
         "max_context": 128000, "capabilities": "chat,code"},
    ]
    ok = 0
    for m in models:
        result = _post("/api/v1/cognitive/models", m)
        if _ok(result):
            ok += 1
            print(f"  OK   model {m['model_id']} ({m['provider']}, tier={m['tier']})")
    print(f"  --> {ok}/{len(models)} models registered")


def seed_efficiency():
    """6. Efficiency SLOs -- 5 endpoint performance budgets."""
    print("\n=== Seeding 5 Efficiency SLOs ===")
    slos = [
        {"endpoint": "/api/v1/core/modules",
         "target_p95_ms": 50, "target_error_rate": 0.001,
         "description": "Module registry listing must be fast for dashboard"},
        {"endpoint": "/api/v1/memory/kanon/sections",
         "target_p95_ms": 120, "target_error_rate": 0.005,
         "description": "Kanon section listing with optional chapter filter"},
        {"endpoint": "/api/v1/cognitive/models/route",
         "target_p95_ms": 30, "target_error_rate": 0.001,
         "description": "Model routing must be near-instant for real-time use"},
        {"endpoint": "/api/v1/skills/executions",
         "target_p95_ms": 200, "target_error_rate": 0.01,
         "description": "Skill execution endpoint tolerates higher latency"},
        {"endpoint": "/api/v1/governance/proposals",
         "target_p95_ms": 80, "target_error_rate": 0.002,
         "description": "Governance proposal submission with auto-classification"},
    ]
    ok = 0
    for s in slos:
        result = _post("/api/v1/efficiency/perf/slos", s)
        if _ok(result):
            ok += 1
            print(f"  OK   SLO {s['endpoint']} (p95<{s['target_p95_ms']}ms)")
    print(f"  --> {ok}/{len(slos)} SLOs defined")


def seed_memory():
    """7. Memory/Kanon sections -- 5 sections."""
    print("\n=== Seeding 5 Kanon Sections ===")
    sections = [
        {"section_id": "kanon.architecture.overview", "title": "Architecture Overview",
         "content": "SYLION is a 65-module autonomous system organized into 12 domains (A-L). "
                    "Each module follows the ModuleManifest contract with lifecycle stages: "
                    "PLANNED, IN_PROGRESS, ACTIVE, DEPRECATED, RETIRED. Inter-module "
                    "communication flows through the event bus (core.event_bus) with "
                    "versioned contracts ensuring backward compatibility.",
         "chapter": "Architecture", "section_number": 1, "hash": "a1b2c3d4"},
        {"section_id": "kanon.governance.decisions", "title": "Decision Classification",
         "content": "All system changes are classified D0-D5 by the decision gate engine. "
                    "D0: trivial config change (auto-approved). D1: non-breaking parameter "
                    "adjustment. D2: minor feature addition. D3: standard module change. "
                    "D4: cross-module architectural change. D5: kernel or infra change "
                    "requiring full council review.",
         "chapter": "Governance", "section_number": 1, "hash": "e5f6g7h8"},
        {"section_id": "kanon.aeis.principles", "title": "AEIS Self-Improvement Principles",
         "content": "The Autonomous Evolution & Improvement System (AEIS) operates under "
                    "three constraints: (1) No change without evidence -- every improvement "
                    "must be backed by telemetry or evaluation data. (2) Reversibility -- "
                    "prefer changes that can be rolled back. (3) Blast radius awareness -- "
                    "understand and limit the scope of every modification.",
         "chapter": "AEIS", "section_number": 1, "hash": "i9j0k1l2"},
        {"section_id": "kanon.cognitive.routing", "title": "Model Routing Strategy",
         "content": "The cognitive model router selects LLM providers based on task type, "
                    "required capabilities, cost tier, and context window requirements. "
                    "Routing is cost-aware: economy-tier models handle routine tasks, while "
                    "premium models are reserved for complex reasoning and analysis. "
                    "Fallback chains ensure availability across provider outages.",
         "chapter": "Cognitive", "section_number": 1, "hash": "m3n4o5p6"},
        {"section_id": "kanon.efficiency.slos", "title": "Performance SLO Framework",
         "content": "Every API endpoint has defined SLOs with target p95 latency and error "
                    "rates. The runtime performance tracker records measurements and checks "
                    "compliance against SLOs. When violations are detected, the AEIS "
                    "improvement queue is notified for self-optimization. Memory budgets "
                    "per module are tracked to prevent leaks.",
         "chapter": "Efficiency", "section_number": 1, "hash": "q7r8s9t0"},
    ]
    ok = 0
    for s in sections:
        result = _post("/api/v1/memory/kanon/sections", s)
        if _ok(result):
            ok += 1
            print(f"  OK   section {s['section_id']}")
    print(f"  --> {ok}/{len(sections)} sections stored")


def seed_aeis():
    """8. AEIS improvements -- 3 improvement proposals."""
    print("\n=== Seeding 3 AEIS Improvements ===")
    improvements = [
        {"title": "Reduce Kanon search latency by 50%",
         "description": "Current Kanon search p95 is 120ms. Target is 60ms by adding "
                        "an in-memory LRU cache for hot sections and pre-computed "
                        "trigram indexes. Evidence: 80% of searches hit 15% of sections.",
         "category": "performance", "priority": 8,
         "source": "efficiency.perf", "evidence": json.dumps({"current_p95_ms": 120, "target_p95_ms": 60})},
        {"title": "Implement circuit breaker for LLM provider calls",
         "description": "Add circuit breaker pattern to cognitive.llm_adapter so that "
                        "failing providers are temporarily removed from the routing pool. "
                        "Threshold: 5 consecutive failures within 60s opens the circuit.",
         "category": "reliability", "priority": 7,
         "source": "governance.decision", "evidence": json.dumps({"recent_outages": 2, "affected_calls": 340})},
        {"title": "Auto-deprecate unused skills after 90 days",
         "description": "Skills with zero executions in 90 days should be automatically "
                        "moved to DEPRECATED lifecycle. Reduces skill registry noise and "
                        "focuses demand analysis on active skills.",
         "category": "maintenance", "priority": 4,
         "source": "skills.registry", "evidence": json.dumps({"unused_skills": 3, "total_skills": 5})},
    ]
    ok = 0
    for imp in improvements:
        result = _post("/api/v1/aeis/improvements", imp)
        if _ok(result):
            ok += 1
            print(f"  OK   improvement: {imp['title'][:50]}...")
    print(f"  --> {ok}/{len(improvements)} improvements queued")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global BASE
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        BASE = sys.argv[-1] if not sys.argv[-1].startswith("-") else BASE

    print(f"SYLION seed script -- target: {BASE}")
    print("=" * 60)

    seed_modules()
    seed_contracts()
    seed_skills()
    seed_governance()
    seed_models()
    seed_efficiency()
    seed_memory()
    seed_aeis()

    print("\n" + "=" * 60)
    print("Seed complete.")


if __name__ == "__main__":
    main()
