@echo off
chcp 65001 > nul
title AutoDub Studio Launcher
echo ========================================================
echo        LAUNCHING AUTODUB STUDIO...
echo ========================================================
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

:: 1. Uu tien tuyet doi moi truong ao .venv tai thu muc du an (dong nhat moi may)
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0gui.py"
    goto :end
)

:: 2. Neu chua co .venv, uu tien goi python da cai packages
where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0gui.py"
    goto :end
)

:: 3. Fallback goi py -3.10
py -3.10 -V >nul 2>nul
if %errorlevel% equ 0 (
    py -3.10 "%~dp0gui.py"
    goto :end
)

:: 4. Fallback py mac dinh
where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0gui.py"
    goto :end
)

:end
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start application.
    echo Please run setup_env.bat to automatically configure unified .venv environment!
    pause
)
