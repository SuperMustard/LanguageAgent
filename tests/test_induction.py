from langpractice import db
from langpractice.induction import format_induction_targets, retrieve_induction_targets
from langpractice.models import Expression, Word


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
    assert "bonjour" in targets[0]


def test_retrieve_prefers_oldest_last_practiced_first():
    conn = db.connect(":memory:")
    db.insert_words(conn, [
        _word(word="recent", last_practiced="2026-08-20T00:00:00+00:00"),
        _word(word="stale", last_practiced="2026-08-01T00:00:00+00:00"),
    ])
    targets = retrieve_induction_targets(conn, "fr", limit=1)
    assert len(targets) == 1
    assert "stale" in targets[0]


def test_retrieve_prefers_lower_mastery_first():
    conn = db.connect(":memory:")
    db.insert_words(conn, [
        _word(word="mastered", mastery=5, last_practiced="2026-08-01T00:00:00+00:00"),
        _word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00"),
    ])
    targets = retrieve_induction_targets(conn, "fr", limit=1)
    assert len(targets) == 1
    assert "weak" in targets[0]


def test_retrieve_mixes_words_and_expressions():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="bonjour", last_practiced="2026-08-01T00:00:00+00:00")])
    db.insert_expressions(conn, [_expr(en_correct="Je vous comprends",
                                        last_practiced="2026-08-02T00:00:00+00:00")])
    targets = retrieve_induction_targets(conn, "fr", limit=2)
    assert len(targets) == 2
    assert any("bonjour" in t for t in targets)
    assert any("Je vous comprends" in t for t in targets)


def test_retrieve_respects_limit():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word=f"w{i}") for i in range(5)])
    assert len(retrieve_induction_targets(conn, "fr", limit=2)) == 2


def test_format_induction_targets_empty_list():
    assert format_induction_targets([]) == ""


def test_format_induction_targets_bullets_each_line():
    result = format_induction_targets(["a", "b"])
    assert result == "- a\n- b"
