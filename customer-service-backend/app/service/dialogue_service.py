from app.domain.messages import Message, ProcessResult, BotMessage
from app.engine.dialogue_engine import DialogueEngine
from app.repository.dialogue_state_repository import DialogueStateRepository


class DialogueService:
    def __init__(self, dialogue_state_repository: DialogueStateRepository,
                 dialogue_engine: DialogueEngine):
        self.dialogue_state_repository = dialogue_state_repository
        self.dialogue_engine = dialogue_engine

    async def handle_message(self, message: Message) -> ProcessResult:
        # 具体处理逻辑
        # 获取对话状态
        state = await self.dialogue_state_repository.load(message.sender_id)

        # 处理本轮对话
        result = await self.dialogue_engine.process(message, state)

        # 保存对话状态
        await self.dialogue_state_repository.save(state)

        return result
