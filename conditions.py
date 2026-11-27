# -*- coding: utf-8 -*-
"""
식단 조건(규칙) 모델 + 검증 + 프롬프트 변환
=============================================
사용자가 등록/수정/삭제하는 '조건'을 구조화한다. 같은 조건을
- 프롬프트(Gemini가 지키도록 지시)와
- 코드 검증(validate, 위반 시 자동 재생성)
양쪽에서 공유한다.

조건 dict 형태(type 별):
- menu_count : {"type","menu","op"("<="/"=="/">="),"count"}
- menu_gap   : {"type","menu","days"}
- menu_section: {"type","menu","section"("중식"/"석식")}
- menu_weekday: {"type","menu","weekdays":["일", ...]}  # 그 요일에만 편성
- category_max: {"type","category"("생선류"),"max"}
"""

from __future__ import annotations

import datetime
import re

# 카테고리(키워드 기반)
FISH_KEYWORDS = ("고등어", "조기", "굴비", "가자미", "가재미", "열기", "임연수", "갈치", "삼치")
CATEGORIES = {"생선류": FISH_KEYWORDS}

TYPES = ["text", "menu_count", "menu_section", "menu_weekday", "menu_gap", "category_max"]
TYPE_LABELS = {
    "text": "서술형 (문장으로 쓰기)",
    "menu_count": "메뉴 월 횟수",
    "menu_section": "메뉴 끼니 제한",
    "menu_weekday": "메뉴 요일 제한",
    "menu_gap": "같은 메뉴 최소 간격",
    "category_max": "생선류 월 최대",
}
OPS = {"<=": "이하", "==": "정확히", ">=": "이상"}

# 요일 선택지(달력 표기와 같은 순서: 일~토)
WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]

_DATE = re.compile(r"\d{1,2}/(\d{1,2})")
_WDAY = re.compile(r"\(([월화수목금토일])\)")


def _day(label: str) -> int:
    m = _DATE.search(label)
    return int(m.group(1)) if m else 0


def _wday(label: str) -> str:
    """'7/1(수)' -> '수'. 못 읽으면 빈 문자열."""
    m = _WDAY.search(label)
    return m.group(1) if m else ""


def _eun(word: str) -> str:
    """받침 유무에 맞는 조사(은/는). '비빔밥는' 같은 어색한 표기 방지."""
    ch = (word or "")[-1:] or ""
    if not ("가" <= ch <= "힣"):
        return "는"
    return "은" if (ord(ch) - 0xAC00) % 28 else "는"


def name_matches(pattern: str, text: str) -> bool:
    """메뉴 이름 대조 — ‘쭈꾸미’와 ‘쭈꾸미볶음’은 같은 메뉴로 본다.

    조건 검증·일시정지 판정이 같은 기준을 쓰도록 여기 한 곳에만 둔다.
    한 글자(예: ‘무’)는 부분 일치 오탐이 심해 완전 일치만 인정한다.
    """
    p, t = (pattern or "").strip(), (text or "").strip()
    if not p or not t:
        return False
    if len(p) < 2 or len(t) < 2:
        return p == t
    return p in t or t in p


def item_has(menu: str, item: str) -> bool:
    """조건의 메뉴가 그 칸에 들어 있는가(조건 검사용, 한 방향).

    ‘불고기’ 조건은 ‘고추장불고기’ 칸에 걸리지만, ‘배추된장국’ 조건이 ‘된장국’ 칸에
    걸리지는 않는다. 횟수를 세는 검사라 name_matches 보다 엄격하게 본다.
    """
    p, t = (menu or "").strip(), (item or "").strip()
    if not p or not t:
        return False
    return p == t if len(p) < 2 else p in t


def _hits(menu: str, meals) -> list:
    """그 메뉴가 메인·반찬·국 어느 자리든 들어간 끼니들."""
    return [m for m in meals if any(item_has(menu, it) for it in m.items)]


