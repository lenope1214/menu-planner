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
import github_sync
import history
import menu_data

POOL_FILE = "menu_pool.json"
COND_FILE = "conditions.json"
EXAMPLES_FILE = "examples.json"
SETTINGS_FILE = "settings.json"
HISTORY_FILE = history.HISTORY_FILE      # 과거 식단 기록(history.py 가 읽고 쓴다)

# 풀의 세 갈래(메뉴 설정 창의 탭과 1:1)
POOL_KEYS = ("mains", "sides", "soups")
POOL_KEY_KR = {"mains": "메인 요리", "sides": "반찬", "soups": "국"}

# 로컬↔레포 동기화 대상(공유 데이터). config.json(키/토큰)은 동기화 제외.
# examples.json 은 참고용 로컬 데이터라 동기화에서 제외.
DATA_FILES = [POOL_FILE, COND_FILE, SETTINGS_FILE, HISTORY_FILE]

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


def pool_to_menupool(pool: dict, exclude_paused: bool = True):
    """저장 dict -> menu_data.MenuPool (생성기용). 기본으로 일시정지 메뉴는 뺀다."""
    from menu_data import MainDish, MenuPool
    if exclude_paused:
        pool = active_pool(pool)
    mains = [MainDish(**_norm_main(m)) for m in pool["mains"]]
    return MenuPool(mains=mains, sides=list(pool["sides"]), soups=list(pool["soups"]))


# ---- 메뉴 일시정지(당분간 못 내는 메뉴) ----
# settings.json 에 저장한다:
#   "paused": {"mains": {이름: {"note": 사유}}, "sides": {...}, "soups": {...}}
# menu_pool.json(마스터 목록)은 건드리지 않는다 — 일시정지는 '지웠다 다시 넣는' 게
# 아니라 잠시 빼두는 운영 상태라서, 메뉴의 속성/조건을 그대로 보존해야 한다.
# settings.json 은 DATA_FILES 라서 GitHub 동기화로 다른 PC에도 함께 반영된다.

def _norm_paused(raw) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {k: {} for k in POOL_KEYS}
    if not isinstance(raw, dict):
        return out
    for k in POOL_KEYS:
        v = raw.get(k)
        if isinstance(v, list):           # ["쭈꾸미", ...] 형태도 받아준다
            out[k] = {str(n).strip(): {} for n in v if str(n).strip()}
        elif isinstance(v, dict):
            out[k] = {str(n).strip(): (m if isinstance(m, dict) else {})
                      for n, m in v.items() if str(n).strip()}
    return out


def get_paused() -> dict[str, dict[str, dict]]:
    return _norm_paused(get_settings().get("paused"))


def save_paused(paused: dict) -> None:
    s = get_settings()
    s["paused"] = _norm_paused(paused)
    save_settings(s)


def is_paused(key: str, name: str) -> bool:
    return name in get_paused().get(key, {})


def paused_note(key: str, name: str) -> str:
    return (get_paused().get(key, {}).get(name) or {}).get("note", "")


def set_paused(key: str, name: str, paused: bool, note: str = "") -> None:
    p = get_paused()
    if paused:
        note = (note or "").strip()
        p.setdefault(key, {})[name] = {"note": note} if note else {}
    else:
        p.get(key, {}).pop(name, None)
    save_paused(p)


def rename_paused(key: str, old: str, new: str) -> None:
    """메뉴 이름을 고치면 일시정지 표시도 따라가게 한다(고아 항목 방지)."""
    if old == new:
        return
    p = get_paused()
    meta = p.get(key, {}).pop(old, None)
    if meta is None:
        return
    if new:
        p.setdefault(key, {})[new] = meta
    save_paused(p)


def clear_paused(key: str, name: str) -> None:
    """메뉴를 삭제할 때 일시정지 표시도 함께 지운다."""
    p = get_paused()
    if p.get(key, {}).pop(name, None) is not None:
        save_paused(p)


def paused_names(key: str | None = None) -> list[str]:
    """일시정지 메뉴 이름 목록(생성기 금지어로 넘길 용도)."""
    p = get_paused()
    keys = [key] if key else list(POOL_KEYS)
    out: list[str] = []
    for k in keys:
        out.extend(p.get(k, {}).keys())
    return out


def paused_summary() -> list[str]:
    """'쭈꾸미(8월말까지)' 형태의 화면 표시용 목록."""
    p = get_paused()
    out: list[str] = []
    for k in POOL_KEYS:
        for name, meta in p.get(k, {}).items():
            note = (meta or {}).get("note", "").strip()
            out.append(f"{name}({note})" if note else name)
    return out


