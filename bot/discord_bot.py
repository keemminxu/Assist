"""Discord 게이트웨이 클라이언트.

- #비서 채널: 메시지를 Conversation(Claude)에 직렬 전달.
- #코멘트 채널: 메시지를 그대로 블로그 일기(daily_logs)에 기록. 메시지 삭제 시 일기도 삭제.
"""
from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)

DISCORD_MAX_MSG = 2000


def chunk_message(text: str, limit: int = DISCORD_MAX_MSG) -> list[str]:
    if not text.strip():
        return ["(빈 응답)"]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _allowed(settings, user_id: int) -> bool:
    return not settings.allowed_user_ids or user_id in settings.allowed_user_ids


def create_client(settings, make_conversation, diary=None) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    conversations: dict[int, object] = {}

    @client.event
    async def on_ready():
        log.info("비서 봇 가동 | user=%s | assist=%s | diary=%s",
                 client.user, settings.assist_channel_id,
                 settings.diary_channel_id or "비활성")

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot or not message.content:
            return

        # #코멘트 채널 → 블로그 일기 기록 (Claude 안 거침)
        if diary and settings.diary_channel_id and message.channel.id == settings.diary_channel_id:
            if not _allowed(settings, message.author.id):
                log.warning("코멘트 허용 목록 밖 사용자 무시: %s", message.author.id)
                return
            try:
                await diary.add(message.content, message.id,
                                message.created_at.isoformat())
                await message.add_reaction("✅")
            except Exception:           # noqa: BLE001 — 일기 유실 침묵 금지
                log.exception("일기 기록 실패")
                try:
                    await message.add_reaction("❌")
                except discord.DiscordException:
                    pass
            return

        # #비서 채널 → Claude 대화
        if message.channel.id != settings.assist_channel_id:
            return
        if not _allowed(settings, message.author.id):
            log.warning("허용 목록 밖 사용자 무시: %s (%s)",
                        message.author, message.author.id)
            return
        conv = conversations.setdefault(message.channel.id, make_conversation())
        try:
            async with message.channel.typing():
                reply = await conv.ask(message.content)
        except Exception as e:           # noqa: BLE001 — 마지막 방어선
            log.exception("메시지 처리 실패")
            reply = f"처리 중 예상 못 한 오류: {e}"
        for chunk in chunk_message(reply):
            await message.channel.send(chunk)

    @client.event
    async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
        # #코멘트 채널의 메시지를 지우면 블로그 일기도 삭제
        if diary and settings.diary_channel_id and payload.channel_id == settings.diary_channel_id:
            try:
                await diary.delete_by_message(payload.message_id)
                log.info("일기 삭제: msg=%s", payload.message_id)
            except Exception:           # noqa: BLE001
                log.exception("일기 삭제 실패: msg=%s", payload.message_id)

    return client
