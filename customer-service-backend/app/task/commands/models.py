from dataclasses import dataclass
from typing import Any, ClassVar, Dict


@dataclass(slots=True)
class Command:
    """Structured engine decision for one turn."""

    command: ClassVar[str] = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Command":
        """Default: no-arg commands just return cls(). Override when fields are needed."""
        return cls()



# ── Intent commands ───────────────────────────────────────────────────────────

@dataclass(slots=True)
class StartFlowCommand(Command):
    """Start a business flow."""

    command: ClassVar[str] = "start_flow"
    flow: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartFlowCommand":
        flow = str(data.get("flow", "")).strip()
        if not flow:
            raise ValueError("start_flow requires a non-empty 'flow'.")
        return cls(flow=flow)


@dataclass(slots=True)
class SetSlotsCommand(Command):
    """Write one or more business slot values."""

    command: ClassVar[str] = "set_slots"
    slots: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetSlotsCommand":
        raw = data.get("slots")
        if not isinstance(raw, dict):
            raise ValueError("set_slots requires a 'slots' JSON object.")
        normalized = {str(k).strip(): v for k, v in raw.items() if str(k).strip()}
        if not normalized:
            raise ValueError("set_slots requires at least one slot.")
        return cls(slots=normalized)


@dataclass(slots=True)
class CancelFlowCommand(Command):
    """Cancel the current active flow."""

    command: ClassVar[str] = "cancel_flow"


@dataclass(slots=True)
class ResumeTaskCommand(Command):
    """Resume a previously interrupted task."""

    command: ClassVar[str] = "resume_task"
    flow: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumeTaskCommand":
        flow = data.get("flow")
        if flow is None:
            return cls()
        normalized = str(flow).strip()
        if not normalized:
            raise ValueError("resume_task 'flow' must be non-empty when provided.")
        return cls(flow=normalized)


# ── 注册表 & 解析函数 ─────────────────────────────────────────────────────────

_COMMAND_REGISTRY: Dict[str, type[Command]] = {
    StartFlowCommand.command: StartFlowCommand,
    SetSlotsCommand.command: SetSlotsCommand,
    CancelFlowCommand.command: CancelFlowCommand,
    ResumeTaskCommand.command: ResumeTaskCommand,
}


def parse_command(data: Dict[str, Any]) -> Command:
    """Parse a single command payload into a Command instance."""
    if not isinstance(data, dict):
        raise ValueError("Each command must be a JSON object.")
    command_name = str(data.get("command") or "").strip()
    cls = _COMMAND_REGISTRY.get(command_name)
    if cls is None:
        raise ValueError(f"Unsupported command type: {command_name!r}")
    return cls.from_dict(data)