def active_pool(pool: dict | None = None) -> dict:
    """일시정지 메뉴를 뺀 풀. 생성기에는 항상 이걸 넘긴다."""
    pool = pool if pool is not None else get_pool()
    p = get_paused()
    return {
        "mains": [m for m in pool.get("mains", []) if m.get("name") not in p["mains"]],
        "sides": [s for s in pool.get("sides", []) if s not in p["sides"]],
        "soups": [s for s in pool.get("soups", []) if s not in p["soups"]],
    }


# ---- 조건 ----

def get_conditions() -> list[dict]:
    c = _load(COND_FILE, None)
    return c if c is not None else cond_mod.default_conditions()


def save_conditions(conds: list[dict]) -> None:
    _save(COND_FILE, conds)


# ---- 예시 식단표(참고 데이터 / few-shot) ----

def get_examples() -> list[dict]:
    """등록된 예시 식단표 목록. 각 항목 {"title": str, "body": str}."""
    e = _load(EXAMPLES_FILE, None)
    if not e:
        return []
    out = []
    for item in e:
        if isinstance(item, dict) and item.get("body"):
            out.append({"title": item.get("title", "예시"), "body": item["body"]})
    return out


def save_examples(examples: list[dict]) -> None:
    _save(EXAMPLES_FILE, examples)


# ---- 공유 설정(settings.json): 추가된 메뉴만 사용(pool_only) 등, 다른 PC와 함께 쓰는 값 ----

def get_settings() -> dict:
    s = _load(SETTINGS_FILE, {})
    return s if isinstance(s, dict) else {}


def save_settings(s: dict) -> None:
    _save(SETTINGS_FILE, s)


def get_pool_only() -> bool:
    return bool(get_settings().get("pool_only", False))


def set_pool_only(v: bool) -> None:
    s = get_settings()
    s["pool_only"] = bool(v)
    save_settings(s)


# ---- 과거 식단 기록 활용 방식 ----
# 기본은 '참고해서 만들기'. 기록이 하나도 없으면 프롬프트 블록이 비므로 그냥 무시된다.

def get_history_mode() -> str:
    v = get_settings().get("history_mode", history.MODE_REF)
    return v if v in history.MODES else history.MODE_REF


def set_history_mode(v: str) -> None:
    s = get_settings()
    s["history_mode"] = v if v in history.MODES else history.MODE_REF
    save_settings(s)


def add_missing_from_history() -> dict[str, int]:
    """과거 기록에 나왔지만 메뉴 풀에 없는 메뉴를 풀에 추가한다(갈래별 추가 개수).

    ‘과거에 냈던 메뉴만으로 만들기’로 넘어가는 다리 역할. 기록에서 이름만 알 수
    있으므로 속성은 기본값으로 넣고(생선류만 이름으로 자동 판정), 나머지는
    메뉴 설정에서 고치게 둔다.
    """
    pool = get_pool()
    names = history.slot_names()
    have = {"mains": {m.get("name", "") for m in pool["mains"]},
            "sides": set(pool["sides"]), "soups": set(pool["soups"])}
    added = {k: 0 for k in POOL_KEYS}
    for k in POOL_KEYS:
        for n in names.get(k, []):
            if not n or n in have[k]:
                continue
            if k == "mains":
                d = _norm_main({"name": n})
                if any(kw in n for kw in cond_mod.FISH_KEYWORDS):
                    d["is_fish"] = True
                pool[k].append(d)
            else:
                pool[k].append(n)
            have[k].add(n)
            added[k] += 1
    if any(added.values()):
        save_pool(pool)
    return added


# ---- GitHub 동기화(프라이빗 레포를 공용 DB로) ----

def get_gh_config() -> dict:
    """GitHub 동기화 설정(token/owner/repo/branch). config.json 에 로컬 저장."""
    c = app_config.get_setting("github", {})
    return c if isinstance(c, dict) else {}


def set_gh_config(cfg: dict) -> None:
    app_config.set_setting("github", cfg)


def gh_ready() -> bool:
    c = get_gh_config()
    return bool(c.get("token") and c.get("owner") and c.get("repo"))


def _repo_path(fname: str) -> str:
    return f"data/{fname}"


def _default_for(fname: str):
    if fname == POOL_FILE:
        return default_pool()
    if fname == COND_FILE:
        return cond_mod.default_conditions()
    if fname == HISTORY_FILE:
        return {}
    return get_settings()


