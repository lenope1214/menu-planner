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

⚠ 아래 수치는 실제 운영 파일 '식단표_EXCEL/7월식단표.xlsx' 의 시트
   '배달-26.07' / '주방-26.07' 에서 그대로 뽑은 값이다(모든 월 시트가 동일).
   열 너비(배달 A~G 31.38 / 주방 B~H 25.13)·메뉴 행 높이(337.5 / 311.25)·
   메뉴 사이 빈 줄까지 원본과 같아야 한다. 임의로 바꾸지 말 것.
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
    PRESET_KITCHEN, SECTIONS, WEEKDAYS_KR,
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

# 엑셀 요일 머리글은 원본과 같이 '일요일'…'토요일' 전체 표기(GUI 미리보기는 '일'…'토').
WD = [w + "요일" for w in WEEKDAYS_KR]

# 시트 기본값 — 원본 sheetFormatPr
DEFAULT_COL_W = 12.63
DEFAULT_ROW_H = 15.75

# 행 높이 — 원본 시트 값 그대로(모든 월 시트 동일)
DLV_ROW_H_HEAD = 37.5     # 배달형: 제목/요일/날짜 행
DLV_ROW_H_MENU = 337.5    # 배달형: 메뉴 행
KIT_ROW_H_HEAD = 33.75    # 주방형: 요일/날짜 행
KIT_ROW_H_MENU = 311.25   # 주방형: 메뉴 행

# 열 너비 — 원본 시트 값 그대로.
# 원본 xlsx 는 '<col min=1 max=7 width=31.38>' 처럼 여러 열을 한 덩어리로 적어서
# openpyxl 로 읽으면 첫 열(A 또는 B)에만 값이 보인다. 나머지 열도 같은 너비다.
DLV_COL_W = 31.38         # 배달형 A~G
KIT_COL_W = 25.13         # 주방형 B~H ('구분' 열 A 는 시트 기본 너비)

# 메뉴 칸: 항목 사이에 빈 줄 한 칸(원본과 같은 모양). 6개 = 11줄.
MENU_SEP = "\n\n"
MENU_BASE_LINES = 11

# ---- 긴 메뉴명으로 줄이 접혔을 때만 행을 키우는 파라미터 ----
_LINE_RATIO = 1.35     # 접힌 한 줄당 추가 높이 ≈ 폰트pt × 이 비율
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


def calc_row_height(texts, col_width: float, font_size: int, base_h: float) -> float:
    """메뉴 행 높이(pt). 평소엔 원본 높이(base_h) 그대로.

    메뉴명이 길어 줄이 접힌 칸이 있으면(기본 11줄 초과) 접힌 줄 수만큼만 키운다.
    """
    lines = max((_cell_lines(t or "", col_width, font_size) for t in texts), default=1)
    extra = max(0, lines - MENU_BASE_LINES)
    h = base_h + extra * font_size * _LINE_RATIO
    return round(min(max(_MAX_ROW_PT, base_h), h), 2)


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
    """원본 시트의 pageSetup/printOptions/sheetFormatPr 를 그대로 재현."""
    from openpyxl.worksheet.page import PageMargins
    from openpyxl.worksheet.properties import PageSetupProperties
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins = PageMargins(left=0 if landscape else 0.7,
                                  right=0 if landscape else 0.7,
                                  top=0.75, bottom=0.75, header=0.0, footer=0.0)
    # 넓힌 열이 종이 폭을 넘어도 인쇄 시 '1페이지 폭'에 자동으로 맞춘다(세로는 여러 장 허용).
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    # 원본: <printOptions gridLines="1" horizontalCentered="1"/>
    ws.print_options.horizontalCentered = True
    ws.print_options.gridLines = True
    ws.sheet_format.defaultColWidth = DEFAULT_COL_W
    ws.sheet_format.defaultRowHeight = DEFAULT_ROW_H


