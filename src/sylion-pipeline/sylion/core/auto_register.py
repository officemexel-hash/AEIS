"""
SYLION Core -- Auto-Register Modules from Manifests

Scans a directory of JSON manifest files and registers each module with
the ModuleRegistry.  Already-registered modules are silently skipped.
Invalid manifests are logged and skipped (no exception propagation).

Emits ``module.auto_registered`` via EventBus for each newly registered
module.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    SecurityProfile,
)

if TYPE_CHECKING:
    from sylion.core.event_bus import EventBus
    from sylion.core.module_registry import ModuleRegistry

log = logging.getLogger("sylion.core.auto_register")

# Required fields that must be present in every manifest JSON.
_REQUIRED_FIELDS = {"module_id", "module_kind", "owner_plan"}

# String-valued enums that need mapping from JSON.
_ENUM_MAP = {
    "module_kind": ModuleKind,
    "security_profile": SecurityProfile,
    "lifecycle_stage": ModuleLifecycleStage,
}


def _parse_manifest(raw: dict) -> ModuleManifest:
    """Convert a raw dict (from JSON) into a ModuleManifest."""
    kwargs: dict = {}

    for field_name, enum_cls in _ENUM_MAP.items():
        if field_name in raw:
            value = raw[field_name]
            try:
                kwargs[field_name] = enum_cls(value)
            except ValueError:
                kwargs[field_name] = enum_cls[str(value)]

    # Pass through simple fields that ModuleManifest accepts directly.
    _SIMPLE_FIELDS = (
        "module_id",
        "owner_plan",
        "implementation_strategy",
        "contract_version",
        "decision_class_entry",
        "auth_mode",
        "execution_guard",
        "audit_mode",
        "description",
        "version",
        "milestone",
    )
    for f in _SIMPLE_FIELDS:
        if f in raw:
            kwargs[f] = raw[f]

    if "depends_on" in raw:
        kwargs["depends_on"] = list(raw["depends_on"])

    return ModuleManifest(**kwargs)


def auto_register_modules(
    registry: ModuleRegistry,
    manifest_dir: str | Path,
    event_bus: EventBus | None = None,
) -> dict:
    """Auto-register all modules from manifest JSON files in *manifest_dir*.

    Parameters
    ----------
    registry:
        The :class:`ModuleRegistry` instance to register into.
    manifest_dir:
        Directory containing ``*.json`` manifest files.
    event_bus:
        Optional :class:`EventBus`.  When provided, a ``module.auto_registered``
        event is published for every newly registered module.

    Returns
    -------
    dict
        ``{"registered": N, "skipped": N, "errors": [...]}``
    """
    manifest_dir = Path(manifest_dir)

    registered = 0
    skipped = 0
    errors: list[str] = []

    # Gracefully handle missing or non-directory paths.
    if not manifest_dir.is_dir():
        log.info("manifest dir %s does not exist -- nothing to auto-register", manifest_dir)
        return {"registered": registered, "skipped": skipped, "errors": errors}

    json_files = sorted(manifest_dir.glob("*.json"))
    if not json_files:
        log.info("no manifest JSON files found in %s", manifest_dir)
        return {"registered": registered, "skipped": skipped, "errors": errors}

    pending: list[tuple[Path, dict]] = []
    for path in json_files:
        # --- load JSON -------------------------------------------------------
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            msg = f"{path.name}: load error -- {exc}"
            log.warning("auto_register: %s", msg)
            errors.append(msg)
            continue

        if not isinstance(raw, dict):
            msg = f"{path.name}: manifest must be a JSON object"
            log.warning("auto_register: %s", msg)
            errors.append(msg)
            continue

        # --- validate required fields ----------------------------------------
        missing = _REQUIRED_FIELDS - set(raw.keys())
        if missing:
            msg = f"{path.name}: missing fields {sorted(missing)}"
            log.warning("auto_register: %s", msg)
            errors.append(msg)
            continue

        pending.append((path, raw))

    unresolved: dict[str, str] = {}
    made_progress = True
    while pending and made_progress:
        made_progress = False
        next_pending: list[tuple[Path, dict]] = []

        for path, raw in pending:
            unresolved.pop(path.name, None)
            module_id = raw["module_id"]

            # --- check already registered ------------------------------------
            if registry.get(module_id) is not None:
                log.debug("auto_register: %s already registered -- skipping", module_id)
                skipped += 1
                made_progress = True
                continue

            # --- parse & register --------------------------------------------
            try:
                manifest = _parse_manifest(raw)
            except Exception as exc:
                msg = f"{path.name}: parse error -- {exc}"
                log.warning("auto_register: %s", msg)
                errors.append(msg)
                made_progress = True
                continue

            try:
                registry.register(manifest)
            except ValueError as exc:
                # Dependency errors may resolve once later manifests register.
                if "Dependency " in str(exc) and " not registered" in str(exc):
                    unresolved[path.name] = str(exc)
                    next_pending.append((path, raw))
                    continue
                # Covers "already registered" (race) and other validation errors.
                msg = f"{path.name}: register error -- {exc}"
                log.warning("auto_register: %s", msg)
                skipped += 1
                made_progress = True
                continue

            registered += 1
            made_progress = True
            log.info("auto-registered %s from %s", module_id, path.name)

            # --- emit event --------------------------------------------------
            if event_bus is not None:
                from sylion.core.event_bus import SylionEvent

                event = SylionEvent(
                    event_id="",
                    topic="module.auto_registered",
                    payload={"module_id": module_id, "source": str(path.name)},
                    source_module="auto_register",
                )
                event_bus.publish(event)

        pending = next_pending

    for path, _raw in pending:
        msg = f"{path.name}: register error -- {unresolved.get(path.name, 'unresolved dependencies')}"
        log.warning("auto_register: %s", msg)
        skipped += 1

    log.info(
        "auto_register complete: %d registered, %d skipped, %d errors",
        registered,
        skipped,
        len(errors),
    )
    return {"registered": registered, "skipped": skipped, "errors": errors}
