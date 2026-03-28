@echo off
title GoldBot - XAUUSD AI Trader
echo ==========================================
echo   GoldBot — XAUUSD AI Trading Bot
echo   Demo mode  |  Groq AI (LLaMA 3.3 70B)
echo ==========================================
echo.

REM Check .env file exists
if not exist "%~dp0.env" (
    echo [ERROR] .env file not found!
    echo [FIX]   Copy .env.example to .env and add your GROQ_API_KEY.
    echo.
    pause
    exit /b 1
)

REM Install dependencies if needed
python -c "import requests, dotenv" 2>nul
if errorlevel 1 (
    echo [SETUP] Installing dependencies...
    pip install -r "%~dp0requirements.txt"
    echo.
)

echo [INFO] Starting bot... (bridge must already be running on port 9999)
echo [INFO] Press Ctrl+C to stop.
echo.
cd /d "%~dp0"
python main.py
pause
