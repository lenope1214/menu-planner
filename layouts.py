# -*- coding: utf-8 -*-
"""
식단표 레이아웃(프리셋) 공용 모델
==================================
생성된 식단표 텍스트를 '프리셋' 레이아웃으로 그리기 위한 공용 데이터 구조.
- 기본형1(달력형): 요일(일~토) × 주(week). 중식/석식 표를 따로 그린다.
- 기본형2(주방형): 구분(중식/석식) + 요일 7칸. 1주일 단위로 중식·석식을 한 표에.

GUI 미리보기와 엑셀/인쇄 내보내기가 '같은' 구조(MonthData)를 공유한다.
"""

from __future__ import annotations

import calendar
import datetime
import re
from dataclasses import dataclass, field

from menu_planner import parse_menu_text

# ----------------------------------------------------------------------------
# 프리셋 식별자/라벨
# ----------------------------------------------------------------------------
PRESET_CALENDAR = "달력형"   # 배달용: 한 시트에 중식/석식 월간 달력
PRESET_KITCHEN = "주방형"    # 주방용: 주 단위 4행 블록(요일/날짜/중식/석식)
PRESETS = [PRESET_CALENDAR, PRESET_KITCHEN]
PRESET_LABELS = {
    PRESET_CALENDAR: "배달용 (월간 달력)",
    PRESET_KITCHEN: "주방용 (주간)",
}

# ----------------------------------------------------------------------------
# 구조 상수
# ----------------------------------------------------------------------------
SECTIONS = ["중식", "석식"]
ITEMS_PER_MEAL = 6                     # 한 끼 6줄: 메인1 + 반찬3 + 김치류1 + 국1
ROW_LABELS = ["메인", "반찬", "반찬", "반찬", "김치류", "국"]

# 달력은 '일요일 시작'(예제 기준)
WEEKDAYS_KR = ["일", "월", "화", "수", "목", "금", "토"]

FOOTER_NOTE = "※ 본 식단은 산지 공급 및 주방 상황에 따라 일부 변경될 수 있음을 양해 부탁드립니다."

_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})\(([월화수목금토일])\)")


# ----------------------------------------------------------------------------
# 월 데이터 모델
# ----------------------------------------------------------------------------
@dataclass
class MonthData:
    """한 달치 식단을 day -> {중식:[6], 석식:[6]} 로 보관."""
    year: int
    month: int
    meals: dict[int, dict[str, list[str]]] = field(default_factory=dict)

    def get(self, day: int, section: str) -> list[str]:
        return self.meals.get(day, {}).get(section, [""] * ITEMS_PER_MEAL)

    def set_item(self, day: int, section: str, idx: int, value: str) -> None:
        arr = self.meals.setdefault(day, {}).setdefault(section, [""] * ITEMS_PER_MEAL)
        if 0 <= idx < ITEMS_PER_MEAL:
            arr[idx] = value

    def has_meal(self, day: int, section: str) -> bool:
        return section in self.meals.get(day, {})

    def is_empty(self) -> bool:
        return not self.meals


def parse_date_label(label: str) -> tuple[int, int, str] | None:
    """'7/1(수)' -> (month, day, weekday). 실패 시 None."""
    m = _DATE_RE.search(label)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3)


def build_month_data(text: str, year: int, month: int) -> MonthData:
    """모델 출력 텍스트 -> MonthData (6칸 보장)."""
    md = MonthData(year=year, month=month)
    for meal in parse_menu_text(text):
        parsed = parse_date_label(meal.date_label)
        if not parsed:
            continue
        _, day, _wd = parsed
        items = list(meal.items)[:ITEMS_PER_MEAL]
        items += [""] * (ITEMS_PER_MEAL - len(items))
        md.meals.setdefault(day, {})[meal.section] = items
    return md


def month_data_to_text(md: MonthData) -> str:
    """MonthData(편집 반영) -> 표준 식단표 텍스트(파서/검증/내보내기 호환)."""
    lines: list[str] = []
    for section in SECTIONS:
        days = [d for d in sorted(md.meals) if md.has_meal(d, section)]
        if not days:
            continue
        lines.append(f"[{section}]")
        for day in days:
            wd = weekday_of(md.year, md.month, day)
            items = md.get(day, section)
            lines.append(f"{md.month}/{day}({wd}): " + ", ".join(items))
    return "\n".join(lines)


def calendar_weeks(year: int, month: int) -> list[list[int]]:
    """일요일 시작 달력 행렬. 각 주는 정수 7개(day), 0=빈칸."""
    cal = calendar.Calendar(firstweekday=6)  # 6=일요일
    return cal.monthdayscalendar(year, month)


def weekday_of(year: int, month: int, day: int) -> str:
    """해당 날짜의 한글 요일(일~토)."""
    # date.weekday(): 월=0..일=6  ->  일요일 시작 인덱스로 변환
    return WEEKDAYS_KR[(datetime.date(year, month, day).weekday() + 1) % 7]
