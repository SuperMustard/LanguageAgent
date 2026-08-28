import pytest

from langpractice.debrief import _strip_json_fence, parse_debrief_payload


def test_parse_debrief_payload_fills_internal_fields():
    payload = {
        "sentences": [
            {
                "zh": "我今天很累。",
                "en_wrong": "I very tired today.",
                "en_correct": "I'm very tired today.",
                "error_note": "缺系动词。",
                "pattern": "系动词缺失",
            }
        ],
        "words": [{"word": "exhausted", "meaning": "筋疲力尽的"}],
    }
    result = parse_debrief_payload(payload, language_code="en", now_iso="2026-08-28T00:00:00+00:00")

    assert len(result.sentences) == 1
    expr = result.sentences[0]
    assert expr.zh == "我今天很累。"
    assert expr.language == "en"
    assert expr.mastery == 0
    assert expr.last_practiced == "2026-08-28T00:00:00+00:00"

    assert len(result.words) == 1
    word = result.words[0]
    assert word.word == "exhausted"
    assert word.meaning == "筋疲力尽的"
    assert word.language == "en"
    assert word.mastery == 0


def test_parse_debrief_payload_word_meaning_optional():
    payload = {"sentences": [], "words": [{"word": "empathie"}]}
    result = parse_debrief_payload(payload, language_code="fr", now_iso="2026-08-28T00:00:00+00:00")
    assert result.words[0].meaning == ""


def test_parse_debrief_payload_empty_arrays_when_no_errors():
    payload = {"sentences": [], "words": []}
    result = parse_debrief_payload(payload, language_code="fr", now_iso="2026-08-28T00:00:00+00:00")
    assert result.sentences == []
    assert result.words == []


def test_parse_debrief_payload_missing_required_field_raises():
    payload = {"sentences": [{"zh": "只有 zh"}], "words": []}
    with pytest.raises(KeyError):
        parse_debrief_payload(payload, language_code="fr", now_iso="2026-08-28T00:00:00+00:00")


def test_strip_json_fence_plain_json_passthrough():
    raw = '{"sentences": [], "words": []}'
    assert _strip_json_fence(raw) == raw


def test_strip_json_fence_removes_markdown_fence():
    raw = '```json\n{"sentences": [], "words": []}\n```'
    assert _strip_json_fence(raw) == '{"sentences": [], "words": []}'
