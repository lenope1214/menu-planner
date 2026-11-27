# -*- coding: utf-8 -*-
"""
엑셀 서식(exporters.py) 잠금
=============================
열 너비·행 높이·메뉴 사이 빈 줄은 가게에서 쓰는 원본 시트(식단표.xlsx 의 배달-/주방- 시트)
값 그대로다. **wrap_text 를 끄면 엑셀에서 6개가 한 줄로 붙어 보인다.**
전부 눈으로만 확인되는 종류라 여기서 못 박아 둔다.
"""

from __future__ import annotations

from openpyxl import load_workbook

import exporters as ex
import layouts
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


# ---- 서식 상수 ----

def test_서식_수치를_지킨다():
    assert ex.DLV_COL_W == 31.38          # 배달 A~G
    assert ex.KIT_COL_W == 25.13          # 주방 B~H
    assert ex.DEFAULT_COL_W == 12.63      # 시트 기본 너비(주방 '구분' 열)
    assert ex.DLV_ROW_H_HEAD == 37.5      # 배달 제목/요일/날짜 행
    assert ex.DLV_ROW_H_MENU == 337.5     # 배달 메뉴 행
    assert ex.KIT_ROW_H_HEAD == 33.75     # 주방 요일/날짜 행
    assert ex.KIT_ROW_H_MENU == 311.25    # 주방 메뉴 행
    assert ex.MENU_SEP == "\n\n"          # 메뉴 사이 빈 줄 한 칸


def test_메뉴_여섯개는_열한_줄로_본다():
    """항목 6개 + 사이 빈 줄 5개 = 11줄. 원본 너비에서는 접히지 않아야 한다."""
    cell = ex.MENU_SEP.join(MENU)
    assert ex._cell_lines(cell, ex.DLV_COL_W, 26) == ex.MENU_BASE_LINES == 11
    assert ex._cell_lines(cell, ex.KIT_COL_W, 24) == 11


def test_긴_메뉴명은_접힌_줄까지_센다():
    short = ex._cell_lines("제육볶음", ex.DLV_COL_W, 26)
    long = ex._cell_lines("매운돼지갈비찜간장양념구이", ex.DLV_COL_W, 26)
    assert short == 1
    assert long > short


def test_행_높이는_평소엔_원본값이고_줄이_접힐_때만_커진다():
    base = ex.DLV_ROW_H_MENU
    normal = ex.calc_row_height([ex.MENU_SEP.join(MENU)], ex.DLV_COL_W, 26, base)
    assert normal == base                              # 평소엔 원본 높이 그대로
    assert ex.calc_row_height([None, ""], ex.DLV_COL_W, 26, base) == base
    long_menu = ["매운돼지갈비찜간장양념구이"] + MENU[1:]
    grown = ex.calc_row_height([ex.MENU_SEP.join(long_menu)], ex.DLV_COL_W, 26, base)
    assert grown > base                                # 접힌 줄만큼만 키운다
    huge = ex.calc_row_height(["가" * 2000], ex.DLV_COL_W, 26, base)
    assert huge == ex._MAX_ROW_PT                      # 과도한 줄바꿈은 잘라낸다


# ---- 배달형(달력) ----

def test_배달형_시트와_열너비(tmp_path):
    wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert wb.sheetnames == ["배달-26.07"]
    for c in "ABCDEFG":
        assert ws.column_dimensions[c].width == ex.DLV_COL_W
    assert ws.page_setup.orientation == "portrait"


def test_넓힌_열은_인쇄시_한_페이지_폭에_맞춘다(tmp_path):
    """7열 × 31.38 은 A4 세로 폭을 넘으므로 fitToWidth 가 없으면 인쇄가 옆으로 잘린다."""
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert ws.page_setup.fitToWidth == 1
    assert ws.page_setup.fitToHeight == 0


def test_배달형_메뉴칸은_줄바꿈이_켜져_있다(tmp_path):
    """원본은 구글 시트라 wrapText 없이도 보이지만, 엑셀은 꺼져 있으면 한 줄로 붙는다."""
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    cell = find_cell(ws, "제육볶음")
    assert cell is not None
    assert cell.alignment.wrap_text is True
    assert cell.value == "\n\n".join(MENU)      # 항목 사이 빈 줄(앞 공백 없이)
    assert ws.row_dimensions[cell.row].height == ex.DLV_ROW_H_MENU


