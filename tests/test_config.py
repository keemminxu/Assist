from bot.config import Settings


def test_parse_user_labels_basic():
    assert Settings._parse_user_labels("111:민수,222:하늘") == {111: "민수", 222: "하늘"}


def test_parse_user_labels_empty_returns_empty_dict():
    assert Settings._parse_user_labels("") == {}


def test_parse_user_labels_skips_malformed_entries():
    # 콜론 없음(333) · 빈 이름(444:) · id가 숫자 아님(abc:foo)은 무시
    assert Settings._parse_user_labels("333,444:,abc:foo,555:보라") == {555: "보라"}


def test_parse_user_labels_trims_whitespace():
    assert Settings._parse_user_labels(" 111 : 민수 , 222 : 하늘 ") == {111: "민수", 222: "하늘"}
