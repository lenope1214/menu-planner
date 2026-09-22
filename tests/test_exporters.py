# -*- coding: utf-8 -*-
"""
엑셀 서식(exporters.py) 잠금
=============================
가게에서 쓰던 서식(7월식단표.xlsx)의 수치를 그대로 재현해야 한다.
**열 너비를 줄이면 메뉴 글자가 잘리고, wrap_text 를 끄면 6개가 한 줄로 붙어 보인다.**
둘 다 눈으로만 확인되는 종류라 여기서 못 박아 둔다.
"""

from __future__ import annotations

from openpyxl import load_workbook

import exporters as ex
from layouts import PRESET_CALENDAR, PRESET_KITCHEN
from helpers import find_cell, line, text

MENU = ["제육볶음", "어묵볶음", "감자조림", "오이무침", "김치류", "콩나물국"]
SAMPLE = text(lunch=[line("7/1(수)", "제육볶음")],
              dinner=[line("7/1(수)", "고등어구이")])


def _sheet(tmp_path, preset):
    p = tmp_path / "t.xlsx"
    ex.save_xlsx(SAMPLE, str(p), preset=preset, year=2026, month=7)
    wb = load_workbook(str(p))
    return wb, wb.worksheets[0]


# ---- 서식 상수(원본에서 뽑은 값) ----

def test_원본_서식_수치를_지킨다():
    assert ex.DLV_COL_W == 31.38          # 배달 A~G
    assert ex.KIT_COL_W == 25.13          # 주방 B~H
    assert ex.DLV_ROW_H_MENU == 337.5
    assert ex.KIT_ROW_H_MENU == 311.25
    assert ex.BASE_LINES == 11            # 항목 6 + 사이 빈 줄 5
    assert ex.WRAP_SLACK == 1.10


def test_일곱글자_메뉴명은_한_줄로_본다():
    """WRAP_SLACK 이 없으면 두 줄로 잡혀 행 높이가 쓸데없이 커진다."""
    assert ex._menu_lines(["매운돼지갈비찜"] * 6, ex.DLV_COL_W, 26) == ex.BASE_LINES


def test_줄이_늘면_그만큼만_키운다():
    assert ex._row_height(ex.BASE_LINES, ex.DLV_ROW_H_MENU) == ex.DLV_ROW_H_MENU
    assert ex._row_height(ex.BASE_LINES + 1, ex.DLV_ROW_H_MENU) == 368.18
    assert ex._row_height(3, ex.DLV_ROW_H_MENU) == ex.DLV_ROW_H_MENU   # 줄어들진 않는다


# ---- 배달형(달력) ----

def test_배달형_시트와_열너비(tmp_path):
    wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert wb.sheetnames == ["배달-26.07"]
    for c in "ABCDEFG":
        assert ws.column_dimensions[c].width == ex.DLV_COL_W
    assert ws.page_setup.orientation == "portrait"


def test_배달형_메뉴칸은_줄바꿈이_켜져_있다(tmp_path):
    """원본은 구글 시트라 wrapText 없이도 보이지만, 엑셀은 꺼져 있으면 한 줄로 붙는다."""
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    cell = find_cell(ws, "제육볶음")
    assert cell is not None
    assert cell.alignment.wrap_text is True
    assert cell.value == "\n\n".join(MENU)      # 항목 사이 빈 줄
    assert ws.row_dimensions[cell.row].height == ex.DLV_ROW_H_MENU


def test_배달형_요일머리글은_전체표기(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert find_cell(ws, "일요일") is not None
    assert find_cell(ws, "토요일") is not None


def test_안내문이_들어간다(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert find_cell(ws, "※") is not None


# ---- 주방형(주간) ----

def test_주방형_시트와_열너비(tmp_path):
    wb, ws = _sheet(tmp_path, PRESET_KITCHEN)
    assert wb.sheetnames == ["주방-26.07"]
    assert ws.column_dimensions["A"].width == ex.DEFAULT_COL_W
    for c in "BCDEFGH":
        assert ws.column_dimensions[c].width == ex.KIT_COL_W
    assert ws.page_setup.orientation == "landscape"


def test_주방형_메뉴칸과_구분칸(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_KITCHEN)
    cell = find_cell(ws, "제육볶음")
    assert cell.alignment.wrap_text is True
    assert ws.row_dimensions[cell.row].height == ex.KIT_ROW_H_MENU
    assert ws.cell(row=cell.row, column=1).value == "중식"


# ---- 메뉴명이 길어지면 행만 키운다 ----

def test_긴_메뉴명이면_행_높이가_커진다(tmp_path):
    long_text = text(lunch=[line("7/1(수)", "매운돼지갈비찜간장양념구이")])
    p = tmp_path / "long.xlsx"
    ex.save_xlsx(long_text, str(p), preset=PRESET_CALENDAR, year=2026, month=7)
    ws = load_workbook(str(p)).worksheets[0]
    cell = find_cell(ws, "매운돼지갈비찜간장양념구이")
    assert ws.row_dimensions[cell.row].height > ex.DLV_ROW_H_MENU


# ---- 텍스트 저장 ----

def test_텍스트로도_저장된다(tmp_path):
    p = tmp_path / "t.txt"
    ex.save_txt(SAMPLE, str(p))
    assert p.read_text(encoding="utf-8") == SAMPLE
