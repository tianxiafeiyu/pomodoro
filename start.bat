@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Pomodoro
echo Start: %date% %time%
echo Starting...
py -3 pomodoro.py || python pomodoro.py || python3 pomodoro.py
if errorlevel 1 (
    echo.
    echo Failed. Check errors above.
    pause
)
