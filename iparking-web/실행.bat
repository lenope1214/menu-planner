@echo off
REM ================================================================
REM  아이파킹 스토어 자동화 웹앱 실행 (Windows)
REM  처음 한 번만 의존성 설치 후, 이후에는 서버 실행 + 브라우저 오픈
REM ================================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python 이 설치되어 있지 않습니다. https://www.python.org 에서 설치해 주세요.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [설치] 최초 실행 - 가상환경과 라이브러리를 설치합니다...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip >nul
  pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

echo [실행] 서버를 시작합니다. 브라우저가 자동으로 열립니다.
echo        종료하려면 이 창에서 Ctrl+C 를 누르세요.
python app.py
pause
