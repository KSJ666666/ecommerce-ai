from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.domain.messages import BotMessage
from app.domain.state import DialogueState


@dataclass(slots=True)
class ActionResult:
    """Result of executing one action without using events."""

    messages: List[BotMessage] = field(default_factory=list)
    slot_updates: Dict[str, Any] = field(default_factory=dict)


class Action(ABC):
    """Runtime action base class."""

    name: str

    @abstractmethod
    async def run(self, state: DialogueState, **kwargs: Any) -> ActionResult:
        """Execute an action against direct state."""


class ActionRegistry:
    """Resolver for runtime actions."""

    def __init__(self) -> None:
        self._actions: Dict[str, Action] = {}

    def register(self, action: Action) -> None:
        self._actions[action.name] = action

    def has(self, name: str) -> bool:
        return name in self._actions

    def get(self, name: str) -> Action:
        if name not in self._actions:
            raise KeyError(f"Unknown action '{name}'.")
        return self._actions[name]
