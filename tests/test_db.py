from langpractice import db
from langpractice.models import Expression, Word


def test_insert_and_fetch_expressions_roundtrip():
    conn = db.connect(":memory:")
    expr = Expression(
        zh="我今天很累。",
        en_wrong="I very tired today.",
        en_correct="I'm very tired today.",
        error_note="缺系动词。",
        pattern="系动词缺失",
        language="en",
        mastery=0,
        last_practiced="2026-08-28T00:00:00+00:00",
    )
    db.insert_expressions(conn, [expr])

    fetched = db.fetch_expressions(conn, "en")
    assert len(fetched) == 1
    assert fetched[0].zh == expr.zh
    assert fetched[0].id is not None

    assert db.fetch_expressions(conn, "fr") == []


def test_insert_and_fetch_words_roundtrip():
    conn = db.connect(":memory:")
    word = Word(word="exhausted", meaning="筋疲力尽的", language="en", mastery=0,
                last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_words(conn, [word])

    fetched = db.fetch_words(conn, "en")
    assert len(fetched) == 1
    assert fetched[0].word == "exhausted"
    assert fetched[0].meaning == "筋疲力尽的"


def test_fetch_filters_by_language():
    conn = db.connect(":memory:")
    db.insert_expressions(conn, [
        Expression(zh="a", en_wrong="a", en_correct="a", error_note="a", pattern="a",
                   language="en", last_practiced="2026-08-28T00:00:00+00:00"),
        Expression(zh="b", en_wrong="b", en_correct="b", error_note="b", pattern="b",
                   language="fr", last_practiced="2026-08-28T00:00:00+00:00"),
    ])
    assert len(db.fetch_expressions(conn, "en")) == 1
    assert len(db.fetch_expressions(conn, "fr")) == 1


def test_insert_expressions_sets_id_on_each_object():
    conn = db.connect(":memory:")
    e1 = Expression(zh="a", en_wrong="a", en_correct="a", error_note="a", pattern="a",
                     language="en", last_practiced="2026-08-28T00:00:00+00:00")
    e2 = Expression(zh="b", en_wrong="b", en_correct="b", error_note="b", pattern="b",
                     language="en", last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_expressions(conn, [e1, e2])
    assert e1.id is not None
    assert e2.id is not None
    assert e1.id != e2.id


def test_insert_words_sets_id_on_each_object():
    conn = db.connect(":memory:")
    w = Word(word="exhausted", meaning="筋疲力尽的", language="en", mastery=0,
             last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_words(conn, [w])
    assert w.id is not None


def test_delete_expression_removes_row_and_reports_success():
    conn = db.connect(":memory:")
    e = Expression(zh="a", en_wrong="a", en_correct="a", error_note="a", pattern="a",
                    language="en", last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_expressions(conn, [e])

    assert db.delete_expression(conn, e.id) is True
    assert db.fetch_expressions(conn, "en") == []


def test_delete_expression_missing_id_returns_false():
    conn = db.connect(":memory:")
    assert db.delete_expression(conn, 9999) is False


def test_delete_word_removes_row_and_reports_success():
    conn = db.connect(":memory:")
    w = Word(word="exhausted", meaning="筋疲力尽的", language="en", mastery=0,
             last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_words(conn, [w])

    assert db.delete_word(conn, w.id) is True
    assert db.fetch_words(conn, "en") == []


def test_delete_word_missing_id_returns_false():
    conn = db.connect(":memory:")
    assert db.delete_word(conn, 9999) is False
