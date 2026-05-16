"""Phase 0 of ADR-001 #1: extension JSONB validation modes.

Every W15 ``ObjectTypeManifest`` carries a JSONB ``extension`` column for
free-form per-instance data. ADR-001 (operator decision) #1 introduces a
hybrid policy on what may be written into that column:

* ``strict``   — only keys declared in ``extension_fields`` are allowed;
                 type-checked; missing optional keys filled from
                 ``ExtensionFieldDef.default``. Rejects unknown keys and
                 type mismatches with :class:`ExtensionValidationError`.
* ``declared`` — undeclared keys are routed into a sub-dict under
                 ``_unvalidated`` and a warning is logged. Declared keys
                 with type mismatch warn but do not raise. Use during
                 partial migration / dev iteration.
* ``free``     — anything goes. A warning is logged once per call so that
                 free-mode types are visible in operator log scans. Release
                 Rail (W14 E6) is responsible for blocking ``free`` types
                 from reaching production; this module only flags.

The validator is intentionally Python-side and runs on the write path
(REST handler / OSDK client / W14 simulator). It does NOT replace the
JSON Schema in ``JsonbExtension.schema_`` — that schema is kept for DDL
CHECK rendering and external tooling. The two sources of truth must
agree; G1 will add a one-shot consistency check.

Usage::

    from sylion.aeis_v2.ontology.extension_validator import (
        validate_extension_payload, ExtensionValidationError,
    )
    payload = validate_extension_payload(
        request.body["extension"], manifest=registry.get("customer")
    )
    # payload now type-checked, defaults filled in, _unvalidated bag
    # populated in 'declared' mode if any unknowns slipped through.

PDF reference: ADR-001 §1 (hybrid extension policy).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sylion.aeis_v2.ontology.manifest import (
    ExtensionFieldDef,
    ObjectTypeManifest,
)

log = logging.getLogger(__name__)


class ExtensionValidationError(ValueError):
    """Raised in ``strict`` mode for unknown keys or type mismatches.

    Inherits from :class:`ValueError` so existing broad ``except ValueError``
    handlers (REST adapters, simulator harness) continue to catch.
    """


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

# Map each ``ExtensionFieldDef.type`` value to the Python runtime
# isinstance() target(s). Booleans are excluded from int because
# ``isinstance(True, int)`` is True in Python and we want strict typing.
_TYPE_CHECKS: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "boolean": (bool,),
    "float": (float, int),  # accept int as float — JSON has no float/int split for whole numbers
    "datetime": (datetime, date, str),  # ISO strings are accepted; consumer must parse
    "array": (list, tuple),
    "object": (dict,),
}


def _check_field_type(value: Any, declared_type: str) -> bool:
    """Compare runtime ``value`` type against the declared schema ``type``.

    Returns True on match, False on mismatch. ``None`` is always accepted
    (the ``ExtensionFieldDef`` model does not currently expose ``required``;
    nullability is implicit). The integer/boolean discrimination matters
    because ``isinstance(True, int)`` is True in Python — without the
    explicit guard, a payload value of ``True`` would silently satisfy
    ``type: integer`` and corrupt downstream analytics.
    """
    if value is None:
        return True
    expected = _TYPE_CHECKS.get(declared_type)
    if expected is None:
        # Unknown declared type — defensive default: don't pass through.
        return False
    if declared_type == "integer":
        # Reject bool which is a subclass of int.
        if isinstance(value, bool):
            return False
        return isinstance(value, int)
    if declared_type == "float":
        # Reject bool here too.
        if isinstance(value, bool):
            return False
        return isinstance(value, expected)
    return isinstance(value, expected)


def _index_fields(fields: list[ExtensionFieldDef]) -> dict[str, ExtensionFieldDef]:
    """Build a name → ExtensionFieldDef lookup."""
    return {ef.name: ef for ef in fields}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def validate_extension_payload(
    payload: dict[str, Any] | None,
    manifest: ObjectTypeManifest,
) -> dict[str, Any]:
    """Validate + normalize an ``extension`` payload against a manifest's policy.

    Args:
        payload: the raw extension dict the caller wants to write. ``None``
            and ``{}`` are both accepted (treated as empty).
        manifest: the loaded :class:`ObjectTypeManifest` whose policy /
            ``extension_fields`` govern this write.

    Returns:
        The validated dict. In ``declared`` mode it may carry an
        ``_unvalidated`` key holding the bag of undeclared inputs. In
        ``strict`` mode the dict contains only declared keys; missing
        optional declarations are filled with ``ExtensionFieldDef.default``
        when that default is non-None.

    Raises:
        ExtensionValidationError: ``strict`` mode only — when an unknown
            key appears, when a value mismatches its declared type, or
            when ``extension_fields`` is empty but a non-empty payload was
            supplied (the policy can't validate anything in that case).
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ExtensionValidationError(
            f"extension payload must be a dict, got {type(payload).__name__}"
        )

    type_id = manifest.metadata.id
    policy = manifest.spec.jsonb_extension.policy
    fields = manifest.spec.jsonb_extension.extension_fields
    declared = _index_fields(fields)

    if policy == "free":
        # No validation. One-line warning so free-mode usage is grep-able
        # in production log scans (Release Rail watch).
        log.warning(
            "extension_validator: type=%s in 'free' mode — payload not validated. "
            "Release Rail (W14 E6) must block this for production.",
            type_id,
        )
        return dict(payload)

    if policy == "strict":
        if not declared and payload:
            raise ExtensionValidationError(
                f"type '{type_id}' has policy='strict' but declares no "
                "extension_fields, while a non-empty payload was supplied. "
                "Either declare the schema or switch policy to 'declared'/'free'."
            )
        # Reject unknown keys.
        unknown = sorted(set(payload) - set(declared))
        if unknown:
            raise ExtensionValidationError(
                f"type '{type_id}' (strict): unknown extension key(s) "
                f"{unknown}. Declared: {sorted(declared)}."
            )
        # Type-check declared values.
        for key, ef in declared.items():
            if key in payload and not _check_field_type(payload[key], ef.type):
                raise ExtensionValidationError(
                    f"type '{type_id}' (strict): key '{key}' expected "
                    f"type '{ef.type}', got {type(payload[key]).__name__}."
                )
        # Fill defaults for missing keys with non-None defaults.
        out: dict[str, Any] = dict(payload)
        for key, ef in declared.items():
            if key not in out and ef.default is not None:
                out[key] = ef.default
        return out

    if policy == "declared":
        out: dict[str, Any] = {}
        unvalidated: dict[str, Any] = {}
        for key, value in payload.items():
            ef = declared.get(key)
            if ef is None:
                unvalidated[key] = value
                continue
            if not _check_field_type(value, ef.type):
                log.warning(
                    "extension_validator: type=%s (declared) key '%s' type "
                    "mismatch — expected '%s', got %s. Routing to _unvalidated.",
                    type_id, key, ef.type, type(value).__name__,
                )
                unvalidated[key] = value
                continue
            out[key] = value
        # Defaults: include declared defaults that the caller omitted.
        for key, ef in declared.items():
            if key not in out and key not in unvalidated and ef.default is not None:
                out[key] = ef.default
        if unvalidated:
            log.warning(
                "extension_validator: type=%s (declared) %d undeclared/"
                "mismatched key(s) routed to _unvalidated: %s",
                type_id, len(unvalidated), sorted(unvalidated),
            )
            out["_unvalidated"] = unvalidated
        return out

    # Defensive: unreachable because Pydantic Literal already enforces it,
    # but keeps the function total.
    raise ExtensionValidationError(
        f"type '{type_id}': unknown extension policy '{policy}'"
    )


__all__ = [
    "ExtensionValidationError",
    "validate_extension_payload",
]
