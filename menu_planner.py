#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한식 뷔페 식단표 자동 생성기 (Korean Buffet Menu Planner)
=========================================================
- 입력: 연도/월 (예: 2026, 7)
- 처리: 해당 월의 일수/요일/공휴일을 계산해 [중식]/[석식] 템플릿 구조 생성
        -> System Instruction + Few-shot 으로 비즈니스 규칙을 Gemini 에 주입
        -> 생성 결과를 코드 레벨 Validation 으로 검증
- 출력: 규칙에 맞는 식단표 텍스트

실행:
    pip install -r requirements.txt
    export GEMINI_API_KEY="..."
    python menu_planner.py 2026 7
    python menu_planner.py 2026 7 --model gemini-2.5-flash --dry-run
"""

from __future__ import annotations

import argparse
import calendar
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from menu_data import MenuPool, default_pool, render_pool_for_prompt

# ----------------------------------------------------------------------------
# 0. 도메인 상수 (규칙 검증 및 프롬프트 주입에 공통 사용)
# ----------------------------------------------------------------------------

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday() 0=월 ... 6=일

# 단가/조리 특성상 월 4회 이하로 제한되는 생선류
FISH_KEYWORDS: tuple[str, ...] = ("고등어", "조기", "굴비", "가자미", "가재미", "열기", "임연수", "갈치", "삼치")

# 평일 중식 전용 + 월 2회 제한
FRIED_CHICKEN = "후라이드치킨"
# 평일/주말 중식 전용
SUYUK = "수육"
# 월 1~2회, 최소 1주 간격
JJUKKUMI = "쭈꾸미"

# 출력에서 김치 종류는 항상 이 텍스트로 통일
KIMCHI_LABEL = "김치류"

# 한 줄(한 끼)에 반드시 6개 메뉴: 메인1 + 반찬3 + 김치류1 + 국1
MENU_COUNT_PER_MEAL = 6

# 2026년 대한민국 공휴일 (필요 시 외부 캘린더 API 로 대체 가능)
KR_HOLIDAYS_2026: dict[tuple[int, int], str] = {
    (1, 1): "신정",
    (2, 16): "설날연휴", (2, 17): "설날", (2, 18): "설날연휴",
    (3, 1): "삼일절", (3, 2): "삼일절대체",
    (5, 5): "어린이날/석가탄신일",
    (6, 6): "현충일",
    (8, 15): "광복절", (8, 17): "광복절대체",
    (9, 24): "추석연휴", (9, 25): "추석", (9, 26): "추석연휴",
    (10, 3): "개천절", (10, 5): "개천절대체",
    (10, 9): "한글날",
    (12, 25): "성탄절",
}


# ----------------------------------------------------------------------------
# 1. 달력 / 템플릿 구조 생성
# ----------------------------------------------------------------------------

@dataclass
class DaySlot:
    """식단표의 하루 단위 슬롯."""
    d: date
    is_weekend: bool
    is_holiday: bool
    holiday_name: str | None = None
    # 소방서 배달 특성상 기본적으로 매일 운영(휴무 없음).
    # 설날·추석 등 예외 휴무는 추후 이 플래그를 False 로 세팅해 제외 처리.
    is_operating: bool = True

    @property
    def weekday_kr(self) -> str:
        return WEEKDAY_KR[self.d.weekday()]

    @property
    def label(self) -> str:
        # 예: 7/1(수)
        return f"{self.d.month}/{self.d.day}({self.weekday_kr})"

    @property
    def cook_easy(self) -> bool:
        # 주말/공휴일은 조리 용이 메뉴 위주
        return self.is_weekend or self.is_holiday


@dataclass
class MonthPlan:
    """한 달치 식단 템플릿 구조."""
    year: int
    month: int
    days: list[DaySlot] = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"{self.year}년 {self.month}월"


def build_month_plan(
    year: int, month: int, closed_days: set[int] | None = None
) -> MonthPlan:
    """연/월을 받아 해당 월의 모든 날짜에 대한 템플릿 구조를 생성한다.

    소방서 배달 특성상 기본적으로 매일(평일/주말/공휴일) 운영한다.
    설날·추석 등 예외 휴무가 필요하면 closed_days 에 '일(day)' 집합을 넘긴다.
    (예: closed_days={17, 18} -> 17·18일 식단 제외)
    """
    if not (1 <= month <= 12):
        raise ValueError(f"잘못된 월: {month}")

    closed_days = closed_days or set()
    _, last_day = calendar.monthrange(year, month)
    plan = MonthPlan(year=year, month=month)

    for day in range(1, last_day + 1):
        d = date(year, month, day)
        is_weekend = d.weekday() >= 5  # 토(5), 일(6)
        holiday_name = KR_HOLIDAYS_2026.get((month, day)) if year == 2026 else None
        plan.days.append(
            DaySlot(
                d=d,
                is_weekend=is_weekend,
                is_holiday=holiday_name is not None,
                holiday_name=holiday_name,
                is_operating=day not in closed_days,
            )
        )
    return plan


def render_template_hint(plan: MonthPlan) -> str:
    """모델에게 '채워야 할 날짜 골격'과 날짜별 속성(주말/공휴일/조리편의)을 전달."""
    lines: list[str] = []
    for s in plan.days:
        if not s.is_operating:
            continue  # 예외 휴무일은 골격에서 제외
        tags = []
        if s.is_holiday:
            tags.append(f"공휴일:{s.holiday_name}")
        elif s.is_weekend:
            tags.append("주말")
        else:
            tags.append("평일")
        if s.cook_easy:
            tags.append("조리용이메뉴")
        lines.append(f"- {s.label} [{', '.join(tags)}]")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# 2. 프롬프트 (System Instruction + Few-shot)
# ----------------------------------------------------------------------------

SYSTEM_INSTRUCTION = f"""\
당신은 한식 뷔페의 영양사 겸 식단 기획 전문가입니다.
주어진 달력 골격을 바탕으로 매일 [중식]과 [석식] 식단을 편성합니다.
아래 비즈니스 규칙을 단 하나도 어기지 말고 정확히 지켜서 식단표 '텍스트만' 출력하세요.

