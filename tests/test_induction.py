from langpractice import db
from langpractice.induction import (
    InductionTarget,
    apply_mastery_updates,
    format_induction_targets,
    retrieve_induction_targets,
    review_induction_usage,
)
from langpractice.models import Expression, Word


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.response


def _word(**overrides):
    base = dict(word="w", meaning="m", language="fr", mastery=0,
                last_practiced="2026-08-01T00:00:00+00:00")
    base.update(overrides)
    return Word(**base)


def _expr(**overrides):
    base = dict(zh="z", en_wrong="wrong", en_correct="correct", error_note="n", pattern="p",
                language="fr", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")
    base.update(overrides)
    return Expression(**base)


def test_retrieve_returns_empty_when_no_history():
    conn = db.connect(":memory:")
    assert retrieve_induction_targets(conn, "fr") == []


def test_retrieve_filters_by_language():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="bonjour", language="fr")])
    db.insert_words(conn, [_word(word="hello", language="en")])
    targets = retrieve_induction_targets(conn, "fr")
    assert len(targets) == 1
    assert "bonjour" in targets[0].label


def test_retrieve_prefers_oldest_last_practiced_first():
    conn = db.connect(":memory:")
    db.insert_words(conn, [
        _word(word="recent", last_practiced="2026-08-20T00:00:00+00:00"),
        _word(word="stale", last_practiced="2026-08-01T00:00:00+00:00"),
    ])
    targets = retrieve_induction_targets(conn, "fr", limit=1)
    assert len(targets) == 1
    assert "stale" in targets[0].label


def test_retrieve_prefers_lower_mastery_first():
    conn = db.connect(":memory:")
    db.insert_words(conn, [
        _word(word="mastered", mastery=5, last_practiced="2026-08-01T00:00:00+00:00"),
        _word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00"),
    ])
    targets = retrieve_induction_targets(conn, "fr", limit=1)
    assert len(targets) == 1
    assert "weak" in targets[0].label


def test_retrieve_mixes_words_and_expressions():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="bonjour", last_practiced="2026-08-01T00:00:00+00:00")])
    db.insert_expressions(conn, [_expr(en_correct="Je vous comprends",
                                        last_practiced="2026-08-02T00:00:00+00:00")])
    targets = retrieve_induction_targets(conn, "fr", limit=2)
    assert len(targets) == 2
    kinds = {t.kind for t in targets}
    assert kinds == {"word", "expression"}


def test_retrieve_respects_limit():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word=f"w{i}") for i in range(5)])
    assert len(retrieve_induction_targets(conn, "fr", limit=2)) == 2


def test_format_induction_targets_empty_list():
    assert format_induction_targets([]) == ""


def test_format_induction_targets_bullets_each_label():
    targets = [InductionTarget(id=1, kind="word", label="a"), InductionTarget(id=2, kind="word", label="b")]
    assert format_induction_targets(targets) == "- a\n- b"


def test_review_induction_usage_empty_targets_skips_llm_call():
    llm = _FakeLLM("[]")
    assert review_induction_usage(llm, "French", "transcript", []) == {}
    assert llm.calls == []


def test_review_induction_usage_parses_outcomes():
    llm = _FakeLLM('[{"id": 1, "outcome": "used_correctly"}, {"id": 2, "outcome": "not_used"}]')
    targets = [InductionTarget(id=1, kind="word", label="a"), InductionTarget(id=2, kind="expression", label="b")]
    outcomes = review_induction_usage(llm, "French", "transcript", targets)
    assert outcomes == {1: "used_correctly", 2: "not_used"}


def test_review_induction_usage_handles_markdown_fence():
    llm = _FakeLLM('```json\n[{"id": 1, "outcome": "used_incorrectly"}]\n```')
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {1: "used_incorrectly"}


def test_review_induction_usage_malformed_json_returns_empty():
    llm = _FakeLLM("not json at all")
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {}


def test_review_induction_usage_ignores_invalid_outcome_values():
    llm = _FakeLLM('[{"id": 1, "outcome": "maybe"}]')
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {}


def test_apply_mastery_updates_increments_on_correct_use():
    conn = db.connect(":memory:")
    w = _word(mastery=0)
    db.insert_words(conn, [w])
    target = InductionTarget(id=w.id, kind="word", label="w")

    apply_mastery_updates(conn, [target], {w.id: "used_correctly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_words(conn, "fr")[0]
    assert fetched.mastery == 1
    assert fetched.last_practiced == "2026-08-28T00:00:00+00:00"


def test_apply_mastery_updates_decrements_on_incorrect_use_floored_at_zero():
    conn = db.connect(":memory:")
    e = _expr(mastery=0)
    db.insert_expressions(conn, [e])
    target = InductionTarget(id=e.id, kind="expression", label="e")

    apply_mastery_updates(conn, [target], {e.id: "used_incorrectly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_expressions(conn, "fr")[0]
    assert fetched.mastery == 0  # 本来就是 0，-1 被地板卡住


def test_apply_mastery_updates_leaves_not_used_untouched():
    conn = db.connect(":memory:")
    w = _word(mastery=3, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_words(conn, [w])
    target = InductionTarget(id=w.id, kind="word", label="w")

    apply_mastery_updates(conn, [target], {w.id: "not_used"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_words(conn, "fr")[0]
    assert fetched.mastery == 3
    assert fetched.last_practiced == "2026-08-01T00:00:00+00:00"


def test_apply_mastery_updates_skips_targets_with_no_outcome():
    conn = db.connect(":memory:")
    w = _word(mastery=3, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_words(conn, [w])
    target = InductionTarget(id=w.id, kind="word", label="w")

    apply_mastery_updates(conn, [target], {}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_words(conn, "fr")[0]
    assert fetched.mastery == 3
    assert fetched.last_practiced == "2026-08-01T00:00:00+00:00"
