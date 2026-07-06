"""iParking 스토어 자동화 웹앱 (백엔드).

브라우저 → (이 Flask 서버) → store.iparking.co.kr 로 요청을 중계한다.
브라우저에서 iParking API 를 직접 부르면 CORS 에 막히기 때문에 서버가 대신 호출한다.

단일 사용자(본인 스토어)가 로컬에서 쓰는 도구이므로 로그인 세션은 서버 메모리에
하나만 보관한다. 여러 사람이 동시에 쓰는 용도가 아니다.

실행:
    pip install -r requirements.txt
    python app.py
    → 브라우저에서 http://127.0.0.1:5000 자동 오픈
"""

from __future__ import annotations

import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

from iparking_client import IParkingClient, IParkingError, Session

app = Flask(__name__)
client = IParkingClient()

# 단일 사용자 로컬 도구: 현재 로그인 세션 하나만 메모리에 유지한다.
_state: dict[str, Session | None] = {"session": None}


def _current() -> Session | None:
    return _state["session"]


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/check-lot")
def check_lot():
    """1단계: 주차장 코드가 유효한지 조회."""
    lot_id = (request.json or {}).get("parkingLotId", "").strip()
    if not lot_id:
        return jsonify(ok=False, error="주차장 코드를 입력해 주세요."), 400
    try:
        detail = client.get_parking_lot(lot_id)
    except IParkingError as exc:
        return jsonify(ok=False, error=exc.message), (exc.status or 502)
    return jsonify(ok=True, parkingLotId=lot_id, detail=detail)


@app.post("/api/login")
def login():
    """2단계: 스토어 아이디/비밀번호로 로그인."""
    data = request.json or {}
    lot_id = data.get("parkingLotId", "").strip()
    account_id = data.get("storeAccountId", "").strip()
    password = data.get("password", "")
    if not (lot_id and account_id and password):
        return jsonify(ok=False, error="주차장 코드·아이디·비밀번호를 모두 입력해 주세요."), 400
    try:
        session = client.login(lot_id, account_id, password)
    except IParkingError as exc:
        return jsonify(ok=False, error=exc.message), (exc.status or 502)
    _state["session"] = session

    store_info = {}
    try:
        store_info = client.get_store_version(session)
    except IParkingError:
        pass  # 부가 정보라 실패해도 로그인 자체는 성공으로 처리
    return jsonify(
        ok=True,
        accountName=session.account_name,
        storeAccountId=session.store_account_id,
        parkingLotId=session.parking_lot_id,
        storeInfo=store_info,
    )


@app.get("/api/tickets")
def tickets():
    """3단계: 로그인한 스토어가 보유한 할인권(티켓) 목록 조회."""
    session = _current()
    if session is None:
        return jsonify(ok=False, error="로그인이 필요합니다."), 401
    try:
        result = client.get_discount_tickets(session)
    except IParkingError as exc:
        status = exc.status or 502
        if status == 401:
            _state["session"] = None
        return jsonify(ok=False, error=exc.message), status
    return jsonify(ok=True, tickets=result)


@app.post("/api/logout")
def logout():
    _state["session"] = None
    return jsonify(ok=True)


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    # 개발/로컬 전용 서버. 브라우저를 살짝 늦게 띄운다.
    threading.Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
