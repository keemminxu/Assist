"""엔트리포인트 — 조립만 한다."""
from __future__ import annotations

import asyncio
import logging
from functools import partial

from bot.claude_runner import run_claude
from bot.config import Settings
from bot.conversation import Conversation
from bot.discord_bot import create_client
from bot.heartbeat import heartbeat_loop
from bot.supa import Supa


async def amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s = Settings.from_env()
    supa = Supa(s.supabase_url, s.supabase_service_key)
    runner = partial(run_claude, claude_bin=s.claude_bin, cwd=s.agent_dir)
    client = create_client(
        s,
        lambda: Conversation(runner=runner, model=s.claude_model,
                             fallback_model=s.claude_fallback_model),
    )
    asyncio.ensure_future(heartbeat_loop(supa))
    await client.start(s.discord_token)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
