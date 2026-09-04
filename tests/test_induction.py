from langpractice import db
from langpractice.induction import (
    InductionTarget,
    apply_mastery_updates,
    format_induction_targets,
    retrieve_induction_targets,
    retrieve_today_collocations,
    review_induction_usage,
)
from langpractice.models import Collocation, Expression, ProPhrase, Word


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


def _phrase(**overrides):
    base = dict(phrase="ph", meaning="m", dimension="同理承接", usage_note="n",
                language="fr", scenario_type="clinic_fr", mastery=0,
                last_practiced="2026-08-01T00:00:00+00:00")
    base.update(overrides)
    return ProPhrase(**base)


def _collocation(**overrides):
    base = dict(phrase="c", meaning="m", note="n", language="fr", source="mining",
                mastery=0, last_practiced="2026-08-01T00:00:00+00:00")
    base.update(overrides)
    return Collocation(**base)


def _set_created_at(conn, collocation_id, created_at):
    conn.execute("UPDATE collocations SET created_at = ? WHERE id = ?", (created_at, collocation_id))
    conn.commit()


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


def test_retrieve_includes_pro_phrases_as_a_third_source():
    conn = db.connect(":memory:")
    db.insert_pro_phrases(conn, [_phrase(phrase="Je comprends votre frustration")])
    targets = retrieve_induction_targets(conn, "fr", limit=1, min_phrases=1)
    assert len(targets) == 1
    assert targets[0].kind == "pro_phrase"
    assert "Je comprends votre frustration" in targets[0].label


def test_retrieve_guarantees_min_phrases_even_when_words_have_lower_mastery():
    conn = db.connect(":memory:")
    # 生词掌握度更低（更该被诱导），但保底配额要求至少 1 个名额必须给话术。
    db.insert_words(conn, [_word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")])
    db.insert_pro_phrases(conn, [_phrase(mastery=5, last_practiced="2026-08-01T00:00:00+00:00")])

    targets = retrieve_induction_targets(conn, "fr", limit=1, min_phrases=1)

    assert len(targets) == 1
    assert targets[0].kind == "pro_phrase"


def test_retrieve_fills_remaining_slots_from_mixed_pool_after_guarantee():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")])
    db.insert_pro_phrases(conn, [_phrase(mastery=0, last_practiced="2026-08-01T00:00:00+00:00")])

    targets = retrieve_induction_targets(conn, "fr", limit=2, min_phrases=1)

    assert len(targets) == 2
    kinds = {t.kind for t in targets}
    assert kinds == {"word", "pro_phrase"}


def test_retrieve_gracefully_degrades_when_no_phrases_exist():
    # min_phrases 配额没有话术池可用时，名额自然让给生词/病句，不报错、不留空位。
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word=f"w{i}") for i in range(3)])
    targets = retrieve_induction_targets(conn, "fr", limit=2, min_phrases=1)
    assert len(targets) == 2
    assert all(t.kind == "word" for t in targets)


def test_retrieve_does_not_exceed_limit_even_with_abundant_phrases():
    conn = db.connect(":memory:")
    db.insert_pro_phrases(conn, [_phrase(phrase=f"p{i}") for i in range(5)])
    targets = retrieve_induction_targets(conn, "fr", limit=2, min_phrases=1)
    assert len(targets) == 2


def test_retrieve_includes_collocations_as_a_fourth_source():
    conn = db.connect(":memory:")
    c = _collocation(phrase="curl up")
    db.insert_collocations(conn, [c])
    _set_created_at(conn, c.id, "2026-08-01 00:00:00")  # 不是今天，走常规配比池

    targets = retrieve_induction_targets(conn, "fr", limit=1, min_collocations=1)
    assert len(targets) == 1
    assert targets[0].kind == "collocation"
    assert "curl up" in targets[0].label


