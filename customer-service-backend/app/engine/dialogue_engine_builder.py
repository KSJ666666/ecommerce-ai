from pathlib import Path

from app.engine.dialogue_engine import DialogueEngine, DialogueConfig
from app.planning.clarify import ClarifyResponder
from app.planning.validator import TurnPlanValidator
from app.task.actions.builder import build_action_runner
from app.task.commands.processor import CommandProcessor
from app.task.flow.executor import FlowExecutor
from app.task.flow.loader import FlowLoader
from app.task.handler import TaskHandler
from app.infrastructure.llm import llm
from app.chitchat.handler import ChitchatHandler
from app.chitchat.responder import ChitchatResponder
from app.knowledge.handler import KnowledgeHandler
from app.knowledge.intents import KNOWLEDGE_INTENTS
from app.knowledge.planner import KnowledgePlanner
from app.knowledge.provider import (
    FaqKnowledgeProvider,
    OrderApiProvider,
    ProductApiProvider,
    RagKnowledgeProvider,
)
from app.knowledge.responder import KnowledgeResponder
from app.planning.planner import TurnPlanner

_PROJECT_ROOT = Path(__file__).parents[2]
_FLOW_CONFIG_DIR = _PROJECT_ROOT / "flow_config"
_FLOW_CONFIG_FILES = ("user_flows.yml", "system_flows.yml")


def build_dialogue_engine() -> DialogueEngine:
    config = DialogueConfig()
    flow_paths = [_FLOW_CONFIG_DIR / f for f in _FLOW_CONFIG_FILES]
    flows = FlowLoader().load_many(flow_paths)
    return DialogueEngine(
        flows=flows,
        knowledge_intents=KNOWLEDGE_INTENTS,
        turn_planner=TurnPlanner(llm=llm),
        task_handler=TaskHandler(
            flows=flows,
            command_processor=CommandProcessor(),
            flow_executor=FlowExecutor(),
            action_runner=build_action_runner(llm=llm, include_custom_actions=True),
            max_steps=config.max_flow_steps,
        ),
        knowledge_handler=KnowledgeHandler(
            responder=KnowledgeResponder(llm=llm),
            providers=[
                ProductApiProvider(),
                OrderApiProvider(),
                FaqKnowledgeProvider(),
                RagKnowledgeProvider(),
            ],
            planner=KnowledgePlanner(intents=KNOWLEDGE_INTENTS),
        ),
        chitchat_handler=ChitchatHandler(
            responder=ChitchatResponder(llm=llm),
        ),
        clarify_responder=ClarifyResponder(llm=llm),
        turn_plan_validator=TurnPlanValidator(),
        config=config,
    )
