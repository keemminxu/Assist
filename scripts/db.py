#!/usr/bin/env python3
"""비서(Claude)가 Bash로 호출하는 Supabase CLI.

owner는 부부 공유 비서의 소유자 구분: minsu | haneul | shared (기본 minsu).
발신자가 하늘이면 --owner haneul, 부부 공동 항목이면 --owner shared.

사용 예:
  python scripts/db.py remember "민수는 매운 음식을 좋아함" --category preference
  python scripts/db.py remember "하늘 회사: 펑타이코리아 AE" --owner haneul
  python scripts/db.py recall 음식 [--owner haneul]
  python scripts/db.py note "NC AI 공모전 마감" --due 2026-06-23T23:59:00+09:00 --category deadline
  python scripts/db.py note "여름 캠페인 소재 마감" --due 2026-07-10T18:00:00+09:00 --category campaign --owner haneul
  python scripts/db.py note "하늘 생일" --due 2026-10-17T00:00:00+09:00 --category birthday --recurring --owner shared
  python scripts/db.py notes [--owner haneul]
  python scripts/db.py note-done 3
  python scripts/db.py projects
  python scripts/db.py project-add "신규 프로젝트" --note "설명" [--owner haneul]
  python scripts/db.py task-add "두바이 외주" "결제 모듈 버그 수정" --due 2026-06-15T18:00:00+09:00 [--owner haneul]
  python scripts/db.py tasks [--owner haneul]      # 미완료 (프로젝트명/owner 필터 가능)
  python scripts/db.py task-done 7
  python scripts/db.py list-add "우유" --kind grocery
  python scripts/db.py list-add "분리수거" --kind chore --owner minsu
  python scripts/db.py list [--kind grocery] [--owner shared]
  python scripts/db.py list-done 4
  python scripts/db.py spend 6000 --category 카페 --memo "스타벅스" [--owner minsu]
  python scripts/db.py expenses [--owner haneul] [--since 2026-06-01]
  python scripts/db.py expense-sum [--month 2026-06] [--owner shared]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")   # Windows 콘솔(cp949) 한글 깨짐 방지

OWNER_CHOICES = ["minsu", "haneul", "shared"]
KST = timezone(timedelta(hours=9))    # 월 경계 등 날짜 판정은 KST 기준


def _owner_write(parser, default: str = "minsu") -> None:
    """쓰기용 --owner (기본값 있음)."""
    parser.add_argument("--owner", default=default, choices=OWNER_CHOICES,
                        help="소유자 (기본 %(default)s)")


def _owner_filter(parser) -> None:
    """조회용 --owner (생략 시 전체)."""
    parser.add_argument("--owner", choices=OWNER_CHOICES,
                        help="소유자 필터 (생략 시 전체). 사람 지정 시 본인+공동(shared) 조회")


def _owner_clause(owner: str) -> str:
    """조회 owner 필터 값. 사람(minsu/haneul)이면 본인+공동, shared면 공동만.

    "내 것 보여줘"를 발신자로 좁힐 때 상대의 비공개 항목은 빼고 공동은 포함하기 위함.
    """
    if owner == "shared":
        return "eq.shared"
    return f"in.({owner},shared)"


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


def _month_range(month: str | None) -> tuple[str, str]:
    """'YYYY-MM' → (그 달 시작 ISO, 다음 달 시작 ISO), KST 자정 경계. None이면 이번 달(KST).

    오프셋 포함 ISO(예: 2026-06-01T00:00:00+09:00)라 PostgREST가 정확한 KST 순간으로 비교한다.
    """
    if month:
        year, mon = (int(x) for x in month.split("-"))
    else:
        now = datetime.now(KST)
        year, mon = now.year, now.month
    start = datetime(year, mon, 1, tzinfo=KST)
    nxt = datetime(year + (mon == 12), (mon % 12) + 1, 1, tzinfo=KST)
    return start.isoformat(), nxt.isoformat()


def _aggregate_expenses(rows: list[dict]) -> dict:
    """지출 row들을 총합/owner별/카테고리별로 집계 (순수 함수)."""
    total = sum(r["amount"] for r in rows)
    by_owner: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    for r in rows:
        by_owner[r["owner"]] = by_owner.get(r["owner"], 0) + r["amount"]
        cat = r.get("category") or "기타"
        by_cat[cat] = by_cat.get(cat, 0) + r["amount"]
    return {
        "count": len(rows),
        "total": total,
        "by_owner": by_owner,
        "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("remember", help="사실/선호 저장")
    r.add_argument("content")
    r.add_argument("--category", default="fact",
                   choices=["fact", "preference", "context"])
    _owner_write(r)

    rc = sub.add_parser("recall", help="기억 키워드 검색")
    rc.add_argument("keyword")
    _owner_filter(rc)

    n = sub.add_parser("note", help="일정 메모 / 마감·생일·기념일·캠페인 리마인더 추가")
    n.add_argument("note")
    n.add_argument("--due", help="ISO8601 예: 2026-06-23T23:59:00+09:00 (생일은 올해 날짜)")
    n.add_argument("--category", default="event",
                   choices=["event", "deadline", "birthday", "anniversary", "campaign"])
    n.add_argument("--recurring", action="store_true", help="매년 반복(생일·기념일)")
    _owner_write(n)

    no = sub.add_parser("notes", help="미완료 일정 메모 목록")
    _owner_filter(no)

    nd = sub.add_parser("note-done", help="일정 메모 완료 처리")
    nd.add_argument("note_id", type=int)

    sub.add_parser("projects", help="프로젝트 목록")

    pa = sub.add_parser("project-add", help="프로젝트 추가")
    pa.add_argument("name")
    pa.add_argument("--note")
    _owner_write(pa)

    ta = sub.add_parser("task-add", help="프로젝트에 할 일 추가")
    ta.add_argument("project_name")
    ta.add_argument("task")
    ta.add_argument("--due", help="ISO8601 예: 2026-06-15T18:00:00+09:00")
    _owner_write(ta)

    tl = sub.add_parser("tasks", help="미완료 할 일 (프로젝트명 생략 시 전체)")
    tl.add_argument("project_name", nargs="?")
    _owner_filter(tl)

    td = sub.add_parser("task-done", help="할 일 완료 처리")
    td.add_argument("task_id", type=int)

    la = sub.add_parser("list-add", help="장보기/집안일 항목 추가")
    la.add_argument("item")
    la.add_argument("--kind", default="grocery", choices=["grocery", "chore"])
    _owner_write(la, default="shared")

    ll = sub.add_parser("list", help="미완료 장보기/집안일")
    ll.add_argument("--kind", choices=["grocery", "chore"], help="종류 필터")
    _owner_filter(ll)

    ld = sub.add_parser("list-done", help="장보기/집안일 완료 처리")
    ld.add_argument("item_id", type=int)

    sp = sub.add_parser("spend", help="지출 기록")
    sp.add_argument("amount", type=int, help="금액(원, 정수)")
    sp.add_argument("--category", help="식비|카페|마트|교통 등")
    sp.add_argument("--memo")
    sp.add_argument("--at", help="지출 시각 ISO8601 (생략 시 지금)")
    _owner_write(sp)

    ex = sub.add_parser("expenses", help="최근 지출 목록")
    _owner_filter(ex)
    ex.add_argument("--since", help="이 날짜 이후만 (ISO8601 또는 YYYY-MM-DD)")

    es = sub.add_parser("expense-sum", help="월 지출 합계 (총/owner별/카테고리별)")
    es.add_argument("--month", help="YYYY-MM (생략 시 이번 달)")
    _owner_filter(es)

    a = p.parse_args()
    c = _client()
    if a.cmd == "remember":
        _print(c.post("/memories", json={"content": a.content, "category": a.category,
                                         "owner": a.owner, "source": "bot"}))
    elif a.cmd == "recall":
        params = {"content": f"ilike.*{a.keyword}*",
                  "select": "id,content,category,owner,created_at",
                  "order": "created_at.desc", "limit": "20"}
        if a.owner:
            params["owner"] = _owner_clause(a.owner)
        _print(c.get("/memories", params=params))
    elif a.cmd == "note":
        body = {"note": a.note, "category": a.category,
                "recurring": a.recurring, "owner": a.owner}
        if a.due:
            body["due_at"] = a.due
        _print(c.post("/schedule_notes", json=body))
    elif a.cmd == "notes":
        params = {"done": "eq.false",
                  "select": "id,note,due_at,category,recurring,owner",
                  "order": "due_at.asc.nullslast"}
        if a.owner:
            params["owner"] = _owner_clause(a.owner)
        _print(c.get("/schedule_notes", params=params))
    elif a.cmd == "note-done":
        _print(c.patch("/schedule_notes", params={"id": f"eq.{a.note_id}"},
                       json={"done": True}))
    elif a.cmd == "projects":
        _print(c.get("/projects", params={
            "select": "id,name,status,owner,note,project_tasks(id,status)",
            "order": "id"}))
    elif a.cmd == "project-add":
        body = {"name": a.name, "owner": a.owner}
        if a.note:
            body["note"] = a.note
        _print(c.post("/projects", json=body))
    elif a.cmd == "task-add":
        pid = _project_id(c, a.project_name)
        body = {"project_id": pid, "task": a.task, "owner": a.owner}
        if a.due:
            body["due_at"] = a.due
        _print(c.post("/project_tasks", json=body))
    elif a.cmd == "tasks":
        params = {"select": "id,task,status,due_at,owner,created_at,projects(name)",
                  "status": "neq.done", "order": "created_at"}
        if a.project_name:
            pid = _project_id(c, a.project_name)
            params["project_id"] = f"eq.{pid}"
        if a.owner:
            params["owner"] = _owner_clause(a.owner)
        _print(c.get("/project_tasks", params=params))
    elif a.cmd == "task-done":
        _print(c.patch("/project_tasks", params={"id": f"eq.{a.task_id}"},
                       json={"status": "done",
                             "done_at": datetime.now(timezone.utc).isoformat()}))
    elif a.cmd == "list-add":
        _print(c.post("/shared_list",
                      json={"item": a.item, "kind": a.kind, "owner": a.owner}))
    elif a.cmd == "list":
        params = {"done": "eq.false", "select": "id,item,kind,owner,created_at",
                  "order": "created_at.asc"}
        if a.kind:
            params["kind"] = f"eq.{a.kind}"
        if a.owner:
            params["owner"] = _owner_clause(a.owner)
        _print(c.get("/shared_list", params=params))
    elif a.cmd == "list-done":
        _print(c.patch("/shared_list", params={"id": f"eq.{a.item_id}"},
                       json={"done": True}))
    elif a.cmd == "spend":
        body = {"amount": a.amount, "owner": a.owner}
        if a.category:
            body["category"] = a.category
        if a.memo:
            body["memo"] = a.memo
        if a.at:
            body["spent_at"] = a.at
        _print(c.post("/expenses", json=body))
    elif a.cmd == "expenses":
        params = {"select": "id,spent_at,amount,category,memo,owner",
                  "order": "spent_at.desc", "limit": "50"}
        if a.owner:
            params["owner"] = _owner_clause(a.owner)
        if a.since:
            params["spent_at"] = f"gte.{a.since}"
        _print(c.get("/expenses", params=params))
    elif a.cmd == "expense-sum":
        start, end = _month_range(a.month)
        query = [("select", "amount,category,owner"),
                 ("spent_at", f"gte.{start}"), ("spent_at", f"lt.{end}"),
                 ("limit", "10000")]
        if a.owner:
            query.append(("owner", _owner_clause(a.owner)))
        resp = c.get("/expenses", params=query)
        resp.raise_for_status()
        summary = {"month": (a.month or start[:7]), **_aggregate_expenses(resp.json())}
        print(json.dumps(summary, ensure_ascii=False, indent=2))


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
