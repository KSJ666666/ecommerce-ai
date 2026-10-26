from typing import Any
from app.task.actions.builtin.registry import register_builtin_actions
from app.task.actions.custom.registry import register_custom_actions
from app.task.actions.runner import ActionRunner


def build_action_runner(
        llm: Any | None = None,
        include_custom_actions: bool = True,
) -> ActionRunner:
    action_runner = ActionRunner()
    register_builtin_actions(action_runner, llm=llm)
    if include_custom_actions:
        register_custom_actions(action_runner)
    return action_runner
