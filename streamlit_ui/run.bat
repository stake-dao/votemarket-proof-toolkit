@echo off

REM Run VoteMarket Toolkit Streamlit UI with UV
REM This script should be run from the streamlit_ui directory

REM Check if UV is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo UV is not installed. Please install it first:
    echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

REM Move to the project root directory
cd /d "%~dp0\.."

REM Run Streamlit with UV
echo Starting VoteMarket Toolkit Streamlit UI...
uv run streamlit run streamlit_ui\app.py %*