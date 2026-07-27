"""프롬프트 — 날짜 앵커, 그리고 muse(공개 블로그) 격리 규칙을 검증."""
from datetime import date

from bot.prompts import (MUSE_PERSONA, PERSONA, briefing_prompt,
                         muse_chance_prompt, muse_deadline_prompt)


def test_briefing_prompt_anchors_today():
    p = briefing_prompt(date(2026, 7, 13))
    assert "2026-07-13" in p
    assert "뉴스" in p and "날씨" in p and "일정" in p


def test_persona_mentions_pippi():
    assert "삐삐" in PERSONA


def test_persona_has_no_muse_material():
    """대화 페르소나에서 아무말 게시판 규칙이 사라져야 한다 — 대화 세션은 블로그에 못 쓴다."""
    assert "muse_post" not in PERSONA
    assert "아무말" not in PERSONA
    assert "diary_recent" not in PERSONA


def test_muse_persona_is_public_aware_and_bans_private_material():
    assert "삐삐" in MUSE_PERSONA
    assert "공개" in MUSE_PERSONA                     # 누구나 읽는 곳임을 인지
    assert "뉴스" in MUSE_PERSONA                     # 기본 소재
    for banned in ("민수", "대화", "일정", "일기", "메모"):    # 금지 조항에 명시
        assert banned in MUSE_PERSONA


def test_muse_persona_is_news_first_and_gates_weather():
    """날씨 도배 사고(2026-07 하순) 재발 방지 — 날씨는 특보급만, 상투적 도입 금지."""
    assert "특보급" in MUSE_PERSONA
    assert "평범한 날씨는 소재가 아니다" in MUSE_PERSONA
    assert "상투적 도입 금지" in MUSE_PERSONA


def test_muse_chance_prompt_anchors_today_and_allows_pass():
    p = muse_chance_prompt(date(2026, 7, 20))
    assert "2026-07-20" in p
    assert "muse_post" in p
    assert "패스" in p                                # 안 쓸 자유 유지


def test_muse_deadline_prompt_anchors_today():
    p = muse_deadline_prompt(date(2026, 7, 20))
    assert "2026-07-20" in p
    assert "muse_post" in p


def test_muse_prompts_push_news_not_weather_tool():
    """프롬프트가 weather 도구를 손쉬운 도피처로 권하면 안 된다."""
    for p in (muse_chance_prompt(date(2026, 7, 20)),
              muse_deadline_prompt(date(2026, 7, 20))):
        assert "뉴스" in p and "WebSearch" in p
        assert "weather" not in p


def test_muse_prompts_embed_recent_posts_for_dedup():
    recent = [{"content": "어제는 반도체 뉴스 얘기를 길게\n했다.",
               "created_at": "2026-07-26T22:25:00+00:00"}]   # UTC 밤 → KST로는 다음날
    for fn in (muse_chance_prompt, muse_deadline_prompt):
        p = fn(date(2026, 7, 27), recent)
        assert "어제는 반도체 뉴스 얘기를 길게 했다." in p   # 줄바꿈은 한 줄로 접힘
        assert "[2026-07-27]" in p                           # KST 날짜로 표기
        assert "겹" in p                                     # 겹침 금지 지시


def test_muse_prompts_handle_empty_recent():
    p = muse_chance_prompt(date(2026, 7, 20), [])
    assert "최근 올라간 글 없음" in p


def test_muse_prompts_never_point_at_private_sources():
    """muse 프롬프트가 대화·일기 같은 사적 소재를 가리키면 안 된다."""
    for p in (muse_chance_prompt(date(2026, 7, 20)),
              muse_deadline_prompt(date(2026, 7, 20)),
              MUSE_PERSONA):
        assert "diary_recent" not in p
        assert "gcal" not in p
        assert "memo_" not in p
