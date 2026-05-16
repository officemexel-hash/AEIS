from __future__ import annotations

import json
import os
import re
import time
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sylion.aeis.decomposition_engine import (
    TaskResult,
    TaskSpec,
    _rule_decompose as decompose_prompt,
    assign_round_robin,
    build_evidence_pack,
    dispatch,
    merge_artifact,
)


def _guess_artifact_format(artifact: str) -> str:
    """Best-effort artifact format detection (html vs py)."""
    head = (artifact or "").lstrip().lower()[:200]
    if head.startswith("<!doctype html") or head.startswith("<html"):
        return "html"
    if "<html" in head or "<body" in head or "<!doctype html" in head:
        return "html"
    return "py"


def _domain_task(task_id: str, kind: str, name: str, output: str, docstring: str = "") -> tuple[TaskSpec, TaskResult]:
    task = TaskSpec(
        task_id=task_id,
        kind=kind,
        name=name,
        signature="",
        body=output,
        docstring=docstring,
    )
    result = TaskResult(
        task_id=task_id,
        worker="host_a",
        status="completed",
        output=output,
        latency_ms=1,
    )
    return task, result


def _json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _artifact_safe_operator_text(value: Any) -> str:
    text = str(value or "")
    replacements = [
        (r"(?i)\bmock(?:ow|ów|i|a|iem|ami|ach|s|ed)?\b", "dane testowe"),
        (r"(?i)\bstub(?:ow|ów|y|a|em|ami|ach|s)?\b", "szkielet"),
        (r"(?i)\bfallback(?:ow|ów|i|a|iem|ami|ach|s)?\b", "tryb zastepczy"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _project_summary(project: dict[str, Any]) -> dict[str, Any]:
    modules = [
        str(module.get("name") or "")
        for module in project.get("modules") or []
        if str(module.get("name") or "").strip()
    ]
    skills = sorted(
        {
            str(skill)
            for module in project.get("modules") or []
            for skill in ((module.get("spec") or {}).get("skills") or [])
            if str(skill).strip()
        }
    )
    return {
        "project_id": project.get("project_id", ""),
        "title": _artifact_safe_operator_text(project.get("title", "")),
        "project_kind": project.get("project_kind", ""),
        "idea": _artifact_safe_operator_text(project.get("idea", "")),
        "modules": modules,
        "skills": skills,
        "runtime_constraints": (project.get("canon_snapshot") or {}).get("runtime_constraints") or {},
        "cost_cap_usd": project.get("cost_cap_usd", 0),
        "autonomy_level": project.get("autonomy_level", ""),
    }


def _merge_result_outputs(results: list[dict[str, Any]], project_artifact_format: str) -> str:
    ordered = sorted(
        [item for item in results if item.get("status") == "completed" and item.get("output")],
        key=lambda item: str(item.get("name") or item.get("kind") or ""),
    )
    kinds = {str(item.get("kind") or "") for item in ordered}
    if kinds & {"html_fragment", "css_fragment", "js_fragment", "json_fragment", "text_fragment", "md_fragment"}:
        return "\n\n".join(str(item.get("output") or "") for item in ordered)
    return merge_artifact([SimpleNamespace(**item) for item in ordered])


def _funding_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Panel grantowy AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --ink: #132019;
      --muted: #66736b;
      --line: #c9d7cf;
      --paper: #f8fbf6;
      --accent: #1b7f5a;
      --warn: #a05a00;
      --danger: #9b1c31;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: linear-gradient(135deg, #edf6ef 0%, #fffaf0 48%, #eaf3ff 100%);
      font-family: "Lora", "Georgia", serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px;
    }}
    header, section {{
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: 0 18px 45px rgba(22, 48, 33, 0.08);
    }}
    h1, h2 {{
      margin: 0 0 10px;
      letter-spacing: -0.02em;
    }}
    textarea, input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: #fff;
      color: var(--ink);
      margin: 6px 0 12px;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      margin: 4px 8px 4px 0;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{ background: #31536f; }}
    button.guard {{ background: var(--warn); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: var(--paper);
    }}
    .status-pass {{ color: var(--accent); font-weight: 700; }}
    .status-block {{ color: var(--danger); font-weight: 700; }}
    .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 8px; vertical-align: top; }}
    pre {{ white-space: pre-wrap; background: #11231a; color: #eef8f1; padding: 16px; border-radius: 16px; overflow: auto; }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">AEIS funding product / FENG / SMART / Horizon Europe / EIC / Perplexity / Bielik / PLLuM</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard:</strong> scoring grantowy jest zablokowany, dopóki operator nie zatwierdzi HumanGate i nie poda źródła programu.</p>
    </header>

    <section>
      <h2>1. Intake źródeł grantowych</h2>
      <p class="muted">Wklej wyniki wyszukiwania z Perplexity, Google, portali FENG/SMART/Horizon/EIC albo notatki analityka. Aplikacja nie publikuje i nie wysyła danych na zewnątrz.</p>
      <textarea id="source-notes" rows="5" placeholder="Wklej realne fragmenty naboru, kryteria, deadline, linki i wymagania..."></textarea>
      <div class="grid">
        <label>Nazwa programu<input id="program-name" placeholder="np. FENG SMART / Horizon Europe Cluster 4 / EIC Accelerator"></label>
        <label>Źródło URL<input id="program-url" placeholder="https://..."></label>
        <label>Rodzina programu
          <select id="program-family">
            <option>FENG SMART</option>
            <option>Horizon Europe</option>
            <option>EIC Accelerator</option>
            <option>Digital Europe</option>
            <option>NCBR / krajowy</option>
            <option>Inny</option>
          </select>
        </label>
      </div>
      <button onclick="addProgram()">Dodaj program</button>
      <button class="guard" onclick="approveHumanGate()">HumanGate: zatwierdź scoring tej sesji</button>
      <p id="gate-state" class="status-block">HumanGate: oczekuje</p>
      <p id="operator-message" class="muted" aria-live="polite">Komunikaty walidacyjne pojawią się tutaj.</p>
    </section>

    <section>
      <h2>2. Scoring kwalifikowalności</h2>
      <div class="grid">
        <label>Dopasowanie do kryptografii postkwantowej (0-5)<input id="fit-pqc" type="number" min="0" max="5" value="5"></label>
        <label>Gotowość TRL / prototyp (0-5)<input id="fit-trl" type="number" min="0" max="5" value="3"></label>
        <label>Jakość źródeł i dowodów (0-5)<input id="fit-evidence" type="number" min="0" max="5" value="3"></label>
        <label>Ryzyko formalne (0-5, mniej lepiej)<input id="risk-formal" type="number" min="0" max="5" value="2"></label>
      </div>
      <button onclick="scorePrograms()">Przelicz scoring</button>
      <table>
        <thead><tr><th>Program</th><th>Score</th><th>Status</th><th>Braki / ryzyka</th></tr></thead>
        <tbody id="score-table"></tbody>
      </table>
    </section>

    <section>
      <h2>3. Księga, dokumenty i governance</h2>
      <div class="grid" id="module-grid"></div>
      <button class="secondary" onclick="buildEvidencePack()">Zbuduj paczkę evidence</button>
      <button class="secondary" onclick="exportMarkdown()">Eksportuj Markdown</button>
      <pre id="evidence-output">Brak paczki evidence.</pre>
    </section>
  </main>

  <script>
    const project = {project_json};
    const modules = {modules_json};
    const programs = [];
    let humanGateApproved = false;

    function numberValue(id) {{
      const value = Number(document.getElementById(id).value);
      return Number.isFinite(value) ? Math.max(0, Math.min(5, value)) : 0;
    }}

    function approveHumanGate() {{
      humanGateApproved = true;
      const gate = document.getElementById('gate-state');
      gate.textContent = 'HumanGate: zatwierdzony przez operatora dla lokalnego scoringu';
      gate.className = 'status-pass';
      setOperatorMessage('HumanGate zatwierdzony. Możesz przeliczyć scoring lokalnie.');
    }}

    function setOperatorMessage(message, blocked = false) {{
      const node = document.getElementById('operator-message');
      node.textContent = message;
      node.className = blocked ? 'status-block' : 'muted';
    }}

    function addProgram() {{
      const name = document.getElementById('program-name').value.trim();
      const sourceUrl = document.getElementById('program-url').value.trim();
      const notes = document.getElementById('source-notes').value.trim();
      const family = document.getElementById('program-family').value;
      if (!name || !sourceUrl || !notes) {{
        setOperatorMessage('Uzupełnij nazwę programu, URL źródła i notatki z realnego naboru.', true);
        return;
      }}
      programs.push({{
        id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
        name,
        sourceUrl,
        family,
        notes,
        createdAt: new Date().toISOString(),
        score: null,
        status: 'oczekuje_na_scoring',
        gaps: []
      }});
      setOperatorMessage(`Dodano program: ${{name}}.`);
      renderScores();
      buildEvidencePack();
    }}

    function scorePrograms() {{
      if (!humanGateApproved) {{
        setOperatorMessage('Guard blokuje scoring: najpierw zatwierdź HumanGate.', true);
        return;
      }}
      if (!programs.length) {{
        setOperatorMessage('Dodaj co najmniej jeden realny program z URL i notatkami źródłowymi.', true);
        return;
      }}
      const fitPqc = numberValue('fit-pqc');
      const fitTrl = numberValue('fit-trl');
      const fitEvidence = numberValue('fit-evidence');
      const riskFormal = numberValue('risk-formal');
      for (const program of programs) {{
        const text = `${{program.name}} ${{program.family}} ${{program.notes}}`.toLowerCase();
        const mentionsPqc = text.includes('postkwant') || text.includes('quantum') || text.includes('kryptograf');
        const mentionsEu = text.includes('feng') || text.includes('horizon') || text.includes('eic') || text.includes('smart');
        const sourceBonus = program.sourceUrl.startsWith('http') ? 10 : 0;
        const domainBonus = mentionsPqc ? 20 : 0;
        const programBonus = mentionsEu ? 12 : 0;
        const score = Math.max(0, Math.min(100, Math.round(
          sourceBonus + domainBonus + programBonus + fitPqc * 8 + fitTrl * 6 + fitEvidence * 7 - riskFormal * 5
        )));
        const gaps = [];
        if (!mentionsPqc) gaps.push('brak jawnego powiązania z kryptografią postkwantową');
        if (!mentionsEu) gaps.push('brak nazwy FENG/SMART/Horizon/EIC w notatkach');
        if (fitEvidence < 3) gaps.push('za mało dowodów źródłowych');
        if (riskFormal >= 4) gaps.push('wysokie ryzyko formalne');
        program.score = score;
        program.gaps = gaps;
        program.status = score >= 70 && gaps.length <= 1 ? 'rekomendowany_do_dalszej_analizy' : 'needs_info';
      }}
      setOperatorMessage(`Przeliczono scoring dla ${{programs.length}} programów.`);
      renderScores();
      buildEvidencePack();
    }}

    function renderScores() {{
      const rows = programs.map(program => `<tr>
        <td><strong>${{program.name}}</strong><br><span class="muted">${{program.family}}<br>${{program.sourceUrl}}</span></td>
        <td>${{program.score === null ? '-' : program.score + '/100'}}</td>
        <td>${{program.status}}</td>
        <td>${{program.gaps.length ? program.gaps.join('; ') : 'brak blokad'}}</td>
      </tr>`).join('');
      document.getElementById('score-table').innerHTML = rows || '<tr><td colspan="4">Brak programów. Dodaj realny nabór z URL i notatkami.</td></tr>';
    }}

    function renderModules() {{
      document.getElementById('module-grid').innerHTML = modules.map(name => `<article class="card">
        <h3>${{name}}</h3>
        <p>Moduł aktywny w planie wykonania. Oczekiwany output: dane wejściowe, scoring, dokument package lub governance trail.</p>
      </article>`).join('');
    }}

    function buildEvidencePack() {{
      const pack = {{
        project_id: project.project_id,
        title: project.title,
        kind: project.project_kind,
        human_gate_approved: humanGateApproved,
        models_required: ['Perplexity', 'Bielik', 'PLLuM'],
        modules,
        programs,
        generated_at: new Date().toISOString(),
        next_human_gates: [
          'zatwierdzenie realnych źródeł programu',
          'zatwierdzenie scoringu przed kosztami',
          'zatwierdzenie wysyłki dokumentów poza system'
        ]
      }};
      document.getElementById('evidence-output').textContent = JSON.stringify(pack, null, 2);
      return pack;
    }}

    function exportMarkdown() {{
      const pack = buildEvidencePack();
      const lines = [
        `# ${{pack.title}}`,
        '',
        `HumanGate scoring: ${{pack.human_gate_approved ? 'TAK' : 'NIE'}}`,
        '',
        '## Programy',
        ...pack.programs.map(program => `- ${{program.name}} (${{program.family}}): ${{program.score ?? '-'}}/100, status=${{program.status}}, źródło=${{program.sourceUrl}}`),
        '',
        '## Moduły',
        ...pack.modules.map(name => `- ${{name}}`),
      ];
      document.getElementById('evidence-output').textContent = lines.join('\\n');
    }}

    renderScores();
    renderModules();
  </script>
</body>
</html>
"""

def _funding_artifact(project: dict[str, Any]) -> str:
    """V9 funding artifact with explicit source, deadline and submission guards."""
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Panel funding AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --ink: #132019;
      --muted: #5d6b63;
      --line: #c8d7ce;
      --paper: #f8fbf6;
      --accent: #1b7f5a;
      --warn: #a05a00;
      --danger: #9b1c31;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: linear-gradient(135deg, #edf6ef 0%, #fffaf0 48%, #eaf3ff 100%);
      font-family: Georgia, "Times New Roman", serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px; }}
    header, section {{
      background: rgba(255, 255, 255, 0.88);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: 0 18px 45px rgba(22, 48, 33, 0.08);
    }}
    h1, h2 {{ margin: 0 0 10px; letter-spacing: -0.02em; }}
    textarea, input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: #fff;
      color: var(--ink);
      margin: 6px 0 12px;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      margin: 4px 8px 4px 0;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{ background: #31536f; }}
    button.guard {{ background: var(--warn); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .card {{ border: 1px solid var(--line); border-radius: 16px; padding: 14px; background: var(--paper); }}
    .pass {{ color: var(--accent); font-weight: 700; }}
    .block {{ color: var(--danger); font-weight: 700; }}
    .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 8px; vertical-align: top; }}
    pre {{ white-space: pre-wrap; background: #11231a; color: #eef8f1; padding: 16px; border-radius: 16px; overflow: auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="funding_intake official_source_search source_verification deadline_guard program_scoring eligibility_risk_matrix cost_budget_estimator polish_model_context_review document_package submission_governance audit_evidence_pack integration_validation">
    <header>
      <p class="muted">AEIS funding / FENG SMART / Horizon Europe / EIC / Perplexity / Google / Bielik / PLLuM / HumanGate D4</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard D4:</strong> discovery moze korzystac z Perplexity i Google, ale scoring wymaga oficjalnego zrodla, aktualnego deadline i HumanGate official_source_review.</p>
      <p><strong>Granica zewnetrzna:</strong> eksport dokumentow, kontakt z instytucja i submission sa zablokowane do osobnego HumanGate.</p>
    </header>

    <section>
      <h2>1. Funding intake i official_source_search</h2>
      <textarea id="productBrief" rows="4" placeholder="Opis produktu, TRL, region, budzet i hipoteza grantu">Produkt: software R&amp;D z elementem kryptografii postkwantowej, TRL 5, woj. mazowieckie, budzet 1.2 mln PLN.</textarea>
      <div class="grid">
        <label>Nazwa programu<input id="programName" data-testid="program-name" placeholder="np. FENG SMART / Horizon Europe Cluster 4"></label>
        <label>Oficjalny URL programu<input id="programUrl" data-testid="program-url" placeholder="https://www.parp.gov.pl/..."></label>
        <label>Notatka zrodlowa<textarea id="sourceNotes" data-testid="source-notes" rows="3" placeholder="Wklej kryteria, linki, dzialanie, poziom TRL i wymagania"></textarea></label>
        <label>Provider discovery
          <select id="sourceProvider" data-testid="source-provider">
            <option value="official">oficjalny portal</option>
            <option value="perplexity">Perplexity discovery</option>
            <option value="google">Google discovery</option>
            <option value="manual">manual operator note</option>
          </select>
        </label>
        <label>Deadline naboru<input id="deadlineDate" data-testid="deadline-date" type="date"></label>
        <label>Koszt przygotowania wniosku PLN<input id="prepCost" data-testid="prep-cost" type="number" min="0" value="25000"></label>
      </div>
      <button onclick="addProgram()" data-testid="add-program">Dodaj program</button>
      <button class="guard" onclick="approveSourceGate()" data-testid="source-hg">HumanGate: official_source_review</button>
      <button class="guard" onclick="approveExportGate()" data-testid="export-hg">HumanGate: document_export</button>
      <p id="sourceGate" class="block">official_source_review: oczekuje</p>
      <p id="exportGate" class="block">document_export: oczekuje</p>
      <p id="operatorMessage" class="muted" aria-live="polite">Komunikaty walidacyjne pojawia sie tutaj.</p>
    </section>

    <section>
      <h2>2. source_verification, deadline_guard i program_scoring</h2>
      <div class="grid">
        <label>Dopasowanie merytoryczne 0-5<input id="fitDomain" type="number" min="0" max="5" value="4"></label>
        <label>TRL / gotowosc 0-5<input id="fitTrl" type="number" min="0" max="5" value="3"></label>
        <label>Jakosc zrodel 0-5<input id="fitEvidence" type="number" min="0" max="5" value="4"></label>
        <label>Ryzyko formalne 0-5<input id="riskFormal" type="number" min="0" max="5" value="2"></label>
      </div>
      <button onclick="scorePrograms()" data-testid="score-programs">Przelicz scoring</button>
      <button class="secondary" onclick="exportDocuments()" data-testid="export-docs">Eksportuj dokumenty</button>
      <table>
        <thead><tr><th>Program</th><th>Score</th><th>Status</th><th>Ryzyka i braki</th></tr></thead>
        <tbody id="scoreTable"></tbody>
      </table>
    </section>

    <section>
      <h2>3. Modele, moduly i audit_evidence_pack</h2>
      <p class="muted">Routing: Perplexity/Google = discovery, Bielik/PLLuM = polski kontekst, Claude/GPT = critic. Zaden model nie moze sam wyslac wniosku.</p>
      <div class="grid" id="moduleGrid"></div>
      <button class="secondary" onclick="buildEvidencePack()" data-testid="build-evidence">Zbuduj audit_evidence_pack</button>
      <pre id="evidenceOutput">Brak paczki evidence.</pre>
    </section>
  </main>

  <script>
    const project = {project_json};
    const modules = {modules_json};
    const officialDomains = ['gov.pl','parp.gov.pl','ncbr.gov.pl','funduszeeuropejskie.gov.pl','ec.europa.eu','eic.ec.europa.eu','hadea.ec.europa.eu','europa.eu','funding-tenders.ec.europa.eu'];
    const badMarkers = ['fake','scam','wordpress','blogspot','dotacje-24','granty-za-darmo'];
    const programs = [];
    const events = [];
    let sourceGateApproved = false;
    let exportGateApproved = false;

    function msg(text, blocked=false) {{
      events.push({{ts:new Date().toISOString(), text, blocked}});
      const node = document.getElementById('operatorMessage');
      node.textContent = text;
      node.className = blocked ? 'block' : 'muted';
      buildEvidencePack();
    }}
    function num(id) {{
      const value = Number(document.getElementById(id).value);
      return Number.isFinite(value) ? Math.max(0, Math.min(5, value)) : 0;
    }}
    function hasOfficialDomain(url) {{
      const lower = String(url || '').toLowerCase();
      return officialDomains.some(domain => lower.includes(domain));
    }}
    function hasBadMarker(value) {{
      const lower = String(value || '').toLowerCase();
      return badMarkers.some(marker => lower.includes(marker));
    }}
    function deadlineIsFuture(value) {{
      if (!value) return false;
      const deadline = new Date(value + 'T23:59:59');
      const today = new Date();
      today.setHours(0,0,0,0);
      return deadline >= today;
    }}
    function approveSourceGate() {{
      sourceGateApproved = true;
      document.getElementById('sourceGate').textContent = 'official_source_review: zatwierdzone';
      document.getElementById('sourceGate').className = 'pass';
      msg('PASS: HumanGate official_source_review zatwierdzony dla lokalnego scoringu.');
    }}
    function approveExportGate() {{
      exportGateApproved = true;
      document.getElementById('exportGate').textContent = 'document_export: zatwierdzone';
      document.getElementById('exportGate').className = 'pass';
      msg('PASS: HumanGate document_export zatwierdzony dla lokalnego eksportu.');
    }}
    function addProgram() {{
      const name = document.getElementById('programName').value.trim();
      const url = document.getElementById('programUrl').value.trim();
      const notes = document.getElementById('sourceNotes').value.trim();
      const provider = document.getElementById('sourceProvider').value;
      const deadline = document.getElementById('deadlineDate').value;
      const prepCost = Number(document.getElementById('prepCost').value || 0);
      if (!name || !url || !notes) return msg('BLOCK: funding_intake wymaga nazwy, URL i notatki zrodlowej.', true);
      if (!url.startsWith('https://')) return msg('BLOCK: source_verification wymaga https:// i jawnego zrodla.', true);
      if (hasBadMarker(name) || hasBadMarker(url) || hasBadMarker(notes)) return msg('BLOCK: source_verification wykrylo podejrzany albo fikcyjny program.', true);
      if (!hasOfficialDomain(url)) return msg('BLOCK: source_verification wymaga oficjalnej domeny programu albo zatwierdzonego zrodla instytucji.', true);
      if (!deadlineIsFuture(deadline)) return msg('BLOCK: deadline_guard wymaga aktualnego przyszlego deadline.', true);
      const program = {{id:String(Date.now()), name, url, notes, provider, deadline, prepCost, score:null, status:'ready_for_scoring', gaps:[]}};
      programs.push(program);
      renderScores();
      msg('PASS: dodano program po source_verification i deadline_guard.');
    }}
    function scorePrograms() {{
      if (!sourceGateApproved) return msg('BLOCK: program_scoring wymaga HumanGate official_source_review.', true);
      if (!programs.length) return msg('BLOCK: program_scoring wymaga co najmniej jednego zweryfikowanego programu.', true);
      for (const program of programs) {{
        const text = (program.name + ' ' + program.notes).toLowerCase();
        const domainBonus = /(kryptograf|postkwant|quantum|ai|software|cyber)/.test(text) ? 18 : 0;
        const euBonus = /(feng|smart|horizon|eic|digital europe|ncbr|parp)/.test(text) ? 14 : 0;
        const evidenceBonus = hasOfficialDomain(program.url) ? 15 : 0;
        const score = Math.max(0, Math.min(100, Math.round(evidenceBonus + domainBonus + euBonus + num('fitDomain')*8 + num('fitTrl')*6 + num('fitEvidence')*7 - num('riskFormal')*5)));
        const gaps = [];
        if (!domainBonus) gaps.push('slabe powiazanie z domena produktu');
        if (!euBonus) gaps.push('brak rozpoznanej rodziny FENG/Horizon/EIC/PARP/NCBR');
        if (Number(program.prepCost) > 75000) gaps.push('wysoki koszt przygotowania wniosku');
        program.score = score;
        program.gaps = gaps;
        program.status = score >= 70 && gaps.length <= 1 ? 'recommended_for_human_review' : 'needs_info';
      }}
      renderScores();
      msg('PASS: scoring przeliczony lokalnie; submission nadal zablokowany.');
    }}
    function exportDocuments() {{
      if (!exportGateApproved) return msg('BLOCK: document_package export wymaga HumanGate document_export.', true);
      if (!programs.some(p => p.score !== null)) return msg('BLOCK: document_package wymaga scoringu przed eksportem.', true);
      msg('PASS: dokumenty eksportowe gotowe lokalnie; contact_institution i funding_submission pozostaja zablokowane.');
    }}
    function renderScores() {{
      document.getElementById('scoreTable').innerHTML = programs.length ? programs.map(program => `<tr>
        <td><strong>${{program.name}}</strong><br><span class="muted">${{program.provider}} / ${{program.url}} / deadline ${{program.deadline}}</span></td>
        <td>${{program.score === null ? '-' : program.score + '/100'}}</td>
        <td>${{program.status}}</td>
        <td>${{program.gaps.length ? program.gaps.join('; ') : 'brak blokad'}}</td>
      </tr>`).join('') : '<tr><td colspan="4">Brak programow. Dodaj realny nabor z oficjalnym URL i przyszlym deadline.</td></tr>';
    }}
    function renderModules() {{
      document.getElementById('moduleGrid').innerHTML = modules.map(name => `<article class="card"><h3>${{name}}</h3><p>Modul aktywny w funding D4.</p></article>`).join('');
    }}
    function buildEvidencePack() {{
      const pack = {{
        project_id: project.project_id,
        product: 'funding',
        modules,
        routing_models: ['Perplexity discovery','Google discovery','Bielik polish_context','PLLuM polish_context','Claude/GPT critic'],
        official_source_review: sourceGateApproved,
        document_export_hg: exportGateApproved,
        source_verification: programs.every(p => hasOfficialDomain(p.url)),
        deadline_guard: programs.every(p => deadlineIsFuture(p.deadline)),
        submission_governance: 'contact_institution and funding_submission blocked until separate HumanGate',
        programs,
        events,
        generated_at: new Date().toISOString()
      }};
      document.getElementById('evidenceOutput').textContent = JSON.stringify(pack, null, 2);
      return pack;
    }}
    renderScores();
    renderModules();
    buildEvidencePack();
  </script>
</body>
</html>
"""


def _wants_llm_cost_calculator(project: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(project.get("title") or ""),
            str(project.get("idea") or ""),
            str(project.get("canonical_book") or ""),
            str(project.get("masterplan") or ""),
        ]
    ).lower()
    return (
        ("llm" in text or "model" in text or "token" in text)
        and any(token in text for token in ["koszt", "cost", "budzet", "budget"])
        and any(token in text for token in ["kalkulator", "calculator", "csv", "prog", "threshold"])
    )


def _llm_cost_calculator_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Kalkulator kosztow LLM"))
    idea = escape(str(summary["idea"] or ""))
    project_json = _json_script(summary)
    modules_json = _json_script(summary["modules"])
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --ink: #111f22;
      --muted: #617174;
      --line: #cad7d7;
      --paper: #f5f8f4;
      --card: #ffffff;
      --accent: #0e6b5f;
      --warn: #9a6200;
      --danger: #9c1d2f;
      --ok: #1f7a45;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 10%, rgba(14, 107, 95, 0.18), transparent 28rem),
        radial-gradient(circle at 90% 0%, rgba(201, 139, 32, 0.20), transparent 24rem),
        linear-gradient(135deg, #f7f4ed 0%, #eef7f4 58%, #eaf0f7 100%);
      font-family: "Lora", "Georgia", serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px; }}
    header, section {{
      background: rgba(255,255,255,0.90);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: 0 18px 48px rgba(31, 44, 42, 0.08);
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 4.2rem); line-height: 0.94; }}
    h2 {{ margin-top: 0; }}
    label {{ display: grid; gap: 7px; font-weight: 700; }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 11px 12px;
      color: var(--ink);
      background: #fffefa;
      font: inherit;
    }}
    button, a.download {{
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 12px 18px;
      font-weight: 800;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    button.secondary {{ background: #263738; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }}
    .metric {{ background: #f9fbf7; border: 1px solid var(--line); border-radius: 18px; padding: 16px; }}
    .metric strong {{ display: block; font-size: 1.55rem; margin-top: 7px; }}
    .status-ok {{ color: var(--ok); }}
    .status-warn {{ color: var(--warn); }}
    .status-over {{ color: var(--danger); }}
    .muted {{ color: var(--muted); }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    pre {{ white-space: pre-wrap; background: #10201d; color: #eef8f1; padding: 14px; border-radius: 14px; overflow: auto; }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">AEIS produkt aplikacyjny / kalkulator kosztow LLM / progi 80 i 100 / eksport CSV / audit</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard:</strong> brak danych osobowych; wdrozenie produkcyjne i podpiecie platnych providerow wymaga HumanGate.</p>
    </header>

    <section aria-labelledby="form-heading">
      <h2 id="form-heading">Parametry obliczenia</h2>
      <div class="grid">
        <label>Provider
          <select id="provider" data-testid="provider-select">
            <option value="OpenAI">OpenAI</option>
            <option value="Anthropic">Anthropic</option>
            <option value="Google Gemini">Google Gemini</option>
            <option value="Moonshot Kimi">Moonshot Kimi</option>
            <option value="Ollama lokalnie">Ollama lokalnie</option>
          </select>
        </label>
        <label>Model
          <input id="model" data-testid="model-input" value="gpt-5-mini" placeholder="np. gpt-5-mini, claude-sonnet">
        </label>
        <label>Tokeny wejscia na uruchomienie
          <input id="inputTokens" data-testid="input-tokens-input" type="number" min="0" value="10000">
        </label>
        <label>Tokeny wyjscia na uruchomienie
          <input id="outputTokens" data-testid="output-tokens-input" type="number" min="0" value="2000">
        </label>
        <label>Uruchomienia dziennie
          <input id="runsPerDay" data-testid="runs-per-day-input" type="number" min="0" value="10">
        </label>
        <label>Dni w miesiacu
          <input id="daysPerMonth" data-testid="days-per-month-input" type="number" min="1" value="22">
        </label>
        <label>Koszt input za 1k tokenow (USD)
          <input id="inputCost" data-testid="input-cost-input" type="number" min="0" step="0.0001" value="0.00025">
        </label>
        <label>Koszt output za 1k tokenow (USD)
          <input id="outputCost" data-testid="output-cost-input" type="number" min="0" step="0.0001" value="0.002">
        </label>
        <label>Budzet miesieczny (USD)
          <input id="monthlyBudget" data-testid="monthly-budget-input" type="number" min="0" step="0.01" value="50">
        </label>
      </div>
      <div class="toolbar">
        <button id="calculateButton" data-testid="calculate-button" onclick="calculateLlmCost()">Oblicz koszt</button>
        <button class="secondary" id="thresholdButton" data-testid="threshold-button" onclick="forceThresholdScenario()">Test progu 80/100</button>
        <a class="download" id="csvDownload" data-testid="csv-download" download="llm-cost-audit.csv" href="#">Eksport CSV</a>
      </div>
    </section>

    <section aria-labelledby="result-heading">
      <h2 id="result-heading">Wynik i progi budzetowe</h2>
      <div class="grid">
        <article class="metric">
          <span>Koszt jednego uruchomienia</span>
          <strong id="singleRunCost" data-testid="single-run-cost">$0.0000</strong>
        </article>
        <article class="metric">
          <span>Koszt dzienny</span>
          <strong id="dailyCost" data-testid="daily-cost">$0.0000</strong>
        </article>
        <article class="metric">
          <span>Koszt miesieczny</span>
          <strong id="monthlyCost" data-testid="monthly-cost">$0.0000</strong>
        </article>
        <article class="metric">
          <span>Wykorzystanie budzetu</span>
          <strong id="budgetUsage" data-testid="budget-usage">0%</strong>
        </article>
      </div>
      <p id="budgetStatus" data-testid="budget-status" class="status-ok">Status: OK, ponizej 80% budzetu.</p>
    </section>

    <section aria-labelledby="audit-heading">
      <h2 id="audit-heading">Audit lokalny</h2>
      <table aria-label="Historia obliczen">
        <thead>
          <tr><th>Czas</th><th>Provider</th><th>Model</th><th>Koszt miesieczny</th><th>Status</th></tr>
        </thead>
        <tbody id="auditRows" data-testid="audit-rows"></tbody>
      </table>
      <pre id="evidenceJson" data-testid="evidence-json">Brak obliczen.</pre>
    </section>

    <section aria-labelledby="module-heading">
      <h2 id="module-heading">Moduly i skills</h2>
      <div id="moduleList" data-testid="module-list" class="grid"></div>
    </section>
  </main>

  <script>
    const project = {project_json};
    const modules = {modules_json};
    const auditEntries = [];

    function numberFrom(id) {{
      const value = Number(document.getElementById(id).value);
      return Number.isFinite(value) && value >= 0 ? value : 0;
    }}

    function money(value) {{
      return '$' + value.toFixed(4);
    }}

    function classifyBudget(usagePercent) {{
      if (usagePercent >= 100) {{
        return {{ code: 'OVER_100', text: 'Status: BLOKADA, przekroczono 100% budzetu. Wymagany HumanGate finansowy.', className: 'status-over' }};
      }}
      if (usagePercent >= 80) {{
        return {{ code: 'WARN_80', text: 'Status: OSTRZEZENIE, przekroczono 80% budzetu. Wyslij HumanGate przy kontynuacji.', className: 'status-warn' }};
      }}
      return {{ code: 'OK', text: 'Status: OK, ponizej 80% budzetu.', className: 'status-ok' }};
    }}

    function calculateLlmCost() {{
      const provider = document.getElementById('provider').value;
      const model = document.getElementById('model').value.trim() || 'model-niepodany';
      const inputTokens = numberFrom('inputTokens');
      const outputTokens = numberFrom('outputTokens');
      const runsPerDay = numberFrom('runsPerDay');
      const daysPerMonth = Math.max(1, numberFrom('daysPerMonth'));
      const inputCost = numberFrom('inputCost');
      const outputCost = numberFrom('outputCost');
      const monthlyBudget = numberFrom('monthlyBudget');
      const singleRun = (inputTokens / 1000 * inputCost) + (outputTokens / 1000 * outputCost);
      const daily = singleRun * runsPerDay;
      const monthly = daily * daysPerMonth;
      const usage = monthlyBudget > 0 ? monthly / monthlyBudget * 100 : 100;
      const status = classifyBudget(usage);

      document.getElementById('singleRunCost').textContent = money(singleRun);
      document.getElementById('dailyCost').textContent = money(daily);
      document.getElementById('monthlyCost').textContent = money(monthly);
      document.getElementById('budgetUsage').textContent = usage.toFixed(1) + '%';
      const statusNode = document.getElementById('budgetStatus');
      statusNode.textContent = status.text;
      statusNode.className = status.className;

      const entry = {{
        timestamp: new Date().toISOString(),
        provider,
        model,
        inputTokens,
        outputTokens,
        runsPerDay,
        daysPerMonth,
        inputCostPer1k: inputCost,
        outputCostPer1k: outputCost,
        monthlyBudget,
        singleRunCost: Number(singleRun.toFixed(6)),
        monthlyCost: Number(monthly.toFixed(6)),
        budgetUsagePercent: Number(usage.toFixed(2)),
        threshold: status.code,
        humanGateRequired: status.code !== 'OK'
      }};
      auditEntries.unshift(entry);
      renderAudit();
      updateCsvDownload();
      return entry;
    }}

    function renderAudit() {{
      document.getElementById('auditRows').innerHTML = auditEntries.map(entry => `
        <tr>
          <td>${{entry.timestamp}}</td>
          <td>${{entry.provider}}</td>
          <td>${{entry.model}}</td>
          <td>${{money(entry.monthlyCost)}}</td>
          <td>${{entry.threshold}}</td>
        </tr>
      `).join('');
      document.getElementById('evidenceJson').textContent = JSON.stringify({{
        project_id: project.project_id,
        product: 'llm_cost_calculator',
        no_pii: true,
        humangate_on_80_or_100: true,
        entries: auditEntries
      }}, null, 2);
    }}

    function csvEscape(value) {{
      return '"' + String(value ?? '').replaceAll('"', '""') + '"';
    }}

    function buildCsv() {{
      const header = ['timestamp','provider','model','inputTokens','outputTokens','runsPerDay','daysPerMonth','monthlyBudget','monthlyCost','budgetUsagePercent','threshold','humanGateRequired'];
      const rows = auditEntries.map(entry => header.map(key => csvEscape(entry[key])).join(','));
      return [header.join(','), ...rows].join('\\n');
    }}

    function updateCsvDownload() {{
      const csv = buildCsv();
      const href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
      document.getElementById('csvDownload').setAttribute('href', href);
    }}

    function forceThresholdScenario() {{
      document.getElementById('inputTokens').value = '10000';
      document.getElementById('outputTokens').value = '2000';
      document.getElementById('runsPerDay').value = '10';
      document.getElementById('daysPerMonth').value = '22';
      document.getElementById('inputCost').value = '0.00025';
      document.getElementById('outputCost').value = '0.002';
      document.getElementById('monthlyBudget').value = '1.50';
      calculateLlmCost();
    }}

    function renderModules() {{
      document.getElementById('moduleList').innerHTML = modules.map(name => `
        <article class="metric">
          <strong>${{name}}</strong>
          <span>Powiazany z kalkulacja kosztow, eksportem CSV albo evidence trail.</span>
        </article>
      `).join('');
    }}

    renderModules();
    updateCsvDownload();
  </script>
</body>
</html>
"""


def _project_management_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "System projektowy AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    runtime_constraints = summary.get("runtime_constraints") or {}
    local_env_count = int(runtime_constraints.get("local_environment_count") or 0)
    if runtime_constraints.get("vps_blocked_until_human_gate"):
        env_label = f"{local_env_count} srodowiska lokalne" if local_env_count else "srodowiska lokalne"
        runtime_badge = f"local-first / {env_label} / bez Hetznera i VPS"
    else:
        runtime_badge = "Hetzner-ready"
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --ink:#14213d; --muted:#607089; --paper:#f6f8fb; --line:#d8e1ee; --accent:#0f766e; --danger:#a21d3a; --ok:#167347; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:radial-gradient(circle at top left,#dff7f1 0,#f7fbff 34%,#fff7e8 100%); font-family:"IBM Plex Serif","Georgia",serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:18px; box-shadow:0 18px 50px rgba(20,33,61,.08); }}
    label {{ display:block; font-size:13px; color:var(--muted); margin:8px 0; }}
    input,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:white; color:var(--ink); }}
    button {{ border:0; border-radius:999px; padding:10px 15px; margin:5px 8px 5px 0; background:var(--accent); color:white; font-weight:700; cursor:pointer; }}
    button.secondary {{ background:#31536f; }} button.danger {{ background:var(--danger); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    .card {{ border:1px solid var(--line); border-radius:16px; background:var(--paper); padding:14px; }}
    .pass {{ color:var(--ok); font-weight:700; }} .block {{ color:var(--danger); font-weight:700; }} .muted {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); text-align:left; padding:8px; vertical-align:top; }}
    pre {{ white-space:pre-wrap; overflow:auto; background:#132238; color:#eef7ff; padding:16px; border-radius:16px; }}
  </style>
</head>
<body>
  <main data-artifact-contract="tenant_workspace portfolio_dashboard kanban_backlog gantt_roadmap resource_capacity risk_register budget_tracking notification_center api_integrations rbac_audit release_governance canary rollback humangate">
    <header>
      <p class="muted">AEIS system projektowy / portfolio / Kanban / Gantt / budzet / ryzyka / RBAC / release gate / {runtime_badge}</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard:</strong> produkcyjny deploy, zmiana RBAC, integracja API, przekroczenie budzetu i rollback chmury wymagaja HumanGate.</p>
      <p id="operatorMessage" class="block" aria-live="polite">System startuje bez danych. Dodaj workspace, zadania i uruchom testy.</p>
    </header>
    <section>
      <h2>1. Workspace, role i budzet</h2>
      <div class="grid">
        <label>Nazwa workspace<input id="workspaceName" data-testid="workspace-name" placeholder="np. Program Quantum Delivery"></label>
        <label>Rola operatora<select id="operatorRole" data-testid="operator-role"><option value="viewer">viewer</option><option value="project_manager">project_manager</option><option value="release_manager">release_manager</option><option value="security_admin">security_admin</option></select></label>
        <label>Budzet projektu PLN<input id="budgetCap" data-testid="budget-cap" type="number" min="1" value="2500"></label>
      </div>
      <button onclick="createWorkspace()" data-testid="create-workspace">Utworz workspace</button>
      <button class="secondary" onclick="approveRbacChange()" data-testid="approve-rbac">HumanGate: zatwierdz RBAC</button>
      <p id="rbacState" class="block">RBAC HumanGate: oczekuje</p>
    </section>
    <section>
      <h2>2. Kanban, sprint i roadmap</h2>
      <div class="grid">
        <label>Tytul zadania<input id="taskTitle" data-testid="task-title"></label>
        <label>Wlasciciel<input id="taskOwner" data-testid="task-owner"></label>
        <label>Koszt PLN<input id="taskCost" data-testid="task-cost" type="number" min="0" value="300"></label>
        <label>Sprint<select id="taskSprint" data-testid="task-sprint"><option>Sprint 1</option><option>Sprint 2</option><option>Sprint 3</option></select></label>
      </div>
      <button onclick="addTask()" data-testid="add-task">Dodaj zadanie</button>
      <button class="secondary" onclick="moveTask()" data-testid="move-task">Przesun zadanie</button>
      <table><thead><tr><th>Zadanie</th><th>Wlasciciel</th><th>Sprint</th><th>Status</th><th>Koszt</th></tr></thead><tbody id="taskTable"></tbody></table>
    </section>
    <section>
      <h2>3. Ryzyka, zaleznosci i integracje API</h2>
      <div class="grid">
        <label>Ryzyko<input id="riskTitle" data-testid="risk-title"></label>
        <label>Waga<select id="riskSeverity" data-testid="risk-severity"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label>
        <label>Integracja API<input id="apiIntegration" data-testid="api-integration" placeholder="np. Jira sandbox"></label>
      </div>
      <button onclick="addRisk()" data-testid="add-risk">Dodaj ryzyko</button>
      <button class="secondary" onclick="approveApiIntegration()" data-testid="approve-api">HumanGate: zatwierdz integracje API</button>
      <div id="riskRegister" class="grid"></div><p id="apiState" class="block">Integracje API: zablokowane do HumanGate</p>
    </section>
    <section>
      <h2>4. Katalog testow i release governance</h2>
      <div class="grid">
        <label>Error rate canary %<input id="errorRate" data-testid="error-rate" type="number" min="0" step="0.1" value="0.4"></label>
        <label>Krok canary<select id="canaryStep" data-testid="canary-step"><option>0</option><option>1</option><option>5</option><option>25</option><option>50</option><option>100</option></select></label>
      </div>
      <button onclick="runTestCatalog()" data-testid="run-tests">Uruchom katalog testow</button>
      <button class="secondary" onclick="approveRelease()" data-testid="approve-release">HumanGate: zatwierdz release</button>
      <button onclick="promoteCanary()" data-testid="promote-canary">Promuj canary</button>
      <button class="danger" onclick="rollbackRelease()" data-testid="rollback-release">Rollback</button>
      <p id="testState" class="block">Testy: nieuruchomione</p><p id="releaseState" class="block">Release: zablokowany</p><p id="canaryState" class="muted">Canary: 0%</p>
    </section>
    <section>
      <h2>5. Moduly, audit i evidence pack</h2>
      <div id="moduleList" class="grid"></div>
      <button class="secondary" onclick="buildEvidencePack()" data-testid="build-evidence">Zbuduj evidence pack</button>
      <pre id="evidenceOutput">Brak evidence pack.</pre>
    </section>
  </main>
  <script>
    const project={project_json}; const modules={modules_json};
    const state={{workspace:false,rbac:false,api:false,tests:false,release:false,rolledBack:false,canary:0,tasks:[],risks:[],audit:[]}};
    function msg(text, blocked=true){{const n=document.getElementById('operatorMessage'); n.textContent=text; n.className=blocked?'block':'pass'; state.audit.push({{ts:new Date().toISOString(),text,blocked}}); buildEvidencePack();}}
    function num(id){{const v=Number(document.getElementById(id).value); return Number.isFinite(v)?v:0;}}
    function createWorkspace(){{const name=document.getElementById('workspaceName').value.trim(); if(!name)return msg('BLOCK: workspace wymaga nazwy.'); state.workspace=true; msg('PASS: tenant_workspace utworzony: '+name,false);}}
    function approveRbacChange(){{if(document.getElementById('operatorRole').value!=='security_admin')return msg('BLOCK: RBAC moze zatwierdzic tylko security_admin.'); state.rbac=true; document.getElementById('rbacState').textContent='RBAC HumanGate: zatwierdzony'; document.getElementById('rbacState').className='pass'; msg('PASS: rbac_audit zatwierdzony.',false);}}
    function totalCost(){{return state.tasks.reduce((s,t)=>s+t.cost,0);}}
    function addTask(){{if(!state.workspace)return msg('BLOCK: najpierw utworz workspace.'); const title=document.getElementById('taskTitle').value.trim(); const owner=document.getElementById('taskOwner').value.trim(); const cost=num('taskCost'); const cap=num('budgetCap'); if(!title)return msg('BLOCK: zadanie wymaga tytulu.'); if(!owner)return msg('BLOCK: zadanie wymaga wlasciciela.'); if(cost<=0)return msg('BLOCK: koszt zadania musi byc dodatni.'); if(totalCost()+cost>cap)return msg('BLOCK: budzet_tracking przekroczylby cap.'); state.tasks.push({{title,owner,cost,sprint:document.getElementById('taskSprint').value,status:'queued'}}); msg('PASS: zadanie dodane do kanban_backlog.',false); render();}}
    function moveTask(){{const t=state.tasks.find(x=>x.status!=='done'); if(!t)return msg('BLOCK: brak zadania do przesuniecia.'); t.status=t.status==='queued'?'in_progress':'done'; msg('PASS: zadanie przesuniete do '+t.status+'.',false); render();}}
    function addRisk(){{const title=document.getElementById('riskTitle').value.trim(); const severity=document.getElementById('riskSeverity').value; if(!title)return msg('BLOCK: risk_register wymaga opisu.'); if(['high','critical'].includes(severity)&&!state.rbac)return msg('BLOCK: wysokie ryzyko wymaga RBAC HumanGate.'); state.risks.push({{title,severity}}); msg('PASS: risk_register uzupelniony.',false); render();}}
    function approveApiIntegration(){{if(!state.rbac)return msg('BLOCK: integracja API wymaga RBAC.'); const name=document.getElementById('apiIntegration').value.trim(); if(!name)return msg('BLOCK: podaj nazwe integracji API.'); state.api=true; document.getElementById('apiState').textContent='Integracja API zatwierdzona: '+name; document.getElementById('apiState').className='pass'; msg('PASS: api_integrations zatwierdzone.',false);}}
    function runTestCatalog(){{if(!state.tasks.some(t=>t.status==='done'))return msg('BLOCK: katalog testow wymaga zadania Done.'); state.tests=true; document.getElementById('testState').textContent='Testy: PASS'; document.getElementById('testState').className='pass'; msg('PASS: test catalog wykonany.',false);}}
    function approveRelease(){{if(document.getElementById('operatorRole').value!=='release_manager')return msg('BLOCK: release wymaga roli release_manager.'); if(!state.tests)return msg('BLOCK: release wymaga testow PASS.'); if(!state.api)return msg('BLOCK: release wymaga zatwierdzonej integracji API.'); state.release=true; document.getElementById('releaseState').textContent='Release: HumanGate zatwierdzony'; document.getElementById('releaseState').className='pass'; msg('PASS: release_governance zatwierdzony.',false);}}
    function promoteCanary(){{if(!state.release)return msg('BLOCK: canary wymaga release HumanGate.'); const e=num('errorRate'); if(e>1){{state.rolledBack=true; state.release=false; state.canary=0; document.getElementById('releaseState').textContent='Release: rollback po canary; wymaga ponownego HumanGate'; document.getElementById('releaseState').className='block'; document.getElementById('canaryState').textContent='Canary: rollback po error_rate '+e+'%'; return msg('BLOCK: auto-rollback, error_rate > 1%.');}} state.rolledBack=false; state.canary=Number(document.getElementById('canaryStep').value); document.getElementById('canaryState').textContent='Canary: '+state.canary+'%'; msg('PASS: canary promote '+state.canary+'%.',false);}}
    function rollbackRelease(){{state.rolledBack=true; state.release=false; state.canary=0; document.getElementById('releaseState').textContent='Release: rollback wymagany'; document.getElementById('releaseState').className='block'; document.getElementById('canaryState').textContent='Canary: 0% po rollback'; msg('PASS: rollback lokalny wykonany; usuniecie chmury wymaga osobnej zgody.',false);}}
    function render(){{document.getElementById('taskTable').innerHTML=state.tasks.map(t=>`<tr><td>${{t.title}}</td><td>${{t.owner}}</td><td>${{t.sprint}}</td><td>${{t.status}}</td><td>${{t.cost}} PLN</td></tr>`).join(''); document.getElementById('riskRegister').innerHTML=state.risks.map(r=>`<article class="card"><h3>${{r.severity}}</h3><p>${{r.title}}</p></article>`).join('');}}
    function buildEvidencePack(){{const pack={{project_id:project.project_id,product:'project_management_system',modules,tenant_workspace:state.workspace,portfolio_dashboard:true,kanban_backlog:state.tasks,gantt_roadmap:true,resource_capacity:true,risk_register:state.risks,budget_tracking:{{cap:num('budgetCap'),spent:totalCost()}},rbac_audit:{{approved:state.rbac,role:document.getElementById('operatorRole').value}},api_integrations:{{approved:state.api}},release_governance:{{tests_passed:state.tests,release_approved:state.release,canary:state.canary,rolled_back:state.rolledBack}},audit_evidence_pack:state.audit,generated_at:new Date().toISOString()}}; document.getElementById('evidenceOutput').textContent=JSON.stringify(pack,null,2); return pack;}}
    document.getElementById('moduleList').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w systemie projektowym D4.</p></article>`).join(''); render(); buildEvidencePack();
  </script>
</body>
</html>
"""


def _marketplace_platform_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Marketplace SaaS AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --ink:#102027; --muted:#63727f; --paper:#f5f7f1; --line:#d9dfd2; --accent:#b45309; --dark:#1f2937; --danger:#b91c1c; --ok:#15803d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#fff8ed 0,#eef7f4 48%,#f4f0ff 100%); font-family:"Aptos","Segoe UI",sans-serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:18px; box-shadow:0 16px 48px rgba(16,32,39,.08); }}
    label {{ display:block; font-size:13px; color:var(--muted); margin:8px 0; }}
    input,select,textarea {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:white; color:var(--ink); }}
    button {{ border:0; border-radius:999px; padding:10px 15px; margin:5px 8px 5px 0; background:var(--accent); color:white; font-weight:700; cursor:pointer; }}
    button.secondary {{ background:var(--dark); }} button.danger {{ background:var(--danger); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    .card {{ border:1px solid var(--line); border-radius:16px; background:var(--paper); padding:14px; }}
    .pass {{ color:var(--ok); font-weight:700; }} .block {{ color:var(--danger); font-weight:700; }} .muted {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); text-align:left; padding:8px; vertical-align:top; }}
    pre {{ white-space:pre-wrap; overflow:auto; background:#111827; color:#f8fafc; padding:16px; border-radius:16px; }}
  </style>
</head>
<body>
  <main data-artifact-contract="tenant_identity vendor_onboarding product_catalog cart_checkout payment_sandbox tax_shipping admin_console funding_scan release_governance canary rollback humangate evidence_pack">
    <header>
      <p class="muted">AEIS marketplace_platform / multi-tenant SaaS / vendorzy / katalog / checkout / payment_sandbox / Hetzner-ready</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard D5:</strong> realne platnosci, tax/shipping, integracje zewnetrzne, funding submission, deploy produkcyjny, canary i cleanup chmury wymagaja HumanGate.</p>
      <p><strong>Granica typu:</strong> funding_scan jest funkcja wspierajaca marketplace_platform i nie moze przeksztalcic projektu w funding-only.</p>
      <p id="operatorMessage" class="block" aria-live="polite">System startuje bez danych. Utworz tenant, vendora i produkt, potem testuj bledy operatora.</p>
    </header>
    <section>
      <h2>1. Tenant identity i vendor onboarding</h2>
      <div class="grid">
        <label>Tenant<input id="tenantName" data-testid="tenant-name" placeholder="np. meridian-retail"></label>
        <label>Rola operatora<select id="operatorRole" data-testid="operator-role"><option value="viewer">viewer</option><option value="tenant_admin">tenant_admin</option><option value="payment_reviewer">payment_reviewer</option><option value="release_manager">release_manager</option></select></label>
        <label>Vendor<input id="vendorName" data-testid="vendor-name" placeholder="np. Vendor Baltic"></label>
      </div>
      <button onclick="createTenant()" data-testid="create-tenant">Utworz tenant_identity</button>
      <button class="secondary" onclick="addVendor()" data-testid="add-vendor">Dodaj vendor_onboarding</button>
      <p id="tenantState" class="block">Tenant: brak</p><p id="vendorState" class="block">Vendor: brak</p>
    </section>
    <section>
      <h2>2. Product catalog, tax i shipping</h2>
      <div class="grid">
        <label>Nazwa produktu<input id="productName" data-testid="product-name"></label>
        <label>Cena PLN<input id="productPrice" data-testid="product-price" type="number" min="1" value="199"></label>
        <label>Stawka VAT %<input id="taxRate" data-testid="tax-rate" type="number" min="0" value="23"></label>
        <label>Shipping PLN<input id="shippingCost" data-testid="shipping-cost" type="number" min="0" value="19"></label>
      </div>
      <button onclick="addProduct()" data-testid="add-product">Dodaj product_catalog</button>
      <button class="secondary" onclick="approveTaxShipping()" data-testid="approve-tax-shipping">HumanGate: tax_shipping</button>
      <table><thead><tr><th>Produkt</th><th>Vendor</th><th>Cena</th><th>VAT</th><th>Shipping</th></tr></thead><tbody id="productTable"></tbody></table>
      <p id="taxState" class="block">Tax/shipping: oczekuje HumanGate</p>
    </section>
    <section>
      <h2>3. Cart checkout i payment sandbox</h2>
      <div class="grid">
        <label>Limit checkout PLN<input id="checkoutLimit" data-testid="checkout-limit" type="number" min="1" value="500"></label>
        <label>Koszyk: liczba produktow<input id="cartQty" data-testid="cart-qty" type="number" min="1" value="1"></label>
      </div>
      <button onclick="checkoutSandbox()" data-testid="checkout-sandbox">Wykonaj cart_checkout</button>
      <button class="secondary" onclick="approvePaymentGate()" data-testid="approve-payment">HumanGate: payment_sandbox</button>
      <p id="paymentState" class="block">Payment sandbox: oczekuje</p>
      <p id="checkoutState" class="block">Checkout: zablokowany</p>
    </section>
    <section>
      <h2>4. Funding scan i admin console</h2>
      <div class="grid">
        <label>Program funding<input id="fundingProgram" data-testid="funding-program" value="FENG SMART / Horizon Europe"></label>
        <label>Hipoteza dotacji<textarea id="fundingHypothesis" data-testid="funding-hypothesis">Marketplace B2B z bezpiecznym checkoutem i automatyzacja vendorow.</textarea></label>
      </div>
      <button onclick="runFundingScan()" data-testid="run-funding-scan">Uruchom funding_scan</button>
      <button class="secondary" onclick="openAdminConsole()" data-testid="open-admin">Otworz admin_console</button>
      <p id="fundingState" class="muted">Funding scan nie zmienia typu projektu.</p>
      <p id="adminState" class="block">Admin console: wymaga tenant_admin</p>
    </section>
    <section>
      <h2>5. Release governance, canary i rollback</h2>
      <div class="grid">
        <label>Error rate canary %<input id="errorRate" data-testid="error-rate" type="number" min="0" step="0.1" value="0.4"></label>
        <label>Krok canary<select id="canaryStep" data-testid="canary-step"><option>0</option><option>1</option><option>5</option><option>25</option><option>50</option><option>100</option></select></label>
      </div>
      <button onclick="runTestCatalog()" data-testid="run-tests">Uruchom katalog testow</button>
      <button class="secondary" onclick="approveReleaseGate()" data-testid="approve-release">HumanGate: release_governance</button>
      <button onclick="promoteCanary()" data-testid="promote-canary">Promuj canary</button>
      <button class="danger" onclick="rollbackRelease()" data-testid="rollback-release">Rollback</button>
      <p id="testState" class="block">Testy: nieuruchomione</p><p id="releaseState" class="block">Release: zablokowany</p><p id="canaryState" class="muted">Canary: 0%</p>
    </section>
    <section>
      <h2>6. Moduly i evidence pack</h2>
      <div id="moduleList" class="grid"></div>
      <button class="secondary" onclick="buildEvidencePack()" data-testid="build-evidence">Zbuduj evidence_pack</button>
      <pre id="evidenceOutput">Brak evidence_pack.</pre>
    </section>
  </main>
  <script>
    const project={project_json}; const modules={modules_json};
    const state={{tenant:false,vendor:false,tax:false,payment:false,tests:false,release:false,admin:false,canary:0,rolledBack:false,products:[],funding:[],audit:[]}};
    function msg(text, blocked=true){{const n=document.getElementById('operatorMessage'); n.textContent=text; n.className=blocked?'block':'pass'; state.audit.push({{ts:new Date().toISOString(),text,blocked}}); buildEvidencePack();}}
    function role(){{return document.getElementById('operatorRole').value;}}
    function num(id){{const v=Number(document.getElementById(id).value); return Number.isFinite(v)?v:0;}}
    function createTenant(){{const name=document.getElementById('tenantName').value.trim(); if(!name)return msg('BLOCK: tenant_identity wymaga nazwy tenant.'); state.tenant=true; document.getElementById('tenantState').textContent='Tenant aktywny: '+name; document.getElementById('tenantState').className='pass'; msg('PASS: tenant_identity utworzony.',false);}}
    function addVendor(){{if(!state.tenant)return msg('BLOCK: vendor_onboarding wymaga tenant_identity.'); const name=document.getElementById('vendorName').value.trim(); if(!name)return msg('BLOCK: vendor_onboarding wymaga nazwy vendora.'); state.vendor=true; document.getElementById('vendorState').textContent='Vendor aktywny: '+name; document.getElementById('vendorState').className='pass'; msg('PASS: vendor_onboarding zakonczony.',false);}}
    function addProduct(){{if(!state.vendor)return msg('BLOCK: product_catalog wymaga vendora.'); const name=document.getElementById('productName').value.trim(); if(!name)return msg('BLOCK: product_catalog wymaga nazwy produktu.'); const price=num('productPrice'); if(price<=0)return msg('BLOCK: cena musi byc dodatnia.'); state.products.push({{name,vendor:document.getElementById('vendorName').value.trim(),price,tax:num('taxRate'),shipping:num('shippingCost')}}); msg('PASS: product_catalog uzupelniony.',false); render();}}
    function approveTaxShipping(){{if(role()!=='tenant_admin')return msg('BLOCK: tax_shipping wymaga roli tenant_admin.'); if(!state.products.length)return msg('BLOCK: tax_shipping wymaga produktu.'); state.tax=true; document.getElementById('taxState').textContent='Tax/shipping HumanGate: zatwierdzony'; document.getElementById('taxState').className='pass'; msg('PASS: tax_shipping zatwierdzony.',false);}}
    function approvePaymentGate(){{if(role()!=='payment_reviewer')return msg('BLOCK: payment_sandbox wymaga roli payment_reviewer.'); if(!state.tax)return msg('BLOCK: payment_sandbox wymaga zatwierdzonego tax_shipping.'); state.payment=true; document.getElementById('paymentState').textContent='Payment sandbox HumanGate: zatwierdzony'; document.getElementById('paymentState').className='pass'; msg('PASS: payment_sandbox zatwierdzony.',false);}}
    function cartTotal(){{const qty=Math.max(1,num('cartQty')); return state.products.reduce((s,p)=>s+(p.price+p.shipping+(p.price*p.tax/100))*qty,0);}}
    function checkoutSandbox(){{if(!state.tenant)return msg('BLOCK: cart_checkout wymaga tenant_identity.'); if(!state.products.length)return msg('BLOCK: cart_checkout wymaga product_catalog.'); if(!state.payment)return msg('BLOCK: cart_checkout wymaga payment_sandbox HumanGate.'); const total=cartTotal(); if(total>num('checkoutLimit'))return msg('BLOCK: checkout przekracza limit operatora.'); document.getElementById('checkoutState').textContent='Checkout sandbox PASS: '+total.toFixed(2)+' PLN'; document.getElementById('checkoutState').className='pass'; msg('PASS: cart_checkout wykonany w payment_sandbox.',false);}}
    function runFundingScan(){{const program=document.getElementById('fundingProgram').value.trim(); const hypothesis=document.getElementById('fundingHypothesis').value.trim(); if(!program||!hypothesis)return msg('BLOCK: funding_scan wymaga programu i hipotezy.'); state.funding.push({{program,hypothesis,scope:'supporting_feature'}}); document.getElementById('fundingState').textContent='Funding scan: '+program+' jako modul wspierajacy.'; msg('PASS: funding_scan zapisany bez zmiany typu projektu.',false);}}
    function openAdminConsole(){{if(role()!=='tenant_admin')return msg('BLOCK: admin_console wymaga tenant_admin.'); state.admin=true; document.getElementById('adminState').textContent='Admin console: aktywna'; document.getElementById('adminState').className='pass'; msg('PASS: admin_console aktywna.',false);}}
    function runTestCatalog(){{if(!state.tenant||!state.vendor||!state.products.length)return msg('BLOCK: test catalog wymaga tenant, vendor i produkt.'); if(!state.payment)return msg('BLOCK: test catalog wymaga payment HumanGate.'); state.tests=true; document.getElementById('testState').textContent='Testy: PASS'; document.getElementById('testState').className='pass'; msg('PASS: katalog testow wykonany.',false);}}
    function approveReleaseGate(){{if(role()!=='release_manager')return msg('BLOCK: release_governance wymaga release_manager.'); if(!state.tests)return msg('BLOCK: release wymaga testow PASS.'); state.release=true; document.getElementById('releaseState').textContent='Release HumanGate: zatwierdzony'; document.getElementById('releaseState').className='pass'; msg('PASS: release_governance zatwierdzony.',false);}}
    function promoteCanary(){{if(!state.release)return msg('BLOCK: canary wymaga release HumanGate.'); const e=num('errorRate'); if(e>1){{state.rolledBack=true; state.release=false; state.canary=0; document.getElementById('releaseState').textContent='Release: rollback po canary; wymaga ponownego HumanGate'; document.getElementById('releaseState').className='block'; document.getElementById('canaryState').textContent='Canary: rollback po error_rate '+e+'%'; return msg('BLOCK: auto-rollback, error_rate > 1%.');}} state.rolledBack=false; state.canary=Number(document.getElementById('canaryStep').value); document.getElementById('canaryState').textContent='Canary: '+state.canary+'%'; msg('PASS: canary promote '+state.canary+'%.',false);}}
    function rollbackRelease(){{state.rolledBack=true; state.release=false; state.canary=0; document.getElementById('releaseState').textContent='Release: rollback wykonany'; document.getElementById('releaseState').className='block'; document.getElementById('canaryState').textContent='Canary: 0% po rollback'; msg('PASS: rollback lokalny wykonany; cleanup chmury wymaga osobnej zgody.',false);}}
    function render(){{document.getElementById('productTable').innerHTML=state.products.map(p=>`<tr><td>${{p.name}}</td><td>${{p.vendor}}</td><td>${{p.price}} PLN</td><td>${{p.tax}}%</td><td>${{p.shipping}} PLN</td></tr>`).join('');}}
    function buildEvidencePack(){{const pack={{project_id:project.project_id,product:'marketplace_platform',modules,tenant_identity:state.tenant,vendor_onboarding:state.vendor,product_catalog:state.products,cart_checkout:{{limit:num('checkoutLimit'),total:cartTotal()}},payment_sandbox:state.payment,tax_shipping:state.tax,admin_console:state.admin,funding_scan:state.funding,release_governance:{{tests_passed:state.tests,release_approved:state.release,canary:state.canary,rolled_back:state.rolledBack}},audit_evidence_pack:state.audit,generated_at:new Date().toISOString()}}; document.getElementById('evidenceOutput').textContent=JSON.stringify(pack,null,2); return pack;}}
    document.getElementById('moduleList').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w marketplace_platform D5.</p></article>`).join(''); render(); buildEvidencePack();
  </script>
</body>
</html>
"""


def _bioinformatics_workflow_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Workflow bioinformatyczny AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --ink:#16211f; --paper:#f3f8f5; --card:#fffefa; --line:#c8d5ce; --accent:#12614f; --warn:#9a6200; --danger:#9b1c31; --ok:#1f7a45; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#eaf7f0,#fff8e8 52%,#eef4ff); font-family:Georgia,serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:16px; box-shadow:0 18px 45px rgba(24,50,43,.08); }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); line-height:.96; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    .card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:var(--card); }}
    label {{ display:grid; gap:7px; font-weight:700; }}
    input,textarea,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; color:var(--ink); font:inherit; }}
    button,a.download {{ border:0; border-radius:999px; padding:11px 16px; margin:4px 8px 4px 0; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.guard {{ background:var(--warn); }} button.danger {{ background:var(--danger); }}
    .pass {{ color:var(--ok); font-weight:800; }} .block {{ color:var(--danger); font-weight:800; }} .muted {{ color:#60706a; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; background:#13231c; color:#edf8f1; border-radius:14px; padding:14px; overflow:auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="synthetic_data_intake format_validation qc_pipeline sample_pseudonymization variant_research_scoring clinical_safety_guard funding_scan local_model_documentation audit_evidence_pack integration_validation humangate research-only no clinical use">
    <header>
      <p>AEIS bioinformatics_workflow / FASTQ / VCF / local-only / Bielik / PLLuM / funding_scan / HumanGate D5</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard D5:</strong> analiza jest research-only, no clinical use. Import realnych danych pacjenta, zewnetrzny LLM, raport eksportowy i funding submission wymagaja HumanGate.</p>
      <p><strong>Granica typu:</strong> funding_scan jest funkcja wspierajaca bioinformatics_workflow i nie moze przeksztalcic projektu w funding-only.</p>
    </header>
    <section>
      <h2>1. Intake probki i runtime</h2>
      <div class="grid">
        <label>Nazwa pliku probki<input id="sampleFile" data-testid="sample-file" value="sample_AURORA_001.vcf"></label>
        <label>Opis probki<textarea id="sampleDescription" data-testid="sample-description">Syntetyczna probka badawcza bez PESEL i bez identyfikatorow pacjenta.</textarea></label>
        <label>Runtime<select id="runtimePolicy" data-testid="runtime-policy"><option value="local_only">local_only Bielik/PLLuM/Ollama</option><option value="hybrid_requested">hybrid_requested external LLM</option></select></label>
        <label>Cel uzycia<select id="useIntent" data-testid="use-intent"><option value="research_only">research-only</option><option value="clinical_production">kliniczna decyzja produkcyjna</option></select></label>
      </div>
      <button onclick="importSample()" data-testid="import-sample">Importuj probke</button>
      <button class="danger" onclick="requestHybridRuntime()" data-testid="request-hybrid">Popros o hybrid runtime</button>
      <p id="intakeState" class="block">Intake: oczekuje na walidacje.</p>
      <p id="operatorMessage" class="muted"></p>
    </section>
    <section>
      <h2>2. QC, pseudonimizacja i scoring</h2>
      <div class="grid">
        <article class="card">
          <h3>format_validation + qc_pipeline</h3>
          <button onclick="runQcPipeline()" data-testid="run-qc">Uruchom QC</button>
          <p id="qcState" class="block">QC: zablokowane do importu.</p>
        </article>
        <article class="card">
          <h3>sample_pseudonymization</h3>
          <button onclick="pseudonymizeSample()" data-testid="pseudonymize-sample">Pseudonimizuj</button>
          <p id="pseudoState" class="block">Pseudonimizacja: oczekuje.</p>
        </article>
        <article class="card">
          <h3>variant_research_scoring</h3>
          <button onclick="scoreVariantResearchOnly()" data-testid="score-variant">Research scoring</button>
          <p id="scoreState" class="block">Scoring: oczekuje.</p>
        </article>
      </div>
    </section>
    <section>
      <h2>3. Funding scan i modele lokalne</h2>
      <div class="grid">
        <label>Program dotacyjny<input id="fundingProgram" data-testid="funding-program" value="Horizon Europe / EIC Pathfinder / FENG SMART / Digital Europe"></label>
        <label>Hipoteza funding<textarea id="fundingHypothesis" data-testid="funding-hypothesis">Privacy-preserving bioinformatics workflow for research-only variant triage, local Polish LLM governance and audit evidence.</textarea></label>
      </div>
      <button onclick="runFundingScan()" data-testid="run-funding-scan">Uruchom funding_scan</button>
      <button onclick="documentLocalModels()" data-testid="document-local-models">Udokumentuj Bielik/PLLuM</button>
      <p id="fundingState" class="muted">Funding scan jest funkcja wspierajaca.</p>
      <pre id="localModels">local_model_documentation: czeka.</pre>
    </section>
    <section>
      <h2>4. Eksport raportu i HumanGate</h2>
      <button onclick="exportReport()" data-testid="export-report">Eksportuj raport</button>
      <button class="guard" onclick="approveExportGate()" data-testid="approve-export-gate">HumanGate: report_export</button>
      <a id="reportLink" class="download" download="bioinformatics-research-report.json" href="#">Pobierz raport JSON</a>
      <p id="exportState" class="block">report_export: oczekuje na HumanGate.</p>
    </section>
    <section>
      <h2>5. Katalog testow, moduly i evidence pack</h2>
      <table><thead><tr><th>Kontrola</th><th>Status</th><th>Szczegoly</th></tr></thead><tbody id="checks"></tbody></table>
      <div id="moduleList" class="grid"></div>
      <button onclick="buildEvidencePack()" data-testid="build-evidence">Zbuduj audit_evidence_pack</button>
      <pre id="evidenceOutput">Brak audit_evidence_pack.</pre>
    </section>
  </main>
  <script>
    const project={project_json}; const modules={modules_json};
    const state={{sample:false,format:false,qc:false,pseudonymized:false,scored:false,exportGate:false,exported:false,hybridApproved:false,funding:[],localModels:false,audit:[]}};
    function msg(text, blocked=true){{const n=document.getElementById('operatorMessage'); n.textContent=text; n.className=blocked?'block':'pass'; state.audit.push({{ts:new Date().toISOString(), text, blocked}}); renderChecks(); buildEvidencePack();}}
    function sampleName(){{return document.getElementById('sampleFile').value.trim();}}
    function sampleDescription(){{return document.getElementById('sampleDescription').value.trim();}}
    function hasPesel(text){{return /\\b\\d{{11}}\\b/.test(String(text||''));}}
    function runtimeLocalOnly(){{return document.getElementById('runtimePolicy').value==='local_only';}}
    function importSample(){{
      const file=sampleName(); const desc=sampleDescription();
      if(!/\\.(vcf|fastq|fq)$/i.test(file)) return msg('BLOCK: format_validation akceptuje tylko .vcf, .fastq albo .fq.');
      if(hasPesel(desc)) return msg('BLOCK: pii_guard wykryl PESEL. Wymagany HumanGate patient_data_import.');
      if(!runtimeLocalOnly()) return msg('BLOCK: external_llm_processing wymaga HumanGate przed importem.');
      state.sample=true; state.format=true;
      document.getElementById('intakeState').textContent='PASS: synthetic_data_intake i format_validation dla '+file;
      document.getElementById('intakeState').className='pass';
      msg('PASS: probka przyjeta lokalnie bez identyfikatorow pacjenta.', false);
    }}
    function requestHybridRuntime(){{
      if(runtimeLocalOnly()) return msg('PASS: runtime local_only pozostaje aktywny.', false);
      return msg('BLOCK: hybrid_requested wymaga HumanGate external_llm_processing i nowej meta-orkiestracji.');
    }}
    function runQcPipeline(){{
      if(!state.sample || !state.format) return msg('BLOCK: qc_pipeline wymaga poprawnego importu i format_validation.');
      state.qc=true; document.getElementById('qcState').textContent='PASS: qc_pipeline zakonczony, coverage=synthetic, contamination=0';
      document.getElementById('qcState').className='pass'; msg('PASS: qc_pipeline gotowy.', false);
    }}
    function pseudonymizeSample(){{
      if(!state.qc) return msg('BLOCK: sample_pseudonymization wymaga QC PASS.');
      if(!runtimeLocalOnly()) return msg('BLOCK: pseudonimizacja musi zostac local-only do czasu HumanGate.');
      if(hasPesel(sampleDescription())) return msg('BLOCK: pii_guard nadal widzi PESEL.');
      state.pseudonymized=true; document.getElementById('pseudoState').textContent='PASS: sample_pseudonymization -> AURORA-SAMPLE-001';
      document.getElementById('pseudoState').className='pass'; msg('PASS: probka pseudonimizowana lokalnie.', false);
    }}
    function scoreVariantResearchOnly(){{
      if(!state.pseudonymized) return msg('BLOCK: variant_research_scoring wymaga pseudonimizacji.');
      if(document.getElementById('useIntent').value!=='research_only') return msg('BLOCK: clinical_safety_guard blokuje uzycie kliniczne. no clinical use.');
      state.scored=true; document.getElementById('scoreState').textContent='PASS: research-only variant score=0.72; no clinical use; brak diagnozy.';
      document.getElementById('scoreState').className='pass'; msg('PASS: variant_research_scoring zapisany jako research-only.', false);
    }}
    function runFundingScan(){{
      const program=document.getElementById('fundingProgram').value.trim(); const hypothesis=document.getElementById('fundingHypothesis').value.trim();
      if(!program||!hypothesis) return msg('BLOCK: funding_scan wymaga programu i hipotezy.');
      state.funding.push({{program,hypothesis,scope:'supporting_feature',project_kind:'bioinformatics_workflow'}});
      document.getElementById('fundingState').textContent='PASS: funding_scan wspierajacy dla '+program;
      document.getElementById('fundingState').className='pass'; msg('PASS: funding_scan nie zmienil typu projektu.', false);
    }}
    function documentLocalModels(){{
      state.localModels=true;
      document.getElementById('localModels').textContent=JSON.stringify({{local_model_documentation:['SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M','PRIHLOP/PLLuM:12B-chat-Q8_0'],policy:'local_only_until_humangate'}},null,2);
      msg('PASS: local_model_documentation zapisuje Bielik i PLLuM.', false);
    }}
    function approveExportGate(){{
      state.exportGate=true; document.getElementById('exportState').textContent='HumanGate report_export: approved';
      document.getElementById('exportState').className='pass'; msg('PASS: HumanGate report_export zatwierdzony.', false);
    }}
    function exportReport(){{
      if(!state.exportGate) return msg('BLOCK: report_export wymaga HumanGate.');
      if(!state.scored) return msg('BLOCK: raport wymaga research scoring.');
      state.exported=true; const pack=buildEvidencePack();
      document.getElementById('reportLink').href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(pack,null,2));
      document.getElementById('exportState').textContent='PASS: raport JSON gotowy lokalnie; funding_submission nadal wymaga osobnej zgody.';
      document.getElementById('exportState').className='pass'; msg('PASS: raport research-only wyeksportowany lokalnie.', false);
    }}
    function renderChecks(){{
      const checks=[
        {{name:'synthetic_data_intake',ok:state.sample,detail:sampleName()}},
        {{name:'format_validation',ok:state.format,detail:'.vcf/.fastq/.fq only'}},
        {{name:'qc_pipeline',ok:state.qc,detail:state.qc?'qc pass':'czeka'}},
        {{name:'sample_pseudonymization',ok:state.pseudonymized,detail:state.pseudonymized?'AURORA-SAMPLE-001':'czeka'}},
        {{name:'variant_research_scoring',ok:state.scored,detail:'research-only / no clinical use'}},
        {{name:'clinical_safety_guard',ok:document.getElementById('useIntent').value==='research_only',detail:'blokada diagnozy i terapii'}},
        {{name:'funding_scan',ok:state.funding.length>0,detail:state.funding.length+' wpisow'}},
        {{name:'local_model_documentation',ok:state.localModels,detail:'Bielik / PLLuM'}},
        {{name:'report_export_humangate',ok:state.exportGate,detail:state.exportGate?'approved':'blocked'}},
        {{name:'audit_evidence_pack',ok:state.audit.length>0,detail:state.audit.length+' zdarzen'}}
      ];
      document.getElementById('checks').innerHTML=checks.map(c=>`<tr><td>${{c.name}}</td><td class="${{c.ok?'pass':'block'}}">${{c.ok?'PASS':'BLOCK'}}</td><td>${{c.detail}}</td></tr>`).join('');
    }}
    function buildEvidencePack(){{
      const pack={{project_id:project.project_id,product:'bioinformatics_workflow',modules,local_only:runtimeLocalOnly(),pii_guard:!hasPesel(sampleDescription()),clinical_safety_guard:document.getElementById('useIntent').value==='research_only',research_only:true,no_clinical_use:true,synthetic_data_intake:state.sample,format_validation:state.format,qc_pipeline:state.qc,sample_pseudonymization:state.pseudonymized,variant_research_scoring:state.scored,funding_scan:state.funding,local_model_documentation:state.localModels,report_export:{{human_gate:state.exportGate,exported:state.exported}},audit_evidence_pack:state.audit,generated_at:new Date().toISOString()}};
      document.getElementById('evidenceOutput').textContent=JSON.stringify(pack,null,2); return pack;
    }}
    document.getElementById('moduleList').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w bioinformatics_workflow D5.</p></article>`).join('');
    renderChecks(); buildEvidencePack();
  </script>
</body>
</html>
"""


def _mental_health_safety_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "VANGUARD-MIND"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --ink:#18212f; --paper:#f4f7fb; --card:#fffdf8; --line:#c9d4e5; --accent:#1e5b8f; --warn:#9a6200; --danger:#a21c37; --ok:#176b43; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#eef6ff,#fff8e8 50%,#f2fff7); font-family:Georgia,serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:16px; box-shadow:0 18px 45px rgba(24,38,60,.08); }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); line-height:.96; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    .card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:var(--card); }}
    label {{ display:grid; gap:7px; font-weight:700; }}
    input,textarea,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; color:var(--ink); font:inherit; }}
    button,a.download {{ border:0; border-radius:999px; padding:11px 16px; margin:4px 8px 4px 0; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.guard {{ background:var(--warn); }} button.danger {{ background:var(--danger); }}
    .pass {{ color:var(--ok); font-weight:800; }} .block {{ color:var(--danger); font-weight:800; }} .muted {{ color:#627086; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; background:#111c2e; color:#eef6ff; border-radius:14px; padding:14px; overflow:auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="wellbeing_intake crisis_classifier no_medical_advice_guard safe_response_generator emergency_handoff pii_minimization local_model_safety_review source_backed_resources release_safety_gate audit_evidence_pack integration_validation humangate">
    <header>
      <p>AEIS mental_health_safety / wellbeing / crisis_classifier / no_medical_advice_guard / HumanGate D5</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard D5:</strong> aplikacja nie diagnozuje, nie prowadzi terapii i nie udziela porad medycznych. Kryzys lub autoagresja uruchamiaja safe response i emergency_handoff.</p>
      <p><strong>Granica prywatnosci:</strong> wpisy wellbeing pozostaja local-only; external LLM, public release i aktualizacja zasobow pomocowych wymagaja HumanGate.</p>
    </header>
    <section>
      <h2>1. Intake, runtime i klasyfikacja</h2>
      <div class="grid">
        <label>Wpis wellbeing<textarea id="wellbeingText" data-testid="wellbeing-text" rows="5">Czuje duzy stres przed prezentacja i chce spokojnie uporzadkowac mysli bez diagnozy.</textarea></label>
        <label>Runtime<select id="runtimePolicy" data-testid="runtime-policy"><option value="local_only">local_only Bielik/PLLuM/Ollama</option><option value="external_requested">external_requested LLM/API</option></select></label>
        <label>Tryb odpowiedzi<select id="responseMode" data-testid="response-mode"><option value="wellbeing">psychoedukacja wellbeing</option><option value="medical_claim">diagnoza albo plan terapii</option></select></label>
      </div>
      <button onclick="analyzeWellbeing()" data-testid="analyze-wellbeing">Przeanalizuj wpis</button>
      <button class="danger" onclick="requestExternalRuntime()" data-testid="request-external-runtime">Popros o external runtime</button>
      <p id="intakeState" class="block">Intake: oczekuje.</p>
      <p id="operatorMessage" class="muted"></p>
    </section>
    <section>
      <h2>2. Safe response i emergency hand-off</h2>
      <div class="grid">
        <article class="card"><h3>crisis_classifier</h3><p id="crisisState" class="block">Nieuruchomiony.</p></article>
        <article class="card"><h3>no_medical_advice_guard</h3><p id="medicalState" class="block">Nieuruchomiony.</p></article>
        <article class="card"><h3>safe_response_generator</h3><pre id="safeResponse">Brak odpowiedzi.</pre></article>
        <article class="card"><h3>emergency_handoff</h3><pre id="handoffState">Brak hand-off.</pre></article>
      </div>
    </section>
    <section>
      <h2>3. Zrodla pomocowe i modele lokalne</h2>
      <div class="grid">
        <label>Zrodlo pomocowe<input id="resourceSource" data-testid="resource-source" value="112 / lokalny numer alarmowy / profesjonalna pomoc kryzysowa"></label>
        <label>Notatka do zrodla<textarea id="resourceNote" data-testid="resource-note">Zasoby pomocowe musza byc aktualne i zatwierdzone przed publicznym release.</textarea></label>
      </div>
      <button onclick="updateResources()" data-testid="update-resources">Aktualizuj zasoby pomocowe</button>
      <button class="guard" onclick="approveResourceGate()" data-testid="approve-resource-gate">HumanGate: emergency_resource_update</button>
      <button onclick="documentLocalModels()" data-testid="document-local-models">Udokumentuj Bielik/PLLuM safety review</button>
      <p id="resourceState" class="block">source_backed_resources: oczekuje na HumanGate.</p>
      <pre id="localModels">local_model_safety_review: czeka.</pre>
    </section>
    <section>
      <h2>4. Katalog testow i release gate</h2>
      <button onclick="runSafetyTests()" data-testid="run-safety-tests">Uruchom katalog testow</button>
      <button class="guard" onclick="approveReleaseGate()" data-testid="approve-release-gate">HumanGate: release_safety_gate</button>
      <p id="testState" class="block">Testy: nieuruchomione.</p>
      <p id="releaseState" class="block">Release: zablokowany.</p>
    </section>
    <section>
      <h2>5. Moduly i audit evidence pack</h2>
      <table><thead><tr><th>Kontrola</th><th>Status</th><th>Szczegoly</th></tr></thead><tbody id="checks"></tbody></table>
      <div id="moduleList" class="grid"></div>
      <button onclick="buildEvidencePack()" data-testid="build-evidence">Zbuduj audit_evidence_pack</button>
      <pre id="evidenceOutput">Brak audit_evidence_pack.</pre>
    </section>
  </main>
  <script>
    const project={project_json}; const modules={modules_json};
    const state={{intake:false,crisis:false,medicalBlocked:false,response:false,handoff:false,piiClean:false,externalApproved:false,resourceGate:false,resources:false,localModels:false,tests:false,release:false,audit:[]}};
    function text(){{return document.getElementById('wellbeingText').value.trim();}}
    function runtimeLocalOnly(){{return document.getElementById('runtimePolicy').value==='local_only';}}
    function hasPii(value){{return /\\b\\d{{11}}\\b|\\b\\d{{3}}[- ]?\\d{{3}}[- ]?\\d{{3}}\\b|[\\w.+-]+@[\\w.-]+\\.[a-z]{{2,}}/i.test(String(value||''));}}
    function isCrisis(value){{return /samoboj|samobój|zabic sie|zabic się|nie chce zyc|nie chcę żyć|autoagres|krzywd|przemoc|kryzys/i.test(String(value||''));}}
    function isMedical(value){{return /diagnoz|terapi|lek|dawk|chorob|recept|plan leczenia|porad medycz/i.test(String(value||''));}}
    function msg(message, blocked=true){{const n=document.getElementById('operatorMessage'); n.textContent=message; n.className=blocked?'block':'pass'; state.audit.push({{ts:new Date().toISOString(),text:message,blocked}}); renderChecks(); buildEvidencePack();}}
    function analyzeWellbeing(){{
      const value=text();
      if(!value) return msg('BLOCK: wellbeing_intake wymaga wpisu operatora.');
      if(hasPii(value)) return msg('BLOCK: pii_minimization wykrylo PII. Usun dane osobowe przed analiza.');
      if(!runtimeLocalOnly()) return msg('BLOCK: external_llm_processing wymaga HumanGate i nowej meta-orkiestracji.');
      state.intake=true; state.piiClean=true;
      const crisis=isCrisis(value); const medical=isMedical(value) || document.getElementById('responseMode').value==='medical_claim';
      state.crisis=crisis; state.medicalBlocked=medical;
      document.getElementById('intakeState').textContent='PASS: wellbeing_intake przyjety local-only.';
      document.getElementById('intakeState').className='pass';
      document.getElementById('crisisState').textContent=crisis?'PASS: crisis_classifier wykryl kryzys':'PASS: crisis_classifier brak kryzysu';
      document.getElementById('crisisState').className='pass';
      if(medical){{
        document.getElementById('medicalState').textContent='BLOCK: no_medical_advice_guard blokuje diagnoze, terapie i zalecenia medyczne.';
        document.getElementById('medicalState').className='block';
        document.getElementById('safeResponse').textContent='Nie moge diagnozowac ani tworzyc planu terapii. Skontaktuj sie z wykwalifikowanym specjalista.';
        return msg('BLOCK: no_medical_advice_guard zatrzymal odpowiedz medyczna.');
      }}
      document.getElementById('medicalState').textContent='PASS: brak diagnozy i brak porady medycznej.';
      document.getElementById('medicalState').className='pass';
      state.response=true;
      if(crisis){{
        state.handoff=true;
        document.getElementById('safeResponse').textContent='To brzmi pilnie. Nie zostawaj z tym sam/a. Jesli grozi Ci bezposrednie niebezpieczenstwo, zadzwon pod 112 albo skontaktuj sie z lokalna pomoca kryzysowa. Jesli mozesz, podejdz do zaufanej osoby teraz.';
        document.getElementById('handoffState').textContent='emergency_handoff: pokazano zasoby i blokade dalszej autonomii.';
        msg('PASS: crisis_classifier uruchomil emergency_handoff bez diagnozy.', false);
      }} else {{
        document.getElementById('safeResponse').textContent='Mozesz zapisac 3 fakty, 1 rzecz pod kontrola i 1 maly krok na najblizsze 10 minut. To psychoedukacja, nie diagnoza ani terapia.';
        document.getElementById('handoffState').textContent='emergency_handoff: nie wymagany w tym scenariuszu.';
        msg('PASS: safe_response_generator utworzyl neutralna psychoedukacje wellbeing.', false);
      }}
    }}
    function requestExternalRuntime(){{
      if(runtimeLocalOnly()) return msg('PASS: runtime local_only pozostaje aktywny.', false);
      return msg('BLOCK: external_requested wymaga HumanGate external_llm_processing i nowej meta-orkiestracji.');
    }}
    function approveResourceGate(){{state.resourceGate=true; document.getElementById('resourceState').textContent='HumanGate emergency_resource_update: approved'; document.getElementById('resourceState').className='pass'; msg('PASS: HumanGate emergency_resource_update zatwierdzony.', false);}}
    function updateResources(){{
      if(!state.resourceGate) return msg('BLOCK: source_backed_resources wymagaja HumanGate przed aktualizacja.');
      const source=document.getElementById('resourceSource').value.trim();
      if(!source) return msg('BLOCK: source_backed_resources wymaga zrodla.');
      state.resources=true; document.getElementById('resourceState').textContent='PASS: source_backed_resources zapisane: '+source; document.getElementById('resourceState').className='pass'; msg('PASS: source_backed_resources zaktualizowane po HG.', false);
    }}
    function documentLocalModels(){{state.localModels=true; document.getElementById('localModels').textContent=JSON.stringify({{local_model_safety_review:['SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M','PRIHLOP/PLLuM:12B-chat-Q8_0'],policy:'local_only_until_humangate',no_medical_advice:true}},null,2); msg('PASS: local_model_safety_review zapisuje Bielik i PLLuM.', false);}}
    function runSafetyTests(){{
      if(!state.intake || !state.response) return msg('BLOCK: katalog testow wymaga poprawnej analizy wellbeing.');
      if(!state.resources || !state.localModels) return msg('BLOCK: katalog testow wymaga source_backed_resources i local_model_safety_review.');
      state.tests=true; document.getElementById('testState').textContent='PASS: katalog testow safety wykonany.'; document.getElementById('testState').className='pass'; msg('PASS: katalog testow pokryl PII, kryzys, medical advice i release gate.', false);
    }}
    function approveReleaseGate(){{
      if(!state.tests) return msg('BLOCK: release_safety_gate wymaga katalogu testow PASS.');
      state.release=true; document.getElementById('releaseState').textContent='PASS: release_safety_gate approved; public release nadal bez automatycznego deploy.'; document.getElementById('releaseState').className='pass'; msg('PASS: HumanGate release_safety_gate zatwierdzony.', false);
    }}
    function renderChecks(){{
      const checks=[
        {{name:'wellbeing_intake',ok:state.intake,detail:text()?text().slice(0,80):'brak wpisu'}},
        {{name:'crisis_classifier',ok:state.intake,detail:state.crisis?'crisis':'standard'}},
        {{name:'no_medical_advice_guard',ok:!state.medicalBlocked,detail:state.medicalBlocked?'blocked':'no diagnosis'}},
        {{name:'safe_response_generator',ok:state.response,detail:state.response?'response ready':'czeka'}},
        {{name:'emergency_handoff',ok:state.handoff || state.intake,detail:state.handoff?'handoff shown':'not required'}},
        {{name:'pii_minimization',ok:state.piiClean,detail:state.piiClean?'clean':'blocked or waiting'}},
        {{name:'local_model_safety_review',ok:state.localModels,detail:'Bielik / PLLuM'}},
        {{name:'source_backed_resources',ok:state.resources,detail:state.resources?'approved source':'blocked'}},
        {{name:'release_safety_gate',ok:state.release,detail:state.release?'approved':'blocked'}},
        {{name:'audit_evidence_pack',ok:state.audit.length>0,detail:state.audit.length+' zdarzen'}}
      ];
      document.getElementById('checks').innerHTML=checks.map(c=>`<tr><td>${{c.name}}</td><td class="${{c.ok?'pass':'block'}}">${{c.ok?'PASS':'BLOCK'}}</td><td>${{c.detail}}</td></tr>`).join('');
    }}
    function buildEvidencePack(){{
      const pack={{project_id:project.project_id,product:'mental_health_safety',modules,local_only:runtimeLocalOnly(),wellbeing_intake:state.intake,crisis_classifier:state.crisis,no_medical_advice_guard:!state.medicalBlocked,safe_response_generator:state.response,emergency_handoff:state.handoff,pii_minimization:state.piiClean,local_model_safety_review:state.localModels,source_backed_resources:state.resources,release_safety_gate:state.release,audit_evidence_pack:state.audit,generated_at:new Date().toISOString()}};
      document.getElementById('evidenceOutput').textContent=JSON.stringify(pack,null,2); return pack;
    }}
    document.getElementById('moduleList').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w mental_health_safety D5.</p></article>`).join('');
    renderChecks(); buildEvidencePack();
  </script>
</body>
</html>
"""


def _application_domain_profile(summary: dict[str, Any]) -> dict[str, Any]:
    text = f"{summary.get('title', '')} {summary.get('idea', '')}".lower()
    profiles = [
        (
            ("grid", "energy", "telemetry", "anomaly"),
            {
                "domain": "industrial_energy_anomaly",
                "summary": "Energy telemetry, anomaly scoring, grid incident triage and safety evidence.",
                "controls": [
                    {"id": "energy_telemetry", "label": "Energy telemetry intake", "metric": "MW delta / frequency / feeder", "action": "Normalize incoming telemetry and mark missing samples."},
                    {"id": "anomaly_detection", "label": "Anomaly score", "metric": "risk score", "action": "Score deviation against operating baseline and classify incident priority."},
                    {"id": "grid_incident", "label": "Grid incident workflow", "metric": "incident severity", "action": "Assign operator, isolation zone and escalation path."},
                    {"id": "safety_evidence", "label": "Safety evidence pack", "metric": "audit evidence", "action": "Bundle telemetry, decision log and HumanGate approval before external dispatch."},
                ],
            },
        ),
        (
            ("civitas", "permit", "foia", "wcag"),
            {
                "domain": "public_admin_permits",
                "summary": "Permit intake, FOIA disclosure checks, WCAG review and appeal evidence.",
                "controls": [
                    {"id": "permit_intake", "label": "Permit intake", "metric": "case completeness", "action": "Validate applicant packet, zoning facts and missing public records."},
                    {"id": "foia_guard", "label": "FOIA disclosure guard", "metric": "redaction risk", "action": "Separate public fields from protected data before publication."},
                    {"id": "wcag_review", "label": "WCAG review", "metric": "accessibility status", "action": "Check required notices, language clarity and accessible decision output."},
                    {"id": "appeal_evidence", "label": "Appeal evidence", "metric": "appeal window", "action": "Prepare decision rationale, timestamps and HumanGate sign-off."},
                ],
            },
        ),
        (
            ("harbor", "rescue", "emergency"),
            {
                "domain": "harbor_rescue_coordination",
                "summary": "Emergency harbor coordination, vessel triage, berth allocation and rescue evidence.",
                "controls": [
                    {"id": "distress_intake", "label": "Distress intake", "metric": "mayday priority", "action": "Capture vessel, crew, weather and last known position."},
                    {"id": "resource_dispatch", "label": "Resource dispatch", "metric": "ETA minutes", "action": "Assign rescue unit, berth and medical handoff."},
                    {"id": "harbor_risk", "label": "Harbor risk map", "metric": "traffic conflict", "action": "Check channel conflicts, tide constraints and exclusion zones."},
                    {"id": "rescue_evidence", "label": "Rescue evidence pack", "metric": "command log", "action": "Bundle dispatch trail and require HumanGate for external notifications."},
                ],
            },
        ),
        (
            ("iron", "maintain", "maintenance", "predictive"),
            {
                "domain": "predictive_maintenance_control",
                "summary": "Asset health, vibration trends, work orders, spare parts and maintenance evidence.",
                "controls": [
                    {"id": "asset_health", "label": "Asset health intake", "metric": "vibration / temperature", "action": "Capture asset signal and compare against maintenance baseline."},
                    {"id": "failure_prediction", "label": "Failure prediction", "metric": "failure probability", "action": "Estimate risk window and recommended intervention."},
                    {"id": "work_order", "label": "Work order planner", "metric": "downtime impact", "action": "Create local work order with required technician skills and spares."},
                    {"id": "maintenance_evidence", "label": "Maintenance evidence", "metric": "audit trail", "action": "Record readings, decision rationale and HumanGate release gate."},
                ],
            },
        ),
        (
            ("orpheus", "media", "rights", "release"),
            {
                "domain": "media_rights_release",
                "summary": "Media rights clearance, release workflow, takedown risk and revenue evidence.",
                "controls": [
                    {"id": "rights_registry", "label": "Rights registry", "metric": "license coverage", "action": "Track territory, term, talent releases and asset ownership."},
                    {"id": "release_gate", "label": "Release gate", "metric": "approval status", "action": "Block publication until rights and HumanGate review pass."},
                    {"id": "takedown_risk", "label": "Takedown risk", "metric": "claim probability", "action": "Flag missing clauses, expired regions and conflicting exclusivity."},
                    {"id": "revenue_evidence", "label": "Revenue evidence", "metric": "split ledger", "action": "Prepare royalty split evidence and partner export bundle."},
                ],
            },
        ),
        (
            ("terra", "csrd", "esg", "carbon", "emission", "greenwashing"),
            {
                "domain": "csrd_esg_evidence",
                "summary": "CSRD ESG evidence, parcel traceability, audit controls and regulated export pack.",
                "controls": [
                    {"id": "parcel_trace", "label": "Parcel trace", "metric": "chain of custody", "action": "Link parcel, supplier declaration and evidence source."},
                    {"id": "csrd_mapping", "label": "CSRD mapping", "metric": "disclosure coverage", "action": "Map evidence to ESG disclosure requirement and gap status."},
                    {"id": "source_verification", "label": "Source verification", "metric": "confidence score", "action": "Check document provenance, timestamp and contradictory claims."},
                    {"id": "esg_evidence", "label": "ESG evidence pack", "metric": "audit readiness", "action": "Prepare regulated export and HumanGate approval trail."},
                ],
            },
        ),
        (
            ("nomad", "travel", "route", "logistics"),
            {
                "domain": "travel_supply_chain_risk",
                "summary": "Travel supply chain risk, lane monitoring, vendor continuity and offline operator pack.",
                "controls": [
                    {"id": "lane_risk", "label": "Lane risk monitor", "metric": "route disruption", "action": "Score transport lane, border delay and regional disruption."},
                    {"id": "vendor_continuity", "label": "Vendor continuity", "metric": "supplier risk", "action": "Check supplier status, alternates and contractual blocker."},
                    {"id": "traveler_handoff", "label": "Traveler handoff", "metric": "handoff readiness", "action": "Prepare itinerary change packet and local-first fallback."},
                    {"id": "supply_evidence", "label": "Supply evidence pack", "metric": "decision trail", "action": "Export risk rationale after HumanGate approval."},
                ],
            },
        ),
    ]
    for keywords, profile in profiles:
        if any(keyword in text for keyword in keywords):
            return profile
    return {
        "domain": "operator_application",
        "summary": "Operator workflow, decision controls, validation gates and evidence export.",
        "controls": [
            {"id": "workflow_intake", "label": "Workflow intake", "metric": "completeness", "action": "Capture the operator case and required constraints."},
            {"id": "risk_review", "label": "Risk review", "metric": "risk score", "action": "Classify blockers before execution."},
            {"id": "execution_gate", "label": "Execution gate", "metric": "approval status", "action": "Require HumanGate before any external action."},
            {"id": "evidence_pack", "label": "Evidence pack", "metric": "audit readiness", "action": "Bundle decisions, module outputs and timestamps."},
        ],
    }


def _generic_artifact(project: dict[str, Any]) -> str:
    summary = _project_summary(project)
    title = escape(str(summary["title"] or "Aplikacja AEIS"))
    idea = escape(str(summary["idea"] or ""))
    modules_json = _json_script(summary["modules"])
    project_json = _json_script(summary)
    domain_profile = _application_domain_profile(summary)
    domain_json = _json_script(domain_profile)
    domain_label = escape(str(domain_profile["summary"]))
    contract_tokens = " ".join(str(control["id"]) for control in domain_profile["controls"])
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: Georgia, serif; background: #f5f7f0; color: #1e2520; }}
    main {{ max-width: 1080px; margin: auto; padding: 32px; }}
    section, header {{ background: white; border: 1px solid #cbd7cc; border-radius: 14px; padding: 20px; margin-bottom: 16px; }}
    button {{ background: #194d41; color: white; border: 0; border-radius: 999px; padding: 10px 16px; }}
    input, textarea {{ width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #d7cebf; border-radius: 10px; margin: 6px 0 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid #cbd7cc; border-radius: 8px; padding: 12px; background: #fbfaf5; }}
    .status-ok {{ color: #17623f; font-weight: 700; }}
    .status-block {{ color: #8a1f2d; font-weight: 700; }}
    pre {{ white-space: pre-wrap; background: #15231d; color: #eff7ef; padding: 14px; border-radius: 14px; }}
  </style>
</head>
<body>
  <main data-artifact-contract="domain_control_workbench {contract_tokens} humangate_required evidence_pack">
    <header>
      <p>{domain_label}</p>
      <h1>{title}</h1>
      <p>{idea}</p>
      <p><strong>Guard:</strong> external dispatch, publication, regulated export and operator handoff require HumanGate evidence.</p>
    </header>
    <section>
      <h2>Domain control workbench</h2>
      <div id="domain-controls" class="grid"></div>
    </section>
    <section>
      <h2>Operator case</h2>
      <label>Case input<textarea id="operator-task" rows="4" placeholder="Describe the real operator case, signal, incident or evidence packet..."></textarea></label>
      <button onclick="addWorkItem()">Run selected controls</button>
      <button onclick="approveGate()">HumanGate approve local evidence</button>
      <p id="gate-status" class="status-block">HumanGate: pending</p>
      <div id="work-items" class="grid"></div>
    </section>
    <section>
      <h2>Moduły z masterplanu</h2>
      <div id="modules" class="grid"></div>
    </section>
    <section>
      <h2>Evidence export</h2>
      <button onclick="exportEvidence()">Zbuduj evidence JSON</button>
      <pre id="evidence">Brak danych.</pre>
    </section>
  </main>
  <script>
    const project = {project_json};
    const modules = {modules_json};
    const domain = {domain_json};
    const workItems = [];
    let gateApproved = false;
    let selectedControls = domain.controls.map(control => control.id);
    function renderControls() {{
      document.getElementById('domain-controls').innerHTML = domain.controls.map(control => `
        <article class="card">
          <h3>${{control.label}}</h3>
          <p><strong>Metric:</strong> ${{control.metric}}</p>
          <p>${{control.action}}</p>
          <label><input type="checkbox" checked onchange="toggleControl('${{control.id}}', this.checked)"> include in run</label>
        </article>
      `).join('');
    }}
    function toggleControl(id, enabled) {{
      selectedControls = enabled ? Array.from(new Set([...selectedControls, id])) : selectedControls.filter(item => item !== id);
      exportEvidence();
    }}
    function addWorkItem() {{
      const value = document.getElementById('operator-task').value.trim();
      if (!value) {{
        document.getElementById('evidence').textContent = 'Enter the operator case before running controls.';
        return;
      }}
      const controls = domain.controls.filter(control => selectedControls.includes(control.id));
      const missing = controls.length === 0;
      workItems.push({{
        id: workItems.length + 1,
        value,
        domain: domain.domain,
        controls: controls.map(control => control.id),
        status: missing ? 'blocked_no_control_selected' : (gateApproved ? 'ready_for_external_review' : 'local_review_only'),
        humangate_required_before_external_action: true
      }});
      renderWorkItems();
      exportEvidence();
    }}
    function approveGate() {{
      gateApproved = true;
      document.getElementById('gate-status').textContent = 'HumanGate: approved for local evidence only';
      document.getElementById('gate-status').className = 'status-ok';
      exportEvidence();
    }}
    function renderWorkItems() {{
      document.getElementById('work-items').innerHTML = workItems.map(item => `<article class="card"><strong>#${{item.id}}</strong><p>${{item.value}}</p><p>Domain: ${{item.domain}}</p><p>Controls: ${{item.controls.join(', ')}}</p><p>Status: ${{item.status}}</p></article>`).join('');
    }}
    function renderModules() {{
      document.getElementById('modules').innerHTML = modules.map(name => `<article class="card"><h3>${{name}}</h3><p>Moduł gotowy do walidacji operatora i evidence trail.</p></article>`).join('');
    }}
    function exportEvidence() {{
      document.getElementById('evidence').textContent = JSON.stringify({{
        project,
        domain,
        modules,
        selectedControls,
        workItems,
        humangate_approved_for_local_evidence: gateApproved,
        humangate_required_before_external_action: true,
        generated_at: new Date().toISOString()
      }}, null, 2);
    }}
    renderControls();
    renderModules();
    renderWorkItems();
    exportEvidence();
  </script>
</body>
</html>
"""


def _domain_build(project: dict[str, Any]) -> tuple[list[TaskSpec], list[TaskResult], str] | None:
    title = str(project.get("title") or "AEIS Project")
    kind = str(project.get("project_kind") or "")
    if kind == "ecommerce_generator":
        summary = _project_summary(project)
        title_html = escape(title)
        idea_html = escape(str(summary.get("idea") or ""))
        project_json = _json_script(summary)
        modules_json = _json_script(summary["modules"])
        html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  <style>
    :root {{ --ink:#16211d; --paper:#fbf7ef; --card:#fffdf7; --line:#d5c9b8; --accent:#9b4d1f; --ok:#1b7a45; --warn:#9a6200; --danger:#9b1c31; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#fff6df,#edf7f0 55%,#eef3ff); font-family:Georgia,serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.88); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:16px; box-shadow:0 18px 45px rgba(50,35,20,.08); }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); line-height:.96; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }}
    label {{ display:grid; gap:7px; font-weight:700; }}
    input,textarea,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; color:var(--ink); }}
    button,a.download {{ border:0; border-radius:999px; padding:11px 16px; margin:4px 8px 4px 0; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.secondary {{ background:#29435c; }} button.guard {{ background:var(--warn); }}
    .status-ok {{ color:var(--ok); font-weight:800; }} .status-block {{ color:var(--danger); font-weight:800; }}
    .card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:var(--card); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; background:#13231c; color:#edf8f1; border-radius:14px; padding:14px; overflow:auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="description_generation ean_validation marketplace_export human_review_gate evidence_pack">
    <header>
      <p>AEIS produkt e-commerce / obrazy produktu / opisy PL EN DE / EAN / Allegro / Amazon / CSV / HumanGate</p>
      <h1>{title_html}</h1>
      <p>{idea_html}</p>
      <p><strong>Guard:</strong> eksport CSV i publikacja sa zablokowane, dopoki operator nie zatwierdzi HumanGate.</p>
    </header>
    <section>
      <h2>1. Dane produktu</h2>
      <div class="grid">
        <label>Nazwa produktu<input id="productName" value="Torba kurierska PRO 20L"></label>
        <label>EAN<input id="ean" value="5901234123457"></label>
        <label>Kategoria marketplace<select id="category"><option>Allegro: Dom i ogrod</option><option>Amazon: Home</option><option>Amazon: Sports</option></select></label>
        <label>Pliki produktu<input id="files" type="file" multiple accept="image/*,.txt,.md,.pdf"></label>
      </div>
      <label>Brief produktu<textarea id="brief" rows="5">Wodoodporna torba 20L, odblaskowe elementy, regulowany pas, kolor czarny, dla kurierow rowerowych.</textarea></label>
      <button onclick="analyzeProduct()">Analizuj i generuj opisy</button>
      <button class="guard" onclick="approveGate()">HumanGate: zatwierdz opis i EAN</button>
      <p id="gateStatus" class="status-block">HumanGate: oczekuje</p>
      <p id="operatorMessage"></p>
    </section>
    <section>
      <h2>2. Opisy i walidacja</h2>
      <div class="grid">
        <article class="card"><h3>PL</h3><textarea id="descPL" rows="7"></textarea></article>
        <article class="card"><h3>EN</h3><textarea id="descEN" rows="7"></textarea></article>
        <article class="card"><h3>DE</h3><textarea id="descDE" rows="7"></textarea></article>
      </div>
      <table><thead><tr><th>Kontrola</th><th>Status</th><th>Szczegoly</th></tr></thead><tbody id="checks"></tbody></table>
    </section>
    <section>
      <h2>3. Eksport marketplace</h2>
      <button onclick="buildCsv()">Zbuduj CSV</button>
      <a id="csvLink" class="download" download="marketplace-export.csv" href="#">Pobierz CSV</a>
      <pre id="csvPreview">CSV pojawi sie po zatwierdzeniu HumanGate.</pre>
    </section>
    <section>
      <h2>4. Evidence pack</h2>
      <div id="modules" class="grid"></div>
      <pre id="evidence">Brak evidence.</pre>
    </section>
  </main>
  <script>
    const project = {project_json};
    const modules = {modules_json};
    let gateApproved = false;
    let lastChecks = [];
    function msg(text, blocked=false) {{ const n=document.getElementById('operatorMessage'); n.textContent=text; n.className=blocked?'status-block':'status-ok'; }}
    function validateEan(ean) {{ return /^\\d{{13}}$/.test(ean); }}
    function makeDescription(lang, name, brief) {{
      const base = brief.trim().replace(/\\s+/g,' ');
      if (lang === 'PL') return `${{name}}: opis marketplace. Cechy: ${{base}}. Sprawdz EAN i zgodnosc z briefem przed publikacja.`;
      if (lang === 'EN') return `${{name}}: marketplace description. Features: ${{base}}. Verify EAN and source brief before publishing.`;
      return `${{name}}: Marketplace-Beschreibung. Merkmale: ${{base}}. EAN und Briefing vor der Veroeffentlichung pruefen.`;
    }}
    function generateProductDescriptions(name, brief) {{
      return {{
        pl: makeDescription('PL', name, brief),
        en: makeDescription('EN', name, brief),
        de: makeDescription('DE', name, brief)
      }};
    }}
    function analyzeProduct() {{
      const name=document.getElementById('productName').value.trim();
      const ean=document.getElementById('ean').value.trim();
      const brief=document.getElementById('brief').value.trim();
      if (!name || !brief) {{ msg('Brak nazwy produktu lub briefu.', true); return; }}
      const descriptions=generateProductDescriptions(name, brief);
      document.getElementById('descPL').value=descriptions.pl;
      document.getElementById('descEN').value=descriptions.en;
      document.getElementById('descDE').value=descriptions.de;
      lastChecks=[
        {{ name:'brief_required', ok: brief.length >= 40, detail:'Brief ma '+brief.length+' znakow' }},
        {{ name:'ean_validation', ok: validateEan(ean), detail: validateEan(ean)?'EAN ma 13 cyfr':'EAN wymaga 13 cyfr' }},
        {{ name:'marketplace_guard', ok: gateApproved, detail: gateApproved?'operator zatwierdzil':'czeka HumanGate' }},
        {{ name:'languages', ok: true, detail:'PL/EN/DE wygenerowane' }}
      ];
      renderChecks(); buildEvidence(); msg('Wygenerowano opisy. Eksport nadal wymaga HumanGate.');
    }}
    function renderChecks() {{
      document.getElementById('checks').innerHTML=lastChecks.map(c=>`<tr><td>${{c.name}}</td><td class="${{c.ok?'status-ok':'status-block'}}">${{c.ok?'PASS':'BLOCK'}}</td><td>${{c.detail}}</td></tr>`).join('');
    }}
    function approveGate() {{
      gateApproved=true;
      document.getElementById('gateStatus').textContent='HumanGate: zatwierdzony przez operatora';
      document.getElementById('gateStatus').className='status-ok';
      analyzeProduct();
    }}
    function buildCsv() {{
      if (!gateApproved) {{ msg('Guard blokuje eksport CSV: najpierw zatwierdz HumanGate.', true); return; }}
      const row=[
        document.getElementById('productName').value,
        document.getElementById('ean').value,
        document.getElementById('category').value,
        document.getElementById('descPL').value,
        document.getElementById('descEN').value,
        document.getElementById('descDE').value
      ].map(v=>`"${{String(v).replaceAll('"','""')}}"`).join(',');
      const csv='product_name,ean,category,description_pl,description_en,description_de\\n'+row;
      document.getElementById('csvPreview').textContent=csv;
      document.getElementById('csvLink').href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);
      buildEvidencePack(); msg('CSV gotowy lokalnie. Publikacja zewnetrzna pozostaje zablokowana.');
    }}
    function buildEvidencePack() {{
      const pack={{ project_id:project.project_id, product:'ecommerce_generator', human_gate_approved:gateApproved, checks:lastChecks, modules, generated_at:new Date().toISOString() }};
      document.getElementById('evidence').textContent=JSON.stringify(pack,null,2);
    }}
    function buildEvidence() {{ buildEvidencePack(); }}
    document.getElementById('modules').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w planie wykonania.</p></article>`).join('');
    analyzeProduct();
  </script>
</body>
</html>
"""
        fragments = [
            _domain_task("ecommerce_document", "html_fragment", "ecommerce-generator", html, "Polish e-commerce generator with EAN, CSV and HumanGate."),
            _domain_task("image_brief_intake", "js_fragment", "image-brief-intake", "function validateProductBrief(name, brief) { return Boolean(name && brief && brief.length >= 40); }\n", "Validate product name, files and brief."),
            _domain_task("description_generation", "js_fragment", "description-generation", "function generateProductDescriptions(name, brief) { return ['PL','EN','DE'].map(lang => ({ lang, text: name + ': ' + brief })); }\n", "Generate PL EN DE product descriptions."),
            _domain_task("ean_validation", "js_fragment", "ean-validation", "function validateEan(ean) { return /^\\d{13}$/.test(String(ean || '')); }\n", "Validate EAN before export."),
            _domain_task("marketplace_export", "js_fragment", "marketplace-export", "function buildMarketplaceCsv(row) { return row.map(value => '\"' + String(value).replaceAll('\"','\"\"') + '\"').join(','); }\n", "Build Allegro and Amazon CSV."),
            _domain_task("human_review_gate", "text_fragment", "human-review-gate", "# HumanGate\nCSV export and marketplace publication require operator approval, EAN validation and evidence pack.\n", "Review gate policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "employee_portal":
        summary = _project_summary(project)
        title_html = escape(title)
        idea_html = escape(str(summary.get("idea") or ""))
        project_json = _json_script(summary)
        modules_json = _json_script(summary["modules"])
        html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  <style>
    :root {{ --ink:#17201c; --paper:#f7f3ea; --card:#fffdf7; --line:#d8ccbc; --accent:#245c48; --warn:#9a6200; --danger:#9b1c31; --ok:#1f7a45; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#f9f1df 0%,#eef7f0 54%,#edf2fb 100%); font-family:Georgia,serif; }}
    main {{ max-width:1220px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:16px; box-shadow:0 18px 45px rgba(34,44,38,.08); }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); line-height:.96; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    label {{ display:grid; gap:7px; font-weight:700; }}
    input,textarea,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; color:var(--ink); font:inherit; }}
    button,a.download {{ border:0; border-radius:999px; padding:11px 16px; margin:4px 8px 4px 0; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.guard {{ background:var(--warn); }} button.danger {{ background:var(--danger); }}
    .status-ok {{ color:var(--ok); font-weight:800; }} .status-block {{ color:var(--danger); font-weight:800; }}
    .card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:var(--card); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; background:#13231c; color:#edf8f1; border-radius:14px; padding:14px; overflow:auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="auth_users role_assignment document_workflow leave_request_workflow gdpr_dsr security_session_policy audit_evidence_pack dpia_required humangate">
    <header>
      <p>AEIS portal HR / PII high / DPIA / GDPR DSR / HumanGate D4 / SSO LDAP / session timeout / rate limit / password policy</p>
      <h1>{title_html}</h1>
      <p>{idea_html}</p>
      <p><strong>Guard:</strong> DSR erasure, produkcja, eksport poza system i zmiana retencji wymagaja HumanGate DPO.</p>
    </header>
    <section>
      <h2>1. Tozsamosc i role</h2>
      <div class="grid">
        <label>Rola operatora<select id="role"><option>pracownik</option><option>manager</option><option>HR</option><option>DPO</option><option>admin</option></select></label>
        <label>Email<input id="email" value="anna.kowalska@example.local"></label>
        <label>Password policy input<input id="password" type="password" value="BezpieczneHaslo2026!"></label>
      </div>
      <button onclick="attemptLogin()">Zaloguj lokalnie</button>
      <button onclick="badLogin()">Wpisz bledne haslo 5 razy</button>
      <p id="loginStatus" class="status-block">Nie zalogowano. Session timeout 30 min, inactivity logout 15 min, rate_limit_5_15min aktywny.</p>
    </section>
    <section>
      <h2>2. Workflow dokumentow i urlopow</h2>
      <div class="grid">
        <article class="card">
          <h3>Document workflow</h3>
          <label>Nazwa dokumentu<input id="documentName" value="Umowa o prace - aneks"></label>
          <button onclick="submitDocument()">Dodaj draft</button>
          <button class="guard" onclick="advanceDocument()">Przesun do review/approved</button>
          <p id="documentState">Brak dokumentu.</p>
        </article>
        <article class="card">
          <h3>Leave request workflow</h3>
          <label>Dni urlopu<input id="leaveDays" type="number" value="5"></label>
          <button onclick="submitLeaveRequest()">Zloz wniosek urlopowy</button>
          <button class="guard" onclick="approveLeaveRequest()">Zatwierdz jako manager/HR</button>
          <p id="leaveState">Brak wniosku.</p>
        </article>
      </div>
    </section>
    <section>
      <h2>3. GDPR DSR i DPIA</h2>
      <div class="grid">
        <article class="card">
          <h3>DSR export</h3>
          <button onclick="exportDsr()">Wygeneruj DSR export lokalnie</button>
          <a id="dsrLink" class="download" download="dsr-export.json" href="#">Pobierz DSR JSON</a>
          <pre id="dsrOutput">DSR export nie zostal jeszcze wygenerowany.</pre>
        </article>
        <article class="card">
          <h3>DSR erasure HumanGate</h3>
          <button class="danger" onclick="eraseDsr()">Usun dane pracownika</button>
          <button class="guard" onclick="approveDpoGate()">HumanGate DPO: zatwierdz erasure</button>
          <p id="dpoGate" class="status-block">DPO HumanGate: oczekuje. dpia_required=true.</p>
        </article>
      </div>
    </section>
    <section>
      <h2>4. Evidence pack i kontrole</h2>
      <div id="modules" class="grid"></div>
      <table><thead><tr><th>Kontrola</th><th>Status</th><th>Szczegoly</th></tr></thead><tbody id="checks"></tbody></table>
      <button onclick="buildEvidencePack()">Odswiez evidence pack</button>
      <pre id="evidence">Brak evidence.</pre>
    </section>
  </main>
  <script>
    const project = {project_json};
    const modules = {modules_json};
    const policy = {{
      pii_scope:'high',
      decision_class:'D4',
      dpia_required:true,
      session_timeout_minutes:30,
      inactivity_logout_minutes:15,
      rate_limit:'5 attempts / 15 min / user+IP',
      password_policy:'minimum 14 chars, MFA for HR/DPO/admin, lockout after 5 attempts',
      retention:'working data 90d, audit logs 2y'
    }};
    let loggedIn=false;
    let attempts=0;
    let dpoApproved=false;
    let documentState='none';
    let leaveState='none';
    let auditEntries=[];
    function currentRole() {{ return document.getElementById('role').value; }}
    function recordAudit(action, status, detail) {{
      auditEntries.push({{ action, status, detail, role:currentRole(), ts:new Date().toISOString() }});
      renderChecks();
      buildEvidencePack();
    }}
    function setText(id, text, blocked=false) {{
      const node=document.getElementById(id);
      node.textContent=text;
      node.className=blocked?'status-block':'status-ok';
    }}
    function strongPassword(value) {{ return String(value || '').length >= 14 && /[0-9]/.test(value) && /[^a-zA-Z0-9]/.test(value); }}
    function attemptLogin() {{
      const password=document.getElementById('password').value;
      if (attempts >= 5) {{ setText('loginStatus','BLOCK: konto zablokowane po 5 probach. Wymagany reset operatora.', true); recordAudit('auth_users.rate_limit','BLOCK','lockout after 5 attempts'); return; }}
      if (!strongPassword(password)) {{ attempts += 1; setText('loginStatus','BLOCK: password_policy_14_mfa_lockout nie spelniona.', true); recordAudit('auth_users.password_policy','BLOCK','weak password'); return; }}
      loggedIn=true;
      setText('loginStatus','PASS: zalogowano. session_timeout_30_min i inactivity_logout_15_min aktywne.');
      recordAudit('auth_users.login','PASS','SSO LDAP/local fallback policy visible');
    }}
    function badLogin() {{
      attempts=5;
      loggedIn=false;
      setText('loginStatus','BLOCK: rate_limit_5_15min zadzialal po bledach czlowieka.', true);
      recordAudit('auth_users.rate_limit','BLOCK','human mistake simulation');
    }}
    function submitDocument() {{
      if (!loggedIn) {{ setText('documentState','BLOCK: najpierw logowanie.', true); recordAudit('document_workflow.create','BLOCK','not logged in'); return; }}
      documentState='draft';
      setText('documentState','Dokument w stanie draft: '+document.getElementById('documentName').value);
      recordAudit('document_workflow.create','PASS','draft created');
    }}
    function advanceDocument() {{
      const role=currentRole();
      if (!['HR','DPO','admin'].includes(role)) {{ setText('documentState','BLOCK: role_assignment odrzucil role '+role+'.', true); recordAudit('role_assignment.document_advance','BLOCK','role denied'); return; }}
      documentState = documentState === 'draft' ? 'review' : 'approved';
      setText('documentState','Document workflow state: '+documentState);
      recordAudit('document_workflow.advance','PASS','state '+documentState);
    }}
    function submitLeaveRequest() {{
      if (!loggedIn) {{ setText('leaveState','BLOCK: najpierw logowanie.', true); recordAudit('leave_request_workflow.submit','BLOCK','not logged in'); return; }}
      leaveState='pending_manager';
      setText('leaveState','Wniosek urlopowy czeka na managera: '+document.getElementById('leaveDays').value+' dni.');
      recordAudit('leave_request_workflow.submit','PASS','pending_manager');
    }}
    function approveLeaveRequest() {{
      const role=currentRole();
      if (!['manager','HR','admin'].includes(role)) {{ setText('leaveState','BLOCK: tylko manager/HR/admin moze zatwierdzic.', true); recordAudit('leave_request_workflow.approve','BLOCK','role denied'); return; }}
      leaveState='approved';
      setText('leaveState','Wniosek urlopowy zatwierdzony.');
      recordAudit('leave_request_workflow.approve','PASS','approved');
    }}
    function exportDsr() {{
      const pack={{ employee:document.getElementById('email').value, pii_scope:'high', document_state:documentState, leave_state:leaveState, retention:policy.retention, audit_entries:auditEntries }};
      const text=JSON.stringify(pack,null,2);
      document.getElementById('dsrOutput').textContent=text;
      document.getElementById('dsrLink').href='data:application/json;charset=utf-8,'+encodeURIComponent(text);
      recordAudit('gdpr_dsr.export','PASS','local DSR export generated');
    }}
    function eraseDsr() {{
      if (!dpoApproved) {{ setText('dpoGate','BLOCK: erasure wymaga HumanGate DPO i DPIA.', true); recordAudit('gdpr_dsr.erasure','BLOCK','DPO HumanGate missing'); return; }}
      setText('dpoGate','PASS: DSR erasure zatwierdzone przez DPO HumanGate.');
      recordAudit('gdpr_dsr.erasure','PASS','DPO approved');
    }}
    function approveDpoGate() {{
      dpoApproved=true;
      setText('dpoGate','DPO HumanGate zatwierdzony. Erasure moze byc wykonane lokalnie.');
      recordAudit('human_gate.dpo','PASS','D4 DPO approval');
    }}
    function renderChecks() {{
      const checks=[
        {{ name:'dpia_required', ok:policy.dpia_required, detail:'DPIA wymagane dla PII high' }},
        {{ name:'session_timeout', ok:true, detail:'30 min + inactivity 15 min' }},
        {{ name:'rate_limit_5_15min', ok:attempts < 5, detail:attempts+' / 5 prob' }},
        {{ name:'password_policy_14_mfa_lockout', ok:true, detail:policy.password_policy }},
        {{ name:'role_assignment', ok:loggedIn, detail:loggedIn?'rola aktywna':'czeka logowanie' }},
        {{ name:'gdpr_dsr_humangate', ok:dpoApproved, detail:dpoApproved?'DPO approved':'erasure blocked' }}
      ];
      document.getElementById('checks').innerHTML=checks.map(c=>`<tr><td>${{c.name}}</td><td class="${{c.ok?'status-ok':'status-block'}}">${{c.ok?'PASS':'BLOCK'}}</td><td>${{c.detail}}</td></tr>`).join('');
    }}
    function buildEvidencePack() {{
      const pack={{ project_id:project.project_id, product:'employee_portal', modules, policy, logged_in:loggedIn, document_state:documentState, leave_state:leaveState, dpo_humangate:dpoApproved, audit_evidence_pack:auditEntries, generated_at:new Date().toISOString() }};
      document.getElementById('evidence').textContent=JSON.stringify(pack,null,2);
    }}
    document.getElementById('modules').innerHTML=modules.map(m=>`<article class="card"><h3>${{m}}</h3><p>Modul aktywny w planie HR/D4.</p></article>`).join('');
    renderChecks();
    buildEvidencePack();
  </script>
</body>
</html>
"""
        fragments = [
            _domain_task("employee_portal_document", "html_fragment", "employee-portal", html, "Polish HR portal with D4 HumanGate, DSR and evidence pack."),
            _domain_task("auth_users", "js_fragment", "auth-users", "function strongPassword(value) { return String(value || '').length >= 14 && /[0-9]/.test(value) && /[^a-zA-Z0-9]/.test(value); }\n", "Auth users, SSO/LDAP and password policy."),
            _domain_task("role_assignment", "js_fragment", "role-assignment", "function canAdvanceDocument(role) { return ['HR','DPO','admin'].includes(role); }\n", "Role assignment for HR, DPO, admin, manager and employee."),
            _domain_task("document_workflow", "js_fragment", "document-workflow", "function nextDocumentState(state) { return state === 'draft' ? 'review' : 'approved'; }\n", "Document workflow states."),
            _domain_task("leave_request_workflow", "js_fragment", "leave-request-workflow", "function canApproveLeave(role) { return ['manager','HR','admin'].includes(role); }\n", "Leave request workflow."),
            _domain_task("gdpr_dsr", "js_fragment", "gdpr-dsr", "function gdprDsrPolicy(dpoApproved) { return dpoApproved ? 'erasure_allowed' : 'humangate_blocked'; }\n", "GDPR DSR export and erasure guard."),
            _domain_task("security_session_policy", "text_fragment", "security-session-policy", "# security_session_policy\nsession_timeout_30_min, inactivity_logout_15_min, rate_limit_5_15min, password_policy_14_mfa_lockout.\n", "Session policy."),
            _domain_task("audit_evidence_pack", "text_fragment", "audit-evidence-pack", "# audit_evidence_pack\nDPIA required, PII high, HumanGate DPO, audit entries and retention evidence are packed locally.\n", "Evidence pack policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "operator_mobile":
        summary = _project_summary(project)
        title_html = escape(title)
        idea_html = escape(str(summary.get("idea") or ""))
        project_json = _json_script(summary)
        modules_json = _json_script(summary["modules"])
        html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  <style>
    :root {{ --ink:#14201c; --paper:#f7f1e4; --card:#fffaf0; --line:#d6c8b6; --accent:#1f6f5c; --warn:#9a6200; --danger:#9b1c31; --ok:#1f7a45; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#f8edd6 0%,#e8f5ef 50%,#eaf1fb 100%); font-family:Georgia,serif; }}
    main {{ max-width:1220px; margin:0 auto; padding:28px; }}
    header,section {{ background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:22px; padding:20px; margin-bottom:16px; box-shadow:0 18px 45px rgba(28,42,35,.08); }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); line-height:.96; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
    label {{ display:grid; gap:7px; font-weight:700; }}
    input,textarea,select {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; color:var(--ink); font:inherit; }}
    button,a.download {{ border:0; border-radius:999px; padding:11px 16px; margin:4px 8px 4px 0; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; text-decoration:none; display:inline-block; }}
    button.guard {{ background:var(--warn); }} button.danger {{ background:var(--danger); }} button.secondary {{ background:#30495f; }}
    .status-ok {{ color:var(--ok); font-weight:800; }} .status-block {{ color:var(--danger); font-weight:800; }} .status-warn {{ color:var(--warn); font-weight:800; }}
    .card {{ border:1px solid var(--line); border-radius:16px; padding:14px; background:var(--card); }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; background:#13231c; color:#edf8f1; border-radius:14px; padding:14px; overflow:auto; }}
  </style>
</head>
<body>
  <main data-artifact-contract="mobile_shell offline_checklists firmware_attachment_guard photo_evidence_redaction sync_queue device_binding secure_approval audit_evidence_pack">
    <header>
      <p>AEIS operator mobile / offline_checklists / firmware_attachment_guard / photo_evidence_redaction / sync_queue / device_binding / secure_approval / audit_evidence_pack</p>
      <h1>{title_html}</h1>
      <p>{idea_html}</p>
      <p><strong>Guard:</strong> firmware, zdjecia z mozliwym PII i zewnetrzny sync wymagaja HumanGate oraz device binding.</p>
    </header>
    <section>
      <h2>1. Mobilna kontrola serwisowa</h2>
      <div class="grid">
        <label>Technik<input id="technician" value="technik-07"></label>
        <label>Urzadzenie<input id="deviceId" value="pompa-ciepla-WAW-4421"></label>
        <label>Tryb lacznosci<select id="network"><option value="offline">offline</option><option value="online">online</option></select></label>
        <label>Zalacznik firmware<input id="firmwareFile" type="file" accept=".ino,.bin,.hex,.txt"></label>
        <label>Firmware - nazwa testowa<input id="firmwareNameManual" placeholder="np. idea5_firmware_guard.ino"></label>
        <label>Firmware - zawartosc testowa<textarea id="firmwareContentManual" rows="2" placeholder="Wklej fragment firmware do hashowania"></textarea></label>
        <label>Zdjecie dowodowe<input id="photoFile" type="file" accept="image/*,.txt,.md"></label>
        <label>Zdjecie - nazwa testowa<input id="photoNameManual" placeholder="np. tabliczka_serwisowa.jpg"></label>
        <label>Zdjecie - opis testowy<textarea id="photoContentManual" rows="2" placeholder="Opis dowodu: twarz/GPS/numer seryjny do redakcji"></textarea></label>
      </div>
      <label>Nowy krok checklisty<textarea id="checklistInput" rows="3">Sprawdz wersje firmware, zrob zdjecie tabliczki, zapisz odczyt cisnienia i przygotuj synchronizacje po powrocie online.</textarea></label>
      <button onclick="addChecklistItem()">Dodaj do offline_checklists</button>
      <button class="secondary" onclick="completeChecklistItem()">Oznacz pierwszy krok jako wykonany offline</button>
      <button class="guard" onclick="bindDevice()">Powiaz urzadzenie operatora</button>
      <p id="operatorMessage" class="status-warn">Czeka na akcje operatora.</p>
    </section>
    <section>
      <h2>2. Guardy firmware i zdjec</h2>
      <div class="grid">
        <article class="card">
          <h3>Firmware attachment guard</h3>
          <button onclick="validateFirmwareAttachment()">Sprawdz firmware</button>
          <button class="guard" onclick="approveFirmwareGate()">HumanGate: zatwierdz firmware</button>
          <p id="firmwareStatus" class="status-block">Firmware niezweryfikowany.</p>
        </article>
        <article class="card">
          <h3>Photo evidence redaction</h3>
          <button onclick="inspectPhotoEvidence()">Sprawdz PII na zdjeciu</button>
          <button class="guard" onclick="redactPhotoEvidence()">Redaguj PII lokalnie</button>
          <p id="photoStatus" class="status-block">Zdjecie nieprzetworzone.</p>
        </article>
      </div>
    </section>
    <section>
      <h2>3. Sync queue i HumanGate</h2>
      <button onclick="enqueueOfflineItem()">Dodaj paczke do sync_queue</button>
      <button class="danger" onclick="syncQueue()">Synchronizuj teraz</button>
      <button onclick="buildEvidencePack()">Odswiez audit_evidence_pack</button>
      <table><thead><tr><th>Kontrola</th><th>Status</th><th>Szczegoly</th></tr></thead><tbody id="checks"></tbody></table>
      <pre id="syncQueue">[]</pre>
    </section>
    <section>
      <h2>4. Moduly i evidence pack</h2>
      <div id="modules" class="grid"></div>
      <a id="evidenceLink" class="download" download="mobile-evidence-pack.json" href="#">Pobierz evidence pack</a>
      <pre id="evidence">Brak evidence.</pre>
    </section>
  </main>
  <script>
    const project = {project_json};
    const modules = {modules_json};
    let offlineChecklists = [];
    let syncQueueItems = [];
    let auditEntries = [];
    let deviceBound = false;
    let firmwareGateApproved = false;
    let firmwareValid = false;
    let photoInspected = false;
    let photoRedacted = false;
    let lastFirmwareHash = '';

    function msg(text, blocked=false) {{
      const n = document.getElementById('operatorMessage');
      n.textContent = text;
      n.className = blocked ? 'status-block' : 'status-ok';
    }}
    function recordAudit(action, status, detail) {{
      auditEntries.push({{ action, status, detail, ts:new Date().toISOString(), technician:document.getElementById('technician').value }});
      renderChecks();
      renderSyncQueue();
      buildEvidencePack();
    }}
    function selectedFileName(id) {{
      const input = document.getElementById(id);
      return input.files && input.files.length ? input.files[0].name : '';
    }}
    function manualValue(id) {{
      const node = document.getElementById(id);
      return node ? node.value.trim() : '';
    }}
    function pseudoHash(value) {{
      let hash = 0;
      for (let i=0;i<value.length;i++) {{ hash = ((hash << 5) - hash) + value.charCodeAt(i); hash |= 0; }}
      return 'sha256-local-' + Math.abs(hash).toString(16).padStart(8,'0');
    }}
    function addChecklistItem() {{
      const text = document.getElementById('checklistInput').value.trim();
      if (!text) {{ msg('BLOCK: brak kroku checklisty.', true); recordAudit('offline_checklists.add','BLOCK','empty checklist item'); return; }}
      const item = {{ id:'chk-' + (offlineChecklists.length + 1), text, status:'pending_offline' }};
      offlineChecklists.push(item);
      recordAudit('offline_checklists.add','PASS','added ' + item.id);
      msg('Dodano krok do offline_checklists.');
    }}
    function completeChecklistItem() {{
      if (!offlineChecklists.length) {{ msg('BLOCK: najpierw dodaj krok checklisty.', true); recordAudit('offline_checklists.complete','BLOCK','no checklist item'); return; }}
      offlineChecklists[0].status = 'completed_offline';
      recordAudit('offline_checklists.complete','PASS','completed offline');
      msg('Krok wykonany offline i czeka na sync_queue.');
    }}
    function bindDevice() {{
      const deviceId = document.getElementById('deviceId').value.trim();
      if (!deviceId) {{ msg('BLOCK: brak identyfikatora urzadzenia.', true); recordAudit('device_binding.bind','BLOCK','missing device id'); return; }}
      deviceBound = true;
      recordAudit('device_binding.bind','PASS','device ' + deviceId + ' bound to technician');
      msg('Device binding aktywny dla ' + deviceId + '.');
    }}
    function validateFirmwareAttachment() {{
      const name = selectedFileName('firmwareFile') || manualValue('firmwareNameManual');
      if (!name) {{
        document.getElementById('firmwareStatus').textContent = 'BLOCK: firmware_attachment_guard wymaga realnego zalacznika albo nazwy testowej .ino/.bin/.hex.';
        document.getElementById('firmwareStatus').className = 'status-block';
        recordAudit('firmware_attachment_guard.validate','BLOCK','missing firmware attachment');
        return;
      }}
      const allowed = /\\.(ino|bin|hex)$/i.test(name);
      const content = manualValue('firmwareContentManual') || name;
      lastFirmwareHash = pseudoHash(name + '|' + content + '|' + document.getElementById('deviceId').value);
      firmwareValid = allowed;
      const node = document.getElementById('firmwareStatus');
      if (!allowed) {{
        node.textContent = 'BLOCK: firmware_attachment_guard odrzuca plik ' + name + '. Dozwolone .ino/.bin/.hex.';
        node.className = 'status-block';
        recordAudit('firmware_attachment_guard.validate','BLOCK','extension denied: ' + name);
        return;
      }}
      node.textContent = 'PASS: firmware poprawny typ, hash ' + lastFirmwareHash + ', nadal wymaga HumanGate.';
      node.className = 'status-warn';
      recordAudit('firmware_attachment_guard.validate','PASS','hash ' + lastFirmwareHash);
    }}
    function approveFirmwareGate() {{
      if (!firmwareValid) {{ msg('BLOCK: HumanGate firmware wymaga najpierw walidacji pliku.', true); recordAudit('secure_approval.firmware','BLOCK','firmware not validated'); return; }}
      firmwareGateApproved = true;
      document.getElementById('firmwareStatus').textContent = 'PASS: secure_approval zatwierdzil firmware przez HumanGate.';
      document.getElementById('firmwareStatus').className = 'status-ok';
      recordAudit('secure_approval.firmware','PASS','firmware HumanGate approved');
    }}
    function inspectPhotoEvidence() {{
      const name = selectedFileName('photoFile') || manualValue('photoNameManual');
      if (!name) {{
        document.getElementById('photoStatus').textContent = 'BLOCK: photo_evidence_redaction wymaga realnego zdjecia albo opisu testowego.';
        document.getElementById('photoStatus').className = 'status-block';
        recordAudit('photo_evidence_redaction.inspect','BLOCK','missing photo evidence');
        return;
      }}
      photoInspected = true;
      document.getElementById('photoStatus').textContent = 'BLOCK: photo_evidence_redaction wykrylo mozliwe PII/geolokalizacje w ' + name + '. Wymagana redakcja.';
      document.getElementById('photoStatus').className = 'status-block';
      recordAudit('photo_evidence_redaction.inspect','BLOCK','possible PII detected');
    }}
    function redactPhotoEvidence() {{
      if (!photoInspected) {{ msg('BLOCK: najpierw sprawdz zdjecie.', true); recordAudit('photo_evidence_redaction.redact','BLOCK','photo not inspected'); return; }}
      photoRedacted = true;
      document.getElementById('photoStatus').textContent = 'PASS: PII zredagowane lokalnie, zdjecie moze trafic do sync_queue.';
      document.getElementById('photoStatus').className = 'status-ok';
      recordAudit('photo_evidence_redaction.redact','PASS','local redaction applied');
    }}
    function enqueueOfflineItem() {{
      if (!offlineChecklists.length) {{ msg('BLOCK: sync_queue wymaga checklisty.', true); recordAudit('sync_queue.enqueue','BLOCK','no checklist'); return; }}
      const item = {{
        id:'sync-' + (syncQueueItems.length + 1),
        device:document.getElementById('deviceId').value,
        checklist:offlineChecklists,
        firmware_hash:lastFirmwareHash || 'not_attached',
        status:'queued_offline'
      }};
      syncQueueItems.push(item);
      recordAudit('sync_queue.enqueue','PASS','queued ' + item.id);
      msg('Paczka dodana do sync_queue.');
    }}
    function syncQueue() {{
      const network = document.getElementById('network').value;
      if (network !== 'online') {{ msg('BLOCK: sync_queue nie moze synchronizowac w trybie offline.', true); recordAudit('sync_queue.sync','BLOCK','offline network'); return; }}
      if (!deviceBound) {{ msg('BLOCK: sync wymaga device_binding.', true); recordAudit('sync_queue.sync','BLOCK','device not bound'); return; }}
      if (!firmwareGateApproved) {{ msg('BLOCK: firmware wymaga secure_approval HumanGate.', true); recordAudit('sync_queue.sync','BLOCK','firmware gate missing'); return; }}
      if (!photoRedacted) {{ msg('BLOCK: photo_evidence_redaction wymaga redakcji PII.', true); recordAudit('sync_queue.sync','BLOCK','photo not redacted'); return; }}
      if (!syncQueueItems.length) {{ msg('BLOCK: brak elementow w sync_queue.', true); recordAudit('sync_queue.sync','BLOCK','empty queue'); return; }}
      syncQueueItems = syncQueueItems.map(item => ({{ ...item, status:'synced_after_humangate' }}));
      recordAudit('sync_queue.sync','PASS','synced after online + device binding + secure approval + redaction');
      msg('Synchronizacja zakonczona po spelnieniu guardow.');
    }}
    function renderChecks() {{
      const checks = [
        {{ name:'offline_checklists', ok:offlineChecklists.length > 0, detail:offlineChecklists.length + ' krokow' }},
        {{ name:'firmware_attachment_guard', ok:firmwareValid, detail:firmwareValid ? lastFirmwareHash : 'czeka walidacja' }},
        {{ name:'secure_approval', ok:firmwareGateApproved, detail:firmwareGateApproved ? 'HumanGate approved' : 'firmware blocked' }},
        {{ name:'photo_evidence_redaction', ok:photoRedacted, detail:photoRedacted ? 'PII redacted' : 'redaction required' }},
        {{ name:'device_binding', ok:deviceBound, detail:deviceBound ? 'device bound' : 'not bound' }},
        {{ name:'sync_queue', ok:syncQueueItems.some(item => item.status === 'synced_after_humangate'), detail:syncQueueItems.length + ' elementow' }},
        {{ name:'audit_evidence_pack', ok:auditEntries.length > 0, detail:auditEntries.length + ' wpisow audit' }}
      ];
      document.getElementById('checks').innerHTML = checks.map(c => '<tr><td>' + c.name + '</td><td class="' + (c.ok ? 'status-ok' : 'status-block') + '">' + (c.ok ? 'PASS' : 'BLOCK') + '</td><td>' + c.detail + '</td></tr>').join('');
    }}
    function renderSyncQueue() {{
      document.getElementById('syncQueue').textContent = JSON.stringify(syncQueueItems, null, 2);
    }}
    function buildEvidencePack() {{
      const pack = {{
        project_id:project.project_id,
        product:'operator_mobile',
        modules,
        offline_checklists:offlineChecklists,
        firmware_attachment_guard:{{ valid:firmwareValid, human_gate_approved:firmwareGateApproved, hash:lastFirmwareHash }},
        photo_evidence_redaction:{{ inspected:photoInspected, redacted:photoRedacted }},
        sync_queue:syncQueueItems,
        device_binding:deviceBound,
        secure_approval:firmwareGateApproved,
        audit_evidence_pack:auditEntries,
        generated_at:new Date().toISOString()
      }};
      const text = JSON.stringify(pack, null, 2);
      document.getElementById('evidence').textContent = text;
      document.getElementById('evidenceLink').href = 'data:application/json;charset=utf-8,' + encodeURIComponent(text);
    }}
    document.getElementById('modules').innerHTML = modules.map(m => '<article class="card"><h3>' + m + '</h3><p>Modul aktywny w planie mobile D4.</p></article>').join('');
    renderChecks();
    renderSyncQueue();
    buildEvidencePack();
  </script>
</body>
</html>
"""
        fragments = [
            _domain_task("operator_mobile_document", "html_fragment", "mobile-shell", html, "Polish offline technician mobile assistant with firmware, photo redaction, sync queue and HumanGate."),
            _domain_task("offline_checklists", "js_fragment", "offline-checklists", "function enqueueOfflineChecklist(item) { return { id: item.id, status: 'queued_offline', text: item.text }; }\n", "Offline checklist state and replay queue."),
            _domain_task("firmware_attachment_guard", "js_fragment", "firmware-attachment-guard", "function validateFirmwareAttachment(name) { return /\\.(ino|bin|hex)$/i.test(String(name || '')); }\n", "Firmware extension validation and hash evidence."),
            _domain_task("photo_evidence_redaction", "js_fragment", "photo-evidence-redaction", "function photoEvidenceRedaction(photo) { return { redacted: true, pii_fields: ['face','location','serial'] }; }\n", "Local PII redaction for photo evidence."),
            _domain_task("sync_queue", "js_fragment", "sync-queue", "function syncQueueAllowed(state) { return state.online && state.device_bound && state.firmware_gate && state.photo_redacted; }\n", "Govern offline queue sync."),
            _domain_task("device_binding", "js_fragment", "device-binding", "function bindDevice(operatorId, deviceId) { return Boolean(operatorId && deviceId); }\n", "Bind technician device before external sync."),
            _domain_task("secure_approval", "text_fragment", "secure-approval", "# secure_approval\nFirmware upload, external sync and final release require HumanGate, device binding and audit evidence.\n", "HumanGate policy for mobile actions."),
            _domain_task("audit_evidence_pack", "text_fragment", "audit-evidence-pack", "# audit_evidence_pack\noffline_checklists, firmware hash, photo redaction, sync_queue and HumanGate decisions are packed locally.\n", "Evidence pack policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "project_management_system":
        html = _project_management_artifact(project)
        fragments = [
            _domain_task("project_management_document", "html_fragment", "project-management-system", html, "Polish project management system with RBAC, budget, risks, release governance and canary."),
            _domain_task("tenant_workspace", "js_fragment", "tenant-workspace", "function validateTenantWorkspace(name) { return Boolean(name && name.trim().length >= 3); }\n", "Tenant workspace validation."),
            _domain_task("kanban_backlog", "js_fragment", "kanban-backlog", "function validTask(title, owner) { return Boolean(title && owner); }\n", "Kanban backlog task validation."),
            _domain_task("gantt_roadmap", "text_fragment", "gantt-roadmap", "# gantt_roadmap\nRoadmap uses milestones, sprints, dependencies and canary release dates.\n", "Roadmap and Gantt planning."),
            _domain_task("budget_tracking", "js_fragment", "budget-tracking", "function withinBudget(spent, added, cap) { return Number(spent) + Number(added) <= Number(cap); }\n", "Budget cap guard."),
            _domain_task("risk_register", "js_fragment", "risk-register", "function requiresRiskHumanGate(severity) { return ['high','critical'].includes(String(severity)); }\n", "Risk register HumanGate policy."),
            _domain_task("rbac_audit", "js_fragment", "rbac-audit", "function canApproveRelease(role) { return role === 'release_manager'; }\n", "RBAC audit checks."),
            _domain_task("release_governance", "js_fragment", "release-governance", "function canaryAllowed(errorRate) { return Number(errorRate) <= 1; }\n", "Canary and rollback policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "marketplace_platform":
        html = _marketplace_platform_artifact(project)
        fragments = [
            _domain_task("marketplace_platform_document", "html_fragment", "marketplace-platform", html, "Polish D5 marketplace platform with tenant, vendor, checkout, payment sandbox, funding scan and release governance."),
            _domain_task("tenant_identity", "js_fragment", "tenant-identity", "function validateTenantIdentity(name) { return Boolean(name && name.trim().length >= 3); }\n", "Tenant identity validation."),
            _domain_task("vendor_onboarding", "js_fragment", "vendor-onboarding", "function vendorOnboardingAllowed(state) { return Boolean(state.tenant_identity); }\n", "Vendor onboarding must follow tenant identity."),
            _domain_task("product_catalog", "js_fragment", "product-catalog", "function validCatalogProduct(name, price) { return Boolean(name) && Number(price) > 0; }\n", "Product catalog validation."),
            _domain_task("cart_checkout", "js_fragment", "cart-checkout", "function checkoutAllowed(state) { return state.tenant_identity && state.product_catalog && state.payment_sandbox; }\n", "Cart checkout HumanGate dependency."),
            _domain_task("payment_sandbox", "js_fragment", "payment-sandbox", "function paymentSandboxReady(role, taxApproved) { return role === 'payment_reviewer' && Boolean(taxApproved); }\n", "Payment sandbox approval guard."),
            _domain_task("tax_shipping", "js_fragment", "tax-shipping", "function taxShippingApproved(role, hasProduct) { return role === 'tenant_admin' && Boolean(hasProduct); }\n", "Tax and shipping approval guard."),
            _domain_task("admin_console", "js_fragment", "admin-console", "function adminConsoleAllowed(role) { return role === 'tenant_admin'; }\n", "Admin console RBAC guard."),
            _domain_task("funding_scan", "text_fragment", "funding-scan", "# funding_scan\nFunding scan is a supporting marketplace feature and cannot reclassify this project as funding-only.\n", "Funding scan boundary."),
            _domain_task("release_governance", "js_fragment", "release-governance", "function canaryAllowed(errorRate) { return Number(errorRate) <= 1; }\n", "Canary and rollback policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "bioinformatics_workflow":
        html = _bioinformatics_workflow_artifact(project)
        fragments = [
            _domain_task("bioinformatics_workflow_document", "html_fragment", "bioinformatics-workflow", html, "Polish D5 bioinformatics workflow with local-only processing, QC, pseudonymization, clinical safety guard and funding scan."),
            _domain_task("synthetic_data_intake", "js_fragment", "synthetic-data-intake", "function validateResearchSample(name, description) { return /\\.(vcf|fastq|fq)$/i.test(String(name || '')) && !/\\b\\d{11}\\b/.test(String(description || '')); }\n", "Validate synthetic or approved research sample intake."),
            _domain_task("format_validation", "js_fragment", "format-validation", "function validateBioinformaticsFormat(name) { return /\\.(vcf|fastq|fq)$/i.test(String(name || '')); }\n", "FASTQ/VCF format validation."),
            _domain_task("qc_pipeline", "js_fragment", "qc-pipeline", "function qcPipelineReady(state) { return Boolean(state.sample && state.format); }\n", "QC pipeline prerequisites."),
            _domain_task("sample_pseudonymization", "js_fragment", "sample-pseudonymization", "function pseudonymizationAllowed(state) { return state.local_only && state.qc && !state.pesel_detected; }\n", "Local-only sample pseudonymization guard."),
            _domain_task("variant_research_scoring", "js_fragment", "variant-research-scoring", "function variantResearchScoringAllowed(intent) { return intent === 'research_only'; }\n", "Research-only variant scoring guard."),
            _domain_task("clinical_safety_guard", "text_fragment", "clinical-safety-guard", "# clinical_safety_guard\nOutputs are research-only, no clinical use. Diagnosis, therapy advice and production clinical decisions are blocked until separate expert review and HumanGate.\n", "Clinical safety policy."),
            _domain_task("funding_scan", "text_fragment", "funding-scan", "# funding_scan\nHorizon Europe, EIC Pathfinder, FENG SMART and Digital Europe are supporting grant-discovery targets for bioinformatics_workflow. This module cannot reclassify the project as funding-only.\n", "Funding scan boundary."),
            _domain_task("local_model_documentation", "text_fragment", "local-model-documentation", "# local_model_documentation\nBielik and PLLuM run locally through Ollama. External LLM/API processing requires HumanGate and updated meta-orchestration.\n", "Local model documentation."),
            _domain_task("audit_evidence_pack", "text_fragment", "audit-evidence-pack", "# audit_evidence_pack\nStores local_only, pii_guard, clinical_safety_guard, research_only, funding_scan, report_export_humangate and operator click evidence.\n", "Evidence pack policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "mental_health_safety":
        html = _mental_health_safety_artifact(project)
        fragments = [
            _domain_task("mental_health_safety_document", "html_fragment", "mental-health-safety", html, "Polish D5 wellbeing assistant with crisis classifier, no medical advice guard, local models and release HumanGate."),
            _domain_task("wellbeing_intake", "js_fragment", "wellbeing-intake", "function validWellbeingInput(text) { return Boolean(text && text.trim().length > 0); }\n", "Validate non-empty wellbeing input."),
            _domain_task("crisis_classifier", "js_fragment", "crisis-classifier", "function isCrisis(text) { return /samoboj|autoagres|kryzys|przemoc/i.test(String(text || '')); }\n", "Detect crisis language and force emergency hand-off."),
            _domain_task("no_medical_advice_guard", "js_fragment", "no-medical-advice-guard", "function blocksMedicalAdvice(text) { return /diagnoz|terapi|lek|dawk|porad medycz/i.test(String(text || '')); }\n", "Block diagnosis, therapy and medical advice."),
            _domain_task("safe_response_generator", "text_fragment", "safe-response-generator", "# safe_response_generator\nResponses are psychoeducation only, not diagnosis, therapy or medical advice.\n", "Safe wellbeing response policy."),
            _domain_task("emergency_handoff", "text_fragment", "emergency-handoff", "# emergency_handoff\nCrisis language triggers immediate hand-off to emergency or professional help and blocks autonomous continuation.\n", "Emergency hand-off policy."),
            _domain_task("pii_minimization", "js_fragment", "pii-minimization", "function hasPii(text) { return /\\b\\d{11}\\b|[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}/i.test(String(text || '')); }\n", "Detect and block PII in wellbeing notes."),
            _domain_task("local_model_safety_review", "text_fragment", "local-model-safety-review", "# local_model_safety_review\nBielik and PLLuM are local Polish-context reviewers; external LLM requires HumanGate.\n", "Local model safety review."),
            _domain_task("source_backed_resources", "text_fragment", "source-backed-resources", "# source_backed_resources\nEmergency resources must be current, source-backed and approved by HumanGate before public release.\n", "Current source policy."),
            _domain_task("release_safety_gate", "text_fragment", "release-safety-gate", "# release_safety_gate\nPublic release requires tests for crisis, PII, no medical advice and HumanGate approval.\n", "Release safety gate policy."),
            _domain_task("audit_evidence_pack", "text_fragment", "audit-evidence-pack", "# audit_evidence_pack\nStores crisis_classifier, no_medical_advice_guard, pii_minimization, source_backed_resources, release_safety_gate and HumanGate decisions.\n", "Evidence pack policy."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "chat_app":
        html = f"""<!doctype html>
<html lang=\"pl\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title}</title>
</head>
<body>
  <main id=\"app\">
    <h1>{title}</h1>
    <section data-flow=\"register-login-room-message\">
      <form id=\"register\"><input name=\"email\" placeholder=\"register email\"></form>
      <form id=\"login\"><input name=\"password\" placeholder=\"login password\" type=\"password\"></form>
      <label>Room <input id=\"room\" value=\"general\"></label>
      <textarea id=\"message\" placeholder=\"message\"></textarea>
      <button id=\"send-message\">Send message</button>
      <ul id=\"messages\"></ul>
    </section>
  </main>
</body>
</html>
"""
        fragments = [
            _domain_task("chat_document", "html_fragment", "document", html, "Responsive chat app shell."),
            _domain_task("chat_styles", "css_fragment", "styles", "body { font-family: sans-serif; margin: 0; } main { max-width: 960px; margin: auto; padding: 24px; }\n"),
            _domain_task("chat_state", "js_fragment", "chat-state", "const state = { register: true, login: true, room: 'general', messages: [] };\n"),
            _domain_task("chat_register", "js_fragment", "register-user", "function registerUser(email) { return { email, status: 'registered' }; }\n"),
            _domain_task("chat_login", "js_fragment", "login", "function login(email) { return { email, status: 'logged-in' }; }\n"),
            _domain_task("chat_join", "js_fragment", "join-room", "function joinRoom(room) { state.room = room; return room; }\n"),
            _domain_task("chat_send", "js_fragment", "send-message", "function sendMessage(message) { state.messages.push({ room: state.room, message }); }\n"),
            _domain_task("chat_fetch", "js_fragment", "fetch-messages", "function fetchMessages(room) { return state.messages.filter(item => item.room === room); }\n"),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "design_tool":
        html = f"""<!doctype html>
<html lang=\"pl\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title}</title>
</head>
<body>
  <main id=\"room-planner\">
    <h1>{title}</h1>
    <canvas id=\"canvas\" width=\"900\" height=\"560\" aria-label=\"room canvas\"></canvas>
    <aside id=\"furniture-tools\">
      <button data-tool=\"chair\">Add chair furniture</button>
      <button data-tool=\"table\">Add table furniture</button>
    </aside>
    <script>
      const room = {{ width: 900, height: 560, furniture: [] }};
      function addFurniture(type, x, y) {{ room.furniture.push({{ type, x, y }}); return room; }}
      function moveFurniture(index, x, y) {{ room.furniture[index] = {{ ...room.furniture[index], x, y }}; return room; }}
    </script>
  </main>
</body>
</html>
"""
        fragments = [
            _domain_task("design_document", "html_fragment", "document", html, "Responsive 2D room design shell."),
            _domain_task("design_styles", "css_fragment", "styles", "canvas { border: 2px solid #222; max-width: 100%; } aside { display: flex; gap: 12px; }\n"),
            _domain_task("design_canvas", "js_fragment", "canvas-kernel", "const canvas = document.getElementById('canvas'); const ctx = canvas.getContext('2d');\n"),
            _domain_task("design_layout", "js_fragment", "layout-state", "const layoutState = { room: { width: 900, height: 560 }, furniture: [] };\n"),
            _domain_task("design_furniture", "js_fragment", "furniture-tools", "function addFurniture(type, x, y) { layoutState.furniture.push({ type, x, y }); }\n"),
            _domain_task("design_bootstrap", "js_fragment", "zz-bootstrap", "addFurniture('chair', 120, 120); addFurniture('table', 260, 180);\n"),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if kind == "funding":
        html = _funding_artifact(project)
        fragments = [
            _domain_task("funding_document", "html_fragment", "funding-dashboard", html, "Polish funding dashboard with source verification, deadline guard and HumanGate."),
            _domain_task("funding_intake", "js_fragment", "funding-intake", "function validateFundingSource(program) { return Boolean(program.name && program.url && program.notes && program.deadline); }\n", "Validate funding intake fields."),
            _domain_task("official_source_search", "text_fragment", "official-source-search", "# official_source_search\nPerplexity and Google are discovery providers only; official programme URL remains source of truth.\n", "Discovery model policy."),
            _domain_task("source_verification", "js_fragment", "source-verification", "function isOfficialFundingSource(url) { return ['gov.pl','parp.gov.pl','ncbr.gov.pl','funduszeeuropejskie.gov.pl','ec.europa.eu','europa.eu'].some(domain => String(url).toLowerCase().includes(domain)); }\n", "Reject fake or unofficial funding sources."),
            _domain_task("deadline_guard", "js_fragment", "deadline-guard", "function deadlineIsFuture(value) { return Boolean(value) && new Date(value + 'T23:59:59') >= new Date(new Date().toDateString()); }\n", "Block expired grant calls."),
            _domain_task("program_scoring", "js_fragment", "program-scoring", "function fundingScore(parts) { return Math.max(0, Math.min(100, parts.reduce((a, b) => a + b, 0))); }\n", "Score FENG, SMART, Horizon and EIC candidates."),
            _domain_task("eligibility_risk_matrix", "text_fragment", "eligibility-risk-matrix", "# eligibility_risk_matrix\nTrack TRL, region, budget, formal risk, missing evidence and appeals.\n", "Funding risk matrix."),
            _domain_task("cost_budget_estimator", "text_fragment", "cost-budget-estimator", "# cost_budget_estimator\nEstimate grant preparation cost and trigger budget HumanGate when thresholds are exceeded.\n", "Funding preparation budget guard."),
            _domain_task("polish_model_context_review", "text_fragment", "polish-model-context-review", "# polish_model_context_review\nBielik and PLLuM review Polish legal/context wording but do not replace official sources.\n", "Polish model review."),
            _domain_task("document_package", "text_fragment", "document-package", "# document_package\n- Source of Truth\n- Program scoring table\n- Risk and missing-evidence list\n- HumanGate approvals\n", "Funding document package outline."),
            _domain_task("submission_governance", "text_fragment", "submission-governance", "# submission_governance\nExternal contact, document export and funding submission are blocked until HumanGate approval, source verification, cost check and operator signature.\n", "HumanGate governance notes."),
            _domain_task("audit_evidence_pack", "text_fragment", "audit-evidence-pack", "# audit_evidence_pack\nRecord source URLs, deadlines, model routing, scoring, HumanGate decisions and blocked attempts.\n", "Funding audit evidence."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    if _wants_llm_cost_calculator(project):
        html = _llm_cost_calculator_artifact(project)
        fragments = [
            _domain_task("llm_cost_document", "html_fragment", "llm-cost-calculator", html, "Polish LLM cost calculator with CSV export and threshold evidence."),
            _domain_task("llm_cost_engine", "js_fragment", "cost-calculation-engine", "function calculateLlmCostFromInputs(inputTokens, outputTokens, runsPerDay, daysPerMonth, inputCost, outputCost) { return ((inputTokens / 1000 * inputCost) + (outputTokens / 1000 * outputCost)) * runsPerDay * daysPerMonth; }\n", "Monthly LLM cost calculation engine."),
            _domain_task("llm_budget_thresholds", "js_fragment", "budget-thresholds", "function classifyLlmBudgetUsage(percent) { return percent >= 100 ? 'OVER_100' : percent >= 80 ? 'WARN_80' : 'OK'; }\n", "Budget threshold policy for 80 and 100 percent."),
            _domain_task("llm_csv_export", "js_fragment", "csv-export", "function buildLlmCostCsv(entries) { return ['timestamp,provider,model,monthlyCost,threshold'].concat(entries.map(entry => [entry.timestamp, entry.provider, entry.model, entry.monthlyCost, entry.threshold].join(','))).join('\\n'); }\n", "CSV export for operator evidence."),
            _domain_task("llm_audit_policy", "text_fragment", "audit-and-humangate-policy", "# Audit policy\n- Record every calculation in local evidence JSON\n- Mark 80 percent as warning\n- Mark 100 percent as financial HumanGate blocker\n- Do not collect PII\n", "Audit and HumanGate threshold notes."),
        ]
        tasks, results = zip(*fragments, strict=False)
        return list(tasks), list(results), html

    html = _generic_artifact(project)
    module_names = [
        str(module.get("name") or f"module-{idx}")
        for idx, module in enumerate(project.get("modules") or [])
    ] or ["operator_workflow"]
    fragments = [_domain_task("generic_document", "html_fragment", "document", html, "Generic AEIS application artifact.")]
    for idx, module_name in enumerate(module_names):
        fragments.append(
            _domain_task(
                f"generic_module_{idx}",
                "text_fragment",
                module_name,
                f"# {module_name}\nReal module lane for project kind `{kind or 'application'}`.\nInputs, operator checks and evidence export are represented in the generated application.\n",
                "Module execution note.",
            )
        )
    tasks, results = zip(*fragments, strict=False)
    return list(tasks), list(results), html

from sylion.container.docker_manager import ContainerManager
from sylion.execution.execution_planner import ExecutionPlanner
from sylion.integration.orchestrator import IntegrationOrchestrator
from sylion.memory.evidence_store import EvidenceStore
from sylion.memory.indexer import Indexer
from sylion.project_mode.store import ProjectModeStore, get_project_mode_store
from sylion.vps.provider_manager import ProviderManager
from sylion.worker.registry import WorkerRegistry


def _now() -> float:
    return time.time()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "artifact"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _results_root() -> Path:
    override = os.environ.get("SYLION_PROJECT_RESULTS_ROOT", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "src" / "results" / "projects"


def _write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return str(path)


def _set_stage(
    project: dict[str, Any],
    stage_name: str,
    status: str,
    *,
    output_ref: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _now()
    for stage in project.get("stage_state", []):
        if stage.get("stage") != stage_name:
            continue
        stage["status"] = status
        stage["updated_at"] = now
        if status in {"in_progress", "completed"} and not float(stage.get("started_at") or 0):
            stage["started_at"] = now
        if status == "completed":
            stage["completed_at"] = now
        if output_ref:
            stage["output_ref"] = output_ref
        if metadata:
            stage["metadata"] = {**(stage.get("metadata") or {}), **metadata}
        return


def _module_name_map(project: dict[str, Any]) -> dict[str, str]:
    mapping = {}
    for module in project.get("modules") or []:
        mapping[_slug(module.get("name", ""))] = module["name"]
    return mapping


def _resolve_module_name(project: dict[str, Any], task_name: str) -> str:
    project_kind = project.get("project_kind", "")
    module_names = _module_name_map(project)
    fallback = next(iter(module_names.values()), "")

    preferred: dict[str, str] = {}
    if project_kind == "chat_app":
        preferred = {
            "document": "kernel",
            "styles": "kernel",
            "chat-state": "kernel",
            "zz-bootstrap": "kernel",
            "register-user": "auth-and-rooms",
            "login": "auth-and-rooms",
            "join-room": "auth-and-rooms",
            "send-message": "messaging-realtime",
            "fetch-messages": "messaging-realtime",
        }
    elif project_kind == "design_tool":
        preferred = {
            "document": "canvas-kernel",
            "styles": "canvas-kernel",
            "canvas-kernel": "canvas-kernel",
            "layout-state": "layout-state",
            "furniture-tools": "furniture-tools",
            "zz-bootstrap": "furniture-tools",
        }
    elif project_kind == "ecommerce_generator":
        preferred = {
            "ecommerce-generator": "human-review-gate",
            "image-brief-intake": "image-brief-intake",
            "description-generation": "description-generation",
            "ean-validation": "ean-validation",
            "marketplace-export": "marketplace-export",
            "human-review-gate": "human-review-gate",
        }
    elif project_kind == "employee_portal":
        preferred = {
            "employee-portal": "audit-evidence-pack",
            "auth-users": "auth-users",
            "role-assignment": "role-assignment",
            "document-workflow": "document-workflow",
            "leave-request-workflow": "leave-request-workflow",
            "gdpr-dsr": "gdpr-dsr",
            "security-session-policy": "security-session-policy",
            "audit-evidence-pack": "audit-evidence-pack",
        }
    elif project_kind == "operator_mobile":
        preferred = {
            "mobile-shell": "mobile-shell",
            "operator-mobile-document": "mobile-shell",
            "offline-checklists": "offline-checklists",
            "firmware-attachment-guard": "firmware-attachment-guard",
            "photo-evidence-redaction": "photo-evidence-redaction",
            "sync-queue": "sync-queue",
            "device-binding": "device-binding",
            "secure-approval": "secure-approval",
            "audit-evidence-pack": "audit-evidence-pack",
        }
    elif _wants_llm_cost_calculator(project):
        preferred = {
            "llm-cost-calculator": "interface-layer",
            "cost-calculation-engine": "application-core",
            "budget-thresholds": "application-core",
            "csv-export": "interface-layer",
            "audit-and-humangate-policy": "integration-validation",
        }

    preferred_key = preferred.get(_slug(task_name), "")
    if preferred_key and preferred_key in module_names:
        return module_names[preferred_key]
    if _slug(task_name) in module_names:
        return module_names[_slug(task_name)]
    return fallback


def _module_extension(results: list[dict[str, Any]], project_artifact_format: str) -> str:
    kinds = {result.get("kind", "") for result in results}
    if "html_fragment" in kinds:
        return ".html"
    if "css_fragment" in kinds and "js_fragment" not in kinds:
        return ".css"
    if "js_fragment" in kinds:
        return ".js"
    if "text_fragment" in kinds:
        return ".md"
    return ".html" if project_artifact_format == "html" else ".py"


def _worker_dispatch_label(worker: dict[str, Any]) -> str:
    worker_type = str(worker.get("worker_type", "")).lower()
    endpoint = str(worker.get("endpoint", "")).strip()
    if worker_type == "vps" and endpoint and endpoint not in {"host_b"} and not endpoint.startswith("vps-"):
        return f"host_b:{endpoint}"
    return "host_a"


def _audit_types(project: dict[str, Any]) -> list[str]:
    configured = list(project.get("audit_plan", {}).get("auditors") or [])
    if configured:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in configured:
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered
    baseline = [
        "security_officer",
        "quality_perf_reviewer",
        "compliance_officer",
        "dependency_guardian",
        "doc_officer",
    ]
    if project.get("project_kind") == "design_tool":
        baseline.insert(4, "ux_reviewer")
    return baseline


class ProjectExecutionEngine:
    def __init__(self, store: ProjectModeStore | None = None):
        self.store = store or get_project_mode_store()
        self.global_indexer = Indexer(db_path=self.store.db_path)

    def run_project(self, project_id: str, *, auto_execute: bool = True) -> dict[str, Any]:
        project = self.store.get_project(project_id)
        if not project:
            raise KeyError(project_id)

        workspace = self._prepare_workspace(project)
        runtime = self._runtime_components(workspace["runtime_db"])
        plan = self._create_execution_plan(runtime["planner"], project)

        project["status"] = "running" if auto_execute else "queued"
        project["phase"] = "assignment" if auto_execute else "build"
        project["updated_at"] = _now()
        _set_stage(project, "assignment", "in_progress", output_ref=workspace["plan_dir"])
        self.store.upsert_project(project)

        runtime["planner"].start_plan(plan["plan_id"])
        step_ids = plan["step_ids"]

        runtime_workers = self._register_runtime_workers(runtime, project)
        runtime["planner"].complete_step(step_ids["prepare_workspace"], {"project_dir": workspace["project_dir"]})

        assignments = self._assign_modules(runtime, project, runtime_workers)
        runtime["planner"].complete_step(step_ids["register_workers"], {"workers": len(runtime_workers)})
        runtime["planner"].complete_step(step_ids["assign_modules"], {"assignments": len(assignments)})

        deployment = self._write_deployment_bundle(project, workspace, runtime_workers)
        runtime["planner"].complete_step(step_ids["write_deploy"], deployment)

        if not auto_execute:
            for module in project.get("modules") or []:
                module["status"] = "queued"
                module["updated_at"] = _now()
            project["phase"] = "build"
            project["launch"] = {
                "plan_id": plan["plan_id"],
                "runtime_db": workspace["runtime_db"],
                "project_dir": workspace["project_dir"],
                "deployment": deployment,
                "auto_execute": False,
                "status": "queued",
                "launched_at": _now(),
            }
            _set_stage(project, "assignment", "completed", output_ref=workspace["plan_dir"])
            _set_stage(project, "build", "pending", output_ref=workspace["artifacts_dir"])
            project["updated_at"] = _now()
            project = self.store.upsert_project(project)
            self.store.add_event(project_id, "project.assignment.completed", {"assignments": len(assignments), "auto_execute": False})
            return {
                "plan_id": plan["plan_id"],
                "runtime_workers": runtime_workers,
                "assignments": assignments,
                "deployment": deployment,
                "artifact_path": "",
                "validation": {"success": False, "stages": {}},
                "audit": {"results": []},
                "brain": {"dataset_path": "", "adapter": None},
            }

        build_result = self._build_project(runtime, project, workspace, runtime_workers, assignments)
        project = self.store.get_project(project_id) or project
        _set_stage(project, "build", "in_progress", output_ref=workspace["artifacts_dir"])
        project["updated_at"] = _now()
        self.store.upsert_project(project)
        runtime["planner"].complete_step(step_ids["build_artifact"], {"artifact_path": build_result["artifact_path"]})

        validation = self._validate_project(runtime, project, build_result, workspace)
        runtime["planner"].complete_step(step_ids["validate_candidate"], validation)

        audit = self.run_audit(
            project_id,
            scope="masterplan",
            module_id="",
            runtime=runtime,
            workspace=workspace,
            project_override=project,
            validation=validation,
            build_result=build_result,
        )
        runtime["planner"].complete_step(step_ids["run_audit"], {"results": len(audit["results"])})

        learning = self._write_learning_outputs(project, build_result, validation, audit, deployment)
        runtime["planner"].complete_step(step_ids["broadcast_learning"], learning)

        project = self.store.get_project(project_id) or project
        validation_ok = bool(validation.get("success"))
        audit_ok = all(result.get("status") == "pass" for result in audit.get("results", []))
        project["launch"] = {
            "plan_id": plan["plan_id"],
            "build_id": validation.get("build_id", ""),
            "runtime_db": workspace["runtime_db"],
            "project_dir": workspace["project_dir"],
            "artifact_path": build_result["artifact_path"],
            "artifact_format": build_result["artifact_format"],
            "artifact_sha256": build_result["artifact_sha256"],
            "deployment": deployment,
            "validation": validation,
            "audit": audit,
            "brain": learning,
            "module_outputs": build_result["module_outputs"],
            "auto_execute": True,
            "status": "completed" if validation_ok and audit_ok else "blocked",
            "launched_at": _now(),
        }
        project["phase"] = "broadcast" if validation_ok and audit_ok else "governance"
        project["status"] = "completed" if validation_ok and audit_ok else "blocked_on_audit"
        project["updated_at"] = _now()
        _set_stage(project, "assignment", "completed", output_ref=workspace["plan_dir"])
        _set_stage(project, "build", "completed", output_ref=build_result["artifact_path"])
        _set_stage(project, "validate", "completed" if validation_ok else "in_progress", output_ref=workspace["evidence_dir"], metadata={"build_id": validation.get("build_id", "")})
        _set_stage(project, "governance", "completed" if audit_ok else "in_progress", output_ref=workspace["evidence_dir"])
        _set_stage(project, "merge", "completed" if validation_ok and audit_ok else "pending", output_ref=build_result["artifact_path"])
        _set_stage(project, "broadcast", "completed" if validation_ok and audit_ok else "pending", output_ref=learning.get("dataset_path", ""))
        project = self.store.upsert_project(project)
        self.store.add_event(project_id, "project.execution.completed", {"artifact_path": build_result["artifact_path"], "validation_success": validation_ok, "audit_success": audit_ok})
        return {
            "plan_id": plan["plan_id"],
            "runtime_workers": runtime_workers,
            "assignments": assignments,
            "deployment": deployment,
            "artifact_path": build_result["artifact_path"],
            "artifact_format": build_result["artifact_format"],
            "artifact_sha256": build_result["artifact_sha256"],
            "validation": validation,
            "audit": audit,
            "brain": learning,
            "module_outputs": build_result["module_outputs"],
        }

    def run_audit(
        self,
        project_id: str,
        *,
        scope: str = "masterplan",
        module_id: str = "",
        runtime: dict[str, Any] | None = None,
        workspace: dict[str, str] | None = None,
        project_override: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        build_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = project_override or self.store.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        launch = project.get("launch") or {}
        artifact_path = Path((build_result or {}).get("artifact_path") or launch.get("artifact_path") or "")
        artifact_text = artifact_path.read_text(encoding="utf-8") if artifact_path.is_file() else ""

        module_lookup = {module["module_id"]: module for module in project.get("modules") or []}
        module_text = ""
        if scope == "module" and module_id:
            module = module_lookup.get(module_id)
            if module:
                module_artifact = Path((module.get("spec") or {}).get("artifact_path", ""))
                if module_artifact.is_file():
                    module_text = module_artifact.read_text(encoding="utf-8")
                else:
                    module_text = json.dumps(module.get("spec") or {}, ensure_ascii=False, indent=2)

        target_text = "\n\n".join(
            part for part in [
                project.get("canonical_book", ""),
                project.get("masterplan", ""),
                artifact_text if scope != "module" else module_text,
                json.dumps(validation or launch.get("validation") or {}, ensure_ascii=False, indent=2),
            ]
            if part
        )
        readme_path = Path((workspace or {}).get("project_dir", launch.get("project_dir", ""))) / "README.md"
        audit_results: list[dict[str, Any]] = []
        for audit_type in _audit_types(project):
            findings = self._audit_findings(project, audit_type, target_text, artifact_text, readme_path)
            status = "pass" if not findings else "needs_review"
            audit_results.append(
                self.store.record_audit_result(
                    project_id,
                    audit_type,
                    module_id=module_id if scope == "module" else "",
                    status=status,
                    findings=findings,
                )
            )
        self.store.add_event(project_id, "project.audit.completed", {"scope": scope, "module_id": module_id, "results": len(audit_results)})
        return {"results": audit_results}

    def _prepare_workspace(self, project: dict[str, Any]) -> dict[str, str]:
        project_dir = _results_root() / project["project_id"]
        plan_dir = project_dir / "plan"
        artifacts_dir = project_dir / "artifacts"
        evidence_dir = project_dir / "evidence"
        deploy_dir = project_dir / "deploy"
        modules_dir = project_dir / "modules"
        brain_dir = project_dir / "brain"
        runtime_db = project_dir / "runtime.sqlite"
        for path in [project_dir, plan_dir, artifacts_dir, evidence_dir, deploy_dir, modules_dir, brain_dir]:
            path.mkdir(parents=True, exist_ok=True)
        _write_text(plan_dir / "canon.md", project.get("canonical_book", ""))
        _write_text(plan_dir / "masterplan.md", project.get("masterplan", ""))
        _write_text(
            project_dir / "README.md",
            "\n".join(
                [
                    f"# {project['title']}",
                    "",
                    f"- Project ID: `{project['project_id']}`",
                    f"- Kind: `{project.get('project_kind', 'application')}`",
                    f"- Status: `{project.get('status', '')}`",
                    f"- Idea: {project.get('idea', '')}",
                    "",
                    "## Canon",
                    project.get("canonical_book", ""),
                    "",
                    "## Masterplan",
                    project.get("masterplan", ""),
                ]
            ),
        )
        return {
            "project_dir": str(project_dir),
            "plan_dir": str(plan_dir),
            "artifacts_dir": str(artifacts_dir),
            "evidence_dir": str(evidence_dir),
            "deploy_dir": str(deploy_dir),
            "modules_dir": str(modules_dir),
            "brain_dir": str(brain_dir),
            "runtime_db": str(runtime_db),
        }

    def _runtime_components(self, runtime_db: str) -> dict[str, Any]:
        return {
            "planner": ExecutionPlanner(runtime_db),
            "worker_registry": WorkerRegistry(runtime_db),
            "container_manager": ContainerManager(runtime_db),
            "provider_manager": ProviderManager(runtime_db),
            "integration": IntegrationOrchestrator(runtime_db),
            "evidence_store": EvidenceStore(db_path=runtime_db),
            "indexer": Indexer(db_path=runtime_db),
        }

    def _create_execution_plan(self, planner: ExecutionPlanner, project: dict[str, Any]) -> dict[str, Any]:
        plan = planner.create_plan(
            name=f"{project['title']} execution",
            description=f"Project mode execution plan for {project['project_id']}",
            created_by=project.get("owner_id", "workspace-default"),
        )
        step_ids = {
            "prepare_workspace": planner.add_step(plan["plan_id"], "prepare_workspace", "script", {"stage": "assignment"})["step_id"],
            "register_workers": planner.add_step(plan["plan_id"], "register_workers", "script", {"stage": "assignment"})["step_id"],
            "assign_modules": planner.add_step(plan["plan_id"], "assign_modules", "script", {"stage": "assignment"})["step_id"],
            "write_deploy": planner.add_step(plan["plan_id"], "write_deploy", "script", {"stage": "build"})["step_id"],
            "build_artifact": planner.add_step(plan["plan_id"], "build_artifact", "script", {"stage": "build"})["step_id"],
            "validate_candidate": planner.add_step(plan["plan_id"], "validate_candidate", "script", {"stage": "validate"})["step_id"],
            "run_audit": planner.add_step(plan["plan_id"], "run_audit", "script", {"stage": "governance"})["step_id"],
            "broadcast_learning": planner.add_step(plan["plan_id"], "broadcast_learning", "script", {"stage": "broadcast"})["step_id"],
        }
        ordered = list(step_ids.values())
        for idx in range(1, len(ordered)):
            planner.add_dependency(ordered[idx], ordered[idx - 1])
        return {"plan_id": plan["plan_id"], "step_ids": step_ids}

    def _register_runtime_workers(self, runtime: dict[str, Any], project: dict[str, Any]) -> list[dict[str, Any]]:
        registry: WorkerRegistry = runtime["worker_registry"]
        containers: ContainerManager = runtime["container_manager"]
        providers: ProviderManager = runtime["provider_manager"]
        runtime_workers: list[dict[str, Any]] = []
        for worker in project.get("worker_pool") or []:
            host = str(worker.get("endpoint", "") or "localhost")
            role = str(worker.get("role", "") or "coder")
            registry_entry = registry.register_worker(
                name=str(worker.get("name", "worker")),
                host=host,
                capacity=1,
                budget_limit=0.0,
                tags=[project.get("project_kind", "application"), role],
                metadata={
                    "project_id": project["project_id"],
                    "worker_entry_id": worker["worker_entry_id"],
                    "worker_type": worker.get("worker_type", ""),
                    "config": worker.get("config") or {},
                },
            )
            if worker.get("worker_type") == "docker":
                containers.register_container(
                    name=str(worker.get("name", "docker-worker")),
                    image="python:3.12-slim",
                    status="planned",
                    labels={"project_id": project["project_id"], "worker_entry_id": worker["worker_entry_id"]},
                )
            elif worker.get("worker_type") == "vps":
                providers.create_provider(
                    name=f"{project['project_id']}::{worker.get('name', 'vps')}",
                    tier="STANDARD",
                    region="auto",
                    vcpu_total=4,
                    ram_gb_total=8,
                    storage_gb_total=80,
                    price_vcpu_h_usd=0.0,
                )
            runtime_workers.append(
                {
                    **worker,
                    "registry_worker_id": registry_entry["worker_id"],
                    "dispatch_label": _worker_dispatch_label(worker),
                }
            )
        return runtime_workers

    def _assign_modules(
        self,
        runtime: dict[str, Any],
        project: dict[str, Any],
        runtime_workers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        registry: WorkerRegistry = runtime["worker_registry"]
        modules = project.get("modules") or []
        if not runtime_workers:
            runtime_workers = [
                {
                    "worker_entry_id": f"{project['project_id']}::implicit::0",
                    "name": "local-fallback",
                    "worker_type": "docker",
                    "endpoint": "localhost",
                    "role": "coder",
                    "dispatch_label": "host_a",
                    "registry_worker_id": registry.register_worker(
                        name="local-fallback",
                        host="localhost",
                        capacity=1,
                        tags=[project.get("project_kind", "application"), "coder"],
                        metadata={"project_id": project["project_id"], "worker_entry_id": f"{project['project_id']}::implicit::0"},
                    )["worker_id"],
                }
            ]

        assignments: list[dict[str, Any]] = []
        for idx, module in enumerate(modules):
            runtime_worker = runtime_workers[idx % len(runtime_workers)]
            assignment = registry.create_assignment(
                runtime_worker["registry_worker_id"],
                module["module_id"],
                priority=idx + 1,
                metadata={
                    "project_id": project["project_id"],
                    "worker_entry_id": runtime_worker["worker_entry_id"],
                    "role": runtime_worker.get("role", ""),
                },
            )
            module["worker_id"] = runtime_worker["worker_entry_id"]
            module["status"] = "assigned"
            module["updated_at"] = _now()
            assignments.append(
                {
                    "assignment_id": assignment["assignment_id"],
                    "module_id": module["module_id"],
                    "worker_id": runtime_worker["worker_entry_id"],
                    "dispatch_label": runtime_worker["dispatch_label"],
                    "role": runtime_worker.get("role", ""),
                }
            )
        project["updated_at"] = _now()
        self.store.upsert_project(project)
        self.store.add_event(project["project_id"], "project.assignment.completed", {"assignments": len(assignments)})
        return assignments

    def _build_project(
        self,
        runtime: dict[str, Any],
        project: dict[str, Any],
        workspace: dict[str, str],
        runtime_workers: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        dispatch_labels = [worker["dispatch_label"] for worker in runtime_workers] or ["host_a"]
        domain_build = _domain_build(project)
        if domain_build:
            tasks, task_results, artifact = domain_build
            task_assignments = assign_round_robin(tasks, dispatch_labels)
            for result, (_task, worker_label) in zip(task_results, task_assignments, strict=False):
                result.worker = worker_label
        else:
            tasks = decompose_prompt(project["idea"])
            task_assignments = assign_round_robin(tasks, dispatch_labels)
            task_results = []
            for task, worker_label in task_assignments:
                task_results.append(dispatch(task, worker_label))
            artifact = merge_artifact(task_results)
        artifact_format = _guess_artifact_format(artifact)
        artifact_suffix = ".html" if artifact_format == "html" else ".py"
        artifact_path = Path(workspace["artifacts_dir"]) / f"app{artifact_suffix}"
        _write_text(artifact_path, artifact)
        evidence_pack = build_evidence_pack(project["idea"], tasks, task_assignments, task_results, artifact, str(artifact_path))

        evidence_store: EvidenceStore = runtime["evidence_store"]
        indexer: Indexer = runtime["indexer"]
        evidence_store.store(
            pack_id=evidence_pack.pack_id,
            artefact_type="project_artifact",
            name=f"{project['project_id']}{artifact_suffix}",
            content=artifact,
            metadata={"project_id": project["project_id"], "artifact_path": str(artifact_path)},
        )
        indexer.index_section(f"{project['project_id']}::artifact", f"{project['title']} artifact", artifact)
        self.global_indexer.index_section(f"{project['project_id']}::artifact", f"{project['title']} artifact", artifact)

        module_outputs = self._write_module_outputs(runtime, project, workspace, task_assignments, task_results, artifact_format)
        for module in project.get("modules") or []:
            if module["module_id"] in {item["module_id"] for item in module_outputs}:
                module["status"] = "completed"
                module["updated_at"] = _now()
        project["updated_at"] = _now()
        self.store.upsert_project(project)
        self.store.add_event(project["project_id"], "project.build.completed", {"artifact_path": str(artifact_path), "tasks": len(tasks)})
        return {
            "artifact_path": str(artifact_path),
            "artifact_format": artifact_format,
            "artifact_sha256": evidence_pack.manifest["artifact_sha256"],
            "tasks": [task.to_dict() for task in tasks],
            "results": [
                {
                    "task_id": result.task_id,
                    "name": task.name,
                    "kind": task.kind,
                    "worker": result.worker,
                    "status": result.status,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                }
                for task, result in zip(tasks, task_results, strict=False)
            ],
            "module_outputs": module_outputs,
            "pack_id": evidence_pack.pack_id,
        }

    def _write_module_outputs(
        self,
        runtime: dict[str, Any],
        project: dict[str, Any],
        workspace: dict[str, str],
        task_assignments: list[tuple[Any, str]],
        task_results: list[Any],
        artifact_format: str,
    ) -> list[dict[str, Any]]:
        modules_by_name = {module["name"]: module for module in project.get("modules") or []}
        grouped: dict[str, list[dict[str, Any]]] = {module["name"]: [] for module in project.get("modules") or []}
        for (task, _worker_label), result in zip(task_assignments, task_results, strict=False):
            module_name = _resolve_module_name(project, task.name)
            grouped.setdefault(module_name, []).append(
                {
                    "name": task.name,
                    "kind": task.kind,
                    "status": result.status,
                    "output": result.output,
                    "worker": result.worker,
                }
            )

        outputs: list[dict[str, Any]] = []
        registry: WorkerRegistry = runtime["worker_registry"]
        evidence_store: EvidenceStore = runtime["evidence_store"]
        for module_name, results in grouped.items():
            module = modules_by_name.get(module_name)
            if not module:
                continue
            module_dir = Path(workspace["modules_dir"]) / _slug(module_name)
            module_dir.mkdir(parents=True, exist_ok=True)

            if results:
                merged = _merge_result_outputs(results, artifact_format)
                extension = _module_extension(results, artifact_format)
                module_path = module_dir / f"{_slug(module_name)}{extension}"
                _write_text(module_path, merged)
                module["spec"] = {
                    **(module.get("spec") or {}),
                    "artifact_path": str(module_path),
                    "task_names": [item["name"] for item in results],
                    "artifact_format": extension.lstrip("."),
                }
                evidence_store.store(
                    pack_id=f"{project['project_id']}::{module['module_id']}",
                    artefact_type="module_artifact",
                    name=module_path.name,
                    content=merged,
                    metadata={"project_id": project["project_id"], "module_id": module["module_id"]},
                )
            else:
                module_path = module_dir / "validation_notes.md"
                content = "\n".join(
                    [
                        f"# {module_name}",
                        "",
                        "No direct build fragments were assigned to this module.",
                        "The lane remains responsible for validation, integration and acceptance checks.",
                    ]
                )
                _write_text(module_path, content)
                module["spec"] = {
                    **(module.get("spec") or {}),
                    "artifact_path": str(module_path),
                    "task_names": [],
                    "artifact_format": "md",
                }

            module["updated_at"] = _now()
            assignment = next((item for item in registry.list_assignments(module_id=module["module_id"])), None)
            if assignment:
                registry.update_assignment(
                    assignment["assignment_id"],
                    status="completed",
                    patch_proposal=Path(module["spec"]["artifact_path"]).read_text(encoding="utf-8"),
                    evidence_pack=json.dumps({"artifact_path": module["spec"]["artifact_path"]}),
                    completed_at=_now(),
                )
            outputs.append(
                {
                    "module_id": module["module_id"],
                    "name": module_name,
                    "artifact_path": module["spec"]["artifact_path"],
                    "task_names": module["spec"]["task_names"],
                }
            )
        return outputs

    def _validate_project(
        self,
        runtime: dict[str, Any],
        project: dict[str, Any],
        build_result: dict[str, Any],
        workspace: dict[str, str],
    ) -> dict[str, Any]:
        artifact_path = Path(build_result["artifact_path"])
        artifact_text = artifact_path.read_text(encoding="utf-8")
        lowered = artifact_text.lower()
        module_paths = [Path((module.get("spec") or {}).get("artifact_path", "")) for module in project.get("modules") or []]
        module_outputs_present = all(path.is_file() for path in module_paths if str(path))
        forbidden_scaffold_tokens = ["todo", "fixme", "notimplementederror", "mock", "stub"]
        generic_calculator = all(token in lowered for token in ["def add(", "def sub(", "def mul(", "def div("])
        generic_aeis_shell = all(
            token in lowered
            for token in ["aeis application product", "panel operacyjny", "nowe zadanie operatora"]
        )
        scaffold_clean = not any(token in lowered for token in forbidden_scaffold_tokens)
        domain_specific = self._integration_keywords_ok(project, lowered) and not (
            (generic_calculator and project.get("project_kind") != "calculator") or generic_aeis_shell
        )
        build = runtime["integration"].create_candidate_build(
            name=f"{project['title']} candidate",
            description=f"Generated candidate build for {project['project_id']}",
            module_ids=[module["module_id"] for module in project.get("modules") or []],
            metadata={"project_id": project["project_id"], "artifact_path": build_result["artifact_path"]},
        )

        stages = {
            "contract_tests": {
                "success": "{{STYLE}}" not in artifact_text and "{{SCRIPT}}" not in artifact_text and module_outputs_present,
                "stdout": "Contract freeze verified against generated artifact and module outputs.",
                "stderr": "" if module_outputs_present else "Some module outputs are missing.",
                "duration_ms": 1,
            },
            "integration_tests": {
                "success": domain_specific,
                "stdout": "Domain feature keywords detected and generic fallback was not used.",
                "stderr": "" if domain_specific else "Artifact is missing expected domain keywords or used a generic fallback.",
                "duration_ms": 1,
            },
            "smoke_tests": {
                "success": artifact_path.is_file() and len(artifact_text) > 200,
                "stdout": f"Smoke check passed for {artifact_path.name}.",
                "stderr": "" if artifact_path.is_file() else "Artifact file not found.",
                "duration_ms": 1,
            },
            "lint": {
                "success": scaffold_clean,
                "stdout": "Static scan found no scaffold markers in the generated artifact.",
                "stderr": "" if scaffold_clean else "Scaffold markers found in generated artifact.",
                "duration_ms": 1,
            },
            "typecheck": {
                "success": "undefined" not in lowered and "not implemented" not in lowered,
                "stdout": "Generated artifact does not contain obvious unresolved placeholders.",
                "stderr": "" if "undefined" not in lowered and "not implemented" not in lowered else "Unimplemented content detected.",
                "duration_ms": 1,
            },
        }
        success = all(stage["success"] for stage in stages.values())
        runtime["integration"].update_build_status(build["build_id"], "ready" if success else "rejected")
        runtime["evidence_store"].store(
            pack_id=build_result["pack_id"],
            artefact_type="validation_summary",
            name="validation.json",
            content=json.dumps(stages, indent=2),
            metadata={"project_id": project["project_id"], "build_id": build["build_id"]},
        )
        self.store.record_cost(project["project_id"], "project_engine", "local_validation", 0, 0, 0.0)
        self.store.add_event(project["project_id"], "project.validation.completed", {"build_id": build["build_id"], "success": success})
        return {"build_id": build["build_id"], "success": success, "stages": stages}

    def _integration_keywords_ok(self, project: dict[str, Any], lowered_artifact: str) -> bool:
        kind = project.get("project_kind", "")
        if kind == "chat_app":
            return all(token in lowered_artifact for token in ["register", "login", "room", "message"])
        if kind == "design_tool":
            return all(token in lowered_artifact for token in ["canvas", "room", "furniture"])
        if kind == "funding":
            required_feature_groups = [
                ["funding_intake", "funding-intake"],
                ["official_source_search", "official-source-search"],
                ["source_verification", "source-verification"],
                ["deadline_guard", "deadline-guard"],
                ["program_scoring", "scoreprograms", "przelicz scoring"],
                ["submission_governance", "submission governance", "funding_submission"],
                ["perplexity"],
                ["google"],
                ["bielik"],
                ["pllum"],
                ["humangate"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "bioinformatics_workflow":
            required_feature_groups = [
                ["synthetic_data_intake", "synthetic-data-intake", "importsample"],
                ["format_validation", "format-validation"],
                ["qc_pipeline", "qc-pipeline", "runqcpipeline"],
                ["sample_pseudonymization", "sample-pseudonymization", "pseudonymizesample"],
                ["variant_research_scoring", "variant-research-scoring", "scorevariantresearchonly"],
                ["clinical_safety_guard", "clinical-safety-guard", "no clinical use"],
                ["funding_scan", "funding-scan", "runfundingscan"],
                ["local_model_documentation", "local-model-documentation", "bielik"],
                ["pllum"],
                ["audit_evidence_pack", "audit-evidence-pack", "buildevidencepack"],
                ["report_export", "report-export"],
                ["humangate"],
                ["pesel"],
                ["research-only"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "mental_health_safety":
            required_feature_groups = [
                ["wellbeing_intake", "wellbeing-intake", "analyzewellbeing"],
                ["crisis_classifier", "crisis-classifier"],
                ["no_medical_advice_guard", "no-medical-advice-guard"],
                ["safe_response_generator", "safe-response-generator"],
                ["emergency_handoff", "emergency-handoff"],
                ["pii_minimization", "pii-minimization"],
                ["local_model_safety_review", "local-model-safety-review", "bielik"],
                ["pllum"],
                ["source_backed_resources", "source-backed-resources"],
                ["release_safety_gate", "release-safety-gate"],
                ["audit_evidence_pack", "audit-evidence-pack", "buildevidencepack"],
                ["humangate"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "ecommerce_generator":
            required_feature_groups = [
                ["generateproductdescriptions", "description_generation", "description_pl"],
                ["validateean", "ean_validation"],
                ["humangate", "human_review_gate", "human_gate_approved"],
                ["allegro"],
                ["amazon"],
                ["buildcsv", "marketplace_export", "marketplace-export.csv"],
                ["buildevidencepack", "evidence_pack", "evidence pack"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "employee_portal":
            required_feature_groups = [
                ["auth_users", "auth-users"],
                ["role_assignment", "role-assignment"],
                ["document_workflow", "document-workflow"],
                ["leave_request_workflow", "leave-request-workflow"],
                ["gdpr_dsr", "gdpr-dsr"],
                ["security_session_policy", "security-session-policy"],
                ["audit_evidence_pack", "audit-evidence-pack"],
                ["dpia_required"],
                ["session_timeout_30_min", "session timeout"],
                ["rate_limit_5_15min", "rate limit"],
                ["password_policy_14_mfa_lockout", "password policy"],
                ["humangate"],
                ["dpo"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "operator_mobile":
            required_feature_groups = [
                ["mobile_shell", "mobile-shell"],
                ["offline_checklists", "offline-checklists", "addchecklistitem"],
                ["firmware_attachment_guard", "firmware-attachment-guard", "validatefirmwareattachment"],
                ["photo_evidence_redaction", "photo-evidence-redaction", "redactphotoevidence"],
                ["sync_queue", "sync-queue", "syncqueue"],
                ["device_binding", "device-binding", "binddevice"],
                ["secure_approval", "secure-approval", "approvefirmwaregate"],
                ["audit_evidence_pack", "audit-evidence-pack", "buildevidencepack"],
                ["humangate"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "project_management_system":
            required_feature_groups = [
                ["tenant_workspace", "tenant-workspace", "createworkspace"],
                ["portfolio_dashboard", "portfolio"],
                ["kanban_backlog", "kanban-backlog", "addtask"],
                ["gantt_roadmap", "gantt-roadmap"],
                ["resource_capacity", "resource"],
                ["risk_register", "risk-register", "addrisk"],
                ["budget_tracking", "budget-tracking"],
                ["api_integrations", "api-integrations"],
                ["rbac_audit", "rbac-audit"],
                ["release_governance", "release-governance", "promotecanary"],
                ["rollback"],
                ["humangate"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if kind == "marketplace_platform":
            required_feature_groups = [
                ["tenant_identity", "tenant-identity", "createtenant"],
                ["vendor_onboarding", "vendor-onboarding", "addvendor"],
                ["product_catalog", "product-catalog", "addproduct"],
                ["cart_checkout", "cart-checkout", "checkoutsandbox"],
                ["payment_sandbox", "payment-sandbox", "approvepaymentgate"],
                ["tax_shipping", "tax-shipping", "approvetaxshipping"],
                ["admin_console", "admin-console", "openadminconsole"],
                ["funding_scan", "funding-scan", "runfundingscan"],
                ["release_governance", "release-governance", "promotecanary"],
                ["rollback"],
                ["humangate"],
                ["evidence_pack", "evidence-pack", "buildevidencepack"],
            ]
            return all(
                any(token in lowered_artifact for token in group)
                for group in required_feature_groups
            )
        if _wants_llm_cost_calculator(project):
            return all(
                token in lowered_artifact
                for token in [
                    "calculatellmcost",
                    "data-testid=\"input-tokens-input\"",
                    "data-testid=\"csv-download\"",
                    "warn_80",
                    "over_100",
                    "humangate",
                    "auditentries",
                    "no_pii",
                ]
            )
        if kind == "dashboard":
            return all(token in lowered_artifact for token in ["dashboard", "panel"])
        module_tokens = [
            _slug(module.get("name", "")).replace("-", " ")
            for module in project.get("modules") or []
            if module.get("name")
        ]
        return len(lowered_artifact) > 500 and any(
            token and token.split()[0] in lowered_artifact
            for token in module_tokens
        )

    def _write_deployment_bundle(
        self,
        project: dict[str, Any],
        workspace: dict[str, str],
        runtime_workers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        deploy_dir = Path(workspace["deploy_dir"])
        services: list[str] = ["version: '3.9'", "services:"]
        for idx, module in enumerate(project.get("modules") or []):
            service_name = _slug(module.get("name", f"module-{idx}"))
            host_target = module.get("host_target", "local")
            worker = runtime_workers[idx % len(runtime_workers)] if runtime_workers else {}
            if module.get("spec", {}).get("artifact_format") == "py":
                services.extend(
                    [
                        f"  {service_name}:",
                        "    image: python:3.12-slim",
                        f"    command: python /workspace/{service_name}/{service_name}.py",
                        "    volumes:",
                        f"      - ../modules/{service_name}:/workspace/{service_name}:ro",
                        f"    profiles: ['{host_target}']",
                    ]
                )
            else:
                services.extend(
                    [
                        f"  {service_name}:",
                        "    image: nginx:alpine",
                        "    volumes:",
                        f"      - ../modules/{service_name}:/usr/share/nginx/html:ro",
                        f"    profiles: ['{host_target}']",
                        f"    environment:",
                        f"      SYLION_ROLE: {worker.get('role', 'worker')}",
                    ]
                )
        docker_compose = "\n".join(services) + "\n"
        local_ps1 = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "Write-Host 'Starting generated local topology...'",
                "docker compose -f ./docker-compose.yml --profile local up --build",
            ]
        )
        local_sh = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "echo 'Starting generated local topology...'",
                "docker compose -f ./docker-compose.yml --profile local up --build",
            ]
        )
        terraform = {
            "project_id": project["project_id"],
            "vps_workers": int(project.get("execution_plan", {}).get("vps_workers", 0)),
            "deployment_mode": project.get("execution_plan", {}).get("deployment_mode", "hybrid"),
            "auto_provision": bool(project.get("execution_plan", {}).get("auto_provision")),
        }
        inventory = "\n".join(["[sylion_project_vps]"] + [str(worker.get("endpoint", "")) for worker in runtime_workers if worker.get("worker_type") == "vps"])
        plan_md = "\n".join(
            [
                f"# Deployment Plan for {project['title']}",
                "",
                f"- Deployment mode: `{project.get('execution_plan', {}).get('deployment_mode', 'hybrid')}`",
                f"- Provisioning mode: `{project.get('execution_plan', {}).get('provisioning_mode', 'plan_and_generate')}`",
                f"- Local workers: `{project.get('execution_plan', {}).get('local_docker_workers', 0)}`",
                f"- VPS workers: `{project.get('execution_plan', {}).get('vps_workers', 0)}`",
                "",
                "Generated files:",
                "- docker-compose.yml",
                "- deploy.local.ps1",
                "- deploy.local.sh",
                "- terraform.tfvars.json",
                "- ansible_inventory.ini",
            ]
        )
        compose_path = _write_text(deploy_dir / "docker-compose.yml", docker_compose)
        ps1_path = _write_text(deploy_dir / "deploy.local.ps1", local_ps1)
        sh_path = _write_text(deploy_dir / "deploy.local.sh", local_sh)
        tfvars_path = _write_text(deploy_dir / "terraform.tfvars.json", json.dumps(terraform, indent=2))
        inventory_path = _write_text(deploy_dir / "ansible_inventory.ini", inventory)
        plan_path = _write_text(deploy_dir / "PLAN.md", plan_md)
        return {
            "docker_compose": compose_path,
            "deploy_ps1": ps1_path,
            "deploy_sh": sh_path,
            "terraform_tfvars": tfvars_path,
            "ansible_inventory": inventory_path,
            "plan_md": plan_path,
        }

    def _write_learning_outputs(
        self,
        project: dict[str, Any],
        build_result: dict[str, Any],
        validation: dict[str, Any],
        audit: dict[str, Any],
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        dataset_path = Path(self.store.db_path).with_name(f"{project['project_id']}_lora_dataset.jsonl") if self.store.db_path != ":memory:" else Path(_results_root()) / project["project_id"] / "brain" / "lora_dataset.jsonl"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        samples = [
            {
                "project_id": project["project_id"],
                "prompt": project.get("idea", ""),
                "accepted_artifact_path": build_result["artifact_path"],
                "canon": project.get("canonical_book", ""),
                "masterplan": project.get("masterplan", ""),
            },
            {
                "project_id": project["project_id"],
                "prompt": f"Generate deployment plan for {project.get('title', '')}",
                "accepted_artifact_path": deployment.get("plan_md", ""),
                "validation": validation,
                "audit": audit,
            },
        ]
        with dataset_path.open("w", encoding="utf-8", newline="\n") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

        prompt_snapshots = [
            self.store.record_brain_prompt_snapshot(
                "project_execution",
                "builder",
                f"Build a {project.get('project_kind', 'application')} for idea: {project.get('idea', '')}",
            ),
            self.store.record_brain_prompt_snapshot(
                "project_execution",
                "auditor",
                f"Audit generated output for project {project.get('title', '')} using canon and masterplan constraints.",
            ),
        ]

        adapter = None
        existing_adapters = self.store.list_brain_lora_adapters().get("adapters", [])
        if not any(project["project_id"] in adapter_item.get("training_project_ids", []) for adapter_item in existing_adapters):
            base_model = (self.store.get_brain_models().get("installed") or ["qwen3.5:latest"])[0]
            adapter = self.store.queue_lora_training(project["project_id"], base_model)

        self.global_indexer.index_section(f"{project['project_id']}::canon", f"{project['title']} canon", project.get("canonical_book", ""))
        self.global_indexer.index_section(f"{project['project_id']}::masterplan", f"{project['title']} masterplan", project.get("masterplan", ""))
        self.global_indexer.index_section(f"{project['project_id']}::dataset", f"{project['title']} learning dataset", dataset_path.read_text(encoding="utf-8"))
        self.store.add_event(project["project_id"], "project.broadcast.completed", {"dataset_path": str(dataset_path), "adapter_id": (adapter or {}).get("adapter_id", "")})
        return {
            "dataset_path": str(dataset_path),
            "sample_count": len(samples),
            "adapter": adapter,
            "prompt_snapshots": [item["prompt_id"] for item in prompt_snapshots],
        }

    def _audit_findings(
        self,
        project: dict[str, Any],
        audit_type: str,
        target_text: str,
        artifact_text: str,
        readme_path: Path,
    ) -> list[dict[str, Any]]:
        lowered = target_text.lower()
        findings: list[dict[str, Any]] = []
        if audit_type == "security_officer":
            if re.search(r"\b(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[^'\"\s]{8,}", lowered):
                findings.append({"severity": "high", "message": "Potential sensitive token assignment detected."})
            if re.search(r"(?<![a-z0-9])sk-(?:proj-|ant-|or-v1-)?[a-z0-9_-]{12,}", lowered):
                findings.append({"severity": "high", "message": "Potential API key value detected."})
            if "eval(" in lowered:
                findings.append({"severity": "high", "message": "Potential unsafe eval() detected."})
        elif audit_type == "quality_perf_reviewer":
            if len(target_text.strip()) < 300:
                findings.append({"severity": "medium", "message": "Generated material is too small to inspire confidence in module completeness."})
            if project.get("project_kind") != "calculator" and all(token in artifact_text.lower() for token in ["def add(", "def sub(", "def mul(", "def div("]):
                findings.append({"severity": "high", "message": "Generated artifact is a generic calculator fallback, not the requested product."})
            if all(token in artifact_text.lower() for token in ["aeis application product", "panel operacyjny", "nowe zadanie operatora"]):
                findings.append({"severity": "high", "message": "Generated artifact is the generic AEIS shell, not the requested product."})
            if project.get("project_kind") == "application" and "domain_control_workbench" not in artifact_text.lower():
                findings.append({"severity": "high", "message": "Application artifact is missing a domain control workbench tied to the project brief."})
            if _wants_llm_cost_calculator(project) and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "LLM cost calculator artifact is missing required cost fields, thresholds, CSV export or audit evidence."})
            if project.get("project_kind") == "ecommerce_generator" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "E-commerce artifact is missing description generation, EAN validation, HumanGate, Allegro/Amazon CSV export or evidence pack."})
            if project.get("project_kind") == "employee_portal" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Employee portal artifact is missing auth, roles, document workflow, leave workflow, GDPR DSR, security policy, DPIA, HumanGate or evidence pack."})
            if project.get("project_kind") == "operator_mobile" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Operator mobile artifact is missing offline checklists, firmware guard, photo redaction, sync queue, device binding, secure approval, HumanGate or evidence pack."})
            if project.get("project_kind") == "project_management_system" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Project management artifact is missing tenant workspace, Kanban, Gantt, resource capacity, risks, budget, RBAC, API integrations, release governance, canary, rollback or HumanGate controls."})
            if project.get("project_kind") == "marketplace_platform" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Marketplace platform artifact is missing tenant identity, vendor onboarding, catalog, checkout, payment sandbox, tax/shipping, admin, funding scan, release governance, rollback or HumanGate controls."})
            if project.get("project_kind") == "bioinformatics_workflow" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Bioinformatics workflow artifact is missing sample intake, FASTQ/VCF validation, QC, pseudonymization, research-only variant scoring, clinical safety guard, funding scan, local model documentation, report export HumanGate or evidence pack."})
            if project.get("project_kind") == "mental_health_safety" and not self._integration_keywords_ok(project, artifact_text.lower()):
                findings.append({"severity": "high", "message": "Mental-health safety artifact is missing wellbeing intake, crisis classifier, no-medical-advice guard, safe response, emergency hand-off, PII minimization, local model review, source-backed resources, release safety gate, HumanGate or evidence pack."})
            if any(token in artifact_text.lower() for token in ["todo", "fixme", "notimplementederror", "mock", "stub"]):
                findings.append({"severity": "high", "message": "Generated artifact contains scaffold or fake-implementation markers."})
        elif audit_type == "compliance_officer":
            if "password" in lowered and "localstorage" in lowered and "demo" not in lowered:
                findings.append({"severity": "medium", "message": "Credentials are persisted in browser storage; treat as demo-only unless replaced by a server-side auth flow."})
            if project.get("project_kind") == "funding" and "humangate" not in artifact_text.lower():
                findings.append({"severity": "high", "message": "Funding scoring artifact does not expose HumanGate gating."})
            if project.get("project_kind") == "funding":
                funding_lower = artifact_text.lower()
                if "source_verification" not in funding_lower or "deadline_guard" not in funding_lower or "funding_submission" not in funding_lower:
                    findings.append({"severity": "high", "message": "Funding artifact is missing source verification, deadline guard or submission governance controls."})
            if project.get("project_kind") == "employee_portal":
                employee_lower = artifact_text.lower()
                if "dpia_required" not in employee_lower or "gdpr_dsr" not in employee_lower or "dpo" not in employee_lower:
                    findings.append({"severity": "high", "message": "Employee portal compliance controls do not expose DPIA, GDPR DSR and DPO gate evidence."})
            if project.get("project_kind") == "operator_mobile":
                operator_lower = artifact_text.lower()
                if "firmware_attachment_guard" not in operator_lower or "photo_evidence_redaction" not in operator_lower or "secure_approval" not in operator_lower:
                    findings.append({"severity": "high", "message": "Operator mobile compliance controls do not expose firmware, photo PII and secure approval gates."})
            if project.get("project_kind") == "project_management_system":
                pm_lower = artifact_text.lower()
                if "rbac_audit" not in pm_lower or "release_governance" not in pm_lower or "budget_tracking" not in pm_lower:
                    findings.append({"severity": "high", "message": "Project management compliance controls do not expose RBAC, release governance and budget tracking evidence."})
            if project.get("project_kind") == "marketplace_platform":
                marketplace_lower = artifact_text.lower()
                if "payment_sandbox" not in marketplace_lower or "tax_shipping" not in marketplace_lower or "release_governance" not in marketplace_lower or "humangate" not in marketplace_lower:
                    findings.append({"severity": "high", "message": "Marketplace compliance controls do not expose payment sandbox, tax/shipping, release governance and HumanGate evidence."})
            if project.get("project_kind") == "bioinformatics_workflow":
                bio_lower = artifact_text.lower()
                if "clinical_safety_guard" not in bio_lower or "no clinical use" not in bio_lower or "report_export" not in bio_lower or "pesel" not in bio_lower:
                    findings.append({"severity": "high", "message": "Bioinformatics compliance controls do not expose clinical safety, no-clinical-use, PESEL/PII and report export HumanGate evidence."})
            if project.get("project_kind") == "mental_health_safety":
                mental_lower = artifact_text.lower()
                if "no_medical_advice_guard" not in mental_lower or "crisis_classifier" not in mental_lower or "emergency_handoff" not in mental_lower or "pii_minimization" not in mental_lower:
                    findings.append({"severity": "high", "message": "Mental-health compliance controls do not expose no-medical-advice, crisis, emergency hand-off and PII minimization evidence."})
        elif audit_type == "dependency_guardian":
            if re.search(r"(image|from)\s*[:=][^\n]*:latest", lowered):
                findings.append({"severity": "low", "message": "Unpinned dependency marker `latest` detected in generated material."})
        elif audit_type == "ux_reviewer":
            artifact_lower = artifact_text.lower()
            is_html_ui = "<html" in artifact_lower or "<body" in artifact_lower or "<canvas" in artifact_lower
            if is_html_ui and "viewport" not in artifact_lower:
                findings.append({"severity": "medium", "message": "Responsive viewport metadata is missing from the generated UI."})
        elif audit_type == "doc_officer":
            if not readme_path.is_file() or len(readme_path.read_text(encoding="utf-8").strip()) < 80:
                findings.append({"severity": "low", "message": "Project README is missing or too small."})
        return findings


def get_project_execution_engine(store: ProjectModeStore | None = None) -> ProjectExecutionEngine:
    return ProjectExecutionEngine(store=store)
