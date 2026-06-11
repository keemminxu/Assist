import json

import pytest

from bot.claude_runner import ClaudeError, RateLimited, _parse_result


def test_parse_success_returns_reply_and_session():
    out = json.dumps({"type": "result", "subtype": "success",
                      "result": "  안녕하세요!  ", "session_id": "sess-abc"})
    reply, sid = _parse_result(0, out, "")
    assert reply == "안녕하세요!"
    assert sid == "sess-abc"


def test_parse_nonzero_with_429_raises_rate_limited():
    with pytest.raises(RateLimited):
        _parse_result(1, "", "API Error: 429 rate limit exceeded")


def test_parse_nonzero_with_limit_reached_raises_rate_limited():
    with pytest.raises(RateLimited):
        _parse_result(1, "5-hour limit reached", "")


def test_parse_nonzero_other_raises_claude_error():
    with pytest.raises(ClaudeError):
        _parse_result(1, "", "segfault")


def test_parse_zero_but_invalid_json_raises_claude_error():
    with pytest.raises(ClaudeError):
        _parse_result(0, "이건 JSON 아님", "")