def _where(ms, limit: int = 4) -> str:
    """위반 위치를 ‘중식 7/1(수), 석식 7/3(금)’ 처럼 적는다(다시 만들 때 고칠 곳을 알려주려고)."""
    out = ", ".join(f"{m.section} {m.date_label}" for m in ms[:limit])
    return out + (f" 외 {len(ms) - limit}건" if len(ms) > limit else "")


def _real_wday(m, year: int | None, month: int | None) -> str:
    """그 날짜의 실제 요일. 연/월을 모르면 표기된 요일을 믿는다.

    모델이 ‘7/1(일)’ 처럼 요일을 틀리게 적으면 표기만 봐서는 요일 조건이 통과해 버린다.
    """
    if year and month:
        try:
            wd = datetime.date(year, month, _day(m.date_label)).weekday()   # 월=0
            return WEEKDAYS[(wd + 1) % 7]
        except ValueError:
            pass
    return _wday(m.date_label)


def default_conditions() -> list[dict]:
    """현재 비즈니스 규칙을 기본 조건으로 시드."""
    return [
        {"type": "category_max", "category": "생선류", "max": 4},
        {"type": "menu_count", "menu": "후라이드치킨", "op": "==", "count": 2},
        {"type": "menu_section", "menu": "후라이드치킨", "section": "중식"},
        {"type": "menu_section", "menu": "수육", "section": "중식"},
        {"type": "menu_count", "menu": "쭈꾸미", "op": "<=", "count": 2},
        {"type": "menu_gap", "menu": "쭈꾸미", "days": 7},
    ]


def to_text(c: dict) -> str:
    """조건을 사람이 읽는 한 줄로."""
    t = c.get("type")
    if t == "text":
        return (c.get("text") or "").strip()
    if t == "menu_count":
        return f"{c['menu']} 월 {c['count']}회 {OPS.get(c['op'], c['op'])}"
    if t == "menu_section":
        return f"{c['menu']}{_eun(c['menu'])} {c['section']}에만 편성"
    if t == "menu_weekday":
        wds = c.get("weekdays") or []
        return f"{c['menu']}{_eun(c['menu'])} {'·'.join(wds)}요일에만 편성"
    if t == "menu_gap":
        return f"{c['menu']} 최소 {c['days']}일 간격"
    if t == "category_max":
        return f"{c['category']} 월 최대 {c['max']}회"
    return str(c)


# ----------------------------------------------------------------------------
# 서술형 문장 → 구조화 조건
# ----------------------------------------------------------------------------
# 사용자가 "비빔밥은 일요일에만 넣어줘" 처럼 문장으로 적으면, 아는 형태는
# 구조화 조건으로 바꿔 준다. 구조화되면 코드 검증(validate)까지 걸리므로
# 규칙이 지켜졌는지 확인하고 자동 재생성까지 할 수 있다.
# 해석이 안 되면 빈 리스트를 돌려주고, 호출한 쪽이 문장 그대로 저장한다.

_MENU_RE = re.compile(r"^\s*[‘'\"“]?(?P<word>[가-힣A-Za-z0-9]{2,})")
_NUM_RE = re.compile(r"(?:월|한\s*달에|매달)\s*(\d+)\s*(?:회|번)|(\d+)\s*(?:회|번)")
_GAP_RE = re.compile(r"(\d+)\s*일\s*(?:이상\s*)?(?:간격|건너|띄|텀)")

_KO_NUM = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6}

# 떼어낼 조사. '이/가'는 일부러 뺐다 — 고등어구이·가자미구이·조기구이처럼
# 이름이 '이'로 끝나는 메뉴가 실제로 있어서, 떼면 '고등어구'가 돼 버린다.
_PARTICLES = ("은", "는", "을", "를")


def _split_menu(s: str) -> tuple[str, str]:
    """문장 앞머리의 메뉴 이름과 그 뒤 나머지를 분리한다.

    한글은 조사가 이름에 붙어 있어('비빔밥은') 정규식만으로는 잘리지 않는다.
    이름을 통째로 잡은 뒤 조사만 떼어낸다.
    """
    m = _MENU_RE.match(s)
    if not m:
        return "", ""
    word, rest = m.group("word"), s[m.end():]
    for p in _PARTICLES:
        if word.endswith(p) and len(word) - len(p) >= 2:
            return word[:-len(p)], word[-len(p):] + rest
    return word, rest


