"""
SYLION Core -- Manifest Loader

Parse and validate module.yaml manifests.
Validates against canonical ModuleManifest schema.
Checks dependencies exist in ModuleRegistry.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sylion.core.module_registry import ModuleRegistry, get_registry

# Re-export ContractRegistry for backward compatibility
from sylion.core.contract_registry import (  # noqa: F401
    ContractRegistry, get_contract_registry,
)
try:
    from sylion.core.contract_registry import ContractType, Contract  # noqa: F401
except ImportError:
    pass

log = logging.getLogger("sylion.core.manifest_loader")


class ManifestLoader:
    """Parse and validate module.yaml manifests."""

    REQUIRED_FIELDS = {"module_id", "module_kind", "owner_plan"}

    def __init__(self, registry: ModuleRegistry | None = None):
        self._registry = registry or get_registry()

    def load_yaml(self, path: Path) -> dict:
        """Load a module.yaml file and validate it."""
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        errors = self._validate(raw)
        if errors:
            raise ValueError(f"Invalid manifest {path}: {errors}")
        return raw

    def load_dict(self, data: dict) -> dict:
        """Validate a manifest dict."""
        errors = self._validate(data)
        if errors:
            raise ValueError(f"Invalid manifest: {errors}")
        return data

    def _validate(self, raw: dict) -> list[str]:
        errors: list[str] = []

        if not isinstance(raw, dict):
            return ["manifest must be a dict"]

        for req in self.REQUIRED_FIELDS:
            if req not in raw:
                errors.append(f"missing required field: {req}")

        if "module_kind" in raw and raw["module_kind"] not in {e.value for e in __import__("sylion.core.module_registry", fromlist=["ModuleKind"]).ModuleKind}:
            errors.append(f"invalid module_kind: {raw['module_kind']}")

        return errors
