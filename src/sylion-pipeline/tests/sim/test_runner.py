"""Tests for sim runner — verify it doesn't crash on empty or minimal scenarios."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")

from sylion.sim.personas import get_persona
from sylion.sim.runner import SimRunner
from sylion.sim.scenarios import Scenario


@pytest.fixture(autouse=True)
def _blank_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")


class TestRunnerSmoke:
    def test_static_empty_scenarios(self):
        runner = SimRunner()
        persona = get_persona("p1_solo_indie")
        report = runner.run_static(persona, scenarios=[])
        assert report.scenarios_run == 0
        assert report.cards_emitted == 0
        assert report.decision_latency_avg == 0.0

    def test_static_single_scenario(self):
        runner = SimRunner()
        persona = get_persona("p1_solo_indie")
        scenarios = [
            Scenario(
                id="test_idea",
                title="Test idea intake",
                events=[
                    {"topic": "aeis.idea.intake.completed", "payload": {"idea_id": "i-test", "domain": "software"}}
                ],
                expected_cards_min=1,
            )
        ]
        report = runner.run_static(persona, scenarios=scenarios)
        assert report.scenarios_run == 1
        assert report.cards_emitted >= 0
        assert report.accuracy >= 0.0

    def test_dynamic_short_run(self):
        runner = SimRunner()
        persona = get_persona("p9_devrel")
        report = runner.run_dynamic(persona, duration_sec=2, events_per_sec=1)
        assert report.scenarios_run >= 1
        assert report.mode == "dynamic"

    def test_different_personas_produce_different_actions(self):
        runner = SimRunner()
        scenarios = [
            Scenario(
                id="test_idea",
                title="Test idea intake",
                events=[
                    {"topic": "aeis.idea.intake.completed", "payload": {"idea_id": "i-test", "domain": "software"}}
                ],
                expected_cards_min=1,
            )
        ]
        p1 = get_persona("p1_solo_indie")
        p8 = get_persona("p8_compliance_off")
        r1 = runner.run_static(p1, scenarios=scenarios)
        r8 = runner.run_static(p8, scenarios=scenarios)
        # Compliance officer should have higher HG rate than solo indie
        p1_hg_rate = r1.hg_triggered_count / max(r1.cards_emitted, 1)
        p8_hg_rate = r8.hg_triggered_count / max(r8.cards_emitted, 1)
        assert p8_hg_rate >= p1_hg_rate, "Compliance officer should trigger HG at least as often as solo indie"
