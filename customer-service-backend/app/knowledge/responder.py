from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import StrOutputParser

from app.domain.messages import BotMessage
from app.knowledge.context_builder import KnowledgeContext
from app.knowledge.provider import KnowledgeChunk
from app.prompts import load_prompt_template
from app.prompts.transcript import TranscriptBuilder


class KnowledgeResponder:
    """
    Generates open-ended knowledge responses using LLM.

    Assembles a prompt from:
      1. Retrieved knowledge chunks (from KnowledgeProvider list)
      2. Recent conversation history (all tracks, last N turns)
      3. The user's current question

    Supports multi-turn follow-up because the full turn history is included.
    When no explicit question is present (object-triggered), prompts the user
    to ask their question.
    """

    def __init__(self, *, llm: Any, transcript_builder: TranscriptBuilder | None = None) -> None:
        self.llm = llm
        self.transcript_builder = transcript_builder or TranscriptBuilder()
        self.output_parser = StrOutputParser()
        self.response_prompt = load_prompt_template("knowledge/response")
        self.greeting_prompt = load_prompt_template("knowledge/greeting_response")

    async def respond(
        self,
        context: KnowledgeContext,
        chunks: list[KnowledgeChunk],
    ) -> list[BotMessage]:
        knowledge_content = "\n\n".join(chunk.content for chunk in chunks)
        history = self.transcript_builder.build_transcript(context.recent_turns)

        if not context.has_explicit_query:
            return await self._respond_with_greeting(knowledge_content)

        chain = self.response_prompt | self.llm | self.output_parser
        text = await chain.ainvoke({
            "knowledge_content": knowledge_content,
            "history": history,
            "user_message": context.user_message,
        })
        return [BotMessage(text=text.strip() or "抱歉，我暂时没有找到相关信息。")]

    async def _respond_with_greeting(self, knowledge_content: str) -> list[BotMessage]:
        chain = self.greeting_prompt | self.llm | self.output_parser
        text = await chain.ainvoke({"knowledge_content": knowledge_content})
        return [BotMessage(text=text.strip() or "已收到商品信息，你想了解什么？")]

