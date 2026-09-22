@echo off
REM ============================================================
REM  Menu Planner launcher - just double-click this file.
REM  (This file is ASCII-only on purpose: cmd.exe mis-parses
REM   batch files that contain Korean characters.)
REM ============================================================
cd /d "%~dp0"
title Menu Planner

REM --- [1] find python: .venv > py launcher > python ---
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

REM --- [2] install required libraries if missing ---
%PY% -c "from google import genai; import openpyxl" >nul 2>nul
if errorlevel 1 (
    echo Installing required libraries... this may take a few minutes.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Library install failed. Check your internet connection.
        echo.
        pause
        exit /b 1
    )
)

REM --- [3] run the app ---
echo Starting Menu Planner...
%PY% gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] The program exited with an error. See the message above.
    echo.
    pause
)
