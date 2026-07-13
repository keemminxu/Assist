"""GCal — 매칭·종일 보정·포맷. httpx.MockTransport 사용 (google-auth 안 거침)."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from bot.gcal import (KST, AmbiguousMatch, GCal, GcalError, NoMatch,
                      fmt_event, match_events, next_day)


def make_gcal(handler, cal_ids=("me@gmail.com",)):
    return GCal(cal_ids, token_provider=lambda: "tok",
                transport=httpx.MockTransport(handler),
                now=lambda: datetime(2026, 7, 13, 9, 0, tzinfo=KST))


def timed(id_, title, start_iso, end_iso):
    return {"id": id_, "summary": title,
            "start": {"dateTime": start_iso}, "end": {"dateTime": end_iso}}


def test_next_day_for_all_day_end_exclusive():
    assert next_day("2026-07-13") == "2026-07-14"


def test_fmt_event_all_day():
    ev = {"id": "x", "summary": "여행", "start": {"date": "2026-07-20"},
          "end": {"date": "2026-07-21"}}
    assert fmt_event(ev) == "2026-07-20 종일  여행"


def test_match_by_title_substring_case_insensitive():
    events = [timed("a", "치과 예약", "2026-07-14T15:00:00+09:00", "2026-07-14T16:00:00+09:00"),
              timed("b", "회식", "2026-07-14T19:00:00+09:00", "2026-07-14T20:00:00+09:00")]
    got = match_events(events, title="치과")
    assert [e["id"] for e in got] == ["a"]


def test_match_narrows_by_start_time():
    events = [timed("a", "치과", "2026-07-14T15:00:00+09:00", "2026-07-14T16:00:00+09:00"),
              timed("b", "치과", "2026-07-21T15:00:00+09:00", "2026-07-21T16:00:00+09:00")]
    got = match_events(events, title="치과", start="2026-07-21T15:00")
    assert [e["id"] for e in got] == ["b"]


def test_agenda_formats_sorted_lines():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"items": [
            timed("a", "회식", "2026-07-14T19:00:00+09:00", "2026-07-14T20:00:00+09:00"),
            timed("b", "치과", "2026-07-14T15:00:00+09:00", "2026-07-14T16:00:00+09:00")]})
    out = make_gcal(handler).agenda(days=1)
    lines = out.splitlines()
    assert "치과" in lines[0] and "회식" in lines[1]   # 시간순 정렬


def test_agenda_empty():
    out = make_gcal(lambda r: httpx.Response(200, json={"items": []})).agenda(days=3)
    assert "일정 없음" in out


def test_add_all_day_uses_end_exclusive():
    captured = {}
    def handler(request):
        if request.method == "POST":
            import json as j
            captured.update(j.loads(request.content))
            return httpx.Response(200, json={"id": "n", "summary": "여행",
                                             "start": {"date": "2026-07-20"},
                                             "end": {"date": "2026-07-21"}})
        return httpx.Response(200, json={"items": []})
    out = make_gcal(handler).add("여행", start="2026-07-20")
    assert captured["end"] == {"date": "2026-07-21"}
    assert "등록됨" in out


def test_add_timed_defaults_one_hour():
    captured = {}
    def handler(request):
        import json as j
        captured.update(j.loads(request.content))
        return httpx.Response(200, json=timed("n", "치과", "2026-07-14T15:00:00+09:00",
                                              "2026-07-14T16:00:00+09:00"))
    make_gcal(handler).add("치과", start="2026-07-14T15:00")
    assert captured["start"]["dateTime"] == "2026-07-14T15:00:00"
    assert captured["end"]["dateTime"] == "2026-07-14T16:00:00"


def test_delete_no_match_raises():
    with pytest.raises(NoMatch):
        make_gcal(lambda r: httpx.Response(200, json={"items": []})).delete("치과")


def test_delete_ambiguous_raises_with_candidates():
    def handler(request):
        return httpx.Response(200, json={"items": [
            timed("a", "치과", "2026-07-14T15:00:00+09:00", "2026-07-14T16:00:00+09:00"),
            timed("b", "치과", "2026-07-21T15:00:00+09:00", "2026-07-21T16:00:00+09:00")]})
    with pytest.raises(AmbiguousMatch) as ei:
        make_gcal(handler).delete("치과")
    assert len(ei.value.candidates) == 2


def test_update_moves_event():
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "PATCH":
            return httpx.Response(200, json=timed("a", "치과", "2026-07-15T16:00:00+09:00",
                                                  "2026-07-15T17:00:00+09:00"))
        return httpx.Response(200, json={"items": [
            timed("a", "치과", "2026-07-14T15:00:00+09:00", "2026-07-14T16:00:00+09:00")]})
    out = make_gcal(handler).update("치과", new_start="2026-07-15T16:00", new_end="2026-07-15T17:00")
    assert ("PATCH", "/calendar/v3/calendars/me@gmail.com/events/a") in calls
    assert "변경됨" in out


def test_update_move_preserves_duration():
    captured = {}
    def handler(request):
        if request.method == "PATCH":
            import json as j
            captured.update(j.loads(request.content))
            return httpx.Response(200, json=timed("a", "치과", "2026-07-15T16:00:00+09:00",
                                                  "2026-07-15T18:00:00+09:00"))
        return httpx.Response(200, json={"items": [
            timed("a", "치과", "2026-07-14T15:00:00+09:00", "2026-07-14T17:00:00+09:00")]})
    make_gcal(handler).update("치과", new_start="2026-07-15T16:00")
    assert captured["end"]["dateTime"] == "2026-07-15T18:00:00"   # 원본 2시간 유지


def test_update_allday_to_timed_clears_date():
    captured = {}
    def handler(request):
        if request.method == "PATCH":
            import json as j
            captured.update(j.loads(request.content))
            return httpx.Response(200, json=timed("a", "여행", "2026-07-20T10:00:00+09:00",
                                                  "2026-07-20T11:00:00+09:00"))
        return httpx.Response(200, json={"items": [
            {"id": "a", "summary": "여행", "start": {"date": "2026-07-20"},
             "end": {"date": "2026-07-21"}}]})
    make_gcal(handler).update("여행", new_start="2026-07-20T10:00")
    assert "date" in captured["start"] and captured["start"]["date"] is None
    assert "date" in captured["end"] and captured["end"]["date"] is None


def test_list_paginates():
    def handler(request):
        token = request.url.params.get("pageToken")
        if token is None:
            return httpx.Response(200, json={
                "items": [timed("a", "치과", "2026-07-14T15:00:00+09:00",
                                "2026-07-14T16:00:00+09:00")],
                "nextPageToken": "p2"})
        assert token == "p2"
        return httpx.Response(200, json={
            "items": [timed("b", "회식", "2026-07-14T19:00:00+09:00",
                            "2026-07-14T20:00:00+09:00")]})
    out = make_gcal(handler).agenda(days=1)
    assert "치과" in out and "회식" in out


def test_api_error_raises_gcal_error():
    with pytest.raises(GcalError):
        make_gcal(lambda r: httpx.Response(400, json={"error": "bad"})).agenda(days=1)
