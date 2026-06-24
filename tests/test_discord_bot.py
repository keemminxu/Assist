from types import SimpleNamespace

from bot.discord_bot import frame_prompt


def _settings(labels):
    return SimpleNamespace(user_labels=labels)


def test_frame_prompt_uses_label_when_mapped():
    s = _settings({111: "민수"})
    assert frame_prompt(s, 111, "devkeem", "안녕") == "[발신자: 민수]\n안녕"


def test_frame_prompt_falls_back_to_display_name_when_unmapped():
    s = _settings({111: "민수"})
    assert frame_prompt(s, 999, "몽쿠리", "일정 잡아줘") == "[발신자: 몽쿠리]\n일정 잡아줘"


def test_frame_prompt_header_is_first_line():
    s = _settings({})
    framed = frame_prompt(s, 1, "하늘", "여러\n줄\n메시지")
    assert framed.splitlines()[0] == "[발신자: 하늘]"
