@echo off
chcp 65001 > nul
title AutoDub Studio Launcher
echo ========================================================
echo        ĐANG KHỞI CHẠY AUTODUB STUDIO...
echo ========================================================
python gui.py
if errorlevel 1 (
    echo.
    echo [LỖI] Không thể khởi chạy ứng dụng.
    echo Vui lòng kiểm tra môi trường Python và chạy: pip install -r requirements.txt
    pause
)
