import pytest

from langpractice.scenario_gen import generate_persona_card


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.response


# role_identity 是 AI 要演的角色，必须是学习者的对手方（患者），不能是学习者自己的身份
# （护士）——这正是场景生成 prompt 里明确要求避免的撞车 bug，fixture 故意写对以防回归。
_VALID_PAYLOAD = """{
  "role_identity": "一位因为害怕打针而抗拒配合的患者",
  "emotional_state": "紧张、有点抗拒",
  "speaking_style": "简短、带犹豫",
  "hidden_motivation": "其实想尽快结束，但嘴上一直找借口拖延",
  "scenario_description": "患者拒绝打针，你（学习者）是护士，要安抚并完成注射。",
  "difficulty_level": "中级"
}"""


def test_generate_persona_card_parses_valid_payload():
    llm = _FakeLLM(_VALID_PAYLOAD)
    card = generate_persona_card(llm, "我是护士，有患者拒绝打针", "fr")
    assert card.language == "fr"
    assert card.target_language == "French"
    assert card.role_identity == "一位因为害怕打针而抗拒配合的患者"
    assert card.scenario_description.startswith("患者拒绝打针")
    assert card.key.startswith("custom_")


def test_generate_persona_card_key_is_unique_per_call():
    llm = _FakeLLM(_VALID_PAYLOAD)
    card1 = generate_persona_card(llm, "desc", "en")
    card2 = generate_persona_card(llm, "desc", "en")
    assert card1.key != card2.key


def test_generate_persona_card_handles_markdown_fence():
    llm = _FakeLLM(f"```json\n{_VALID_PAYLOAD}\n```")
    card = generate_persona_card(llm, "desc", "en")
    assert card.role_identity == "一位因为害怕打针而抗拒配合的患者"


def test_generate_persona_card_raises_on_missing_field():
    llm = _FakeLLM('{"role_identity": "a"}')
    with pytest.raises(ValueError):
        generate_persona_card(llm, "desc", "en")


def test_generate_persona_card_unknown_language_defaults_to_english():
    llm = _FakeLLM(_VALID_PAYLOAD)
    card = generate_persona_card(llm, "desc", "xx")
    assert card.target_language == "English"
