"""Discord 게이트웨이 클라이언트 — #비서 채널 메시지를 Conversation에 직렬 전달."""
from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)

DISCORD_MAX_MSG = 2000


def chunk_message(text: str, limit: int = DISCORD_MAX_MSG) -> list[str]:
    if not text.strip():
        return ["(빈 응답)"]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def create_client(settings, make_conversation) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    conversations: dict[int, object] = {}

    @client.event
    async def on_ready():
        log.info("비서 봇 가동 | user=%s | channel=%s",
                 client.user, settings.assist_channel_id)

    @client.event
    async def on_message(message: discord.Message):
        if (message.author.bot
                or message.channel.id != settings.assist_channel_id
                or not message.content):
            return
        if settings.allowed_user_ids and message.author.id not in settings.allowed_user_ids:
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

    return client
