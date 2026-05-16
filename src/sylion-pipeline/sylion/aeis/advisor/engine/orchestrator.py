"""Engine orchestrator — coordinates the full event-to-card pipeline.

Steps per `00_master_spec.md` §4:

  1. event arrives -> match against active rules
  2. for each matching rule, build CardContext (preferences, pricing, history,
     council snapshot)
  3. resolve LLM judge model, call rationale + alternatives prompts, audit calls
  4. compute 4-component confidence (with x0.8 multiplier on local fallback)
  5. assign D-level via 5 upgrade rules
  6. determine if Evidence Pack required (D5 full / D3+ light)
  7. build header + body + envelope, validate, persist, emit
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from sylion.aeis.advisor.engine._db import (
    insert_evidence_pack,
    insert_recommendation,
    insert_rule_firing,
)
from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    CardContext,
    DecisionCard,
    EvidencePack,
    OnboardingCard,
    Rule,
    RuleFiring,
    new_uuid,
)
from sylion.aeis.advisor.engine.card_builder import (
    EnvelopeValidationError,
    build_decision_card,
    build_envelope,
    build_header,
    validate_envelope,
)
from sylion.aeis.advisor.engine.confidence import calculate_confidence
from sylion.aeis.advisor.engine.d_ladder import (
    EvidencePackRequirement,
    assign_d_level,
    determine_evidence_pack_requirement,
)
from sylion.aeis.advisor.engine.llm_judge import (
    get_client,
    parse_json_response,
    record_audit,
    resolve_judge_model,
)
from sylion.aeis.advisor.engine.llm_judge.prompts import (
    evidence_fidelity_prompt,
    evidence_rationale_prompt,
    evidence_rollback_prompt,
    rationale_prompt,
)
from sylion.aeis.advisor.engine.rule_engine import match_event_to_rules

log = logging.getLogger("sylion.aeis.advisor.engine.orchestrator")


def process_event(
    *,
    topic: str,
    payload: dict[str, Any],
    operator_id: str,
    triggering_event_id: str = "",
    sync_gate: bool = False,
) -> list[AdvisorCardEnvelope]:
    """Run rule -> judge -> card pipeline for a single event."""
    context_for_dsl = _build_dsl_context(topic=topic, payload=payload, operator_id=operator_id)
    context_for_dsl["sync_gate"] = sync_gate
    rule_matches = match_event_to_rules(topic, context_for_dsl)

    if not rule_matches:
        log.debug("no rules matched for topic=%s", topic)
        return []

    cards: list[AdvisorCardEnvelope] = []
    for rule, debug_path in rule_matches:
        try:
            env = _build_card_for_rule(
                rule=rule,
                topic=topic,
                payload=payload,
                operator_id=operator_id,
                triggering_event_id=triggering_event_id,
                debug_path=debug_path,
            )
            if env is not None:
                cards.append(env)
        except Exception:
            log.exception("rule %s failed during card build", rule.rule_id)
            insert_rule_firing(
                RuleFiring(
                    rule_id=rule.rule_id,
                    rule_version=rule.version,
                    triggering_event_id=triggering_event_id,
                    context=context_for_dsl,
                    decision_taken="failed",
                )
            )
    return cards


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def _build_dsl_context(*, topic: str, payload: dict[str, Any], operator_id: str = "") -> dict[str, Any]:
    """Surface helpers DSL rules can target."""
    payload_dict = dict(payload or {})
    return {
        "topic": topic,
        "payload": payload_dict,
        # Computed convenience fields
        "_match_council_preference": _match_council_preference(payload_dict, operator_id=operator_id),
    }


def _match_council_preference(payload: dict[str, Any], *, operator_id: str = "") -> bool:
    """Return True if proposed Council size matches the saved operator preference."""
    preferred = payload.get("preferred_council_size")
    if preferred is None and operator_id:
        prefs = _load_operator_preferences(
            operator_id=operator_id,
            project_type=str(payload.get("project_type") or payload.get("type") or ""),
            project_domain=str(payload.get("project_domain") or payload.get("domain") or ""),
        )
        preferred = prefs.get("council_size")
    if preferred is None:
        preferred = 5
    proposed = payload.get("proposed_council_size")
    if proposed is None:
        return True
    try:
        return int(proposed) == preferred
    except (TypeError, ValueError):
        return True


def _build_card_context(
    *,
    rule: Rule,
    topic: str,
    payload: dict[str, Any],
    operator_id: str,
    triggering_event_id: str,
) -> CardContext:
    project_type = str(payload.get("project_type") or payload.get("type") or "")
    project_domain = str(payload.get("project_domain") or payload.get("domain") or "")
    project_id = str(payload.get("project_id") or "")
    idea_id = str(payload.get("idea_id") or "")

    preferences = _load_operator_preferences(
        operator_id=operator_id,
        project_type=project_type,
        project_domain=project_domain,
    )
    preferences["__changing_keys__"] = list(payload.get("changing_preference_keys") or [])
    pricing_snapshot: dict[str, Any] = {"source_label": "assumption", "is_assumption": True}
    history_snapshot: dict[str, Any] = {}
    council_snapshot: dict[str, Any] = {}

    risk_level = _infer_risk_level(rule.recommendation_type, payload)
    cost_estimate = float(payload.get("estimated_cost_usd") or 0.0)
    affects_production = bool(payload.get("is_production")) or "production" in project_type
    affects_multiple = bool(payload.get("affects_multiple_projects"))
    rollback_days = float(payload.get("rollback_days") or 0.0)
    rollback_data_loss = bool(payload.get("rollback_data_loss"))

    return CardContext(
        operator_id=operator_id,
        triggering_event_topic=topic,
        triggering_event_payload=payload,
        triggering_event_id=triggering_event_id,
        project_id=project_id,
        project_type=project_type,
        project_domain=project_domain,
        idea_id=idea_id,
        rule=rule,
        preferences=preferences,
        pricing_snapshot=pricing_snapshot,
        history_snapshot=history_snapshot,
        council_snapshot=council_snapshot,
        risk_level=risk_level,
        cost_estimate_usd=cost_estimate,
        affects_production=affects_production,
        affects_multiple_projects=affects_multiple,
        rollback_takes_days=rollback_days,
        rollback_data_loss=rollback_data_loss,
        autonomy_level=str(preferences.get("autonomy_level") or "suggest"),
    )


def _infer_risk_level(recommendation_type: str, payload: dict[str, Any]) -> str:
    explicit = payload.get("risk_level")
    if isinstance(explicit, str) and explicit in ("low", "medium", "high", "critical"):
        return explicit
    if recommendation_type == "REC_TYPE_BLOCK_PRODUCTION_DEPLOY":
        return "critical"
    if recommendation_type in {"REC_TYPE_VPS_SCALING", "REC_TYPE_AUTONOMY_POLICY"}:
        return "high"
    if recommendation_type in {"REC_TYPE_PURCHASE_PLAN", "REC_TYPE_BUDGET_CONFIG"}:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Card construction per rule
# ---------------------------------------------------------------------------


def _build_card_for_rule(
    *,
    rule: Rule,
    topic: str,
    payload: dict[str, Any],
    operator_id: str,
    triggering_event_id: str,
    debug_path: str,
) -> AdvisorCardEnvelope | None:
    context = _build_card_context(
        rule=rule,
        topic=topic,
        payload=payload,
        operator_id=operator_id,
        triggering_event_id=triggering_event_id,
    )

    # 1) LLM judge — rationale + alternatives in one call
    judge_output, audit_id, used_local_fallback = _call_rationale_judge(
        context=context,
        recommendation_type=rule.recommendation_type,
        operator_id=operator_id,
    )

    # 2) confidence
    confidence = calculate_confidence(
        council_snapshot=context.council_snapshot,
        history_snapshot=context.history_snapshot,
        pricing_snapshot=context.pricing_snapshot,
        used_local_fallback=used_local_fallback,
    )

    # 3) D-level + Evidence Pack requirement
    assignment = assign_d_level(
        recommendation_type=rule.recommendation_type,
        suggestion_type=None,
        context=context,
    )
    pack_requirement = determine_evidence_pack_requirement(
        d_level=assignment.final_level,
        recommendation_type=rule.recommendation_type,
    )

    # 4) Evidence Pack creation if required
    evidence_pack_id = ""
    if pack_requirement != EvidencePackRequirement.NONE:
        evidence_pack_id = _create_evidence_pack(
            context=context,
            recommendation_type=rule.recommendation_type,
            d_level=assignment.final_level,
            pack_template=("d5_full" if pack_requirement == EvidencePackRequirement.FULL else "d3_light"),
            confidence=confidence,
            related_audit_ids=[audit_id] if audit_id else [],
        )

    # 5) Build body
    if rule.recommendation_type == "REC_TYPE_IDEA_INTAKE_GUIDANCE":
        body = build_decision_card(
            context=context,
            judge_output=judge_output,
            recommendation_type=rule.recommendation_type,
        )
    else:
        body = build_decision_card(
            context=context,
            judge_output=judge_output,
            recommendation_type=rule.recommendation_type,
        )

    # 6) Header
    title = _title_for_rule(rule, topic, payload)
    sources = ["rule_engine", "llm_judge"] if not used_local_fallback else ["rule_engine", "llm_judge", "history_match"]
    header = build_header(
        context=context,
        title=title,
        rationale=str(judge_output.get("rationale", ""))[:8000] or _default_rationale(rule.recommendation_type),
        risk_level=context.risk_level,
        risk_explanation=str(judge_output.get("risk_explanation", "")),
        confidence=confidence,
        sources=sources,
        d_level=assignment.final_level,
        d_level_trace=assignment.trace(),
        evidence_pack_id=evidence_pack_id,
        llm_judge_audit_id=audit_id,
        history_based=bool(context.history_snapshot),
        related_history_card_ids=[],
        push_priority=_push_priority_for_risk(context.risk_level),
        requires_biometric=context.risk_level in ("high", "critical") or assignment.final_level in ("D4", "D5"),
        card_type="decision",
    )

    env = build_envelope(header=header, body=body)

    # 7) Validate, persist, emit
    errors = validate_envelope(env)
    if errors:
        log.error("envelope validation failed (%d errors): %s", len(errors), errors)
        insert_rule_firing(
            RuleFiring(
                rule_id=rule.rule_id,
                rule_version=rule.version,
                triggering_event_id=triggering_event_id,
                context={"errors": errors, "debug_path": debug_path},
                decision_taken="schema_validation_failed",
            )
        )
        _emit_internal_event(
            "aeis.advisor.events.validation_failed",
            {"errors": errors, "rule_id": rule.rule_id, "topic": topic},
        )
        return None

    insert_recommendation(env)
    insert_rule_firing(
        RuleFiring(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            triggering_event_id=triggering_event_id,
            context={"debug_path": debug_path, "d_level": assignment.final_level},
            produced_card_id=header.card_id,
            decision_taken="emit",
        )
    )

    _emit_internal_event(
        "aeis.advisor.engine.recommendation_emitted",
        {
            "card_id": header.card_id,
            "rule_id": rule.rule_id,
            "operator_id": operator_id,
            "risk_level": header.risk_level,
            "d_level": header.d_level,
            "card_type": header.card_type,
            "project_id": header.project_id,
            "evidence_pack_id": header.evidence_pack_id,
        },
    )

    if used_local_fallback:
        _emit_internal_event(
            "aeis.advisor.engine.local_fallback_used",
            {"card_id": header.card_id, "operator_id": operator_id},
        )

    return env


# ---------------------------------------------------------------------------
# LLM judge call wrapping
# ---------------------------------------------------------------------------


def _call_rationale_judge(
    *,
    context: CardContext,
    recommendation_type: str,
    operator_id: str,
) -> tuple[dict[str, Any], str, bool]:
    routing = resolve_judge_model(
        judge_purpose="rationale",
        risk_level=context.risk_level,
        operator_preferences=context.preferences,
    )
    prompt = rationale_prompt(
        recommendation_type=recommendation_type,
        risk_level=context.risk_level,
        project_type=context.project_type,
        project_domain=context.project_domain,
        context=_judge_prompt_context(context=context, operator_id=operator_id),
    )

    client = get_client()
    models_to_try = _dedupe_model_chain(routing.fallback_chain or [routing.primary_model_id])
    parent_audit_id: str | None = None
    last_audit_id = ""
    last_reason = "no_model_attempted"

    for attempt_index, model_id in enumerate(models_to_try):
        response = client.call(model_id, prompt)
        parsed = parse_json_response(response.text, default={})
        valid, reason = _validate_judge_output(parsed)
        if not valid:
            response.error = response.error or f"invalid_judge_output:{reason}"
            last_audit_id = record_audit(
                operator_id=operator_id,
                judge_purpose="rationale",
                prompt=prompt,
                response=response,
                parent_audit_id=parent_audit_id,
            )
            parent_audit_id = parent_audit_id or last_audit_id
            last_reason = reason
            log.warning(
                "LLM judge output rejected model=%s recommendation=%s reason=%s",
                model_id,
                recommendation_type,
                reason,
            )
            continue

        audit_id = record_audit(
            operator_id=operator_id,
            judge_purpose="rationale",
            prompt=prompt,
            response=response,
            parent_audit_id=parent_audit_id,
        )
        parsed["_llm_judge_cost_usd"] = response.cost_usd
        parsed["_llm_judge_prompt_tokens"] = response.prompt_tokens
        parsed["_llm_judge_response_tokens"] = response.response_tokens
        parsed["_llm_judge_latency_ms"] = response.latency_ms
        parsed["_llm_judge_model_id"] = response.model_id
        used_local_fallback = (
            response.was_stub
            or response.provider_id == "ollama_local"
            or bool(getattr(response, "fallback_used", False) and response.provider_id == "ollama_local")
            or routing.reason == "local_fallback"
            or (attempt_index > 0 and response.provider_id == "ollama_local")
        )
        return parsed, audit_id, used_local_fallback

    raise RuntimeError(
        f"LLM judge did not return required structured JSON for {recommendation_type}; "
        f"last_audit_id={last_audit_id}; last_reason={last_reason}"
    )


def _dedupe_model_chain(models: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for model in models:
        model_id = str(model or "").strip()
        if model_id and model_id not in seen:
            seen.add(model_id)
            out.append(model_id)
    return out


def _validate_judge_output(parsed: Any) -> tuple[bool, str]:
    if not isinstance(parsed, dict):
        return False, "not_json_object"
    rationale = str(parsed.get("rationale") or "").strip()
    if len(rationale) < 120:
        return False, "rationale_too_short_or_missing"
    if rationale.upper() == "OK":
        return False, "smoke_test_response"
    for key in ("expected_benefit", "expected_downside", "quality_impact"):
        if not str(parsed.get(key) or "").strip():
            return False, f"missing_{key}"
    alternatives = parsed.get("alternatives")
    if alternatives is not None and not isinstance(alternatives, list):
        return False, "alternatives_not_list"
    return True, ""


_SECRET_FIELD_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|authorization|bearer)",
    re.IGNORECASE,
)


def _judge_prompt_context(*, context: CardContext, operator_id: str) -> dict[str, Any]:
    """Build redacted, semantically complete context for LLM Judge.

    The runtime must not ask a model to judge a project while showing only
    field names. It needs the actual idea/title/domain values, with secret-like
    fields masked before they reach the prompt/audit log.
    """
    payload = context.triggering_event_payload or {}
    return {
        "topic": context.triggering_event_topic,
        "operator_id": operator_id,
        "project_id": context.project_id,
        "idea_id": context.idea_id,
        "project_type": context.project_type,
        "project_domain": context.project_domain,
        "risk_level": context.risk_level,
        "payload_keys": list(payload.keys()),
        "payload": _redact_for_judge(payload),
        "preferences": _redact_for_judge({
            "autonomy_level": context.autonomy_level,
            "llm_judge_routing": context.preferences.get("llm_judge_routing"),
            "cost_ceilings": context.preferences.get("cost_ceilings"),
            "quality_speed_cost": context.preferences.get("quality_speed_cost"),
            "funding_model_profile": context.preferences.get("funding_model_profile"),
        }),
    }


def _redact_for_judge(value: Any, *, field_name: str = "", depth: int = 0) -> Any:
    if _SECRET_FIELD_RE.search(field_name or ""):
        return "<redacted>"
    if depth > 6:
        return "<truncated>"
    if isinstance(value, dict):
        return {
            str(k): _redact_for_judge(v, field_name=str(k), depth=depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_judge(v, field_name=field_name, depth=depth + 1) for v in value[:25]]
    if isinstance(value, str):
        return value[:1500]
    return value


# ---------------------------------------------------------------------------
# Evidence Pack creation
# ---------------------------------------------------------------------------


def _create_evidence_pack(
    *,
    context: CardContext,
    recommendation_type: str,
    d_level: str,
    pack_template: str,
    confidence,
    related_audit_ids: list[str],
) -> str:
    decision_class = _decision_class_for(recommendation_type)
    pack = EvidencePack(
        evidence_pack_id=new_uuid(),
        card_id="",  # filled when card emits; back-reference via card.evidence_pack_id
        d_level=d_level,
        pack_template=pack_template,
        decision_class=decision_class,
        domain=context.project_domain or "system",
        rationale=_evidence_rationale(context, decision_class, related_audit_ids),
        rollback_plan=_evidence_rollback(context, decision_class, related_audit_ids),
        fidelity_test=_evidence_fidelity(context, decision_class, related_audit_ids),
        confidence_breakdown=confidence.as_dict(),
        historical_acceptance_rate=confidence.historical_acceptance_rate,
        llm_judge_audit_ids=related_audit_ids,
        simulation_results=[],
        created_by=context.operator_id,
        status="draft",
    )
    insert_evidence_pack(pack)
    _emit_internal_event(
        "aeis.advisor.engine.evidence_pack_required",
        {
            "evidence_pack_id": pack.evidence_pack_id,
            "decision_class": decision_class,
            "d_level": d_level,
            "operator_id": context.operator_id,
            "pack_template": pack_template,
        },
    )
    return pack.evidence_pack_id


def _decision_class_for(recommendation_type: str) -> str:
    if recommendation_type.startswith("REC_TYPE_PURCHASE") or recommendation_type in {
        "REC_TYPE_DOWNGRADE_PLAN",
        "REC_TYPE_CANCEL_PLAN",
    }:
        return "subscription_change"
    if recommendation_type in {"REC_TYPE_BLOCK_PRODUCTION_DEPLOY", "REC_TYPE_PRODUCTION_EXECUTION"}:
        return "production_deploy"
    if recommendation_type == "REC_TYPE_VPS_SCALING":
        return "scaling_decision"
    if recommendation_type == "REC_TYPE_AUTONOMY_POLICY":
        return "autonomy_change"
    return "advisor_recommendation"


def _load_operator_preferences(
    *,
    operator_id: str,
    project_type: str | None = None,
    project_domain: str | None = None,
) -> dict[str, Any]:
    """Read runtime preferences selected in onboarding for AdvisorEngine calls."""
    keys = [
        "autonomy_level",
        "council_size",
        "quality_speed_cost",
        "trusted_providers",
        "blocked_providers",
        "funding_model_profile",
        "cost_ceilings",
        "llm_judge_routing",
        "llm_judge_routing_override",
        "default_project_domain",
    ]
    prefs: dict[str, Any] = {}
    try:
        from sylion.aeis.advisor.preferences.service import get_preferences_service

        service = get_preferences_service()
        for key in keys:
            try:
                resolved = service.get_effective(
                    user_id=operator_id,
                    project_type=project_type or None,
                    project_domain=project_domain or None,
                    preference_key=key,
                )
                value = getattr(resolved, "value", None)
                if value is not None:
                    prefs[key] = value
            except Exception:
                log.debug("preference lookup failed key=%s operator=%s", key, operator_id, exc_info=True)
    except Exception:
        log.debug("preferences service unavailable for operator=%s", operator_id, exc_info=True)

    routing = prefs.get("llm_judge_routing")
    if isinstance(routing, dict) and "llm_judge_routing_override" not in prefs:
        prefs["llm_judge_routing_override"] = {"rationale": routing}
    return prefs


def _evidence_rationale(context: CardContext, decision_class: str, audit_ids: list[str]) -> str:
    routing = resolve_judge_model(judge_purpose="evidence_rationale")
    prompt = evidence_rationale_prompt(
        decision_class=decision_class,
        context={
            "context": context.triggering_event_payload,
            "domain": context.project_domain,
            "related_audit_ids": audit_ids,
        },
    )
    response = get_client().call(routing.primary_model_id, prompt)
    record_audit(
        operator_id=context.operator_id,
        judge_purpose="evidence_rationale",
        prompt=prompt,
        response=response,
    )
    parsed = parse_json_response(response.text, default={})
    text = parsed.get("rationale") if isinstance(parsed, dict) else None
    return text or response.text or _default_evidence_text("rationale", decision_class)


def _evidence_rollback(context: CardContext, decision_class: str, audit_ids: list[str]) -> str:
    routing = resolve_judge_model(judge_purpose="evidence_rollback")
    prompt = evidence_rollback_prompt(
        decision_class=decision_class,
        context={"domain": context.project_domain, "related_audit_ids": audit_ids},
    )
    response = get_client().call(routing.primary_model_id, prompt)
    record_audit(
        operator_id=context.operator_id,
        judge_purpose="evidence_rollback",
        prompt=prompt,
        response=response,
    )
    parsed = parse_json_response(response.text, default={})
    text = parsed.get("rollback_plan") if isinstance(parsed, dict) else None
    return text or response.text or _default_evidence_text("rollback", decision_class)


def _evidence_fidelity(context: CardContext, decision_class: str, audit_ids: list[str]) -> str:
    routing = resolve_judge_model(judge_purpose="evidence_fidelity")
    prompt = evidence_fidelity_prompt(
        decision_class=decision_class,
        context={"domain": context.project_domain, "related_audit_ids": audit_ids},
    )
    response = get_client().call(routing.primary_model_id, prompt)
    record_audit(
        operator_id=context.operator_id,
        judge_purpose="evidence_fidelity",
        prompt=prompt,
        response=response,
    )
    parsed = parse_json_response(response.text, default={})
    text = parsed.get("fidelity_test") if isinstance(parsed, dict) else None
    return text or response.text or _default_evidence_text("fidelity_test", decision_class)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _title_for_rule(rule: Rule, topic: str, payload: dict[str, Any]) -> str:
    base = rule.description or rule.recommendation_type or "Advisor recommendation"
    return base[:120]


def _default_rationale(recommendation_type: str) -> str:
    return (
        f"Doradca ocenil zdarzenie lifecycle i przygotowal rekomendacje {recommendation_type} "
        "na podstawie dopasowania reguly oraz odpowiedzi sedziego LLM. Szczegolowe "
        "uzasadnienie nie zostalo wygenerowane w tym srodowisku, dlatego karta zachowuje "
        "minimalne uzasadnienie operacyjne zamiast ukrywac problem."
    )


def _default_evidence_text(part: str, decision_class: str) -> str:
    if part == "rationale":
        return (
            f"Ta klasa decyzji ({decision_class}) wymaga Evidence Pack. Doradca przygotowal "
            "minimalne uzasadnienie, bo sedzia LLM nie zwrocil pelnej tresci. Operator musi "
            "uzupelnic je przed podpisem: opisac problem, alternatywy, powod wyboru oraz "
            "oczekiwane wyniki."
        )
    if part == "rollback":
        return (
            f"Plan rollback ({decision_class}): krokowa procedura wycofania. Kazdy krok "
            "powinien zawierac akcje, szacowany czas, odpowiedzialnego (operator | "
            "dostawca | system) oraz kryterium wykrycia potrzeby rollbacku."
        )
    return (
        f"Test zgodnosci ({decision_class}): zdefiniuj mierzalna metryke sukcesu, okno "
        "pomiarowe, zrodlo danych i dopuszczalna tolerancje. Metryka musi byc "
        "weryfikowalna po decyzji."
    )


def _push_priority_for_risk(risk: str) -> str:
    return {
        "low": "low",
        "medium": "normal",
        "high": "high",
        "critical": "urgent",
    }.get(risk, "normal")


def _emit_internal_event(topic: str, payload: dict[str, Any]) -> None:
    """Try to emit on the existing event_bus; never raise on bus errors."""
    try:
        from sylion.core.event_bus import EventBus, SylionEvent

        bus = _get_event_bus()
        if bus is None:
            return
        event = SylionEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            source_module="sylion.aeis.advisor.engine",
            timestamp=time.time(),
        )
        if hasattr(bus, "publish"):
            bus.publish(event)
    except Exception:
        log.debug("event_bus emit failed for topic=%s (engine continues)", topic)


def _get_event_bus():
    try:
        from sylion.core.event_bus_factory import get_event_bus
        return get_event_bus()
    except Exception:
        try:
            from sylion.core.event_backbone import get_event_backbone
            return get_event_backbone()
        except Exception:
            return None
