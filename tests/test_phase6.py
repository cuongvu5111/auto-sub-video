"""
Kiểm thử cho Phase 6: Module Audio Mixer, Subtitle Generator & Pipeline.
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

from core.audio_mixer import format_ass_timestamp, generate_ass_file


def test_ass_timestamp_formatting():
    """Kiểm tra định dạng timestamp theo chuẩn ASS."""
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(65.5) == "0:01:05.50"
    assert format_ass_timestamp(3661.25) == "1:01:01.25"
    print("✓ test_ass_timestamp_formatting: PASSED")


def test_generate_ass_file():
    """Kiểm tra sinh tệp phụ đề .ass."""
    sample_segments = [
        {"start": 0.5, "end": 2.3, "translated_text": "Xin chào các bạn"},
        {"start": 2.5, "end": 4.1, "translated_text": "Hôm nay có mẹo rất hay"}
    ]
    test_ass = root_dir / "temp" / "test_sample.ass"
    test_ass.parent.mkdir(parents=True, exist_ok=True)

    result_path = generate_ass_file(sample_segments, test_ass)
    assert result_path.exists() and result_path.stat().st_size > 0

    content = result_path.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "TikTokStyle" in content
    assert "Xin chào các bạn" in content
    print("✓ test_generate_ass_file: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 6 ===")
    test_ass_timestamp_formatting()
    test_generate_ass_file()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 6 ĐÃ VƯỢT QUA ===")
