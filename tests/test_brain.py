"""Brain — 페이크 러너로 백오프·다운시프트·리셋 검증."""
import asyncio

from bot.brain import LIMIT_MESSAGE, Brain, BrainError, RateLimited


def run(coro):
    return asyncio.run(coro)


class FakeRunner:
    def __init__(self, script):
        """script: 호출마다 소비. 예외 인스턴스면 raise, 문자열이면 반환."""
        self.script = list(script)
        self.calls = []            # (prompt, model)
        self.resets = 0

    async def ask(self, prompt, model):
        self.calls.append((prompt, model))
        action = self.script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    async def reset(self):
        self.resets += 1


def make_brain(runner, sleeps):
    async def fake_sleep(sec):
        sleeps.append(sec)
    return Brain(runner, model="sonnet", fallback_model="haiku", sleep=fake_sleep)


def test_happy_path():
    r = FakeRunner(["안녕!"])
    assert run(make_brain(r, []).ask("hi")) == "안녕!"
    assert r.calls == [("hi", "sonnet")]


def test_rate_limit_backs_off_then_downshifts():
    r = FakeRunner([RateLimited("429"), RateLimited("429"), "폴백 응답"])
    sleeps = []
    out = run(make_brain(r, sleeps).ask("hi"))
    assert out == "폴백 응답"
    assert sleeps == [30, 90]                       # 백오프는 락 밖 sleep으로
    assert [m for _, m in r.calls] == ["sonnet", "sonnet", "haiku"]  # 3번째부터 다운시프트


def test_rate_limit_exhausts_to_limit_message():
    r = FakeRunner([RateLimited("x")] * 4)
    assert run(make_brain(r, []).ask("hi")) == LIMIT_MESSAGE


def test_generic_error_resets_session_and_retries_once():
    r = FakeRunner([BrainError("세션 손상"), "복구 응답"])
    out = run(make_brain(r, []).ask("hi"))
    assert out == "복구 응답"
    assert r.resets == 1


def test_generic_error_twice_returns_human_message():
    r = FakeRunner([BrainError("a"), BrainError("b")])
    out = run(make_brain(r, []).ask("hi"))
    assert "다시" in out                            # 사람 말 안내, 원문 노출 없음
    assert "a" not in out and "b" not in out


def test_reset_retry_rate_limited_continues_backoff():
    """리셋 재시도가 한도에 걸리면 백오프를 계속해 결국 성공한다."""
    r = FakeRunner([BrainError("x"), RateLimited("429"), RateLimited("429"), "ok"])
    sleeps = []
    out = run(make_brain(r, sleeps).ask("hi"))
    assert out == "ok"
    assert r.resets == 1                    # 리셋은 한 번만
    assert sleeps == [30, 90]               # 백오프 계속됨
    assert [m for _, m in r.calls] == ["sonnet", "sonnet", "sonnet", "haiku"]


def test_serial_queue_but_backoff_outside_lock():
    """첫 메시지가 백오프 대기 중일 때 두 번째 메시지가 끼어들 수 있다."""
    order = []

    class SlowRunner:
        def __init__(self):
            self.first = True

        async def ask(self, prompt, model):
            if prompt == "first" and self.first:
                self.first = False
                raise RateLimited("429")
            order.append(prompt)
            return f"ok:{prompt}"

        async def reset(self):
            pass

    async def scenario():
        release = asyncio.Event()

        async def gated_sleep(sec):
            await release.wait()   # 첫 메시지의 백오프를 인위로 붙잡는다

        brain = Brain(SlowRunner(), model="s", fallback_model="h", sleep=gated_sleep)
        t1 = asyncio.create_task(brain.ask("first"))
        await asyncio.sleep(0)     # t1이 1차 시도(실패) 후 백오프 대기에 들어가게
        t2 = asyncio.create_task(brain.ask("second"))
        await asyncio.sleep(0.01)
        assert order == ["second"]   # 백오프 동안 락이 풀려 second가 먼저 처리됨
        release.set()
        await asyncio.gather(t1, t2)

    run(scenario())
