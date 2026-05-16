"""W15 Object Type Registry — runtime catalog of loaded manifests.

The registry is the single source of truth for "which types exist now"
in this running instance. It is populated at import / startup time from
the manifests directory, and used by:

- REST routes (``sylion/api/ontology_routes.py``) to dispatch CRUD
- OSDK generator to emit Python classes
- W16 Apps Builder to introspect what types are bindable
- W18 Operator Terminal to surface "available types" in command palette

Phase 0 implementation is in-process only (no PG persistence). Manifests
live on disk as the source of truth; the registry caches their parsed
form. To reload after editing a manifest, call ``registry.reload()``.

Multi-instance v2 (with W17 central plane) will eventually replicate the
registry across nodes via the deployment plane — out of scope here.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Iterable

from sylion.aeis_v2.ontology.manifest import (
    ManifestValidationError,
    ObjectTypeManifest,
    load_manifest_dir,
    validate_relations,
)

log = logging.getLogger(__name__)


# Default location of object type manifests on disk. Other directories can
# be registered explicitly with ``register_dir()`` (e.g. tests, plugins).
DEFAULT_MANIFEST_DIR = (
    Path(__file__).resolve().parent / "manifests"
)


class ObjectTypeRegistry:
    """Thread-safe in-memory map of ``type_id → ObjectTypeManifest``."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._manifests: dict[str, ObjectTypeManifest] = {}
        # Where each manifest came from (for diagnostics + reload).
        self._sources: dict[str, Path] = {}
        # Directories that contributed to the registry. Reload re-walks
        # all of them. Insertion order preserved for predictable conflict
        # resolution: later sources override earlier ones.
        self._dirs: list[Path] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register_dir(self, directory: Path | str) -> int:
        """Load every manifest in *directory* and add to registry.

        Returns the count of new+updated manifests. On validation error
        the partially loaded directory is rolled back — the registry
        never ends up half-populated.
        """
        d = Path(directory).resolve()
        with self._lock:
            try:
                fresh = load_manifest_dir(d)
            except ManifestValidationError:
                raise
            for mid, manifest in fresh.items():
                self._manifests[mid] = manifest
                # source = first .yaml under d that matches mid (fallback)
                guess = d / f"{mid}.yaml"
                self._sources[mid] = guess if guess.exists() else d
            if d not in self._dirs:
                self._dirs.append(d)
            log.info(
                "ontology registry: %d manifest(s) loaded from %s "
                "(total %d type(s))",
                len(fresh), d, len(self._manifests),
            )
            return len(fresh)

    def register_manifest(self, manifest: ObjectTypeManifest, source: Path | None = None) -> None:
        """Add or replace a single manifest in the registry."""
        with self._lock:
            self._manifests[manifest.metadata.id] = manifest
            if source:
                self._sources[manifest.metadata.id] = source

    def reload(self) -> int:
        """Drop all manifests and re-walk every registered directory ATOMICALLY.

        P1-5 fix: previously reload() cleared state then loaded each dir;
        a failure mid-load left the registry half-populated. Now we build
        a fresh state in a local var and swap it in only after every dir
        loaded successfully. Failure raises ManifestValidationError WITHOUT
        touching the live registry.

        Returns total manifests in the registry after reload.
        """
        with self._lock:
            old_dirs = self._dirs.copy()
            # Build fresh state separately — DO NOT mutate self until success.
            new_manifests: dict[str, ObjectTypeManifest] = {}
            new_sources: dict[str, Path] = {}
            new_dirs: list[Path] = []
            for d in old_dirs:
                if not d.is_dir():
                    log.warning("registry.reload(): directory %s no longer exists", d)
                    continue
                # load_manifest_dir raises on validation failure — we propagate
                # WITHOUT having touched live state.
                fresh = load_manifest_dir(d)
                for mid, manifest in fresh.items():
                    if mid in new_manifests:
                        raise ManifestValidationError(
                            f"reload: duplicate metadata.id '{mid}' across dirs",
                            path=d,
                        )
                    new_manifests[mid] = manifest
                    guess = d / f"{mid}.yaml"
                    new_sources[mid] = guess if guess.exists() else d
                new_dirs.append(d)
            # W15 cross-manifest orphan-relation detector. Run BEFORE the
            # atomic swap so that a typo like `target='custmer'` is rejected
            # without ever poisoning the live registry. The registry is the
            # right place for this check because it is the only point where
            # every manifest is simultaneously in scope. Set env var
            # SYLION_SKIP_RELATION_VALIDATION=1 to bypass (dev-mode only;
            # see :func:`validate_relations` docstring for the safety note).
            errors = validate_relations(list(new_manifests.values()))
            if errors:
                raise ManifestValidationError(
                    f"Cross-manifest validation failed ({len(errors)} errors):\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )
            # Atomic swap — every dir loaded successfully.
            self._manifests = new_manifests
            self._sources = new_sources
            self._dirs = new_dirs
            log.info("registry.reload(): atomic swap, %d types loaded", len(new_manifests))
            return len(new_manifests)

    # ------------------------------------------------------------------
    # Read access
    # ------------------------------------------------------------------

    def get(self, type_id: str) -> ObjectTypeManifest | None:
        with self._lock:
            return self._manifests.get(type_id)

    def __contains__(self, type_id: str) -> bool:
        with self._lock:
            return type_id in self._manifests

    def __len__(self) -> int:
        with self._lock:
            return len(self._manifests)

    def __iter__(self) -> Iterable[ObjectTypeManifest]:
        with self._lock:
            # Snapshot to avoid race during iteration.
            return iter(list(self._manifests.values()))

    def list_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._manifests.keys())

    def list_summaries(self) -> list[dict[str, str]]:
        """Compact diagnostic summary suitable for ``GET /api/v1/ontology/types``."""
        with self._lock:
            return [
                {
                    "id": m.metadata.id,
                    "name_pl": m.metadata.name_pl,
                    "name_en": m.metadata.name_en,
                    "version": m.metadata.version,
                    "d_level": m.metadata.d_level,
                    "tags": ",".join(m.metadata.tags),
                    "actions": str(len(m.spec.actions)),
                    "dedicated_columns": str(len(m.spec.dedicated_columns)),
                    "relations": str(len(m.spec.relations)),
                    "audit_enabled": str(m.spec.audit.enabled).lower(),
                    "search_enabled": str(m.spec.search.enabled).lower(),
                    "source": str(self._sources.get(m.metadata.id, "?")),
                }
                for m in sorted(self._manifests.values(),
                                key=lambda x: x.metadata.id)
            ]

    def source_of(self, type_id: str) -> Path | None:
        with self._lock:
            return self._sources.get(type_id)


