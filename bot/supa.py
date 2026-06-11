"""Supabase PostgREST 얇은 비동기 클라이언트 (service role 키 사용)."""
from __future__ import annotations

import httpx


class Supa:
    def __init__(self, url: str, service_key: str, transport=None):
        self._client = httpx.AsyncClient(
            base_url=f"{url}/rest/v1",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            timeout=15.0,
            transport=transport,
        )

    async def upsert(self, table: str, row: dict, *, on_conflict: str) -> None:
        resp = await self._client.post(
            f"/{table}",
            params={"on_conflict": on_conflict},
            json=row,
            headers={"Prefer": "resolution=merge-duplicates"},
        )
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
