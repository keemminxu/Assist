"""프롬프트 — 날짜 앵커가 실제로 박히는지만 검증."""
from datetime import date

from bot.prompts import MUSE_CHANCE, MUSE_DEADLINE, PERSONA, briefing_prompt


def test_briefing_prompt_anchors_today():
    p = briefing_prompt(date(2026, 7, 13))
    assert "2026-07-13" in p
    assert "뉴스" in p and "날씨" in p and "일정" in p


def test_persona_mentions_pippi():
    assert "삐삐" in PERSONA


def test_muse_prompts_exist():
    assert "muse_post" in MUSE_CHANCE and "muse_post" in MUSE_DEADLINE
