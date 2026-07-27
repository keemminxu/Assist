"""desk(memos)·blog(bot_muse/daily_logs) Supabase PostgREST 얇은 비동기 클라이언트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))


def _client(url: str, service_key: str, transport=None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{url}/rest/v1",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
        timeout=15.0,
        transport=transport,
    )


class MemoStore:
    """desk DB memos 테이블 CRUD."""

    def __init__(self, url: str, service_key: str, transport=None):
        self._c = _client(url, service_key, transport)

    async def add(self, content: str) -> dict:
        resp = await self._c.post("/memos", json={"content": content},
                                  headers={"Prefer": "return=representation"})
        resp.raise_for_status()
        return resp.json()[0]

    async def list(self) -> list[dict]:
        resp = await self._c.get("/memos", params={
            "select": "id,content,created_at", "order": "id.asc"})
        resp.raise_for_status()
        return resp.json()

    async def update(self, memo_id: int, content: str) -> bool:
        resp = await self._c.patch("/memos", params={"id": f"eq.{memo_id}"},
                                   json={"content": content},
                                   headers={"Prefer": "return=representation"})
        resp.raise_for_status()
        return bool(resp.json())

    async def delete(self, memo_id: int) -> bool:
        resp = await self._c.delete("/memos", params={"id": f"eq.{memo_id}"},
                                    headers={"Prefer": "return=representation"})
        resp.raise_for_status()
        return bool(resp.json())

    async def aclose(self) -> None:
        await self._c.aclose()


class MuseStore:
    """blog DB — bot_muse 쓰기/카운트 + daily_logs 읽기(아무말 소재)."""

    def __init__(self, url: str, service_key: str, transport=None,
                 now=lambda: datetime.now(KST)):
        self._c = _client(url, service_key, transport)
        self._now = now

    async def count_today(self) -> int:
        start = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
        resp = await self._c.get("/bot_muse", params={
            "select": "id", "created_at": f"gte.{start.isoformat()}"})
        resp.raise_for_status()
        return len(resp.json())

    async def post(self, content: str) -> None:
        resp = await self._c.post("/bot_muse", json={"content": content},
                                  headers={"Prefer": "return=minimal"})
        resp.raise_for_status()

    async def recent_posts(self, n: int = 8) -> list[dict]:
        """최근 공개 글 — muse 프롬프트에 실어 소재·첫 문장 반복을 막는다."""
        resp = await self._c.get("/bot_muse", params={
            "select": "content,created_at", "order": "created_at.desc", "limit": str(n)})
        resp.raise_for_status()
        return resp.json()

    async def recent_diary(self, n: int = 5) -> list[dict]:
        resp = await self._c.get("/daily_logs", params={
            "select": "content,created_at", "order": "created_at.desc", "limit": str(n)})
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._c.aclose()
