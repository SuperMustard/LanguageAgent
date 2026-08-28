from dataclasses import dataclass
from typing import Protocol


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient(Protocol):
    """统一接口，角色扮演和 Debrief 都通过它调用模型。换实现（Mock -> Groq）不改调用方代码。"""

    def chat(self, messages: list[Message]) -> str:
        ...
