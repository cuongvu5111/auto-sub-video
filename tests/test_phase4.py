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


def _mock_translation_response(indexes):
    import json
    from unittest.mock import MagicMock

    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps([
        {"index": index, "translated_text": f"Bản dịch {index}"}
        for index in indexes
    ])
    return response


def _translation_test_segments(count):
    return [
        {"index": index, "start": float(index), "end": float(index + 1), "text": f"原文{index}"}
        for index in range(count)
    ]


def test_configurable_translation_batch_size():
    """The configured batch size controls request count without losing segment order."""
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    original_batch_size = Config.LLM_TRANSLATION_BATCH_SIZE
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        Config.LLM_TRANSLATION_BATCH_SIZE = 2
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_translation_response([0, 1]),
            _mock_translation_response([2, 3]),
            _mock_translation_response([4]),
        ]
        with patch("openai.OpenAI", return_value=mock_client), patch("core.translator._sleep_with_cancel"):
            results = translate_segments(_translation_test_segments(5))

        assert mock_client.chat.completions.create.call_count == 3
        assert [segment["translation_status"] for segment in results] == ["translated"] * 5
        assert [segment["translated_text"] for segment in results] == [f"Bản dịch {i}" for i in range(5)]
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model
        Config.LLM_TRANSLATION_BATCH_SIZE = original_batch_size

    print("✓ test_configurable_translation_batch_size: PASSED")


def test_invalid_large_translation_batch_splits_before_fallback():
    """An incomplete large response is retried as smaller batches instead of losing all lines."""
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_translation_response([0]),
            _mock_translation_response([0, 1]),
            _mock_translation_response([2, 3]),
        ]
        logs = []
        with patch("openai.OpenAI", return_value=mock_client), patch("core.translator._sleep_with_cancel"):
            results = translate_segments(
                _translation_test_segments(4),
                batch_size=4,
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert mock_client.chat.completions.create.call_count == 3
        assert [segment["translation_status"] for segment in results] == ["translated"] * 4
        assert [segment["translated_text"] for segment in results] == [f"Bản dịch {i}" for i in range(4)]
        assert any("retrying as smaller batches" in message for message in logs)
        assert not any("kept in the source language" in message for message in logs)
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model

    print("✓ test_invalid_large_translation_batch_splits_before_fallback: PASSED")


def test_oversized_translation_batch_splits_before_fallback():
    """A provider context-size error retries smaller batches before preserving source text."""
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("maximum context length exceeded"),
            _mock_translation_response([0, 1]),
            _mock_translation_response([2, 3]),
        ]
        logs = []
        with patch("openai.OpenAI", return_value=mock_client), patch("core.translator._sleep_with_cancel"):
            results = translate_segments(
                _translation_test_segments(4),
                batch_size=4,
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert mock_client.chat.completions.create.call_count == 3
        assert [segment["translation_status"] for segment in results] == ["translated"] * 4
        assert any("retrying as smaller batches" in message for message in logs)
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model

    print("✓ test_oversized_translation_batch_splits_before_fallback: PASSED")


def test_timed_out_translation_batch_splits_before_fallback():
    """A timed-out large request is retried as smaller chunks before source fallback."""
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("Request timed out."),
            _mock_translation_response([0, 1]),
            _mock_translation_response([2, 3]),
        ]
        logs = []
        with patch("openai.OpenAI", return_value=mock_client), patch("core.translator._sleep_with_cancel"):
            results = translate_segments(
                _translation_test_segments(4),
                batch_size=4,
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert mock_client.chat.completions.create.call_count == 3
        assert [segment["translation_status"] for segment in results] == ["translated"] * 4
        assert any("retrying as smaller batches" in message for message in logs)
        assert not any("kept in the source language" in message for message in logs)
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model

    print("✓ test_timed_out_translation_batch_splits_before_fallback: PASSED")


def test_translation_batch_size_validation():
    """Reject invalid batch settings before creating provider clients."""
    from unittest.mock import patch

    with patch("openai.OpenAI") as mock_openai:
        for invalid_size in (0, 33, 1.5, "1.5", True):
            try:
                translate_segments(_translation_test_segments(1), batch_size=invalid_size)
            except ValueError as exc:
                assert "between 1 and 32" in str(exc)
            else:
                raise AssertionError(f"Invalid LLM batch size was accepted: {invalid_size!r}.")
        mock_openai.assert_not_called()
    print("✓ test_translation_batch_size_validation: PASSED")


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


def test_incomplete_translation_response_recovers_per_segment():
    """An incomplete batch response is split so valid lines are recovered independently."""
    import json
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([{"index": 0, "translated_text": "Xin chào"}])
        mock_client.chat.completions.create.return_value = mock_response
        logs = []
        with patch("openai.OpenAI", return_value=mock_client):
            result = translate_segments(
                [
                    {"index": 0, "start": 0.0, "end": 1.0, "text": "你好"},
                    {"index": 1, "start": 1.0, "end": 2.0, "text": "再见"},
                ],
                progress_callback=lambda message, percent: logs.append(message),
            )
        assert [segment["translation_status"] for segment in result] == ["translated", "source_fallback"]
        assert result[0]["translated_text"] == "Xin chào"
        assert result[1]["translated_text"] == "再见"
        assert any("retrying as smaller batches" in message for message in logs)
        assert any("kept in the source language" in message for message in logs)
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model

    print("✓ test_incomplete_translation_response_recovers_per_segment: PASSED")


def test_rate_limit_retry_wait_is_capped():
    """A provider-supplied long Retry-After value must not stall the queue indefinitely."""
    import json
    from unittest.mock import MagicMock, patch
    from config import Config

    original_backup = Config.LLM_BACKUP_ENABLED
    original_url = Config.LLM_BASE_URL
    original_model = Config.LLM_MODEL
    try:
        Config.LLM_BACKUP_ENABLED = False
        Config.LLM_BASE_URL = "https://api.test.invalid/v1"
        Config.LLM_MODEL = "test-model"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([{"index": 0, "translated_text": "Xin chào"}])
        mock_client.chat.completions.create.side_effect = [Exception("429 retry after 3600s"), mock_response]
        logs = []
        with patch("openai.OpenAI", return_value=mock_client), patch("core.translator.time.sleep") as sleep:
            result = translate_segments(
                [{"index": 0, "start": 0.0, "end": 1.0, "text": "你好"}],
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert result[0]["translated_text"] == "Xin chào"
        assert any("60.0s" in message for message in logs)
        total_wait = sum(call.args[0] for call in sleep.call_args_list)
        assert 60.0 <= total_wait < 61.0
    finally:
        Config.LLM_BACKUP_ENABLED = original_backup
        Config.LLM_BASE_URL = original_url
        Config.LLM_MODEL = original_model

    print("✓ test_rate_limit_retry_wait_is_capped: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 4 ===")
    test_clean_json_response()
    test_empty_segments()
    test_prompt_builder()
    test_configurable_translation_batch_size()
    test_invalid_large_translation_batch_splits_before_fallback()
    test_oversized_translation_batch_splits_before_fallback()
    test_timed_out_translation_batch_splits_before_fallback()
    test_translation_batch_size_validation()
    test_llm_config_persistence()
    test_llm_connection_validation()
    test_multi_provider_failover()
    test_incomplete_translation_response_recovers_per_segment()
    test_rate_limit_retry_wait_is_capped()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 4 ĐÃ VƯỢT QUA ===")
