from __future__ import annotations

from sylion.aeis.advisor.actions._models import CardAction
from sylion.aeis.advisor.actions.handlers.accept_handler import AcceptHandler
from sylion.aeis.advisor.actions.routing_table import get_handler


def test_get_handler_returns_expected_class():
    handler = get_handler(CardAction.ACCEPT)
    assert isinstance(handler, AcceptHandler)
