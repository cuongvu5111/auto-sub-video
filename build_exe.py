"""
Kịch bản đóng gói ứng dụng Desktop AutoDub Studio thành tệp thực thi Windows (.exe).
Sử dụng PyInstaller, tự động đính kèm FFmpeg portable và các phụ thuộc cần thiết.
"""

import sys
import subprocess
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT_DIR = Path(__file__).resolve().parent
ENTRY_POINT = ROOT_DIR / "gui.py"
BIN_FFMPEG = ROOT_DIR / "bin" / "ffmpeg.exe"


def check_pyinstaller():
    """Kiểm tra và cài đặt PyInstaller nếu chưa có."""
    try:
        import PyInstaller
        print("✓ PyInstaller đã sẵn sàng.")
    except ImportError:
        print("Đang cài đặt PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def build_application():
    """Thực thi lệnh đóng gói với PyInstaller."""
    check_pyinstaller()

    print("\n=== BẮT ĐẦU ĐÓNG GÓI AUTODUB STUDIO ===")

    # Tham số đóng gói
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",                  # Đóng gói ra thư mục phân phối (tối ưu tốc độ mở app)
        "--windowed",                # Ẩn cửa sổ terminal phụ
        "--name", "AutoDubStudio",   # Tên ứng dụng
        # Đính kèm binary FFmpeg portable
        f"--add-data={BIN_FFMPEG};bin" if BIN_FFMPEG.exists() else "",
        # Đính kèm file mẫu cấu hình
        f"--add-data={ROOT_DIR / '.env.example'};.",
        # Khai báo các module ẩn
        "--hidden-import=faster_whisper",
        "--hidden-import=edge_tts",
        "--hidden-import=pydub",
        "--hidden-import=openai",
        "--hidden-import=dotenv",
        "--hidden-import=yt_dlp",
        str(ENTRY_POINT)
    ]

    # Loại bỏ các tham số rỗng
    cmd = [arg for arg in cmd if arg]

    print("Lệnh thực thi:", " ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode == 0:
        dist_path = ROOT_DIR / "dist" / "AutoDubStudio"
        exe_path = dist_path / "AutoDubStudio.exe"
        print(f"\n🎉 ĐÓNG GÓI THÀNH CÔNG!")
        print(f"Thư mục ứng dụng: {dist_path}")
        print(f"Tệp thực thi: {exe_path}")
    else:
        print(f"\n❌ Đóng gói thất bại với mã lỗi: {result.returncode}")


if __name__ == "__main__":
    build_application()
