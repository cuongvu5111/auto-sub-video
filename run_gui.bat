@echo off
chcp 65001 > nul
title AutoDub Studio Launcher
echo ========================================================
echo        LAUNCHING AUTODUB STUDIO...
echo ========================================================
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0gui.py"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        py "%~dp0gui.py"
    ) else (
        python "%~dp0gui.py"
    )
)

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start application.
    echo Please verify Python environment and run: pip install -r requirements.txt
    pause
)
