# 한식 뷔페 식단표 자동 생성기 (Korean Buffet Menu Planner)

연도/월을 입력하면 해당 월의 일수·요일·공휴일을 자동 계산하여 매일 **[중식]/[석식]**
식단표를 Gemini API로 생성합니다. 모든 비즈니스 규칙을 **System Instruction + Few-shot**
으로 주입하고, 생성 결과를 **코드 레벨 Validation**으로 2차 검증합니다.

## 설치 & 실행

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="YOUR_KEY"

# 식단표 생성 (기본 모델: gemini-2.5-pro)
python menu_planner.py 2026 7

# 모델 변경
python menu_planner.py 2026 7 --model gemini-2.5-flash

# API 호출 없이 달력 골격/프롬프트만 확인
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
