import uuid
from dataclasses import dataclass, field

from .llm.base import LLMClient, Message
from .personas import PersonaCard, render_persona_prompt


@dataclass
class PracticeSession:
    """一场演练的运行时状态。铁律：turn() 只做角色扮演，绝不纠错——纠错在 debrief.py 里单独发生。"""

    id: str
    card: PersonaCard
    llm: LLMClient
    history: list[Message] = field(default_factory=list)

    @classmethod
    def start(cls, card: PersonaCard, llm: LLMClient) -> "PracticeSession":
        session = cls(id=str(uuid.uuid4()), card=card, llm=llm)
        session.history.append(Message(role="system", content=render_persona_prompt(card)))
        opening = llm.chat(session.history)
        session.history.append(Message(role="assistant", content=opening))
        return session

    @property
    def opening_line(self) -> str:
        for m in self.history:
            if m.role == "assistant":
                return m.content
        return ""

    def turn(self, user_text: str) -> str:
        self.history.append(Message(role="user", content=user_text))
        reply = self.llm.chat(self.history)
        self.history.append(Message(role="assistant", content=reply))
        return reply

    def transcript_text(self) -> str:
        speaker_names = {"assistant": "AI", "user": "学习者"}
        lines = [
            f"{speaker_names[m.role]}：{m.content}"
            for m in self.history
            if m.role in speaker_names
        ]
        return "\n".join(lines)
