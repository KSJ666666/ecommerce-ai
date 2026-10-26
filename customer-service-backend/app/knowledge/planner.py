from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.context_builder import KnowledgeContext
from app.knowledge.intents import KnowledgeIntent


@dataclass(slots=True)
class KnowledgePlan:
    provider_ids: list[str] = field(default_factory=list)


class KnowledgePlanner:
    def __init__(self, intents: list[KnowledgeIntent] | None = None) -> None:
        self._intent_map = {i.id: i for i in (intents or [])}

    def plan(self, context: KnowledgeContext) -> KnowledgePlan:
        base_providers = self._base_providers_for_intent(context.intent)

        if context.focused_object_type == "order" and context.order_number:
            return KnowledgePlan(provider_ids=["api.order", *base_providers])
        if context.focused_object_type == "product" and context.product_id:
            return KnowledgePlan(provider_ids=["api.product", *base_providers])
        return KnowledgePlan(provider_ids=base_providers)

    def _base_providers_for_intent(self, intent: str | None) -> list[str]:
        if intent and intent in self._intent_map:
            return list(self._intent_map[intent].provider_ids)
        return ["faq.default", "rag.default"]
