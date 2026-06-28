# -*- coding: utf-8 -*-
"""
식단 조건(규칙) 모델 + 검증 + 프롬프트 변환
=============================================
사용자가 등록/수정/삭제하는 '조건'을 구조화한다. 같은 조건을
- 프롬프트(Gemini가 지키도록 지시)와
- 코드 검증(validate, 위반 시 자동 재생성)
양쪽에서 공유한다.

조건 dict 형태(type 별):
- menu_count : {"type","menu","op"("<="/"=="/">="),"count"}
- menu_gap   : {"type","menu","days"}
- menu_section: {"type","menu","section"("중식"/"석식")}
- category_max: {"type","category"("생선류"),"max"}
"""

from __future__ import annotations

import re

# 카테고리(키워드 기반)
FISH_KEYWORDS = ("고등어", "조기", "굴비", "가자미", "가재미", "열기", "임연수", "갈치", "삼치")
CATEGORIES = {"생선류": FISH_KEYWORDS}

TYPES = ["menu_count", "menu_section", "menu_gap", "category_max"]
TYPE_LABELS = {
    "menu_count": "메뉴 월 횟수",
    "menu_section": "메뉴 끼니 제한",
    "menu_gap": "같은 메뉴 최소 간격",
    "category_max": "생선류 월 최대",
}
OPS = {"<=": "이하", "==": "정확히", ">=": "이상"}

_DATE = re.compile(r"\d{1,2}/(\d{1,2})")


def _day(label: str) -> int:
    m = _DATE.search(label)
    return int(m.group(1)) if m else 0


def default_conditions() -> list[dict]:
    """현재 비즈니스 규칙을 기본 조건으로 시드."""
    return [
        {"type": "category_max", "category": "생선류", "max": 4},
        {"type": "menu_count", "menu": "후라이드치킨", "op": "==", "count": 2},
        {"type": "menu_section", "menu": "후라이드치킨", "section": "중식"},
        {"type": "menu_section", "menu": "수육", "section": "중식"},
        {"type": "menu_count", "menu": "쭈꾸미", "op": "<=", "count": 2},
        {"type": "menu_gap", "menu": "쭈꾸미", "days": 7},
    ]


def to_text(c: dict) -> str:
    """조건을 사람이 읽는 한 줄로."""
    t = c.get("type")
    if t == "menu_count":
        return f"{c['menu']} 월 {c['count']}회 {OPS.get(c['op'], c['op'])}"
    if t == "menu_section":
        return f"{c['menu']}는 {c['section']}에만 편성"
    if t == "menu_gap":
        return f"{c['menu']} 최소 {c['days']}일 간격"
    if t == "category_max":
        return f"{c['category']} 월 최대 {c['max']}회"
    return str(c)


def conditions_prompt(conds: list[dict]) -> str:
    if not conds:
        return ""
    lines = "\n".join(f"- {to_text(c)}" for c in conds)
    return "[반드시 지켜야 할 추가 조건(어기면 실패로 간주)]\n" + lines


def validate(meals, conds: list[dict]) -> list[str]:
    """조건 위반 목록(빈 리스트=통과). meals: MealLine 리스트."""
    errors: list[str] = []
    for c in conds:
        t = c.get("type")
        if t == "menu_count":
            cnt = sum(1 for m in meals if c["menu"] in m.main)
            n, op = c["count"], c["op"]
            ok = (op == "<=" and cnt <= n) or (op == "==" and cnt == n) or \
                 (op == ">=" and cnt >= n)
            if not ok:
                errors.append(f"{to_text(c)} (현재 {cnt}회)")
        elif t == "menu_section":
            bad = [m for m in meals if c["menu"] in m.main and m.section != c["section"]]
            if bad:
                errors.append(f"{to_text(c)} (위반 {len(bad)}건)")
        elif t == "menu_gap":
            days = sorted(_day(m.date_label) for m in meals if c["menu"] in m.main)
            for a, b in zip(days, days[1:]):
                if b - a < c["days"]:
                    errors.append(f"{to_text(c)} (간격 {b - a}일)")
                    break
        elif t == "category_max":
            kws = CATEGORIES.get(c["category"], ())
            cnt = sum(1 for m in meals if any(k in m.main for k in kws))
            if cnt > c["max"]:
                errors.append(f"{to_text(c)} (현재 {cnt}회)")
    return errors


def referenced_menus(conds: list[dict]) -> set[str]:
    return {c["menu"] for c in conds if "menu" in c}
