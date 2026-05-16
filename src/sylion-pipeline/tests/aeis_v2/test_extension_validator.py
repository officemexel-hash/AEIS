"""Tests for ``sylion.aeis_v2.ontology.extension_validator`` — ADR-001 #1.

Covers all three policy modes (strict / declared / free), default injection,
type coercion edge cases (bool vs int, datetime ISO strings), and the
``_unvalidated`` routing in ``declared`` mode. Uses pytest's ``caplog``
fixture to assert warning emission for ``free`` and ``declared`` modes.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest

from sylion.aeis_v2.ontology.extension_validator import (
    ExtensionValidationError,
    _check_field_type,
    validate_extension_payload,
)
from sylion.aeis_v2.ontology.manifest import (
    ExtensionFieldDef,
    JsonbExtension,
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
)


def _build_manifest(
    type_id: str,
    policy: str,
    fields: list[ExtensionFieldDef] | None = None,
) -> ObjectTypeManifest:
    """Helper: minimal manifest with a customizable extension config.

    Avoids touching the on-disk YAML manifests so tests stay hermetic.
    """
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id,
            name_pl="Test",
            name_en="Test",
        ),
        spec=ObjectTypeSpec(
            jsonb_extension=JsonbExtension(
                field="extension",
                policy=policy,  # type: ignore[arg-type]
                extension_fields=fields or [],
            ),
        ),
    )


# --------------------------------------------------------------------------
# strict mode
# --------------------------------------------------------------------------


def test_strict_rejects_unknown_field() -> None:
    """An undeclared key must blow up in strict mode."""
    manifest = _build_manifest(
        "test_strict_unknown",
        "strict",
        [ExtensionFieldDef(name="known", type="string")],
    )
    with pytest.raises(ExtensionValidationError, match="unknown extension key"):
        validate_extension_payload({"known": "ok", "rogue": 42}, manifest)


def test_strict_rejects_type_mismatch() -> None:
    """Declared key with wrong runtime type must raise."""
    manifest = _build_manifest(
        "test_strict_type",
        "strict",
        [ExtensionFieldDef(name="age", type="integer")],
    )
    with pytest.raises(ExtensionValidationError, match="expected type 'integer'"):
        validate_extension_payload({"age": "not-a-number"}, manifest)


def test_strict_fills_default_for_missing_optional() -> None:
    """Missing declared key with a default must be filled from the manifest."""
    manifest = _build_manifest(
        "test_strict_default",
        "strict",
        [
            ExtensionFieldDef(name="tier", type="string", default="standard"),
            ExtensionFieldDef(name="loyalty", type="integer", default=0),
        ],
    )
    out = validate_extension_payload({}, manifest)
    assert out == {"tier": "standard", "loyalty": 0}


def test_strict_rejects_empty_extension_fields_when_payload_present() -> None:
    """Strict + empty schema + non-empty payload = unable-to-validate, raise."""
    manifest = _build_manifest("test_strict_empty", "strict", fields=[])
    with pytest.raises(ExtensionValidationError, match="declares no extension_fields"):
        validate_extension_payload({"foo": "bar"}, manifest)


def test_strict_rejects_bool_for_integer_field() -> None:
    """Booleans must NOT pass an integer type check (Python's int is True)."""
    manifest = _build_manifest(
        "test_strict_bool_int",
        "strict",
        [ExtensionFieldDef(name="count", type="integer")],
    )
    with pytest.raises(ExtensionValidationError, match="expected type 'integer'"):
        validate_extension_payload({"count": True}, manifest)


# --------------------------------------------------------------------------
# declared mode
# --------------------------------------------------------------------------


def test_declared_routes_unknown_to_unvalidated_subdict() -> None:
    """In declared mode, unknown keys land in ``_unvalidated`` and don't raise."""
    manifest = _build_manifest(
        "test_declared_unknown",
        "declared",
        [ExtensionFieldDef(name="email", type="string")],
    )
    out = validate_extension_payload(
        {"email": "x@y.z", "future_field": [1, 2, 3]}, manifest
    )
    assert out["email"] == "x@y.z"
    assert out["_unvalidated"] == {"future_field": [1, 2, 3]}


def test_declared_warns_but_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Declared mode emits a warning instead of raising on type mismatch."""
    manifest = _build_manifest(
        "test_declared_warn",
        "declared",
        [ExtensionFieldDef(name="age", type="integer")],
    )
    with caplog.at_level(logging.WARNING, logger="sylion.aeis_v2.ontology.extension_validator"):
        out = validate_extension_payload({"age": "thirty"}, manifest)
    # Mismatched value goes to _unvalidated, not the top level.
    assert "age" not in out or out.get("age") != "thirty"
    assert out["_unvalidated"] == {"age": "thirty"}
    assert any(
        "type mismatch" in rec.message and "age" in rec.message
        for rec in caplog.records
    ), f"expected mismatch warning, got: {[r.message for r in caplog.records]}"


# --------------------------------------------------------------------------
# free mode
# --------------------------------------------------------------------------


def test_free_passes_anything_through() -> None:
    """Free mode returns payload as-is, no validation."""
    manifest = _build_manifest("test_free_anything", "free")
    payload = {"a": 1, "b": [1, 2, {"nested": True}], "c": None}
    out = validate_extension_payload(payload, manifest)
    assert out == payload
    # Returns a fresh dict (not the same object) so callers can mutate safely.
    assert out is not payload


def test_free_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Free mode must log one warning so prod scans can flag it."""
    manifest = _build_manifest("test_free_warn", "free")
    with caplog.at_level(logging.WARNING, logger="sylion.aeis_v2.ontology.extension_validator"):
        validate_extension_payload({"x": 1}, manifest)
    assert any(
        "free" in rec.message and "test_free_warn" in rec.message
        for rec in caplog.records
    ), f"expected free-mode warning, got: {[r.message for r in caplog.records]}"


# --------------------------------------------------------------------------
# misc / edge cases
# --------------------------------------------------------------------------


def test_validator_handles_empty_payload() -> None:
    """``None`` and ``{}`` payloads must both be accepted across all policies."""
    # Strict with declared fields + empty payload → defaults applied.
    strict_m = _build_manifest(
        "empty_strict",
        "strict",
        [ExtensionFieldDef(name="foo", type="string", default="bar")],
    )
    assert validate_extension_payload(None, strict_m) == {"foo": "bar"}
    assert validate_extension_payload({}, strict_m) == {"foo": "bar"}

    # Declared with empty payload → empty dict, no _unvalidated.
    declared_m = _build_manifest(
        "empty_declared",
        "declared",
        [ExtensionFieldDef(name="foo", type="string")],
    )
    assert validate_extension_payload(None, declared_m) == {}

    # Free with empty payload → empty dict.
    free_m = _build_manifest("empty_free", "free")
    assert validate_extension_payload(None, free_m) == {}


def test_validator_recognizes_array_and_object_types() -> None:
    """The validator must accept ``array`` (list) and ``object`` (dict) declarations."""
    manifest = _build_manifest(
        "test_arr_obj",
        "strict",
        [
            ExtensionFieldDef(name="tags", type="array"),
            ExtensionFieldDef(name="meta", type="object"),
        ],
    )
    out = validate_extension_payload(
        {"tags": ["a", "b"], "meta": {"k": "v"}}, manifest
    )
    assert out == {"tags": ["a", "b"], "meta": {"k": "v"}}

    # Mismatch: array declared, scalar provided.
    with pytest.raises(ExtensionValidationError, match="expected type 'array'"):
        validate_extension_payload({"tags": "single", "meta": {}}, manifest)
    # Mismatch: object declared, list provided.
    with pytest.raises(ExtensionValidationError, match="expected type 'object'"):
        validate_extension_payload({"tags": [], "meta": [1, 2]}, manifest)


def test_check_field_type_rejects_unknown_declared_type() -> None:
    """Defensive: unknown declared_type must return False, not crash."""
    assert _check_field_type("anything", "nonexistent_type") is False


def test_check_field_type_accepts_none_universally() -> None:
    """``None`` is permitted for every declared type (nullability)."""
    for t in ("string", "integer", "boolean", "float", "datetime", "array", "object"):
        assert _check_field_type(None, t) is True


def test_validator_raises_on_non_dict_payload() -> None:
    """Anything other than dict / None must blow up cleanly."""
    manifest = _build_manifest(
        "test_non_dict",
        "strict",
        [ExtensionFieldDef(name="foo", type="string")],
    )
    with pytest.raises(ExtensionValidationError, match="must be a dict"):
        validate_extension_payload([1, 2, 3], manifest)  # type: ignore[arg-type]


def test_extension_field_def_rejects_invalid_slug() -> None:
    """ExtensionFieldDef.name must obey snake_case slug rule."""
    with pytest.raises(ValueError, match="snake_case slug"):
        ExtensionFieldDef(name="BadName", type="string")


def test_jsonb_extension_rejects_duplicate_field_names() -> None:
    """Same key declared twice in extension_fields must fail validation."""
    with pytest.raises(ValueError, match="duplicate extension_field"):
        JsonbExtension(
            extension_fields=[
                ExtensionFieldDef(name="dup", type="string"),
                ExtensionFieldDef(name="dup", type="integer"),
            ]
        )


def test_jsonb_extension_default_policy_is_strict() -> None:
    """Backward compatibility: omitting ``policy`` should yield strict."""
    je = JsonbExtension()
    assert je.policy == "strict"
    assert je.extension_fields == []
