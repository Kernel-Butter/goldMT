@echo off
title GoldBot MT5 Bridge
echo ==========================================
echo   GoldBot MT5 Bridge Server
echo   Port: 9999  |  Make sure MT5 is open
echo ==========================================
echo.

REM Check if MetaTrader5 package is installed
python -c "import MetaTrader5" 2>nul
if errorlevel 1 (
    echo [SETUP] MetaTrader5 package not found. Installing...
    pip install -r "%~dp0requirements.txt"
    echo.
)

echo [INFO] Starting bridge server...
echo [INFO] Keep this window open while the bot is running.
echo [INFO] Press Ctrl+C to stop.
echo.
cd /d "%~dp0"
python mt5_server.py
pause
