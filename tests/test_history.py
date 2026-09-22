# -*- coding: utf-8 -*-
"""
과거 식단 기록(history.py) 잠금
================================
쌓인 기록은 되돌릴 수 없는 데이터라 저장/교체 규칙이 특히 중요하다.
- 과거 식단 창의 저장 = **교체**(화면에서 비운 칸이 지워져야 한다)
- 엑셀 가져오기 / 현재 표 저장 = **덮어쓰기**(다른 날짜를 지우면 안 된다)
"""

from __future__ import annotations

from datetime import date

import exporters as ex
import history
import layouts
from layouts import PRESET_CALENDAR, PRESET_KITCHEN

LUNCH = ["제육볶음", "어묵볶음", "감자조림", "마늘쫑무침", "김치류", "콩나물국"]
DINNER = ["고등어구이", "연근조림", "호박나물", "오이무침", "김치류", "미역국"]
LUNCH30 = ["닭볶음탕", "계란찜", "콩나물무침", "브로콜리숙회", "김치류", "배추된장국"]
DINNER30 = ["수육", "도라지무침", "시래기나물", "멸치볶음", "김치류", "무국"]


def _june():
    md = layouts.MonthData(year=2026, month=6)
    md.meals[29] = {"중식": list(LUNCH), "석식": list(DINNER)}
    md.meals[30] = {"중식": list(LUNCH30), "석식": list(DINNER30)}
    return md


# ---- 저장/조회 ----

def test_저장하고_그대로_읽는다():
    assert history.save_month(_june()) == 2
    back = history.get_month(2026, 6)
    assert back.get(29, "중식") == LUNCH
    assert back.get(30, "석식") == DINNER30
    assert history.day_count() == 2
    assert history.recorded_months() == [(2026, 6)]


def test_모자란_칸은_여섯_칸으로_채운다():
    md = layouts.MonthData(year=2026, month=6)
    md.meals[1] = {"중식": ["비빔밥", "잡채"]}
    history.save_month(md)
    assert history.get_month(2026, 6).get(1, "중식") == ["비빔밥", "잡채", "", "", "", ""]


def test_교체_저장은_빠진_날짜를_지운다():
    history.save_month(_june())
    only_one = layouts.MonthData(year=2026, month=6)
    only_one.meals[1] = {"중식": list(LUNCH)}
    history.save_month(only_one, merge=False)
    assert history.day_count() == 1


def test_덮어쓰기_저장은_다른_날짜를_남긴다():
    history.save_month(_june())
    extra = layouts.MonthData(year=2026, month=6)
    extra.meals[1] = {"중식": list(LUNCH)}
    history.save_month(extra, merge=True)
    assert history.day_count() == 3


def test_빈_달은_통째로_지운다():
    history.save_month(_june())
    history.save_month(layouts.MonthData(year=2026, month=6))
    assert history.recorded_months() == []


def test_달_삭제():
    history.save_month(_june())
    assert history.delete_month(2026, 6) is True
    assert history.delete_month(2026, 6) is False


# ---- 통계 / 꼬리 ----

def test_메인_사용현황():
    history.save_month(_june())
    st = history.main_stats()
    assert st["제육볶음"]["count"] == 1
    assert st["제육볶음"]["last"] == date(2026, 6, 29)


def test_기준일_이전만_센다():
    history.save_month(_june())
    assert "닭볶음탕" not in history.main_stats(before=date(2026, 6, 30))


def test_지난달_꼬리의_상대일():
    """상대일은 '대상 월 1일 = 1' 기준 — 생성 결과의 일(day)에서 바로 빼려고."""
    history.save_month(_june())
    tail = history.recent_tail(2026, 7)
    assert (0, "중식", "닭볶음탕", "6/30") in tail      # 지난달 마지막 날 = 0
    assert (-1, "중식", "제육볶음", "6/29") in tail     # 그 전날 = -1


def test_꼬리는_기간_밖을_안_가져온다():
    history.save_month(_june())
    assert history.recent_tail(2026, 8) == []          # 6월은 8월 기준 너무 멀다


def test_이름_모으기는_김치류를_뺀다():
    history.save_month(_june())
    names = history.all_names()
    assert "제육볶음" in names and "미역국" in names
    assert "김치류" not in names


def test_자리별로_이름을_모은다():
    history.save_month(_june())
    slots = history.slot_names()
    assert "수육" in slots["mains"]
    assert "계란찜" in slots["sides"]
    assert "무국" in slots["soups"]
    assert "수육" not in slots["soups"]


# ---- 프롬프트 블록 ----

def test_참고_모드는_실제_식단과_사용현황을_싣는다():
    history.save_month(_june())
    blk = history.prompt_block(2026, 7, history.MODE_REF)
    assert "6/29(월): 제육볶음" in blk
    assert "과거 메인 요리 사용 현황" in blk
    assert "과거에 냈던 메뉴만 사용" not in blk


def test_과거메뉴만_모드는_허용목록을_붙인다():
    history.save_month(_june())
    blk = history.prompt_block(2026, 7, history.MODE_ONLY)
    assert "과거에 냈던 메뉴만 사용" in blk
    assert "· 메인: " in blk


def test_끄면_아무것도_안_싣는다():
    history.save_month(_june())
    assert history.prompt_block(2026, 7, history.MODE_OFF) == ""


def test_대상_월_이전_기록만_참고한다():
    history.save_month(_june())
    assert history.prompt_block(2026, 6, history.MODE_REF) == ""


def test_기록이_없으면_빈_블록():
    assert history.prompt_block(2026, 7, history.MODE_REF) == ""


# ---- 엑셀 가져오기(내보내기와 왕복) ----

def test_엑셀_왕복이_그대로_돌아온다(tmp_path):
    """exporters 로 저장한 파일을 history 가 다시 읽어야 한다(두 서식 모두)."""
    src = layouts.month_data_to_text(_june())
    for preset in (PRESET_CALENDAR, PRESET_KITCHEN):
        p = tmp_path / f"{preset}.xlsx"
        ex.save_xlsx(src, str(p), preset=preset, year=2026, month=6)
        history.delete_month(2026, 6)
        assert history.import_xlsx(str(p)) == [(2026, 6, 2)]
        back = history.get_month(2026, 6)
        assert back.get(29, "중식") == LUNCH, preset
        assert back.get(30, "석식") == DINNER30, preset


def test_안내문이_메뉴로_딸려오지_않는다(tmp_path):
    p = tmp_path / "t.xlsx"
    ex.save_xlsx(layouts.month_data_to_text(_june()), str(p),
                 preset=PRESET_CALENDAR, year=2026, month=6)
    history.import_xlsx(str(p))
    got = history.get_month(2026, 6)
    assert sorted(got.meals) == [29, 30]         # ※ 안내문 칸이 날짜로 들어오면 깨진다


def test_시트이름에서_연월을_읽는다():
    assert history._ym_from_sheet("배달-26.07") == (2026, 7)
    assert history._ym_from_sheet("주방-26.07") == (2026, 7)
    assert history._ym_from_sheet("Sheet1") is None


# ---- 요약 ----

def test_요약_문구():
    assert history.summary() == "아직 기록이 없어요."
    history.save_month(_june())
    assert history.summary() == "2026.06 · 1개월 2일 기록됨"
