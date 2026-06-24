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
    user_labels: dict[int, str]         # discord id → 이름(민수/하늘). 발신자 헤더용
    supabase_url: str
    supabase_service_key: str
    claude_bin: str
    claude_model: str
    claude_fallback_model: str
    agent_dir: str
    diary_channel_id: int               # 0이면 코멘트 기능 비활성
    blog_supabase_url: str              # 빈 문자열이면 비활성
    blog_supabase_service_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            discord_token=os.environ["DISCORD_TOKEN"],
            assist_channel_id=int(os.environ["ASSIST_CHANNEL_ID"]),
            allowed_user_ids=frozenset(
                int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()),
            user_labels=cls._parse_user_labels(os.getenv("USER_LABELS", "")),
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_service_key=os.environ["SUPABASE_SERVICE_KEY"],
            claude_bin=os.getenv("CLAUDE_BIN", "claude"),
            claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
            claude_fallback_model=os.getenv("CLAUDE_FALLBACK_MODEL", "haiku"),
            agent_dir=os.getenv("AGENT_DIR", "agent"),
            diary_channel_id=int(os.getenv("DIARY_CHANNEL_ID", "0") or "0"),
            blog_supabase_url=os.getenv("BLOG_SUPABASE_URL", ""),
            blog_supabase_service_key=os.getenv("BLOG_SUPABASE_SERVICE_KEY", ""),
        )

    @staticmethod
    def _parse_user_labels(raw: str) -> dict[int, str]:
        """'<id>:민수,<id>:하늘' → {id: 이름}. 형식 안 맞는 항목은 무시."""
        labels: dict[int, str] = {}
        for pair in raw.split(","):
            uid, sep, name = pair.partition(":")
            uid, name = uid.strip(), name.strip()
            if sep and uid.isdigit() and name:
                labels[int(uid)] = name
        return labels
