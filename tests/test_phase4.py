"""
Kiểm thử cho Phase 4: Module Dịch Thuật LLM (Translator).
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

from core.translator import clean_json_response, build_system_prompt, translate_segments


def test_clean_json_response():
    """Kiểm tra hàm làm sạch phản hồi JSON từ LLM khi có markdown fences."""
    raw_with_markdown = """
    Chào bạn, đây là bản dịch:
    ```json
    [
      {"index": 0, "start": 0.0, "end": 2.0, "translated_text": "Xin chào"}
    ]
    ```
    Hy vọng giúp ích được cho bạn!
    """
    cleaned = clean_json_response(raw_with_markdown)
    assert cleaned.startswith("[") and cleaned.endswith("]"), f"Lỗi parse JSON: {cleaned}"
    print("✓ test_clean_json_response: PASSED")


def test_empty_segments():
    """Kiểm tra xử lý danh sách rỗng không phát sinh lỗi."""
    assert translate_segments([]) == []
    print("✓ test_empty_segments: PASSED")


def test_prompt_builder():
    """Kiểm tra sinh prompt kỹ thuật."""
    prompt = build_system_prompt("Tiếng Trung", "Tiếng Việt", "Hài hước", "Luffy: Lù")
    assert "Tiếng Trung" in prompt
    assert "Tiếng Việt" in prompt
    assert "Luffy: Lù" in prompt
    print("✓ test_prompt_builder: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 4 ===")
    test_clean_json_response()
    test_empty_segments()
    test_prompt_builder()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 4 ĐÃ VƯỢT QUA ===")
