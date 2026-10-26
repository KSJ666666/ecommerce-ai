from dataclasses import dataclass, field
from typing import Any, List

from jinja2 import Template

from app.task.actions.runner import ActionRunner
from app.domain.messages import BotMessage
from app.task.flow.links import (
    FallbackLink,
    ConditionalLink,
    StaticLink,
)
from app.task.flow.steps import (
    ActionFlowStep,
    CollectSlotStep,
    EndFlowStep,
    FlowStep,
    SetSlotsFlowStep,
)
from app.domain.contexts import CollectSystemContext
from app.task.flow.lifecycle import end_current_flow
from app.task.flow.model import Flow, FlowsList
from app.task.flow.step_result import (
    FlowContinue,
    FlowStepResult,
    FlowPause,
)
from app.domain.state import DialogueState


@dataclass(slots=True)
class TaskRunResult:
    """任务轨道执行结果。"""
    action_names: List[str] = field(default_factory=list)
    messages: List[BotMessage] = field(default_factory=list)


class FlowExecutor:
    """推进活跃流程，直到需要执行下一个动作。"""

    def __init__(self, *, max_steps: int = 250) -> None:
        self.max_steps = max_steps

    async def advance_flows(
        self,
        state: DialogueState,
        flows: FlowsList,
    ) -> FlowPause:
        if state.current_context is None:
            return FlowPause("action_listen")
        return await self.advance_flows_until_next_action(state, flows)

    async def advance_flows_until_next_action(
        self,
        state: DialogueState,
        flows: FlowsList,
    ) -> FlowPause:
        step_result: FlowStepResult = FlowContinue()
        steps_taken = 0

        while isinstance(step_result, FlowContinue):
            steps_taken += 1
            if steps_taken > self.max_steps:
                raise RuntimeError(
                    f"Flow execution exceeded {self.max_steps} steps."
                )

            ctx = state.current_context
            if ctx is None:
                step_result = FlowPause("action_listen")
                break

            flow = flows.flow_by_id(ctx.flow_id)
            if flow is None:
                raise ValueError(f"Unknown active flow '{ctx.flow_id}'.")

            current_step = (
                flow.step_by_id(ctx.step_id)
                if ctx.step_id
                else flow.start_step()
            )
            if current_step is None:
                end_current_flow(state, flows)
                continue

            if isinstance(current_step, CollectSlotStep):
                self._try_fill_from_focused_object(current_step, state)
                collect_step_result = self._advance_collect_step(
                    current_step, flow, state, flows
                )
                if collect_step_result is not None:
                    step_result = collect_step_result
                    continue

            if self._should_run_current_collect_step(current_step, state):
                next_step = current_step
            else:
                next_step = self._select_next_step(current_step, flow, state)
                if next_step is None:
                    end_current_flow(state, flows)
                    continue

            state.update_current_step(next_step.id)
            if isinstance(next_step, CollectSlotStep):
                self._try_fill_from_focused_object(next_step, state)
            step_result = self.run_step(next_step, flow, state, flows)

        if isinstance(step_result, FlowPause):
            return step_result

        return FlowPause("action_listen")

    def run_step(
        self,
        step: FlowStep,
        flow: Flow,
        state: DialogueState,
        flows: FlowsList,
    ) -> FlowStepResult:
        if isinstance(step, ActionFlowStep):
            action_name = self._render_step_action(step.action, state)
            if action_name == "action_listen":
                return FlowPause("action_listen")
            args = self._resolve_action_args(step.args, state.current_context_data())
            return FlowPause(action_name, action_kwargs=args)

        if isinstance(step, CollectSlotStep):
            if self._is_slot_filled(step.slot_name, state):
                return FlowContinue()
            collect_flow = flows.flow_by_id("system_collect_information")
            if collect_flow is None:
                raise ValueError(
                    "Collect steps require a 'system_collect_information' flow."
                )
            start_step = collect_flow.start_step()
            if start_step is None:
                raise ValueError(
                    "The 'system_collect_information' flow has no start step."
                )
            state.activate_system_flow(
                CollectSystemContext(
                    step_id=start_step.id,
                    slot_name=step.slot_name,
                    response={
                        "mode": step.response.mode,
                        "text": step.response.text,
                        "prompt": step.response.prompt,
                    },
                )
            )
            return FlowContinue()

        if isinstance(step, SetSlotsFlowStep):
            for slot_item in step.slots:
                state.set_slot(slot_item["key"], slot_item["value"])
            return FlowContinue()

        if isinstance(step, EndFlowStep):
            end_current_flow(state, flows)
            return FlowContinue(has_flow_ended=True)

        return FlowContinue()

    @staticmethod
    def _is_slot_filled(slot_name: str, state: DialogueState) -> bool:
        value = state.get_slot(slot_name)
        return value is not None and value != ""

    # focused_object → slot 映射表：(object_type, slot_name) → 取值函数
    _FOCUSED_OBJECT_SLOT_MAP: dict = {
        ("order",   "order_number"): lambda fo: fo.id,
        ("product", "product_id"):   lambda fo: fo.id,
    }

    def _try_fill_from_focused_object(
        self,
        step: CollectSlotStep,
        state: DialogueState,
    ) -> None:
        """若 focused_object 能提供当前 collect slot 的值且槽位为空，自动填入。"""
        if self._is_slot_filled(step.slot_name, state):
            return
        fo = state.focused_object
        if fo is None:
            return
        extractor = self._FOCUSED_OBJECT_SLOT_MAP.get((fo.type, step.slot_name))
        if extractor is not None:
            state.set_slot(step.slot_name, extractor(fo))

    def _should_run_current_collect_step(
        self,
        step: FlowStep,
        state: DialogueState,
    ) -> bool:
        return isinstance(step, CollectSlotStep) and not self._is_slot_filled(
            step.slot_name, state
        )

    def _advance_collect_step(
        self,
        step: CollectSlotStep,
        flow: Flow,
        state: DialogueState,
        flows: FlowsList,
    ) -> FlowStepResult | None:
        if not self._is_slot_filled(step.slot_name, state):
            return None

        rule = step.validation
        if rule is None:
            return None
        condition = rule.condition
        if condition is not None and self._evaluate_condition(condition, state, flow, step):
            return None

        state.set_slot(step.slot_name, None)

        if rule.failure_response is not None:
            failure_resp = rule.failure_response
            return FlowPause(
                "action_response",
                action_kwargs={
                    "mode": failure_resp.mode,
                    "text": failure_resp.text,
                    "prompt": failure_resp.prompt,
                },
            )

        return FlowContinue()

    def _select_next_step(
        self, step: FlowStep, flow: Flow, state: DialogueState
    ) -> FlowStep | None:
        links = step.next
        if not links:
            return None
        for link in links:
            if isinstance(link, StaticLink):
                return flow.step_by_id(link.target)
            if isinstance(link, ConditionalLink):
                if self._evaluate_condition(link.condition, state, flow, step):
                    return flow.step_by_id(link.target)
            if isinstance(link, FallbackLink):
                return flow.step_by_id(link.target)
        return None

    @staticmethod
    def _evaluate_condition(
        expression: str, state: DialogueState, flow: Flow, step: FlowStep
    ) -> bool:
        if not expression.strip():
            return True
        document = {
            "slots": state.visible_slots(),
            "context": dict(state.current_context_data()),
            "flow_id": flow.id,
            "step_id": step.id,
        }
        try:
            return bool(eval(expression, {"__builtins__": {}}, document))
        except Exception:
            return False

    @staticmethod
    def _render_step_action(action_name: str, state: DialogueState) -> str:
        if "{{" not in action_name:
            return action_name
        return Template(action_name).render(context=state.current_context_data())

    @staticmethod
    def _resolve_context_reference(reference: str, context: dict[str, Any]) -> Any:
        ref = str(reference).strip()
        if not ref.startswith("context."):
            return None
        current: Any = context
        for part in ref.split(".")[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                return None
        return current

    @classmethod
    def _resolve_action_args(
        cls,
        raw_args: dict[str, Any] | str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = cls._resolve_argument_value(raw_args, context)
        return resolved if isinstance(resolved, dict) else {}

    @classmethod
    def _resolve_argument_value(cls, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str) and value.strip().startswith("context."):
            return cls._resolve_context_reference(value, context)
        if isinstance(value, dict):
            return {
                key: cls._resolve_argument_value(item, context)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._resolve_argument_value(item, context) for item in value]
        return value

    async def run_task(
        self,
        state: DialogueState,
        flows: FlowsList,
        action_runner: ActionRunner,
        *,
        max_steps: int = 1000,
    ) -> TaskRunResult:
        """循环推进 flow 并执行 action，直到等待用户输入为止。"""
        result = TaskRunResult()
        step_count = 0

        while True:
            action_call = await self.advance_flows(state, flows)
            action_result = await action_runner.run(
                action_call.action_name,
                state,
                **action_call.action_kwargs,
            )

            for slot_name, value in action_result.slot_updates.items():
                state.set_slot(slot_name, value)
            result.messages.extend(action_result.messages)
            result.action_names.append(action_call.action_name)
            state.latest_action_name = action_call.action_name

            step_count += 1
            if action_call.action_name == "action_listen":
                break
            if step_count >= max_steps:
                raise RuntimeError(
                    f"Flow execution exceeded {max_steps} steps."
                )

        return result
