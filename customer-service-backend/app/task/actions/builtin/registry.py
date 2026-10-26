from typing import Any

from app.task.actions.builtin.action_listen import ActionListen
from app.task.actions.builtin.action_response import ActionResponse
from app.task.actions.runner import ActionRunner


def register_builtin_actions(
    action_runner: ActionRunner,
    llm: Any | None = None,
) -> ActionRunner:
    for action in (
        ActionListen(),
        ActionResponse(llm=llm),
    ):
        action_runner.registry.register(action)
    return action_runner
