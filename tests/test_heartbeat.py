import asyncio

import pytest

from bot.heartbeat import heartbeat_loop


async def test_upserts_then_sleeps_each_cycle():
    rows = []

    class FakeSupa:
        async def upsert(self, table, row, *, on_conflict):
            rows.append((table, row["component"], on_conflict))

    ticks = 0

    async def fake_sleep(seconds):
        nonlocal ticks
        assert seconds == 300
        ticks += 1
        if ticks >= 3:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await heartbeat_loop(FakeSupa(), sleep=fake_sleep)
    assert rows == [("heartbeat", "discord-bot", "component")] * 3


async def test_upsert_failure_does_not_kill_loop():
    calls = 0

    class FlakySupa:
        async def upsert(self, table, row, *, on_conflict):
            nonlocal calls
            calls += 1
            raise RuntimeError("db down")

    ticks = 0

    async def fake_sleep(seconds):
        nonlocal ticks
        ticks += 1
        if ticks >= 2:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await heartbeat_loop(FlakySupa(), sleep=fake_sleep)
    assert calls == 2       # 실패해도 다음 주기 계속
