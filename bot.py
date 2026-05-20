"""Discord ↔ Claude(OpenClaw 경유) 개인 비서 봇.

OpenClaw가 localhost:8000에서 OpenAI 호환 엔드포인트를 노출한다는 가정 하에,
AsyncOpenAI 클라이언트로 Claude CLI 세션을 호출한다.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict, deque

import discord
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# ──────────────────────────────────────────────
# 1. 환경 설정 (모두 .env 에서 주입)
# ──────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "http://localhost:8000/v1")
OPENCLAW_API_KEY = os.getenv("OPENCLAW_API_KEY", "openclaw-local")
MODEL_NAME = os.getenv("MODEL_NAME", "anthropic/claude-opus-4-7")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("assist-bot")

# ──────────────────────────────────────────────
# 2. Claude(OpenClaw) 클라이언트
# ──────────────────────────────────────────────
claude = AsyncOpenAI(base_url=OPENCLAW_BASE_URL, api_key=OPENCLAW_API_KEY)

SYSTEM_PROMPT = (
    "너는 김민수의 24시간 개인 비서야.\n"
    "항상 친절하고 명확하게 대답해 주고, 디스코드에 어울리게 마크다운을 적절히 활용해.\n"
    "장황한 설명보다 핵심을 먼저 전달하는 걸 선호해."
)

HISTORY_TURN_LIMIT = 20  # 채널별 최근 20턴(user+assistant ≈ 40 메시지)
channel_history: dict[int, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=HISTORY_TURN_LIMIT * 2)
)

# ──────────────────────────────────────────────
# 3. 디스코드 클라이언트
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

DISCORD_MAX_MSG = 2000


async def call_claude(channel_id: int, user_text: str) -> str:
    history = channel_history[channel_id]
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    resp = await claude.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7,
    )
    reply = (resp.choices[0].message.content or "").strip()
    history.append({"role": "assistant", "content": reply})
    return reply


async def send_chunked(channel: discord.abc.Messageable, text: str) -> None:
    """디스코드 2000자 제한을 넘는 응답을 분할 전송."""
    if not text:
        await channel.send("(빈 응답)")
        return
    for i in range(0, len(text), DISCORD_MAX_MSG):
        await channel.send(text[i : i + DISCORD_MAX_MSG])


@client.event
async def on_ready() -> None:
    log.info(
        "비서 봇 부팅 완료 | user=%s | model=%s | api=%s",
        client.user,
        MODEL_NAME,
        OPENCLAW_BASE_URL,
    )


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author == client.user or not message.content:
        return

    try:
        async with message.channel.typing():
            reply = await call_claude(message.channel.id, message.content)
            await send_chunked(message.channel, reply)
    except Exception as e:
        log.exception("Claude 호출 실패")
        await message.channel.send(
            f"🧠 처리 중 에러가 발생했습니다: `{type(e).__name__}: {e}`"
        )


if __name__ == "__main__":
    client.run(DISCORD_TOKEN, log_handler=None)
