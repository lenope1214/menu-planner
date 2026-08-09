# 한식 뷔페 식단표 자동 생성기 (Korean Buffet Menu Planner)

연도/월을 입력하면 해당 월의 일수·요일·공휴일을 자동 계산하여 매일 **[중식]/[석식]**
식단표를 Gemini API로 생성합니다. 모든 비즈니스 규칙을 **System Instruction + Few-shot**
으로 주입하고, 생성 결과를 **코드 레벨 Validation**으로 2차 검증합니다.

**하이브리드 전략**: 메뉴 마스터 데이터(`menu_data.py`)를 코드에 **시드 풀**로 두고
이를 Gemini에 '허용 어휘'로 전달해 변동성·원가를 통제하며, 부족하면 동일 스타일로 보충합니다.
운영일은 **소방서 배달 특성상 매일(평일/주말/공휴일)** 생성하며, 설날·추석 등 예외 휴무는
`--closed-days` 로 제외합니다.

## 🖥 Windows 데스크톱 프로그램 (어르신용 GUI)

큰 글씨·큰 버튼의 단순 화면으로 누구나 식단표를 만들 수 있습니다. **2단 레이아웃**:

- **왼쪽**: 엑셀처럼 보이는 표 미리보기 — **셀을 더블클릭하면 메뉴를 바로 수정**(중식/석식 줄무늬 구분)
- **오른쪽**: 설정 패널 — 연/월 선택·[식단표 만들기]·진행상태·저장/복사/인쇄·**API 키 입력**
- **API 키는 오른쪽 칸에 한 번만 입력**하면 프로그램 폴더의 `config.json`(개발: `menu-planner\config.json`, 배포: `MenuPlanner.exe` 옆)에 저장되어 자동 사용
- 저장: 엑셀(.xlsx)·텍스트(.txt) / 복사: 클립보드 / 인쇄: 기본 프린터 (모두 표의 수정 내용 반영)
- 생성 시 규칙 위반은 **자동 재생성(최대 2회)** 으로 보정

```bash
# 개발자 실행(파이썬)
pip install -r requirements.txt
python gui.py
```

### .exe 빌드 (배포용)

**① GitHub Actions(권장)** — `Actions` 탭 → `Build Windows EXE` → `Run workflow`
실행 후 산출물(`MenuPlanner-windows`)에서 `MenuPlanner.exe` 다운로드. (브랜치 푸시 시 자동 실행)

**② 내 Windows PC에서 직접** — 저장소를 받은 뒤 `build_windows.bat` 더블클릭 →
`dist\MenuPlanner.exe` 생성.

> 최종 사용자는 `.exe` 하나만 받으면 됩니다(파이썬 설치 불필요). 첫 실행 시 [설정]에서 키만 등록.

## CLI 설치 & 실행

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="YOUR_KEY"

# 식단표 생성 (기본 모델: gemini-2.5-pro)
python menu_planner.py 2026 7

# 모델 변경
python menu_planner.py 2026 7 --model gemini-2.5-flash

# 예외 휴무일 제외 (예: 설날 연휴 2/16~18)
python menu_planner.py 2026 2 --closed-days 16,17,18

# API 호출 없이 달력 골격/메뉴 풀/프롬프트만 확인
python menu_planner.py 2026 7 --dry-run
```

## 반영된 비즈니스 규칙

| # | 규칙 | 주입 방식 |
|---|------|-----------|
| 1 | 끼니당 6개(메인1·반찬3·김치류1·국1) | 프롬프트 + Validation |
| 2 | 김치 종류는 모두 `김치류`로 통일 | 프롬프트 + Validation |
| 3 | 쌈류/소스류/국 수식어 제거 | 프롬프트 |
| 4 | 같은 메인 4일 이내 재등장 금지 | 프롬프트 + Validation |
| 5 | 모든 메인 월 1회 이상 골고루 | 프롬프트 |
| 6 | A/B/C 팀 메인 분산 | 프롬프트 |
| 7 | 수육: 중식 전용 | 프롬프트 + Validation |
| 8 | 후라이드치킨: 평일 중식, 월 2회 | 프롬프트 + Validation |
| 9 | 쭈꾸미: 월 1~2회, 최소 1주 간격 | 프롬프트 + Validation |
| 10 | 생선류 월 4회 이하 | 프롬프트 + Validation |
| 11 | 점심=자극적 / 저녁=깔끔 | 프롬프트 |
| 12 | 저녁·주말·공휴일=조리 용이 메뉴 | 프롬프트 |

## 구조

- `build_month_plan()` — 연/월 → 날짜·요일·주말·공휴일 템플릿 골격
- `SYSTEM_INSTRUCTION` / `FEWSHOT_EXAMPLE` — 규칙 주입(프롬프트 엔지니어링)
- `generate_menu()` — Gemini(`gemini-2.5-pro`/`flash`) 호출
- `validate_menu()` — 규칙 위반 자동 검출(재생성 판단용)
