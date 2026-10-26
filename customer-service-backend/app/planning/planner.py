from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser

from app.domain.messages import Message, MessageType
from app.task.flow.model import FlowsList
from app.task.flow.steps import CollectSlotStep
from app.domain.state import DialogueState
from app.knowledge.intents import KnowledgeIntent
from app.planning.plan import TurnPlan
from app.planning.parser import TurnPlanParser
from app.prompts import load_prompt_template
from app.prompts.transcript import TranscriptBuilder


@dataclass(slots=True)
class TurnPlannerConfig:
    """Configuration for the default turn planner."""

    max_history_turns: int | None = 20
    allow_blank_user_messages: bool = False
    prompt_name: str = "planning/turn_plan_v1"


class TurnPlanner:
    """Prompt-oriented turn-plan generator."""

    def __init__(
        self,
        *,
        llm: Any,
        config: TurnPlannerConfig | None = None,
        transcript_builder: TranscriptBuilder | None = None,
        turn_plan_parser: TurnPlanParser | None = None,
        output_parser: StrOutputParser | None = None,
    ) -> None:
        self.llm = llm
        self.config = config or TurnPlannerConfig()
        self.transcript_builder = transcript_builder or TranscriptBuilder()
        self.turn_plan_parser = turn_plan_parser or TurnPlanParser()
        self.output_parser = output_parser or StrOutputParser()
        self.prompt = self._load_prompt()

    async def predict(
        self,
        message: Message,
        state: DialogueState,
        flows: FlowsList,
        knowledge_intents: list[KnowledgeIntent] | None = None,
    ) -> TurnPlan:
        self._validate_message(message)
        prompt_inputs = self.build_prompt_inputs(message, state, flows, knowledge_intents)
        return await self.predict_from_prompt_inputs(
            message=message,
            state=state,
            flows=flows,
            prompt_inputs=prompt_inputs,
        )

    def build_prompt_inputs(
        self,
        message: Message,
        state: DialogueState,
        flows: FlowsList,
        knowledge_intents: list[KnowledgeIntent] | None = None,
    ) -> Dict[str, Any]:
        completed_turns = state.recent_turns(self.config.max_history_turns)
        transcript = self.transcript_builder.build_transcript(
            completed_turns
        )
        current_conversation = self.transcript_builder.append_user_message(
            transcript, message
        )
        active_task = state.active_task
        current_flow = flows.flow_by_id(active_task.flow_id) if active_task else None
        active_task_state = self._build_task_prompt_state(
            task=active_task,
            state=state,
            flows=flows,
        )
        interrupted_task_states = [
            self._build_task_prompt_state(task=task, state=state, flows=flows)
            for task in state.paused_tasks
        ]
        flow_slots = list(active_task_state.get("slots", [])) if active_task_state else []
        transcript = self._append_session_slot_context(
            transcript=transcript,
            current_flow=current_flow,
            flow_slots=flow_slots,
        )
        available_flows_json = json.dumps(
            {"flows": [self._flow_to_prompt_dict(flow) for flow in flows]},
            ensure_ascii=False,
        )
        active_task_json = (
            json.dumps(active_task_state, ensure_ascii=False)
            if active_task_state is not None
            else "null"
        )
        interrupted_tasks_json = json.dumps(
            interrupted_task_states,
            ensure_ascii=False,
        )
        task_bootstrap_json = json.dumps(
            self._build_task_bootstrap_state(state=state, flows=flows),
            ensure_ascii=False,
        )
        fo = state.focused_object
        focused_object_json = json.dumps(
            {"type": fo.type, "id": fo.id, "title": fo.title, "attributes": fo.attributes}
            if fo is not None else None,
            ensure_ascii=False,
        )
        knowledge_intents_json = json.dumps(
            [{"id": i.id, "description": i.description} for i in (knowledge_intents or [])],
            ensure_ascii=False,
        )
        now = datetime.now().astimezone()
        return {
            "current_date": now.strftime("%d %B, %Y"),
            "current_time": now.strftime("%H:%M:%S"),
            "current_timezone": now.tzname(),
            "current_day": now.strftime("%A"),
            "current_conversation": current_conversation,
            "user_message": message.text or "",
            "available_flows_json": available_flows_json,
            "active_task_json": active_task_json,
            "interrupted_tasks_json": interrupted_tasks_json,
            "task_bootstrap_json": task_bootstrap_json,
            "focused_object_json": focused_object_json,
            "knowledge_intents_json": knowledge_intents_json,
        }

    @staticmethod
    def _append_session_slot_context(
        *,
        transcript: str,
        current_flow: Any,
        flow_slots: List[Dict[str, Any]],
    ) -> str:
        if current_flow is not None or not flow_slots:
            return transcript

        slot_lines = []
        for slot_item in flow_slots:
            value = slot_item.get("value")
            if value in (None, ""):
                continue
            slot_lines.append(f"{slot_item.get('name')}={value}")
        if not slot_lines:
            return transcript

        context_line = "SYSTEM: 当前会话已保留上下文：" + "；".join(slot_lines)
        if not transcript:
            return context_line
        return f"{transcript}\n{context_line}"

    async def predict_from_prompt_inputs(
        self,
        *,
        message: Message,
        state: DialogueState,
        flows: FlowsList,
        prompt_inputs: Dict[str, Any],
    ) -> TurnPlan:
        chain = self.prompt | self.llm | self.output_parser
        llm_output = await chain.ainvoke(prompt_inputs)
        return self.turn_plan_parser.parse(llm_output)

    def _validate_message(self, message: Message) -> None:
        if message.type is not MessageType.TEXT:
            raise ValueError(
                "TurnPlanner only accepts user text messages."
            )
        if self.config.allow_blank_user_messages:
            return
        if (message.text or "").strip():
            return
        raise ValueError("User message text must not be empty.")

    @staticmethod
    def _flow_to_prompt_dict(flow: Any) -> Dict[str, Any]:
        return {
            "id": flow.id,
            "name": flow.readable_name() if hasattr(flow, "readable_name") else flow.id,
            "description": flow.description or "",
            "slots": [
                {
                    "name": slot.name,
                    "description": getattr(slot, "description", "") or "",
                }
                for slot in getattr(flow, "slots", [])
            ],
        }

    def _build_flow_slots(
        self,
        *,
        task: Any,
        state: DialogueState,
        flows: FlowsList,
        current_flow: Any,
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen_names: set[str] = set()
        slot_defs = (
            list(current_flow.slots)
            if current_flow is not None and getattr(current_flow, "slots", None)
            else []
        )
        task_slots = dict(getattr(task, "slots", {}) or {})
        for slot_name, slot_value in task_slots.items():
            if slot_value in (None, ""):
                continue
            slot_def = flows.slot_by_name(slot_name)
            if slot_def is None:
                continue
            slot_defs.append(slot_def)

        for slot_def in slot_defs:
            if slot_def.name in seen_names:
                continue
            seen_names.add(slot_def.name)
            result.append(
                {
                    "name": slot_def.name,
                    "value": state.get_slot_from_task(task, slot_def.name),
                    "type": slot_def.type,
                    "description": slot_def.description,
                }
            )
        return result

    def _build_task_prompt_state(
        self,
        *,
        task: Any,
        state: DialogueState,
        flows: FlowsList,
    ) -> Dict[str, Any] | None:
        if task is None:
            return None
        flow = flows.flow_by_id(task.flow_id)
        current_step = (
            flow.step_by_id(task.step_id)
            if flow is not None and task.step_id
            else None
        )
        requested_slot = None
        requested_slot_description = ""
        if isinstance(current_step, CollectSlotStep):
            requested_slot = current_step.slot_name
            requested_slot_description = current_step.description

        flow_slots = self._build_flow_slots(
            task=task,
            state=state,
            flows=flows,
            current_flow=flow,
        )
        return {
            "flow_id": task.flow_id,
            "flow_name": flow.readable_name() if flow is not None else task.flow_id,
            "step_id": task.step_id,
            "requested_slot": requested_slot,
            "requested_slot_description": requested_slot_description,
            "slots": flow_slots,
        }

    @staticmethod
    def _build_task_bootstrap_state(
        *,
        state: DialogueState,
        flows: FlowsList,
    ) -> Dict[str, Any]:
        focused_object = state.focused_object
        if focused_object is None:
            return {"focused_object": None, "flow_bootstrap_hints": []}

        focused_object_payload = {
            "type": focused_object.type,
            "id": focused_object.id,
            "title": focused_object.title,
            "attributes": focused_object.attributes,
        }

        if focused_object.type == "order":
            candidate_hints = [
                ("order_status_query", {"order_number": focused_object.id}),
                ("logistics_tracking", {"order_number": focused_object.id}),
                ("refund_request", {"order_number": focused_object.id}),
            ]
        elif focused_object.type == "product":
            candidate_hints = [
                ("similar_product_recommendation", {"product_id": focused_object.id}),
            ]
        else:
            candidate_hints = []

        flow_bootstrap_hints = [
            {"flow_id": flow_id, "slots": slots}
            for flow_id, slots in candidate_hints
            if flows.flow_by_id(flow_id) is not None
        ]
        return {
            "focused_object": focused_object_payload,
            "flow_bootstrap_hints": flow_bootstrap_hints,
        }


    def _load_prompt(self):
        return load_prompt_template(self.config.prompt_name)
