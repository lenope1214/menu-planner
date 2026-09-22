# -*- coding: utf-8 -*-
"""
조건 해석/검증(conditions.py) 잠금
===================================
서술형 문장을 구조화 조건으로 바꾸는 `parse_text` 는 손대기 쉬운 곳이라
문장 종류별로 결과를 못 박아 둔다. 특히 **조사 처리 회귀**를 막는다.
"""

from __future__ import annotations

import conditions as cond
from menu_planner import parse_menu_text
from helpers import line, text


def _one(sentence, kind):
    """문장에서 특정 종류의 조건 하나를 꺼낸다."""
    got = [c for c in cond.parse_text(sentence) if c["type"] == kind]
    assert got, f"‘{sentence}’ 에서 {kind} 를 못 뽑았다: {cond.parse_text(sentence)}"
    return got[0]


# ---- 조사 처리 회귀 방지 (가장 중요) ----

def test_이로_끝나는_메뉴_이름이_깨지지_않는다():
    """‘이/가’를 조사로 떼면 ‘고등어구이 → 고등어구’ 가 된다. 절대 떼면 안 된다."""
    for name in ("고등어구이", "가자미구이", "조기구이"):
        c = _one(f"{name}는 저녁에만 내줘", "menu_section")
        assert c["menu"] == name


def test_앞머리에서_메뉴와_나머지를_가른다():
    assert cond._split_menu("비빔밥은 일요일에만") == ("비빔밥", "은 일요일에만")


# ---- 문장 → 조건 ----

def test_요일_제한():
    c = _one("비빔밥은 일요일에만 넣어줘", "menu_weekday")
    assert c["menu"] == "비빔밥" and c["weekdays"] == ["일"]


def test_평일과_주말은_요일_묶음으로_푼다():
    assert _one("닭갈비는 평일에만", "menu_weekday")["weekdays"] == ["월", "화", "수", "목", "금"]
    assert _one("돈까스는 주말에만", "menu_weekday")["weekdays"] == ["일", "토"]


def test_한_문장에서_여러_조건을_뽑는다():
    got = cond.parse_text("수육은 점심에만 내고 월 2회 이하로")
    kinds = {c["type"] for c in got}
    assert kinds == {"menu_section", "menu_count"}
    assert _one("수육은 점심에만 내고 월 2회 이하로", "menu_section")["section"] == "중식"
    cnt = _one("수육은 점심에만 내고 월 2회 이하로", "menu_count")
    assert (cnt["op"], cnt["count"]) == ("<=", 2)


def test_횟수_비교말을_구분한다():
    assert _one("불고기는 최소 3회 이상", "menu_count")["op"] == ">="
    assert _one("후라이드치킨은 한 달에 정확히 두 번", "menu_count") == {
        "type": "menu_count", "menu": "후라이드치킨", "op": "==", "count": 2}
    assert _one("갈비찜은 월 3회", "menu_count")["op"] == "<="   # 표현 없으면 약한 쪽


def test_간격_표현():
    assert _one("쭈꾸미는 10일 간격으로", "menu_gap")["days"] == 10
    assert _one("쭈꾸미는 일주일 간격으로", "menu_gap")["days"] == 7


def test_간격의_숫자를_월_횟수로_오해하지_않는다():
    got = cond.parse_text("쭈꾸미는 10일 간격으로")
    assert not [c for c in got if c["type"] == "menu_count"]


def test_카테고리_월_최대():
    assert cond.parse_text("생선류는 월 4회 이하") == [
        {"type": "category_max", "category": "생선류", "max": 4}]


def test_못_알아들으면_빈_리스트():
    assert cond.parse_text("맛있게 잘 부탁해요") == []
    assert cond.parse_text("") == []


# ---- 이름 대조 ----

def test_부분_일치는_같은_메뉴로_본다():
    assert cond.name_matches("쭈꾸미", "쭈꾸미볶음")
    assert cond.name_matches("쭈꾸미볶음", "쭈꾸미")


def test_한_글자는_완전_일치만_인정한다():
    assert not cond.name_matches("무", "무국")
    assert cond.name_matches("무", "무")


# ---- 사람이 읽는 문장 ----

def test_받침에_맞는_조사를_붙인다():
    assert cond.to_text({"type": "menu_section", "menu": "수육", "section": "중식"}) \
        == "수육은 중식에만 편성"
    assert cond.to_text({"type": "menu_section", "menu": "만두", "section": "석식"}) \
        == "만두는 석식에만 편성"


# ---- 조건 검증 ----

def _meals(*lines_):
    return parse_menu_text(text(lunch=list(lines_)))


def test_월_횟수_위반():
    c = {"type": "menu_count", "menu": "후라이드치킨", "op": "==", "count": 2}
    errs = cond.validate(_meals(line("7/1(수)", "후라이드치킨")), [c])
    assert any("현재 1회" in e for e in errs)


def test_끼니_제한_위반():
    c = {"type": "menu_section", "menu": "수육", "section": "중식"}
    meals = parse_menu_text(text(dinner=[line("7/1(수)", "수육")]))
    assert cond.validate(meals, [c])


def test_요일_제한은_반찬_자리도_본다():
    c = {"type": "menu_weekday", "menu": "비빔밥", "weekdays": ["일"]}
    meals = _meals(line("7/1(수)", "불고기", sides=["비빔밥", "감자조림", "오이무침"]))
    assert cond.validate(meals, [c])


def test_최소_간격_위반():
    c = {"type": "menu_gap", "menu": "쭈꾸미", "days": 7}
    errs = cond.validate(_meals(line("7/1(수)", "쭈꾸미"), line("7/5(일)", "쭈꾸미")), [c])
    assert any("간격 4일" in e for e in errs)


def test_생선류_월_최대_위반():
    c = {"type": "category_max", "category": "생선류", "max": 1}
    meals = _meals(line("7/1(수)", "고등어구이"), line("7/6(월)", "가자미구이"))
    assert any("현재 2회" in e for e in cond.validate(meals, [c]))


def test_기본_조건은_모두_사람이_읽을_수_있다():
    for c in cond.default_conditions():
        assert cond.to_text(c) and not cond.to_text(c).startswith("{")
