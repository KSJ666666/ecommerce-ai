from typing import Optional

from app.task.actions.base import ActionRegistry, ActionResult
from app.domain.state import DialogueState


class ActionRunner:
    """Execute actions requested by the flow executor."""

    def __init__(
        self,
        registry: Optional[ActionRegistry] = None,
    ) -> None:
        self.registry = registry or ActionRegistry()

    async def run(
        self,
        action_name: str,
        state: DialogueState,
        **action_kwargs: object,
    ) -> ActionResult:
        if self.registry.has(action_name):
            action = self.registry.get(action_name)
            return await action.run(state, **action_kwargs)
        raise ValueError(
            f"Action '{action_name}' is not registered."
        )