[식단 구성 규칙]
1. 매일 중식/석식 각각 정확히 {MENU_COUNT_PER_MEAL}개 메뉴를 한 줄에 표기한다.
   순서: 메인요리1, 반찬3, {KIMCHI_LABEL}, 국1  (쉼표+공백으로 구분)
2. 김치 종류(배추김치, 깍두기, 총각김치 등)는 무조건 "{KIMCHI_LABEL}" 한 단어로만 적는다.
3. 다음은 절대 메뉴명에 포함하지 않는다(간략하게 메뉴명만):
   - 쌈류(상추쌈, 양배추쌈 등)
   - 소스류(새우젓, 쌈장, 초장 등)
   - 국 이름 앞 수식 조사(맑은, 얼큰한, 시원한 등) → 예) '맑은콩나물국' → '콩나물국'

[중복/밸런스 규칙]
4. 같은 메인 메뉴는 최소 4일 이내 재등장 금지(같은 메인은 4일 간격 이상).
5. 모든 메인 요리가 한 달에 최소 1회 이상 골고루 나오도록 밸런스를 맞춘다.
6. A/B/C 팀 구분 기준으로 메인 요리가 자주 겹치지 않게 분산 설계한다.

[특정 메뉴 제한]
7. '{SUYUK}': 평일/주말 '중식'에만 편성(석식 금지).
8. '{FRIED_CHICKEN}': '평일 중식'에만 편성, 한 달에 정확히 2회.
9. '{JJUKKUMI}': 한 달 최소 1회~최대 2회, 연속 등장 금지(최소 1주 건너뜀).
10. 생선류(고등어/조기/굴비/가자미/열기 등): 단가·조리 특성상 한 달 총합 4회 이하로 엄격 제한.

