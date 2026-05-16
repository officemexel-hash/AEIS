"""W14 E11 — 6 Demo Projects.

Manifest-driven demo projects that exercise the full W14 lifecycle for 6
different domains:

  1. mobile_field_inspector  (mobile-app, D4)
  2. public_project_showcase (web-portal, D3)
  3. factory_automation_panel (industrial-iot, D5)
  4. operator_crm           (crm, D4)
  5. funding_pipeline_tracker (fintech-grants, D4)
  6. skills_marketplace     (marketplace, D5)

E11 deliverables in this commit (skeleton):
  - 6 manifest YAML files in manifests/ — declarative spec per project
  - DemoProjectOrchestrator — load + validate + initialize per manifest
  - Each manifest defines: personas, domain-specific errors, blockers,
    test classes, success criteria

Full lifecycle execution (Idea -> SoT -> Masterplan -> Implementation ->
Verification -> Release -> Memory) lands in next iteration via Kimi parallel.
"""
from __future__ import annotations

from sylion.aeis.testing.demo_projects.orchestrator import (
    DemoProjectManifest, DemoProjectOrchestrator, MANIFEST_DIR, execute_demo,
)

__all__ = [
    "DemoProjectOrchestrator", "DemoProjectManifest",
    "MANIFEST_DIR", "execute_demo",
]
