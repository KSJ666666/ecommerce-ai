import time
from dataclasses import dataclass
from enum import Enum
from typing import List

from app.domain.messages import Message, MessageType, ProcessResult
from app.task.commands.models import Command, SetSlotsCommand
from app.task.flow.steps import CollectSlotStep
from app.task.flow.model import FlowsList
from app.task.handler import TaskHandler
from app.knowledge.intents import KnowledgeIntent
from app.planning.planner import TurnPlanner
from app.planning.clarify import ClarifyResponder
from app.chitchat.handler import ChitchatHandler
from app.knowledge.handler import KnowledgeHandler
from app.domain.contexts import CollectSystemContext
from app.domain.state import DialogueState, Turn
from app.planning.validator import TurnPlanValidator


class TrackType(str, Enum):
    TASK = "task"
    KNOWLEDGE = "knowledge"
    CHITCHAT = "chitchat"


@dataclass(slots=True)
class DialogueConfig:
    """流程执行限制与会话超时设置。"""

    max_flow_steps: int = 1000
    session_timeout_seconds: float = 60.0 * 60.0


class DialogueEngine:
    """无状态对话引擎：接收消息和当前状态，驱动流程并返回结果。

    不做任何 I/O。状态的加载与保存由 DialogueService 负责。
    """

    def __init__(
            self,
            flows: FlowsList,
            knowledge_intents: list[KnowledgeIntent],
            turn_planner: TurnPlanner,
            task_handler: TaskHandler,
            knowledge_handler: KnowledgeHandler,
            chitchat_handler: ChitchatHandler,
            clarify_responder: ClarifyResponder,
            turn_plan_validator: TurnPlanValidator,
            config: DialogueConfig
    ) -> None:
        self.flows = flows
        self.knowledge_intents = knowledge_intents
        self.turn_planner = turn_planner
        self.task_handler = task_handler
        self.knowledge_handler = knowledge_handler
        self.chitchat_handler = chitchat_handler
        self.clarify_responder = clarify_responder
        self.turn_plan_validator = turn_plan_validator
        self.config = config

    async def process(self, message: Message, state: DialogueState) -> ProcessResult:
        """处理一条消息，直接修改 state，返回本轮结果。"""
        self._prepare_session(state)
        turn = self._begin_turn(state, message)

        if message.type is MessageType.OBJECT:
            state.set_focused_object(message.object)

        intent: str | None = None
        if message.type is MessageType.TEXT:
            turn_plan = await self.turn_planner.predict(message, state, self.flows, self.knowledge_intents)
            validation = self.turn_plan_validator.validate(
                turn_plan, state=state, flows=self.flows, knowledge_intents=self.knowledge_intents,
            )
            if not validation.valid:
                return await self._finish_with_clarify(
                    message=message, state=state, turn=turn,
                    reason=validation.reason,
                    clarify_target=validation.clarify_target,
                    clarify_message=validation.clarify_message,
                )
            if validation.selected_track == "task":
                commands: List[Command] = list(turn_plan.task.commands if turn_plan.task is not None else [])
                track_type = TrackType.TASK
            elif validation.selected_track == "knowledge":
                commands = []
                track_type = TrackType.KNOWLEDGE
                intent = turn_plan.knowledge.intent if turn_plan.knowledge else None
            else:
                commands = []
                track_type = TrackType.CHITCHAT
        else:
            object_clarify_message = self._render_object_clarify_message(
                message=message, state=state, flows=self.flows,
            )
            if object_clarify_message is not None:
                return await self._finish_with_clarify(
                    message=message, state=state, turn=turn,
                    reason="object_requires_intent",
                    clarify_target="target_flow",
                    clarify_message=object_clarify_message,
                )
            commands = self._resolve_object_commands(
                message=message, state=state, flows=self.flows,
            )
            track_type = TrackType.TASK

        if track_type is TrackType.TASK:
            await self.task_handler.handle(commands=commands, state=state, turn=turn)
        elif track_type is TrackType.KNOWLEDGE:
            state.pause_active_task()
            turn.assistant_messages.extend(
                await self.knowledge_handler.handle(message=message, state=state, intent=intent)
            )
        else:
            state.pause_active_task()
            turn.assistant_messages.extend(await self.chitchat_handler.handle(message=message, state=state))

        committed_turn = state.commit_pending_turn()
        if committed_turn is None:
            raise ValueError("No pending turn available for commit.")

        return ProcessResult(
            sender_id=message.sender_id,
            message_id=message.message_id,
            messages=list(turn.assistant_messages),
        )

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _prepare_session(self, state: DialogueState) -> None:
        session = state.current_session()
        now = time.time()
        if session is None:
            state.start_session()
            return
        if session.is_closed():
            state.reset_runtime_state_for_new_session()
            state.start_session()
            return
        if now - session.last_activity_at > self.config.session_timeout_seconds:
            state.close_current_session()
            state.reset_runtime_state_for_new_session()
            state.start_session()

    @staticmethod
    def _begin_turn(state: DialogueState, message: Message) -> Turn:
        if state.pending_turn is not None:
            raise ValueError(
                "Cannot start a new turn while another pending turn exists."
            )
        return state.begin_turn(message)

    async def _finish_with_clarify(
            self,
            *,
            message: Message,
            state: DialogueState,
            turn: Turn,
            reason: str | None,
            clarify_target: str | None,
            clarify_message: str | None,
    ) -> ProcessResult:
        messages = await self.clarify_responder.respond(
            message=message, state=state,
            reason=reason,
            clarify_target=clarify_target,
            fallback_message=clarify_message,
        )
        turn.assistant_messages.extend(messages)
        state.commit_pending_turn()
        return ProcessResult(
            sender_id=message.sender_id,
            message_id=message.message_id,
            messages=list(turn.assistant_messages),
        )

    def _resolve_object_commands(
            self,
            message: Message,
            state: DialogueState,
            flows: FlowsList,
    ) -> List[Command]:
        message_object = message.object
        if message_object is None:
            return []

        object_type = message_object.type.strip().lower()
        collect_slot_name = self._current_collect_slot_name(state=state, flows=flows)

        if object_type == "order":
            if collect_slot_name == "order_number":
                return [SetSlotsCommand(slots={"order_number": message_object.id})]
            return []

        if object_type == "product":
            if collect_slot_name == "product_id":
                return [SetSlotsCommand(slots={"product_id": message_object.id})]
            return []

        return []

    def _render_object_clarify_message(
            self,
            message: Message,
            state: DialogueState,
            flows: FlowsList,
    ) -> str | None:
        if message.type is not MessageType.OBJECT:
            return None

        message_object = message.object
        if message_object is None:
            return None

        object_type = message_object.type.strip().lower()
        if object_type not in {"order", "product"}:
            return None

        collect_slot_name = self._current_collect_slot_name(state=state, flows=flows)
        if object_type == "order" and collect_slot_name == "order_number":
            return None
        if object_type == "product" and collect_slot_name == "product_id":
            return None

        if object_type == "order":
            return "我已经收到这个订单了。你想查订单状态、查物流，还是申请退款呢？"
        return "我已经收到这个商品了。你想了解它的商品信息、发货情况，还是售后相关问题呢？"

    @staticmethod
    def _current_collect_slot_name(
            state: DialogueState,
            flows: FlowsList,
    ) -> str | None:
        if isinstance(state.active_system_flow, CollectSystemContext):
            return state.active_system_flow.slot_name or None

        active_task = state.active_task
        if active_task is None:
            return None
        current_flow = flows.flow_by_id(active_task.flow_id)
        if current_flow is None:
            return None
        current_step = current_flow.step_by_id(active_task.step_id)
        if not isinstance(current_step, CollectSlotStep):
            return None
        return current_step.slot_name
