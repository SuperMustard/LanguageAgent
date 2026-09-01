import json

from langpractice.export import expressions_to_json, pro_phrases_to_json, words_to_txt
from langpractice.models import Expression, ProPhrase, Word


def _expr(**overrides) -> Expression:
    base = dict(
        zh="我今天很累。",
        en_wrong="I very tired today.",
        en_correct="I'm very tired today.",
        error_note="缺系动词。",
        pattern="系动词缺失",
        language="en",
        mastery=3,
        last_practiced="2026-08-20T10:00:00+00:00",
    )
    base.update(overrides)
    return Expression(**base)


def _word(**overrides) -> Word:
    base = dict(word="exhausted", meaning="筋疲力尽的", language="en", mastery=1,
                last_practiced="2026-08-20T10:00:00+00:00")
    base.update(overrides)
    return Word(**base)


def _phrase(**overrides) -> ProPhrase:
    base = dict(
        phrase="Je comprends que ce soit frustrant, laissez-moi vous aider.",
        meaning="我理解这令人沮丧，让我来帮您。",
        dimension="同理承接",
        usage_note="先接住情绪，再切入解决方案。",
        language="fr",
        scenario_type="clinic_fr",
        mastery=2,
        last_practiced="2026-08-20T10:00:00+00:00",
    )
    base.update(overrides)
    return ProPhrase(**base)


def test_expressions_to_json_has_exactly_five_fields():
    data = json.loads(expressions_to_json([_expr()]))
    assert len(data) == 1
    record = data[0]
    assert set(record.keys()) == {"zh", "en_wrong", "en_correct", "error_note", "pattern"}


def test_expressions_to_json_strips_internal_fields():
    data = json.loads(expressions_to_json([_expr()]))
    record = data[0]
    assert "language" not in record
    assert "mastery" not in record
    assert "last_practiced" not in record


def test_expressions_to_json_field_values_exact():
    data = json.loads(expressions_to_json([_expr()]))
    record = data[0]
    assert record["zh"] == "我今天很累。"
    assert record["en_wrong"] == "I very tired today."
    assert record["en_correct"] == "I'm very tired today."
    assert record["error_note"] == "缺系动词。"
    assert record["pattern"] == "系动词缺失"


def test_expressions_to_json_empty_list():
    assert json.loads(expressions_to_json([])) == []


def test_words_to_txt_format_with_meaning():
    text = words_to_txt([_word(word="exhausted", meaning="筋疲力尽的")])
    assert text == "exhausted|筋疲力尽的\n"


def test_words_to_txt_format_without_meaning():
    text = words_to_txt([_word(word="empathie", meaning="")])
    assert text == "empathie\n"


def test_words_to_txt_dedup_case_insensitive():
    words = [
        _word(word="Resilient", meaning="有韧性的"),
        _word(word="resilient", meaning="有韧性的（重复）"),
    ]
    text = words_to_txt(words)
    lines = text.splitlines()
    assert len(lines) == 1
    assert lines[0] == "Resilient|有韧性的"  # 保留第一次出现的写法


def test_words_to_txt_empty_list():
    assert words_to_txt([]) == ""


def test_langhelper_collection_condition_zh_or_en_wrong_present():
    # 模拟 langhelper parse_sentences 的硬性收录条件：至少要有 zh 或 en_wrong
    data = json.loads(expressions_to_json([_expr()]))
    for record in data:
        assert record["zh"] or record["en_wrong"]


def test_pro_phrases_to_json_has_exactly_three_fields():
    data = json.loads(pro_phrases_to_json([_phrase()]))
    assert len(data) == 1
    assert set(data[0].keys()) == {"phrase", "meaning", "note"}


def test_pro_phrases_to_json_strips_internal_fields_and_downgrades_usage_note():
    data = json.loads(pro_phrases_to_json([_phrase()]))
    record = data[0]
    assert record["phrase"] == "Je comprends que ce soit frustrant, laissez-moi vous aider."
    assert record["meaning"] == "我理解这令人沮丧，让我来帮您。"
    assert record["note"] == "先接住情绪，再切入解决方案。"
    assert "dimension" not in record
    assert "scenario_type" not in record
    assert "language" not in record
    assert "mastery" not in record
    assert "last_practiced" not in record


def test_pro_phrases_to_json_dedup_case_insensitive():
    phrases = [
        _phrase(phrase="Vous comprenez", dimension="同理承接"),
        _phrase(phrase="vous comprenez", dimension="设立边界"),
    ]
    data = json.loads(pro_phrases_to_json(phrases))
    assert len(data) == 1
    assert data[0]["phrase"] == "Vous comprenez"  # 保留第一次出现的写法


def test_pro_phrases_to_json_empty_list():
    assert json.loads(pro_phrases_to_json([])) == []
