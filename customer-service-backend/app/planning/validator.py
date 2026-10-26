from app.task.commands.models import (
    CancelFlowCommand,
    ResumeTaskCommand,
    SetSlotsCommand,
    StartFlowCommand,
)
from app.task.flow.model import FlowsList
from app.domain.state import DialogueState
from app.knowledge.intents import KnowledgeIntent
from app.planning.plan import TurnPlan, TurnPlanValidationResult, build_clarify_message


class TurnPlanValidator:
    def validate(
            self,
            turn_plan: TurnPlan,
            state: DialogueState,
            flows: FlowsList,
            knowledge_intents: list[KnowledgeIntent],
    ) -> TurnPlanValidationResult:
        active_tracks = turn_plan.active_tracks()
        if not active_tracks:
            return self._reject("missing_track", "primary_track", state)
        if len(active_tracks) > 1:
            return self._reject("multiple_tracks", "primary_track", state)

        selected_track = active_tracks[0]
        if selected_track == "task":
            return self._validate_task(turn_plan, state=state, flows=flows)
        if selected_track == "knowledge":
            return self._validate_knowledge(turn_plan, state=state, knowledge_intents=knowledge_intents)
        return TurnPlanValidationResult(valid=True, selected_track="chitchat")

    def _validate_task(
            self,
            turn_plan: TurnPlan,
            *,
            state: DialogueState,
            flows: FlowsList,
    ) -> TurnPlanValidationResult:
        task_plan = turn_plan.task
        if task_plan is None or not task_plan.commands:
            return self._reject("missing_task_commands", "target_flow", state)

        allowed = (StartFlowCommand, ResumeTaskCommand, CancelFlowCommand, SetSlotsCommand)
        if not all(isinstance(command, allowed) for command in task_plan.commands):
            return self._reject("invalid_task_commands", "target_flow", state)

        start_commands = [command for command in task_plan.commands if isinstance(command, StartFlowCommand)]
        if len(start_commands) > 1:
            return self._reject("multiple_task_flows", "target_flow", state)
        if start_commands:
            flow = flows.flow_by_id(start_commands[0].flow)
            if flow is None:
                return self._reject("unknown_task_flow", "target_flow", state)
        return TurnPlanValidationResult(valid=True, selected_track="task")

    def _validate_knowledge(
            self,
            turn_plan: TurnPlan,
            *,
            state: DialogueState,
            knowledge_intents: list[KnowledgeIntent],
    ) -> TurnPlanValidationResult:
        knowledge_plan = turn_plan.knowledge
        if knowledge_plan is None or not knowledge_plan.intent:
            return self._reject("missing_knowledge_intent", "knowledge_intent", state)

        intent_map = {i.id: i for i in knowledge_intents}
        intent_meta = intent_map.get(knowledge_plan.intent)
        if intent_meta is None:
            return self._reject("unknown_knowledge_intent", "knowledge_intent", state)

        required_object = intent_meta.requires_object
        focused_object = state.focused_object
        if required_object is not None:
            if focused_object is None or focused_object.type != required_object:
                return self._reject("missing_focused_object", "focused_object", state)

        return TurnPlanValidationResult(valid=True, selected_track="knowledge")

    def _reject(
            self,
            reason: str,
            clarify_target: str,
            state: DialogueState,
    ) -> TurnPlanValidationResult:
        return TurnPlanValidationResult(
            valid=False,
            reason=reason,
            clarify_target=clarify_target,
            clarify_message=build_clarify_message(
                reason=reason,
                clarify_target=clarify_target,
                state=state,
            ),
        )
