#!/usr/bin/env python3
"""비서(Claude)가 Bash로 호출하는 Google Calendar CLI (서비스 계정 인증).

사전 조건: 각 캘린더를 서비스 계정 이메일에 "일정 변경" 권한으로 공유해야 함.
대상 캘린더 ID는 .env의 GCAL_IDS (쉼표 구분, 첫 번째가 기본 캘린더).

사용 예:
  python scripts/gcal.py agenda                 # 오늘부터 7일
  python scripts/gcal.py agenda --days 1        # 오늘만
  python scripts/gcal.py add "치과" --start 2026-06-13T15:00 --end 2026-06-13T16:00
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


def _client() -> tuple[httpx.Client, list[str]]:
    load_dotenv(REPO_ROOT / ".env")
    key_path = os.getenv("GCAL_SA_KEY", str(REPO_ROOT / ".gcal-sa.json"))
    cal_ids = [c.strip() for c in os.environ["GCAL_IDS"].split(",") if c.strip()]
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/calendar"])
    creds.refresh(GoogleRequest())
    client = httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=15.0,
    )
    return client, cal_ids


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

    ad = sub.add_parser("add", help="일정 추가")
    ad.add_argument("summary")
    ad.add_argument("--start", required=True,
                    help="ISO8601. 시간 없으면(YYYY-MM-DD) 종일 일정")
    ad.add_argument("--end", required=True)
    ad.add_argument("--cal", help="캘린더 ID (생략 시 GCAL_IDS 첫 번째)")
    ad.add_argument("--desc")

    de = sub.add_parser("delete", help="일정 삭제")
    de.add_argument("event_id")
    de.add_argument("--cal", help="캘린더 ID (생략 시 GCAL_IDS 첫 번째)")

    a = p.parse_args()
    c, cal_ids = _client()

    if a.cmd == "agenda":
        now = datetime.now(KST)
        lines: list[tuple[str, str]] = []
        for cal in cal_ids:
            label = cal.split("@")[0]
            resp = c.get(f"/calendars/{cal}/events", params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(days=a.days)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime", "maxResults": "50",
            })
            resp.raise_for_status()
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
                    "start": {"dateTime": a.start, "timeZone": "Asia/Seoul"},
                    "end": {"dateTime": a.end, "timeZone": "Asia/Seoul"}}
        if a.desc:
            body["description"] = a.desc
        resp = c.post(f"/calendars/{cal}/events", json=body)
        resp.raise_for_status()
        ev = resp.json()
        print(f"등록됨: {_fmt_event(ev, cal.split('@')[0])}")
    elif a.cmd == "delete":
        cal = a.cal or cal_ids[0]
        resp = c.delete(f"/calendars/{cal}/events/{a.event_id}")
        resp.raise_for_status()
        print("삭제됨")


if __name__ == "__main__":
    main()
