import httpx

from bot.supa import Supa


def make_supa(handler):
    return Supa("https://x.supabase.co", "secret-key",
                transport=httpx.MockTransport(handler))


async def test_upsert_targets_table_with_merge_duplicates():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["prefer"] = request.headers.get("Prefer")
        captured["apikey"] = request.headers.get("apikey")
        return httpx.Response(201, json=[])

    supa = make_supa(handler)
    await supa.upsert("heartbeat",
                      {"component": "bot", "last_seen": "2026-06-11T00:00:00Z"},
                      on_conflict="component")
    assert "/rest/v1/heartbeat" in captured["url"]
    assert "on_conflict=component" in captured["url"]
    assert captured["prefer"] == "resolution=merge-duplicates"
    assert captured["apikey"] == "secret-key"


async def test_upsert_raises_on_http_error():
    def handler(request):
        return httpx.Response(500, json={"message": "boom"})

    supa = make_supa(handler)
    try:
        await supa.upsert("heartbeat", {"component": "bot"}, on_conflict="component")
        assert False, "예외가 나야 함"
    except httpx.HTTPStatusError:
        pass
