"""tools 핸들러 — 페이크 의존성으로 검증 (MCP 래핑은 build_server가 얇게)."""
import asyncio

from bot.gcal import AmbiguousMatch, NoMatch
from bot.tools import (CHAT_ALLOWED_TOOLS, MUSE_ALLOWED_TOOLS, MUSE_DAILY_LIMIT,
                       build_muse_server, build_server, handle_gcal_add,
                       handle_gcal_delete, handle_gcal_update, handle_memo_add,
                       handle_memo_delete, handle_memo_list, handle_memo_update,
                       handle_muse_post)


def run(coro):
    return asyncio.run(coro)


def text_of(result: dict) -> str:
    return result["content"][0]["text"]


class FakeMemos:
    def __init__(self):
        self.rows = []
        self._next = 1

    async def add(self, content):
        row = {"id": self._next, "content": content}
        self._next += 1
        self.rows.append(row)
        return row

    async def list(self):
        return list(self.rows)

    async def update(self, memo_id, content):
        for r in self.rows:
            if r["id"] == memo_id:
                r["content"] = content
                return True
        return False

    async def delete(self, memo_id):
        before = len(self.rows)
        self.rows = [r for r in self.rows if r["id"] != memo_id]
        return len(self.rows) < before


class FakeMuse:
    def __init__(self, today=0):
        self.today = today
        self.posted = []

    async def count_today(self):
        return self.today

    async def post(self, content):
        self.posted.append(content)
        self.today += 1


class FakeGcal:
    """호출 인자를 기록하고, exc가 있으면 대신 던진다."""
    def __init__(self, exc=None):
        self._exc = exc
        self.calls = []

    def add(self, *a, **kw):
        if self._exc:
            raise self._exc
        self.calls.append((a, kw))
        return "등록됨: X"

    def update(self, *a, **kw):
        if self._exc:
            raise self._exc
        self.calls.append((a, kw))
        return "변경됨: X"

    def delete(self, *a, **kw):
        if self._exc:
            raise self._exc
        self.calls.append((a, kw))
        return "삭제됨: X"


def test_memo_add_and_list():
    memos = FakeMemos()
    out = run(handle_memo_add(memos, {"content": "매직랩 사야 됨"}))
    assert "매직랩" in text_of(out)
    listed = text_of(run(handle_memo_list(memos, {})))
    assert "1." in listed and "매직랩" in listed


def test_memo_list_empty():
    assert "메모 없음" in text_of(run(handle_memo_list(FakeMemos(), {})))


def test_memo_update_missing_id():
    out = run(handle_memo_update(FakeMemos(), {"id": 9, "content": "x"}))
    assert "못 찾" in text_of(out)


def test_memo_delete():
    memos = FakeMemos()
    run(handle_memo_add(memos, {"content": "우유"}))
    assert "삭제" in text_of(run(handle_memo_delete(memos, {"id": 1})))
    assert memos.rows == []


def test_muse_post_respects_daily_limit():
    muse = FakeMuse(today=MUSE_DAILY_LIMIT)
    out = run(handle_muse_post(muse, {"content": "글"}))
    assert muse.posted == []
    assert "상한" in text_of(out)


def test_muse_post_writes_under_limit():
    muse = FakeMuse(today=0)
    out = run(handle_muse_post(muse, {"content": "오늘의 아무말"}))
    assert muse.posted == ["오늘의 아무말"]
    assert "게시" in text_of(out)


def test_chat_tools_cannot_post_to_blog():
    """대화 세션은 공개 블로그에 글을 못 쓴다 — muse_post 제외가 격리의 절반."""
    assert "mcp__assist__muse_post" not in CHAT_ALLOWED_TOOLS
    assert "mcp__assist__gcal_agenda" in CHAT_ALLOWED_TOOLS
    assert "mcp__assist__memo_add" in CHAT_ALLOWED_TOOLS
    assert "mcp__assist__diary_recent" in CHAT_ALLOWED_TOOLS
    assert "WebSearch" in CHAT_ALLOWED_TOOLS


def test_muse_tools_cannot_reach_private_data():
    """muse(공개 블로그) 세션은 사적 데이터 도구에 접근 불가 — 나머지 절반.
    weather도 없다: 1회 호출로 소재가 나오는 도구가 날씨 도배(2026-07 하순)의 원인이었다."""
    assert set(MUSE_ALLOWED_TOOLS) == {"mcp__assist__muse_post", "WebSearch"}


async def _fake_weather():
    return "맑음"


def server_tool_names(cfg):
    """create_sdk_mcp_server 결과에서 실제 등록된 도구명을 뽑는다 — 상수가 아니라 배선 검증."""
    import mcp.types as mt
    handler = cfg["instance"].request_handlers[mt.ListToolsRequest]
    res = run(handler(mt.ListToolsRequest(method="tools/list")))
    return sorted(t.name for t in res.root.tools)


def test_build_muse_server_registers_only_public_safe_tools():
    """muse 서버에는 muse_post 하나뿐 — 사적 도구는 물론 weather도 등록되지 않는다."""
    cfg = build_muse_server(muse=FakeMuse())
    assert server_tool_names(cfg) == ["muse_post"]


def test_build_server_does_not_register_muse_post():
    """대화 서버에는 muse_post가 등록되지 않는다 — 사적 컨텍스트 세션은 공개 발행 불가."""
    cfg = build_server(gcal=FakeGcal(), memos=FakeMemos(), muse=FakeMuse(),
                       weather_fn=_fake_weather)
    names = server_tool_names(cfg)
    assert "muse_post" not in names
    assert "diary_recent" in names and "gcal_agenda" in names


def test_gcal_update_ambiguous_returns_candidates():
    gcal = FakeGcal(exc=AmbiguousMatch(["7/14 치과", "7/21 치과"]))
    out = text_of(run(handle_gcal_update(gcal, {"title": "치과", "new_start": "x"})))
    assert "여러 개" in out and "7/21 치과" in out


def test_gcal_delete_no_match():
    gcal = FakeGcal(exc=NoMatch("'치과' 없음"))
    assert "못 찾" in text_of(run(handle_gcal_delete(gcal, {"title": "치과"})))


def test_gcal_add_empty_end_becomes_none():
    """SDK required 스키마 탓에 모델이 보내는 빈 문자열은 None으로 정규화돼야 한다."""
    gcal = FakeGcal()
    run(handle_gcal_add(gcal, {"title": "치과", "start": "2026-07-14T15:00",
                               "end": "", "description": ""}))
    (a, kw), = gcal.calls
    assert a == ("치과", "2026-07-14T15:00", None, None)
    assert kw == {}


def test_gcal_update_empty_optionals_become_none():
    gcal = FakeGcal()
    run(handle_gcal_update(gcal, {"title": "치과", "start": "", "new_title": "",
                                  "new_start": "2026-07-15T16:00", "new_end": ""}))
    (a, kw), = gcal.calls
    assert a == ("치과", None)
    assert kw == {"new_title": None, "new_start": "2026-07-15T16:00", "new_end": None}
