"""Blog Supabase의 daily_logs에 일기를 기록/삭제 (service role 키).

#코멘트 채널 메시지를 그대로 블로그 일기 피드로 보낸다. assist의 desk 프로젝트가
아니라 블로그 전용 Supabase(mnatdbpscbvhhsxstvaq)에 쓴다.
"""
from __future__ import annotations

import httpx


class Diary:
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

    async def add(self, content: str, discord_message_id, created_at: str) -> None:
        resp = await self._client.post(
            "/daily_logs",
            json={
                "content": content,
                "discord_message_id": str(discord_message_id),
                "created_at": created_at,
            },
            headers={"Prefer": "return=minimal"},
        )
        resp.raise_for_status()

    async def delete_by_message(self, discord_message_id) -> None:
        resp = await self._client.delete(
            "/daily_logs",
            params={"discord_message_id": f"eq.{discord_message_id}"},
        )
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
