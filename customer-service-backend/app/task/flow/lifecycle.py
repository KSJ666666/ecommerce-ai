from app.domain.contexts import CompletedSystemContext, TaskContext
from app.task.flow.model import FlowsList


def end_current_flow(state, flows: FlowsList) -> object | None:
    """结束当前正在执行的流程。

    - 若有活跃系统流程，直接结束并返回。
    - 若有活跃业务任务，结束任务并在需要时触发完成流程。
    """
    if state.active_system_flow is not None:
        return state.end_system_flow()

    task = state.active_task
    if task is None:
        return None

    state.active_task = None
    _trigger_completed_if_needed(task, state, flows)
    return task


def _trigger_completed_if_needed(
    task: TaskContext,
    state,
    flows: FlowsList,
) -> None:
    """若任务完成后无暂停任务，且流程配置了完成回调，则激活完成系统流程。"""
    if state.paused_tasks:
        return
    flow = flows.flow_by_id(task.flow_id)
    if flow is None:
        return
    system_flow = flows.flow_by_id("system_completed")
    start_step = system_flow.start_step() if system_flow is not None else None
    state.activate_system_flow(
        CompletedSystemContext(
            step_id=start_step.id if start_step is not None else None,
            previous_flow_name=flow.readable_name(),
        )
    )
