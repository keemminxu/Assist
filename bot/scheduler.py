"""하루 이벤트 스케줄러 — 아침 브리핑(07:30) + 아무말 기회 2회(랜덤) + 마감 체크(23:00).

모든 시각은 KST. 기동 시점보다 과거인 이벤트는 스킵한다(재시작 시 중복 발화 방지).
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime, time, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
BRIEFING_AT = time(7, 30)
MUSE_DEADLINE_AT = time(23, 0)
MUSE_WINDOW = (time(10, 0), time(22, 0))
TICK_SECONDS = 30


def make_day_plan(day: date, rng: random.Random) -> list[tuple[datetime, str]]:
    events = [
        (datetime.combine(day, BRIEFING_AT, KST), "briefing"),
        (datetime.combine(day, MUSE_DEADLINE_AT, KST), "muse_deadline"),
    ]
    lo = datetime.combine(day, MUSE_WINDOW[0], KST)
    hi = datetime.combine(day, MUSE_WINDOW[1], KST)
    span = int((hi - lo).total_seconds())
    for _ in range(2):
        t = lo + timedelta(seconds=rng.randint(0, span))
        events.append((t.replace(second=0, microsecond=0), "muse_chance"))
    return sorted(events)


async def run_loop(handlers, *, now=lambda: datetime.now(KST),
                   sleep=asyncio.sleep, rng: random.Random | None = None) -> None:
    """handlers: {"briefing"|"muse_chance"|"muse_deadline": async 콜러블}."""
    rng = rng or random.Random()
    plan: list[tuple[datetime, str]] = []
    plan_day: date | None = None
    while True:
        n = now()
        if plan_day != n.date():
            plan_day = n.date()
            plan = [e for e in make_day_plan(plan_day, rng) if e[0] > n]
            log.info("오늘 스케줄: %s",
                     ", ".join(f"{t:%H:%M} {k}" for t, k in plan) or "(남은 이벤트 없음)")
        due = [e for e in plan if e[0] <= n]
        plan = [e for e in plan if e[0] > n]
        for _, kind in due:
            try:
                await handlers[kind]()
            except Exception:                        # noqa: BLE001 — 루프는 죽지 않는다
                log.exception("스케줄 이벤트 실패: %s", kind)
        await sleep(TICK_SECONDS)
