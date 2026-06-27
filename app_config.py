# -*- coding: utf-8 -*-
"""
앱 설정 저장/로드 (API 키 등)
==============================
- API 키는 사용자 PC의 설정 폴더에 1회 저장하고 이후 자동 로드한다.
- Windows: %APPDATA%\\MenuPlanner\\config.json
- 그 외(개발/테스트): ~/.config/MenuPlanner/config.json
- ⚠ 평문 JSON 저장이다. 다중 사용자 PC에서는 OS 계정 권한으로 보호한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "MenuPlanner"


def config_dir() -> Path:
    """OS별 설정 폴더 경로."""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    """설정을 읽어 dict 로 반환(없으면 빈 dict)."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    """설정을 저장한다."""
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    # 가능하면 소유자만 읽도록 권한 제한(POSIX)
    try:
        os.chmod(config_path(), 0o600)
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
