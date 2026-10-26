from __future__ import annotations

from dataclasses import dataclass

from app.domain.messages import Message
from app.domain.state import DialogueState, Turn


@dataclass(slots=True)
class KnowledgeContext:
    message: Message
    recent_turns: list[Turn]
    product_id: str | None
    order_number: str | None
    focused_object_type: str | None
    intent: str | None = None

    @property
    def user_message(self) -> str:
        return (self.message.text or "").strip()

    @property
    def has_explicit_query(self) -> bool:
        return bool(self.user_message)


class KnowledgeContextBuilder:
    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns

    def build(self, message: Message, state: DialogueState, intent: str | None = None) -> KnowledgeContext:
        recent_turns = state.recent_turns(self.max_turns)
        focused_object = state.focused_object
        product_id = (
            focused_object.id
            if focused_object is not None and focused_object.type == "product"
            else state.get_slot("product_id") or None
        )
        order_number = (
            focused_object.id
            if focused_object is not None and focused_object.type == "order"
            else state.get_slot("order_number") or None
        )
        return KnowledgeContext(
            message=message,
            recent_turns=recent_turns,
            product_id=product_id,
            order_number=order_number,
            focused_object_type=focused_object.type if focused_object is not None else None,
            intent=intent,
        )
