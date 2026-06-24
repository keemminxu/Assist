from scripts.db import _aggregate_expenses, _month_range, _owner_clause


def test_month_range_mid_year_is_kst_boundary():
    start, end = _month_range("2026-06")
    assert start == "2026-06-01T00:00:00+09:00"     # KST 자정 경계
    assert end == "2026-07-01T00:00:00+09:00"


def test_month_range_december_rolls_to_next_year():
    start, end = _month_range("2026-12")
    assert start == "2026-12-01T00:00:00+09:00"
    assert end == "2027-01-01T00:00:00+09:00"


def test_owner_clause_person_includes_shared():
    # "내 것" 조회 = 본인 + 공동(shared), 상대 비공개는 제외
    assert _owner_clause("minsu") == "in.(minsu,shared)"
    assert _owner_clause("haneul") == "in.(haneul,shared)"


def test_owner_clause_shared_only():
    assert _owner_clause("shared") == "eq.shared"


def test_aggregate_expenses_totals_and_groups():
    rows = [
        {"amount": 6000, "category": "카페", "owner": "minsu"},
        {"amount": 40000, "category": "마트", "owner": "shared"},
        {"amount": 3000, "category": "카페", "owner": "haneul"},
        {"amount": 5000, "category": None, "owner": "minsu"},   # 카테고리 없음 → '기타'
    ]
    agg = _aggregate_expenses(rows)
    assert agg["count"] == 4
    assert agg["total"] == 54000
    assert agg["by_owner"] == {"minsu": 11000, "shared": 40000, "haneul": 3000}
    assert agg["by_category"] == {"마트": 40000, "카페": 9000, "기타": 5000}
    assert list(agg["by_category"]) == ["마트", "카페", "기타"]   # 큰 금액 순


def test_aggregate_expenses_empty():
    assert _aggregate_expenses([]) == {
        "count": 0, "total": 0, "by_owner": {}, "by_category": {}}
