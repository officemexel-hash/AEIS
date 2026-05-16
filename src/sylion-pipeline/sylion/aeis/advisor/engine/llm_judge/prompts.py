"""Prompt templates for LLM-as-judge calls."""

from __future__ import annotations

import json
from typing import Any


_SYSTEM_HEADER = (
    "Jestes doradca SYLION AEIS. Generuj rekomendacje dla polskiego operatora "
    "jako scisly JSON. Wszystkie wartosci tekstowe musza byc po polsku. "
    "Nie dodawaj prozy poza JSON i nie uzywaj markdown fences."
)


def rationale_prompt(
    *,
    recommendation_type: str,
    risk_level: str,
    project_type: str,
    project_domain: str,
    context: dict[str, Any],
) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: przygotuj wieloakapitowe uzasadnienie operatorskie dla typu rekomendacji
"{recommendation_type}".

Ryzyko: {risk_level}
Typ projektu: {project_type or "n/a"}
Domena projektu: {project_domain or "n/a"}

Kontekst (JSON):
{json.dumps(context, default=str, indent=2)[:4000]}

Schemat wyjscia:
{{
  "rationale": "<wyjasnienie 200-500 slow, kilka akapitow, po polsku>",
  "expected_benefit": "<jedno lub dwa zdania po polsku>",
  "expected_downside": "<jedno lub dwa zdania po polsku>",
  "quality_impact": "<jedno zdanie po polsku>",
  "alternatives": [
    {{
      "title": "... po polsku",
      "short_description": "... po polsku",
      "trade_off_summary": "... po polsku",
      "risk_level": "low|medium|high|critical",
      "confidence_score": 0.0
    }}
  ]
}}
Maksymalnie 5 alternatyw.
"""


def evidence_rationale_prompt(*, decision_class: str, context: dict[str, Any]) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: przygotuj uzasadnienie Evidence Pack dla klasy decyzji "{decision_class}".

Dlugosc: 250-500 slow. Uwzglednij problem, rozwazane alternatywy,
powod wyboru tej opcji i oczekiwane rezultaty. Pisz po polsku.

Context:
{json.dumps(context, default=str, indent=2)[:4000]}

Schemat wyjscia:
{{"rationale": "<text>"}}
"""


def evidence_rollback_prompt(*, decision_class: str, context: dict[str, Any]) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: przygotuj krokowy plan rollback dla klasy decyzji "{decision_class}".

Dlugosc: 150-400 slow. Kazdy krok musi zawierac: akcje, szacowany czas,
odpowiedzialnego (operator | dostawca | system) oraz kryterium wykrycia.
Pisz po polsku.

Context:
{json.dumps(context, default=str, indent=2)[:3000]}

Schemat wyjscia:
{{"rollback_plan": "<text>"}}
"""


def evidence_fidelity_prompt(*, decision_class: str, context: dict[str, Any]) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: zaprojektuj test zgodnosci dla klasy decyzji "{decision_class}".

Dlugosc: 80-200 slow. Uwzglednij mierzalna metryke sukcesu, okno pomiarowe,
zrodlo danych i akceptowalna tolerancje. Pisz po polsku.

Context:
{json.dumps(context, default=str, indent=2)[:2500]}

Schemat wyjscia:
{{"fidelity_test": "<text>"}}
"""


def evidence_risk_prompt(*, decision_class: str, context: dict[str, Any]) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: wskaz ryzyka klasy D5 dla klasy decyzji "{decision_class}". Pisz po polsku.

Output schema:
{{
  "identified_risks": [
    {{"risk_id": "r1", "description": "...", "probability": "low|medium|high",
      "impact": "low|medium|high|critical", "mitigation": "..."}}
  ],
  "worst_case_scenario": "<opis 150-300 slow po polsku>"
}}

Context:
{json.dumps(context, default=str, indent=2)[:3000]}
"""


def evidence_compliance_prompt(*, decision_class: str, context: dict[str, Any]) -> str:
    return f"""{_SYSTEM_HEADER}

Zadanie: przeglad compliance D5 dla klasy decyzji "{decision_class}". Pisz po polsku.

Output schema:
{{
  "regulatory_constraints_reviewed": true,
  "compliance_concerns": ["..."],
  "legal_review_completed": false,
  "legal_review_notes": "..."
}}

Context:
{json.dumps(context, default=str, indent=2)[:3000]}
"""
