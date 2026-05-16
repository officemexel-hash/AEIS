"""
SYLION AEIS — Autonomous Engineering Intelligence System

Pipeline v8.5.0 · MZ 3.5.5 · Autonomy under Canon

Architecture: LEGO — 65 wymienialnych modułów w 12 klasach.
Contracts: gRPC/Protobuf (Python implementation first).
Decision ladder: D0–D5.

Module classes:
  A: Core Kernel     — nieruchoma kość pacierzowa (8 modułów)
  B: Cognitive        — warstwa rozumowania (7 modułów)
  C: Execution        — warstwa wykonawcza (6 modułów)
  D: Memory           — Księga, pamięć, kompakty (7 modułów)
  E: Governance       — D0–D5, Council, Evidence (7 modułów)
  F: Security         — auth, audit, phantom (8 modułów)
  G: Efficiency       — bloat, perf, memory, cost (4 moduły)
  H: AEIS Self-*      — self-observation → self-preservation (5 modułów)
  I: Skills & Demand  — skill lifecycle + demand signals (3 moduły)
  J: Surface          — Console API + UI + WebSocket (3 moduły)
  K: Rebuildability   — rebuild orchestration + cutover (4 moduły)
  L: Quality          — golden set + regression (3 moduły)
"""

__version__ = "8.5.0"
__księga_version__ = "3.5"
__mz_version__ = "3.5.5"
