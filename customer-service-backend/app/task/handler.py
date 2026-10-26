from typing import List

from app.task.actions.runner import ActionRunner
from app.task.commands.models import Command
from app.task.commands.processor import CommandProcessor
from app.domain.state import DialogueState, Turn
from app.task.flow.executor import FlowExecutor
from app.task.flow.model import FlowsList


class TaskHandler:
    def __init__(
        self,
        flows: FlowsList,
        command_processor: CommandProcessor,
        flow_executor: FlowExecutor,
        action_runner: ActionRunner,
        max_steps: int = 1000,
    ) -> None:
        self.flows = flows
        self.command_processor = command_processor
        self.flow_executor = flow_executor
        self.action_runner = action_runner
        self.max_steps = max_steps

    async def handle(
        self,
        commands: List[Command],
        state: DialogueState,
        turn: Turn,
    ) -> None:
        if commands:
            self.command_processor.run(commands, state, self.flows)

        run = await self.flow_executor.run_task(
            state, self.flows, self.action_runner,
            max_steps=self.max_steps,
        )
        turn.assistant_messages.extend(run.messages)
