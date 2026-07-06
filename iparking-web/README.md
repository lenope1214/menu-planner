# 아이파킹 스토어 자동화 웹앱

아이파킹 제휴점(스토어) 포털(`store.iparking.co.kr`)이 브라우저에서 호출하는 것과
동일한 REST/JSON API를, 로컬 웹앱으로 재현한 도구입니다.

**현재 구현 범위 (3단계)**

1. **주차장 코드 확인** — 주차장 코드(예: `KOR00056422`)가 유효한지 조회
2. **스토어 로그인** — 스토어 아이디 + 비밀번호로 로그인해 JWT 발급
3. **보유 할인권 조회** — 로그인한 스토어가 가진 할인권(티켓) 목록 표시

> 손님 차량정보를 입력해 실제로 할인/등록을 처리하는 기능은 **다음 단계**입니다.
> 그 요청(차량 등록 API)의 cURL을 확보하면 이 앱에 이어서 붙입니다.

## 구조

```
브라우저(화면)  ──►  Flask 서버(app.py)  ──►  store.iparking.co.kr API
```

브라우저에서 iParking API를 직접 부르면 **CORS**에 막히므로, 파이썬 서버가
대신 호출(서버-투-서버)합니다. 로그인 토큰도 서버에만 보관해 화면에 노출되지 않습니다.

| 파일 | 역할 |
|------|------|
| `iparking_client.py` | iParking API 클라이언트 (로그인·토큰·조회, 비밀번호 인코딩) |
| `app.py` | Flask 백엔드 — 화면 제공 + API 중계 |
| `templates/index.html` | 3단계 위저드 화면 |
| `static/app.js` | 프런트엔드 로직 |
| `실행.bat` | Windows 실행 (최초 실행 시 자동으로 라이브러리 설치) |

## 실행 (Windows)

`실행.bat` 더블클릭. 최초 실행은 라이브러리 설치로 조금 걸리고, 이후에는 바로
서버가 뜨며 브라우저(`http://127.0.0.1:5000`)가 자동으로 열립니다.

### 수동 실행 (개발자용)

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 인증 방식 메모

- 로그인: `POST /auth/login-v2`, 본문
  `{"parkingLotId","storeAccountId","storePassword"}`
- `storePassword = base64( sha256_hex( 평문비밀번호 ) )` — 앱이 평문을 받아 자동 변환
- 발급된 JWT는 이후 요청에 `Authorization`(액세스) / `Refresh-Token`(리프레시) 헤더로 전달

## 보안 주의

- 서버로 전송되는 비밀번호 값은 결국 **SHA-256 해시**입니다. 이 해시가 유출되면
  평문을 몰라도 로그인이 가능하니, 로그·화면 캡처 등에 노출되지 않도록 주의하세요.
- 이 앱은 **본인 스토어 계정으로 본인 업무를 자동화**하는 로컬 단일 사용자 도구를
  전제로 합니다. `127.0.0.1`(내 PC)에서만 접속되며 외부에 노출하지 마세요.
- iParking의 비공식(내부) API를 사용하므로, 사이트 개편 시 동작이 바뀔 수 있고
  서비스 약관을 확인할 필요가 있습니다. 가능하면 정식 제휴/API도 함께 문의하세요.
