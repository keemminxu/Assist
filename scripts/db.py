#!/usr/bin/env python3
"""비서(Claude)가 Bash로 호출하는 Supabase CLI.

사용 예:
  python scripts/db.py remember "민수는 매운 음식을 좋아함" --category preference
  python scripts/db.py recall 음식
  python scripts/db.py meal "제육볶음" --type lunch
  python scripts/db.py meals
  python scripts/db.py note "NC AI 공모전 마감" --due 2026-06-23T23:59:00+09:00 --category deadline
  python scripts/db.py note "와이프 생일" --due 2026-08-14T00:00:00+09:00 --category birthday --recurring
  python scripts/db.py notes
  python scripts/db.py note-done 3
  python scripts/db.py projects
  python scripts/db.py project-add "신규 프로젝트" --note "설명"
  python scripts/db.py task-add "두바이 외주" "결제 모듈 버그 수정" --due 2026-06-15T18:00:00+09:00
  python scripts/db.py tasks            # 전체 미완료
  python scripts/db.py tasks "블로그"   # 프로젝트별 미완료
  python scripts/db.py task-done 7
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

    n = sub.add_parser("note", help="일정 메모 / 마감·생일·기념일 리마인더 추가")
    n.add_argument("note")
    n.add_argument("--due", help="ISO8601 예: 2026-06-23T23:59:00+09:00 (생일은 올해 날짜)")
    n.add_argument("--category", default="event",
                   choices=["event", "deadline", "birthday", "anniversary"])
    n.add_argument("--recurring", action="store_true", help="매년 반복(생일·기념일)")

    sub.add_parser("notes", help="미완료 일정 메모 목록")

    nd = sub.add_parser("note-done", help="일정 메모 완료 처리")
    nd.add_argument("note_id", type=int)

    sub.add_parser("projects", help="프로젝트 목록")

    pa = sub.add_parser("project-add", help="프로젝트 추가")
    pa.add_argument("name")
    pa.add_argument("--note")

    ta = sub.add_parser("task-add", help="프로젝트에 할 일 추가")
    ta.add_argument("project_name")
    ta.add_argument("task")
    ta.add_argument("--due", help="ISO8601 예: 2026-06-15T18:00:00+09:00")

    tl = sub.add_parser("tasks", help="미완료 할 일 (프로젝트명 생략 시 전체)")
    tl.add_argument("project_name", nargs="?")

    td = sub.add_parser("task-done", help="할 일 완료 처리")
    td.add_argument("task_id", type=int)

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
        body = {"note": a.note, "category": a.category, "recurring": a.recurring}
        if a.due:
            body["due_at"] = a.due
        _print(c.post("/schedule_notes", json=body))
    elif a.cmd == "notes":
        _print(c.get("/schedule_notes",
                     params={"done": "eq.false",
                             "select": "id,note,due_at,category,recurring",
                             "order": "due_at.asc.nullslast"}))
    elif a.cmd == "note-done":
        _print(c.patch("/schedule_notes", params={"id": f"eq.{a.note_id}"},
                       json={"done": True}))
    elif a.cmd == "projects":
        _print(c.get("/projects", params={
            "select": "id,name,status,note,project_tasks(id,status)",
            "order": "id"}))
    elif a.cmd == "project-add":
        body = {"name": a.name}
        if a.note:
            body["note"] = a.note
        _print(c.post("/projects", json=body))
    elif a.cmd == "task-add":
        pid = _project_id(c, a.project_name)
        body = {"project_id": pid, "task": a.task}
        if a.due:
            body["due_at"] = a.due
        _print(c.post("/project_tasks", json=body))
    elif a.cmd == "tasks":
        params = {"select": "id,task,status,due_at,created_at,projects(name)",
                  "status": "neq.done", "order": "created_at"}
        if a.project_name:
            pid = _project_id(c, a.project_name)
            params["project_id"] = f"eq.{pid}"
        _print(c.get("/project_tasks", params=params))
    elif a.cmd == "task-done":
        from datetime import datetime, timezone
        _print(c.patch("/project_tasks", params={"id": f"eq.{a.task_id}"},
                       json={"status": "done",
                             "done_at": datetime.now(timezone.utc).isoformat()}))


def _project_id(c: httpx.Client, name: str) -> int:
    resp = c.get("/projects", params={"name": f"ilike.*{name}*", "select": "id,name"})
    resp.raise_for_status()
    rows = resp.json()
    if len(rows) != 1:
        found = ", ".join(r["name"] for r in rows) or "없음"
        raise SystemExit(f"프로젝트 '{name}' 매칭 {len(rows)}건 (후보: {found}) — 정확한 이름으로 다시")
    return rows[0]["id"]


if __name__ == "__main__":
    main()
