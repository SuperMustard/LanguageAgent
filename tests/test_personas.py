from langpractice.personas import BUILTIN_SCENARIOS, render_persona_prompt


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
