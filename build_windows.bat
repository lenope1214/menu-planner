@echo off
REM ============================================================
REM  Windows 에서 식단표 프로그램(.exe) 직접 빌드
REM  사용법: 이 파일을 더블클릭하거나, 명령창에서 build_windows.bat 실행
REM ============================================================
chcp 65001 >nul
echo [1/3] 필요한 라이브러리 설치 중...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [2/3] EXE 빌드 중... (몇 분 걸릴 수 있어요)
pyinstaller --noconfirm --onefile --windowed --name MenuPlanner --collect-all google.genai gui.py

echo [3/3] 완료!  dist\MenuPlanner.exe 파일을 확인하세요.
pause
