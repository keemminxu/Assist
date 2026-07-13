"""MemoStore/MuseStore — MockTransport로 PostgREST 요청 검증."""
import asyncio
import json
from datetime import datetime

import httpx
import pytest

from bot.store import KST, MemoStore, MuseStore


def run(coro):
    return asyncio.run(coro)


def make_transport(record, response_json=None, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        record.append(request)
        return httpx.Response(status, json=response_json if response_json is not None else [])
    return httpx.MockTransport(handler)


def test_memo_add_posts_content_and_returns_row():
    reqs = []
    store = MemoStore("https://d.supabase.co", "k",
                      transport=make_transport(reqs, [{"id": 1, "content": "우유"}]))
    row = run(store.add("우유"))
    assert row["id"] == 1
    assert reqs[0].method == "POST"
    assert reqs[0].url.path == "/rest/v1/memos"
    assert json.loads(reqs[0].content) == {"content": "우유"}


def test_memo_list_orders_by_id():
    reqs = []
    store = MemoStore("https://d.supabase.co", "k",
                      transport=make_transport(reqs, [{"id": 1, "content": "우유"}]))
    rows = run(store.list())
    assert rows[0]["content"] == "우유"
    assert reqs[0].url.params["order"] == "id.asc"


def test_memo_update_returns_false_when_id_missing():
    store = MemoStore("https://d.supabase.co", "k",
                      transport=make_transport([], []))   # PostgREST: 매칭 0건이면 빈 배열
    assert run(store.update(999, "새 내용")) is False


def test_memo_delete_returns_true_when_deleted():
    reqs = []
    store = MemoStore("https://d.supabase.co", "k",
                      transport=make_transport(reqs, [{"id": 3}]))
    assert run(store.delete(3)) is True
    assert reqs[0].method == "DELETE"
    assert reqs[0].url.params["id"] == "eq.3"


def test_memo_add_raises_on_http_error():
    store = MemoStore("https://d.supabase.co", "k",
                      transport=make_transport([], {"message": "boom"}, status=500))
    with pytest.raises(httpx.HTTPStatusError):
        run(store.add("우유"))


def test_sends_service_key_headers():
    reqs = []
    store = MemoStore("https://d.supabase.co", "service-key",
                      transport=make_transport(reqs, []))
    run(store.list())
    assert reqs[0].headers["apikey"] == "service-key"
    assert reqs[0].headers["Authorization"] == "Bearer service-key"


def test_muse_count_today_uses_kst_midnight():
    fixed_now = datetime(2026, 7, 13, 15, 0, tzinfo=KST)
    reqs = []
    store = MuseStore("https://b.supabase.co", "k",
                      transport=make_transport(reqs, [{"id": 1}, {"id": 2}]),
                      now=lambda: fixed_now)
    assert run(store.count_today()) == 2
    assert reqs[0].url.params["created_at"] == "gte.2026-07-13T00:00:00+09:00"


def test_muse_post_inserts_content():
    reqs = []
    store = MuseStore("https://b.supabase.co", "k", transport=make_transport(reqs, []))
    run(store.post("오늘의 아무말"))
    assert json.loads(reqs[0].content) == {"content": "오늘의 아무말"}


def test_recent_diary_limits_and_orders_desc():
    reqs = []
    store = MuseStore("https://b.supabase.co", "k",
                      transport=make_transport(reqs, [{"content": "일기"}]))
    rows = run(store.recent_diary(3))
    assert rows == [{"content": "일기"}]
    assert reqs[0].url.params["limit"] == "3"
    assert reqs[0].url.params["order"] == "created_at.desc"
