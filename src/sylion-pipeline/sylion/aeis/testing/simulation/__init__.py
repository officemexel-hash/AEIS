"""W14 Simulation Engine — 5 layers L0-L4.

L0: SimulationContract — isolation, model_mode, persistence, safety
L1: Program execution sandbox (in-memory, mock EventBus, mock LLM)
L2: Human Work simulation (workflow execution by persona)
L3: Human Decision simulation (gate choices, approvals)
L4: Human Error injection (14 error classes)

Auto-discard branch state after run; persist trace + findings + evidence.
"""
from __future__ import annotations

from sylion.aeis.testing.simulation.contract import (
    DEFAULT_ISOLATION, DEFAULT_MODEL_MODE, DEFAULT_PERSISTENCE, DEFAULT_SAFETY,
    build_contract,
)
from sylion.aeis.testing.simulation.engine import SimulationEngine
from sylion.aeis.testing.simulation.mock_bus import MockEventBus
from sylion.aeis.testing.simulation.mock_llm import MockLLM
from sylion.aeis.testing.simulation.sandbox import TransactionalSandbox

__all__ = [
    "build_contract",
    "DEFAULT_ISOLATION", "DEFAULT_MODEL_MODE",
    "DEFAULT_PERSISTENCE", "DEFAULT_SAFETY",
    "SimulationEngine",
    "TransactionalSandbox",
    "MockEventBus",
    "MockLLM",
]
