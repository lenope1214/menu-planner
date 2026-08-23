# -*- coding: utf-8 -*-
"""
식단표 내보내기/인쇄 유틸
==========================
- 텍스트 저장(.txt)
- 엑셀 저장(.xlsx) — 가게에서 쓰던 서식 그대로:
    · 배달형(preset='달력형') : 세로 A4, 한 시트에 [중식][석식] 월간 달력.
        제목 Arial 60 / 요일헤더 Arial 29굵게(F3F3F3) / 날짜 GoogleSansText 29굵게
        / 메뉴 GoogleSansText 26(6개를 빈 줄로 연결) 중식=D9D2E9·석식=FCE5CD, 빈칸=D0E0E3.
    · 주방형(preset='주방형') : 가로 A4, 주 단위 4행 블록(요일/날짜/중식/석식).
        구분=Arial 24굵게, 중식=D9D2E9·석식=FCE5CD, 날짜헤더=CFE2F3, 메뉴=F3F3F3.
- 인쇄(Windows: 메모장 인쇄 동사 / 그 외 안내)
"""

from __future__ import annotations

import datetime
import math
import os
import sys
import tempfile
import unicodedata

from menu_planner import parse_menu_text
import layouts
from layouts import (
    PRESET_KITCHEN, SECTIONS, ITEMS_PER_MEAL, WEEKDAYS_KR,
    FOOTER_NOTE, MonthData, build_month_data, calendar_weeks,
)

# ---- 가게 서식 상수(7월식단표.xlsx 기준) ----
FONT_HEAD = "Arial"
FONT_BODY = "Google Sans Text"
TXT = "FF1F1F1F"          # 본문 글자색(ARGB)
GRAY = "FFF3F3F3"         # 요일/날짜 헤더, 주방 메뉴
LAVENDER = "FFD9D2E9"     # 중식
PEACH = "FFFCE5CD"        # 석식
TEAL = "FFD0E0E3"         # 배달 빈칸
BLUE = "FFCFE2F3"         # 주방 날짜헤더
FOOTER_TEXT = "\n" + FOOTER_NOTE
WD = WEEKDAYS_KR          # 일~토

# 메뉴 열 너비(엑셀 단위). 기존 13 → 넓혀서 줄바꿈/행높이를 줄인다.
# (넓혀서 종이 폭을 넘어도 _page 의 fitToWidth 로 인쇄는 1페이지 폭에 맞춰짐)
MENU_COL_WIDTH = 26.0

# ---- 행 높이 자동 계산 파라미터 ----
_LINE_RATIO = 1.35     # 한 줄 높이 ≈ 폰트pt × 이 비율(줄간격 포함)
_ROW_PAD_PT = 16       # 셀 위/아래 여백(pt)
_MIN_ROW_PT = 120      # 최소 행 높이(pt)
_MAX_ROW_PT = 620      # 최대 행 높이(pt) — 과도한 줄바꿈 방지 클램프
_COL_PX_PER_UNIT = 7.0     # 엑셀 열너비 1 ≈ 7px(기본 폰트 문자폭)
_COL_PX_PAD = 5.0          # 열 좌우 여백(px)


