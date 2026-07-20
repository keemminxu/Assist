"""삐삐 두뇌 — Agent SDK 상주 세션.

Brain: 직렬 큐(락) + 429 백오프(락 **밖** 대기) + 모델 다운시프트 + 세션 리셋 재시도.
SDKRunner: ClaudeSDKClient 래퍼 — 모델 교체/리셋 시 클라이언트 재생성.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

_BACKOFFS = (0, 30, 90, 180)       # 시도 4회
_DOWNSHIFT_FROM = 2                # 3번째 시도(인덱스 2)부터 폴백 모델
LIMIT_MESSAGE = "지금 Claude 사용 한도에 걸려 있어. 잠시 뒤에 다시 불러줘. 🙏"
ERROR_MESSAGE = "머리가 좀 꼬였어 — 잠깐 뒤에 다시 불러줘."
_RATE_MARKERS = ("429", "rate limit", "limit reached")


class BrainError(Exception):
    """두뇌 호출 실패 (일반)."""


class RateLimited(BrainError):
    """구독 한도 도달."""


class Brain:
    """runner 프로토콜: async ask(prompt, model) -> str / async reset()."""

    def __init__(self, runner, *, model: str = "sonnet",
                 fallback_model: str = "haiku", sleep=asyncio.sleep):
        self._runner = runner
        self._model = model
        self._fallback = fallback_model
        self._sleep = sleep
        self._lock = asyncio.Lock()

    async def ask(self, prompt: str) -> str:
        for i, delay in enumerate(_BACKOFFS):
            if delay:
                await self._sleep(delay)            # 락 밖 — 다른 메시지가 끼어들 수 있다
            model = self._fallback if i >= _DOWNSHIFT_FROM else self._model
            async with self._lock:
                try:
                    return await self._runner.ask(prompt, model=model)
                except RateLimited:
                    log.warning("rate limited (시도 %d/%d)", i + 1, len(_BACKOFFS))
                except BrainError as e:
                    log.error("두뇌 오류, 세션 리셋 후 재시도: %s", e)
                    await self._runner.reset()
                    try:
                        return await self._runner.ask(prompt, model=model)
                    except RateLimited:
                        log.warning("리셋 후 재시도도 rate limited (시도 %d)", i + 1)
                    except BrainError as e2:
                        log.error("리셋 재시도도 실패: %s", e2)
                        return ERROR_MESSAGE
        return LIMIT_MESSAGE

    async def rotate(self) -> None:
        """세션 교체 (아침 브리핑 직전 등)."""
        async with self._lock:
            await self._runner.reset()

    async def ask_fresh(self, prompt: str) -> str:
        """빈 세션에서 1회 질의 — 이전 대화·이전 글 컨텍스트를 물려받지 않는다 (muse 격리용)."""
        await self.rotate()
        return await self.ask(prompt)


class SDKRunner:
    """실제 Agent SDK 세션. options_factory(model) -> ClaudeAgentOptions."""

    def __init__(self, options_factory):
        self._factory = options_factory
        self._client = None
        self._model: str | None = None

    async def _ensure(self, model: str):
        from claude_agent_sdk import ClaudeSDKClient
        if self._client is not None and model != self._model:
            await self.reset()
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._factory(model))
            await self._client.connect()
            self._model = model

    async def ask(self, prompt: str, model: str) -> str:
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
        try:
            await self._ensure(model)
            await self._client.query(prompt)
            parts: list[str] = []
            async for msg in self._client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(msg, ResultMessage):
                    if getattr(msg, "is_error", False):
                        raw = (getattr(msg, "result", "") or "").lower()
                        if any(m in raw for m in _RATE_MARKERS):
                            raise RateLimited(raw[:200])
                        raise BrainError(raw[:200] or "result error")
            reply = "\n".join(p for p in parts if p.strip()).strip()
            if not reply:
                raise BrainError("빈 응답")
            return reply
        except (RateLimited, BrainError):
            raise
        except Exception as e:                      # noqa: BLE001 — SDK 오류 전부 BrainError로
            raw = str(e).lower()
            if any(m in raw for m in _RATE_MARKERS):
                await self.reset()                  # fatal 후 클라이언트 상태 불명 — 스트림 잔여물 제거
                raise RateLimited(str(e)[:200]) from e
            raise BrainError(str(e)[:200]) from e

    async def reset(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:                       # noqa: BLE001 — 리셋은 실패해도 진행
                log.exception("세션 disconnect 실패 (무시)")
            self._client = None
            self._model = None
