import copy
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from app.domain.messages import BotMessage, Message, MessageType, MessageObject
from app.domain.contexts import TaskContext, SystemContext


@dataclass(slots=True)
class Turn:
    """一次对话轮次。"""

    turn_id: str
    input_message: Message
    assistant_messages: List[BotMessage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "input_message": self.input_message.to_dict(),
            "assistant_messages": [m.to_dict() for m in self.assistant_messages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        return cls(
            turn_id=data["turn_id"],
            input_message=Message.from_dict(data["input_message"]),
            assistant_messages=[BotMessage.from_dict(m) for m in data.get("assistant_messages", [])],
        )


@dataclass(slots=True)
class Session:
    """一个会话，将多个轮次按活跃窗口分组。"""

    session_id: str
    started_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    closed_at: float | None = None
    turns: List[Turn] = field(default_factory=list)

    def is_closed(self) -> bool:
        return self.closed_at is not None

    def append_turn(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.last_activity_at = time.time()

    def close(self) -> None:
        if self.closed_at is None:
            self.closed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "last_activity_at": self.last_activity_at,
            "closed_at": self.closed_at,
            "turns": [t.to_dict() for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            started_at=data.get("started_at", time.time()),
            last_activity_at=data.get("last_activity_at", time.time()),
            closed_at=data.get("closed_at"),
            turns=[Turn.from_dict(t) for t in data.get("turns", [])],
        )


@dataclass(slots=True)
class FocusedObject:
    """当前对话聚焦的业务对象（如订单、商品）。"""

    type: str
    id: str
    title: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_message_object(cls, message_object: MessageObject) -> "FocusedObject":
        return cls(
            type=message_object.type,
            id=message_object.id,
            title=message_object.title,
            attributes=dict(message_object.attributes),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "id": self.id, "title": self.title, "attributes": dict(self.attributes)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FocusedObject":
        return cls(
            type=data["type"],
            id=data["id"],
            title=data.get("title", ""),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass(slots=True)
class DialogueState:
    """完整的对话状态，记录业务任务、系统流程、聚焦对象和会话历史。"""

    sender_id: str
    # ── 任务轨道 ──────────────────────────────────────────────
    active_task: TaskContext | None = None
    paused_tasks: List[TaskContext] = field(default_factory=list)
    # ── 系统流程（同一时刻最多一个） ────────────────────────────
    active_system_flow: SystemContext | None = None
    # ── 聚焦业务对象 ──────────────────────────────────────────
    focused_object: FocusedObject | None = None
    # ── 会话历史 ──────────────────────────────────────────────
    sessions: List[Session] = field(default_factory=list)
    current_session_id: str | None = None
    pending_turn: Turn | None = None
    latest_action_name: str | None = None

    # ── 当前执行上下文 ─────────────────────────────────────────

    @property
    def current_context(self) -> TaskContext | SystemContext | None:
        """当前正在执行的上下文：系统流程优先，否则为业务任务。"""
        return self.active_system_flow or self.active_task

    def clone(self) -> "DialogueState":
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 存储的字典（不含 pending_turn，它是处理中的瞬态）。"""
        return {
            "sender_id": self.sender_id,
            "active_task": self.active_task.to_dict() if self.active_task is not None else None,
            "paused_tasks": [t.to_dict() for t in self.paused_tasks],
            "active_system_flow": self.active_system_flow.to_dict() if self.active_system_flow is not None else None,
            "focused_object": self.focused_object.to_dict() if self.focused_object is not None else None,
            "sessions": [s.to_dict() for s in self.sessions],
            "current_session_id": self.current_session_id,
            "latest_action_name": self.latest_action_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueState":
        """从字典还原 DialogueState。"""
        state = cls(sender_id=data["sender_id"])
        raw_task = data.get("active_task")
        state.active_task = TaskContext.from_dict(raw_task) if raw_task is not None else None
        state.paused_tasks = [TaskContext.from_dict(t) for t in data.get("paused_tasks", [])]
        raw_sys = data.get("active_system_flow")
        state.active_system_flow = SystemContext.from_dict(raw_sys) if raw_sys is not None else None
        raw_fo = data.get("focused_object")
        state.focused_object = FocusedObject.from_dict(raw_fo) if raw_fo is not None else None
        state.sessions = [Session.from_dict(s) for s in data.get("sessions", [])]
        state.current_session_id = data.get("current_session_id")
        state.latest_action_name = data.get("latest_action_name")
        return state

    # ── 任务管理 ──────────────────────────────────────────────

    def start_new_task(self, flow_id: str, step_id: str) -> TaskContext:
        """创建并激活一个新的业务任务，返回新建的 TaskContext。"""
        task = TaskContext(flow_id=flow_id, step_id=step_id)
        self.active_task = task
        return task

    def pause_active_task(self) -> Optional[TaskContext]:
        """将当前活跃任务移入暂停列表，同时清除系统流程，返回被暂停的任务。"""
        task = self.active_task
        if task is None:
            return None
        self.active_system_flow = None
        self.active_task = None
        self.paused_tasks.append(task)
        return task

    def resume_task(self, flow_id: str | None = None) -> Optional[TaskContext]:
        """从暂停列表中恢复任务（按 flow_id 匹配，或恢复最新一个），返回恢复的任务。"""
        if not self.paused_tasks:
            return None
        if flow_id is not None:
            for i in range(len(self.paused_tasks) - 1, -1, -1):
                if self.paused_tasks[i].flow_id == flow_id:
                    task = self.paused_tasks.pop(i)
                    self.active_task = task
                    return task
            return None
        # 恢复最新暂停的任务
        task = self.paused_tasks.pop()
        self.active_task = task
        return task

    def cancel_active_task(self) -> Optional[TaskContext]:
        """取消当前活跃任务（含系统流程），返回被取消的任务。"""
        self.active_system_flow = None
        task = self.active_task
        self.active_task = None
        return task

    # ── 系统流程管理 ───────────────────────────────────────────

    def activate_system_flow(self, ctx: SystemContext) -> None:
        """激活一个系统流程（替换当前系统流程）。"""
        self.active_system_flow = ctx

    def end_system_flow(self) -> Optional[SystemContext]:
        """结束当前系统流程，返回被结束的系统流程。"""
        ctx = self.active_system_flow
        self.active_system_flow = None
        return ctx

    # ── 槽位管理 ──────────────────────────────────────────────

    def set_slot(self, name: str, value: Any) -> None:
        if self.active_task is not None:
            self.active_task.slots[name] = value

    def get_slot(self, name: str, default: Any = None) -> Any:
        if self.active_task is None:
            return default
        return self.active_task.slots.get(name, default)

    def get_slot_from_task(
            self,
            task: TaskContext | None,
            name: str,
            default: Any = None,
    ) -> Any:
        if task is None:
            return default
        return task.slots.get(name, default)

    def visible_slots(self) -> Dict[str, Any]:
        if self.active_task is None:
            return {}
        return dict(self.active_task.slots)

    # ── 执行上下文辅助 ─────────────────────────────────────────

    def current_context_data(self) -> Dict[str, Any]:
        ctx = self.current_context
        return ctx.context_dict() if ctx is not None else {}

    def current_flow_id(self) -> str | None:
        ctx = self.current_context
        return ctx.flow_id if ctx else None

    def current_step_id(self) -> str | None:
        ctx = self.current_context
        return ctx.step_id if ctx else None

    def update_current_step(self, step_id: str | None) -> None:
        ctx = self.current_context
        if ctx is not None and step_id is not None:
            ctx.step_id = step_id

    # ── 聚焦对象 ──────────────────────────────────────────────

    def set_focused_object(self, message_object: MessageObject | None) -> None:
        if message_object is None:
            return
        self.focused_object = FocusedObject.from_message_object(message_object)

    # ── 会话管理 ──────────────────────────────────────────────

    def current_session(self) -> Optional[Session]:
        if self.current_session_id is None:
            return None
        for session in reversed(self.sessions):
            if session.session_id == self.current_session_id:
                return session
        return None

    def start_session(self, session_id: str | None = None) -> Session:
        session = Session(
            session_id=session_id or f"{self.sender_id}:session:{len(self.sessions) + 1}"
        )
        self.sessions.append(session)
        self.current_session_id = session.session_id
        return session

    def close_current_session(self) -> Optional[Session]:
        session = self.current_session()
        if session is None:
            return None
        session.close()
        self.current_session_id = None
        return session

    def reset_runtime_state_for_new_session(self) -> None:
        self.active_task = None
        self.paused_tasks = []
        self.active_system_flow = None
        self.focused_object = None
        self.latest_action_name = None

    def ensure_active_session(self) -> Session:
        session = self.current_session()
        if session is not None and not session.is_closed():
            return session
        return self.start_session()

    def begin_turn(self, message: Message) -> Turn:
        session = self.current_session()
        turn = Turn(
            turn_id=f"{session.session_id}:{message.message_id}",
            input_message=message,
        )
        self.pending_turn = turn
        return turn

    def commit_pending_turn(self) -> Optional[Turn]:
        if self.pending_turn is None:
            return None
        session = self.ensure_active_session()
        session.append_turn(self.pending_turn)
        committed = self.pending_turn
        self.pending_turn = None
        return committed

    def current_session_turns(self) -> List[Turn]:
        session = self.current_session()
        return list(session.turns) if session else []

    def recent_turns(self, max_turns: int | None = None) -> List[Turn]:
        turns = self.current_session_turns()
        return turns if max_turns is None else turns[-max_turns:]
