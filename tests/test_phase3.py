"""
Kiểm thử cho Phase 3: Module Nhận Diện Giọng Nói (Transcriber).
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


def test_whisper_beam_size_and_word_timestamps_are_configurable():
    from core.transcriber import transcribe_audio
    from config import Config
    from unittest.mock import MagicMock
    import tempfile

    with tempfile.TemporaryDirectory(prefix="whisper_options_", dir=str(root_dir / "temp")) as tmp:
        audio_path = Path(tmp) / "input.wav"
        audio_path.write_bytes(b"fake audio fixture")
        segment = SimpleNamespace(start=0.0, end=0.8, text="hello", words=None)
        model = MagicMock()
        model.transcribe.return_value = ([segment], SimpleNamespace())

        with patch("core.transcriber.get_whisper_model", return_value=model), \
             patch.object(Config, "WHISPER_BEAM_SIZE", 2):
            result = transcribe_audio(audio_path, language="en", word_timestamps=False)

        assert len(result) == 1
        assert result[0]["words"] == []
        assert model.transcribe.call_args.kwargs["beam_size"] == 2
        assert model.transcribe.call_args.kwargs["word_timestamps"] is False

    print("✓ test_whisper_beam_size_and_word_timestamps_are_configurable: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 3 ===")
    test_missing_audio_handling()
    test_whisper_beam_size_and_word_timestamps_are_configurable()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 3 ĐÃ VƯỢT QUA ===")
