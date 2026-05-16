"""
openhands.tools.delegate shim — DelegationVisualizer.

In full OpenHands this provides terminal UI for delegation chains.
In SYLION shim it's a no-op — we log delegation info through Rich console.
"""


class DelegationVisualizer:
    """No-op delegation visualizer."""
    def __init__(self, name: str = ""):
        self.name = name

    def __repr__(self) -> str:
        return f"DelegationVisualizer(name={self.name!r})"
