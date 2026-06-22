import httpx

from bot.diary import Diary


def make_diary(handler):
    return Diary("https://blog.supabase.co", "blog-service-key",
                 transport=httpx.MockTransport(handler))


async def test_add_posts_content_message_id_and_time():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["apikey"] = request.headers.get("apikey")
        captured["prefer"] = request.headers.get("Prefer")
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=[])

    d = make_diary(handler)
    await d.add("오늘 비 온다", "12345", "2026-06-22T16:48:00+09:00")
    assert captured["method"] == "POST"
    assert "/daily_logs" in captured["url"]
    assert captured["apikey"] == "blog-service-key"
    assert captured["prefer"] == "return=minimal"
    assert captured["body"] == {
        "content": "오늘 비 온다",
        "discord_message_id": "12345",
        "created_at": "2026-06-22T16:48:00+09:00",
    }


async def test_delete_uses_eq_filter_on_message_id():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(204)

    d = make_diary(handler)
    await d.delete_by_message("98765")
    assert captured["method"] == "DELETE"
    assert "/daily_logs" in captured["url"]
    assert "discord_message_id=eq.98765" in captured["url"]


async def test_add_raises_on_http_error():
    def handler(request):
        return httpx.Response(500, json={"message": "boom"})

    d = make_diary(handler)
    try:
        await d.add("x", "1", "2026-06-22T00:00:00+09:00")
        assert False, "예외가 나야 함"
    except httpx.HTTPStatusError:
        pass
