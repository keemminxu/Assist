"""5분마다 heartbeat 테이블 갱신. evening-checkin 루틴이 30분 무신호를 사망으로 판정."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 300


async def heartbeat_loop(supa, *, component: str = "discord-bot",
                         sleep=asyncio.sleep) -> None:
    while True:
        try:
            await supa.upsert(
                "heartbeat",
                {"component": component,
                 "last_seen": datetime.now(timezone.utc).isoformat()},
                on_conflict="component",
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:           # noqa: BLE001 — 신호 실패가 봇을 죽이면 안 됨
            log.warning("heartbeat 실패: %s", e)
        await sleep(INTERVAL_SECONDS)
