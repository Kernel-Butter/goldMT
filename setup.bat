@echo off
title GoldBot — First Time Setup
echo ==========================================
echo   GoldBot Setup
echo   Run this once after cloning the project
echo ==========================================
echo.

cd /d "%~dp0"

REM --- Step 1: .env ---
if not exist ".env" (
    echo [SETUP] Creating .env from template...
    copy ".env.example" ".env" >nul
    echo [DONE]  .env created.
    echo [ACTION] Open .env and add your GROQ_API_KEY before starting the bot.
    echo.
) else (
    echo [OK]    .env already exists.
)

REM --- Step 2: Python venv ---
if not exist "venv" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv venv
    echo [DONE]  venv created.
    echo.
) else (
    echo [OK]    venv already exists.
)

REM --- Step 3: Install bot dependencies ---
echo [SETUP] Installing bot dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo [DONE]  Bot dependencies installed.
echo.

REM --- Step 4: Install bridge dependencies ---
echo [SETUP] Installing bridge dependencies...
pip install -r bridge\requirements.txt --quiet
echo [DONE]  Bridge dependencies installed.
echo.

REM --- Step 5: Generate .claude/settings.json with correct path for this machine ---
echo [SETUP] Generating MCP config for this machine...

if not exist ".claude" mkdir ".claude"

REM Write settings.json using current directory as the base path
REM %~dp0 gives the full path to this script's directory (with trailing backslash)
REM We replace backslashes with forward slashes for JSON compatibility
set "PROJECT_PATH=%~dp0"
set "PROJECT_PATH=%PROJECT_PATH:\=/%"
REM Remove trailing slash
if "%PROJECT_PATH:~-1%"=="/" set "PROJECT_PATH=%PROJECT_PATH:~0,-1%"

(
    echo {
    echo   "mcpServers": {
    echo     "goldbot-context": {
    echo       "command": "npx",
    echo       "args": [
    echo         "-y",
    echo         "@modelcontextprotocol/server-filesystem",
    echo         "%PROJECT_PATH%/agents"
    echo       ]
    echo     }
    echo   }
    echo }
) > ".claude\settings.json"

echo [DONE]  MCP config written to .claude\settings.json
echo.

REM --- Done ---
echo ==========================================
echo   Setup complete!
echo ==========================================
echo.
echo Next steps:
echo   1. Open .env and add your GROQ_API_KEY
echo   2. Open MetaTrader 5 and log into your demo account
echo   3. Run start_all.bat to launch everything
echo.
pause
