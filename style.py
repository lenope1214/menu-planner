# -*- coding: utf-8 -*-
"""
사용자 서식 설정(가벼운 옵션)
==============================
config.json 에 저장되는 표시 서식값. 미리보기(gui)와 엑셀(exporters)이 공유한다.
- title_size : 중식/석식 제목 글씨 크기(pt)
- menu_size  : 메뉴 글씨 크기(pt)
- show_border: 표 테두리 보임 여부
- theme      : 색 테마 키
"""

from __future__ import annotations

DEFAULT_STYLE = {
    "title_size": 32,
    "menu_size": 11,
    "show_border": True,
    "theme": "green",
}

# 제목/메뉴 크기 선택지(라벨 -> pt)
TITLE_SIZES = {"작게": 24, "보통": 32, "크게": 40}
MENU_SIZES = {"작게": 10, "보통": 11, "크게": 13}

# 색 테마(라벨/강조색/요일헤더/중식/석식)
THEMES = {
    "green": {"label": "초록", "accent": "#2E7D32", "header": "#D9E1F2",
              "lunch": "#E4DFEC", "dinner": "#FCE4D6"},
    "blue":  {"label": "파랑", "accent": "#1565C0", "header": "#D6E4F0",
              "lunch": "#DCE6F2", "dinner": "#FCE4D6"},
    "brown": {"label": "갈색", "accent": "#8D6E63", "header": "#EFE3D6",
              "lunch": "#EFE3D6", "dinner": "#F3E0D0"},
}


def normalize(style: dict | None) -> dict:
    """누락/이상값을 기본값으로 보정한 서식 dict 반환."""
    s = dict(DEFAULT_STYLE)
    if style:
        for k in DEFAULT_STYLE:
            if k in style:
                s[k] = style[k]
    if s["theme"] not in THEMES:
        s["theme"] = "green"
    return s


def theme_of(style: dict) -> dict:
    return THEMES.get(style.get("theme", "green"), THEMES["green"])


def label_for_size(table: dict, size: int) -> str:
    """pt -> 라벨(작게/보통/크게). 일치 없으면 '보통'."""
    for lbl, v in table.items():
        if v == size:
            return lbl
    return "보통"


def theme_key_for_label(label: str) -> str:
    for key, info in THEMES.items():
        if info["label"] == label:
            return key
    return "green"
