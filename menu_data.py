# -*- coding: utf-8 -*-
"""
메뉴 마스터 데이터 (시드/Seed)
================================
하이브리드 전략의 '코드 측' 데이터.
- 이 풀을 Gemini 에 '허용 어휘'로 전달해 변동성·원가를 통제한다.
- 각 메뉴의 속성(flavor/difficulty/meal_scope/월간제한 등)으로
  비즈니스 규칙을 코드와 프롬프트 양쪽에서 강제할 수 있게 한다.
- ⚠ 아래 값들은 실제 운영 마스터 데이터로 교체할 자리(Seed)다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ----------------------------------------------------------------------------
# 메인 요리 (속성 포함)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class MainDish:
    name: str
    flavor: str = "자극"          # "자극"(점심 선호) | "담백"(저녁 선호)
    difficulty: int = 2           # 1=쉬움(주말/공휴일/저녁 선호) ~ 3=어려움
    meal_scope: str = "both"      # "lunch" | "dinner" | "both"
    is_fish: bool = False         # 생선류(월 4회 이하 합산 대상)
    team: str = "A"               # A/B/C 분산 그룹
    monthly_max: int | None = None      # 월간 최대 편성 횟수(없으면 무제한)
    monthly_min: int = 1                # 월간 최소 편성 횟수(밸런스)
    min_gap_days: int = 4               # 동일 메인 재등장 최소 간격(기본 4일)
    weekday_only: bool = False          # 평일만 편성 가능


# 시드 메인 풀 — 실제 운영 메뉴로 교체 예정
MAIN_DISHES: list[MainDish] = [
    # --- 자극적인 맛 (점심 선호) ---
    MainDish("고추장불고기", flavor="자극", difficulty=2, team="A"),
    MainDish("제육볶음",     flavor="자극", difficulty=2, team="A"),
    MainDish("닭볶음탕",     flavor="자극", difficulty=3, team="B"),
    MainDish("매운돼지갈비찜", flavor="자극", difficulty=3, team="B"),
    MainDish("오징어볶음",   flavor="자극", difficulty=2, team="C"),
    MainDish("낙지볶음",     flavor="자극", difficulty=3, team="C"),
    MainDish("닭갈비",       flavor="자극", difficulty=2, team="A"),
    # 특수 제한 메뉴
    MainDish("쭈꾸미",  flavor="자극", difficulty=3, team="C",
             monthly_max=2, monthly_min=1, min_gap_days=7),
    MainDish("후라이드치킨", flavor="자극", difficulty=2, team="B",
             meal_scope="lunch", monthly_max=2, monthly_min=2, weekday_only=True),
    MainDish("수육", flavor="담백", difficulty=2, team="A", meal_scope="lunch"),

    # --- 담백한 맛 (저녁 선호) ---
    MainDish("불고기",       flavor="담백", difficulty=1, team="A"),
    MainDish("갈비찜",       flavor="담백", difficulty=3, team="B"),
    MainDish("닭백숙",       flavor="담백", difficulty=2, team="C", meal_scope="dinner"),
    MainDish("동그랑땡",     flavor="담백", difficulty=1, team="A"),
    MainDish("돈까스",       flavor="담백", difficulty=1, team="B"),
    MainDish("계란말이",     flavor="담백", difficulty=1, team="C", meal_scope="dinner"),

    # --- 생선류 (월 4회 이하 합산) ---
    MainDish("고등어구이", flavor="담백", difficulty=2, is_fish=True, team="B"),
    MainDish("가자미구이", flavor="담백", difficulty=2, is_fish=True, team="C"),
    MainDish("조기구이",   flavor="담백", difficulty=2, is_fish=True, team="A"),
    MainDish("갈치조림",   flavor="자극", difficulty=3, is_fish=True, team="B"),
]


# ----------------------------------------------------------------------------
# 반찬 / 국 (이름 위주 — 추후 속성 확장 가능)
# ----------------------------------------------------------------------------

# 반찬 풀 (한 끼 3개): flavor 균형용으로 분류만 가볍게
SIDE_DISHES: list[str] = [
    "어묵볶음", "감자조림", "마늘쫑무침", "계란찜", "콩나물무침", "브로콜리숙회",
    "연근조림", "시래기나물무침", "오이무침", "도라지무침", "호박나물", "멸치볶음",
    "미역줄기볶음", "잡채", "골뱅이무침", "두부조림",
    "가지나물", "숙주나물", "고사리나물", "무생채",
]

# 국 풀 (수식 조사 없이 메뉴명만)
SOUPS: list[str] = [
    "콩나물국", "배추된장국", "미역국", "무국", "북엇국", "시금치된장국",
    "감자국", "어묵국", "김치국", "황태국", "근대국", "유부국",
]


@dataclass
class MenuPool:
    mains: list[MainDish] = field(default_factory=lambda: list(MAIN_DISHES))
    sides: list[str] = field(default_factory=lambda: list(SIDE_DISHES))
    soups: list[str] = field(default_factory=lambda: list(SOUPS))


def default_pool() -> MenuPool:
    return MenuPool()


def render_pool_for_prompt(pool: MenuPool) -> str:
    """허용 어휘(메인 풀 + 속성, 반찬/국 풀)를 프롬프트용 텍스트로 직렬화."""
    lines = ["[허용 메인 요리 풀] (이 목록 위주로 선택, 속성/제한 준수)"]
    for m in pool.mains:
        tags = [m.flavor, f"난이도{m.difficulty}", f"팀{m.team}", f"끼니:{m.meal_scope}"]
        if m.is_fish:
            tags.append("생선류")
        if m.weekday_only:
            tags.append("평일만")
        if m.monthly_max is not None:
            tags.append(f"월최대{m.monthly_max}")
        lines.append(f"- {m.name} ({', '.join(tags)})")
    lines.append("\n[반찬 풀] " + ", ".join(pool.sides))
    lines.append("[국 풀] " + ", ".join(pool.soups))
    return "\n".join(lines)
