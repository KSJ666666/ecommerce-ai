from typing import Any

from app.task.actions.base import Action, ActionResult
from app.domain.state import DialogueState


class ActionListen(Action):
    """The assistant waits for the next user message."""

    name = "action_listen"

    async def run(self, state: DialogueState, **kwargs: Any) -> ActionResult:
        return ActionResult()
