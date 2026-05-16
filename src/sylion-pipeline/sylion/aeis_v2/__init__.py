"""SYLION AEIS v2 — nowa generacja warstw architektonicznych.

Reprezentuje 4 nowe planes wprowadzone w v2 (PDF Kompletny Obraz, 2026-04-27):

- ``ontology``  (W15) — Ontology Runtime Plane: generic data model przez
  YAML manifesty, hybrid PG storage (dedicated columns + JSONB), OSDK
  auto-generator, action types z D-level mapping, lineage hash-chain.

- ``apps``       (W16) — Operational Apps Builder Plane: aplikacje przez
  manifest, Next.js runtime, component library 20-30 widgetów.

- ``deployment`` (W17) — Deployment Plane (hybrid local+central): multi-
  instance management, blue-green rollout, rollback < 60s, policy-as-code.

- ``terminal``   (W18) — Operator Terminal Plane: live activity stream,
  session threading, command palette, replay sesji jak film.

In-place upgrade — żadnego forka v1. Każda warstwa ma własne moduły obok
istniejących v1 modules; W14 testing ontology zostanie zlifted to W15
side-by-side w fazie G3 charteru W15.

Wersjonowanie:
    AEIS v1.x  — obecny stan (LIVE)
    AEIS v2.0  — W15 G4 done
    AEIS v2.5  — W15+W16 G4
    AEIS v3.0  — W15+W16+W17 G4
    AEIS v3.5  — +W18 (osobna ścieżka)

Status TYLKO: skeleton (Phase 0). Implementacja G1-G4 w kolejnych sesjach.
"""
from __future__ import annotations

__version__ = "2.0.0-alpha.0"
__phase__ = "Phase 0 (skeleton)"
