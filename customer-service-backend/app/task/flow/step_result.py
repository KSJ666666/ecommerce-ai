from dataclasses import dataclass, field
from typing import Any


class FlowStepResult:
    """Base class for flow step execution results."""


class FlowContinue(FlowStepResult):
    """Continue advancing to the next step."""

    def __init__(self, has_flow_ended: bool = False) -> None:
        self.has_flow_ended = has_flow_ended


@dataclass(slots=True)
class FlowPause(FlowStepResult):
    """Pause flow advancement and return the next action to run."""

    action_name: str
    action_kwargs: dict[str, Any] = field(default_factory=dict)
