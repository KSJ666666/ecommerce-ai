from app.chitchat.responder import ChitchatResponder
from app.domain.messages import BotMessage, Message
from app.domain.state import DialogueState


class ChitchatHandler:
    def __init__(
        self,
        responder: ChitchatResponder,
        max_turns: int = 10,
    ) -> None:
        self.responder = responder
        self.max_turns = max_turns

    async def handle(self, *, message: Message, state: DialogueState) -> list[BotMessage]:
        recent_turns = state.recent_turns(self.max_turns)
        return await self.responder.respond(message=message, recent_turns=recent_turns)
