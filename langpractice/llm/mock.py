"""离线可用的占位 LLM：角色扮演返回预设台词轮换，Debrief 返回固定示例 JSON。
用来在接入 Groq 之前验证 演练 -> 结束 -> Debrief -> 存库 -> 导出 的完整数据流。
接入真实模型时只需在别处换成 GroqLLMClient，调用方代码不用改（见 llm/base.py 的 LLMClient 接口）。
"""

from .base import Message

_DEBRIEF_MARKER = "严格输出一个 JSON 对象"

_PERSONA_FILLERS = {
    "fr": [
        "Hmpf... d'accord. Et vous comptez faire quoi, alors ?",
        "Bon. J'espere que ca ne va pas prendre trop longtemps.",
        "Ah bon ? Continuez, je vous ecoute.",
        "Tres bien. On verra si ca marche vraiment.",
    ],
    "en": [
        "I see. Can you walk me through that a bit more?",
        "Interesting — what made you choose that approach?",
        "Okay, noted. What else should I know?",
        "Alright, let's move on to the next point then.",
    ],
}

MOCK_DEBRIEF_JSON = """{
  "sentences": [
    {
      "zh": "我今天很累，因为昨晚没睡好。",
      "en_wrong": "I very tired today because last night sleep not good.",
      "en_correct": "I'm really tired today because I didn't sleep well last night.",
      "error_note": "中文形容词可以直接做谓语（\\"我很累\\"），但英语必须用 be 动词；中文常省略助动词，导致漏掉 didn't。",
      "pattern": "系动词缺失 / 中式直译"
    }
  ],
  "words": [
    {"word": "exhausted", "meaning": "筋疲力尽的"}
  ]
}"""


class MockLLMClient:
    def chat(self, messages: list[Message]) -> str:
        system = next((m.content for m in messages if m.role == "system"), "")
        if _DEBRIEF_MARKER in system:
            return MOCK_DEBRIEF_JSON

        lang = "fr" if "French" in system else "en"
        fillers = _PERSONA_FILLERS[lang]
        turn = sum(1 for m in messages if m.role == "assistant")
        return fillers[turn % len(fillers)]
