import json

from langpractice.mining import (
    clean_meaning,
    parse_sentence_csv,
    parse_vocabulary_csv,
    render_mining_prompt,
    run_mining_triage,
)


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.response


def test_clean_meaning_drops_web_segment_and_keeps_single_pos():
    assert clean_meaning("n. 独处 独居; web. 孤独 寂寞 孤寂  ") == "独处 独居"


def test_clean_meaning_keeps_pos_prefix_when_multiple_segments():
    raw = "n. 过度 超过 过分 过多的量; adj. 超额的 额外的; web. 过量"
    assert clean_meaning(raw) == "n. 过度 超过; adj. 超额的 额外的"


def test_clean_meaning_handles_no_web_segment():
    assert clean_meaning("n. 临床医师; web. 临床医生 临床医学专家 临床家  ") == "临床医师"


def test_clean_meaning_empty_input_returns_empty_string():
    assert clean_meaning("") == ""


def test_parse_vocabulary_csv_basic():
    content = (
        "Word,Phonetic,Translation,Date\n"
        "solitude,/ˈsɑːlətuːd/,n. 独处 独居; web. 孤独 寂寞 孤寂  ,2026-09-01\n"
    ).encode("utf-8")
    rows = parse_vocabulary_csv(content)
    assert rows == [
        {"word": "solitude", "phonetic": "/ˈsɑːlətuːd/", "meaning": "独处 独居"}
    ]


def test_parse_vocabulary_csv_ignores_placeholder_date():
    content = (
        "Word,Phonetic,Translation,Date\n"
        "cannabis,/ˈkænəbɪs/,n. 大麻制品; web. 大麻属,--\n"
    ).encode("utf-8")
    rows = parse_vocabulary_csv(content)
    assert rows[0]["word"] == "cannabis"
    assert "date" not in rows[0]


def test_parse_vocabulary_csv_skips_rows_without_word():
    content = "Word,Phonetic,Translation,Date\n,,,--\n".encode("utf-8")
    assert parse_vocabulary_csv(content) == []


def test_parse_vocabulary_csv_handles_bom():
    content = "﻿Word,Phonetic,Translation,Date\ntherapy,/ˈθerəpi/,n. 治疗 疗法,--\n".encode(
        "utf-8"
    )
    rows = parse_vocabulary_csv(content)
    assert rows[0]["word"] == "therapy"


def test_parse_sentence_csv_basic():
    content = (
        "Sentence,Translation,URL,Date\n"
        "get into your pajamas and go to bed,穿上睡衣去睡觉,https://example.com/v,2026.09.01\n"
    ).encode("utf-8")
    rows = parse_sentence_csv(content)
    assert rows == [
        {
            "sentence": "get into your pajamas and go to bed",
            "translation": "穿上睡衣去睡觉",
            "url": "https://example.com/v",
            "csv_date": "2026.09.01",
        }
    ]


def test_parse_sentence_csv_skips_rows_without_sentence():
    content = "Sentence,Translation,URL,Date\n,,,\n".encode("utf-8")
    assert parse_sentence_csv(content) == []


def test_render_mining_prompt_substitutes_language_label_and_sentences():
    prompt = render_mining_prompt(["I curled up in bed.", "She put it off."], "en")
    assert "英语" in prompt
    assert "1. I curled up in bed." in prompt
    assert "2. She put it off." in prompt
    assert "{{" not in prompt


def test_render_mining_prompt_supports_french():
    prompt = render_mining_prompt(["Bonjour."], "fr")
    assert "法语" in prompt


def test_run_mining_triage_parses_indexed_results():
    response = json.dumps(
        {
            "results": [
                {
                    "index": 1,
                    "words": [{"word": "curl up", "meaning": "蜷缩"}],
                    "collocations": [],
                },
                {
                    "index": 2,
                    "words": [],
                    "collocations": [{"phrase": "put off", "meaning": "推迟", "note": ""}],
                },
            ]
        }
    )
    llm = _FakeLLM(response)
    results = run_mining_triage(llm, ["I curled up in bed.", "She put it off."], "en")
    assert results[1]["words"] == [{"word": "curl up", "meaning": "蜷缩"}]
    assert results[2]["collocations"] == [{"phrase": "put off", "meaning": "推迟", "note": ""}]
    assert len(llm.calls) == 1


def test_run_mining_triage_skips_malformed_index_without_failing_batch():
    response = json.dumps(
        {
            "results": [
                {"index": 1, "words": [{"word": "a", "meaning": "b"}], "collocations": []},
                {"index": "not-a-number", "words": [], "collocations": []},
                {"index": 99, "words": [], "collocations": []},
            ]
        }
    )
    llm = _FakeLLM(response)
    results = run_mining_triage(llm, ["only one sentence."], "en")
    assert list(results.keys()) == [1]


def test_run_mining_triage_strips_json_fence():
    response = '```json\n{"results": [{"index": 1, "words": [], "collocations": []}]}\n```'
    llm = _FakeLLM(response)
    results = run_mining_triage(llm, ["hello."], "en")
    assert 1 in results


def test_run_mining_triage_empty_sentences_returns_empty_without_calling_llm():
    llm = _FakeLLM("{}")
    assert run_mining_triage(llm, [], "en") == {}
    assert llm.calls == []
