# -*- coding: utf-8 -*-
"""
앱 설정 저장/로드 (API 키 등)
==============================
- API 키는 '프로그램(코드/실행파일)이 있는 폴더'의 config.json 에 저장한다.
  · 개발 실행(파이썬): menu-planner/config.json  (이 파일 옆)
  · 배포(.exe): MenuPlanner.exe 와 같은 폴더의 config.json
- ⚠ 평문 JSON 저장이다. config.json 은 .gitignore 로 커밋을 막아 둔다.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "MenuPlanner"


def config_dir() -> Path:
    """설정 폴더 = 프로그램(코드/실행파일)이 위치한 폴더.

    - 개발 실행(파이썬): 이 파일이 있는 menu-planner 폴더
    - 배포(.exe): MenuPlanner.exe 와 같은 폴더
    """
    if getattr(sys, "frozen", False):  # PyInstaller 로 빌드된 .exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return config_dir() / "config.json"


def _backup_path() -> Path:
    return config_dir() / "config.json.bak"


def load_config() -> dict:
    """설정을 읽어 dict 로 반환. 본파일이 손상되면 백업본에서 복구(없으면 빈 dict)."""
    p = config_path()
    for cand in (p, _backup_path()):
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            continue  # 손상 → 다음 후보(백업본)로
    return {}


def save_config(cfg: dict) -> None:
    """설정을 원자적으로 저장한다(쓰는 도중 깨져도 기존 파일 보존 + 백업본 유지).

    - 임시 파일에 먼저 쓰고 os.replace 로 교체(원자적).
    - 교체 전 직전 정상본을 config.json.bak 으로 복사(복구용).
    """
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = config_path()
    tmp = d / "config.json.tmp"
    data = json.dumps(cfg, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # 직전 정상본 백업(있으면)
    if p.exists():
        try:
            shutil.copy2(p, _backup_path())
        except OSError:
            pass
    os.replace(tmp, p)  # 원자적 교체
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def get_api_key() -> str:
    """저장된 API 키(없으면 환경변수, 그래도 없으면 빈 문자열)."""
    return (
        load_config().get("api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


def set_api_key(api_key: str) -> None:
    cfg = load_config()
    cfg["api_key"] = api_key.strip()
    save_config(cfg)


def get_setting(key: str, default=None):
    return load_config().get(key, default)


def set_setting(key: str, value) -> None:
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
