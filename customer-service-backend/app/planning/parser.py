import json
from typing import Any

from app.task.commands.models import parse_command
from app.planning.plan import ChitchatTurnPlan, KnowledgeTurnPlan, TaskTurnPlan, TurnPlan


class TurnPlanParser:
    def parse(self, payload: str) -> TurnPlan:
        normalized_payload = self._strip_code_fences(payload)
        try:
            data = json.loads(normalized_payload)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM output is not valid JSON: {e.msg}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError("TurnPlan output must be a JSON object.")

        task_plan = self._parse_task(data.get("task"))
        knowledge_plan = self._parse_knowledge(data.get("knowledge"))
        chitchat_plan = self._parse_chitchat(data.get("chitchat"))
        return TurnPlan(
            task=task_plan,
            knowledge=knowledge_plan,
            chitchat=chitchat_plan,
        )

    def _parse_task(self, payload: Any) -> TaskTurnPlan | None:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("'task' must be a JSON object or null.")
        commands_data = payload.get("commands", [])
        if not isinstance(commands_data, list):
            raise ValueError("'task.commands' must be a JSON array.")
        commands = [parse_command(item) for item in commands_data]
        return TaskTurnPlan(commands=commands)

    @staticmethod
    def _parse_knowledge(payload: Any) -> KnowledgeTurnPlan | None:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("'knowledge' must be a JSON object or null.")
        intent = str(payload.get("intent") or "").strip()
        return KnowledgeTurnPlan(intent=intent)

    @staticmethod
    def _parse_chitchat(payload: Any) -> ChitchatTurnPlan | None:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("'chitchat' must be a JSON object or null.")
        return ChitchatTurnPlan()

    @staticmethod
    def _strip_code_fences(payload: str) -> str:
        content = payload.strip()
        if content.startswith("```") and content.endswith("```"):
            lines = content.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[1:-1]).strip()
        return content
