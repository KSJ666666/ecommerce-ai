from dataclasses import dataclass, field
from typing import Any

from app.task.commands.models import Command


@dataclass(slots=True)
class TaskTurnPlan:
    commands: list[Command] = field(default_factory=list)


@dataclass(slots=True)
class KnowledgeTurnPlan:
    intent: str = ""


@dataclass(slots=True)
class ChitchatTurnPlan:
    pass


@dataclass(slots=True)
class TurnPlan:
    task: TaskTurnPlan | None = None
    knowledge: KnowledgeTurnPlan | None = None
    chitchat: ChitchatTurnPlan | None = None

    def active_tracks(self) -> list[str]:
        tracks: list[str] = []
        if self.task is not None:
            tracks.append("task")
        if self.knowledge is not None:
            tracks.append("knowledge")
        if self.chitchat is not None:
            tracks.append("chitchat")
        return tracks


@dataclass(slots=True)
class TurnPlanValidationResult:
    valid: bool
    selected_track: str | None = None
    reason: str | None = None
    clarify_target: str | None = None
    clarify_message: str | None = None


def build_clarify_message(
    *,
    reason: str | None,
    clarify_target: str | None,
    state: Any,
) -> str:
    if reason == "multiple_tracks":
        return "你这次同时提到了多个方向。我们先处理一个，你想先办业务还是先咨询信息呢？"

    focused_object = getattr(state, "focused_object", None)
    if clarify_target == "focused_object":
        if focused_object is not None and focused_object.type == "order":
            return "请先发送你想咨询的订单，我再继续帮你看。"
        return "请先发送你想咨询的商品或订单，我再继续帮你看。"

    if clarify_target == "knowledge_intent":
        return "你是想了解商品信息、订单信息，还是售后配送规则呢？"

    if clarify_target == "primary_track":
        return "你是想先处理业务问题，还是先咨询信息呢？"

    if reason == "missing_task_commands":
        return "你这次是想办理什么业务呢？比如查订单、查物流，或者申请退款。"

    if reason == "missing_knowledge_intent":
        return "你想了解哪一类信息呢？比如商品信息、订单信息，或者售后规则。"

    return "我还需要再确认一下你的意思，你可以换个更具体的说法告诉我。"
