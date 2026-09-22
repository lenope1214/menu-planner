# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 안내서입니다.

## 프로젝트 개요

한식 뷔페 **식단표 자동 생성기**. 연/월을 입력하면 매일 [중식]/[석식] 식단표를
Gemini API로 생성하고, 비즈니스 규칙을 코드로 2차 검증한다. 어르신용 Windows
데스크톱 GUI(.exe)로 배포한다.

## 구성 파일

| 파일 | 역할 |
|------|------|
| `menu_planner.py` | 핵심 로직 — 달력 생성, 프롬프트(System Instruction), Gemini 호출, 규칙 검증(`validate_menu`), 자동 재생성(`generate_validated_menu`), CLI |
| `menu_data.py` | 메뉴 시드 풀(메인/반찬/국 + 메인 속성). **실제 운영 메뉴로 교체 예정** |
| `app_config.py` | API 키를 PC 설정폴더(`%APPDATA%\MenuPlanner`)에 저장/로드 |
| `exporters.py` | 엑셀(.xlsx)/텍스트 저장, Windows 인쇄 |
| `gui.py` | Tkinter 2단 GUI — 왼쪽 엑셀형 표 미리보기(셀 더블클릭 수정) + 오른쪽 설정 패널 |
| `settings_windows.py` | 메뉴 설정 창(검색·정렬·일시정지) / 조건 설정 창 |
| `history.py` | 과거 실제 식단 기록 저장/조회, 통계, 프롬프트 블록, 엑셀 가져오기 |
| `history_window.py` | 과거 식단 입력 창(한 행 = 하루, 중식 6칸 + 석식 6칸) |
| `store.py` | 메뉴 풀·조건·설정 영속화(JSON) + 일시정지 상태 + GitHub 동기화 |
| `tests/` | 회귀 테스트(pytest) — 규칙 검증·조건 해석·엑셀 서식·과거 기록·충돌 점검 |
| `.github/workflows/build-windows.yml` | 테스트 통과 후 Windows 단일 `.exe` 자동 빌드(PyInstaller) |

