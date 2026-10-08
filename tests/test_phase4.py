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


def test_llm_config_persistence():
    """Kiểm tra lưu cấu hình LLM vào tệp .env."""
    from config import Config
    orig_url = Config.LLM_BASE_URL
    orig_key = Config.LLM_API_KEY
    orig_model = Config.LLM_MODEL

    try:
        Config.save_llm_config("https://api.test.com/v1", "test-key-123", "test-model-456")
        assert Config.LLM_BASE_URL == "https://api.test.com/v1"
        assert Config.LLM_API_KEY == "test-key-123"
        assert Config.LLM_MODEL == "test-model-456"

        env_file = Config.BASE_DIR / ".env"
        assert env_file.exists()
        content = env_file.read_text(encoding="utf-8")
        assert "LLM_BASE_URL=https://api.test.com/v1" in content
        assert "LLM_API_KEY=test-key-123" in content
        assert "LLM_MODEL=test-model-456" in content
        print("✓ test_llm_config_persistence: PASSED")
    finally:
        Config.save_llm_config(orig_url, orig_key, orig_model)


def test_llm_connection_validation():
    """Kiểm tra validation khi tham số rỗng hoặc không hợp lệ."""
    from core.translator import test_llm_connection
    ok, msg = test_llm_connection("", "key", "model")
    assert not ok and "Base URL cannot be empty" in msg

    ok, msg = test_llm_connection("http://localhost:11434/v1", "key", "")
    assert not ok and "Model name cannot be empty" in msg
    print("✓ test_llm_connection_validation: PASSED")


def test_multi_provider_failover():
    """Kiểm tra cơ chế chuyển đổi tự động sang Backup Provider khi Primary bị 429 Rate Limit."""
    import json
    from unittest.mock import MagicMock, patch
    from config import Config
    from core.translator import translate_segments

    orig_backup_en = Config.LLM_BACKUP_ENABLED
    orig_backup_url = Config.LLM_BACKUP_BASE_URL
    orig_backup_key = Config.LLM_BACKUP_API_KEY
    orig_backup_model = Config.LLM_BACKUP_MODEL

    try:
        Config.LLM_BACKUP_ENABLED = True
        Config.LLM_BACKUP_BASE_URL = "https://api.backup.com/v1"
        Config.LLM_BACKUP_API_KEY = "backup-key-123"
        Config.LLM_BACKUP_MODEL = "gemini-backup"

        segments = [{"index": 0, "start": 0.0, "end": 2.0, "text": "你好"}]
        logs = []

        mock_primary = MagicMock()
        mock_primary.chat.completions.create.side_effect = Exception("429 Rate Limit reached")

        mock_backup = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = json.dumps([{"index": 0, "translated_text": "Xin chào"}])
        mock_backup.chat.completions.create.return_value = mock_resp

        def mock_client_init(base_url, **kwargs):
            if "backup" in str(base_url):
                return mock_backup
            return mock_primary

        with patch("openai.OpenAI", side_effect=mock_client_init):
            results = translate_segments(segments, progress_callback=lambda msg, pct: logs.append(msg))

        assert results[0]["translated_text"] == "Xin chào"
        assert any("switch sang Backup" in log for log in logs)
        print("✓ test_multi_provider_failover: PASSED (Tự động failover sang Backup Provider khi Primary gặp 429)")

    finally:
        Config.LLM_BACKUP_ENABLED = orig_backup_en
        Config.LLM_BACKUP_BASE_URL = orig_backup_url
        Config.LLM_BACKUP_API_KEY = orig_backup_key
        Config.LLM_BACKUP_MODEL = orig_backup_model


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 4 ===")
    test_clean_json_response()
    test_empty_segments()
    test_prompt_builder()
    test_llm_config_persistence()
    test_llm_connection_validation()
    test_multi_provider_failover()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 4 ĐÃ VƯỢT QUA ===")
