"""삐삐의 in-process MCP 도구.

handle_* 는 의존성을 명시적으로 받는 순수 핸들러(테스트 대상).
build_server()가 이를 @tool로 감싸 create_sdk_mcp_server로 조립한다.
"""
from __future__ import annotations

import asyncio

from claude_agent_sdk import create_sdk_mcp_server, tool

from bot.gcal import AmbiguousMatch, GcalError, NoMatch

MUSE_DAILY_LIMIT = 2

# 세션별 도구 화이트리스트 — muse(공개 블로그) 세션은 사적 데이터 도구에 접근할 수 없고,
# 대화 세션은 muse_post가 없어 블로그에 글을 못 쓴다. 각 방향 모두 서버 등록(build_server/
# build_muse_server)과 allowed_tools의 이중 차단이다.
_PRIVATE_TOOLS = ("gcal_agenda", "gcal_add", "gcal_update", "gcal_delete",
                  "memo_add", "memo_list", "memo_update", "memo_delete", "diary_recent")
CHAT_ALLOWED_TOOLS = [f"mcp__assist__{n}" for n in (*_PRIVATE_TOOLS, "weather")] + ["WebSearch"]
# muse에 weather 없음 — 날씨 도배 사고(2026-07 하순)의 원인이 "1회 호출로 소재가 나오는"
# 손쉬운 도구였다. 특보급 날씨는 어차피 WebSearch 뉴스로 잡힌다.
MUSE_ALLOWED_TOOLS = ["mcp__assist__muse_post", "WebSearch"]


def _text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


# ── gcal ──────────────────────────────────────────────────────────

async def handle_gcal_agenda(gcal, args: dict) -> dict:
    days = int(args.get("days", 7))
    return _text(await asyncio.to_thread(gcal.agenda, days))


async def handle_gcal_add(gcal, args: dict) -> dict:
    # SDK가 dict 스키마를 전부 required로 선언 → 모델이 선택 인자를 ""로 보냄 → None 정규화
    try:
        out = await asyncio.to_thread(
            gcal.add, args["title"], args["start"],
            args.get("end") or None, args.get("description") or None)
        return _text(out)
    except GcalError as e:
        return _text(f"등록 실패: {e}")


def _mutate_result(fn) -> dict:
    """update/delete 공통 — 매칭 예외를 사람 말로 변환."""
    try:
        return _text(fn())
    except AmbiguousMatch as e:
        lines = "\n".join(f"- {c}" for c in e.candidates)
        return _text(f"같은 이름의 일정이 여러 개야 — 어느 걸 말하는지 알려줘:\n{lines}")
    except NoMatch as e:
        return _text(f"일정을 못 찾았어: {e}")
    except GcalError as e:
        return _text(f"실패: {e}")


async def handle_gcal_update(gcal, args: dict) -> dict:
    def call():
        return gcal.update(args["title"], args.get("start") or None,
                           new_title=args.get("new_title") or None,
                           new_start=args.get("new_start") or None,
                           new_end=args.get("new_end") or None)
    return await asyncio.to_thread(_mutate_result, call)


async def handle_gcal_delete(gcal, args: dict) -> dict:
    def call():
        return gcal.delete(args["title"], args.get("start") or None)
    return await asyncio.to_thread(_mutate_result, call)


# ── memo ──────────────────────────────────────────────────────────

async def handle_memo_add(memos, args: dict) -> dict:
    row = await memos.add(args["content"])
    return _text(f"메모 등록: {row['id']}. {row['content']}")


async def handle_memo_list(memos, args: dict) -> dict:
    rows = await memos.list()
    if not rows:
        return _text("메모 없음")
    return _text("\n".join(f"{r['id']}. {r['content']}" for r in rows))


async def handle_memo_update(memos, args: dict) -> dict:
    ok = await memos.update(int(args["id"]), args["content"])
    return _text("수정 완료" if ok else f"id={args['id']} 메모를 못 찾았어")


async def handle_memo_delete(memos, args: dict) -> dict:
    ok = await memos.delete(int(args["id"]))
    return _text("삭제 완료" if ok else f"id={args['id']} 메모를 못 찾았어")


