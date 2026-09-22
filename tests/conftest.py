# -*- coding: utf-8 -*-
"""
테스트 공통 준비
=================
⚠ 가장 중요한 장치: **설정 폴더를 임시 폴더로 갈아끼운다.**
`app_config.config_dir()` 는 프로그램 폴더를 가리키므로, 그대로 두면 테스트가
실제 `menu_pool.json` / `settings.json` / `history.json` 을 덮어써 버린다.
store 와 history 는 파일을 열 때마다 `config_dir()` 를 부르므로 함수만 바꿔치기하면 된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 저장소 루트를 import 경로에 넣는다(설치 없이 바로 테스트할 수 있게)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app_config  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """모든 테스트를 임시 설정 폴더에서 돌린다(실제 사용자 데이터 보호)."""
    monkeypatch.setattr(app_config, "config_dir", lambda: tmp_path)
    return tmp_path
