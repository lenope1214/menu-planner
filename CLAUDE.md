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
- `tests/test_exporters.py` 는 서식 수치(열 너비·메뉴 행 높이·메뉴 사이 빈 줄,
  `wrap_text=True`, 인쇄 폭맞춤)를 잠근다.
  **이 테스트가 깨지면 인쇄물이 깨진 것**이다.
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

## 조건이 새지 않게 하는 장치 (검증·재생성)

- **조건 검사는 메인·반찬·국 전부를 본다**(`conditions._hits` / `item_has`). 메인만 세면
  ‘계란찜 월 3회 이하’ 같은 반찬·국 조건은 어겨도 늘 통과한다. 횟수류는 한 방향
  (`item_has`: 조건 이름이 칸 이름에 들어 있을 때만), 요일·일시정지는 `name_matches`.
- **달력 대조**: `validate_menu(..., year, month, closed_days)` 가 빠진 날짜·중복·틀린 요일
  표기를 잡는다. 출력이 중간에 끊기거나 모델이 요일을 틀리게 적으면 나머지 검사가
  전부 통과해 버리므로, 생성 경로에서는 반드시 연/월을 넘길 것. 요일 조건도 표기가 아니라
  실제 달력(`_real_wday`)으로 본다.
- **위반 메시지에는 날짜를 적는다**(`_where`). 재생성 프롬프트에 그대로 들어가 고칠 곳을 알려준다.
- **재생성은 ‘위반만 고치기’**: `generate_validated_menu` 가 지금까지 가장 나은 결과를
  `previous` 로 주고 위반 목록만 고치게 한다(통째로 새로 만들면 다른 자리에서 새 위반이 난다).
  재시도마다 temperature 를 낮추고, 끝내 못 맞추면 **위반이 가장 적었던** 결과를 돌려준다.
- **우선순위**: `SYSTEM_INSTRUCTION` 의 특정 메뉴 규칙(7~10)은 기본값일 뿐이고, 사용자 조건이
  우선한다고 시스템 지시·조건 블록 양쪽에 적어 뒀다. 사용자가 ‘후라이드치킨 월 3회’로 바꿨는데
  시스템 지시가 ‘정확히 2회’라고 우기면 조건이 무시된 것처럼 보인다.
- **마지막 방어선은 코드가 직접 고치기**(`menu_planner.repair_menu`). 모델은 ‘쓰지 마라’를
  여러 번 들어도 과거 기록·예시에 자주 나온 메뉴를 계속 쓰는 일이 있다(실제 사례: 일시정지
  반찬 7번, 석식 수육 3건을 4회 시도로도 못 고침). `validate_menu(culprits=[])` 가 ‘바꿔야 할 칸’을
  알려주면, 그 칸만 풀의 다른 메뉴(덜 나온 것부터)로 바꿔 보고 **위반이 실제로 줄어드는 교체만**
  받아들인다. 모자란 횟수(‘정확히 2회’인데 1회)는 맞는 자리에 채워 넣는다.
  새 검사를 추가하면 `blame(...)` 으로 바꿀 칸을 같이 알려 줄 것 — 안 그러면 repair 가 못 고친다.
  형식 오류·빠진 날짜처럼 바꿔치기로 못 푸는 위반은 건드리지 않고 재시도/경고로 넘긴다.
- 서술형(✎) 조건은 여전히 프롬프트에만 실리고 코드로 확인하지 못한다.

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
- 수치는 `exporters.py` 상단 상수에 모아 뒀다. **원본 값 그대로이니 임의로 바꾸지 말 것.**
  - 열 너비: 배달 A~G `DLV_COL_W`=31.38 / 주방 B~H `KIT_COL_W`=25.13(‘구분’ 열 A 는 기본 12.63).
    원본은 `<col min=1 max=7>` 처럼 묶어 적혀 있어 openpyxl 로 읽으면 첫 열에만 너비가
    보인다 — 예전에 이걸 ‘A 만 넓고 나머지는 좁다’로 잘못 읽어 13 → 26 으로 헤맸다.
  - 메뉴 행 높이: 배달 `DLV_ROW_H_MENU`=337.5 / 주방 `KIT_ROW_H_MENU`=311.25.
  - 메뉴 칸은 항목 사이에 **빈 줄 한 칸**(`MENU_SEP`="\n\n", 6개 = 11줄). 원본 셀에는
    `"\n \n "` 처럼 공백이 섞여 있지만 가운데 정렬이 틀어지므로 공백은 넣지 않는다.
  - 열 합계가 종이 폭을 넘으므로 `_page()` 의 `fitToWidth=1` 로 인쇄를 1페이지 폭에 맞춘다.
