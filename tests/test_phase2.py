"""
Kiểm thử cho Phase 2: Module Downloader & Audio Extractor.
"""

import sys
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows để in tiếng Việt mượt mà
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Thêm thư mục gốc vào sys.path để import core
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.downloader import is_url, download_video
from core.audio_extractor import find_ffmpeg, extract_audio


def test_is_url():
    """Kiểm tra hàm nhận diện URL."""
    assert is_url("https://www.tiktok.com/@user/video/123") is True
    assert is_url("http://example.com/video.mp4") is True
    assert is_url("D:/videos/my_video.mp4") is False
    assert is_url("C:\\test\\clip.mp4") is False
    print("✓ test_is_url: PASSED")


def test_local_video_handling():
    """Kiểm tra xử lý video cục bộ nếu tệp không tồn tại sẽ báo lỗi đúng."""
    try:
        download_video("non_existent_file.mp4")
        assert False, "Cần ném ngoại lệ FileNotFoundError"
    except FileNotFoundError:
        print("✓ test_local_video_handling: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 2 ===")
    test_is_url()
    test_local_video_handling()
    print("=== TẤT CẢ TEST ĐƠN VỊ ĐÃ VƯỢT QUA ===")
