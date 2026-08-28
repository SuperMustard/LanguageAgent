"""接 Groq Llama 的真实实现，符合 LLMClient 接口，跟 MockLLMClient 可无缝互换。"""

from groq import Groq

from .base import Message


class GroqLLMClient:
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b") -> None:
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY 未设置：在项目根目录的 .env 里填入你的 key（见 .env.example）"
            )
        self._client = Groq(api_key=api_key)
        self._model = model

    def chat(self, messages: list[Message]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return response.choices[0].message.content