def _char_width(ch: str) -> int:
    """전각(한글/한자/가나 등)=2, 반각=1 로 표시폭 계산."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _cell_lines(text: str, col_width: float, font_size: int) -> int:
    """셀 텍스트가 차지하는 표시 줄 수(명시적 줄바꿈 + 자동 줄바꿈 추정).

    col_width: 엑셀 열 너비, font_size: 셀 폰트 pt.
    한 줄에 들어가는 '표시폭 단위(전각=2)'를 열너비·폰트로 추정한다.
    """
    if not text:
        return 1
    col_px = col_width * _COL_PX_PER_UNIT + _COL_PX_PAD
    half_char_px = font_size * (96.0 / 72.0) / 2.0     # 반각 1글자(=1단위) 픽셀폭
    units_per_line = max(2.0, col_px / half_char_px)   # 한 줄 표시폭 단위 수
    lines = 0
    for seg in text.split("\n"):
        if not seg:
            lines += 1                                  # 빈 줄
            continue
        w = sum(_char_width(c) for c in seg)
        lines += max(1, math.ceil(w / units_per_line))
    return lines


def calc_row_height(texts, col_width: float, font_size: int) -> float:
    """한 행의 여러 셀 중 가장 높은 셀 기준으로 행 높이(pt)를 계산."""
    lines = max((_cell_lines(t or "", col_width, font_size) for t in texts), default=1)
    h = lines * font_size * _LINE_RATIO + _ROW_PAD_PT
    return round(max(_MIN_ROW_PT, min(_MAX_ROW_PT, h)), 1)


def save_txt(text: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ----------------------------------------------------------------------------
# 엑셀 저장 (.xlsx)
# ----------------------------------------------------------------------------

def save_xlsx(text: str, path: str, title: str = "식단표",
              preset: str = layouts.PRESET_CALENDAR,
              year: int | None = None, month: int | None = None) -> None:
    from openpyxl import Workbook

    year, month = _infer_year_month(text, year, month)
    md = build_month_data(text, year, month)
    wb = Workbook()
    wb.remove(wb.active)
    if preset == PRESET_KITCHEN:
        _xlsx_kitchen(wb, md)
    else:
        _xlsx_delivery(wb, md)
    wb.save(path)


def _infer_year_month(text, year, month):
    if year and month:
        return year, month
    mo = None
    for meal in parse_menu_text(text):
        p = layouts.parse_date_label(meal.date_label)
        if p:
            mo = p[0]
            break
    today = datetime.date.today()
    return year or today.year, month or mo or today.month


# ---- 셀 스타일 헬퍼 ----
def _border():
    from openpyxl.styles import Border, Side
    s = Side(style="thin", color="000000")
    return Border(left=s, right=s, top=s, bottom=s)


def _set(ws, r, c, value, *, font, size, bold=False, color=TXT, fill=None,
         halign="center", valign="center", wrap=False, border=None):
    from openpyxl.styles import Font, Alignment, PatternFill
    cell = ws.cell(row=r, column=c, value=value)
    cell.font = Font(name=font, size=size, bold=bold, color=color)
    cell.alignment = Alignment(horizontal=halign, vertical=valign, wrap_text=wrap)
    cell.border = border if border is not None else _border()
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    return cell


def _merge_box(ws, r1, c1, r2, c2, value, *, font, size, bold=False, color=TXT,
               fill=None, halign="center", valign="center"):
    """범위 병합 + 바깥 테두리(모든 셀에 테두리)."""
    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
    bd = _border()
    for rr in range(r1, r2 + 1):
        for cc in range(c1, c2 + 1):
            cell = ws.cell(row=rr, column=cc)
            cell.border = bd
            if fill:
                from openpyxl.styles import PatternFill
                cell.fill = PatternFill("solid", fgColor=fill)
    _set(ws, r1, c1, value, font=font, size=size, bold=bold, color=color,
         fill=fill, halign=halign, valign=valign)


def _page(ws, landscape):
    from openpyxl.worksheet.page import PageMargins
    from openpyxl.worksheet.properties import PageSetupProperties
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins = PageMargins(left=0 if landscape else 0.7,
                                  right=0 if landscape else 0.7,
                                  top=0.75, bottom=0.75)
    # 넓힌 열이 종이 폭을 넘어도 인쇄 시 '1페이지 폭'에 자동으로 맞춘다(세로는 여러 장 허용).
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


# ---- 배달형(달력형): 세로 A4, 한 시트에 중식/석식 ----
def _xlsx_delivery(wb, md: MonthData) -> None:
    ws = wb.create_sheet("배달")
    for c in "ABCDEFG":  # 요일 7칸 균일하게 넓힘
        ws.column_dimensions[c].width = MENU_COL_WIDTH
    _page(ws, landscape=False)

    weeks = calendar_weeks(md.year, md.month)
    r = 1
    for section in SECTIONS:
        r = _delivery_section(ws, md, section, weeks, r)


def _delivery_section(ws, md, section, weeks, r):
    menu_fill = LAVENDER if section == "중식" else PEACH

    # 제목 (3행 병합, Arial 60)
    _merge_box(ws, r, 1, r + 2, 7, f"{md.month}월 식단표 ({section})",
               font=FONT_HEAD, size=60, color=None)
    for k in range(3):
        ws.row_dimensions[r + k].height = 37.5
    r += 3

    # 요일 헤더 (Arial 29 굵게, F3F3F3)
    for ci, wd in enumerate(WD, start=1):
        _set(ws, r, ci, wd, font=FONT_HEAD, size=29, bold=True, color=None,
             fill=GRAY, valign="center")
    ws.row_dimensions[r].height = 37.5
    r += 1

    # 주별: 날짜행 + 메뉴행
    for week in weeks:
        for ci, day in enumerate(week, start=1):
            _set(ws, r, ci, (day or None), font=FONT_BODY, size=29, bold=True,
                 fill=(GRAY if day else TEAL), valign="center")
        ws.row_dimensions[r].height = 37.5
        vals = []
        for ci, day in enumerate(week, start=1):
            has = day and md.has_meal(day, section)
            val = "\n\n".join(md.get(day, section)) if has else None
            _set(ws, r + 1, ci, val, font=FONT_BODY, size=26,
                 fill=(menu_fill if day else TEAL), valign="top", wrap=True)
            vals.append(val)
        # 넓힌 메뉴 열 너비 기준으로 내용에 맞춰 행 높이 계산
        ws.row_dimensions[r + 1].height = calc_row_height(vals, MENU_COL_WIDTH, 26)
        r += 2

    # 안내문 (3행 병합, Arial 29 굵게, 정렬 일반=왼쪽)
    _merge_box(ws, r, 1, r + 2, 7, FOOTER_TEXT, font=FONT_HEAD, size=29,
               bold=True, color=None, halign=None, valign="top")
    for k in range(3):
        ws.row_dimensions[r + k].height = 37.5
    return r + 3


# ---- 주방형: 가로 A4, 주 단위 4행 블록 ----
def _xlsx_kitchen(wb, md: MonthData) -> None:
    ws = wb.create_sheet("주방")
    ws.column_dimensions["A"].width = 13.0        # '구분' 라벨 열
    for c in "BCDEFGH":                            # 요일 7칸 균일하게 넓힘
        ws.column_dimensions[c].width = MENU_COL_WIDTH
    _page(ws, landscape=True)

    weeks = calendar_weeks(md.year, md.month)
    r = 1
    for week in weeks:
        if not any(d and md.meals.get(d) for d in week):
            continue
        # 헤더행 + 날짜행: 구분 칸은 두 행 병합
        _merge_box(ws, r, 1, r + 1, 1, "구분", font=FONT_HEAD, size=24, bold=True,
                   color=None, fill=GRAY)
        for ci, wd in enumerate(WD):
            _set(ws, r, ci + 2, wd, font=FONT_HEAD, size=24, bold=True, color=None,
                 fill=BLUE, valign="center")
            _set(ws, r + 1, ci + 2, (week[ci] or None), font=FONT_BODY, size=24,
                 bold=True, fill=BLUE, valign="top")
        ws.row_dimensions[r].height = 33.8
        ws.row_dimensions[r + 1].height = 33.8

        # 중식/석식 행
        for k, section in enumerate(SECTIONS):
            rr = r + 2 + k
            _set(ws, rr, 1, section, font=FONT_BODY, size=24, bold=True,
                 fill=(LAVENDER if section == "중식" else PEACH), valign="center")
            vals = []
            for ci, day in enumerate(week):
                has = day and md.has_meal(day, section)
                val = "\n\n".join(md.get(day, section)) if has else None
                _set(ws, rr, ci + 2, val, font=FONT_BODY, size=24, fill=GRAY,
                     valign="top", wrap=True)
                vals.append(val)
            # 넓힌 메뉴 열 너비 기준으로 내용에 맞춰 행 높이 계산
            ws.row_dimensions[rr].height = calc_row_height(vals, MENU_COL_WIDTH, 24)
        r += 4


# ----------------------------------------------------------------------------
# 인쇄
# ----------------------------------------------------------------------------

def print_text(text: str, title: str = "식단표") -> str:
    body = f"{title}\n{'=' * 40}\n\n{text}\n"
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="menu_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    if sys.platform.startswith("win"):
        os.startfile(path, "print")  # type: ignore[attr-defined]
    return path
