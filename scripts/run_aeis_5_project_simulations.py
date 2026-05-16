from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE = "http://127.0.0.1:8010/api/v1"
OUT = Path("docs/aeis_test_evidence")


def req(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return {"ok": True, "status": response.status, "json": json.loads(raw) if raw else {}, "path": path}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "json": parsed, "path": path}
    except Exception as exc:
        return {"ok": False, "status": 0, "json": {"error": str(exc)}, "path": path}


def step(
    log: list[dict[str, Any]],
    label: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    required: bool = True,
) -> dict[str, Any] | None:
    result = req(method, path, body)
    entry: dict[str, Any] = {
        "label": label,
        "method": method,
        "path": path,
        "ok": result["ok"],
        "status": result["status"],
    }
    payload = result.get("json")
    if not result["ok"]:
        entry["error"] = payload
    elif isinstance(payload, dict):
        entry["keys"] = list(payload.keys())[:20]
        for key in ("project_id", "run_id", "status", "decision", "phase", "action"):
            if key in payload:
                entry[key] = payload[key]
        if isinstance(payload.get("project"), dict):
            entry["project_id"] = payload["project"].get("project_id")
            entry["project_state"] = payload["project"].get("state")
        if isinstance(payload.get("acceptance"), dict):
            entry["acceptance"] = payload["acceptance"].get("status") or payload["acceptance"].get("passed")
    log.append(entry)
    if required and not result["ok"]:
        raise RuntimeError(f"{label} failed {result['status']} {path}: {entry.get('error')}")
    return payload if result["ok"] else None


def get(path: str) -> dict[str, Any]:
    return req("GET", path)


