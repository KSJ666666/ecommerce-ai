from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class TaskContext:
    """业务任务执行快照（对应用户发起的对话流程）。"""

    flow_id: str
    step_id: str | None = None
    slots: Dict[str, Any] = field(default_factory=dict)

    def context_dict(self) -> Dict[str, Any]:
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {"flow_id": self.flow_id, "step_id": self.step_id, "slots": dict(self.slots)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(
            flow_id=data["flow_id"],
            step_id=data.get("step_id"),
            slots=dict(data.get("slots", {})),
        )


@dataclass(slots=True)
class SystemContext:
    """系统流程执行快照（对应系统发起的交互，如收集信息、确认、纠错等）。"""

    flow_id: str
    step_id: str | None = None

    def context_dict(self) -> Dict[str, Any]:
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "base", "flow_id": self.flow_id, "step_id": self.step_id}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemContext":
        if cls is SystemContext:
            subcls = _SYSTEM_CONTEXT_TYPES.get(data.get("type", ""), SystemContext)
            if subcls is not SystemContext:
                return subcls.from_dict(data)
        return cls(flow_id=data.get("flow_id", ""), step_id=data.get("step_id"))


@dataclass(slots=True)
class CollectSystemContext(SystemContext):
    """系统流程：收集槽位信息（system_collect_information）。"""

    flow_id: str = "system_collect_information"
    slot_name: str = ""
    response: Dict[str, Any] = field(default_factory=dict)

    def context_dict(self) -> Dict[str, Any]:
        return {"slot_name": self.slot_name, "response": dict(self.response)}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "collect",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "slot_name": self.slot_name,
            "response": dict(self.response),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollectSystemContext":
        return cls(
            step_id=data.get("step_id"),
            slot_name=data.get("slot_name", ""),
            response=dict(data.get("response", {})),
        )


@dataclass(slots=True)
class StartedSystemContext(SystemContext):
    """系统流程：告知用户新任务已开始（system_task_started）。"""

    flow_id: str = "system_task_started"
    started_flow_id: str = ""
    started_flow_name: str = ""

    def context_dict(self) -> Dict[str, Any]:
        return {
            "started_flow_id": self.started_flow_id,
            "started_flow_name": self.started_flow_name,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "started",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "started_flow_id": self.started_flow_id,
            "started_flow_name": self.started_flow_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartedSystemContext":
        return cls(
            step_id=data.get("step_id"),
            started_flow_id=data.get("started_flow_id", ""),
            started_flow_name=data.get("started_flow_name", ""),
        )


@dataclass(slots=True)
class ResumedSystemContext(SystemContext):
    """系统流程：告知用户恢复之前的任务（system_task_resumed）。"""

    flow_id: str = "system_task_resumed"
    resumed_flow_id: str = ""
    resumed_flow_name: str = ""

    def context_dict(self) -> Dict[str, Any]:
        return {
            "resumed_flow_id": self.resumed_flow_id,
            "resumed_flow_name": self.resumed_flow_name,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "resumed",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "resumed_flow_id": self.resumed_flow_id,
            "resumed_flow_name": self.resumed_flow_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumedSystemContext":
        return cls(
            step_id=data.get("step_id"),
            resumed_flow_id=data.get("resumed_flow_id", ""),
            resumed_flow_name=data.get("resumed_flow_name", ""),
        )


@dataclass(slots=True)
class CanceledSystemContext(SystemContext):
    """系统流程：告知用户任务已取消（system_task_canceled）。"""

    flow_id: str = "system_task_canceled"
    canceled_flow_id: str = ""
    canceled_flow_name: str = ""

    def context_dict(self) -> Dict[str, Any]:
        return {
            "canceled_flow_id": self.canceled_flow_id,
            "canceled_flow_name": self.canceled_flow_name,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "canceled",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "canceled_flow_id": self.canceled_flow_id,
            "canceled_flow_name": self.canceled_flow_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanceledSystemContext":
        return cls(
            step_id=data.get("step_id"),
            canceled_flow_id=data.get("canceled_flow_id", ""),
            canceled_flow_name=data.get("canceled_flow_name", ""),
        )


@dataclass(slots=True)
class InterruptedSystemContext(SystemContext):
    """系统流程：告知用户当前任务被打断（system_task_interrupted）。"""

    flow_id: str = "system_task_interrupted"
    interrupted_flow_id: str = ""
    interrupted_flow_name: str = ""
    started_flow_id: str = ""
    started_flow_name: str = ""

    def context_dict(self) -> Dict[str, Any]:
        return {
            "interrupted_flow_id": self.interrupted_flow_id,
            "interrupted_flow_name": self.interrupted_flow_name,
            "started_flow_id": self.started_flow_id,
            "started_flow_name": self.started_flow_name,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "interrupted",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "interrupted_flow_id": self.interrupted_flow_id,
            "interrupted_flow_name": self.interrupted_flow_name,
            "started_flow_id": self.started_flow_id,
            "started_flow_name": self.started_flow_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterruptedSystemContext":
        return cls(
            step_id=data.get("step_id"),
            interrupted_flow_id=data.get("interrupted_flow_id", ""),
            interrupted_flow_name=data.get("interrupted_flow_name", ""),
            started_flow_id=data.get("started_flow_id", ""),
            started_flow_name=data.get("started_flow_name", ""),
        )


@dataclass(slots=True)
class CannotHandleSystemContext(SystemContext):
    """系统流程：无法处理当前请求（system_cannot_handle）。"""

    flow_id: str = "system_cannot_handle"
    reason: str | None = None

    def context_dict(self) -> Dict[str, Any]:
        return {"reason": self.reason}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "cannot_handle",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CannotHandleSystemContext":
        return cls(step_id=data.get("step_id"), reason=data.get("reason"))


@dataclass(slots=True)
class CompletedSystemContext(SystemContext):
    """系统流程：任务完成收尾（system_completed）。"""

    flow_id: str = "system_completed"
    previous_flow_name: str = ""

    def context_dict(self) -> Dict[str, Any]:
        return {"previous_flow_name": self.previous_flow_name}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "completed",
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "previous_flow_name": self.previous_flow_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompletedSystemContext":
        return cls(step_id=data.get("step_id"), previous_flow_name=data.get("previous_flow_name", ""))


_SYSTEM_CONTEXT_TYPES: Dict[str, type] = {
    "collect": CollectSystemContext,
    "started": StartedSystemContext,
    "resumed": ResumedSystemContext,
    "canceled": CanceledSystemContext,
    "interrupted": InterruptedSystemContext,
    "cannot_handle": CannotHandleSystemContext,
    "completed": CompletedSystemContext,
}
