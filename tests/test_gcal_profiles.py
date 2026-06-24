import pytest

from scripts.gcal import WIFE_NOT_CONNECTED, _resolve_cal_ids

MINSU = ["m@personal", "fam@group.calendar.google.com"]
WIFE = ["w@personal"]


def test_minsu_is_default_profile():
    assert _resolve_cal_ids("minsu", MINSU, WIFE) == MINSU


def test_wife_returns_only_wife_ids():
    assert _resolve_cal_ids("wife", MINSU, WIFE) == WIFE


def test_wife_unconnected_raises_with_guidance():
    with pytest.raises(SystemExit) as e:
        _resolve_cal_ids("wife", MINSU, [])
    assert "연결" in str(e.value)
    assert "연결" in WIFE_NOT_CONNECTED


def test_all_merges_and_dedups_shared_family_calendar():
    wife_with_dupe = ["w@personal", "fam@group.calendar.google.com"]
    merged = _resolve_cal_ids("all", MINSU, wife_with_dupe)
    assert merged == ["m@personal", "fam@group.calendar.google.com", "w@personal"]


def test_all_falls_back_to_minsu_when_wife_empty():
    assert _resolve_cal_ids("all", MINSU, []) == MINSU


def test_family_returns_only_group_calendars():
    # 가족(@group) 캘린더만 골라낸다 — 에이전트가 ID를 몰라도 됨
    assert _resolve_cal_ids("family", MINSU, WIFE) == ["fam@group.calendar.google.com"]


def test_family_raises_when_no_group_calendar():
    with pytest.raises(SystemExit) as e:
        _resolve_cal_ids("family", ["m@personal"], WIFE)
    assert "가족" in str(e.value)
