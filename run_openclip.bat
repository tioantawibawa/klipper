@echo off
title OpenClip - 100% Local AI Short Video Clipper
echo ========================================================
echo   Starting OpenClip (100%% Local AI Desktop App)...
echo ========================================================
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe main.py
) else (
    python main.py
)
pause
