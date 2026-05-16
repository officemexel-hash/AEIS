"""Action routing table."""
from __future__ import annotations

from sylion.aeis.advisor.actions._models import CardAction
from sylion.aeis.advisor.actions.handlers.accept_handler import AcceptHandler
from sylion.aeis.advisor.actions.handlers.base import ActionHandler
from sylion.aeis.advisor.actions.handlers.dont_learn_handler import DontLearnHandler
from sylion.aeis.advisor.actions.handlers.human_gate_handler import HumanGateHandler
from sylion.aeis.advisor.actions.handlers.masterplan_handler import MasterplanHandler
from sylion.aeis.advisor.actions.handlers.modify_handler import ModifyHandler
from sylion.aeis.advisor.actions.handlers.not_useful_handler import NotUsefulHandler
from sylion.aeis.advisor.actions.handlers.preference_handler import PreferenceHandler
from sylion.aeis.advisor.actions.handlers.reject_handler import RejectHandler
from sylion.aeis.advisor.actions.handlers.remind_later_handler import RemindLaterHandler

_ROUTING: dict[CardAction, type[ActionHandler]] = {
    CardAction.ACCEPT: AcceptHandler,
    CardAction.REJECT: RejectHandler,
    CardAction.MODIFY: ModifyHandler,
    CardAction.REMIND_LATER: RemindLaterHandler,
    CardAction.NOT_USEFUL: NotUsefulHandler,
    CardAction.CONVERT_TO_HUMAN_GATE: HumanGateHandler,
    CardAction.CONVERT_TO_MASTERPLAN_CHANGE: MasterplanHandler,
    CardAction.SAVE_AS_PREFERENCE: PreferenceHandler,
    CardAction.DONT_LEARN_FROM_THIS: DontLearnHandler,
}


def get_handler(action: CardAction) -> ActionHandler:
    handler_cls = _ROUTING.get(action)
    if handler_cls is None:
        raise ValueError(f"unsupported action: {action}")
    return handler_cls()