# ---- 배달형(달력형): 세로 A4, 한 시트에 중식/석식 ----
def _xlsx_delivery(wb, md: MonthData) -> None:
    ws = wb.create_sheet(f"배달-{md.year % 100:02d}.{md.month:02d}")
    for c in "ABCDEFG":  # 요일 7칸 균일하게 넓힘
        ws.column_dimensions[c].width = DLV_COL_W
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
        ws.row_dimensions[r + k].height = DLV_ROW_H_HEAD
    r += 3

    # 요일 헤더 (Arial 29 굵게, F3F3F3, 세로정렬 지정 없음 = 원본과 동일)
    for ci, wd in enumerate(WD, start=1):
        _set(ws, r, ci, wd, font=FONT_HEAD, size=29, bold=True, color=None,
             fill=GRAY, valign=None)
    ws.row_dimensions[r].height = DLV_ROW_H_HEAD
    r += 1

    # 주별: 날짜행 + 메뉴행
    for week in weeks:
        for ci, day in enumerate(week, start=1):
            # 날짜칸은 숫자만 — 가게의 주방 시트가 INDIRECT 로 이 값을 끌어다 쓰고,
            # 회전 번호 (1)(2)(3) 은 주방 쪽에서만 붙인다.
            _set(ws, r, ci, (day or None),
                 font=FONT_BODY, size=29, bold=True,
                 fill=(GRAY if day else TEAL), valign=None)
        ws.row_dimensions[r].height = DLV_ROW_H_HEAD
        vals = []
        for ci, day in enumerate(week, start=1):
            has = day and md.has_meal(day, section)
            items = md.get(day, section) if has else []
            val = MENU_SEP.join(items) if has else None
            # wrap=True 여야 엑셀이 셀 안의 줄바꿈을 그대로 보여준다.
            _set(ws, r + 1, ci, val, font=FONT_BODY, size=26,
                 fill=(menu_fill if day else TEAL), valign="top", wrap=True)
            vals.append(val)
        # 원본 높이 그대로, 긴 메뉴명으로 줄이 접힌 주만 그만큼 키운다
        ws.row_dimensions[r + 1].height = calc_row_height(vals, DLV_COL_W, 26, DLV_ROW_H_MENU)
        r += 2

    # 안내문 (3행 병합, Arial 29 굵게, 정렬 일반=왼쪽)
    _merge_box(ws, r, 1, r + 2, 7, FOOTER_TEXT, font=FONT_HEAD, size=29,
               bold=True, color=None, halign=None, valign="top")
    for k in range(3):
        ws.row_dimensions[r + k].height = DLV_ROW_H_HEAD
    return r + 3


# ---- 주방형: 가로 A4, 주 단위 4행 블록 ----
def _xlsx_kitchen(wb, md: MonthData) -> None:
    ws = wb.create_sheet(f"주방-{md.year % 100:02d}.{md.month:02d}")
    ws.column_dimensions["A"].width = DEFAULT_COL_W   # '구분' 라벨 열(원본은 기본 너비)
    for c in "BCDEFGH":                            # 요일 7칸 균일하게 넓힘
        ws.column_dimensions[c].width = KIT_COL_W
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
                 fill=BLUE, valign=None)
            _set(ws, r + 1, ci + 2,
                 (layouts.date_with_cycle(md.year, md.month, week[ci]) if week[ci] else None),
                 font=FONT_BODY, size=24,
                 bold=True, fill=BLUE, valign="top")
        ws.row_dimensions[r].height = KIT_ROW_H_HEAD
        ws.row_dimensions[r + 1].height = KIT_ROW_H_HEAD

        # 중식/석식 행
        for k, section in enumerate(SECTIONS):
            rr = r + 2 + k
            _set(ws, rr, 1, section, font=FONT_BODY, size=24, bold=True,
                 fill=(LAVENDER if section == "중식" else PEACH), valign="center")
            vals = []
            for ci, day in enumerate(week):
                has = day and md.has_meal(day, section)
                items = md.get(day, section) if has else []
                val = MENU_SEP.join(items) if has else None
                _set(ws, rr, ci + 2, val, font=FONT_BODY, size=24, fill=GRAY,
                     valign="top", wrap=True)
                vals.append(val)
            # 원본 높이 그대로, 긴 메뉴명으로 줄이 접힌 주만 그만큼 키운다
            ws.row_dimensions[rr].height = calc_row_height(vals, KIT_COL_W, 24, KIT_ROW_H_MENU)
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
