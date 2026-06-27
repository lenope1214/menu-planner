# -*- coding: utf-8 -*-
"""
식단표 내보내기/인쇄 유틸
==========================
- 텍스트 저장(.txt)
- 엑셀 저장(.xlsx)  ← openpyxl
- 인쇄(Windows: 메모장 인쇄 동사 사용 / 그 외: 안내)
"""

from __future__ import annotations

import os
import sys
import tempfile

from menu_planner import parse_menu_text


# ----------------------------------------------------------------------------
# 텍스트 저장
# ----------------------------------------------------------------------------

def save_txt(text: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ----------------------------------------------------------------------------
# 엑셀 저장 (.xlsx)
# ----------------------------------------------------------------------------

def save_xlsx(text: str, path: str, title: str = "식단표") -> None:
    """식단표 텍스트를 표 형태(.xlsx)로 저장한다."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    meals = parse_menu_text(text)
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31] or "식단표"

    headers = ["구분", "날짜", "메인요리", "반찬1", "반찬2", "반찬3", "김치", "국"]
    ws.append(headers)
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill("solid", fgColor="D9E1F2")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for m in meals:
        items = m.items + [""] * (6 - len(m.items))  # 6칸 보장
        ws.append([m.section, m.date_label, *items[:6]])

    # 보기 좋은 열 너비/정렬(어르신 가독성)
    widths = [8, 12, 14, 12, 12, 12, 8, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(size=11)

    wb.save(path)


# ----------------------------------------------------------------------------
# 인쇄
# ----------------------------------------------------------------------------

def print_text(text: str, title: str = "식단표") -> str:
    """식단표를 인쇄한다.

    Windows: 임시 텍스트 파일을 만들어 OS 인쇄 동사로 기본 프린터에 전송.
    그 외 OS: 임시 파일 경로를 반환(직접 인쇄 안내용).
    반환: 생성된 임시 파일 경로.
    """
    body = f"{title}\n{'=' * 40}\n\n{text}\n"
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="menu_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)

    if sys.platform.startswith("win"):
        # Windows 전용: 등록된 인쇄 동사로 기본 프린터에 출력
        os.startfile(path, "print")  # type: ignore[attr-defined]
    return path