def _count_of(s: str) -> int | None:
    m = _NUM_RE.search(s)
    if m:
        return int(m.group(1) or m.group(2))
    for word, n in _KO_NUM.items():       # '한 달에 두 번' 같은 표기
        if re.search(rf"{word}\s*(?:회|번)", s):
            return n
    return None


def _weekdays_of(s: str) -> list[str]:
    found = {w for w in WEEKDAYS if re.search(rf"{w}요일", s)}
    if "주말" in s:
        found |= {"토", "일"}
    if "평일" in s:
        found |= {"월", "화", "수", "목", "금"}
    return [w for w in WEEKDAYS if w in found]


def parse_text(sentence: str) -> list[dict]:
    """서술형 문장에서 알아들은 조건들을 뽑는다(못 알아들으면 빈 리스트).

    한 문장이 여러 규칙을 담을 수 있어 리스트로 돌려준다.
    (예: '비빔밥은 일요일 중식에만' → 요일 제한 + 끼니 제한)
    """
    s = (sentence or "").strip()
    if not s:
        return []
    menu, body = _split_menu(s)   # 규칙은 메뉴 이름 뒤쪽에서만 찾는다
    if not menu:
        return []

    out: list[dict] = []

    # 생선류 등 카테고리 월 최대
    if menu in CATEGORIES:
        n = _count_of(body)
        if n is not None:
            return [{"type": "category_max", "category": menu, "max": n}]
        return []

    # 요일 제한
    wds = _weekdays_of(body)
    if wds:
        out.append({"type": "menu_weekday", "menu": menu, "weekdays": wds})

    # 끼니 제한
    lunch = re.search(r"중식|점심", body)
    dinner = re.search(r"석식|저녁", body)
    if lunch and not dinner:
        out.append({"type": "menu_section", "menu": menu, "section": "중식"})
    elif dinner and not lunch:
        out.append({"type": "menu_section", "menu": menu, "section": "석식"})

    # 최소 간격
    g = _GAP_RE.search(body)
    if g:
        out.append({"type": "menu_gap", "menu": menu, "days": int(g.group(1))})
    elif re.search(r"(일주일|1주일|한\s*주)\s*(?:이상\s*)?(?:간격|건너|띄|텀)", body):
        out.append({"type": "menu_gap", "menu": menu, "days": 7})

    # 월 횟수 — '간격'으로 이미 쓴 숫자와 헷갈리지 않게 간격 표현은 지우고 본다
    cnt_body = _GAP_RE.sub("", body)
    n = _count_of(cnt_body)
    if n is not None:
        if re.search(r"이상|최소", cnt_body):
            op = ">="
        elif re.search(r"정확히|딱", cnt_body):
            op = "=="
        else:
            # '이하/최대/넘지' 는 물론, 표현이 없을 때도 약한 쪽(이하)으로 둔다.
            # 잘못 잡아도 식단을 못 만들게 막지는 않는 방향이 안전하다.
            op = "<="
        out.append({"type": "menu_count", "menu": menu, "op": op, "count": n})

    return out


def conditions_prompt(conds: list[dict]) -> str:
    if not conds:
        return ""
    lines = "\n".join(f"{i}. {to_text(c)}" for i, c in enumerate(conds, start=1))
    return ("[반드시 지켜야 할 추가 조건 — 어기면 실패로 간주]\n"
            "아래 조건은 기본 규칙·참고 예시·과거 식단 기록과 어긋나더라도 항상 우선합니다.\n"
            "메뉴 이름은 메인·반찬·국 어느 자리에 쓰였든 똑같이 셉니다.\n"
            "출력하기 전에 조건을 하나씩 다시 대조해 보고, 어긋난 날이 있으면 고친 뒤 출력하세요.\n"
            + lines)


