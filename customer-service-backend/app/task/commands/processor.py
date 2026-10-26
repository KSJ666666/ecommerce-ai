from typing import List

from app.domain.contexts import (
    CanceledSystemContext,
    CannotHandleSystemContext,
    InterruptedSystemContext,
    ResumedSystemContext,
    StartedSystemContext,
)
from app.domain.state import DialogueState
from app.task.commands.models import (
    CancelFlowCommand,
    Command,
    ResumeTaskCommand,
    SetSlotsCommand,
    StartFlowCommand,
)
from app.task.flow.model import FlowsList


class CommandProcessor:
    """将意图命令应用到对话状态，驱动状态机转换。"""

    def run(
        self,
        commands: List[Command],
        state: DialogueState,
        flows: FlowsList,
    ) -> None:
        for command in commands:
            self._apply(command, state, flows)

    def _apply(
        self,
        command: Command,
        state: DialogueState,
        flows: FlowsList,
    ) -> None:
        if isinstance(command, StartFlowCommand):
            self._handle_start_flow(command, state, flows)
        elif isinstance(command, SetSlotsCommand):
            self._handle_set_slots(command, state)
        elif isinstance(command, CancelFlowCommand):
            self._handle_cancel_flow(state, flows)
        elif isinstance(command, ResumeTaskCommand):
            self._handle_resume_task(command, state, flows)
        else:
            raise ValueError(
                f"Unsupported command instance: {type(command).__name__}"
            )

    def _handle_start_flow(
        self,
        command: StartFlowCommand,
        state: DialogueState,
        flows: FlowsList,
    ) -> None:
        # 清除当前系统流程（不再阻塞新任务启动）
        state.active_system_flow = None

        if command.flow.startswith("system_"):
            raise ValueError(
                f"Cannot start internal system flow '{command.flow}' directly."
            )
        flow = flows.flow_by_id(command.flow)
        if flow is None:
            raise ValueError(f"Unknown flow '{command.flow}'.")
        start_step = flow.start_step()
        if start_step is None:
            raise ValueError(f"Flow '{command.flow}' has no start step.")

        active_task = state.active_task
        if active_task is not None:
            # 当前有活跃任务
            if active_task.flow_id == command.flow:
                # 同一个流程，不重复启动
                return
            # 打断当前任务，尝试恢复暂停中的同名任务
            interrupted_flow_id = active_task.flow_id
            interrupted_flow_name = self._readable_flow_name(active_task.flow_id, flows)
            state.pause_active_task()
            resumed_task = state.resume_task(command.flow)
            started_flow_id = ""
            started_flow_name = ""
            if resumed_task is None:
                state.start_new_task(flow_id=command.flow, step_id=start_step.id)
                started_flow_id = command.flow
                started_flow_name = self._readable_flow_name(command.flow, flows)
            self._activate_interruption_system_flow(
                state,
                flows,
                interrupted_flow_id=interrupted_flow_id,
                interrupted_flow_name=interrupted_flow_name,
                started_flow_id=started_flow_id,
                started_flow_name=started_flow_name,
            )
            return

        # 无活跃任务：尝试恢复暂停中的同名任务，否则新建
        resumed_task = state.resume_task(command.flow)
        if resumed_task is not None:
            self._activate_resumed_system_flow(
                state,
                flows,
                resumed_flow_id=resumed_task.flow_id,
                resumed_flow_name=self._readable_flow_name(resumed_task.flow_id, flows),
            )
            return
        state.start_new_task(flow_id=command.flow, step_id=start_step.id)
        self._activate_started_system_flow(
            state,
            flows,
            started_flow_id=command.flow,
            started_flow_name=self._readable_flow_name(command.flow, flows),
        )

    def _handle_set_slots(
        self,
        command: SetSlotsCommand,
        state: DialogueState,
    ) -> None:
        if state.active_task is None:
            return
        for name, value in command.slots.items():
            state.set_slot(name, value)

    def _handle_cancel_flow(
        self,
        state: DialogueState,
        flows: FlowsList,
    ) -> None:
        canceled_task = state.cancel_active_task()
        if canceled_task is None:
            return
        self._activate_cancel_system_flow(
            state,
            flows,
            canceled_flow_id=canceled_task.flow_id,
            canceled_flow_name=self._readable_flow_name(canceled_task.flow_id, flows),
        )

    def _handle_resume_task(
        self,
        command: ResumeTaskCommand,
        state: DialogueState,
        flows: FlowsList,
    ) -> None:
        resumed_task = None
        if command.flow:
            resumed_task = state.resume_task(command.flow)
        else:
            resumed_task = state.resume_task()
        if resumed_task is None:
            return
        self._activate_resumed_system_flow(
            state,
            flows,
            resumed_flow_id=resumed_task.flow_id,
            resumed_flow_name=self._readable_flow_name(resumed_task.flow_id, flows),
        )

    def trigger_cannot_handle(
        self,
        state: DialogueState,
        flows: FlowsList,
        *,
        reason: str | None = None,
    ) -> None:
        # 清除澄清/完成相关系统流程
        state.active_system_flow = None
        flow = flows.flow_by_id("system_cannot_handle")
        if flow is None:
            raise ValueError(
                "Runtime fallback requires a 'system_cannot_handle' flow."
            )
        start_step = flow.start_step()
        if start_step is None:
            raise ValueError(
                "The 'system_cannot_handle' flow has no start step."
            )
        # 打断当前任务再激活无法处理系统流程
        if state.active_task is not None:
            state.pause_active_task()
        state.activate_system_flow(
            CannotHandleSystemContext(
                step_id=start_step.id,
                reason=reason,
            )
        )

    @staticmethod
    def _activate_cancel_system_flow(
        state: DialogueState,
        flows: FlowsList,
        *,
        canceled_flow_id: str,
        canceled_flow_name: str,
    ) -> None:
        system_flow = flows.flow_by_id("system_task_canceled")
        start_step = system_flow.start_step() if system_flow is not None else None
        if start_step is None:
            return
        state.activate_system_flow(
            CanceledSystemContext(
                step_id=start_step.id,
                canceled_flow_id=canceled_flow_id,
                canceled_flow_name=canceled_flow_name,
            )
        )

    @staticmethod
    def _activate_started_system_flow(
        state: DialogueState,
        flows: FlowsList,
        *,
        started_flow_id: str,
        started_flow_name: str,
    ) -> None:
        system_flow = flows.flow_by_id("system_task_started")
        start_step = system_flow.start_step() if system_flow is not None else None
        if start_step is None:
            return
        state.activate_system_flow(
            StartedSystemContext(
                step_id=start_step.id,
                started_flow_id=started_flow_id,
                started_flow_name=started_flow_name,
            )
        )

    @staticmethod
    def _activate_interruption_system_flow(
        state: DialogueState,
        flows: FlowsList,
        *,
        interrupted_flow_id: str,
        interrupted_flow_name: str,
        started_flow_id: str = "",
        started_flow_name: str = "",
    ) -> None:
        system_flow = flows.flow_by_id("system_task_interrupted")
        start_step = system_flow.start_step() if system_flow is not None else None
        if start_step is None:
            return
        state.activate_system_flow(
            InterruptedSystemContext(
                step_id=start_step.id,
                interrupted_flow_id=interrupted_flow_id,
                interrupted_flow_name=interrupted_flow_name,
                started_flow_id=started_flow_id,
                started_flow_name=started_flow_name,
            )
        )

    @staticmethod
    def _activate_resumed_system_flow(
        state: DialogueState,
        flows: FlowsList,
        *,
        resumed_flow_id: str,
        resumed_flow_name: str,
    ) -> None:
        system_flow = flows.flow_by_id("system_task_resumed")
        start_step = system_flow.start_step() if system_flow is not None else None
        if start_step is None:
            return
        state.activate_system_flow(
            ResumedSystemContext(
                step_id=start_step.id,
                resumed_flow_id=resumed_flow_id,
                resumed_flow_name=resumed_flow_name,
            )
        )

    @staticmethod
    def _readable_flow_name(flow_id: str, flows: FlowsList) -> str:
        flow = flows.flow_by_id(flow_id)
        return flow.readable_name() if flow is not None else flow_id.replace("_", " ")
