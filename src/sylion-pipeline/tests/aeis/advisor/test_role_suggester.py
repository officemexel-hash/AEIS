"""Contract tests for the W13 task-to-role suggester."""

from __future__ import annotations

from types import SimpleNamespace

from sylion.aeis.advisor import role_suggester as rs


def test_short_task_returns_empty_low_confidence_result():
    result = rs.suggest_pipeline("ab")

    assert result.confidence == 0.0
    assert result.steps == []
    assert result.detected_categories == []
    assert result.to_dict()["steps"] == []


def test_unknown_task_uses_default_pipeline_and_manual_review_note():
    result = rs.suggest_pipeline("orchestrate ambiguous work")

    assert result.confidence == 0.3
    assert [step.role_id for step in result.steps] == ["researcher", "planner", "project_manager"]
    assert any("Confidence" in note for note in result.notes_pl)


def test_long_form_task_builds_deduplicated_pipeline():
    result = rs.suggest_pipeline("write book analysis and fact review")

    roles = [step.role_id for step in result.steps]
    assert roles[:3] == ["researcher", "strategist", "ghostwriter"]
    assert "fact_checker" in roles
    assert len(roles) == len(set(roles))
    assert result.estimated_total_minutes == sum(step.estimated_minutes for step in result.steps)
    assert result.estimated_total_cost_usd > 0


def test_code_security_backend_task_combines_templates_in_signal_order():
    categories, signals = rs._detect_signals("implement backend api security tests")
    roles, primary = rs._pick_pipeline(signals)

    assert categories[:2] == ["code", "web"]
    assert signals[:2] == ["implementation", "testing"]
    assert primary == "implementation"
    assert "code_implementer" in roles
    assert "security_auditor" in roles
    assert "backend_specialist" in roles


def test_catalog_models_are_selected_against_available_models(monkeypatch):
    fake_role = SimpleNamespace(
        preferred_models=["expensive-model", "available-model"],
        fallback_models=["fallback-model"],
        cost_profile="high",
    )
    monkeypatch.setattr(
        rs,
        "_load_role_catalog",
        lambda: {"get_role": lambda role_id: fake_role},
    )

    result = rs.suggest_pipeline("write article", available_models=["available-model", "fallback-model"])
    first_step = result.steps[0]

    assert first_step.preferred_model == "available-model"
    assert first_step.fallback_model == "fallback-model"
    assert first_step.cost_profile == "high"
    assert result.estimated_total_cost_usd >= 1.0


def test_unavailable_catalog_preferred_model_is_reported(monkeypatch):
    fake_role = SimpleNamespace(
        preferred_models=["missing-model"],
        fallback_models=["fallback-model"],
        cost_profile="low",
    )
    monkeypatch.setattr(
        rs,
        "_load_role_catalog",
        lambda: {"get_role": lambda role_id: fake_role},
    )

    result = rs.suggest_pipeline("make logo", available_models=["fallback-model"])

    assert result.steps[0].preferred_model == "missing-model"
    assert any("Niedostepne preferred_models" in note for note in result.notes_pl)


def test_unknown_catalog_role_keeps_role_id_and_adds_rationale():
    step = rs._augment_step(
        "unknown_role",
        "reason",
        {"get_role": lambda role_id: None},
        available_models=set(),
    )

    assert step.role_id == "unknown_role"
    assert "rola nieznana" in step.rationale_pl


def test_audio_visual_and_mobile_tasks_map_to_expected_specialists():
    result = rs.suggest_pipeline("video podcast android frontend design")
    roles = [step.role_id for step in result.steps]

    assert "video_editor" in roles
    assert "sound_designer" in roles
    assert "transcriber" in roles
    assert "android_specialist" in roles
    assert "frontend_specialist" in roles
    assert result.confidence == 0.95
