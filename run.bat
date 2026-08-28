@echo off
cd /d "%~dp0"
echo Starting LanguageAgent server...
start "LanguageAgent server (close this window to stop)" "%~dp0.venv\Scripts\python.exe" -m uvicorn langpractice.app:app --host 127.0.0.1 --port 8000
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"