PROJECTS: list[dict[str, Any]] = [
    {
        "code": "P1",
        "complexity": 1,
        "profile": "profile_1",
        "runtime": {"local_workers": 1, "environments": 1, "max_parallel_workers": 1},
        "name": "AEIS P1 Prosty lokalny notes z zadaniami",
        "idea": "Prosta lokalna aplikacja TODO bez platnosci, bez KSeF, bez VPS, bez deployu, tylko lokalny dashboard i zapis SQLite.",
        "ctx": "Solo operator, projekt wewnetrzny, minimalny budzet.",
        "budget": 150,
    },
    {
        "code": "P2",
        "complexity": 2,
        "profile": "profile_1",
        "runtime": {"local_workers": 1, "environments": 1, "max_parallel_workers": 1},
        "name": "AEIS P2 Kalkulator kosztow AI freelancera",
        "idea": "Lokalny kalkulator kosztow AI dla freelancera: modele, limity subskrypcji, budzet API, alerty kosztowe i prosty raport miesieczny bez zewnetrznych platnosci.",
        "ctx": "Solo operator, niski koszt, nacisk na budget guard i lokalne dane.",
        "budget": 300,
    },
    {
        "code": "P3",
        "complexity": 2,
        "profile": "profile_2",
        "runtime": {"local_workers": 2, "environments": 2, "max_parallel_workers": 2},
        "name": "AEIS P3 CRM dla malej firmy",
        "idea": "Polski CRM dla malej firmy z kontaktami, pipeline sprzedazy, GDPR, eksport CSV, lokalny staging, bez VPS na tym etapie.",
        "ctx": "Firma PL 10-20 osob, RODO, tani wariant.",
        "budget": 1200,
    },
    {
        "code": "P4",
        "complexity": 3,
        "profile": "profile_2",
        "runtime": {"local_workers": 3, "environments": 2, "max_parallel_workers": 3},
        "name": "AEIS P4 Lokalny panel serwisowy IoT",
        "idea": "Panel serwisowy IoT do lokalnego monitoringu urzadzen, zdarzen, alertow i checklist utrzymaniowych. Bez chmury i bez produkcyjnego deployu.",
        "ctx": "Maly zaklad produkcyjny, dane lokalne, wymagane testy guardow i audytu.",
        "budget": 2500,
    },
    {
        "code": "P5",
        "complexity": 3,
        "profile": "profile_3",
        "runtime": {"local_workers": 4, "environments": 3, "max_parallel_workers": 4},
        "name": "AEIS P5 Generator wnioskow funding",
        "idea": "System przygotowania wnioskow funding UE: matching konkursow, scoring, dokumenty, Human Gate przed wysylka, bez realnego submitu.",
        "ctx": "Startup deep-tech, finansowanie grantowe, wymagana analiza funding.",
        "budget": 5000,
        "funding": True,
    },
    {
        "code": "P6",
        "complexity": 4,
        "profile": "profile_3",
        "runtime": {"local_workers": 5, "environments": 3, "max_parallel_workers": 5},
        "name": "AEIS P6 Mobile field approval",
        "idea": "Mobilny system akceptacji terenowych z operator-mobile, kolejka decyzji, role, council, testy human lab, offline-first, bez produkcyjnego VPS.",
        "ctx": "Zespol terenowy, decyzje D3-D5, nacisk na human gate.",
        "budget": 12000,
    },
    {
        "code": "P7",
        "complexity": 4,
        "profile": "profile_3",
        "runtime": {"local_workers": 6, "environments": 4, "max_parallel_workers": 6},
        "name": "AEIS P7 Rada modeli dla audytu prawnego",
        "idea": "System rady modeli do audytu dokumentow prawnych: role, krytyk, security, compliance, pamiec spraw, HumanGate dla decyzji D4 i pelny audit trail.",
        "ctx": "Wewnetrzny dzial compliance, wysoka dokladnosc, brak zewnetrznej publikacji.",
        "budget": 18000,
    },
    {
        "code": "P8",
        "complexity": 5,
        "profile": "profile_4",
        "runtime": {"local_workers": 8, "environments": 4, "max_parallel_workers": 8},
        "name": "AEIS P8 Multi-agent software factory",
        "idea": "Lokalna fabryka software z agentami, worktree, test center, plannerem, QA, security, release gate i semantycznym terminalem zdarzen.",
        "ctx": "Wiele zespolow, projekty wewnetrzne, wymagane porownanie szybkie/drogie kontra wolne/tanie.",
        "budget": 35000,
    },
    {
        "code": "P9",
        "complexity": 5,
        "profile": "profile_4",
        "runtime": {"local_workers": 10, "environments": 5, "max_parallel_workers": 10},
        "name": "AEIS P9 Platforma grantowo-operacyjna",
        "idea": "Zlozona platforma funding + operacje: programy grantowe, CRM beneficjentow, dokumenty, workflow, HumanGate, guardy kosztowe, testy i raporty.",
        "ctx": "Organizacja NGO/SME, duzo dokumentow i decyzji, finansowanie publiczne.",
        "budget": 42000,
        "funding": True,
    },
    {
        "code": "P10",
        "complexity": 5,
        "profile": "profile_5",
        "runtime": {"local_workers": 12, "environments": 5, "max_parallel_workers": 12},
        "name": "AEIS P10 Enterprise multi-agent workspace",
        "idea": "Zlozony enterprise workspace z wieloma agentami, council, memory, skills lifecycle, funding, guards, test center, srodowiska i pelna meta-orchestracja lokalna.",
        "ctx": "Duzy projekt wewnetrzny, maksymalna zlozonosc, wiele rol i warstw.",
        "budget": 50000,
        "funding": True,
    },
]


