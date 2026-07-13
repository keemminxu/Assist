"""엔트리포인트 — 조립만 한다. python -m bot.main"""
from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime

from bot import prompts
from bot.brain import Brain, SDKRunner
from bot.config import Settings
from bot.diary import Diary
from bot.discord_bot import chunk_message, create_client
from bot.gcal import GCal, make_token_provider
from bot.scheduler import KST, run_loop
from bot.store import MemoStore, MuseStore
from bot.tools import build_server
from bot.weather import one_liner

log = logging.getLogger("assist")


def make_options_factory(server, persona: str):
    from claude_agent_sdk import ClaudeAgentOptions

    def factory(model: str):
        return ClaudeAgentOptions(
            system_prompt=persona,
            model=model,
            mcp_servers={"assist": server},
            allowed_tools=["mcp__assist__*", "WebSearch"],
            permission_mode="dontAsk",
            max_turns=15,
        )
    return factory


async def amain() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    s = Settings.from_env()

    memos = MemoStore(s.supabase_url, s.supabase_service_key)
    muse = MuseStore(s.blog_supabase_url, s.blog_supabase_service_key)
    diary = Diary(s.blog_supabase_url, s.blog_supabase_service_key)
    gcal = GCal(s.gcal_ids, make_token_provider(s.gcal_sa_key))
    weather_fn = functools.partial(one_liner, s.weather_lat, s.weather_lon)

    server = build_server(gcal=gcal, memos=memos, muse=muse, weather_fn=weather_fn)
    brain = Brain(SDKRunner(make_options_factory(server, prompts.PERSONA)),
                  model=s.claude_model, fallback_model=s.claude_fallback_model)
    client = create_client(s, brain, diary)

    async def send_assist(text: str) -> None:
        channel = client.get_channel(s.assist_channel_id)
        if channel is None:
            log.error("assist 채널을 못 찾음: %s", s.assist_channel_id)
            return
        for chunk in chunk_message(text):
            await channel.send(chunk)

    async def do_briefing() -> None:
        await brain.rotate()                          # 하루 1회 세션 로테이션
        try:
            reply = await brain.ask(prompts.briefing_prompt(datetime.now(KST).date()))
        except Exception:                             # noqa: BLE001 — 침묵 실패 금지
            log.exception("브리핑 생성 실패")
            reply = "아침 브리핑 만들다 넘어졌어 — 뉴스는 이따 직접 물어봐줘."
        await send_assist(reply)

    async def do_muse_chance() -> None:
        reply = await brain.ask(prompts.MUSE_CHANCE)
        log.info("아무말 기회 결과: %s", reply[:80])

    async def do_muse_deadline() -> None:
        if await muse.count_today() == 0:
            reply = await brain.ask(prompts.MUSE_DEADLINE)
            log.info("아무말 마감 결과: %s", reply[:80])

    async def start_scheduler() -> None:
        await client.wait_until_ready()
        await run_loop({"briefing": do_briefing,
                        "muse_chance": do_muse_chance,
                        "muse_deadline": do_muse_deadline})

    asyncio.ensure_future(start_scheduler())
    await client.start(s.discord_token)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
