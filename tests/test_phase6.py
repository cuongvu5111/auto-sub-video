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

from core.audio_mixer import format_ass_timestamp, generate_ass_file, hex_to_ass_color


def test_ass_timestamp_formatting():
    """Kiểm tra định dạng timestamp theo chuẩn ASS."""
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(65.5) == "0:01:05.50"
    assert format_ass_timestamp(3661.25) == "1:01:01.25"
    print("✓ test_ass_timestamp_formatting: PASSED")


def test_hex_to_ass_color():
    """Kiểm tra hàm chuyển đổi mã màu hex sang chuẩn ASS &HAABBGGRR."""
    assert hex_to_ass_color("#000000") == "&H00000000"
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    assert hex_to_ass_color("#FFFF00") == "&H0000FFFF"
    assert hex_to_ass_color("&H00AABBCC") == "&H00AABBCC"
    assert hex_to_ass_color("") == "&H00FFFFFF"
    print("✓ test_hex_to_ass_color: PASSED")


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


def test_custom_ass_styling():
    """Kiểm tra sinh tệp phụ đề với kiểu hộp nền TikTok (BorderStyle=3) và màu tùy biến."""
    sample_segments = [
        {"start": 1.0, "end": 3.0, "translated_text": "Phụ đề hộp nền trắng chữ đen"}
    ]
    test_ass = root_dir / "temp" / "test_box_style.ass"
    result_path = generate_ass_file(
        sample_segments,
        test_ass,
        font_name="Arial",
        font_size=26,
        primary_color="#000000",
        outline_color="#FFFFFF",
        back_color="#FFFFFF",
        border_style=3,
        outline_width=6
    )
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    assert ",3,6,0,2,20,20,40,1" in content
    assert "&H00000000" in content
    assert "&H00FFFFFF" in content
    print("✓ test_custom_ass_styling: PASSED")


def test_ass_subtitle_positioning():
    """Kiểm tra tùy chỉnh vị trí phụ đề (Margin V, Alignment, Box Padding) để che sub cũ."""
    sample_segments = [
        {"start": 1.0, "end": 3.0, "translated_text": "Phụ đề che tiếng Trung"}
    ]
    test_ass = root_dir / "temp" / "test_pos_style.ass"
    result_path = generate_ass_file(
        sample_segments,
        test_ass,
        font_name="Arial",
        font_size=26,
        margin_v=160,
        alignment=2,
        box_padding=12
    )
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    # Style line phải chứa outline_width=12 (từ box_padding), alignment=2, margin_v=160
    assert ",3,12,0,2,20,20,160,1" in content
    print("✓ test_ass_subtitle_positioning: PASSED")


def test_ass_text_watermark():
    """Kiểm tra chèn Text Watermark ở mốc thời gian giữa video."""
    sample_segments = [
        {"start": 0.0, "end": 20.0, "translated_text": "Video dài 20 giây"}
    ]
    test_ass = root_dir / "temp" / "test_watermark.ass"
    wm_config = {
        "enabled": True,
        "text": "Bạn đang xem video được sub bởi Vũ Mạnh Cường",
        "timing_mode": "mid_video",
        "duration": 6.0,
        "position": "center",
        "font_size": 22
    }
    result_path = generate_ass_file(
        sample_segments,
        test_ass,
        total_duration=20.0,
        text_watermark=wm_config
    )
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")

    # Kiểm tra có Style WatermarkStyle
    assert "Style: WatermarkStyle" in content
    # Midpoint của 20s là 10s -> 6s duration là từ 7.0s (0:00:07.00) đến 13.0s (0:00:13.00)
    assert "Dialogue: 1,0:00:07.00,0:00:13.00,WatermarkStyle,,0,0,0,,Bạn đang xem video được sub bởi Vũ Mạnh Cường" in content
    print("✓ test_ass_text_watermark: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 6 ===")
    test_ass_timestamp_formatting()
    test_hex_to_ass_color()
    test_generate_ass_file()
    test_custom_ass_styling()
    test_ass_subtitle_positioning()
    test_ass_text_watermark()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 6 ĐÃ VƯỢT QUA ===")

