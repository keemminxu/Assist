"""환경변수 → Settings. ALLOWED_USER_IDS가 비면 기동 거부 (fail-closed)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """기동을 막아야 하는 설정 오류."""


@dataclass(frozen=True)
class Settings:
    discord_token: str
    assist_channel_id: int
    diary_channel_id: int
    allowed_user_ids: frozenset[int]
    supabase_url: str                # desk — memos
    supabase_service_key: str
    blog_supabase_url: str           # blog — daily_logs, bot_muse
    blog_supabase_service_key: str
    gcal_ids: tuple[str, ...]
    gcal_sa_key: str
    claude_model: str
    claude_fallback_model: str
    weather_lat: float
    weather_lon: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        if env is None:
            load_dotenv()
            env = os.environ
        allowed = frozenset(
            int(x) for x in env.get("ALLOWED_USER_IDS", "").split(",") if x.strip())
        if not allowed:
            raise ConfigError(
                "ALLOWED_USER_IDS가 비어 있음 — 허용 사용자 없이는 기동하지 않는다 (fail-closed)")
        return cls(
            discord_token=env["DISCORD_TOKEN"],
            assist_channel_id=int(env["ASSIST_CHANNEL_ID"]),
            diary_channel_id=int(env["DIARY_CHANNEL_ID"]),
            allowed_user_ids=allowed,
            supabase_url=env["SUPABASE_URL"],
            supabase_service_key=env["SUPABASE_SERVICE_KEY"],
            blog_supabase_url=env["BLOG_SUPABASE_URL"],
            blog_supabase_service_key=env["BLOG_SUPABASE_SERVICE_KEY"],
            gcal_ids=tuple(c.strip() for c in env["GCAL_IDS"].split(",") if c.strip()),
            gcal_sa_key=env.get("GCAL_SA_KEY", ".gcal-sa.json"),
            claude_model=env.get("CLAUDE_MODEL", "sonnet"),
            claude_fallback_model=env.get("CLAUDE_FALLBACK_MODEL", "haiku"),
            weather_lat=float(env.get("WEATHER_LAT", "37.57")),
            weather_lon=float(env.get("WEATHER_LON", "126.98")),
        )