- **GUI 저장은 항상 한 파일에 두 탭**(`save_xlsx(preset=exporters.PRESET_BOTH)`): `배달-YY.MM` 다음에
  `주방-YY.MM`. 보기 형식 라디오는 미리보기만 바꾸고 저장 내용에는 영향이 없다. 구글 시트에서
  `파일 → 가져오기 → 새 시트 삽입` 하면 두 탭이 한 번에 들어간다. `history.import_xlsx` 는
  같은 달의 두 탭을 한 번만 센다.
- 요일 머리글은 엑셀만 ‘일요일…토요일’ 전체 표기, GUI 미리보기는 ‘일…토’.
- **원본과 일부러 다른 곳은 딱 하나: 메뉴 칸의 `wrap_text=True`.**
  원본은 구글 스프레드시트에서 만든 파일이라 `wrapText` 없이도 줄바꿈이 보이지만,
  엑셀은 자동 줄 바꿈이 꺼져 있으면 셀 안의 `\n` 을 그리지 않아 식단이 한 줄로
  보인다(더블클릭하면 제대로 보임). 이 플래그는 되돌리지 말 것.
- 메뉴 행 높이는 평소엔 원본 값 고정이다. 메뉴명이 길어 줄이 접힌 칸이 있을 때만
  `calc_row_height` 가 접힌 줄 수만큼 키운다(`_MAX_ROW_PT` 상한).
- 서식을 손댔으면 원본 시트와 셀 단위로 대조해 볼 것(행 높이·열 너비·병합·색이
  전부 같아야 하고, 달라도 되는 건 날짜칸 회전 번호와 `wrap_text` 뿐).

## 날짜 옆 회전 번호 (1→2→3)

- `layouts.cycle_number()` 한 곳에서만 계산한다. 기준은 `CYCLE_ANCHOR`(2026-12-01 = 1),
  달·해가 바뀌어도 끊기지 않고 매일 1→2→3 으로 돈다. 주기를 바꾸려면 `CYCLE_LEN`.
- **주방용에만 붙인다.** 엑셀 주방형 날짜칸(`12/1 (1)`) · GUI 미리보기 주방형 ·
  주방용 보기에서의 복사/인쇄/텍스트 저장(`12/1(화) (1): …`).
- **배달용에는 넣지 않는다.** 엑셀 배달형 날짜칸은 원본처럼 숫자만 둔다 — 가게의 구글 시트
  주방 탭이 `=INDIRECT("'"&$C$24&"'!a5")` 로 배달 탭의 날짜 숫자를 끌어다 쓰고, 회전 번호는
  그 수식에서 붙이기 때문이다(글자가 들어가면 그 수식이 깨진다).
- 표준 텍스트(검증·엑셀 저장·프롬프트용)에는 붙이지 않는다. `LINE_RE` 와
  `history._cell_day()` 는 번호가 붙은 형식도 읽으므로 내보낸 파일을 다시 가져와도 된다.

## 마지막 식단표 기억 (last_menu.json)

- 만든 식단표는 `store.save_last_menu()` 로 `last_menu.json` 에 남고, 프로그램을 켜면
  `gui._restore_last_menu()` 가 그 연/월·내용을 그대로 다시 띄운다(API 호출 없음).
- 저장 시점(`gui._remember`): 생성 직후 / 칸을 고치고 벗어날 때 / 보기 형식 전환 /
  저장·복사·인쇄 / 창을 닫을 때. 화면에서 고친 내용까지 남는다.
- 이 PC 의 작업 초안이라 `DATA_FILES`(GitHub 동기화)에는 넣지 않는다. `.gitignore` 대상.

## 주의

- 규칙은 프롬프트(`SYSTEM_INSTRUCTION`)와 코드(`validate_menu`) 양쪽에 있음 — 한쪽만 고치지 말 것
- Gemini 모델: `menu_planner.DEFAULT_MODEL`(현재 `gemini-3.6-flash`) 한 곳에서만 정의.
  Gemini 2.5 계열은 신규 사용자 지원 종료(404). 모델이 은퇴/할당량 초과(429)면
  `MODEL_FALLBACKS` 로 자동 대체하므로, 교체 시 이 상수들만 수정하면 된다.
  GUI/CLI가 고를 수 있는 목록은 `list_available_models()` 가 API 에서 받아오고,
  조회 전·실패 시에만 `MODEL_CHOICES`/`MODEL_FALLBACKS` 를 쓴다.
  Pro 계열은 무료 API 키에 할당량이 없어 429가 난다(유료 키 전용)
- `.exe` 빌드는 Windows에서만 가능 → GitHub Actions 또는 `build_windows.bat` 사용
