#!/usr/bin/env python3
"""비서(Claude)가 Bash로 호출하는 Google Calendar CLI (서비스 계정 인증).

사전 조건: 각 캘린더를 서비스 계정 이메일에 "일정 변경" 권한으로 공유해야 함.
대상 캘린더 ID는 .env의 GCAL_IDS (민수, 쉼표 구분, 첫 번째가 기본) / GCAL_IDS_WIFE (하늘).

캘린더 프로파일(--who): minsu(기본)=민수 / wife=하늘 / family=부부 공동(@group) / all=전체 조회.
하늘 캘린더(GCAL_IDS_WIFE)가 아직 비어 있으면 --who wife는 안내만 하고 종료(미리 세팅).
add/delete에서 --who all은 대상이 모호하므로 거부(조회 전용). 등록은 minsu|wife|family.

사용 예:
  python scripts/gcal.py agenda                 # 민수, 오늘부터 7일
  python scripts/gcal.py agenda --days 1        # 민수, 오늘만
  python scripts/gcal.py agenda --who wife       # 하늘 일정만
  python scripts/gcal.py agenda --who all        # 민수+하늘 합쳐서
  python scripts/gcal.py add "치과" --start 2026-06-13T15:00 --end 2026-06-13T16:00
  python scripts/gcal.py add "미용실" --who wife --start 2026-06-13T15:00 --end 2026-06-13T16:00
  python scripts/gcal.py add "여행" --start 2026-07-01 --end 2026-07-03   # 종일 일정
  python scripts/gcal.py delete <event_id> [--cal <calendar_id>]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

KST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/calendar/v3"
REPO_ROOT = Path(__file__).resolve().parents[1]


WIFE_NOT_CONNECTED = (
    "와이프(하늘) 캘린더가 아직 연결되지 않았어요. "
    "(GCAL_IDS_WIFE 비어 있음 — 하늘 캘린더를 서비스 계정에 '일정 변경'으로 공유하고 "
    ".env의 GCAL_IDS_WIFE에 ID를 넣으면 활성화됩니다.)"
)
FAMILY_NOT_FOUND = (
    "가족(공동) 캘린더를 찾지 못했어요. "
    "(GCAL_IDS에 '@group.calendar.google.com' 형태의 공유 캘린더가 없음 — "
    "가족 캘린더를 만들어 서비스 계정에 공유하고 GCAL_IDS에 추가하세요.)"
)
GROUP_SUFFIX = "@group.calendar.google.com"


def _resolve_cal_ids(who: str, minsu_ids: list[str], wife_ids: list[str]) -> list[str]:
    """프로파일(minsu|wife|family|all)을 실제 캘린더 ID 리스트로 해석.

    - minsu(기본): 민수 캘린더. - wife: 하늘 캘린더(미연결이면 SystemExit 안내).
    - family: GCAL_IDS 중 공유(@group) 캘린더만 = 부부 공동 일정용(에이전트가 ID를 몰라도 됨).
    - all: 둘 합치고 중복 제거. 하늘 미연결이면 민수만으로 폴백(깨지지 않게).
    """
    if who == "wife":
        if not wife_ids:
            raise SystemExit(WIFE_NOT_CONNECTED)
        return list(wife_ids)
    if who == "family":
        fam = [c for c in minsu_ids if c.endswith(GROUP_SUFFIX)]
        if not fam:
            raise SystemExit(FAMILY_NOT_FOUND)
        return fam
    if who == "all":
        merged = list(minsu_ids)
        merged += [c for c in wife_ids if c not in merged]
        return merged
    return list(minsu_ids)          # minsu(기본)


def _client(who: str = "minsu") -> tuple[httpx.Client, list[str]]:
    load_dotenv(REPO_ROOT / ".env")
    key_path = os.getenv("GCAL_SA_KEY", str(REPO_ROOT / ".gcal-sa.json"))
    minsu_ids = [c.strip() for c in os.environ["GCAL_IDS"].split(",") if c.strip()]
    wife_ids = [c.strip() for c in os.getenv("GCAL_IDS_WIFE", "").split(",") if c.strip()]
    cal_ids = _resolve_cal_ids(who, minsu_ids, wife_ids)   # wife 미연결이면 인증 전에 중단
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/calendar"])
    creds.refresh(GoogleRequest())
    client = httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=15.0,
    )
    return client, cal_ids


def _check(resp: httpx.Response) -> None:
    if resp.is_error:
        raise SystemExit(f"Calendar API {resp.status_code}: {resp.text[:300]}")


def _norm_dt(value: str) -> str:
    """YYYY-MM-DDTHH:MM → 초 붙여 RFC3339로 정규화."""
    if "T" in value and len(value) == 16:
        return value + ":00"
    return value


def _fmt_event(ev: dict, cal_label: str) -> str:
    start = ev.get("start", {})
    end = ev.get("end", {})
    if "date" in start:                       # 종일 일정
        when = f"{start['date']} 종일"
    else:
        s = datetime.fromisoformat(start["dateTime"]).astimezone(KST)
        e = datetime.fromisoformat(end["dateTime"]).astimezone(KST)
        when = f"{s:%Y-%m-%d %H:%M}~{e:%H:%M}"
    return f"{when}  {ev.get('summary', '(제목 없음)')}  [{cal_label}] (id={ev['id']})"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    ag = sub.add_parser("agenda", help="다가오는 일정")
    ag.add_argument("--days", type=int, default=7)
    ag.add_argument("--who", choices=["minsu", "wife", "family", "all"], default="minsu",
                    help="대상 캘린더 프로파일 (기본 minsu)")

    ad = sub.add_parser("add", help="일정 추가")
    ad.add_argument("summary")
    ad.add_argument("--start", required=True,
                    help="ISO8601. 시간 없으면(YYYY-MM-DD) 종일 일정")
    ad.add_argument("--end", required=True)
    ad.add_argument("--who", choices=["minsu", "wife", "family", "all"], default="minsu",
                    help="대상 캘린더 프로파일 (기본 minsu)")
    ad.add_argument("--cal", help="캘린더 ID (지정 시 --who보다 우선)")
    ad.add_argument("--desc")

    de = sub.add_parser("delete", help="일정 삭제")
    de.add_argument("event_id")
    de.add_argument("--who", choices=["minsu", "wife", "family", "all"], default="minsu",
                    help="대상 캘린더 프로파일 (기본 minsu)")
    de.add_argument("--cal", help="캘린더 ID (지정 시 --who보다 우선)")

    a = p.parse_args()
    if a.cmd in ("add", "delete") and a.who == "all" and not a.cal:
        raise SystemExit("--who all은 조회 전용이에요. 등록·삭제는 --who minsu|wife|family 중 하나로 지정하거나 --cal로 캘린더를 직접 지정하세요.")
    c, cal_ids = _client(a.who)

    if a.cmd == "agenda":
        now = datetime.now(KST)
        lines: list[tuple[str, str]] = []
        for cal in cal_ids:
            label = "가족" if cal.endswith("@group.calendar.google.com") else cal.split("@")[0]
            resp = c.get(f"/calendars/{cal}/events", params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(days=a.days)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime", "maxResults": "50",
            })
            _check(resp)
            for ev in resp.json().get("items", []):
                key = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "")
                lines.append((key, _fmt_event(ev, label)))
        if not lines:
            print(f"앞으로 {a.days}일간 일정 없음")
        for _, line in sorted(lines):
            print(line)
    elif a.cmd == "add":
        cal = a.cal or cal_ids[0]
        all_day = "T" not in a.start
        if all_day:
            body = {"summary": a.summary,
                    "start": {"date": a.start}, "end": {"date": a.end}}
        else:
            body = {"summary": a.summary,
                    "start": {"dateTime": _norm_dt(a.start), "timeZone": "Asia/Seoul"},
                    "end": {"dateTime": _norm_dt(a.end), "timeZone": "Asia/Seoul"}}
        if a.desc:
            body["description"] = a.desc
        resp = c.post(f"/calendars/{cal}/events", json=body)
        _check(resp)
        ev = resp.json()
        print(f"등록됨: {_fmt_event(ev, cal.split('@')[0])}")
    elif a.cmd == "delete":
        cal = a.cal or cal_ids[0]
        resp = c.delete(f"/calendars/{cal}/events/{a.event_id}")
        _check(resp)
        print("삭제됨")


if __name__ == "__main__":
    main()
