# -*- coding: utf-8 -*-
"""
영속화·충돌 점검(store.py) 잠금
=================================
일시정지는 '지웠다 다시 넣는' 게 아니라 잠시 빼두는 운영 상태다.
마스터 목록(menu_pool.json)은 그대로 두고 settings.json 의 paused 만 움직여야,
다시 사용으로 바꿨을 때 속성이 그대로 돌아온다.
"""

from __future__ import annotations

import history
import layouts
import store

POOL = {
    "mains": [{"name": "제육볶음"}, {"name": "후라이드치킨"}],
    "sides": ["어묵볶음", "감자조림"],
    "soups": ["콩나물국"],
}


# ---- 일시정지 ----

def test_일시정지해도_마스터_목록은_그대로():
    store.save_pool(POOL)
    store.set_paused("mains", "제육볶음", True, "재료 수급")
    assert [m["name"] for m in store.get_pool()["mains"]] == ["제육볶음", "후라이드치킨"]
    assert store.is_paused("mains", "제육볶음")
    assert store.paused_note("mains", "제육볶음") == "재료 수급"


def test_생성용_풀에서는_빠진다():
    store.save_pool(POOL)
    store.set_paused("mains", "제육볶음", True)
    assert [m["name"] for m in store.active_pool()["mains"]] == ["후라이드치킨"]
    assert [d.name for d in store.pool_to_menupool(store.get_pool()).mains] == ["후라이드치킨"]


def test_이름을_고치면_일시정지도_따라간다():
    store.save_pool(POOL)
    store.set_paused("sides", "어묵볶음", True, "품절")
    store.rename_paused("sides", "어묵볶음", "어묵조림")
    assert store.paused_note("sides", "어묵조림") == "품절"
    assert not store.is_paused("sides", "어묵볶음")


def test_삭제하면_일시정지_표시도_지운다():
    store.set_paused("soups", "콩나물국", True)
    store.clear_paused("soups", "콩나물국")
    assert store.paused_names() == []


def test_화면표시용_요약():
    store.set_paused("mains", "쭈꾸미", True, "8월말까지")
    store.set_paused("sides", "잡채", True)
    # 순서는 보장 대상이 아니다(갈래 순서에 따름) — 내용만 본다
    assert set(store.paused_summary()) == {"쭈꾸미(8월말까지)", "잡채"}


# ---- 생성 전 충돌 점검 ----

def test_한_갈래가_전부_정지면_막는다():
    store.save_pool(POOL)
    for name in ("제육볶음", "후라이드치킨"):
        store.set_paused("mains", name, True)
    errs = store.check_conflicts(store.get_pool(), [], False)
    assert any("메인 요리가 모두 일시정지" in e for e in errs)


def test_반드시_나와야_하는_조건과_정지는_충돌():
    store.save_pool(POOL)
    store.set_paused("mains", "후라이드치킨", True)
    conds = [{"type": "menu_count", "menu": "후라이드치킨", "op": "==", "count": 2}]
    assert any("후라이드치킨" in e for e in store.check_conflicts(store.get_pool(), conds, False))


def test_이하_조건은_충돌이_아니다():
    store.save_pool(POOL)
    store.set_paused("mains", "후라이드치킨", True)
    conds = [{"type": "menu_count", "menu": "후라이드치킨", "op": "<=", "count": 2}]
    assert store.check_conflicts(store.get_pool(), conds, False) == []


def test_추가된_메뉴만_켜면_풀에_없는_조건을_잡는다():
    store.save_pool(POOL)
    conds = [{"type": "menu_section", "menu": "돈까스", "section": "중식"}]
    assert any("돈까스" in e or "풀에 없습니다" in e
               for e in store.check_conflicts(store.get_pool(), conds, True))


# ---- 설정 ----

def test_과거기록_활용방식_기본값과_저장():
    assert store.get_history_mode() == history.MODE_REF
    store.set_history_mode(history.MODE_ONLY)
    assert store.get_history_mode() == history.MODE_ONLY
    store.set_history_mode("이상한값")
    assert store.get_history_mode() == history.MODE_REF     # 모르는 값은 기본으로


def test_기록_파일도_동기화_대상():
    assert history.HISTORY_FILE in store.DATA_FILES


# ---- 기록 → 메뉴 풀 ----

def test_기록에_있는_메뉴를_풀에_채운다():
    md = layouts.MonthData(year=2026, month=6)
    md.meals[1] = {"중식": ["고등어구이", "어묵볶음", "감자조림", "잡채", "김치류", "미역국"]}
    history.save_month(md)
    store.save_pool({"mains": [], "sides": [], "soups": []})

    added = store.add_missing_from_history()
    assert added == {"mains": 1, "sides": 3, "soups": 1}

    pool = store.get_pool()
    mains = {m["name"]: m for m in pool["mains"]}
    assert mains["고등어구이"]["is_fish"] is True      # 이름으로 생선류 자동 판정
    assert "미역국" in pool["soups"]
    assert store.add_missing_from_history() == {"mains": 0, "sides": 0, "soups": 0}
