"""
Kiểm thử cho Phase 3: Module Nhận Diện Giọng Nói (Transcriber).
"""

import sys
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Thêm thư mục gốc vào sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.transcriber import transcribe_audio, TranscriptionError


def test_missing_audio_handling():
    """Kiểm tra xử lý lỗi khi file âm thanh không tồn tại."""
    try:
        transcribe_audio("non_existent_audio_file.wav")
        assert False, "Cần ném ngoại lệ FileNotFoundError"
    except FileNotFoundError:
        print("✓ test_missing_audio_handling: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 3 ===")
    test_missing_audio_handling()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 3 ĐÃ VƯỢT QUA ===")
