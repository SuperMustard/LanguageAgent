import re

_STAGE_DIRECTION = re.compile(r"\*+[^*]*\*+")
_EXTRA_WHITESPACE = re.compile(r"\s{2,}")


def strip_for_speech(text: str) -> str:
    """去掉 *叹气* / **动作** 这类角色扮演舞台指示，只留给 TTS 念——LLM 常把它们当非语言提示写进回复，
    Azure TTS 会把星号原样念出来（"Asterisk soupire Asterisk"），破坏沉浸感。
    文字记录（debrief 用的 transcript、返回给前端的 X-Reply-Text）不受影响，只影响送进 TTS 的文本。
    """
    stripped = _STAGE_DIRECTION.sub("", text)
    return _EXTRA_WHITESPACE.sub(" ", stripped).strip()
