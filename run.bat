@echo off
cd /d "%~dp0"
echo Starting LanguageAgent voice bot (port 7860)...
start "LanguageAgent voice bot (close this window to stop)" "%~dp0.venv\Scripts\python.exe" -m langpractice.voice_bot -t webrtc --port 7860
echo Starting LanguageAgent server (port 8000)...
start "LanguageAgent server (close this window to stop)" "%~dp0.venv\Scripts\python.exe" -m uvicorn langpractice.app:app --host 127.0.0.1 --port 8000
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"