# --------------------------------------------------------------------------
# Process-wide singleton
# --------------------------------------------------------------------------

_singleton: ObjectTypeRegistry | None = None
_singleton_lock = threading.Lock()


def _walk_manifest_dirs(root: Path) -> list[Path]:
    """Yield ``root`` plus every subdir that contains at least one ``*.yaml``.

    ``load_manifest_dir`` is non-recursive by design (so people can drop
    sidecar YAMLs into a parent dir without them being picked up). For
    multi-namespace registries (e.g. ``manifests/`` for v2 + ``manifests/w14/``
    for the W14 lift) we scan one level deep.
    """
    out: list[Path] = []
    if not root.is_dir():
        return out
    if any(root.glob("*.yaml")):
        out.append(root)
    for sub in sorted(root.iterdir()):
        if not sub.is_dir() or sub.name.startswith((".", "_", "__")):
            continue
        if any(sub.glob("*.yaml")):
            out.append(sub)
    return out


def get_registry() -> ObjectTypeRegistry:
    """Return the shared registry, initializing it on first call.

    On first init we attempt to load ``DEFAULT_MANIFEST_DIR`` AND every
    immediate subdirectory of it (one level deep) so multi-namespace
    layouts like ``manifests/<root> + manifests/w14/`` work without
    explicit re-registration. Failures during this auto-load are
    *logged*, not raised — we don't want a malformed manifest to break
    the entire backend startup. Use ``registry.reload()`` after fixing.
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is not None:  # double-checked
            return _singleton
        reg = ObjectTypeRegistry()
        dirs = _walk_manifest_dirs(DEFAULT_MANIFEST_DIR)
        if not dirs:
            log.info(
                "ontology registry init: %s does not exist or has no manifests. "
                "Use POST /api/v1/ontology/reload after creating files.",
                DEFAULT_MANIFEST_DIR,
            )
        for d in dirs:
            try:
                reg.register_dir(d)
            except ManifestValidationError as exc:
                log.error(
                    "ontology registry init: failed to load %s — %s. "
                    "Continuing with already-loaded manifests.",
                    d, exc,
                )
        _singleton = reg
        return reg
