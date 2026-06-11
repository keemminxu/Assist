"""채널 하나의 직렬 대화: 세션 유지 + 429 백오프 + 모델 다운시프트."""
from __future__ import annotations

import asyncio
import logging

from bot.claude_runner import ClaudeError, RateLimited

log = logging.getLogger(__name__)

_BACKOFFS = (0, 30, 90, 180)        # 시도 4회: 즉시, 30s, 90s, 180s
_DOWNSHIFT_FROM = 2                 # 3번째 시도(인덱스 2)부터 폴백 모델

LIMIT_MESSAGE = "지금 Claude 사용 한도에 걸려 있어요. 잠시 뒤에 다시 말 걸어주세요. 🙏"


class Conversation:
    def __init__(self, runner, *, model: str = "sonnet",
                 fallback_model: str = "haiku", sleep=asyncio.sleep):
        self._runner = runner
        self._model = model
        self._fallback = fallback_model
        self._sleep = sleep
        self._session_id: str | None = None
        self._lock = asyncio.Lock()     # 채널 내 직렬 처리

    async def ask(self, prompt: str) -> str:
        async with self._lock:
            for i, delay in enumerate(_BACKOFFS):
                if delay:
                    await self._sleep(delay)
                model = self._fallback if i >= _DOWNSHIFT_FROM else self._model
                try:
                    reply, sid = await self._runner(
                        prompt, session_id=self._session_id, model=model)
                    self._session_id = sid
                    return reply
                except RateLimited:
                    log.warning("rate limited (시도 %d/%d)", i + 1, len(_BACKOFFS))
                except ClaudeError as e:
                    log.error("claude 오류: %s", e)
                    return f"비서 두뇌 호출 중 오류가 났어요: {e}"
            return LIMIT_MESSAGE
