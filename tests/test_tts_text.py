from langpractice.tts_text import strip_for_speech


def test_strips_single_asterisk_stage_direction():
    assert strip_for_speech("*Soupir* Bonjour.") == "Bonjour."


def test_strips_double_asterisk_stage_direction():
    assert strip_for_speech("**sourit** Bonjour.") == "Bonjour."


def test_strips_stage_direction_in_middle_of_sentence():
    assert strip_for_speech("Bonjour, *hésite un peu* comment allez-vous ?") == \
        "Bonjour, comment allez-vous ?"


def test_strips_multiple_stage_directions():
    assert strip_for_speech("*soupir* Bonjour. *sourit* Ça va ?") == "Bonjour. Ça va ?"


def test_leaves_plain_text_untouched():
    assert strip_for_speech("Bonjour, comment allez-vous ?") == "Bonjour, comment allez-vous ?"


def test_collapses_leftover_double_spaces():
    assert strip_for_speech("Bonjour  *soupir*  comment allez-vous ?") == "Bonjour comment allez-vous ?"
