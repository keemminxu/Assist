"""Discord 게이트웨이.

- #비서: 허용 사용자 메시지를 Brain(상주 Agent SDK 세션)에 전달.
- #코멘트: 메시지를 블로그 일기(daily_logs)로 기록. 삭제 시 일기도 삭제.

handle_message / handle_raw_delete 는 순수 핸들러(테스트 대상),
create_client 가 discord.Client 이벤트에 얇게 바인딩한다.
"""
from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)

DISCORD_MAX_MSG = 2000
HUMAN_ERROR = "어이쿠, 처리하다 넘어졌어. 잠깐 뒤에 다시 불러줘."


def chunk_message(text: str, limit: int = DISCORD_MAX_MSG) -> list[str]:
    """마크다운 줄 경계를 존중하며 limit 이하로 분할. 한 줄이 limit보다 길면 하드 분할."""
    if not text.strip():
        return ["(빈 응답)"]
    chunks: list[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        cand = f"{cur}\n{line}" if cur else line
        if len(cand) > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = cand
    if cur.strip():
        chunks.append(cur)
    return chunks or ["(빈 응답)"]


def _allowed(settings, user_id: int) -> bool:
    return user_id in settings.allowed_user_ids     # fail-closed: 빈 목록은 config가 거부


async def handle_message(settings, brain, diary, message) -> None:
    if message.author.bot or not message.content:
        return

    # #코멘트 → 블로그 일기 (Claude 안 거침)
    if message.channel.id == settings.diary_channel_id:
        if not _allowed(settings, message.author.id):
            log.warning("코멘트 허용 목록 밖 사용자 무시: %s", message.author.id)
            return
        try:
            await diary.add(message.content, message.id,
                            message.created_at.isoformat())
            await message.add_reaction("✅")
        except Exception:                            # noqa: BLE001 — 일기 유실 침묵 금지
            log.exception("일기 기록 실패")
            try:
                await message.add_reaction("❌")
            except Exception:                        # noqa: BLE001
                pass
        return

    # #비서 → 삐삐
    if message.channel.id != settings.assist_channel_id:
        return
    if not _allowed(settings, message.author.id):
        log.warning("허용 목록 밖 사용자 무시: %s", message.author.id)
        return
    try:
        async with message.channel.typing():
            reply = await brain.ask(message.content)
    except Exception:                                # noqa: BLE001 — 마지막 방어선
        log.exception("메시지 처리 실패")
        reply = HUMAN_ERROR
    for chunk in chunk_message(reply):
        await message.channel.send(chunk)


async def handle_raw_delete(settings, diary, payload) -> None:
    if payload.channel_id != settings.diary_channel_id:
        return
    try:
        await diary.delete_by_message(payload.message_id)
        log.info("일기 삭제: msg=%s", payload.message_id)
    except Exception:                                # noqa: BLE001
        log.exception("일기 삭제 실패: msg=%s", payload.message_id)


def create_client(settings, brain, diary) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        log.info("삐삐 가동 | user=%s | assist=%s | diary=%s",
                 client.user, settings.assist_channel_id, settings.diary_channel_id)

    @client.event
    async def on_message(message: discord.Message):
        await handle_message(settings, brain, diary, message)

    @client.event
    async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
        await handle_raw_delete(settings, diary, payload)

    return client
