"""scheduler — 결정적 시각 계산 + 루프(페이크 시계)."""
import asyncio
import random
from datetime import date, datetime, time

from bot.scheduler import KST, make_day_plan, run_loop


def test_day_plan_has_briefing_deadline_and_two_chances():
    plan = make_day_plan(date(2026, 7, 13), random.Random(1))
    kinds = [k for _, k in plan]
    assert kinds.count("briefing") == 1
    assert kinds.count("muse_deadline") == 1
    assert kinds.count("muse_chance") == 2
    assert plan == sorted(plan)                       # 시각순


def test_briefing_and_deadline_times():
    plan = dict((k, t) for t, k in make_day_plan(date(2026, 7, 13), random.Random(1))
                if k in ("briefing", "muse_deadline"))
    assert plan["briefing"].timetz().replace(tzinfo=None) == time(7, 30)
    assert plan["muse_deadline"].timetz().replace(tzinfo=None) == time(23, 0)


def test_muse_chances_within_window():
    for seed in range(20):
        for t, k in make_day_plan(date(2026, 7, 13), random.Random(seed)):
            if k == "muse_chance":
                assert time(10, 0) <= t.timetz().replace(tzinfo=None) <= time(22, 0)


def test_run_loop_fires_due_events_and_skips_past_on_start():
    fired = []
    # 09:59 기동 — 아침 브리핑(07:30)은 지났고, 아무말 기회(10:00~22:00)는 전부 미래
    clock = {"now": datetime(2026, 7, 13, 9, 59, tzinfo=KST)}
    ticks = {"n": 0}

    async def fake_sleep(sec):
        ticks["n"] += 1
        if ticks["n"] > 3:
            raise StopAsyncIteration                 # 루프 탈출용
        clock["now"] = clock["now"].replace(hour=22, minute=59)  # 기회 시각 다 지나감
        if ticks["n"] == 2:
            clock["now"] = clock["now"].replace(hour=23, minute=1)  # 마감 체크 지남

    async def handler(kind):
        fired.append(kind)

    handlers = {k: (lambda k=k: handler(k)) for k in
                ("briefing", "muse_chance", "muse_deadline")}

    async def scenario():
        try:
            await run_loop(handlers, now=lambda: clock["now"],
                           sleep=fake_sleep, rng=random.Random(1))
        except StopAsyncIteration:
            pass

    asyncio.run(scenario())
    assert "briefing" not in fired                   # 기동 전 지난 이벤트는 스킵
    assert fired.count("muse_chance") == 2           # 22:59 도달 시 due
    assert fired.count("muse_deadline") == 1         # 23:01 도달 시 due


def test_run_loop_handler_crash_does_not_kill_loop():
    clock = {"now": datetime(2026, 7, 13, 7, 29, tzinfo=KST)}
    ticks = {"n": 0}
    fired = []

    async def fake_sleep(sec):
        ticks["n"] += 1
        if ticks["n"] == 1:
            clock["now"] = clock["now"].replace(hour=7, minute=31)   # 브리핑 due
        if ticks["n"] > 2:
            raise StopAsyncIteration

    async def boom():
        fired.append("briefing")
        raise RuntimeError("fail")

    async def noop():
        pass

    handlers = {"briefing": boom, "muse_chance": noop, "muse_deadline": noop}

    async def scenario():
        try:
            await run_loop(handlers, now=lambda: clock["now"],
                           sleep=fake_sleep, rng=random.Random(1))
        except StopAsyncIteration:
            pass

    asyncio.run(scenario())                          # 예외로 죽지 않아야 함
    assert fired == ["briefing"]
