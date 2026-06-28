# -*- coding: utf-8 -*-
"""
메뉴 풀 / 조건 / 설정 영속화
=============================
menu-planner 폴더의 JSON 파일에 저장(= app_config.config_dir()).
- menu_pool.json : {"mains":[{...}], "sides":[...], "soups":[...]}
- conditions.json: [조건 dict, ...]
- pool_only 설정은 config.json 에 저장.
첫 실행 시 menu_data.py 의 시드로 채운다.
"""

from __future__ import annotations

import json

import app_config
import conditions as cond_mod
import menu_data

POOL_FILE = "menu_pool.json"
COND_FILE = "conditions.json"

# 메인 메뉴 1개의 필드/기본값
MAIN_FIELDS: dict = {
    "name": "", "flavor": "자극", "difficulty": 2, "meal_scope": "both",
    "is_fish": False, "team": "A", "monthly_max": None, "monthly_min": 1,
    "min_gap_days": 4, "weekday_only": False,
}


def _path(name):
    return app_config.config_dir() / name


def _load(name, default):
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save(name, data):
    d = app_config.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm_main(d: dict) -> dict:
    m = dict(MAIN_FIELDS)
    for k in MAIN_FIELDS:
        if k in d:
            m[k] = d[k]
    return m


# ---- 메뉴 풀 ----

def default_pool() -> dict:
    return {
        "mains": [{f: getattr(m, f) for f in MAIN_FIELDS} for m in menu_data.MAIN_DISHES],
        "sides": list(menu_data.SIDE_DISHES),
        "soups": list(menu_data.SOUPS),
    }


def get_pool() -> dict:
    p = _load(POOL_FILE, None)
    if not p:
        return default_pool()
    p.setdefault("mains", [])
    p.setdefault("sides", [])
    p.setdefault("soups", [])
    p["mains"] = [_norm_main(m) for m in p["mains"]]
    return p


def save_pool(pool: dict) -> None:
    _save(POOL_FILE, pool)


def pool_to_menupool(pool: dict):
    """저장 dict -> menu_data.MenuPool (생성기용)."""
    from menu_data import MainDish, MenuPool
    mains = [MainDish(**_norm_main(m)) for m in pool["mains"]]
    return MenuPool(mains=mains, sides=list(pool["sides"]), soups=list(pool["soups"]))


# ---- 조건 ----

def get_conditions() -> list[dict]:
    c = _load(COND_FILE, None)
    return c if c is not None else cond_mod.default_conditions()


def save_conditions(conds: list[dict]) -> None:
    _save(COND_FILE, conds)


# ---- 설정: 추가된 메뉴만 사용(pool_only) ----

def get_pool_only() -> bool:
    return bool(app_config.get_setting("pool_only", False))


def set_pool_only(v: bool) -> None:
    app_config.set_setting("pool_only", bool(v))


# ---- 충돌 점검(생성 전) ----

def check_conflicts(pool: dict, conds: list[dict], pool_only: bool) -> list[str]:
    """'추가된 메뉴만 사용'이 켜졌을 때 조건이 실현 불가하면 오류 목록 반환."""
    errors: list[str] = []
    if not pool_only:
        return errors
    main_names = [m["name"] for m in pool["mains"]]
    if not main_names:
        errors.append("메뉴 풀에 메인 요리가 없습니다. ‘메뉴 설정’에서 먼저 등록하세요.")
    for c in conds:
        mn = c.get("menu")
        if mn and not any(mn in n or n in mn for n in main_names):
            errors.append(f"조건 ‘{cond_mod.to_text(c)}’의 메뉴가 풀에 없습니다 "
                          f"(‘추가된 메뉴만 사용’ 켜짐).")
    # 월 최소 합계가 운영일보다 많은지 등은 생략(생성 후 검증으로 처리)
    return errors
