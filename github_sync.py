# -*- coding: utf-8 -*-
"""
GitHub 프라이빗 레포를 '무료 DB'처럼 사용하기 위한 최소 클라이언트.
====================================================================
- 표준 라이브러리(urllib)만 사용 — 추가 설치 불필요.
- GitHub Contents API 로 레포 내 JSON 파일을 읽고(get_json) 쓴다(put_json).
- 로컬 앱과 웹버전이 같은 파일을 읽어 데이터를 공유한다.
- 인증: 개인 액세스 토큰(PAT). 토큰은 호출자가 보관(로컬 config.json, 커밋 금지).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

API = "https://api.github.com"


class GitHubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "menu-planner",
    }
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("message", "")
        except Exception:
            pass
        raise GitHubError(f"{e.code} {e.reason}: {detail}", status=e.code)
    except urllib.error.URLError as e:
        raise GitHubError(f"네트워크 오류: {e.reason}")


def _contents_url(owner: str, repo: str, path: str, branch: str | None = None) -> str:
    url = f"{API}/repos/{owner}/{repo}/contents/{path}"
    if branch:
        url += f"?ref={branch}"
    return url


def check_access(owner: str, repo: str, token: str) -> tuple[bool, str]:
    """레포 접근 가능 여부 확인. (성공여부, 메시지)."""
    try:
        res = _request("GET", f"{API}/repos/{owner}/{repo}", token)
        vis = "private" if res.get("private") else "public"
        perms = res.get("permissions", {})
        can_push = perms.get("push", False)
        return True, f"연결 성공: {res.get('full_name')} ({vis}, 쓰기={'가능' if can_push else '불가'})"
    except GitHubError as e:
        if e.status == 404:
            return False, "레포를 찾을 수 없거나 접근 권한이 없습니다(소유자/이름/토큰 권한 확인)."
        if e.status == 401:
            return False, "토큰 인증 실패(토큰이 잘못되었거나 만료)."
        return False, str(e)


def get_json(owner: str, repo: str, path: str, token: str,
             branch: str | None = None) -> tuple[dict | list | None, str | None]:
    """파일을 읽어 (데이터, sha) 반환. 파일이 없으면 (None, None)."""
    try:
        res = _request("GET", _contents_url(owner, repo, path, branch), token)
    except GitHubError as e:
        if e.status == 404:
            return None, None
        raise
    content = base64.b64decode(res["content"]).decode("utf-8")
    return json.loads(content), res.get("sha")


def put_json(owner: str, repo: str, path: str, token: str, data,
             sha: str | None = None, branch: str | None = None,
             message: str | None = None) -> str:
    """파일 쓰기(없으면 생성). 충돌 방지를 위해 기존 sha 필요. 새 sha 반환."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    payload = {
        "message": message or f"Update {path}",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha
    if branch:
        payload["branch"] = branch
    res = _request("PUT", f"{API}/repos/{owner}/{repo}/contents/{path}", token, payload)
    return res["content"]["sha"]
