# -*- coding: utf-8 -*-
"""
규칙 검증(menu_planner.validate_menu) 잠금
==========================================
비즈니스 규칙은 프롬프트(SYSTEM_INSTRUCTION)와 코드(validate_menu) 두 곳에 있다.
여기서 코드 쪽을 고정해 두면, 한쪽만 고쳐서 조용히 어긋나는 사고를 막을 수 있다.
"""

from __future__ import annotations

import menu_planner as mp
from helpers import line, text


# ---- 형식 규칙 ----

def test_정상_식단은_통과한다():
    assert mp.validate_menu(text(lunch=[line("7/1(수)", "제육볶음")])) == []


def test_메뉴가_6개가_아니면_잡는다():
    t = "[중식]\n7/1(수): 제육볶음, 어묵볶음, 감자조림, 김치류, 콩나물국"
    assert any("5개" in e for e in mp.validate_menu(t))


def test_김치류가_두_개면_잡는다():
    t = "[중식]\n7/1(수): 제육볶음, 어묵볶음, 김치류, 오이무침, 김치류, 콩나물국"
    assert any(mp.KIMCHI_LABEL in e for e in mp.validate_menu(t))


def test_포맷이_깨지면_알려준다():
    assert mp.validate_menu("오늘 뭐 먹지") == ["파싱된 식단 라인이 없습니다(출력 포맷 오류)."]


# ---- 같은 메인 4일 간격 ----

def test_같은_메인_4일_이내_재등장을_잡는다():
    t = text(lunch=[line("7/1(수)", "제육볶음"), line("7/4(토)", "제육볶음")])
    assert any("4일 이내" in e for e in mp.validate_menu(t))


def test_4일_이상_떨어지면_통과한다():
    t = text(lunch=[line("7/1(수)", "제육볶음"), line("7/5(일)", "제육볶음")])
    assert mp.validate_menu(t) == []


def test_중식과_석식은_따로_센다():
    t = text(lunch=[line("7/1(수)", "제육볶음")], dinner=[line("7/2(목)", "제육볶음")])
    assert mp.validate_menu(t) == []


# ---- 달 경계(과거 기록과 이어지는 간격) ----

def test_지난달_기록과_이어지는_간격을_잡는다():
    tail = [(0, "중식", "제육볶음", "6/30")]        # 상대일 0 = 지난달 마지막 날
    errs = mp.validate_menu(text(lunch=[line("7/1(수)", "제육볶음")]), history_recent=tail)
    assert any("지난달 6/30" in e for e in errs)


def test_지난달_기록과_4일_이상_떨어지면_통과한다():
    tail = [(0, "중식", "제육볶음", "6/30")]
    assert mp.validate_menu(text(lunch=[line("7/4(토)", "제육볶음")]), history_recent=tail) == []


def test_지난달_기록은_같은_끼니끼리만_본다():
    tail = [(0, "석식", "제육볶음", "6/30")]
    assert mp.validate_menu(text(lunch=[line("7/1(수)", "제육볶음")]), history_recent=tail) == []


def test_같은_메인은_한_번만_보고한다():
    tail = [(0, "중식", "제육볶음", "6/30"), (-1, "중식", "제육볶음", "6/29")]
    t = text(lunch=[line("7/1(수)", "제육볶음"), line("7/2(목)", "제육볶음")])
    errs = [e for e in mp.validate_menu(t, history_recent=tail) if "지난달" in e]
    assert len(errs) == 1


# ---- 과거에 냈던 메뉴만 사용 ----

PAST = {"제육볶음", "어묵볶음", "감자조림", "오이무침", "콩나물국"}


def test_과거에_없던_메뉴를_잡는다():
    t = text(lunch=[line("7/1(수)", "제육볶음",
                         sides=["어묵볶음", "감자조림", "우엉조림"])])
    assert any("우엉조림" in e for e in mp.validate_menu(t, history_names=PAST))


def test_김치류는_과거목록_검사에서_빼준다():
    assert mp.validate_menu(text(lunch=[line("7/1(수)", "제육볶음")]),
                            history_names=PAST) == []


# ---- 일시정지 / 풀 제한 ----

def test_일시정지_메뉴는_반찬_자리도_잡는다():
    t = text(lunch=[line("7/1(수)", "불고기",
                         sides=["쭈꾸미볶음", "감자조림", "오이무침"])])
    assert any("쭈꾸미" in e for e in mp.validate_menu(t, paused=["쭈꾸미"]))


def test_풀에_없는_메인을_잡는다():
    from menu_data import MainDish, MenuPool
    pool = MenuPool(mains=[MainDish("제육볶음")], sides=[], soups=[])
    errs = mp.validate_menu(text(lunch=[line("7/1(수)", "돈까스")]),
                            pool=pool, pool_only=True)
    assert any("돈까스" in e for e in errs)


