"""W15 Ontology Runtime Plane — public API.

Implementacja Phase 0 (skeleton). Ekspozycja:

    from sylion.aeis_v2.ontology import (
        ObjectTypeManifest,    # pydantic model
        load_manifest,         # YAML → ObjectTypeManifest
        compile_to_ddl,        # ObjectTypeManifest → SQL DDL
        ObjectTypeRegistry,    # runtime registry
        get_registry,          # singleton accessor
    )

Charter: ``docs/v2/charters/W15_ontology_runtime.md`` (do uzupełnienia
przez subagenta).

PDF references:
- §3.1 Cel: "Generalna warstwa modelu danych — Robert definiuje dowolne
  typy obiektów przez manifesty YAML, system generuje DDL, REST API,
  Python SDK automatycznie."
- §3.2 Scope IN: hybrid columns + JSONB extension, REST + gRPC + OSDK.
- §3.4 G1 (week 4): schema compiler MVP, 1 example type działa.

Phase 0 deliverables w tym module:
- ``manifest.py`` — schema + reader + validator
- ``compiler.py`` — manifest → DDL
- ``registry.py`` — runtime registry
- ``osdk_gen.py`` — auto-gen Python klienta (skeleton)
"""
from __future__ import annotations

from sylion.aeis_v2.ontology.manifest import (
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
    DedicatedColumn,
    JsonbExtension,
    ExtensionFieldDef,
    Relation,
    AuditConfig,
    SearchConfig,
    ActionDef,
    load_manifest,
    load_manifest_dir,
    ManifestValidationError,
    validate_relations,
)
from sylion.aeis_v2.ontology.extension_validator import (
    ExtensionValidationError,
    validate_extension_payload,
)
from sylion.aeis_v2.ontology.compiler import (
    compile_to_ddl,
    compile_alter,
    DDLArtifacts,
    SchemaCompiler,
)
from sylion.aeis_v2.ontology.registry import (
    ObjectTypeRegistry,
    get_registry,
)
from sylion.aeis_v2.ontology.applier import (
    ApplyResult,
    apply_manifest,
    apply_all,
)
from sylion.aeis_v2.ontology.osdk_gen import (
    GeneratedModule,
    generate_module,
    write_osdk_module,
    regenerate_all,
)
from sylion.aeis_v2.ontology.osdk_ts_gen import (
    GeneratedTsModule,
    generate_ts_module,
    write_ts_module,
    write_ts_barrel,
    regenerate_ts_all,
)

__all__ = [
    # manifest
    "ObjectTypeManifest",
    "ObjectTypeMetadata",
    "ObjectTypeSpec",
    "DedicatedColumn",
    "JsonbExtension",
    "ExtensionFieldDef",
    "Relation",
    "AuditConfig",
    "SearchConfig",
    "ActionDef",
    "load_manifest",
    "load_manifest_dir",
    "ManifestValidationError",
    "validate_relations",
    # extension_validator (ADR-001 #1)
    "ExtensionValidationError",
    "validate_extension_payload",
    # compiler
    "compile_to_ddl",
    "compile_alter",
    "DDLArtifacts",
    "SchemaCompiler",
    # registry
    "ObjectTypeRegistry",
    "get_registry",
    # applier (G1)
    "ApplyResult",
    "apply_manifest",
    "apply_all",
    # osdk_gen (G2)
    "GeneratedModule",
    "generate_module",
    "write_osdk_module",
    "regenerate_all",
    # osdk_ts_gen (G2 — frontend mirror)
    "GeneratedTsModule",
    "generate_ts_module",
    "write_ts_module",
    "write_ts_barrel",
    "regenerate_ts_all",
]
