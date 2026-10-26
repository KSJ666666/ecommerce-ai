from typing import Any, Dict

from jinja2 import Template
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.task.actions.base import Action, ActionResult
from app.domain.messages import BotMessage
from app.domain.state import DialogueState
from app.prompts.transcript import TranscriptBuilder


class ActionResponse(Action):
    """内置响应动作：根据 response kwargs 渲染并输出 bot message。"""

    name = "action_response"

    def __init__(
        self,
        *,
        llm: Any | None = None,
        transcript_builder: TranscriptBuilder | None = None,
    ) -> None:
        self.llm = llm
        self.transcript_builder = transcript_builder or TranscriptBuilder()
        self.output_parser = StrOutputParser()

    async def run(self, state: DialogueState, **kwargs: Any) -> ActionResult:
        context = state.current_context_data()
        mode = str(kwargs.get("mode", "static"))
        text = kwargs.get("text")
        prompt_text = kwargs.get("prompt")

        if mode == "static":
            rendered = self._render(text or "", state, context)
            return ActionResult(messages=[BotMessage(text=rendered)])

        if mode == "rephrase":
            rendered = self._render(text or "", state, context)
            result = await self._run_llm(
                prompt_text=prompt_text,
                state=state,
                current_response=rendered,
                fallback_text=rendered,
            )
            return ActionResult(messages=[BotMessage(text=result)])

        if mode == "generate":
            result = await self._run_llm(
                prompt_text=prompt_text,
                state=state,
                current_response="",
                fallback_text="",
            )
            return ActionResult(messages=[BotMessage(text=result)])

        return ActionResult()

    async def _run_llm(
        self,
        *,
        prompt_text: str | None,
        state: DialogueState,
        current_response: str,
        fallback_text: str,
    ) -> str:
        if not prompt_text or self.llm is None:
            return fallback_text

        user_message = ""
        transcript = self.transcript_builder.build_transcript(
            state.current_session_turns()
        )
        pending_turn = state.pending_turn
        if pending_turn is not None:
            transcript = self.transcript_builder.append_user_message(
                transcript, pending_turn.input_message,
            )
            if pending_turn.input_message.text:
                user_message = pending_turn.input_message.text

        prompt = PromptTemplate.from_template(prompt_text)
        prompt_inputs = {
            "history": transcript,
            "current_response": current_response,
            "user_message": user_message,
        }
        chain = prompt | self.llm | self.output_parser
        rewritten = (await chain.ainvoke(prompt_inputs)).strip()
        return rewritten or fallback_text or current_response

    @staticmethod
    def _render(template: str, state: DialogueState, context: Dict[str, Any]) -> str:
        return str(Template(template).render(slots=state.visible_slots(), context=context))
