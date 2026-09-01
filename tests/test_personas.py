from langpractice import db
from langpractice.models import PersonaCard
from langpractice.personas import get_scenario, list_all_scenario_descriptions, render_persona_prompt


def _card(**overrides):
    base = dict(
        key="clinic_fr",
        language="fr",
        target_language="French",
        role_identity="一位来做按摩治疗的客人，今天诸事不顺",
        emotional_state="烦躁、有点不耐烦",
        speaking_style="简短、带情绪",
        hidden_motivation="其实想放松，但嘴上不饶人",
        scenario_description="客人刚进诊所，一肚子气。",
        difficulty_level="中级",
    )
    base.update(overrides)
    return PersonaCard(**base)


def test_render_without_induction_targets_leaves_block_empty():
    prompt = render_persona_prompt(_card())
    assert "{{induction_targets}}" not in prompt
    assert "{{induction_block}}" not in prompt
    assert "隐藏引导目标" not in prompt


def test_render_with_induction_targets_injects_hidden_goal_block():
    prompt = render_persona_prompt(_card(), induction_targets="- 生词「traiter」")
    assert "隐藏引导目标" in prompt
    assert "生词「traiter」" in prompt
    assert "{{induction_targets}}" not in prompt


def test_render_uses_card_default_hostility_level_when_not_overridden():
    card = _card(hostility_level="难缠")
    prompt = render_persona_prompt(card)
    assert "难缠" in prompt


def test_render_overrides_hostility_level_when_given():
    card = _card(hostility_level="温和")
    prompt = render_persona_prompt(card, hostility_level="极难缠")
    assert "极难缠" in prompt


def test_render_always_includes_hostility_red_line():
    # 红线是写死在模板里的固定文字，不管难缠程度传什么档位都应该出现。
    prompt = render_persona_prompt(_card(hostility_level="极难缠"))
    assert "难缠红线" in prompt
    assert "人身攻击" in prompt


def test_render_fills_all_scenario_placeholders():
    card = _card(
        key="interview_en",
        language="en",
        target_language="English",
        role_identity="一位招聘经理",
        scenario_description="一场30分钟的岗位面试。",
    )
    prompt = render_persona_prompt(card)
    assert card.role_identity in prompt
    assert card.scenario_description in prompt
    assert "{{" not in prompt


def test_get_scenario_finds_seeded_scenario():
    # db.connect() 在 scenarios 表首次为空时会播种 clinic_fr/interview_en。
    conn = db.connect(":memory:")
    card = get_scenario(conn, "clinic_fr")
    assert card is not None
    assert card.key == "clinic_fr"


def test_get_scenario_finds_custom_scenario_the_same_way():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _card(key="custom_xyz", role_identity="一位护士"))
    card = get_scenario(conn, "custom_xyz")
    assert card is not None
    assert card.role_identity == "一位护士"


def test_get_scenario_unknown_key_returns_none():
    conn = db.connect(":memory:")
    assert get_scenario(conn, "does_not_exist") is None


def test_list_all_scenario_descriptions_includes_seeded_and_custom():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _card(key="custom_xyz", scenario_description="患者拒绝打针。"))
    descriptions = list_all_scenario_descriptions(conn)
    assert "clinic_fr" in descriptions
    assert "interview_en" in descriptions
    assert descriptions["custom_xyz"] == "患者拒绝打针。"
