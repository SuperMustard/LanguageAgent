from langpractice import db
from langpractice.models import Expression, PersonaCard, ProPhrase, Word


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


def test_insert_and_fetch_pro_phrases_roundtrip():
    conn = db.connect(":memory:")
    phrase = ProPhrase(
        phrase="Je comprends que ce soit frustrant, laissez-moi voir ce qu'on peut faire.",
        meaning="我理解这确实让人沮丧，让我看看能做些什么。",
        dimension="同理承接",
        usage_note="先接住情绪，再引导到解决方案。",
        language="fr",
        scenario_type="clinic_fr",
        mastery=0,
        last_practiced="2026-08-28T00:00:00+00:00",
    )
    db.insert_pro_phrases(conn, [phrase])

    fetched = db.fetch_pro_phrases(conn, "fr")
    assert len(fetched) == 1
    assert fetched[0].phrase == phrase.phrase
    assert fetched[0].scenario_type == "clinic_fr"
    assert fetched[0].id is not None

    assert db.fetch_pro_phrases(conn, "en") == []


def test_insert_pro_phrases_sets_id_on_each_object():
    conn = db.connect(":memory:")
    p1 = ProPhrase(phrase="a", meaning="a", dimension="设立边界", usage_note="a",
                    language="en", scenario_type="clinic_fr",
                    last_practiced="2026-08-28T00:00:00+00:00")
    p2 = ProPhrase(phrase="b", meaning="b", dimension="设立边界", usage_note="b",
                    language="en", scenario_type="clinic_fr",
                    last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_pro_phrases(conn, [p1, p2])
    assert p1.id is not None
    assert p2.id is not None
    assert p1.id != p2.id


def test_delete_pro_phrase_removes_row_and_reports_success():
    conn = db.connect(":memory:")
    p = ProPhrase(phrase="a", meaning="a", dimension="设立边界", usage_note="a",
                  language="en", scenario_type="clinic_fr",
                  last_practiced="2026-08-28T00:00:00+00:00")
    db.insert_pro_phrases(conn, [p])

    assert db.delete_pro_phrase(conn, p.id) is True
    assert db.fetch_pro_phrases(conn, "en") == []


def test_delete_pro_phrase_missing_id_returns_false():
    conn = db.connect(":memory:")
    assert db.delete_pro_phrase(conn, 9999) is False


def _scenario_card(**overrides):
    base = dict(
        key="custom_abc123",
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


def test_insert_and_fetch_scenario_roundtrip():
    conn = db.connect(":memory:")
    card = _scenario_card()
    db.insert_scenario(conn, card)

    fetched = db.fetch_scenario(conn, "custom_abc123")
    assert fetched is not None
    assert fetched.key == card.key
    assert fetched.role_identity == card.role_identity
    assert fetched.scenario_description == card.scenario_description


def test_fetch_scenario_missing_key_returns_none():
    conn = db.connect(":memory:")
    assert db.fetch_scenario(conn, "does_not_exist") is None


def test_fetch_all_scenarios_returns_every_row():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _scenario_card(key="custom_a"))
    db.insert_scenario(conn, _scenario_card(key="custom_b"))
    scenarios = db.fetch_all_scenarios(conn)
    # 种子场景（clinic_fr/interview_en）在 connect() 时已经播种了，这里只断言
    # 新插入的两条也在，不断言总数——种子场景不是这个测试关心的事。
    assert {"custom_a", "custom_b"} <= {s.key for s in scenarios}


def test_delete_scenario_removes_row_and_reports_success():
    conn = db.connect(":memory:")
    db.insert_scenario(conn, _scenario_card(key="custom_a"))
    assert db.delete_scenario(conn, "custom_a") is True
    assert db.fetch_scenario(conn, "custom_a") is None


def test_delete_scenario_missing_key_returns_false():
    conn = db.connect(":memory:")
    assert db.delete_scenario(conn, "nope") is False


def test_connect_seeds_scenarios_on_fresh_db():
    conn = db.connect(":memory:")
    keys = {s.key for s in db.fetch_all_scenarios(conn)}
    assert {"clinic_fr", "interview_en"} <= keys


def test_seeded_scenarios_are_ordinary_rows_deletable_like_any_other():
    # 没有"内置场景删不掉"这种特殊保护——用户明确说了不需要区分。
    conn = db.connect(":memory:")
    assert db.delete_scenario(conn, "clinic_fr") is True
    assert db.fetch_scenario(conn, "clinic_fr") is None


def test_connect_does_not_reseed_once_scenarios_table_is_non_empty():
    # 场景表非空时不会再播种——不然删了种子场景，下次 connect() 又会把它复活。
    # sqlite3 的 ":memory:" 每次 connect() 都是全新数据库，这里用同一个 conn 手动模拟
    # "表非空后再跑一次播种逻辑"，确认它是幂等的、不会重复插入。
    conn = db.connect(":memory:")
    db.delete_scenario(conn, "clinic_fr")
    remaining_before = len(db.fetch_all_scenarios(conn))

    db._seed_scenarios_if_empty(conn)  # 模拟同一个数据库文件上的下一次 connect()

    remaining_after = len(db.fetch_all_scenarios(conn))
    assert remaining_after == remaining_before
    assert db.fetch_scenario(conn, "clinic_fr") is None
