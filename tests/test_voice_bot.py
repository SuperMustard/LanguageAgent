import pytest

from langpractice import db
from langpractice.voice_bot import _build_transcript, _resolve_scenario


class _FakeRunnerArgs:
    def __init__(self, body):
        self.body = body


class _FakeContext:
    def __init__(self, messages):
        self._messages = messages

    def get_messages(self):
        return self._messages


def test_resolve_scenario_uses_body_scenario_key():
    conn = db.connect(":memory:")  # 播种了 clinic_fr/interview_en，不碰真实数据库文件
    card = _resolve_scenario(conn, _FakeRunnerArgs({"scenario": "interview_en"}))
    assert card.key == "interview_en"
    assert card.language == "en"


def test_resolve_scenario_defaults_to_clinic_fr_when_body_empty():
    conn = db.connect(":memory:")
    card = _resolve_scenario(conn, _FakeRunnerArgs({}))
    assert card.key == "clinic_fr"


def test_resolve_scenario_defaults_when_body_none():
    conn = db.connect(":memory:")
    card = _resolve_scenario(conn, _FakeRunnerArgs(None))
    assert card.key == "clinic_fr"


def test_resolve_scenario_unknown_key_raises():
    conn = db.connect(":memory:")
    with pytest.raises(ValueError):
        _resolve_scenario(conn, _FakeRunnerArgs({"scenario": "does_not_exist"}))


def test_build_transcript_only_includes_user_and_assistant():
    context = _FakeContext(
        [
            {"role": "developer", "content": "system stuff, should not appear"},
            {"role": "assistant", "content": "Bonjour."},
            {"role": "user", "content": "Bonjour, ca va?"},
        ]
    )
    transcript = _build_transcript(context)
    assert transcript == "AI：Bonjour.\n学习者：Bonjour, ca va?"


def test_build_transcript_skips_empty_content():
    context = _FakeContext(
        [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Hello"},
        ]
    )
    assert _build_transcript(context) == "AI：Hello"


def test_build_transcript_empty_when_no_conversation():
    assert _build_transcript(_FakeContext([])) == ""
