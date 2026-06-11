#!/usr/bin/env python3
"""비서(Claude)가 Bash로 호출하는 Supabase CLI.

사용 예:
  python scripts/db.py remember "민수는 매운 음식을 좋아함" --category preference
  python scripts/db.py recall 음식
  python scripts/db.py meal "제육볶음" --type lunch
  python scripts/db.py meals
  python scripts/db.py note "금요일 치과" --due 2026-06-13T10:00:00+09:00
  python scripts/db.py notes
  python scripts/db.py note-done 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")   # Windows 콘솔(cp949) 한글 깨짐 방지


def _client() -> httpx.Client:
    load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return httpx.Client(
        base_url=f"{url}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Prefer": "return=representation"},
        timeout=15.0,
    )


def _print(resp: httpx.Response) -> None:
    resp.raise_for_status()
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("remember", help="사실/선호 저장")
    r.add_argument("content")
    r.add_argument("--category", default="fact",
                   choices=["fact", "preference", "context"])

    rc = sub.add_parser("recall", help="기억 키워드 검색")
    rc.add_argument("keyword")

    m = sub.add_parser("meal", help="식단 기록")
    m.add_argument("description")
    m.add_argument("--type", default="snack",
                   choices=["breakfast", "lunch", "dinner", "snack"])
    m.add_argument("--note")

    sub.add_parser("meals", help="최근 식단 10건")

    n = sub.add_parser("note", help="일정 메모 추가")
    n.add_argument("note")
    n.add_argument("--due", help="ISO8601 예: 2026-06-13T10:00:00+09:00")

    sub.add_parser("notes", help="미완료 일정 메모 목록")

    nd = sub.add_parser("note-done", help="일정 메모 완료 처리")
    nd.add_argument("note_id", type=int)

    a = p.parse_args()
    c = _client()
    if a.cmd == "remember":
        _print(c.post("/memories", json={"content": a.content,
                                         "category": a.category, "source": "bot"}))
    elif a.cmd == "recall":
        _print(c.get("/memories", params={"content": f"ilike.*{a.keyword}*",
                                          "order": "created_at.desc", "limit": "20"}))
    elif a.cmd == "meal":
        body = {"description": a.description, "meal_type": a.type}
        if a.note:
            body["note"] = a.note
        _print(c.post("/meals", json=body))
    elif a.cmd == "meals":
        _print(c.get("/meals", params={"order": "eaten_at.desc", "limit": "10"}))
    elif a.cmd == "note":
        body = {"note": a.note}
        if a.due:
            body["due_at"] = a.due
        _print(c.post("/schedule_notes", json=body))
    elif a.cmd == "notes":
        _print(c.get("/schedule_notes", params={"done": "eq.false",
                                                "order": "created_at.asc"}))
    elif a.cmd == "note-done":
        _print(c.patch("/schedule_notes", params={"id": f"eq.{a.note_id}"},
                       json={"done": True}))


if __name__ == "__main__":
    main()
