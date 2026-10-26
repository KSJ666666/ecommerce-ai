from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

from app.task.flow.links import (
    FlowStepLink,
    link_from_json,
)


class FlowStepType(str, Enum):
    START = "start"
    ACTION = "action"
    COLLECT = "collect"
    SET_SLOTS = "set_slots"
    END = "end"


@dataclass(slots=True)
class ResponseDefinition:
    mode: str = "static"
    text: str | None = None
    prompt: str | None = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ResponseDefinition":
        return cls(
            mode=str(data.get("mode", "static")),
            text=None if data.get("text") is None else str(data["text"]),
            prompt=None if data.get("prompt") is None else str(data["prompt"]),
        )


@dataclass(slots=True)
class SlotValidation:
    condition: str | None = None
    failure_response: ResponseDefinition | None = None


@dataclass(slots=True)
class FlowStep:
    id: str
    type: FlowStepType
    next: List[FlowStepLink] = field(default_factory=list)
    description: str = ""


@dataclass(slots=True)
class StartFlowStep(FlowStep):
    type: FlowStepType = FlowStepType.START

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "StartFlowStep":
        return cls(**load_base_step_fields(data))


@dataclass(slots=True)
class ActionFlowStep(FlowStep):
    type: FlowStepType = FlowStepType.ACTION
    action: str = ""
    args: Dict[str, Any] | str = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ActionFlowStep":
        raw_args = data.get("args")
        if isinstance(raw_args, str):
            args: Dict[str, Any] | str = raw_args
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        return cls(action=str(data["action"]), args=args, **load_base_step_fields(data))


@dataclass(slots=True)
class CollectSlotStep(FlowStep):
    type: FlowStepType = FlowStepType.COLLECT
    slot_name: str = ""
    response: ResponseDefinition = field(default_factory=ResponseDefinition)
    validation: Optional[SlotValidation] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "CollectSlotStep":
        raw_rule = data.get("validation")
        validation = (
            SlotValidation(
                condition=(
                    None if raw_rule.get("condition") is None
                    else str(raw_rule["condition"])
                ),
                failure_response=(
                    ResponseDefinition.from_json(raw_rule["failure_response"])
                    if isinstance(raw_rule.get("failure_response"), dict)
                    else None
                ),
            )
            if raw_rule is not None else None
        )
        raw_response = data.get("response")
        if isinstance(raw_response, dict):
            response = ResponseDefinition.from_json(raw_response)
        else:
            response = ResponseDefinition(text=str(data.get("prompt", "")))
        return cls(
            slot_name=str(data["slot_name"]),
            response=response,
            validation=validation,
            **load_base_step_fields(data),
        )


@dataclass(slots=True)
class SetSlotsFlowStep(FlowStep):
    type: FlowStepType = FlowStepType.SET_SLOTS
    slots: List[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "SetSlotsFlowStep":
        normalized_slots = [
            {"key": str(slot_item["name"]), "value": slot_item["value"]}
            for slot_item in data.get("set_slots", [])
        ]
        return cls(slots=normalized_slots, **load_base_step_fields(data))


@dataclass(slots=True)
class EndFlowStep(FlowStep):
    type: FlowStepType = FlowStepType.END

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EndFlowStep":
        return cls(**load_base_step_fields(data))


def step_from_json(data: Dict[str, Any]) -> FlowStep:
    step_type = FlowStepType(data["type"])
    parser = STEP_TYPE_TO_CLASS[step_type]
    return parser(data)


def load_base_step_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    step_type = FlowStepType(data["type"])
    return {
        "id": str(data["id"]),
        "type": step_type,
        "next": load_next_links(raw_next=data.get("next")),
        "description": str(data.get("description", "")),
    }


STEP_TYPE_TO_CLASS: Dict[
    FlowStepType, Callable[[Dict[str, Any]], FlowStep]
] = {
    FlowStepType.START: StartFlowStep.from_json,
    FlowStepType.ACTION: ActionFlowStep.from_json,
    FlowStepType.COLLECT: CollectSlotStep.from_json,
    FlowStepType.SET_SLOTS: SetSlotsFlowStep.from_json,
    FlowStepType.END: EndFlowStep.from_json,
}


def load_next_links(
    *,
    raw_next: Any,
) -> List[FlowStepLink]:
    if isinstance(raw_next, str):
        return [link_from_json(raw_next)]

    links: List[FlowStepLink] = []
    for item in raw_next or []:
        links.append(link_from_json(item))
    return links