def test_배달형_요일머리글은_전체표기(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert find_cell(ws, "일요일") is not None
    assert find_cell(ws, "토요일") is not None


def test_안내문이_들어간다(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    assert find_cell(ws, "※") is not None


# ---- 날짜 옆 회전 번호(1→2→3) ----

def test_회전번호는_2026년_12월_1일이_1이고_사흘마다_돈다():
    assert [layouts.cycle_number(2026, 12, d) for d in (1, 2, 3, 4, 5, 6)] == [1, 2, 3, 1, 2, 3]
    assert layouts.cycle_number(2026, 11, 30) == 3      # 기준일 앞으로도 이어진다
    assert layouts.cycle_number(2027, 1, 1) == 2        # 달·해가 바뀌어도 끊기지 않는다
    assert layouts.day_with_cycle(2026, 12, 4) == "4 (1)"
    assert layouts.date_with_cycle(2026, 12, 4) == "12/4 (1)"


def test_회전번호는_주방용_엑셀에만_붙는다(tmp_path):
    n = layouts.cycle_number(2026, 7, 1)
    _wb, ws = _sheet(tmp_path, PRESET_KITCHEN)
    values = {c.value for row in ws.iter_rows() for c in row}
    assert f"7/1 ({n})" in values and 1 not in values     # 주방용: 월/일 (번호)

    # 배달용 날짜칸은 원본처럼 숫자만 — 가게 주방 시트가 INDIRECT 로 이 숫자를 끌어다 쓴다
    _wb, ws = _sheet(tmp_path, PRESET_CALENDAR)
    dates = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, int)]
    assert sorted(set(dates)) == list(range(1, 32))
    assert not any(isinstance(c.value, str) and "(1)" in c.value and "/" in c.value
                   for row in ws.iter_rows() for c in row)


def test_텍스트_출력의_회전번호는_다시_읽어도_깨지지_않는다():
    """복사·인쇄·텍스트 저장은 '7/1(수) (N): …' 로 나가고, 파서는 그 형식도 읽는다."""
    md = layouts.build_month_data(SAMPLE, 2026, 7)
    plain = layouts.month_data_to_text(md)
    shown = layouts.month_data_to_text(md, with_cycle=True)
    n = layouts.cycle_number(2026, 7, 1)
    assert f"7/1(수) ({n}): 제육볶음" in shown
    assert "(%d):" % n not in plain                       # 표준 텍스트는 그대로
    back = layouts.build_month_data(shown, 2026, 7)
    assert layouts.month_data_to_text(back) == plain


# ---- 주방형(주간) ----

def test_주방형_시트와_열너비(tmp_path):
    wb, ws = _sheet(tmp_path, PRESET_KITCHEN)
    assert wb.sheetnames == ["주방-26.07"]
    assert ws.column_dimensions["A"].width == ex.DEFAULT_COL_W   # '구분' 라벨 열
    for c in "BCDEFGH":
        assert ws.column_dimensions[c].width == ex.KIT_COL_W
    assert ws.page_setup.orientation == "landscape"


def test_주방형_메뉴칸과_구분칸(tmp_path):
    _wb, ws = _sheet(tmp_path, PRESET_KITCHEN)
    cell = find_cell(ws, "제육볶음")
    assert cell.alignment.wrap_text is True
    assert cell.value == "\n\n".join(MENU)
    assert ws.row_dimensions[cell.row].height == ex.KIT_ROW_H_MENU
    assert ws.cell(row=cell.row, column=1).value == "중식"


# ---- 메뉴명이 길어지면 행만 키운다 ----

def test_긴_메뉴명이면_행_높이가_커진다(tmp_path):
    long_text = text(lunch=[line("7/1(수)", "매운돼지갈비찜간장양념구이")])
    p = tmp_path / "long.xlsx"
    ex.save_xlsx(long_text, str(p), preset=PRESET_CALENDAR, year=2026, month=7)
    ws = load_workbook(str(p)).worksheets[0]
    cell = find_cell(ws, "매운돼지갈비찜간장양념구이")

    _wb2, ws_short = _sheet(tmp_path, PRESET_CALENDAR)
    short_cell = find_cell(ws_short, "제육볶음")
    assert (ws.row_dimensions[cell.row].height
            > ws_short.row_dimensions[short_cell.row].height)


# ---- 텍스트 저장 ----

def test_텍스트로도_저장된다(tmp_path):
    p = tmp_path / "t.txt"
    ex.save_txt(SAMPLE, str(p))
    assert p.read_text(encoding="utf-8") == SAMPLE
