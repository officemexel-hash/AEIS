"""
SYLION gRPC -- Core Service Servers

Implements gRPC service servers for core modules:
- ModuleRegistryService
- EvidenceSpineService

Wraps existing SQLite-backed services to serve proto-defined RPCs.
"""

from __future__ import annotations

import logging

import grpc
from concurrent import futures

from sylion.core.module_registry import (
    get_registry, ModuleManifest, ModuleKind, ModuleLifecycleStage,
)
from sylion.core.evidence_spine import get_evidence_spine, EvidenceEntry

log = logging.getLogger("sylion.grpc.core_server")

# ---------------------------------------------------------------------------
# Lazy proto imports (stubs may not be available)
# ---------------------------------------------------------------------------

try:
    from sylion.grpc_stubs import sylion_core_pb2
    from sylion.grpc_stubs import sylion_core_pb2_grpc
    from sylion.grpc_stubs import sylion_common_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, service servers disabled")


if _HAS_STUBS:

    # -----------------------------------------------------------------------
    # Module Registry Service
    # -----------------------------------------------------------------------

    class ModuleRegistryServicer(sylion_core_pb2_grpc.ModuleRegistryServiceServicer):
        """gRPC server for Module Registry."""

        def __init__(self):
            self._registry = get_registry()

        def RegisterModule(self, request, context):
            """Register a new module."""
            try:
                module_id = request.module_id.module_id
                kind_str = request.module_id.module_kind or "core"
                desc = request.description

                kind_map = {k.value: k for k in ModuleKind}
                kind = kind_map.get(kind_str, list(ModuleKind)[0])

                manifest = ModuleManifest(
                    module_id=module_id,
                    module_kind=kind,
                    owner_plan=request.module_id.owner_plan or "P00",
                    description=desc,
                )
                self._registry.register(manifest)
                return sylion_core_pb2.RegisterModuleResponse(
                    module=sylion_core_pb2.Module(
                        module_id=sylion_common_pb2.ModuleId(
                            module_id=module_id,
                            module_kind=kind_str,
                        ),
                        description=desc,
                    )
                )
            except Exception as exc:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(exc))
                return sylion_core_pb2.RegisterModuleResponse()

        def GetModule(self, request, context):
            """Get a module by ID."""
            result = self._registry.get(request.module_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Module {request.module_id} not found")
                return sylion_core_pb2.GetModuleResponse()
            return sylion_core_pb2.GetModuleResponse(
                module=sylion_core_pb2.Module(
                    module_id=sylion_common_pb2.ModuleId(
                        module_id=result.get("module_id", ""),
                        module_kind=result.get("module_kind", ""),
                    ),
                    description=result.get("description", ""),
                )
            )

        def ListModules(self, request, context):
            """List all modules."""
            kind_filter = request.kind_filter if request.kind_filter else None
            results = self._registry.list_modules(kind=kind_filter)
            modules = []
            for r in results:
                mid = r.get("module_id", "")
                mk = r.get("module_kind", "")
                desc = r.get("description", "")
                # list_modules may return manifest dicts or summary dicts
                if not mid:
                    mid = r.get("manifest", {}).get("module_id", "")
                    mk = r.get("manifest", {}).get("module_kind", "")
                    desc = r.get("manifest", {}).get("description", "")
                modules.append(sylion_core_pb2.Module(
                    module_id=sylion_common_pb2.ModuleId(
                        module_id=mid,
                        module_kind=mk,
                    ),
                    description=desc,
                ))
            return sylion_core_pb2.ListModulesResponse(modules=modules)

        def TransitionModule(self, request, context):
            """Transition a module lifecycle stage."""
            try:
                stage_name = sylion_core_pb2.ModuleStage.Name(request.target)
                stage_name = stage_name.replace("MODULE_", "").lower()
                stage_map = {s.value: s for s in ModuleLifecycleStage}
                target = stage_map.get(stage_name, ModuleLifecycleStage.DRAFT)
                self._registry.transition(request.module_id, target)
            except Exception as exc:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(str(exc))
            return sylion_core_pb2.TransitionModuleResponse()

    # -----------------------------------------------------------------------
    # Evidence Spine Service
    # -----------------------------------------------------------------------

    class EvidenceSpineServicer(sylion_core_pb2_grpc.EvidenceSpineServiceServicer):
        """gRPC server for Evidence Spine."""

        def __init__(self):
            self._spine = get_evidence_spine()

        def AppendEntry(self, request, context):
            """Append an evidence entry."""
            payload = request.payload if request.payload else b""
            entry = EvidenceEntry(
                source_plan=request.source_module or "grpc",
                event_type=request.topic or "grpc.append",
                actor_id="grpc-server",
            )
            result = self._spine.append(entry)
            return sylion_core_pb2.AppendEntryResponse(
                entry=sylion_common_pb2.EvidenceEntry(
                    evidence_id=result.get("entry_id", ""),
                    topic=request.topic,
                    source_module=request.source_module,
                )
            )

        def VerifyChain(self, request, context):
            """Verify the evidence chain."""
            valid, msg = self._spine.verify_chain()
            return sylion_core_pb2.VerifyChainResponse(valid=valid)

        def GetEntry(self, request, context):
            """Get a single evidence entry."""
            entries = self._spine.query(limit=1000)
            found = None
            for e in entries:
                if e.get("entry_id") == request.evidence_id:
                    found = e
                    break
            if not found:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Entry {request.evidence_id} not found")
                return sylion_core_pb2.GetEntryResponse()
            return sylion_core_pb2.GetEntryResponse(
                entry=sylion_common_pb2.EvidenceEntry(
                    evidence_id=found.get("entry_id", ""),
                    topic=found.get("event_type", ""),
                    source_module=found.get("source_plan", ""),
                )
            )

        def Replay(self, request, context):
            """Replay evidence entries (server streaming)."""
            entries = self._spine.replay()
            for entry in entries:
                yield sylion_common_pb2.EvidenceEntry(
                    evidence_id=entry.get("entry_id", ""),
                    topic=entry.get("event_type", ""),
                    source_module=entry.get("source_plan", ""),
                )

    # -----------------------------------------------------------------------
    # Server Factory
    # -----------------------------------------------------------------------

    def create_grpc_server(port: int = 50051, max_workers: int = 10) -> grpc.Server:
        """Create and configure a gRPC server with ALL services."""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

        # Core services
        sylion_core_pb2_grpc.add_ModuleRegistryServiceServicer_to_server(
            ModuleRegistryServicer(), server,
        )
        sylion_core_pb2_grpc.add_EvidenceSpineServiceServicer_to_server(
            EvidenceSpineServicer(), server,
        )

        # EventBus service
        from sylion.grpc.eventbus_server import EventBusServicer
        sylion_core_pb2_grpc.add_EventBusServiceServicer_to_server(
            EventBusServicer(), server,
        )

        # Execution services
        from sylion.grpc.execution_server import WorkflowServicer, JobServicer
        from sylion.grpc_stubs import sylion_execution_pb2_grpc
        sylion_execution_pb2_grpc.add_WorkflowServiceServicer_to_server(
            WorkflowServicer(), server,
        )
        sylion_execution_pb2_grpc.add_JobServiceServicer_to_server(
            JobServicer(), server,
        )

        # Cognitive services
        from sylion.grpc.cognitive_server import ModelRouterServicer, PlanServicer
        from sylion.grpc_stubs import sylion_cognitive_pb2_grpc
        sylion_cognitive_pb2_grpc.add_ModelRouterServiceServicer_to_server(
            ModelRouterServicer(), server,
        )
        sylion_cognitive_pb2_grpc.add_PlanServiceServicer_to_server(
            PlanServicer(), server,
        )

        # Governance services
        from sylion.grpc.governance_server import GovernanceServicer, CouncilServicer
        from sylion.grpc_stubs import sylion_governance_pb2_grpc
        sylion_governance_pb2_grpc.add_GovernanceServiceServicer_to_server(
            GovernanceServicer(), server,
        )
        sylion_governance_pb2_grpc.add_CouncilServiceServicer_to_server(
            CouncilServicer(), server,
        )

        # AEIS services
        from sylion.grpc.aeis_server import (
            AutonomyServicer, ExplanationServicer, ImprovementServicer,
        )
        from sylion.grpc_stubs import sylion_aeis_pb2_grpc
        sylion_aeis_pb2_grpc.add_AutonomyServiceServicer_to_server(
            AutonomyServicer(), server,
        )
        sylion_aeis_pb2_grpc.add_ExplanationServiceServicer_to_server(
            ExplanationServicer(), server,
        )
        sylion_aeis_pb2_grpc.add_ImprovementServiceServicer_to_server(
            ImprovementServicer(), server,
        )

        # Advisor services (Kimi modules)
        try:
            from sylion.aeis.advisor.role_resolver.grpc_server import RoleResolverServicer
            from sylion.aeis.advisor.variants.grpc_server import VariantsServicer
            from sylion.aeis.advisor.subscription.grpc_server import SubscriptionServicer
            from sylion.aeis.advisor.scaling.grpc_server import ScalingServicer
            # Stubs may not exist yet; register only if proto compiled
            # For now, servicers are available for manual wiring
        except ImportError:
            pass

        # Advisor services (Codex modules)
        try:
            from sylion.aeis.advisor.actions.grpc_server import register_actions_service
            from sylion.aeis.advisor.preferences.grpc_server import register_preferences_service
            from sylion.aeis.advisor.pricing.grpc_server import register_pricing_service

            register_actions_service(server)
            register_preferences_service(server)
            register_pricing_service(server)
        except ImportError:
            pass

        server.add_insecure_port(f"[::]:{port}")
        return server
