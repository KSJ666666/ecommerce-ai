from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class MessageType(str, Enum):
    """继承 str 是为了 JSON 序列化时直接得到 "text"/"object"，而不是 "<MessageType.TEXT: 'text'>"。"""

    TEXT = "text"
    OBJECT = "object"


@dataclass(slots=True)
class MessageObject:
    """结构化对象：用户点选的订单卡片 / 商品卡片。"""

    type: str
    id: str
    title: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "title": self.title,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageObject":
        return cls(
            type=data["type"],
            id=data["id"],
            title=data.get("title", ""),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass(slots=True)
class Message:
    """用户发来的一条消息。text 与 object 二选一。"""

    message_id: str
    sender_id: str
    type: MessageType
    text: str | None = None
    object: MessageObject | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "type": self.type.value,   # 枚举必须取 .value 才能落成字符串
            "text": self.text,
            "object": self.object.to_dict() if self.object is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        raw_object = data.get("object")
        return cls(
            message_id=data["message_id"],
            sender_id=data["sender_id"],
            type=MessageType(data["type"]),   # 字符串还原成枚举
            text=data.get("text"),
            object=MessageObject.from_dict(raw_object) if raw_object is not None else None,
        )


@dataclass(slots=True)
class BotMessage:
    """机器人回复的一条消息。"""

    text: str | None = None
    object: MessageObject | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "object": self.object.to_dict() if self.object is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotMessage":
        raw_object = data.get("object")
        return cls(
            text=data.get("text"),
            object=MessageObject.from_dict(raw_object) if raw_object is not None else None,
        )


@dataclass(slots=True)
class ProcessResult:
    """一轮对话的处理结果，可能包含多条机器人消息。"""

    sender_id: str
    message_id: str
    messages: List[BotMessage] = field(default_factory=list)


# day02 时这个类叫 UserMessage，保留别名，避免旧代码 import 失败
UserMessage = Message
