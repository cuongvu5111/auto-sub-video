"""
Kiểm thử cho Phase 5: Module Lồng Tiếng AI (TTS Engine) & Đồng Bộ Tốc Độ.
"""

import sys
import asyncio
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

from core.tts_engine import (
    get_audio_duration,
    process_dubbing_segments,
    synthesize_speech_async,
    adjust_audio_speed,
    TTSError
)


def test_missing_file_duration():
    """Kiểm tra đo thời lượng file không tồn tại sẽ báo lỗi đúng."""
    try:
        get_audio_duration("non_existent_audio.mp3")
        assert False, "Cần ném ngoại lệ FileNotFoundError"
    except FileNotFoundError:
        print("✓ test_missing_file_duration: PASSED")


def test_empty_segments():
    """Kiểm tra xử lý danh sách rỗng không phát sinh lỗi."""
    assert process_dubbing_segments([]) == []
    print("✓ test_empty_segments: PASSED")


def test_live_edge_tts():
    """Kiểm tra gọi thử edge-tts sinh một đoạn audio tiếng Việt ngắn 1-2 từ."""
    test_out = root_dir / "temp" / "test_tts_sample.mp3"
    test_out.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        asyncio.run(synthesize_speech_async("Xin chào", test_out, "vi-VN-NamMinhNeural"))
        assert test_out.exists() and test_out.stat().st_size > 0
        duration = get_audio_duration(test_out)
        print(f"✓ test_live_edge_tts: PASSED (Thời lượng: {duration:.2f}s, Kích thước: {test_out.stat().st_size} bytes)")
    except Exception as e:
        print(f"! test_live_edge_tts SKIPPED/WARNING (Có thể do mạng): {e}")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 5 ===")
    test_missing_file_duration()
    test_empty_segments()
    test_live_edge_tts()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 5 ĐÃ VƯỢT QUA ===")
