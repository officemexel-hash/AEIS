"""Action handler base class."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult


class ActionHandler(ABC):
    @abstractmethod
    def handle(self, ctx: ActionContext) -> HandlerResult:
        """Route one operator action."""
