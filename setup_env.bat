@echo off
chcp 65001 > nul
title AutoDub Studio - Environment Setup
echo ========================================================
echo   THIET LAP MOI TRUONG AO .VENV DONG NHAT CHO DU AN
echo ========================================================
echo.

:: Tim Python 3.10 hoac python phu hop tren he thong
set PYTHON_CMD=
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py -3.10 -V >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py -3.10
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            set PYTHON_CMD=py
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python 3.10 tu https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Su dung trinh thong dich: %PYTHON_CMD%
echo [2/3] Dang khoi tao moi truong ao .venv...
%PYTHON_CMD% -m venv "%~dp0.venv" --system-site-packages

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Khong the tao thu muc .venv!
    pause
    exit /b 1
)

echo [3/3] Cai dat va dong bo toan bo thu vien tu requirements.txt...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"

echo.
echo ========================================================
echo   THIET LAP HOAN TAT! MOI TRUONG DA DUOC DONG NHAT.
echo   Tu bay gio bro chi can click dup run_gui.bat de chay app.
echo ========================================================
pause