## 개발 환경

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt            # 실행만 하려면 requirements.txt
```

API 키는 환경변수 `GEMINI_API_KEY` 또는 GUI 설정에서 입력. **키를 코드/저장소에 커밋 금지.**

## 실행

```bash
python gui.py                     # 데스크톱 GUI
python menu_planner.py 2026 7     # CLI 생성
python menu_planner.py 2026 7 --dry-run            # API 없이 골격/프롬프트 확인
python menu_planner.py 2026 2 --closed-days 16,17,18   # 예외 휴무일 제외
python menu_planner.py 2026 8 --use-history only       # 과거에 냈던 메뉴만으로
```

## 테스트

```bash
pytest            # 전체 (약 1초)
pytest tests/test_exporters.py -v
```

- `tests/conftest.py` 의 `isolated_config` 가 **autouse** 로 `app_config.config_dir` 를
  임시 폴더로 갈아끼운다. 이게 없으면 테스트가 실제 `menu_pool.json`·`history.json` 을
  덮어쓴다. 새 테스트 파일을 만들어도 이 픽스처는 자동으로 걸린다.
- 규칙을 고칠 땐 `tests/test_validate.py` 를 같이 고친다. 프롬프트와 코드 양쪽에
  규칙이 있는 구조라, 코드 쪽을 여기서 못 박아 두는 게 유일한 안전망이다.
- `tests/test_exporters.py` 는 원본 서식 수치(열 너비 31.38/25.13, 행 높이,
  `wrap_text=True`, `WRAP_SLACK`)를 잠근다. **이 테스트가 깨지면 인쇄물이 깨진 것**이다.
- CI는 `test`(ubuntu) → `build`(windows) 순서라 테스트가 깨지면 exe가 안 나온다.

## 핵심 비즈니스 규칙 (변경 시 `validate_menu`도 함께 수정)

- 끼니당 6개: 메인1·반찬3·김치류1·국1. 김치는 모두 "김치류"로 표기
- 같은 메인 4일 이내 재등장 금지 / 모든 메인 월 1회 이상
- 수육=중식만, 후라이드치킨=평일 중식 월 2회, 쭈꾸미=월 1~2회·1주 간격, 생선류=월 4회 이하
- 점심=자극적 / 저녁=깔끔, 주말·공휴일=조리 용이
- 소방서 배달 특성상 **매일(평일/주말/공휴일) 운영**. 예외 휴무는 `closed_days`로 제외

## 조건(conditions.py)

- 종류: `text`(서술형) / `menu_count` / `menu_section` / `menu_weekday`(요일 제한)
  / `menu_gap` / `category_max`. 새 종류를 넣을 땐 `TYPE_LABELS` · `to_text` ·
  `validate` · `_ConditionForm._build_fields` · `_ok` 다섯 곳을 함께 고친다.
- **서술형**: `parse_text()` 가 문장을 아는 형태로 바꿔 주면 구조화 조건으로
  저장돼 코드 검증까지 걸린다(권장). 못 알아들으면 `{"type":"text"}` 로 문장을
  그대로 두고 프롬프트에만 싣는다 — 이건 자동 검사가 안 되므로 목록에 ✎ 로 표시.
  `parse_text` 는 한 문장에서 여러 조건을 뽑을 수 있어 **리스트**를 반환한다.
- 조사 처리 주의: `_split_menu` 는 `은/는/을/를` 만 뗀다. `이/가` 를 떼면
  ‘고등어구이 → 고등어구’ 처럼 실제 메뉴 이름이 깨진다.

## 과거 식단 기록 (history.py)

- `history.json`: `{"2026-07": {"1": {"중식": [6개], "석식": [6개]}}}`. 항목은 항상 6칸.
  `store.DATA_FILES` 에 들어 있어 GitHub 동기화로 다른 PC에도 같이 간다.
- 넣는 길 3가지: 과거 식단 창에 직접 입력 / 예전 식단표 `.xlsx` 가져오기 /
  메인 화면 [지금 표를 기록에 저장](만들어서 실제로 낸 것만 넣는다).
- 활용 방식은 `settings.json` 의 `history_mode`: `off` / `ref`(참고, 기본) / `only`(과거 메뉴만).
  - `ref`: 직전 2개월 실제 식단 전문 + 메인별 총 횟수·마지막 등장일을 프롬프트에 싣는다.
  - `only`: 거기에 더해 과거에 쓴 이름 목록만 허용하고 `validate_menu` 로도 막는다.
- **달 경계 검증**: `recent_tail()` 이 지난달 꼬리를 `(상대일, 끼니, 메인, 표기)` 로 주고,
  상대일은 '대상 월 1일 = 1' 기준이라 생성 결과의 일(day)과 바로 뺄 수 있다.
  같은 달 안만 보는 기존 4일 규칙이 달을 넘어가도 이어지게 하는 장치.
- `history.py` 는 **store 를 import 하지 않는다**(store → history 방향이라 순환이 된다).
  풀에 반영하는 일은 `store.add_missing_from_history()` 쪽에 둔다.
  같은 이유로 `menu_planner` 도 history 를 모듈 상단에서 부르지 않는다(CLI 안에서 지연 import).
- 엑셀 가져오기는 배달형/주방형 두 서식을 모두 읽는다. 판정은 '1~31 정수가 여러 칸인 행 =
  날짜행', '줄바꿈이 든 칸 = 메뉴칸'. 안내문(※)이 메뉴로 딸려 들어가지 않게
  항목 2개 미만인 칸은 버린다.

## 메뉴 일시정지 (당분간 못 내는 메뉴)

- 상태는 `settings.json` 의 `paused` 에 저장: `{"mains": {이름: {"note": 사유}}, "sides":…, "soups":…}`.
  `menu_pool.json`(마스터 목록)은 건드리지 않는다 — 재개하면 속성이 그대로 돌아와야 하므로.
- 생성 경로: `store.pool_to_menupool()` 이 기본으로 제외 + `paused` 이름 목록을
  프롬프트 금지 블록과 `validate_menu` 에 함께 넘긴다. **‘추가된 메뉴만 사용’이 꺼져
  있어도** 모델이 지어낼 수 있으므로 검증까지 반드시 같이 태울 것.
- 이름 대조는 `conditions.name_matches()` 한 곳만 사용(‘쭈꾸미’↔‘쭈꾸미볶음’ 부분 일치,
  한 글자는 완전 일치만).
- `store.check_conflicts()` 가 생성 전에 잡는 충돌: 한 갈래가 전부 정지 / ‘월 N회 이상·정확히’
  조건의 메뉴가 정지.

## 엑셀 서식

- 기준은 `식단표_EXCEL/7월식단표.xlsx` 의 `배달-26.07` / `주방-26.07` 시트(모든 월 시트 동일).
- 수치는 `exporters.py` 상단 상수에 모아 뒀다. **열 너비를 줄이면 메뉴 글자가 잘린다**
  (배달 A~G=31.38 / 주방 B~H=25.13, 셀에 wrap 이 없어 너비가 표시 폭을 그대로 결정).
- 요일 머리글은 엑셀만 ‘일요일…토요일’ 전체 표기, GUI 미리보기는 ‘일…토’.
- **원본과 일부러 다른 곳은 딱 하나: 메뉴 칸의 `wrap_text=True`.**
  원본은 구글 스프레드시트에서 만든 파일이라 `wrapText` 없이도 줄바꿈이 보이지만,
  엑셀은 자동 줄 바꿈이 꺼져 있으면 셀 안의 `\n` 을 그리지 않아 식단이 한 줄로
  보인다(더블클릭하면 제대로 보임). 이 플래그는 되돌리지 말 것.
- 행 높이는 `BASE_LINES`(=11줄: 항목 6 + 사이 빈 줄 5) 기준. 줄바꿈으로 줄이
  늘어난 만큼만 비례해 키워 원본 높이를 유지한다(`_menu_lines` / `_row_height`).

## 주의

- 규칙은 프롬프트(`SYSTEM_INSTRUCTION`)와 코드(`validate_menu`) 양쪽에 있음 — 한쪽만 고치지 말 것
- Gemini 모델: `menu_planner.DEFAULT_MODEL`(현재 `gemini-3.6-flash`) 한 곳에서만 정의.
  Gemini 2.5 계열은 신규 사용자 지원 종료(404). 모델이 은퇴/할당량 초과(429)면
  `MODEL_FALLBACKS` 로 자동 대체하므로, 교체 시 이 상수들만 수정하면 된다.
  Pro 계열은 무료 API 키에 할당량이 없어 429가 난다(유료 키 전용)
- `.exe` 빌드는 Windows에서만 가능 → GitHub Actions 또는 `build_windows.bat` 사용
