"""Sim runner — static / dynamic / AI-generated modes for persona simulation."""

from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from sylion.sim._db_shim import install_sim_pool
from sylion.sim.personas import Persona
from sylion.sim.scenarios import (
    STATIC_SCENARIOS,
    Scenario,
    generate_dynamic_scenarios,
)

log = logging.getLogger("sylion.sim.runner")


@dataclass
class DecisionRecord:
    scenario_id: str
    event_topic: str
    card_id: str
    card_type: str
    d_level: str
    risk_level: str
    action_taken: str
    latency_ms: float
    council_used: bool
    hg_triggered: bool
    cost_estimate_usd: float


@dataclass
class SimReport:
    persona_id: str
    mode: str
    scenarios_run: int = 0
    cards_emitted: int = 0
    decision_latency_avg: float = 0.0
    council_used_count: int = 0
    hg_triggered_count: int = 0
    cost_estimate_total: float = 0.0
    accuracy: float = 0.0
    decisions: list[DecisionRecord] = field(default_factory=list)
    raw_scenarios: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "mode": self.mode,
            "scenarios_run": self.scenarios_run,
            "cards_emitted": self.cards_emitted,
            "decision_latency_avg": round(self.decision_latency_avg, 3),
            "council_used_count": self.council_used_count,
            "hg_triggered_count": self.hg_triggered_count,
            "cost_estimate_total": round(self.cost_estimate_total, 4),
            "accuracy": round(self.accuracy, 3),
            "decisions": [
                {
                    "scenario_id": d.scenario_id,
                    "event_topic": d.event_topic,
                    "card_id": d.card_id,
                    "card_type": d.card_type,
                    "d_level": d.d_level,
                    "risk_level": d.risk_level,
                    "action_taken": d.action_taken,
                    "latency_ms": round(d.latency_ms, 2),
                    "council_used": d.council_used,
                    "hg_triggered": d.hg_triggered,
                    "cost_estimate_usd": round(d.cost_estimate_usd, 6),
                }
                for d in self.decisions
            ],
        }


# ---------------------------------------------------------------------------
# Persona heuristic engine
# ---------------------------------------------------------------------------

_CARD_ACTIONS = [
    "accept",
    "reject",
    "modify",
    "remind_later",
    "not_useful",
    "convert_to_human_gate",
    "save_as_preference",
    "dont_learn_from_this",
]


def _weighted_choice(options: dict[str, float]) -> str:
    items = list(options.items())
    weights = [w for _, w in items]
    total = sum(weights)
    if total == 0:
        return "accept"
    r = random.uniform(0, total)
    cumulative = 0.0
    for action, weight in items:
        cumulative += weight
        if r <= cumulative:
            return action
    return items[-1][0]


def apply_heuristic(persona: Persona, card: dict[str, Any]) -> str:
    """Return a card action based on persona profile and card attributes."""
    header = card.get("header", {})
    d_level = header.get("d_level", "D0")
    risk_level = header.get("risk_level", "low")
    card_type = header.get("card_type", "decision")

    # Start from persona default distribution
    dist = dict(persona.default_distribution)
    # Ensure all actions have a weight
    for a in _CARD_ACTIONS:
        if a not in dist:
            dist[a] = 0.0

    # Risk appetite adjustments
    if risk_level in ("high", "critical"):
        if persona.risk_appetite <= 2:
            dist["convert_to_human_gate"] = dist.get("convert_to_human_gate", 0.0) + 0.30
            dist["accept"] = max(0.0, dist.get("accept", 0.0) - 0.20)
        elif persona.risk_appetite >= 4:
            dist["accept"] = dist.get("accept", 0.0) + 0.10

    # D-level adjustments
    if d_level == "D5":
        if persona.risk_appetite <= 2:
            dist["convert_to_human_gate"] = dist.get("convert_to_human_gate", 0.0) + 0.40
            dist["reject"] = dist.get("reject", 0.0) + 0.20
            dist["accept"] = max(0.0, dist.get("accept", 0.0) - 0.50)
        elif persona.risk_appetite >= 4:
            dist["accept"] = dist.get("accept", 0.0) + 0.05
    elif d_level in ("D3", "D4"):
        if persona.risk_appetite <= 2:
            dist["convert_to_human_gate"] = dist.get("convert_to_human_gate", 0.0) + 0.20
            dist["accept"] = max(0.0, dist.get("accept", 0.0) - 0.15)

    # Funding card preference
    if card_type == "funding":
        if persona.funding_preference:
            dist["accept"] = dist.get("accept", 0.0) + 0.15
        else:
            dist["not_useful"] = dist.get("not_useful", 0.0) + 0.25
            dist["accept"] = max(0.0, dist.get("accept", 0.0) - 0.15)

    # Cost sensitivity
    body = card.get("decision") or card.get("funding") or card.get("scaling") or {}
    cost_impact = body.get("cost_impact", {}) if isinstance(body, dict) else {}
    cost_usd = 0.0
    if isinstance(cost_impact, dict):
        try:
            cost_usd = float(cost_impact.get("absolute_value", "0"))
        except Exception:
            cost_usd = 0.0
    if cost_usd > 100:
        if persona.cost_sensitivity == "high":
            dist["reject"] = dist.get("reject", 0.0) + 0.25
            dist["accept"] = max(0.0, dist.get("accept", 0.0) - 0.20)
        elif persona.cost_sensitivity == "medium":
            dist["modify"] = dist.get("modify", 0.0) + 0.10

    # Normalize
    total = sum(dist.values())
    if total > 0:
        dist = {k: v / total for k, v in dist.items()}

    return _weighted_choice(dist)


