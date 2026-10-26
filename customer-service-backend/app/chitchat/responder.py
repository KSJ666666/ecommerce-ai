from typing import Any

from langchain_core.output_parsers import StrOutputParser

from app.domain.messages import BotMessage, Message
from app.domain.state import Turn
from app.prompts import load_prompt_template
from app.prompts.transcript import TranscriptBuilder


class ChitchatResponder:
    def __init__(self, *, llm: Any, transcript_builder: TranscriptBuilder | None = None) -> None:
        self.llm = llm
        self.transcript_builder = transcript_builder or TranscriptBuilder()
        self.output_parser = StrOutputParser()
        self.prompt = load_prompt_template("chitchat/response")

    async def respond(self, *, message: Message, recent_turns: list[Turn]) -> list[BotMessage]:
        history = self.transcript_builder.build_transcript(recent_turns)
        chain = self.prompt | self.llm | self.output_parser
        text = await chain.ainvoke({
            "history": history,
            "user_message": (message.text or "").strip(),
        })
        return [BotMessage(text=text.strip() or "你好。")]