def test_retrieve_guarantees_min_collocations_even_when_words_have_lower_mastery():
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")])
    c = _collocation(mastery=5, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_collocations(conn, [c])
    _set_created_at(conn, c.id, "2026-08-01 00:00:00")

    targets = retrieve_induction_targets(conn, "fr", limit=1, min_collocations=1)

    assert len(targets) == 1
    assert targets[0].kind == "collocation"


def test_retrieve_min_collocations_defaults_to_zero():
    # config.INDUCTION_MIN_COLLOCATIONS 默认 0——不设保底时 collocation 走跟生词/病句
    # 一样的混合池竞争，不会因为默认参数意外抢占名额。
    conn = db.connect(":memory:")
    db.insert_words(conn, [_word(word="weak", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")])
    c = _collocation(mastery=5, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_collocations(conn, [c])
    _set_created_at(conn, c.id, "2026-08-01 00:00:00")

    targets = retrieve_induction_targets(conn, "fr", limit=1)

    assert len(targets) == 1
    assert targets[0].kind == "word"  # mastery 更低，混合池里赢过掌握度 5 的语块


def test_retrieve_today_collocations_returns_fresh_mastery_zero_rows():
    conn = db.connect(":memory:")
    c = _collocation(phrase="fresh one", mastery=0, last_practiced="")
    db.insert_collocations(conn, [c])  # 默认 created_at = 今天

    targets = retrieve_today_collocations(conn, "fr")
    assert len(targets) == 1
    assert targets[0].kind == "collocation"
    assert "fresh one" in targets[0].label


def test_retrieve_today_collocations_excludes_already_practiced():
    conn = db.connect(":memory:")
    c = _collocation(phrase="already touched", mastery=0, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_collocations(conn, [c])
    assert retrieve_today_collocations(conn, "fr") == []


def test_retrieve_today_collocations_excludes_old_created_at():
    conn = db.connect(":memory:")
    c = _collocation(phrase="old one", mastery=0, last_practiced="")
    db.insert_collocations(conn, [c])
    _set_created_at(conn, c.id, "2026-08-01 00:00:00")
    assert retrieve_today_collocations(conn, "fr") == []


def test_today_channel_collocations_are_excluded_from_regular_quota_pool():
    # 今天新入库、mastery=0、从没被诱导过的 collocation 应该只走今日通道，不该在
    # retrieve_induction_targets 的常规配比池里重复出现（否则同一条被抽两次）。
    conn = db.connect(":memory:")
    c = _collocation(phrase="fresh today", mastery=0, last_practiced="")
    db.insert_collocations(conn, [c])  # 默认 created_at = 今天

    regular = retrieve_induction_targets(conn, "fr", limit=5, min_collocations=5)
    assert all(t.kind != "collocation" for t in regular)

    today = retrieve_today_collocations(conn, "fr")
    assert len(today) == 1
    assert today[0].id == c.id


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
    # 返回的 key 是 targets 列表里的位置（0-based），不是 InductionTarget.id——
    # 见 induction.py 里的说明：三张表的 id 各自从 1 自增，用 db id 当 key 会撞号。
    llm = _FakeLLM('[{"id": 0, "outcome": "used_correctly"}, {"id": 1, "outcome": "not_used"}]')
    targets = [InductionTarget(id=1, kind="word", label="a"), InductionTarget(id=2, kind="expression", label="b")]
    outcomes = review_induction_usage(llm, "French", "transcript", targets)
    assert outcomes == {0: "used_correctly", 1: "not_used"}


def test_review_induction_usage_uses_list_position_not_db_id_when_ids_collide():
    # 回归测试：word 和 pro_phrase 各自的表都从 id=1 自增，完全可能撞号。
    # 用列表位置当 key 后，两个目标即使 db id 相同也不会互相覆盖判断结果。
    llm = _FakeLLM('[{"id": 0, "outcome": "used_correctly"}, {"id": 1, "outcome": "used_incorrectly"}]')
    targets = [
        InductionTarget(id=1, kind="word", label="a"),
        InductionTarget(id=1, kind="pro_phrase", label="b"),
    ]
    outcomes = review_induction_usage(llm, "French", "transcript", targets)
    assert outcomes == {0: "used_correctly", 1: "used_incorrectly"}


def test_review_induction_usage_handles_markdown_fence():
    llm = _FakeLLM('```json\n[{"id": 0, "outcome": "used_incorrectly"}]\n```')
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {0: "used_incorrectly"}


def test_review_induction_usage_malformed_json_returns_empty():
    llm = _FakeLLM("not json at all")
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {}


def test_review_induction_usage_ignores_invalid_outcome_values():
    llm = _FakeLLM('[{"id": 0, "outcome": "maybe"}]')
    targets = [InductionTarget(id=1, kind="word", label="a")]
    assert review_induction_usage(llm, "French", "t", targets) == {}


def test_apply_mastery_updates_increments_on_correct_use():
    conn = db.connect(":memory:")
    w = _word(mastery=0)
    db.insert_words(conn, [w])
    target = InductionTarget(id=w.id, kind="word", label="w")

    # outcomes 的 key 是列表位置（这里只有一个 target，位置是 0），不是 db id——
    # 见 induction.py 的说明。
    apply_mastery_updates(conn, [target], {0: "used_correctly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_words(conn, "fr")[0]
    assert fetched.mastery == 1
    assert fetched.last_practiced == "2026-08-28T00:00:00+00:00"


def test_apply_mastery_updates_decrements_on_incorrect_use_floored_at_zero():
    conn = db.connect(":memory:")
    e = _expr(mastery=0)
    db.insert_expressions(conn, [e])
    target = InductionTarget(id=e.id, kind="expression", label="e")

    apply_mastery_updates(conn, [target], {0: "used_incorrectly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_expressions(conn, "fr")[0]
    assert fetched.mastery == 0  # 本来就是 0，-1 被地板卡住


def test_apply_mastery_updates_handles_pro_phrase_kind():
    conn = db.connect(":memory:")
    p = _phrase(mastery=0)
    db.insert_pro_phrases(conn, [p])
    target = InductionTarget(id=p.id, kind="pro_phrase", label="p")

    apply_mastery_updates(conn, [target], {0: "used_correctly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_pro_phrases(conn, "fr")[0]
    assert fetched.mastery == 1
    assert fetched.last_practiced == "2026-08-28T00:00:00+00:00"


def test_apply_mastery_updates_handles_collocation_kind():
    conn = db.connect(":memory:")
    c = _collocation(mastery=0)
    db.insert_collocations(conn, [c])
    target = InductionTarget(id=c.id, kind="collocation", label="c")

    apply_mastery_updates(conn, [target], {0: "used_correctly"}, "2026-08-28T00:00:00+00:00")

    fetched = db.fetch_collocations(conn, "fr")[0]
    assert fetched.mastery == 1
    assert fetched.last_practiced == "2026-08-28T00:00:00+00:00"


def test_apply_mastery_updates_disambiguates_targets_with_colliding_db_ids():
    # 回归测试：word/pro_phrase/collocation 各自的表都从 id=1 自增，撞号是完全可能的。
    # 用列表位置对齐后，各个目标的更新互不干扰，即使 db id 相同。
    conn = db.connect(":memory:")
    w = _word(mastery=0)
    db.insert_words(conn, [w])
    p = _phrase(mastery=0)
    db.insert_pro_phrases(conn, [p])
    c = _collocation(mastery=0)
    db.insert_collocations(conn, [c])
    assert w.id == p.id == c.id == 1  # 前提：确实撞号了，不然这个回归测试没有意义

    targets = [
        InductionTarget(id=w.id, kind="word", label="w"),
        InductionTarget(id=p.id, kind="pro_phrase", label="p"),
        InductionTarget(id=c.id, kind="collocation", label="c"),
    ]
    apply_mastery_updates(
        conn, targets,
        {0: "used_correctly", 1: "used_incorrectly", 2: "used_correctly"},
        "2026-08-28T00:00:00+00:00",
    )

    assert db.fetch_words(conn, "fr")[0].mastery == 1
    assert db.fetch_pro_phrases(conn, "fr")[0].mastery == 0  # -1 被地板卡在 0
    assert db.fetch_collocations(conn, "fr")[0].mastery == 1


def test_apply_mastery_updates_leaves_not_used_untouched():
    conn = db.connect(":memory:")
    w = _word(mastery=3, last_practiced="2026-08-01T00:00:00+00:00")
    db.insert_words(conn, [w])
    target = InductionTarget(id=w.id, kind="word", label="w")

    apply_mastery_updates(conn, [target], {0: "not_used"}, "2026-08-28T00:00:00+00:00")

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
