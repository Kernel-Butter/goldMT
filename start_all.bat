@echo off
title GoldBot — Launcher
color 0A
echo.
echo  ================================================
echo    GoldBot ^| XAUUSD AI Trader
echo    Starting all services...
echo  ================================================
echo.

REM Check .env
if not exist "%~dp0.env" (
    echo  [ERROR] .env file not found!
    echo  [FIX]   Copy .env.example to .env and add your GROQ_API_KEY.
    echo.
    pause
    exit /b 1
)

REM Check venv
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found!
    echo  [FIX]   Run: python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo  [1/3] Starting MT5 Bridge...
start "GoldBot Bridge" cmd /k "cd /d %~dp0 && venv\Scripts\activate && echo Bridge starting... && python bridge/mt5_server.py"
timeout /t 4 /nobreak > nul

echo  [2/3] Starting Bot...
start "GoldBot Bot" cmd /k "cd /d %~dp0 && venv\Scripts\activate && echo Bot starting... && python main.py"
timeout /t 3 /nobreak > nul

echo  [3/3] Starting Dashboard...
start "GoldBot Dashboard" cmd /k "cd /d %~dp0 && venv\Scripts\activate && streamlit run dashboard.py --server.headless true --server.port 8501"
timeout /t 4 /nobreak > nul

echo.
echo  [OK] All services started!
echo  [OK] Dashboard: http://localhost:8501
echo.
start http://localhost:8501
echo  Close this window or press any key to exit launcher.
pause > nul
