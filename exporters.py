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
   메뉴 글자가 잘리지 않는 건 '열 너비'가 전적으로 결정하므로 임의로 줄이지 말 것.
"""

from __future__ import annotations

import datetime
import math
import os
import sys
import tempfile

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

# 엑셀 요일 머리글은 원본과 같이 '일요일'…'토요일' 전체 표기(GUI 미리보기는 '일'…'토').
WD = [w + "요일" for w in WEEKDAYS_KR]

# 시트 기본값 — 원본 sheetFormatPr
DEFAULT_COL_W = 12.63
DEFAULT_ROW_H = 15.75

# 배달형(달력형): A~G 7칸 모두 같은 너비. 이 값이 줄면 메뉴 글자가 잘린다.
DLV_COL_W = 31.38
DLV_ROW_H_HEAD = 37.5     # 제목/요일/날짜 행
DLV_ROW_H_MENU = 337.5    # 메뉴 6줄이 들어가는 행

# 주방형: A(구분)만 기본 너비, B~H(요일 7칸)는 25.13
KIT_COL_W = 25.13
KIT_ROW_H_HEAD = 33.75    # 요일/날짜 행
KIT_ROW_H_MENU = 311.25   # 메뉴 행

# 메뉴 칸이 원래 상정하는 줄 수: 항목 6개 + 그 사이 빈 줄 5개 = 11줄.
# 원본 행 높이가 정확히 이 줄 수에 비례한다(337.5/11 = 30.68 = 26pt×1.18,
# 311.25/11 = 28.30 = 24pt×1.18). 그래서 '줄 수 ÷ 11' 로 원본 높이를 그대로
# 재현하고, 메뉴명이 길어 줄이 늘어난 만큼만 키운다.
BASE_LINES = ITEMS_PER_MEAL * 2 - 1

# 줄바꿈 판정 여유(_menu_lines 설명 참고). 1.0 이면 경계선 메뉴명까지 접힌다.
WRAP_SLACK = 1.10


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


def _menu_lines(items, col_width: float, font_size: float) -> int:
    """메뉴 6개를 한 칸에 넣었을 때 실제로 차지하는 줄 수(사이 빈 줄 포함).

    ‘자동 줄 바꿈’을 켜면 긴 메뉴명은 두 줄로 접힌다. 그만큼 행을 키워야
    글자가 잘리지 않으므로, 접힌 줄까지 세어 둔다.
    엑셀 열 너비 단위는 '기본 글꼴(11pt) 숫자 한 글자 폭'이라, 실제 글꼴이
    크면 한 줄에 들어가는 글자 수가 그 비율만큼 줄어든다.

    WRAP_SLACK: 한글 글리프는 계산상 한 칸(1em)보다 조금 좁게 그려진다.
    이 여유가 없으면 6글자짜리 평범한 메뉴명(‘고추장불고기’)이 아슬아슬하게
    두 줄로 잡혀 행이 쓸데없이 커진다. 원본이 '한 항목 = 한 줄'(6개+빈 줄 5개
    = 11줄)로 설계돼 있으므로, 애매한 경우는 접지 않는 쪽으로 둔다.
    """
    budget = max(1.0, col_width * 11.0 / font_size) * WRAP_SLACK
    lines = 0
    for it in items:
        # 한글·한자·전각은 숫자 두 글자 폭으로 계산
        w = sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(it))
        lines += max(1, math.ceil(w / budget)) if w else 1
    return lines + max(0, len(items) - 1)   # 항목 사이 빈 줄


def _row_height(lines: int, base: float) -> float:
    """원본과 같은 높이를 유지하되, 줄이 11줄을 넘으면 그 비율만큼만 키운다."""
    return round(base * max(lines, BASE_LINES) / BASE_LINES, 2)


def _page(ws, landscape):
    """원본 시트의 pageSetup/printOptions/sheetFormatPr 를 그대로 재현."""
    from openpyxl.worksheet.page import PageMargins
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins = PageMargins(left=0 if landscape else 0.7,
                                  right=0 if landscape else 0.7,
                                  top=0.75, bottom=0.75, header=0.0, footer=0.0)
    # 원본: <printOptions gridLines="1" horizontalCentered="1"/>
    ws.print_options.horizontalCentered = True
    ws.print_options.gridLines = True
    ws.sheet_format.defaultColWidth = DEFAULT_COL_W
    ws.sheet_format.defaultRowHeight = DEFAULT_ROW_H


# ---- 배달형(달력형): 세로 A4, 한 시트에 중식/석식 ----
def _xlsx_delivery(wb, md: MonthData) -> None:
    ws = wb.create_sheet(f"배달-{md.year % 100:02d}.{md.month:02d}")
    for c in "ABCDEFG":            # 원본: <col min="1" max="7" width="31.38"/>
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
            _set(ws, r, ci, (day or None), font=FONT_BODY, size=29, bold=True,
                 fill=(GRAY if day else TEAL), valign=(None if day else "top"))
        ws.row_dimensions[r].height = DLV_ROW_H_HEAD
        lines = 0
        for ci, day in enumerate(week, start=1):
            has = day and md.has_meal(day, section)
            items = md.get(day, section) if has else []
            val = "\n\n".join(items) if has else None
            # wrap=True 여야 엑셀이 셀 안의 줄바꿈을 그대로 보여준다.
            _set(ws, r + 1, ci, val, font=FONT_BODY, size=26,
                 fill=(menu_fill if day else TEAL), valign="top", wrap=True)
            if has:
                lines = max(lines, _menu_lines(items, DLV_COL_W, 26))
        ws.row_dimensions[r + 1].height = _row_height(lines, DLV_ROW_H_MENU)
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
    ws.column_dimensions["A"].width = DEFAULT_COL_W   # 구분 칸(원본은 기본 너비)
    for c in "BCDEFGH":            # 원본: <col min="2" max="8" width="25.13"/>
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
            _set(ws, r + 1, ci + 2, (week[ci] or None), font=FONT_BODY, size=24,
                 bold=True, fill=BLUE, valign="top")
        ws.row_dimensions[r].height = KIT_ROW_H_HEAD
        ws.row_dimensions[r + 1].height = KIT_ROW_H_HEAD

        # 중식/석식 행
        for k, section in enumerate(SECTIONS):
            rr = r + 2 + k
            _set(ws, rr, 1, section, font=FONT_BODY, size=24, bold=True,
                 fill=(LAVENDER if section == "중식" else PEACH), valign="center")
            lines = 0
            for ci, day in enumerate(week):
                has = day and md.has_meal(day, section)
                items = md.get(day, section) if has else []
                val = "\n\n".join(items) if has else None
                _set(ws, rr, ci + 2, val, font=FONT_BODY, size=24, fill=GRAY,
                     valign="top", wrap=True)
                if has:
                    lines = max(lines, _menu_lines(items, KIT_COL_W, 24))
            ws.row_dimensions[rr].height = _row_height(lines, KIT_ROW_H_MENU)
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
