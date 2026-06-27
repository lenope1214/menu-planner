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
| `.github/workflows/build-windows.yml` | Windows에서 단일 `.exe` 자동 빌드(PyInstaller) |

## 개발 환경

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

API 키는 환경변수 `GEMINI_API_KEY` 또는 GUI 설정에서 입력. **키를 코드/저장소에 커밋 금지.**

## 실행

```bash
python gui.py                     # 데스크톱 GUI
python menu_planner.py 2026 7     # CLI 생성
python menu_planner.py 2026 7 --dry-run            # API 없이 골격/프롬프트 확인
python menu_planner.py 2026 2 --closed-days 16,17,18   # 예외 휴무일 제외
```

## 핵심 비즈니스 규칙 (변경 시 `validate_menu`도 함께 수정)

- 끼니당 6개: 메인1·반찬3·김치류1·국1. 김치는 모두 "김치류"로 표기
- 같은 메인 4일 이내 재등장 금지 / 모든 메인 월 1회 이상
- 수육=중식만, 후라이드치킨=평일 중식 월 2회, 쭈꾸미=월 1~2회·1주 간격, 생선류=월 4회 이하
- 점심=자극적 / 저녁=깔끔, 주말·공휴일=조리 용이
- 소방서 배달 특성상 **매일(평일/주말/공휴일) 운영**. 예외 휴무는 `closed_days`로 제외

## 주의

- 규칙은 프롬프트(`SYSTEM_INSTRUCTION`)와 코드(`validate_menu`) 양쪽에 있음 — 한쪽만 고치지 말 것
- Gemini 모델: `gemini-2.5-flash`(기본, 빠름) / `gemini-2.5-pro`
- `.exe` 빌드는 Windows에서만 가능 → GitHub Actions 또는 `build_windows.bat` 사용
