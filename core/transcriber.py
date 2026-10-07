"""
Module nhận diện giọng nói và trích xuất mốc thời gian (Speech-to-Text).
Sử dụng faster-whisper (CTranslate2) tối ưu hóa chạy cực nhanh trên CPU với INT8.
"""

import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from config import Config

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class TranscriptionError(Exception):
    """Lỗi xảy ra trong quá trình nhận diện giọng nói."""
    pass


# Biến toàn cục lưu trữ model đã nạp để tái sử dụng trong cùng phiên làm việc
_CACHED_MODEL = None
_CACHED_MODEL_NAME = None


def get_whisper_model(
    model_size: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None
):
    """
    Nạp hoặc lấy mô hình Whisper đã được lưu trong bộ nhớ đệm (Cache).
    Mặc định nạp mô hình từ Config (base hoặc small, chạy CPU với int8).
    """
    global _CACHED_MODEL, _CACHED_MODEL_NAME

    target_model = model_size or Config.WHISPER_MODEL
    req_device = (device or Config.WHISPER_DEVICE or "auto").lower()
    req_compute = (compute_type or Config.WHISPER_COMPUTE_TYPE or "auto").lower()

    # Tự động nhận diện phần cứng nếu đặt là auto
    hw = Config.detect_hardware_capabilities()
    if req_device == "auto":
        target_device = "cuda" if hw["has_cuda"] else "cpu"
    else:
        target_device = req_device

    if req_compute == "auto":
        target_compute = "float16" if target_device == "cuda" else "int8"
    else:
        target_compute = req_compute

    cache_key = f"{target_model}_{target_device}_{target_compute}"

    if _CACHED_MODEL is not None and _CACHED_MODEL_NAME == cache_key:
        return _CACHED_MODEL

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise TranscriptionError(
            "Thư viện faster-whisper chưa được cài đặt. Vui lòng chạy: pip install faster-whisper"
        )

    try:
        # Nạp mô hình với CTranslate2 (CUDA hoặc CPU)
        model = WhisperModel(
            target_model,
            device=target_device,
            compute_type=target_compute,
            download_root=str(Config.TEMP_DIR / "whisper_models")
        )
        _CACHED_MODEL = model
        _CACHED_MODEL_NAME = cache_key
        return model

    except Exception as e:
        # Nếu đang khởi tạo bằng CUDA mà thất bại (thiếu cuDNN/driver), tự động fallback CPU mượt mà
        if target_device == "cuda":
            try:
                print(f"[Whisper] CUDA initialization failed ({e}). Auto-falling back to CPU int8...")
                fallback_model = WhisperModel(
                    target_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(Config.TEMP_DIR / "whisper_models")
                )
                _CACHED_MODEL = fallback_model
                _CACHED_MODEL_NAME = f"{target_model}_cpu_int8"
                return fallback_model
            except Exception as cpu_err:
                raise TranscriptionError(f"Lỗi khởi tạo Whisper trên CPU sau khi CUDA thất bại: {str(cpu_err)}") from cpu_err

        raise TranscriptionError(f"Không thể khởi tạo mô hình Whisper ({target_model}): {str(e)}") from e


def transcribe_audio(
    audio_path: Path | str,
    language: Optional[str] = "zh",
    word_timestamps: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> List[Dict[str, Any]]:
    """
    Nhận diện giọng nói từ tệp audio WAV và trích xuất danh sách câu thoại kèm mốc thời gian.

    Args:
        audio_path: Đường dẫn tệp âm thanh (nên là WAV 16kHz mono).
        language: Mã ngôn ngữ (ví dụ: 'zh' cho tiếng Trung, 'en' cho tiếng Anh, hoặc 'auto'/None để tự nhận diện).
        word_timestamps: True để lấy mốc thời gian chi tiết đến từng từ (phục vụ hiệu ứng chữ TikTok).
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ).

    Returns:
        List[Dict[str, Any]]: Danh sách các phân đoạn câu thoại:
        [
            {
                "index": 0,
                "start": 0.0,
                "end": 2.15,
                "text": "大家好，今天分享一个实用小技巧",
                "words": [{"word": "大家", "start": 0.0, "end": 0.5}, ...]
            }
        ]
    """
    audio_file = Path(audio_path).resolve()
    if not audio_file.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp âm thanh đầu vào: {audio_path}")

    if progress_callback:
        progress_callback("Đang nạp mô hình nhận diện giọng nói faster-whisper...", 10.0)

    model = get_whisper_model()

    # Chuẩn hóa mã ngôn ngữ (nếu auto thì để None để model tự phát hiện)
    lang = None if (not language or language.lower() in ("auto", "none")) else language.lower()

    if progress_callback:
        progress_callback("Đang bóc tách câu thoại và mốc thời gian...", 30.0)

    try:
        segments, info = model.transcribe(
            str(audio_file),
            language=lang,
            word_timestamps=word_timestamps,
            beam_size=5,
            vad_filter=True, # Bật bộ lọc phát hiện hoạt động giọng nói (bỏ qua khoảng lặng)
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        results = []
        for idx, segment in enumerate(segments):
            seg_data = {
                "index": idx,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "words": []
            }

            if word_timestamps and segment.words:
                for w in segment.words:
                    seg_data["words"].append({
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 2)
                    })

            results.append(seg_data)

            if progress_callback:
                progress_callback(f"Đã nhận diện: [{seg_data['start']}s - {seg_data['end']}s] {seg_data['text']}", 70.0)

        if progress_callback:
            progress_callback(f"Nhận diện hoàn tất: {len(results)} câu thoại.", 100.0)

        return results

    except Exception as e:
        raise TranscriptionError(f"Lỗi trong quá trình nhận diện âm thanh: {str(e)}") from e