[맛/조리 편의]
11. 점심(중식)은 자극적이고 든든한 맛, 저녁(석식)은 깔끔하고 담백한 맛으로 배치.
12. 저녁/주말/공휴일은 조리가 용이한 메뉴(난이도 낮음) 위주로 배치.

[운영일]
13. 소방서 배달 특성상 평일/주말/공휴일 '모든 운영일'에 중식·석식을 빠짐없이 편성한다.
    (휴무일은 입력 골격에서 이미 제외되어 전달되므로, 전달된 날짜는 전부 채운다.)

[메뉴 선택]
14. 아래 '허용 메뉴 풀' 위주로 선택하고 각 메뉴의 속성/제한(끼니, 평일만, 월최대 등)을 지킨다.
    풀로 다양성이 부족할 때만 동일 스타일의 한식 메뉴로 보충한다.

[출력 포맷] (조사/불필요한 줄바꿈 없이, 날짜 사이 빈 줄 없음)
[중식]
M/D(요일): 메인, 반찬, 반찬, 반찬, {KIMCHI_LABEL}, 국
... (전달된 모든 운영일)
[석식]
M/D(요일): 메인, 반찬, 반찬, 반찬, {KIMCHI_LABEL}, 국
... (전달된 모든 운영일)

설명/머리말/코드블록 표시(```) 없이 식단표 텍스트만 출력하세요.
"""

# Few-shot: 포맷과 규칙 적용 예시 (모델이 형식을 모방하도록)
FEWSHOT_EXAMPLE = """\
[예시 출력 형식]
[중식]
7/1(수): 고추장불고기, 어묵볶음, 감자조림, 마늘쫑무침, 김치류, 콩나물국
7/2(목): 닭볶음탕, 계란찜, 콩나물무침, 브로콜리숙회, 김치류, 배추된장국
[석식]
7/1(수): 가자미구이, 연근조림, 시래기나물무침, 오이무침, 김치류, 미역국
7/2(목): 제육볶음, 도라지무침, 호박나물, 멸치볶음, 김치류, 무국
"""


def build_user_prompt(plan: MonthPlan, pool: MenuPool | None = None, correction: str = "") -> str:
    """달력 골격 + 허용 메뉴 풀 + 규칙 리마인드를 담은 사용자 프롬프트.

    correction: 직전 결과의 규칙 위반 목록(있으면 재생성 보정 지시로 덧붙임).
    """
    pool = pool or default_pool()
    fix_block = ""
    if correction:
        fix_block = (
            "\n\n[직전 결과에서 아래 규칙 위반이 발견되었습니다. 반드시 모두 고쳐 다시 생성하세요]\n"
            f"{correction}\n"
        )
    return (
        f"{FEWSHOT_EXAMPLE}\n"
        f"위 형식을 그대로 따라 '{plan.title}' 식단표를 생성하세요.\n\n"
        f"{render_pool_for_prompt(pool)}\n\n"
        f"아래는 채워야 할 운영일 골격입니다(각 날짜 속성 포함). "
        f"전달된 날짜는 전부 중식·석식을 채우고, '조리용이메뉴' 태그가 붙은 날은 "
        f"난이도 낮은 메뉴로 배치하세요.\n\n"
        f"{render_template_hint(plan)}\n\n"
        f"모든 비즈니스 규칙(6개 메뉴/김치류/생선 4회 이하/후라이드치킨 2회/쭈꾸미 1~2회/"
        f"4일 중복금지 등)을 반드시 준수하세요."
        f"{fix_block}"
    )


# ----------------------------------------------------------------------------
# 3. Gemini API 호출
# ----------------------------------------------------------------------------

def generate_menu(
    year: int,
    month: int,
    model: str = "gemini-2.5-pro",
    api_key: str | None = None,
    temperature: float = 0.8,
    closed_days: set[int] | None = None,
    pool: MenuPool | None = None,
    correction: str = "",
) -> str:
    """연/월을 받아 Gemini 를 호출하고 식단표 텍스트를 반환한다.

    closed_days: 예외 휴무일(일자 집합). pool: 허용 메뉴 풀(미지정 시 시드 사용).
    correction: 재생성 보정 지시(규칙 위반 목록).
    """
    # 신규 google-genai SDK 사용 (from google import genai)
    from google import genai
    from google.genai import types

    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini API 키가 필요합니다. (환경변수 GEMINI_API_KEY 또는 설정에서 입력)")

    plan = build_month_plan(year, month, closed_days=closed_days)
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=build_user_prompt(plan, pool=pool, correction=correction),
        config=types.GenerateContentConfig(
            # 데이터 정형성을 위한 System Instruction 설정 부분
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=temperature,
            top_p=0.9,
        ),
    )
    return (response.text or "").strip()


def generate_validated_menu(
    year: int,
    month: int,
    model: str = "gemini-2.5-flash",
    api_key: str | None = None,
    temperature: float = 0.8,
    closed_days: set[int] | None = None,
    pool: MenuPool | None = None,
    max_retries: int = 2,
    progress=None,
) -> tuple[str, list[str]]:
    """검증을 통과할 때까지(최대 max_retries회) 재생성한다.

    반환: (식단표 텍스트, 남은 위반 목록).  위반이 비어 있으면 완전 통과.
    progress: 진행 상황을 받을 콜백 (예: GUI 상태표시). progress(str) 형태.
    """
    correction = ""
    text = ""
    errors: list[str] = []
    for attempt in range(1, max_retries + 2):  # 최초 1회 + 재시도 max_retries회
        if progress:
            progress(f"식단표 생성 중... (시도 {attempt})")
        text = generate_menu(
            year, month, model=model, api_key=api_key, temperature=temperature,
            closed_days=closed_days, pool=pool, correction=correction,
        )
        errors = validate_menu(text)
        if not errors:
            if progress:
                progress("완료: 모든 규칙 통과")
            return text, []
        # 위반을 보정 지시로 만들어 다음 시도에 반영
        correction = "\n".join(f"- {e}" for e in errors)
        if progress:
            progress(f"규칙 위반 {len(errors)}건 → 보정 후 재생성")
    if progress:
        progress(f"완료(일부 규칙 미충족 {len(errors)}건)")
    return text, errors


# ----------------------------------------------------------------------------
# 4. 코드 레벨 Validation (프롬프트가 어겼을 때를 대비한 2차 방어선)
# ----------------------------------------------------------------------------

@dataclass
class MealLine:
    section: str          # "중식" | "석식"
    date_label: str       # "7/1(수)"
    main: str
    items: list[str]      # 전체 6개 메뉴
    raw: str


LINE_RE = re.compile(r"^(?P<date>\d{1,2}/\d{1,2}\([월화수목금토일]\)):\s*(?P<body>.+)$")


def parse_menu_text(text: str) -> list[MealLine]:
    """모델 출력 텍스트를 구조화한다."""
    meals: list[MealLine] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        items = [x.strip() for x in m.group("body").split(",") if x.strip()]
        meals.append(
            MealLine(
                section=section,
                date_label=m.group("date"),
                main=items[0] if items else "",
                items=items,
                raw=line,
            )
        )
    return meals


def _contains_fish(name: str) -> bool:
    return any(k in name for k in FISH_KEYWORDS)


def _day_index(date_label: str) -> int:
    # "7/1(수)" -> 1
    return int(date_label.split("/")[1].split("(")[0])


def validate_menu(text: str) -> list[str]:
    """비즈니스 규칙 위반 목록을 반환한다(빈 리스트 = 통과)."""
    errors: list[str] = []
    meals = parse_menu_text(text)
    if not meals:
        return ["파싱된 식단 라인이 없습니다(출력 포맷 오류)."]

    lunches = [m for m in meals if m.section == "중식"]

    # (1) 끼니별 6개 메뉴 + 김치류 정확히 1개
    for m in meals:
        if len(m.items) != MENU_COUNT_PER_MEAL:
            errors.append(f"[{m.section} {m.date_label}] 메뉴 {len(m.items)}개 (6개 아님): {m.raw}")
        if m.items.count(KIMCHI_LABEL) != 1:
            errors.append(f"[{m.section} {m.date_label}] '{KIMCHI_LABEL}' 정확히 1개여야 함: {m.raw}")

    # (4) 동일 메인 4일 이내 재등장 금지 (섹션별 일자 기준)
    for section in ("중식", "석식"):
        seen: dict[str, int] = {}
        for m in [x for x in meals if x.section == section]:
            di = _day_index(m.date_label)
            if m.main in seen and (di - seen[m.main]) < 4:
                errors.append(
                    f"[{section}] 메인 '{m.main}' 4일 이내 재등장 ({seen[m.main]}일→{di}일)"
                )
            seen[m.main] = di

    # (7) 수육: 중식에만
    for m in meals:
        if SUYUK in m.main and m.section != "중식":
            errors.append(f"[{m.section} {m.date_label}] '{SUYUK}'는 중식에만 편성 가능")

    # (8) 후라이드치킨: 평일 중식, 월 2회
    fc = [m for m in meals if FRIED_CHICKEN in m.main]
    for m in fc:
        if m.section != "중식":
            errors.append(f"[{m.section} {m.date_label}] '{FRIED_CHICKEN}'는 중식 전용")
    if len(fc) != 2:
        errors.append(f"'{FRIED_CHICKEN}' 월 2회여야 함(현재 {len(fc)}회)")

    # (9) 쭈꾸미: 월 1~2회, 연속(같은 주) 금지
    jj_days = sorted(_day_index(m.date_label) for m in lunches if JJUKKUMI in m.main) \
        or sorted(_day_index(m.date_label) for m in meals if JJUKKUMI in m.main)
    if not (1 <= len(jj_days) <= 2):
        errors.append(f"'{JJUKKUMI}' 월 1~2회여야 함(현재 {len(jj_days)}회)")
    if len(jj_days) == 2 and (jj_days[1] - jj_days[0]) < 7:
        errors.append(f"'{JJUKKUMI}' 최소 1주 간격 필요(간격 {jj_days[1]-jj_days[0]}일)")

    # (10) 생선류 월 4회 이하
    fish_count = sum(1 for m in meals if _contains_fish(m.main))
    if fish_count > 4:
        errors.append(f"생선류 월 4회 이하 위반(현재 {fish_count}회)")

    return errors


# ----------------------------------------------------------------------------
# 5. CLI
# ----------------------------------------------------------------------------

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="한식 뷔페 식단표 생성기")
    parser.add_argument("year", type=int, help="연도 (예: 2026)")
    parser.add_argument("month", type=int, help="월 (예: 7)")
    parser.add_argument("--model", default="gemini-2.5-pro",
                        choices=["gemini-2.5-pro", "gemini-2.5-flash"])
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--closed-days", default="",
                        help="예외 휴무일(쉼표구분 일자). 예: --closed-days 17,18 (설날 등)")
    parser.add_argument("--dry-run", action="store_true",
                        help="API 호출 없이 달력 골격/프롬프트만 출력")
    args = parser.parse_args(list(argv) if argv is not None else None)

    closed_days = {int(x) for x in args.closed_days.split(",") if x.strip()}
    plan = build_month_plan(args.year, args.month, closed_days=closed_days)

    if args.dry_run:
        print(f"=== {plan.title} 운영일 골격 ===")
        print(render_template_hint(plan))
        print("\n=== 허용 메뉴 풀 ===")
        print(render_pool_for_prompt(default_pool()))
        print("\n=== System Instruction ===")
        print(SYSTEM_INSTRUCTION)
        return 0

    text = generate_menu(args.year, args.month, model=args.model,
                         temperature=args.temperature, closed_days=closed_days)
    print(text)

    errors = validate_menu(text)
    if errors:
        print("\n=== ⚠ 규칙 위반 검출 (재생성 권장) ===", file=sys.stderr)
        for e in errors:
            print(f" - {e}", file=sys.stderr)
        return 1

    print("\n=== ✅ 모든 비즈니스 규칙 검증 통과 ===", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