# ---------------------------------------------------------------------------
# In-process advisor context
# ---------------------------------------------------------------------------

class _AdvisorContext:
    """Sets up EventBus + AdvisorEngineService + SQLite shim in-process."""

    def __init__(self):
        self.pool = install_sim_pool()
        from sylion.core.event_bus import EventBus
        from sylion.aeis.advisor.engine.service import AdvisorEngineService

        self.bus = EventBus()
        self.svc = AdvisorEngineService()
        self.svc.attach_to_event_bus(self.bus)

    def submit(self, topic: str, payload: dict[str, Any], operator_id: str) -> list[dict[str, Any]]:
        return self.svc.submit_event(topic=topic, payload=payload, operator_id=operator_id)


# ---------------------------------------------------------------------------
# SimRunner
# ---------------------------------------------------------------------------

class SimRunner:
    """Run simulations for a single persona across three modes."""

    def __init__(self):
        self._ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_model = os.environ.get("OLLAMA_SIM_MODEL", "qwen2.5:7b-instruct")

    def _run_scenarios(self, persona: Persona, scenarios: list[Scenario]) -> SimReport:
        report = SimReport(persona_id=persona.id, mode="unknown")
        ctx = _AdvisorContext()
        operator_id = f"sim_{persona.id}"

        total_latency = 0.0
        correct_expectations = 0
        total_expectations = 0

        for scenario in scenarios:
            scenario_correct = 0
            scenario_total = 0
            for ev in scenario.events:
                start = time.perf_counter()
                cards = ctx.submit(ev["topic"], ev["payload"], operator_id)
                base_latency = (time.perf_counter() - start) * 1000.0

                # Persona decision delay (simulated reading time)
                delay_ms = random.expovariate(1.0 / (persona.decision_speed_p50 * 1000.0))
                total_latency += base_latency + delay_ms

                for card in cards:
                    action = apply_heuristic(persona, card)
                    header = card.get("header", {})
                    d_level = header.get("d_level", "D0")
                    risk_level = header.get("risk_level", "low")
                    card_type = header.get("card_type", "decision")

                    council_used = bool(header.get("sources", []))
                    hg_triggered = action == "convert_to_human_gate" or header.get("human_gate_required", False)

                    body = card.get("decision") or card.get("funding") or card.get("scaling") or {}
                    cost_usd = 0.0
                    if isinstance(body, dict):
                        ci = body.get("cost_impact", {})
                        if isinstance(ci, dict):
                            try:
                                cost_usd = float(ci.get("absolute_value", "0"))
                            except Exception:
                                pass

                    report.decisions.append(
                        DecisionRecord(
                            scenario_id=scenario.id,
                            event_topic=ev["topic"],
                            card_id=header.get("card_id", ""),
                            card_type=card_type,
                            d_level=d_level,
                            risk_level=risk_level,
                            action_taken=action,
                            latency_ms=base_latency + delay_ms,
                            council_used=council_used,
                            hg_triggered=hg_triggered,
                            cost_estimate_usd=cost_usd,
                        )
                    )
                    report.cards_emitted += 1
                    if council_used:
                        report.council_used_count += 1
                    if hg_triggered:
                        report.hg_triggered_count += 1
                    report.cost_estimate_total += cost_usd

                # Simple accuracy: did we get at least expected_cards_min?
                scenario_total += 1
                if len(cards) >= scenario.expected_cards_min:
                    scenario_correct += 1

            correct_expectations += scenario_correct
            total_expectations += max(scenario_total, 1)
            report.scenarios_run += 1
            report.raw_scenarios.append({
                "id": scenario.id,
                "title": scenario.title,
                "events_count": len(scenario.events),
                "cards_emitted": len(cards) if scenario.events else 0,
            })

        if report.cards_emitted > 0:
            report.decision_latency_avg = total_latency / report.cards_emitted
        if total_expectations > 0:
            report.accuracy = correct_expectations / total_expectations
        return report

    def run_static(self, persona: Persona, scenarios: list[Scenario] | None = None) -> SimReport:
        """Static: deterministic scenarios, no LLM, fast."""
        if scenarios is None:
            scenarios = STATIC_SCENARIOS
        report = self._run_scenarios(persona, scenarios)
        report.mode = "static"
        return report

    def run_dynamic(self, persona: Persona, duration_sec: int = 60, events_per_sec: float = 0.5) -> SimReport:
        """Dynamic: time-based, generates events, uses real services."""
        count = int(duration_sec * events_per_sec)
        scenarios = generate_dynamic_scenarios(count, seed=hash(persona.id) % 2**31)
        report = self._run_scenarios(persona, scenarios)
        report.mode = "dynamic"
        return report

    def run_ai_generated(self, persona: Persona, llm_model: str = "qwen2.5:7b-instruct") -> SimReport:
        """AI-generated: LLM creates scenarios for persona, runs them."""
        scenarios = self._generate_scenarios_with_llm(persona, llm_model)
        report = self._run_scenarios(persona, scenarios)
        report.mode = "ai_generated"
        return report

    def _generate_scenarios_with_llm(self, persona: Persona, model: str) -> list[Scenario]:
        prompt = (
            f"You are an event generator for an AI advisor system.\n"
            f"Generate 8 realistic scenario events for this operator persona:\n"
            f"- Name: {persona.name}\n"
            f"- Role: {persona.role}\n"
            f"- Risk appetite: {persona.risk_appetite}/5\n"
            f"- Cost sensitivity: {persona.cost_sensitivity}\n"
            f"- Autonomy level: {persona.autonomy_level}\n"
            f"- Typical actions: {', '.join(persona.typical_actions)}\n\n"
            f"Available event topics:\n"
            f"aeis.idea.intake.completed\n"
            f"aeis.system.budget_config_requested\n"
            f"aeis.system.model_setup_requested\n"
            f"aeis.council.formation_requested\n"
            f"aeis.system.autonomy_policy_change_requested\n"
            f"aeis.system.runtime_topology_change_requested\n"
            f"aeis.system.skill_selection_requested\n"
            f"aeis.production.deploy_requested\n"
            f"aeis.system.vps_scaling_requested\n"
            f"aeis.idea.sot_drafted\n"
            f"aeis.masterplan.created\n"
            f"aeis.testing.completed\n\n"
            f"Return ONLY a JSON array. Each element must be an object with:\n"
            f'  "id": string, "title": string, "topic": string, "payload": object\n'
            f"No markdown, no explanation, just raw JSON."
        )

        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 2048},
        }

        try:
            req = urllib.request.Request(
                f"{self._ollama_url}/api/generate",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "")
        except Exception as exc:
            log.warning("Ollama generation failed (%s); falling back to dynamic scenarios", exc)
            return generate_dynamic_scenarios(8, seed=hash(persona.id) % 2**31)

        # Extract JSON from response (handle markdown fences)
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("\n", 1)[0]
        raw = raw.strip()

        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("Ollama response not valid JSON (%s); falling back to dynamic scenarios", exc)
            return generate_dynamic_scenarios(8, seed=hash(persona.id) % 2**31)

        scenarios: list[Scenario] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            sid = item.get("id", f"ai_{persona.id}_{idx}")
            title = item.get("title", f"AI scenario {idx}")
            topic = item.get("topic", "aeis.idea.intake.completed")
            payload = item.get("payload", {})
            if "operator_id" not in payload:
                payload["operator_id"] = f"sim_{persona.id}"
            scenarios.append(
                Scenario(
                    id=sid,
                    title=title,
                    events=[{"topic": topic, "payload": payload}],
                    expected_cards_min=1,
                )
            )

        if not scenarios:
            log.warning("Ollama returned empty scenarios; falling back to dynamic")
            return generate_dynamic_scenarios(8, seed=hash(persona.id) % 2**31)

        return scenarios
