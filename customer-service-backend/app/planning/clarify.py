from typing import Any

from langchain_core.output_parsers import StrOutputParser

from app.domain.messages import BotMessage, Message
from app.domain.state import DialogueState
from app.prompts import load_prompt_template
from app.prompts.transcript import TranscriptBuilder


class ClarifyResponder:
    """Render validator-driven clarify replies in a more natural tone."""

    def __init__(
        self,
        llm: Any | None = None,
        transcript_builder: TranscriptBuilder | None = None,
        output_parser: StrOutputParser | None = None,
    ) -> None:
        self.llm = llm
        self.transcript_builder = transcript_builder or TranscriptBuilder()
        self.output_parser = output_parser or StrOutputParser()
        self.prompt = load_prompt_template("clarify/rewrite")

    async def respond(
        self,
        message: Message,
        state: DialogueState,
        reason: str | None,
        clarify_target: str | None,
        fallback_message: str | None,
    ) -> list[BotMessage]:
        fallback = (fallback_message or "").strip()
        if not fallback:
            return []

        if self.llm is None:
            return [BotMessage(text=fallback)]

        transcript = self.transcript_builder.build_transcript(
            state.current_session_turns()
        )
        transcript = self.transcript_builder.append_user_message(transcript, message)
        focused_object = state.focused_object
        focused_object_text = None
        if focused_object is not None:
            focused_object_text = (
                f"type={focused_object.type}, id={focused_object.id}, title={focused_object.title}"
            )

        chain = self.prompt | self.llm | self.output_parser
        rewritten = (
            await chain.ainvoke(
                {
                    "reason": reason or "",
                    "clarify_target": clarify_target or "",
                    "fallback_message": fallback,
                    "focused_object": focused_object_text,
                    "history": transcript,
                    "user_message": message.text or "",
                }
            )
        ).strip()
        return [BotMessage(text=rewritten or fallback)]
