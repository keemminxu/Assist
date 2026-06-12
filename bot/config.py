"""환경변수 → Settings. .env는 로컬/서버 공통."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    assist_channel_id: int
    allowed_user_ids: frozenset[int]    # 비어 있으면 전원 허용
    supabase_url: str
    supabase_service_key: str
    claude_bin: str
    claude_model: str
    claude_fallback_model: str
    agent_dir: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            discord_token=os.environ["DISCORD_TOKEN"],
            assist_channel_id=int(os.environ["ASSIST_CHANNEL_ID"]),
            allowed_user_ids=frozenset(
                int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()),
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_service_key=os.environ["SUPABASE_SERVICE_KEY"],
            claude_bin=os.getenv("CLAUDE_BIN", "claude"),
            claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
            claude_fallback_model=os.getenv("CLAUDE_FALLBACK_MODEL", "haiku"),
            agent_dir=os.getenv("AGENT_DIR", "agent"),
        )
