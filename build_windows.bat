@echo off
REM ============================================================
REM  Build MenuPlanner.exe on Windows - just double-click.
REM  (ASCII-only on purpose: cmd.exe mis-parses batch files
REM   that contain Korean characters.)
REM ============================================================
cd /d "%~dp0"
title Build MenuPlanner

REM --- find python: .venv > py launcher > python ---
set "PY="
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    set "PY=python"
)
if defined PY goto :found

py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto :found

python --version >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto :found

echo.
echo [ERROR] Python not found.
echo Install Python from https://www.python.org/downloads/
echo and check "Add Python to PATH" during setup.
echo.
pause
exit /b 1

:found

echo [1/3] Installing libraries...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo.
    echo [ERROR] Library install failed. Check your internet connection.
    pause
    exit /b 1
)

echo [2/3] Building EXE... this may take a few minutes.
%PY% -m PyInstaller --noconfirm --onefile --windowed --name MenuPlanner ^
    --collect-all google.genai gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See the messages above.
    pause
    exit /b 1
)

echo [3/3] Done. See dist\MenuPlanner.exe
pause
