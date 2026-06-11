"""claude -p 헤드리스 호출. Max 구독 토큰(CLAUDE_CODE_OAUTH_TOKEN env)으로 인증."""
from __future__ import annotations

import asyncio
import json
import os
import sys


class ClaudeError(Exception):
    """claude CLI 호출 실패 (일반)."""


class RateLimited(ClaudeError):
    """구독 한도(429/limit) 도달."""


_RATE_MARKERS = ("429", "rate limit", "limit reached")


def _parse_result(returncode: int, stdout: str, stderr: str) -> tuple[str, str]:
    if returncode != 0:
        combined = f"{stdout}\n{stderr}".lower()
        if any(m in combined for m in _RATE_MARKERS):
            raise RateLimited(combined.strip()[:300])
        raise ClaudeError(combined.strip()[:300])
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"JSON 파싱 실패: {stdout[:200]}") from e
    if data.get("subtype") != "success":
        raise ClaudeError(f"비정상 종료: {data.get('subtype')}")
    return (data.get("result") or "").strip(), data["session_id"]


async def run_claude(
    prompt: str,
    *,
    session_id: str | None = None,
    model: str = "sonnet",
    claude_bin: str = "claude",
    cwd: str = "agent",
    timeout: float = 300.0,
) -> tuple[str, str]:
    """프롬프트를 보내고 (응답, session_id)를 반환. 세션 지정 시 이어서 대화."""
    cmd = [claude_bin, "-p", prompt,
           "--output-format", "json",
           "--model", model,
           "--dangerously-skip-permissions"]
    if session_id:
        cmd += ["--resume", session_id]
    env = {**os.environ, "ASSIST_PY": sys.executable}  # 비서가 db.py 호출 시 쓸 파이썬
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd, env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise ClaudeError(f"{timeout:.0f}초 안에 응답 없음")
    return _parse_result(proc.returncode or 0,
                         out.decode("utf-8", "replace"),
                         err.decode("utf-8", "replace"))