# ── weather / diary / muse ────────────────────────────────────────

async def handle_weather(weather_fn, args: dict) -> dict:
    return _text(await weather_fn())


async def handle_diary_recent(muse, args: dict) -> dict:
    rows = await muse.recent_diary(int(args.get("n", 5)))
    if not rows:
        return _text("최근 일기 없음")
    return _text("\n---\n".join(
        f"[{r.get('created_at', '')[:10]}] {r['content']}" for r in rows))


async def handle_muse_post(muse, args: dict) -> dict:
    if await muse.count_today() >= MUSE_DAILY_LIMIT:
        return _text(f"오늘은 이미 {MUSE_DAILY_LIMIT}번 썼어 — 상한이라 못 올려.")
    await muse.post(args["content"])
    return _text("게시 완료.")


# ── 조립 ──────────────────────────────────────────────────────────

def build_server(*, gcal, memos, muse, weather_fn):
    """의존성을 클로저로 물고 MCP 서버를 만든다. main.py에서 한 번 호출."""

    @tool("gcal_agenda", "다가오는 일정 조회", {"days": int})
    async def gcal_agenda(args):
        return await handle_gcal_agenda(gcal, args)

    @tool("gcal_add",
          "일정 등록. start/end는 'YYYY-MM-DDTHH:MM' 또는 종일이면 'YYYY-MM-DD'. "
          "end 생략 시 1시간(종일은 하루)짜리",
          {"title": str, "start": str, "end": str, "description": str})
    async def gcal_add(args):
        return await handle_gcal_add(gcal, args)

    @tool("gcal_update",
          "기존 일정 변경. title(+선택 start)로 대상을 찾고 new_title/new_start/new_end로 바꾼다",
          {"title": str, "start": str, "new_title": str, "new_start": str, "new_end": str})
    async def gcal_update(args):
        return await handle_gcal_update(gcal, args)

    @tool("gcal_delete", "일정 삭제. title(+선택 start)로 대상을 찾는다",
          {"title": str, "start": str})
    async def gcal_delete(args):
        return await handle_gcal_delete(gcal, args)

    @tool("memo_add", "메모 등록", {"content": str})
    async def memo_add(args):
        return await handle_memo_add(memos, args)

    @tool("memo_list", "메모 전체 조회 (id와 내용)", {})
    async def memo_list(args):
        return await handle_memo_list(memos, args)

    @tool("memo_update", "메모 내용 수정 (id는 memo_list로 확인)", {"id": int, "content": str})
    async def memo_update(args):
        return await handle_memo_update(memos, args)

    @tool("memo_delete", "메모 삭제 (id는 memo_list로 확인)", {"id": int})
    async def memo_delete(args):
        return await handle_memo_delete(memos, args)

    @tool("weather", "현재 날씨 1줄 (서울 기준)", {})
    async def weather(args):
        return await handle_weather(weather_fn, args)

    @tool("diary_recent", "민수의 최근 블로그 일기 n개 조회", {"n": int})
    async def diary_recent(args):
        return await handle_diary_recent(muse, args)

    # muse_post는 여기 없다 — 사적 데이터를 읽는 대화 세션은 공개 블로그에 글을 쓸 수 없다.
    return create_sdk_mcp_server(name="assist", version="1.0.0", tools=[
        gcal_agenda, gcal_add, gcal_update, gcal_delete,
        memo_add, memo_list, memo_update, memo_delete,
        weather, diary_recent,
    ])


def build_muse_server(*, muse):
    """muse 전용 서버 — 공개 블로그 세션에는 사적 데이터 도구(gcal·memo·diary)를
    allowed_tools 이전에 서버 차원에서 아예 등록하지 않는다. weather도 없다(위 주석)."""

    @tool("muse_post", "블로그 게시판에 글 작성 (하루 2회 상한)", {"content": str})
    async def muse_post(args):
        return await handle_muse_post(muse, args)

    return create_sdk_mcp_server(name="assist", version="1.0.0", tools=[muse_post])
