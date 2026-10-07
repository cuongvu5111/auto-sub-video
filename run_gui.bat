@echo off
chcp 65001 > nul
title AutoDub Studio Launcher
echo ========================================================
echo        LAUNCHING AUTODUB STUDIO...
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
python gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start application.
    echo Please verify Python environment and run: pip install -r requirements.txt
    pause
)
