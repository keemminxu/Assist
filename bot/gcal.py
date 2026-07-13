"""Google Calendar 클라이언트 — v3 scripts/gcal.py 이식(1인용 단순화) + update·제목매칭 신설.

동기(sync) 클라이언트다. 도구 레이어(tools.py)에서 asyncio.to_thread로 감싼다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/calendar/v3"
MATCH_WINDOW_DAYS = 60


class GcalError(RuntimeError):
    """Calendar API 오류."""


class NoMatch(GcalError):
    """매칭되는 일정 없음."""


class AmbiguousMatch(GcalError):
    """복수 매칭 — 실행하지 않고 후보를 되묻는다."""

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__("복수 매칭")


def _norm_dt(value: str) -> str:
    """YYYY-MM-DDTHH:MM → 초 붙여 RFC3339로 정규화."""
    if "T" in value and len(value) == 16:
        return value + ":00"
    return value


def next_day(date_str: str) -> str:
    """종일 일정 end는 exclusive — 하루짜리면 다음날을 end로."""
    return (datetime.fromisoformat(date_str) + timedelta(days=1)).date().isoformat()


def fmt_event(ev: dict) -> str:
    start, end = ev.get("start", {}), ev.get("end", {})
    if "date" in start:
        when = f"{start['date']} 종일"
    else:
        s = datetime.fromisoformat(start["dateTime"]).astimezone(KST)
        e = datetime.fromisoformat(end["dateTime"]).astimezone(KST)
        when = f"{s:%Y-%m-%d %H:%M}~{e:%H:%M}"
    return f"{when}  {ev.get('summary', '(제목 없음)')}"


def _start_key(ev: dict) -> str:
    return ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "")


def match_events(events: list[dict], *, title: str, start: str | None = None) -> list[dict]:
    """제목 부분일치(대소문자 무시), start가 있으면 시작 시각까지 일치해야 함."""
    got = [e for e in events if title.casefold() in e.get("summary", "").casefold()]
    if start:
        want = datetime.fromisoformat(_norm_dt(start))
        if want.tzinfo is None:
            want = want.replace(tzinfo=KST)
        def same_start(ev):
            raw = ev.get("start", {}).get("dateTime")
            if raw is None:
                return ev.get("start", {}).get("date") == start
            return datetime.fromisoformat(raw) == want
        got = [e for e in got if same_start(e)]
    return got


class GCal:
    def __init__(self, cal_ids, token_provider, transport=None,
                 now=lambda: datetime.now(KST)):
        self._ids = list(cal_ids)
        self._token = token_provider
        self._transport = transport
        self._now = now

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=API, timeout=15.0, transport=self._transport,
                            headers={"Authorization": f"Bearer {self._token()}"})

    def _check(self, resp: httpx.Response) -> None:
        if resp.is_error:
            raise GcalError(f"Calendar API {resp.status_code}: {resp.text[:200]}")

    def _list(self, c: httpx.Client, days: int) -> list[tuple[str, dict]]:
        now = self._now()
        out: list[tuple[str, dict]] = []
        for cal in self._ids:
            resp = c.get(f"/calendars/{cal}/events", params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(days=days)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime", "maxResults": "100",
            })
            self._check(resp)
            out += [(cal, ev) for ev in resp.json().get("items", [])]
        return out

    def agenda(self, days: int = 7) -> str:
        with self._client() as c:
            items = self._list(c, days)
        if not items:
            return f"앞으로 {days}일간 일정 없음"
        return "\n".join(fmt_event(ev) for _, ev in
                         sorted(items, key=lambda p: _start_key(p[1])))

    def add(self, title: str, start: str, end: str | None = None,
            description: str | None = None) -> str:
        all_day = "T" not in start
        if all_day:
            body = {"summary": title, "start": {"date": start},
                    "end": {"date": end or next_day(start)}}
        else:
            if end is None:
                s = datetime.fromisoformat(_norm_dt(start))
                end = (s + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
            body = {"summary": title,
                    "start": {"dateTime": _norm_dt(start), "timeZone": "Asia/Seoul"},
                    "end": {"dateTime": _norm_dt(end), "timeZone": "Asia/Seoul"}}
        if description:
            body["description"] = description
        with self._client() as c:
            resp = c.post(f"/calendars/{self._ids[0]}/events", json=body)
            self._check(resp)
        return f"등록됨: {fmt_event(resp.json())}"

    def _find(self, c: httpx.Client, title: str, start: str | None) -> tuple[str, dict]:
        matched = [(cal, ev) for cal, ev in self._list(c, MATCH_WINDOW_DAYS)
                   if match_events([ev], title=title, start=start)]
        if not matched:
            raise NoMatch(f"'{title}' 일정을 못 찾음 (앞으로 {MATCH_WINDOW_DAYS}일 안에 없음)")
        if len(matched) > 1:
            raise AmbiguousMatch([fmt_event(ev) for _, ev in matched])
        return matched[0]

    def update(self, title: str, start: str | None = None, *,
               new_title: str | None = None, new_start: str | None = None,
               new_end: str | None = None) -> str:
        with self._client() as c:
            cal, ev = self._find(c, title, start)
            body: dict = {}
            if new_title:
                body["summary"] = new_title
            if new_start:
                if "T" in new_start:
                    if new_end is None:
                        s = datetime.fromisoformat(_norm_dt(new_start))
                        new_end = (s + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
                    body["start"] = {"dateTime": _norm_dt(new_start), "timeZone": "Asia/Seoul"}
                    body["end"] = {"dateTime": _norm_dt(new_end), "timeZone": "Asia/Seoul"}
                else:
                    body["start"] = {"date": new_start}
                    body["end"] = {"date": new_end or next_day(new_start)}
            if not body:
                return "바꿀 내용이 없어요 (new_title/new_start 중 하나는 필요)"
            resp = c.patch(f"/calendars/{cal}/events/{ev['id']}", json=body)
            self._check(resp)
        return f"변경됨: {fmt_event(resp.json())}"

    def delete(self, title: str, start: str | None = None) -> str:
        with self._client() as c:
            cal, ev = self._find(c, title, start)
            resp = c.delete(f"/calendars/{cal}/events/{ev['id']}")
            self._check(resp)
        return f"삭제됨: {fmt_event(ev)}"


def make_token_provider(key_path: str):
    """서비스 계정 키 → 액세스 토큰 provider (만료 시 자동 갱신)."""
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/calendar"])

    def provider() -> str:
        if not creds.valid:
            creds.refresh(GoogleRequest())
        return creds.token

    return provider