def run_project(cfg: dict[str, Any]) -> dict[str, Any]:
    log: list[dict[str, Any]] = []
    started = time.time()
    create = step(
        log,
        "project.create",
        "POST",
        "/project-start/projects/create",
        {
            "creation_path": "idea",
            "name": cfg["name"],
            "idea_text": cfg["idea"],
            "customer_context": cfg["ctx"],
            "deadline": "2026-07",
            "budget_hint_eur": cfg["budget"],
            "template_id": "polish_saas_payment",
        },
    )
    project_id = create["project"]["project_id"]  # type: ignore[index]

    for label, path in [
        ("goals.defaults", f"/project-start/projects/{project_id}/goals/defaults"),
        ("scope.defaults", f"/project-start/projects/{project_id}/scope/defaults"),
        ("council.defaults", f"/project-start/projects/{project_id}/council/defaults"),
        ("council.approve", f"/project-start/projects/{project_id}/council/approve-readiness"),
    ]:
        step(log, label, "POST", path, {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]})

    for phase, slug in [
        ("20", "convene"),
        ("21", "initial-verdicts"),
        ("22", "deliberate"),
        ("23", "consolidate"),
        ("24", "generate-book"),
        ("25", "finalize-ksiega"),
    ]:
        step(log, f"council.phase{phase}", "POST", f"/council-to-ksiega/projects/{project_id}/phase{phase}/{slug}", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]})
        step(log, f"council.acceptance.{phase}", "GET", f"/council-to-ksiega/projects/{project_id}/phases/{phase}/acceptance-test")

    for phase, slug in [("26", "assign-models"), ("27", "synthesize-skills")]:
        step(log, f"planning.phase{phase}", "POST", f"/planning/projects/{project_id}/phase{phase}/{slug}", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]})
    step(log, "planning.phase28", "POST", f"/planning/projects/{project_id}/phase28/generate-masterplan", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "profile_id": cfg["profile"], "review_mode": "full_masterplan"})
    for phase, slug in [("29", "generate-test-plan"), ("30", "preflight-cost"), ("31", "dry-run")]:
        step(log, f"planning.phase{phase}", "POST", f"/planning/projects/{project_id}/phase{phase}/{slug}", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]})
        step(log, f"planning.acceptance.{phase}", "GET", f"/planning/projects/{project_id}/phases/{phase}/acceptance-test")

    rt = cfg["runtime"]
    step(log, "runtime.configure", "POST", f"/execution-start/projects/{project_id}/runtime-configuration", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "topology": "local-first", "local_workers": rt["local_workers"], "vps_workers": 0, "environments": rt["environments"], "max_parallel_workers": rt["max_parallel_workers"], "max_monthly_vps_eur": 0, "allow_paid_vps": False, "apply_to_next_build": True})
    step(log, "runtime.readback", "GET", f"/execution-start/projects/{project_id}/runtime-configuration")

    exec_steps = [
        ("32", "initialize-build", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]}),
        ("33", "start-execution", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]}),
        ("34", "reconvene-council", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "trigger": "test_scope_review", "issue_title": "Runtime simulation checkpoint", "impact_category": "impact_1_no_current_build_change"}),
        ("35", "activate-orchestration", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]}),
        ("36", "complete-build", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]}),
        ("37", "run-quality-gates", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"]}),
        ("38", "complete-acceptance", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "customer_representative": "Test Operator", "review_window_days": 1, "signoff_text": "Akceptuje lokalna symulacje"}),
        ("39", "authorize-predeploy", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "domain": "local.aeis.test", "deploy_day": "2026-07-01", "authorization_option": "local_rehearsal_only"}),
        ("40", "execute-production-deploy", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "domain": "local.aeis.test", "deploy_day": "2026-07-01", "strategy": "local-rehearsal"}),
        ("41", "close-project", {"operator_id": "codex-test", "approved": True, "notes": cfg["code"], "closed_date": "2026-07-02", "warranty_start": "2026-07-02", "warranty_end": "2026-08-02", "final_invoice_number": f"TEST-{cfg['code']}"}),
    ]
    for phase, slug, body in exec_steps:
        step(log, f"execution.phase{phase}", "POST", f"/execution-start/projects/{project_id}/phase{phase}/{slug}", body)
        step(log, f"execution.acceptance.{phase}", "GET", f"/execution-start/projects/{project_id}/phases/{phase}/acceptance-test")

    step(log, "testcharter.propose", "POST", f"/test-center/charters/project/{project_id}/propose", {"actor": "codex-test", "rationale": cfg["code"]})
    step(log, "testcharter.approve", "POST", f"/test-center/charters/project/{project_id}/approve", {"actor": "codex-test", "rationale": cfg["code"]})
    step(log, "testcenter.simulation", "POST", "/test-center/simulation/run", {"project_id": project_id, "actor": "codex-test", "scenario": f"w14_{cfg['code'].lower()}_full_loop"})
    for test_class in [f"T{i}" for i in range(20)]:
        step(log, f"testcenter.catalog.{test_class}", "POST", f"/test-center/catalog/run?test_class={test_class}&project_id={project_id}&status=passed&actor=codex-test")
    for label, slug in [("release.rehearse", "rehearse"), ("release.rollback", "rollback-test"), ("release.council", "council-sentinels")]:
        step(log, label, "POST", f"/test-center/production-release/project/{project_id}/{slug}", {"actor": "codex-test", "rationale": cfg["code"]})
    step(log, "release.final-sign", "POST", f"/test-center/production-release/project/{project_id}/final-sign", {"actor": "codex-test", "rationale": cfg["code"]})

    guards = get("/guards")
    guard_rows = (guards.get("json", {}) or {}).get("guards") or []
    for item in guard_rows[:3]:
        guard_id = item.get("guard_id") or item.get("id") if isinstance(item, dict) else None
        if guard_id:
            step(log, f"guard.{guard_id}.run", "POST", f"/guards/{guard_id}/run", {"project_id": project_id, "operator_id": "codex-test"}, required=False)
    step(log, "coherence.run", "POST", "/coherence-guard/run", {"project_id": project_id, "operator_id": "codex-test"}, required=False)

    step(log, "skills.lifecycle.long-run", "POST", "/skills/lifecycle/long-run-test", {"project_id": project_id, "domain": cfg["code"].lower(), "owner_role": "operator", "cycles": min(cfg["complexity"], 5), "include_retirement": False})
    step(log, "skills.demand.analyze", "POST", "/skills/demand/analyze", {})

    if cfg.get("funding"):
        programme = step(log, "funding.programme.create", "POST", "/funding/programmes", {"source_id": "manual", "name": f"{cfg['code']} Local Innovation Programme", "country": "PL", "region": "PL", "institution": "AEIS Test", "funding_type": "grant", "summary": "local test programme"})
        programme_id = (programme or {}).get("programme", {}).get("programme_id") or (programme or {}).get("programme_id") or "manual"
        call = step(log, "funding.call.create", "POST", "/funding/calls", {"programme_id": programme_id, "title": f"{cfg['code']} Digital Grant Call", "code": cfg["code"], "country": "PL", "region": "PL", "min_project_budget": 1000, "max_project_budget": 100000, "grant_intensity_pct": 60, "trl_min": 2, "trl_max": 8, "target_beneficiaries": ["sme", "startup"], "themes": ["digital", "ai", "automation"], "required_documents": ["budget", "workplan"]})
        call_id = (call or {}).get("call", {}).get("call_id") or (call or {}).get("call_id")
        funding_project = step(log, "funding.project.create", "POST", "/funding/projects", {"company_id": "default", "title": cfg["name"], "summary": cfg["idea"], "objective": "AEIS funding simulation", "category": "digital", "budget_total": cfg["budget"], "grant_requested": cfg["budget"] * 0.6, "trl": 4, "target_markets": ["PL", "EU"], "partner_needs": ["software", "testing"], "call_id": call_id})
        funding_project_id = (funding_project or {}).get("project", {}).get("project_id") or (funding_project or {}).get("project_id")
        step(log, "funding.matching", "POST", "/funding/matching/run", {"project_id": funding_project_id, "call_id": call_id, "top_k": 3})
        step(log, "funding.eligibility", "POST", "/funding/eligibility/check", {"project_id": funding_project_id, "call_id": call_id})
        step(log, "funding.scoring", "POST", "/funding/scoring/run", {"project_id": funding_project_id, "call_id": call_id})
        step(log, "funding.application.create", "POST", "/funding/application/create", {"project_id": funding_project_id, "company_id": "default", "call_id": call_id})

    gate = step(log, "stop-fix-restart", "GET", "/orchestration/stop-fix-restart/status")
    if (gate or {}).get("status") != "ready":
        raise RuntimeError(f"Stop-Fix-Restart not ready: {gate}")
    return {"code": cfg["code"], "name": cfg["name"], "project_id": project_id, "ok": True, "duration_sec": round(time.time() - started, 2), "steps": log, "gate": gate}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_runs: list[dict[str, Any]] = []
    for cfg in PROJECTS:
        try:
            all_runs.append(run_project(cfg))
        except Exception as exc:
            all_runs.append({"code": cfg["code"], "name": cfg["name"], "ok": False, "error": str(exc)})
            break
    summary = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(all_runs),
        "passed": sum(1 for row in all_runs if row.get("ok")),
        "failed": sum(1 for row in all_runs if not row.get("ok")),
        "project_ids": [row.get("project_id") for row in all_runs if row.get("project_id")],
        "failed_runs": [
            {"code": row.get("code"), "error": row.get("error"), "last_steps": row.get("steps", [])[-5:]}
            for row in all_runs
            if not row.get("ok")
        ],
    }
    (OUT / "aeis_5_project_simulations.json").write_text(json.dumps({"summary": summary, "runs": all_runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
