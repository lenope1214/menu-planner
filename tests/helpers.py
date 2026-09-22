# -*- coding: utf-8 -*-
"""테스트에서 식단표 텍스트를 짧게 만들기 위한 도우미."""

from __future__ import annotations

KIMCHI = "김치류"
SIDES = ["어묵볶음", "감자조림", "오이무침"]
SOUP = "콩나물국"


def line(date_label: str, main: str, sides=None, kimchi=KIMCHI, soup=SOUP) -> str:
    """'7/1(수): 메인, 반찬, 반찬, 반찬, 김치류, 국' 한 줄."""
    items = [main, *(sides if sides is not None else SIDES)]
    if kimchi is not None:
        items.append(kimchi)
    items.append(soup)
    return f"{date_label}: " + ", ".join(items)


def text(lunch=None, dinner=None) -> str:
    """[중식]/[석식] 구역을 갖춘 식단표 텍스트."""
    out: list[str] = []
    if lunch:
        out.append("[중식]")
        out.extend(lunch)
    if dinner:
        out.append("[석식]")
        out.extend(dinner)
    return "\n".join(out)


def find_cell(ws, needle: str):
    """시트에서 특정 글자가 든 첫 셀(위치가 바뀌어도 견디는 테스트용)."""
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and needle in c.value:
                return c
    return None
