from langpractice import db
from langpractice.models import PersonaCard
from langpractice.personas import (
    BUILTIN_SCENARIOS,
    get_scenario,
    list_all_scenario_descriptions,
    render_persona_prompt,
)


def test_render_without_induction_targets_leaves_block_empty():
    card = BUILTIN_SCENARIOS["clinic_fr"]
    prompt = render_persona_prompt(card)
    assert "{{induction_targets}}" not in prompt
    assert "{{induction_block}}" not in prompt
    assert "隐藏引导目标" not in prompt


def test_render_with_induction_targets_injects_hidden_goal_block():
    card = BUILTIN_SCENARIOS["clinic_fr"]
    prompt = render_persona_prompt(card, induction_targets="- 生词「traiter」")
    assert "隐藏引导目标" in prompt
    assert "生词「traiter」" in prompt
    assert "{{induction_targets}}" not in prompt


def test_render_fills_all_scenario_placeholders():
    card = BUILTIN_SCENARIOS["interview_en"]
    prompt = render_persona_prompt(card)
    assert card.role_identity in prompt
    assert card.scenario_description in prompt
    assert "{{" not in prompt


def _custom_card(**overrides):
    base = dict(
        key="custom_xyz",
        language="fr",
        target_language="French",
        role_identity="一位护士",
        emotional_state="耐心但有点忙",
        speaking_style="简洁",
        hidden_motivation="想尽快安抚患者",
        scenario_description="患者拒绝打针。",
        difficulty_level="中级",
    )
    base.update(overrides)
    return PersonaCard(**base)


def test_get_scenario_finds_builtin_without_touching_db():
    conn = db.connect(":memory:")
    card = get_scenario(conn, "clinic_fr")
    assert card is BUILTIN_SCENARIOS["clinic_fr"]


def test_get_scenario_falls_back_to_custom_scenario():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _custom_card())
    card = get_scenario(conn, "custom_xyz")
    assert card is not None
    assert card.role_identity == "一位护士"


def test_get_scenario_unknown_key_returns_none():
    conn = db.connect(":memory:")
    assert get_scenario(conn, "does_not_exist") is None


def test_list_all_scenario_descriptions_merges_builtin_and_custom():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _custom_card())
    descriptions = list_all_scenario_descriptions(conn)
    assert "clinic_fr" in descriptions
    assert "interview_en" in descriptions
    assert descriptions["custom_xyz"] == "患者拒绝打针。"
