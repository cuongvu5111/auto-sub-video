"""
Kịch bản đóng gói ứng dụng Desktop AutoDub Studio thành tệp thực thi Windows (.exe).
Sử dụng PyInstaller, tự động đính kèm FFmpeg portable, assets icons và các phụ thuộc cần thiết.
Sau khi build xong, tự động nén thư mục thành file zip để phát hành lên GitHub Releases.
"""

import sys
import subprocess
import shutil
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
ASSETS_DIR = ROOT_DIR / "assets"


def check_pyinstaller():
    """Kiểm tra và cài đặt PyInstaller nếu chưa có."""
    try:
        import PyInstaller
        print("✓ PyInstaller đã sẵn sàng.")
    except ImportError:
        print("Đang cài đặt PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def build_application():
    """Thực thi lệnh đóng gói với PyInstaller và tạo file ZIP phát hành."""
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
        # Đính kèm assets biểu tượng
        f"--add-data={ASSETS_DIR};assets" if ASSETS_DIR.exists() else "",
        # Đính kèm file mẫu cấu hình
        f"--add-data={ROOT_DIR / '.env.example'};.",
        # Khai báo các module ẩn
        "--hidden-import=PySide6",
        "--hidden-import=faster_whisper",
        "--hidden-import=edge_tts",
        "--hidden-import=pydub",
        "--hidden-import=openai",
        "--hidden-import=dotenv",
        "--hidden-import=yt_dlp",
        "--hidden-import=av",
        "--hidden-import=ctranslate2",
        str(ENTRY_POINT)
    ]

    # Loại bỏ các tham số rỗng
    cmd = [arg for arg in cmd if arg]

    print("Lệnh thực thi:", " ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode == 0:
        dist_path = ROOT_DIR / "dist" / "AutoDubStudio"
        exe_path = dist_path / "AutoDubStudio.exe"
        zip_archive_base = ROOT_DIR / "dist" / "AutoDubStudio-v1.0.0-windows-x64"

        print(f"\n🎉 ĐÓNG GÓI THÀNH CÔNG!")
        print(f"Thư mục ứng dụng: {dist_path}")
        print(f"Tệp thực thi: {exe_path}")

        # Tự động nén thành tệp ZIP sẵn sàng phát hành GitHub Releases
        print("\nĐang tạo tệp nén ZIP cho bản phát hành GitHub Releases...")
        zip_file = shutil.make_archive(
            str(zip_archive_base),
            "zip",
            root_dir=str(ROOT_DIR / "dist"),
            base_dir="AutoDubStudio"
        )
        zip_path = Path(zip_file)
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"\n📦 HOÀN TẤT TỆP NÉN PHÁT HÀNH:")
        print(f"  • Đường dẫn: {zip_path}")
        print(f"  • Dung lượng: {zip_size_mb:.2f} MB")
        print(f"  • Tên file: {zip_path.name}")
        print("\n-> Bạn có thể tải trực tiếp file zip này lên GitHub Releases!")
        return zip_path
    else:
        print(f"\n❌ Đóng gói thất bại với mã lỗi: {result.returncode}")
        return None


if __name__ == "__main__":
    build_application()