def validate(meals, conds: list[dict], year: int | None = None,
             month: int | None = None, culprits: list | None = None) -> list[str]:
    """조건 위반 목록(빈 리스트=통과). meals: MealLine 리스트.

    메뉴는 메인뿐 아니라 반찬·국 자리까지 전부 본다 — 조건은 ‘계란찜 월 3회 이하’처럼
    반찬·국에도 걸 수 있는데, 메인만 세면 그런 조건은 어겨도 늘 통과해 버린다.
    year/month 를 주면 요일 조건을 실제 달력으로 따진다.
    위반 메시지에는 어긴 날짜를 적는다(재생성 때 모델이 고칠 곳을 알 수 있게).

    culprits: 리스트를 주면 ‘바꿔야 할 칸’을 (끼니, 날짜표기, 칸의 메뉴) 로 채워 준다.
        모자라서 생긴 위반(‘월 2회 이상’인데 1회)은 ("", "", 메뉴이름) 으로 넣는다.
        menu_planner.repair_menu 가 이 목록을 보고 직접 메뉴를 바꾼다.
    """
    errors: list[str] = []

    def blame(ms, match):
        if culprits is None:
            return
        for m in ms:
            for it in m.items:
                if match(it):
                    culprits.append((m.section, m.date_label, it))
                    break

    for c in conds:
        t = c.get("type")
        if t == "menu_count":
            hit = _hits(c["menu"], meals)
            cnt, n, op = len(hit), c["count"], c["op"]
            ok = (op == "<=" and cnt <= n) or (op == "==" and cnt == n) or \
                 (op == ">=" and cnt >= n)
            if not ok:
                at = f": {_where(hit, 6)}" if hit else ""
                errors.append(f"{to_text(c)} (현재 {cnt}회{at})")
                if cnt > n:                      # 넘친 만큼(뒤쪽부터) 바꿀 칸으로
                    blame(hit[n:], lambda it, c=c: item_has(c["menu"], it))
                elif culprits is not None:       # 모자란 만큼은 ‘넣어야 할 메뉴’로
                    culprits.extend([("", "", c["menu"])] * (n - cnt))
        elif t == "menu_section":
            bad = [m for m in _hits(c["menu"], meals) if m.section != c["section"]]
            if bad:
                errors.append(f"{to_text(c)} (위반 {len(bad)}건: {_where(bad)})")
                blame(bad, lambda it, c=c: item_has(c["menu"], it))
        elif t == "menu_weekday":
            allow = set(c.get("weekdays") or [])
            if not allow:
                continue          # 요일을 하나도 안 고른 조건은 검사하지 않음
            bad = [m for m in meals
                   if any(name_matches(c["menu"], it) for it in m.items)
                   and _real_wday(m, year, month) not in allow]
            if bad:
                errors.append(f"{to_text(c)} (위반 {len(bad)}건: {_where(bad)})")
                blame(bad, lambda it, c=c: name_matches(c["menu"], it))
        elif t == "menu_gap":
            hit = sorted(_hits(c["menu"], meals), key=lambda m: _day(m.date_label))
            for a, b in zip(hit, hit[1:]):
                gap = _day(b.date_label) - _day(a.date_label)
                if gap < c["days"]:
                    errors.append(f"{to_text(c)} (간격 {gap}일: {_where([a, b])})")
                    blame([b], lambda it, c=c: item_has(c["menu"], it))
                    break
        elif t == "category_max":
            kws = CATEGORIES.get(c["category"], ())
            hit = [m for m in meals if any(k in it for it in m.items for k in kws)]
            if len(hit) > c["max"]:
                errors.append(f"{to_text(c)} (현재 {len(hit)}회: {_where(hit, 8)})")
                blame(hit[c["max"]:], lambda it, kws=kws: any(k in it for k in kws))
    return errors


def referenced_menus(conds: list[dict]) -> set[str]:
    return {c["menu"] for c in conds if "menu" in c}
