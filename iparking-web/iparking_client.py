"""iParking 제휴점(스토어) 포털 API 클라이언트.

store.iparking.co.kr 의 '지역 입주사 할인 관리'(parking-local-tenant-discount-management)
서비스가 브라우저에서 호출하는 것과 동일한 REST/JSON API를 서버에서 그대로 재현한다.

인증 흐름
---------
1. 주차장 코드 조회 : GET  /parking-lot/{parkingLotId}/detail      (인증 불필요)
2. 스토어 로그인    : POST /auth/login-v2                          (JWT 발급)
3. 인증 필요한 호출 : Authorization / Refresh-Token 헤더로 JWT 전달

비밀번호 인코딩
--------------
서버로 보내는 storePassword 는 평문이 아니라 다음과 같이 가공된 값이다.

    storePassword = base64( sha256_hex( 평문비밀번호 ) )

즉 서버는 SHA-256 해시만으로 로그인을 판정한다. 이 해시가 유출되면 평문을
몰라도 로그인이 가능하므로 취급에 주의한다.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field

import requests

BASE_URL = (
    "https://store.iparking.co.kr"
    "/parking-local-tenant-discount-managements/api/v1"
)

# 브라우저와 최대한 유사한 기본 헤더 (일부 WAF 가 UA/Accept 를 검사할 수 있어 맞춰둔다)
_DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://store.iparking.co.kr",
    "Referer": "https://store.iparking.co.kr/home",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
}


class IParkingError(Exception):
    """API 호출 실패. message 는 사용자에게 그대로 보여줘도 되는 한국어."""

    def __init__(self, message: str, *, status: int | None = None, payload=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.payload = payload


def encode_password(plain: str) -> str:
    """평문 비밀번호 -> base64(sha256_hex(평문))."""
    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return base64.b64encode(digest.encode("ascii")).decode("ascii")


def _looks_like_jwt(value) -> bool:
    return isinstance(value, str) and value.count(".") == 2 and value.startswith("eyJ")


def _find_token(obj, keys: tuple[str, ...]):
    """응답 본문(dict/list)을 재귀 탐색해 원하는 키의 JWT 문자열을 찾는다."""
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and _looks_like_jwt(obj[key]):
                return obj[key]
        for value in obj.values():
            found = _find_token(value, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_token(item, keys)
            if found:
                return found
    return None


def _strip_bearer(token: str | None) -> str | None:
    if token and token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


@dataclass
class Session:
    """로그인으로 얻은 토큰 + 스토어 컨텍스트."""

    parking_lot_id: str
    store_account_id: str
    access_token: str
    refresh_token: str | None = None
    account_name: str = ""
    raw_login: dict = field(default_factory=dict)

    @property
    def auth_headers(self) -> dict:
        headers = {"Authorization": self.access_token}
        if self.refresh_token:
            headers["Refresh-Token"] = self.refresh_token
        return headers


class IParkingClient:
    def __init__(self, timeout: float = 15.0):
        self._http = requests.Session()
        self._http.headers.update(_DEFAULT_HEADERS)
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # 내부 공통                                                            #
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, *, headers=None, json=None):
        url = f"{BASE_URL}{path}"
        try:
            resp = self._http.request(
                method, url, headers=headers, json=json, timeout=self.timeout
            )
        except requests.RequestException as exc:  # 네트워크/타임아웃
            raise IParkingError(f"네트워크 오류: {exc}") from exc

        if resp.status_code >= 400:
            raise IParkingError(
                _error_message(resp),
                status=resp.status_code,
                payload=_safe_json(resp),
            )
        return resp

    # ------------------------------------------------------------------ #
    # 1) 주차장 코드 조회 (로그인 전)                                        #
    # ------------------------------------------------------------------ #
    def get_parking_lot(self, parking_lot_id: str) -> dict:
        resp = self._request(
            "GET", f"/parking-lot/{parking_lot_id}/detail"
        )
        return _safe_json(resp) or {}

    # ------------------------------------------------------------------ #
    # 2) 스토어 로그인                                                      #
    # ------------------------------------------------------------------ #
    def login(
        self, parking_lot_id: str, store_account_id: str, password_plain: str
    ) -> Session:
        body = {
            "parkingLotId": parking_lot_id,
            "storeAccountId": store_account_id,
            "storePassword": encode_password(password_plain),
        }
        resp = self._request(
            "POST",
            "/auth/login-v2",
            headers={"Content-Type": "application/json"},
            json=body,
        )
        data = _safe_json(resp) or {}

        # 토큰은 응답 헤더 또는 본문 어디에 실릴지 서버 구현에 따라 달라 양쪽 모두 확인한다.
        access = _strip_bearer(
            resp.headers.get("Authorization")
            or _find_token(data, ("accessToken", "access_token", "token", "jwt"))
        )
        refresh = _strip_bearer(
            resp.headers.get("Refresh-Token")
            or _find_token(data, ("refreshToken", "refresh_token"))
        )
        if not access:
            raise IParkingError(
                "로그인은 응답했지만 인증 토큰을 찾지 못했습니다. "
                "아이디/비밀번호 또는 응답 형식을 확인해 주세요.",
                status=resp.status_code,
                payload=data,
            )

        account_name = ""
        if isinstance(data, dict):
            account_name = (
                data.get("accountName")
                or (data.get("data") or {}).get("accountName", "")
                if isinstance(data.get("data"), dict)
                else data.get("accountName", "")
            ) or ""

        return Session(
            parking_lot_id=parking_lot_id,
            store_account_id=store_account_id,
            access_token=access,
            refresh_token=refresh,
            account_name=account_name,
            raw_login=data if isinstance(data, dict) else {},
        )

    # ------------------------------------------------------------------ #
    # 3) 로그인 후 조회                                                     #
    # ------------------------------------------------------------------ #
    def get_store_version(self, session: Session) -> dict:
        resp = self._request(
            "GET", "/commons/versions/store", headers=session.auth_headers
        )
        return _safe_json(resp) or {}

    def get_discount_tickets(self, session: Session) -> dict:
        resp = self._request(
            "GET",
            f"/stores/{session.parking_lot_id}/discount-tickets/search",
            headers=session.auth_headers,
        )
        return _safe_json(resp) or {}


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def _error_message(resp) -> str:
    data = _safe_json(resp)
    if isinstance(data, dict):
        for key in ("message", "errorMessage", "detail", "error"):
            if data.get(key):
                return f"{data[key]} (HTTP {resp.status_code})"
    if resp.status_code == 401:
        return "인증 실패 또는 세션 만료 (HTTP 401)"
    if resp.status_code == 404:
        return "요청한 자원을 찾을 수 없습니다 (HTTP 404)"
    return f"요청 실패 (HTTP {resp.status_code})"
