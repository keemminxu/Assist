from bot.claude_runner import ClaudeError, RateLimited
from bot.conversation import Conversation


async def test_keeps_session_between_asks():
    calls = []

    async def fake_runner(prompt, *, session_id=None, model=None):
        calls.append((prompt, session_id, model))
        return f"re:{prompt}", "sess-1"

    c = Conversation(runner=fake_runner)
    assert await c.ask("안녕") == "re:안녕"
    assert await c.ask("뭐해") == "re:뭐해"
    assert calls[0][1] is None
    assert calls[1][1] == "sess-1"      # 두 번째부터 세션 이어받기


async def test_rate_limit_backs_off_then_downshifts():
    sleeps, attempts = [], []

    async def fake_sleep(s):
        sleeps.append(s)

    async def fake_runner(prompt, *, session_id=None, model=None):
        attempts.append(model)
        if len(attempts) < 3:
            raise RateLimited("429")
        return "ok", "s"

    c = Conversation(runner=fake_runner, model="sonnet",
                     fallback_model="haiku", sleep=fake_sleep)
    assert await c.ask("hi") == "ok"
    assert sleeps == [30, 90]
    assert attempts == ["sonnet", "sonnet", "haiku"]


async def test_exhausted_rate_limit_returns_friendly_message():
    async def fake_runner(prompt, *, session_id=None, model=None):
        raise RateLimited("429")

    async def fake_sleep(s):
        pass

    c = Conversation(runner=fake_runner, sleep=fake_sleep)
    reply = await c.ask("hi")
    assert "한도" in reply


async def test_claude_error_returns_error_message_without_retry():
    count = 0

    async def fake_runner(prompt, *, session_id=None, model=None):
        nonlocal count
        count += 1
        raise ClaudeError("boom")

    c = Conversation(runner=fake_runner)
    reply = await c.ask("hi")
    assert "오류" in reply
    assert count == 1