# ---- 달력 골격 ----

def test_휴무일은_골격에서_빠진다():
    hint = mp.render_template_hint(mp.build_month_plan(2026, 2, closed_days={16, 17, 18}))
    assert "2/16" not in hint and "2/15" in hint


def test_공휴일은_조리용이로_표시된다():
    hint = mp.render_template_hint(mp.build_month_plan(2026, 1))
    assert "1/1(목) [공휴일:신정, 조리용이메뉴]" in hint


# ---- 프롬프트에 규칙이 함께 실리는지 ----

def test_프롬프트와_코드가_같은_상수를_쓴다():
    assert f"정확히 {mp.MENU_COUNT_PER_MEAL}개" in mp.SYSTEM_INSTRUCTION
    assert mp.KIMCHI_LABEL in mp.SYSTEM_INSTRUCTION


def test_금지메뉴와_과거기록이_프롬프트에_실린다():
    plan = mp.build_month_plan(2026, 7)
    p = mp.build_user_prompt(plan, paused=["쭈꾸미"],
                             history_block="[과거] 6/30(화): 수육")
    assert "쭈꾸미" in p
    assert "6/30(화): 수육" in p


# ---- 달력 대조(연/월을 넘겼을 때) ----

def _full_month(year=2026, month=7, skip=(), relabel=None):
    """4일 간격 규칙에 걸리지 않게 메인을 돌려 가며 채운 한 달치."""
    mains = ["제육볶음", "불고기", "닭갈비", "돈까스", "오리훈제"]
    plan = mp.build_month_plan(year, month)
    rows = []
    for s in plan.days:
        if s.d.day in skip:
            continue
        label = (relabel or {}).get(s.d.day, s.label)
        rows.append(line(label, mains[s.d.day % len(mains)]))
    return text(lunch=rows, dinner=rows)


def test_한_달을_다_채우면_달력_검사를_통과한다():
    assert mp.validate_menu(_full_month(), year=2026, month=7) == []


def test_출력이_끊겨_빠진_날짜를_잡는다():
    errs = mp.validate_menu(_full_month(skip={30, 31}), year=2026, month=7)
    assert any("빠진 날짜 2일" in e and "7/30(목)" in e for e in errs)


def test_휴무일은_빠져도_된다():
    assert mp.validate_menu(_full_month(skip={15}), year=2026, month=7, closed_days={15}) == []


def test_틀리게_적은_요일을_잡는다():
    errs = mp.validate_menu(_full_month(relabel={1: "7/1(일)"}), year=2026, month=7)
    assert any("7/1(일) → 7/1(수)" in e for e in errs)


def test_같은_날짜를_두_번_적으면_잡는다():
    t = text(lunch=[line("7/1(수)", "제육볶음"), line("7/1(수)", "불고기")])
    assert any("두 번" in e for e in mp.validate_menu(t))


# ---- 다시 만들기: 위반만 고치고, 가장 나은 결과를 고른다 ----

def test_다시_만들_때는_직전_식단표와_위반_목록을_함께_준다():
    plan = mp.build_month_plan(2026, 7)
    p = mp.build_user_prompt(plan, correction="- 수육은 중식에만", previous="[중식]\\n7/1(수): 수육")
    assert "[직전 식단표]" in p and "[위반 목록]" in p and "그대로 두세요" in p
    assert "[직전 식단표]" not in mp.build_user_prompt(plan)


def test_끝내_못_맞추면_위반이_가장_적은_결과를_돌려준다(monkeypatch):
    good = _full_month()
    one_bad = _full_month(skip={31})                      # 위반 2건(중식·석식 31일 누락)
    worse = _full_month(skip={29, 30, 31}, relabel={1: "7/1(일)"})
    outputs = iter([one_bad, worse, worse, worse])
    calls = []

    def fake(year, month, **kw):
        calls.append(kw)
        return next(outputs)

    monkeypatch.setattr(mp, "generate_menu", fake)
    out, errs = mp.generate_validated_menu(2026, 7, api_key="x")
    assert out == one_bad and len(errs) == 2              # 마지막(worse)이 아니라 가장 나은 것
    assert calls[0]["previous"] == "" and calls[1]["previous"] == one_bad
    assert "빠진 날짜" in calls[1]["correction"]
    assert calls[1]["temperature"] < calls[0]["temperature"]   # 재시도는 더 보수적으로

    monkeypatch.setattr(mp, "generate_menu", lambda y, m, **kw: good)
    assert mp.generate_validated_menu(2026, 7, api_key="x") == (good, [])
