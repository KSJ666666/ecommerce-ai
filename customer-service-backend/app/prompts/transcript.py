from dataclasses import dataclass
from typing import List, Optional

from app.domain.messages import Message, MessageObject, MessageType
from app.domain.state import Turn


@dataclass(slots=True)
class TranscriptLine:
    speaker: str
    text: str

    def render(self) -> str:
        return f"{self.speaker}: {self.text}"


class TranscriptBuilder:
    """Build LLM-facing transcript from completed turns."""

    USER_PREFIX = "USER"
    AI_PREFIX = "AI"

    def build_transcript(self, turns: List[Turn]) -> str:
        lines: List[TranscriptLine] = []
        for turn in turns:
            user_line = self._user_message_line(turn.input_message)
            if user_line is not None:
                lines.append(user_line)
            for bot_message in turn.assistant_messages:
                if bot_message.text:
                    lines.append(
                        TranscriptLine(self.AI_PREFIX, self._sanitize(bot_message.text))
                    )
        return "\n".join(line.render() for line in lines)

    def append_user_message(
        self, transcript: str, message: Message, prefix: Optional[str] = None
    ) -> str:
        line = self._user_message_line(message, prefix=prefix)
        if line is None:
            return transcript
        if not transcript:
            return line.render()
        return f"{transcript}\n{line.render()}"

    def _user_message_line(
        self,
        message: Message,
        prefix: Optional[str] = None,
    ) -> Optional[TranscriptLine]:
        if message.type is MessageType.TEXT and message.text:
            return TranscriptLine(prefix or self.USER_PREFIX, self._sanitize(message.text))
        if message.type is MessageType.OBJECT and message.object is not None:
            return TranscriptLine(
                prefix or self.USER_PREFIX,
                self._sanitize(self._render_object_message(message.object)),
            )
        return None

    @staticmethod
    def _render_object_message(message_object: MessageObject) -> str:
        object_type = message_object.type.strip() or "object"
        label = "订单对象" if object_type == "order" else "商品对象" if object_type == "product" else "对象"
        parts = [f"[{label}]", f"id={message_object.id}"]
        if message_object.title:
            parts.append(f"title={message_object.title}")
        for key, value in list(message_object.attributes.items())[:3]:
            parts.append(f"{key}={value}")
        return ", ".join(parts)

    @staticmethod
    def _sanitize(text: str) -> str:
        return text.replace("\n", " ").strip()