def sync_pull(progress=None) -> list[str]:
    """레포 → 로컬. 내려받아 갱신한 파일명 목록 반환."""
    c = get_gh_config()
    owner, repo, token = c["owner"], c["repo"], c["token"]
    branch = c.get("branch") or None
    changed = []
    for fname in DATA_FILES:
        if progress:
            progress(f"내려받는 중… {fname}")
        data, _sha = github_sync.get_json(owner, repo, _repo_path(fname), token, branch)
        if data is not None:
            _save(fname, data)
            changed.append(fname)
    return changed


def sync_push(progress=None) -> list[str]:
    """로컬 → 레포. 올린 파일명 목록 반환(없으면 기본값으로 생성)."""
    c = get_gh_config()
    owner, repo, token = c["owner"], c["repo"], c["token"]
    branch = c.get("branch") or None
    pushed = []
    for fname in DATA_FILES:
        local = _load(fname, None)
        if local is None:
            local = _default_for(fname)
        if progress:
            progress(f"올리는 중… {fname}")
        _data, sha = github_sync.get_json(owner, repo, _repo_path(fname), token, branch)
        github_sync.put_json(owner, repo, _repo_path(fname), token, local,
                             sha=sha, branch=branch,
                             message=f"Update {fname} (menu-planner)")
        pushed.append(fname)
    return pushed


def get_use_examples() -> bool:
    return bool(app_config.get_setting("use_examples", True))


def set_use_examples(v: bool) -> None:
    app_config.set_setting("use_examples", bool(v))


def get_model() -> str:
    return app_config.get_setting("model", "gemini-2.5-flash") or "gemini-2.5-flash"


def set_model(v: str) -> None:
    app_config.set_setting("model", (v or "").strip() or "gemini-2.5-flash")


# ---- 충돌 점검(생성 전) ----

def _requires_appearance(c: dict) -> bool:
    """그 메뉴가 '반드시 나와야' 하는 조건인가(일시정지와 정면충돌하는 종류)."""
    if c.get("type") != "menu_count":
        return False  # 끼니 제한·간격 조건은 '나온다면' 규칙이라 충돌 아님
    return c.get("op") == ">=" or (c.get("op") == "==" and int(c.get("count", 0)) > 0)


def check_conflicts(pool: dict, conds: list[dict], pool_only: bool) -> list[str]:
    """생성 전 실현 불가 상황을 잡아낸다(일시정지 + ‘추가된 메뉴만 사용’)."""
    errors: list[str] = []
    paused = get_paused()
    live = active_pool(pool)

    # (1) 일시정지 때문에 쓸 메뉴가 한 갈래라도 바닥난 경우
    for k in POOL_KEYS:
        if paused[k] and not live[k]:
            errors.append(f"{POOL_KEY_KR[k]}가 모두 일시정지 상태입니다. "
                          f"‘메뉴 설정’에서 일부를 다시 사용으로 바꿔 주세요.")

    # (2) 반드시 나와야 하는 조건인데 그 메뉴가 일시정지인 경우
    all_paused = [n for k in POOL_KEYS for n in paused[k]]
    for c in conds:
        mn = c.get("menu")
        if not mn or not _requires_appearance(c):
            continue
        hit = next((n for n in all_paused if cond_mod.name_matches(mn, n)), None)
        if hit:
            errors.append(f"조건 ‘{cond_mod.to_text(c)}’ 는 ‘{hit}’ 이(가) 일시정지라 "
                          f"지킬 수 없습니다. 조건을 지우거나 메뉴를 다시 사용으로 바꿔 주세요.")

    if not pool_only:
        return errors

    # (3) ‘추가된 메뉴만 사용’ — 일시정지를 뺀 실제 사용 가능 목록 기준으로 본다
    main_names = [m["name"] for m in live["mains"]]
    if not main_names:
        errors.append("메뉴 풀에 쓸 수 있는 메인 요리가 없습니다. ‘메뉴 설정’에서 먼저 등록하세요.")
    for c in conds:
        mn = c.get("menu")
        if mn and not any(cond_mod.name_matches(mn, n) for n in main_names) \
                and not any(cond_mod.name_matches(mn, n) for n in all_paused):
            errors.append(f"조건 ‘{cond_mod.to_text(c)}’의 메뉴가 풀에 없습니다 "
                          f"(‘추가된 메뉴만 사용’ 켜짐).")
    # 월 최소 합계가 운영일보다 많은지 등은 생략(생성 후 검증으로 처리)
    return errors
