"""discord_bot 핸들러 — 페이크 brain/diary/메시지로 검증 (게이트웨이 미접속)."""
import asyncio
from types import SimpleNamespace

from bot.discord_bot import handle_message, handle_raw_delete


def run(coro):
    return asyncio.run(coro)


class FakeChannel:
    def __init__(self, id_):
        self.id = id_
        self.sent = []

    def typing(self):
        class _T:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *a):
                return False
        return _T()

    async def send(self, content):
        self.sent.append(content)


class FakeMessage:
    def __init__(self, content, channel, author_id=42, is_bot=False):
        self.content = content
        self.channel = channel
        self.author = SimpleNamespace(id=author_id, bot=is_bot,
                                      display_name="민수")
        self.id = 999
        self.created_at = __import__("datetime").datetime(2026, 7, 13)
        self.reactions = []

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)


class FakeBrain:
    def __init__(self, reply="응답"):
        self.reply = reply
        self.asked = []

    async def ask(self, prompt):
        self.asked.append(prompt)
        return self.reply


class FakeDiary:
    def __init__(self, fail=False):
        self.fail = fail
        self.added = []
        self.deleted = []

    async def add(self, content, mid, created):
        if self.fail:
            raise RuntimeError("blog down")
        self.added.append(content)

    async def delete_by_message(self, mid):
        self.deleted.append(mid)


def make_settings():
    return SimpleNamespace(assist_channel_id=111, diary_channel_id=222,
                           allowed_user_ids=frozenset({42}))


def test_assist_message_goes_to_brain():
    ch = FakeChannel(111)
    brain = FakeBrain("안녕!")
    run(handle_message(make_settings(), brain, FakeDiary(),
                       FakeMessage("hi", ch)))
    assert brain.asked == ["hi"]
    assert ch.sent == ["안녕!"]


def test_disallowed_user_ignored():
    ch = FakeChannel(111)
    brain = FakeBrain()
    run(handle_message(make_settings(), brain, FakeDiary(),
                       FakeMessage("hi", ch, author_id=666)))
    assert brain.asked == [] and ch.sent == []


def test_bot_message_ignored():
    ch = FakeChannel(111)
    brain = FakeBrain()
    run(handle_message(make_settings(), brain, FakeDiary(),
                       FakeMessage("hi", ch, is_bot=True)))
    assert brain.asked == []


def test_other_channel_ignored():
    ch = FakeChannel(333)
    brain = FakeBrain()
    run(handle_message(make_settings(), brain, FakeDiary(),
                       FakeMessage("hi", ch)))
    assert brain.asked == []


def test_diary_channel_records_and_reacts():
    ch = FakeChannel(222)
    diary = FakeDiary()
    msg = FakeMessage("오늘 일기", ch)
    run(handle_message(make_settings(), FakeBrain(), diary, msg))
    assert diary.added == ["오늘 일기"]
    assert msg.reactions == ["✅"]


def test_diary_failure_reacts_x():
    ch = FakeChannel(222)
    msg = FakeMessage("일기", ch)
    run(handle_message(make_settings(), FakeBrain(), FakeDiary(fail=True), msg))
    assert msg.reactions == ["❌"]


def test_brain_crash_sends_human_error():
    class Crashing:
        async def ask(self, prompt):
            raise RuntimeError("boom")
    ch = FakeChannel(111)
    run(handle_message(make_settings(), Crashing(), FakeDiary(),
                       FakeMessage("hi", ch)))
    assert len(ch.sent) == 1 and "boom" not in ch.sent[0]


def test_raw_delete_in_diary_channel():
    diary = FakeDiary()
    payload = SimpleNamespace(channel_id=222, message_id=77)
    run(handle_raw_delete(make_settings(), diary, payload))
    assert diary.deleted == [77]
